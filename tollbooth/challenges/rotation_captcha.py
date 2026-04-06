import base64
import hashlib
import hmac
import json
import math
import secrets
import struct
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from .base import DIFFICULTY_OFFSETS, ChallengeBase, ChallengeHandler, ChallengeType

_TOKEN_TTL = 1800
_DEG = math.pi / 180
_MODELS_DIR = Path(__file__).parent / "models"


def _v3sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _v3cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _v3dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _v3normalize(v):
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if length < 1e-10:
        return [0.0, 0.0, 0.0]
    return [v[0] / length, v[1] / length, v[2] / length]


def _v3scale(v, s):
    return [v[0] * s, v[1] * s, v[2] * s]


def _v3add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mat4_identity():
    m = [0.0] * 16
    m[0] = m[5] = m[10] = m[15] = 1.0
    return m


def _mat4_multiply(a, b):
    o = [0.0] * 16
    for c in range(4):
        for r in range(4):
            o[c * 4 + r] = (
                a[r] * b[c * 4]
                + a[4 + r] * b[c * 4 + 1]
                + a[8 + r] * b[c * 4 + 2]
                + a[12 + r] * b[c * 4 + 3]
            )
    return o


def _mat4_rotate_y(angle):
    m = _mat4_identity()
    c, s = math.cos(angle), math.sin(angle)
    m[0] = c
    m[8] = s
    m[2] = -s
    m[10] = c
    return m


def _mat4_translate(x, y, z):
    m = _mat4_identity()
    m[12] = x
    m[13] = y
    m[14] = z
    return m


def _mat4_look_at(eye, center, up):
    f = _v3normalize(_v3sub(center, eye))
    r = _v3normalize(_v3cross(f, up))
    u = _v3cross(r, f)
    m = [0.0] * 16
    m[0] = r[0]
    m[4] = r[1]
    m[8] = r[2]
    m[12] = -_v3dot(r, eye)
    m[1] = u[0]
    m[5] = u[1]
    m[9] = u[2]
    m[13] = -_v3dot(u, eye)
    m[2] = -f[0]
    m[6] = -f[1]
    m[10] = -f[2]
    m[14] = _v3dot(f, eye)
    m[3] = 0.0
    m[7] = 0.0
    m[11] = 0.0
    m[15] = 1.0
    return m


def _mat4_perspective(fov_deg, aspect, near, far):
    f = 1.0 / math.tan((fov_deg * _DEG) / 2)
    nf = 1.0 / (near - far)
    m = [0.0] * 16
    m[0] = f / aspect
    m[5] = f
    m[10] = (far + near) * nf
    m[11] = -1.0
    m[14] = 2.0 * far * near * nf
    return m


def _transform_point(m, p):
    x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12]
    y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13]
    z = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]
    w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15]
    return [x, y, z, w]


def _clip_to_screen(clip, size):
    if clip[3] <= 0:
        return None
    inv_w = 1.0 / clip[3]
    return [
        (clip[0] * inv_w * 0.5 + 0.5) * size,
        (1.0 - (clip[1] * inv_w * 0.5 + 0.5)) * size,
        clip[2] * inv_w,
        clip[3],
    ]


def _imul(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def _create_rng(seed):
    state = [seed & 0xFFFFFFFF]

    def next_float():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        s = state[0]
        t = _imul(s ^ (s >> 15), 1 | s)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return next_float


_mesh_cache = None


def _load_mesh(gltf_path=None):
    global _mesh_cache
    if _mesh_cache is not None:
        return _mesh_cache

    if gltf_path is None:
        gltf_path = _MODELS_DIR / "scene.gltf"
    gltf_path = Path(gltf_path)

    with open(gltf_path) as f:
        gltf = json.load(f)

    bin_path = gltf_path.parent / gltf["buffers"][0]["uri"]
    with open(bin_path, "rb") as f:
        bin_data = f.read()

    primitive = gltf["meshes"][0]["primitives"][0]
    pos_acc = gltf["accessors"][primitive["attributes"]["POSITION"]]
    norm_acc = gltf["accessors"][primitive["attributes"]["NORMAL"]]
    idx_acc = gltf["accessors"][primitive["indices"]]

    def read_accessor(accessor, fmt_char, components):
        bv = gltf["bufferViews"][accessor["bufferView"]]
        byte_offset = bv.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        elem_size = struct.calcsize(fmt_char)
        stride = bv.get("byteStride", components * elem_size)
        count = accessor["count"]

        result = []
        for i in range(count):
            src = byte_offset + i * stride
            for c in range(components):
                offset = src + c * elem_size
                result.append(struct.unpack_from(f"<{fmt_char}", bin_data, offset)[0])
        return result

    positions = read_accessor(pos_acc, "f", 3)
    normals = read_accessor(norm_acc, "f", 3)

    idx_type = idx_acc.get("componentType", 5125)
    idx_fmt = {5121: "B", 5123: "H", 5125: "I"}.get(idx_type, "I")
    indices = read_accessor(idx_acc, idx_fmt, 1)

    vertex_count = pos_acc["count"]
    triangle_count = idx_acc["count"] // 3

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    for i in range(vertex_count):
        x, y, z = positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]
        min_x, max_x = min(min_x, x), max(max_x, x)
        min_y, max_y = min(min_y, y), max(max_y, y)
        min_z, max_z = min(min_z, z), max(max_z, z)

    center_x = (min_x + max_x) / 2
    center_y = min_y
    center_z = (min_z + max_z) / 2
    extent_x = (max_x - min_x) / 2
    extent_y = max_y - min_y
    extent_z = (max_z - min_z) / 2
    max_extent = max(extent_x, extent_y, extent_z)
    scale = 1.0 / max_extent if max_extent > 0 else 1.0

    for i in range(vertex_count):
        positions[i * 3] = (positions[i * 3] - center_x) * scale
        positions[i * 3 + 1] = (positions[i * 3 + 1] - center_y) * scale
        positions[i * 3 + 2] = (positions[i * 3 + 2] - center_z) * scale

    _mesh_cache = {
        "positions": positions,
        "normals": normals,
        "indices": indices,
        "vertex_count": vertex_count,
        "triangle_count": triangle_count,
        "height": extent_y * scale,
    }
    return _mesh_cache


def _sample_mesh_surface(mesh, count, rng):
    positions = mesh["positions"]
    normals = mesh["normals"]
    indices = mesh["indices"]
    triangle_count = mesh["triangle_count"]

    areas = []
    total_area = 0.0

    for t in range(triangle_count):
        i0 = indices[t * 3] * 3
        i1 = indices[t * 3 + 1] * 3
        i2 = indices[t * 3 + 2] * 3

        ax = positions[i1] - positions[i0]
        ay = positions[i1 + 1] - positions[i0 + 1]
        az = positions[i1 + 2] - positions[i0 + 2]
        bx = positions[i2] - positions[i0]
        by = positions[i2 + 1] - positions[i0 + 1]
        bz = positions[i2 + 2] - positions[i0 + 2]

        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx
        area = math.sqrt(cx * cx + cy * cy + cz * cz) * 0.5
        areas.append(area)
        total_area += area

    if total_area == 0:
        total_area = 1.0

    cdf = []
    running = 0.0
    for a in areas:
        running += a / total_area
        cdf.append(running)

    points = []
    point_normals = []

    for _ in range(count):
        r = rng()
        lo, hi = 0, triangle_count - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            if cdf[mid] < r:
                lo = mid + 1
            else:
                hi = mid
        tri_idx = lo

        u, v = rng(), rng()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        w = 1 - u - v

        i0 = indices[tri_idx * 3] * 3
        i1 = indices[tri_idx * 3 + 1] * 3
        i2 = indices[tri_idx * 3 + 2] * 3

        for c in range(3):
            points.append(
                positions[i0 + c] * w + positions[i1 + c] * u + positions[i2 + c] * v
            )
            point_normals.append(
                normals[i0 + c] * w + normals[i1 + c] * u + normals[i2 + c] * v
            )

    return {"points": points, "normals": point_normals, "count": count}


def _build_matrices(mesh, angle_deg, fov, camera_distance, camera_elevation):
    angle_rad = angle_deg * _DEG
    model = _mat4_multiply(_mat4_translate(0, 0, 0), _mat4_rotate_y(angle_rad))
    model_center_y = mesh["height"] / 2

    eye_y = model_center_y + camera_distance * math.sin(camera_elevation)
    eye_horiz = camera_distance * math.cos(camera_elevation)
    eye = [0.0, eye_y, eye_horiz]
    target = [0.0, model_center_y * 0.85, 0.0]

    view = _mat4_look_at(eye, target, [0.0, 1.0, 0.0])
    proj = _mat4_perspective(fov, 1.0, 0.1, 100.0)
    vp = _mat4_multiply(proj, view)
    mvp = _mat4_multiply(vp, model)

    return {"model": model, "vp": vp, "mvp": mvp, "eye": eye}


def _np_add_noise(arr, scale, seed):
    import numpy as np

    rng = np.random.default_rng(seed)
    noise = (rng.random(arr.shape, dtype=np.float32) - 0.5) * scale
    return np.clip(arr.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def _np_radial_gradient(radius, color_stops):
    import numpy as np
    from PIL import Image

    d = radius * 2
    yy, xx = np.mgrid[0:d, 0:d]
    dx = xx - radius + 0.5
    dy = yy - radius + 0.5
    dist = np.sqrt(dx * dx + dy * dy) / radius

    out = np.zeros((d, d, 4), dtype=np.float32)
    for i in range(len(color_stops) - 1):
        t0, c0 = color_stops[i]
        t1, c1 = color_stops[i + 1]
        mask = (dist >= t0) & (dist < t1)
        if not mask.any():
            continue
        f = np.where(t1 > t0, (dist - t0) / (t1 - t0), 0.0)
        for ch in range(4):
            out[..., ch] = np.where(
                mask,
                out[..., ch] + (c0[ch] + (c1[ch] - c0[ch]) * f),
                out[..., ch],
            )

    out[dist >= 1.0] = 0
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def _make_splat_template(radius, alpha_base=0.3):
    a0 = int((alpha_base + 0.15) * 255)
    a1 = int(alpha_base * 255)
    a2 = int(alpha_base * 0.4 * 255)

    return _np_radial_gradient(
        radius,
        [
            (0.0, (255, 255, 255, a0)),
            (0.35, (235, 240, 245, a1)),
            (0.7, (200, 210, 220, a2)),
            (1.0, (180, 190, 200, 0)),
        ],
    )


def _render_reference(mesh, angle_deg, size=300):
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise ImportError(
            "Pillow and numpy are required for RotationCaptcha: "
            "pip install tollbooth[image]"
        ) from e

    fov = 45
    camera_distance = 3.2
    camera_elevation = 0.35
    light_dir = _v3normalize([0.5, 0.8, 0.6])
    shadow_dir = _v3normalize([-0.4, -1.0, -0.3])
    ambient = 0.3
    base_color = [200, 175, 145]

    matrices = _build_matrices(mesh, angle_deg, fov, camera_distance, camera_elevation)
    model = matrices["model"]
    vp = matrices["vp"]
    eye = matrices["eye"]

    ys = np.linspace(0, 1, size, dtype=np.float32)
    bg = np.stack(
        [
            (232 * (1 - ys) + 192 * ys).astype(np.uint8),
            (228 * (1 - ys) + 188 * ys).astype(np.uint8),
            (224 * (1 - ys) + 184 * ys).astype(np.uint8),
        ],
        axis=1,
    )
    bg_arr = np.repeat(bg[:, np.newaxis, :], size, axis=1)
    img = Image.fromarray(bg_arr, "RGB")

    positions = mesh["positions"]
    indices = mesh["indices"]
    triangle_count = mesh["triangle_count"]

    triangles = []
    shadows = []

    for t in range(triangle_count):
        idx = [indices[t * 3], indices[t * 3 + 1], indices[t * 3 + 2]]

        world_pos = []
        for i in idx:
            p = [positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]]
            tp = _transform_point(model, p)
            world_pos.append([tp[0], tp[1], tp[2]])

        edge1 = _v3sub(world_pos[1], world_pos[0])
        edge2 = _v3sub(world_pos[2], world_pos[0])
        face_normal = _v3normalize(_v3cross(edge1, edge2))

        tri_center = _v3scale(
            _v3add(_v3add(world_pos[0], world_pos[1]), world_pos[2]),
            1.0 / 3.0,
        )
        to_camera = _v3normalize(_v3sub(eye, tri_center))

        if _v3dot(face_normal, to_camera) < 0:
            face_normal = [-face_normal[0], -face_normal[1], -face_normal[2]]

        screen_verts = []
        skip = False
        for wp in world_pos:
            clip = _transform_point(vp, wp)
            sv = _clip_to_screen(clip, size)
            if sv is None:
                skip = True
                break
            screen_verts.append(sv)

        if skip:
            continue

        diff = max(0.0, _v3dot(face_normal, light_dir))
        brightness = ambient + (1 - ambient) * diff
        color = tuple(min(255, round(base_color[c] * brightness)) for c in range(3))

        avg_z = sum(sv[2] for sv in screen_verts) / 3
        triangles.append((screen_verts, color, avg_z))

        shadow_verts = []
        shadow_ok = True
        for wp in world_pos:
            if shadow_dir[1] >= 0:
                shadow_ok = False
                break
            t_val = (0.0 - wp[1]) / shadow_dir[1]
            if t_val < 0:
                shadow_ok = False
                break
            sp = [
                wp[0] + shadow_dir[0] * t_val,
                0.0,
                wp[2] + shadow_dir[2] * t_val,
            ]
            clip = _transform_point(vp, sp)
            sv = _clip_to_screen(clip, size)
            if sv is None:
                shadow_ok = False
                break
            shadow_verts.append(sv)

        if shadow_ok:
            shadows.append((shadow_verts, avg_z + 100))

    shadows.sort(key=lambda s: -s[1])
    shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    for verts, _ in shadows:
        poly = [(v[0], v[1]) for v in verts]
        shadow_draw.polygon(poly, fill=(60, 55, 50, 51))
    img = Image.alpha_composite(img.convert("RGBA"), shadow_layer)

    tri_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tri_draw = ImageDraw.Draw(tri_layer)
    triangles.sort(key=lambda t: -t[2])
    for verts, color, _ in triangles:
        poly = [(v[0], v[1]) for v in verts]
        tri_draw.polygon(poly, fill=(*color, 255))
    img = Image.alpha_composite(img, tri_layer).convert("RGB")

    small_size = round(size * 0.45)
    img = img.resize((small_size, small_size), Image.Resampling.BILINEAR).resize(
        (size, size), Image.Resampling.BILINEAR
    )

    arr = _np_add_noise(np.array(img), 35, int(angle_deg * 997))
    img = Image.fromarray(arr)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_splat(mesh, angle_deg, seed, size=300):
    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        raise ImportError(
            "Pillow and numpy are required for RotationCaptcha: "
            "pip install tollbooth[image]"
        ) from e

    fov = 45
    camera_distance = 3.2
    camera_elevation = 0.35
    splat_count = 1200
    splat_world_radius = 0.055

    rng = _create_rng(seed)
    samples = _sample_mesh_surface(mesh, splat_count, rng)

    img = Image.new("RGBA", (size, size), (26, 28, 46, 255))

    bg_count = 55
    cols = math.ceil(math.sqrt(bg_count))
    cell_size = size / cols
    for i in range(bg_count):
        col = i % cols
        row = i // cols
        sx = (col + 0.3 + rng() * 0.4) * cell_size
        sy = (row + 0.3 + rng() * 0.4) * cell_size
        sr = max(2, int(18 + rng() * 30))
        warmth = rng()
        alpha = 0.1 + rng() * 0.2

        cr = int(200 + warmth * 55)
        cg = int(205 + warmth * 40)
        cb = int(215 + warmth * 25)
        a = int(alpha * 255)
        a2 = int(alpha * 0.5 * 255)

        bg_grad = _np_radial_gradient(
            sr,
            [
                (0.0, (cr, cg, cb, a)),
                (0.5, (cr - 40, cg - 35, cb - 30, a2)),
                (1.0, (cr - 80, cg - 70, cb - 60, 0)),
            ],
        )
        img.alpha_composite(bg_grad, (int(sx - sr), int(sy - sr)))

    matrices = _build_matrices(mesh, angle_deg, fov, camera_distance, camera_elevation)
    mvp = matrices["mvp"]
    focal_len = size / (2 * math.tan((fov * _DEG) / 2))

    projected = []
    for i in range(samples["count"]):
        p = [
            samples["points"][i * 3],
            samples["points"][i * 3 + 1],
            samples["points"][i * 3 + 2],
        ]
        clip = _transform_point(mvp, p)
        if clip[3] <= 0.01:
            continue

        screen = _clip_to_screen(clip, size)
        if screen is None:
            continue

        screen_radius = max(4, (splat_world_radius * focal_len) / clip[3])
        projected.append((screen[0], screen[1], screen[2], screen_radius))

    projected.sort(key=lambda s: -s[2])

    splat_cache = {}
    for x, y, _, radius in projected:
        rng()
        r_int = max(2, int(radius))

        if r_int not in splat_cache:
            splat_cache[r_int] = _make_splat_template(r_int)

        template = splat_cache[r_int]
        img.alpha_composite(template, (int(x - r_int), int(y - r_int)))

    decoy_count = 25 + int(rng() * 20)
    for _ in range(decoy_count):
        dx, dy = rng() * size, rng() * size
        dr = max(2, int(4 + rng() * 10))
        da = 0.08 + rng() * 0.18

        a0 = int((da + 0.1) * 255)
        a1 = int(da * 0.5 * 255)
        decoy = _np_radial_gradient(
            dr,
            [
                (0.0, (250, 252, 255, a0)),
                (0.5, (220, 225, 235, a1)),
                (1.0, (200, 210, 220, 0)),
            ],
        )
        img.alpha_composite(decoy, (int(dx - dr), int(dy - dr)))

    img_rgb = img.convert("RGB")
    arr = _np_add_noise(np.array(img_rgb), 22, seed + 3571)
    img_rgb = Image.fromarray(arr)

    buf = BytesIO()
    img_rgb.save(buf, format="PNG")
    return buf.getvalue()


def _render_sprite_sheet(mesh, angles, seed, size=300):
    from concurrent.futures import ThreadPoolExecutor

    from PIL import Image

    def render_frame(args):
        i, angle = args
        return i, Image.open(BytesIO(_render_splat(mesh, angle, seed + i * 7919, size)))

    count = len(angles)
    sheet = Image.new("RGB", (size * count, size))

    with ThreadPoolExecutor() as pool:
        for i, tile in pool.map(render_frame, enumerate(angles)):
            sheet.paste(tile, (i * size, 0))

    buf = BytesIO()
    sheet.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@dataclass
class RotationCaptcha(ChallengeHandler):
    choice_count: int = 6
    image_size: int = 300
    token_ttl: int = _TOKEN_TTL
    secret: bytes = field(
        default_factory=lambda: secrets.token_bytes(32),
    )

    @property
    def challenge_type(self) -> ChallengeType:
        return ChallengeType.ROTATION_CAPTCHA

    def to_difficulty(self, base: int) -> int:
        return base + DIFFICULTY_OFFSETS[self.challenge_type]

    @property
    def template(self) -> str:
        return (
            Path(__file__).parent / "templates" / "rotation_captcha.html"
        ).read_text()

    def _sign(self, payload: str) -> str:
        return hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()

    def _encrypt(self, plaintext: str, iv: str) -> str:
        key = hmac.new(self.secret, iv.encode(), hashlib.sha256).digest()
        return bytes(a ^ b for a, b in zip(plaintext.encode(), key)).hex()

    def _decrypt_token(self, token: str) -> str:
        iv, ct_hex, ts, nonce, sig = token.split(":")
        payload = f"{iv}:{ct_hex}:{ts}:{nonce}"
        if not hmac.compare_digest(self._sign(payload), sig):
            raise ValueError("invalid signature")
        if time.time() - int(ts) > self.token_ttl:
            raise ValueError("token expired")
        key = hmac.new(self.secret, iv.encode(), hashlib.sha256).digest()
        return bytes(a ^ b for a, b in zip(bytes.fromhex(ct_hex), key)).decode()

    def generate_random_data(self, difficulty: int = 0) -> str:
        seed = secrets.randbelow(2**31)
        rng = _create_rng(seed)
        step_size = 360 / self.choice_count

        correct_idx = int(rng() * self.choice_count)
        base_angle = int(rng() * 360)

        angles = [(base_angle + i * step_size) % 360 for i in range(self.choice_count)]
        correct_angle = angles[correct_idx]

        solution = f"{correct_idx}:{seed}:{base_angle}"
        iv = secrets.token_hex(16)
        ct = self._encrypt(solution, iv)
        ts = str(int(time.time()))
        nonce = secrets.token_hex(8)
        payload = f"{iv}:{ct}:{ts}:{nonce}"
        return f"{payload}:{self._sign(payload)}"

    @property
    def retry_on_failure(self) -> bool:
        return True

    def nonce_from_form(self, raw: str) -> str:
        return raw.strip()

    def verify(self, random_data: str, nonce: int | str, difficulty: int) -> bool:
        try:
            solution = self._decrypt_token(random_data)
            correct_idx = int(solution.split(":")[0])
            return int(nonce) == correct_idx
        except Exception:
            return False

    def render_payload(
        self,
        challenge: ChallengeBase,
        verify_path: str,
        redirect: str,
    ) -> dict:
        solution = self._decrypt_token(challenge.random_data)
        correct_idx, seed, base_angle = solution.split(":")
        correct_idx = int(correct_idx)
        seed = int(seed)
        base_angle = int(base_angle)

        mesh = _load_mesh()
        step_size = 360 / self.choice_count
        angles = [(base_angle + i * step_size) % 360 for i in range(self.choice_count)]

        correct_angle = angles[correct_idx]
        reference_b64 = base64.b64encode(
            _render_reference(mesh, correct_angle, self.image_size)
        ).decode()

        sheet_bytes = _render_sprite_sheet(mesh, angles, seed, self.image_size)
        sheet_b64 = base64.b64encode(sheet_bytes).decode()

        return {
            "id": challenge.id,
            "reference": reference_b64,
            "sheet": sheet_b64,
            "choiceCount": self.choice_count,
            "verifyPath": verify_path,
            "redirect": redirect,
        }
