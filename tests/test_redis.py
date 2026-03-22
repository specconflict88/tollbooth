import random
import time

import pytest

try:
    import redis as _redis_mod

    _client = _redis_mod.Redis(host="127.0.0.1", port=6379, db=0)
    _client.ping()
    HAS_REDIS = True
except Exception:
    _redis_mod = None
    HAS_REDIS = False

pytestmark = pytest.mark.skipif(
    not HAS_REDIS,
    reason="Redis not available at 127.0.0.1:6379",
)

PREFIX = "tollbooth:test"


@pytest.fixture
def client():
    c = _redis_mod.Redis(host="127.0.0.1", port=6379, db=0)
    yield c
    for key in c.scan_iter(f"{PREFIX}*"):
        c.delete(key)


class TestRedisStore:
    def test_set_get(self, client):
        from tollbooth.engine import Challenge
        from tollbooth.redis import RedisStore

        store = RedisStore(client, PREFIX)
        ch = Challenge(
            id="test-1",
            random_data="abcd",
            difficulty=10,
            ip_hash="hash",
            created_at=time.time(),
        )
        store.set(ch)
        got = store.get("test-1")
        assert got is not None
        assert got.id == "test-1"
        assert got.difficulty == 10

    def test_get_missing(self, client):
        from tollbooth.redis import RedisStore

        store = RedisStore(client, PREFIX)
        assert store.get("nonexistent") is None

    def test_ttl_set(self, client):
        from tollbooth.engine import Challenge
        from tollbooth.redis import RedisStore

        store = RedisStore(client, PREFIX, ttl=60)
        ch = Challenge(
            id="ttl-test",
            random_data="x",
            difficulty=1,
            ip_hash="h",
            created_at=time.time(),
        )
        store.set(ch)
        ttl = client.ttl(f"{PREFIX}:c:ttl-test")
        assert 0 < ttl <= 60


class TestRedisEngine:
    def test_create_with_secret(self, client):
        from tollbooth.redis import RedisEngine

        engine = RedisEngine(
            client,
            secret="test-secret",
            prefix=PREFIX,
            auto_sync=False,
        )
        assert client.get(f"{PREFIX}:secret") == b"test-secret"
        assert engine.secret == b"test-secret"

    def test_load_secret_from_redis(self, client):
        from tollbooth.redis import RedisEngine

        RedisEngine(
            client,
            secret="shared",
            prefix=PREFIX,
            auto_sync=False,
        )
        engine2 = RedisEngine(
            client,
            prefix=PREFIX,
            auto_sync=False,
        )
        assert engine2.secret == b"shared"

    def test_no_secret_raises(self, client):
        from tollbooth.redis import RedisEngine

        with pytest.raises(ValueError, match="No secret"):
            RedisEngine(
                client,
                prefix=f"{PREFIX}:empty",
                auto_sync=False,
            )

    def test_config_sync(self, client):
        from tollbooth.redis import RedisEngine

        e1 = RedisEngine(
            client,
            secret="s",
            prefix=PREFIX,
            auto_sync=False,
        )
        e2 = RedisEngine(
            client,
            prefix=PREFIX,
            auto_sync=False,
        )

        e1.update_policy(default_difficulty=20)
        e2.sync()
        assert e2.policy.default_difficulty == 20

    def test_rules_sync(self, client):
        from tollbooth.engine import Rule
        from tollbooth.redis import RedisEngine

        e1 = RedisEngine(
            client,
            secret="s",
            prefix=PREFIX,
            auto_sync=False,
        )
        e2 = RedisEngine(
            client,
            prefix=PREFIX,
            auto_sync=False,
        )

        new_rules = [
            Rule(name="test", action="deny", path="/x"),
        ]
        e1.update_rules(new_rules)
        e2.sync()
        assert len(e2.policy.rules) == 1
        assert e2.policy.rules[0].name == "test"

    def test_secret_sync(self, client):
        from tollbooth.redis import RedisEngine

        e1 = RedisEngine(
            client,
            secret="old",
            prefix=PREFIX,
            auto_sync=False,
        )
        e2 = RedisEngine(
            client,
            prefix=PREFIX,
            auto_sync=False,
        )

        e1.update_secret("new-secret")
        e2.sync()
        assert e2.secret == b"new-secret"

    def test_challenge_shared(self, client):
        from tollbooth.redis import RedisEngine

        e1 = RedisEngine(
            client,
            secret="s",
            prefix=PREFIX,
            auto_sync=False,
        )
        e2 = RedisEngine(
            client,
            prefix=PREFIX,
            auto_sync=False,
        )

        request = {
            "method": "GET",
            "path": "/",
            "query": "",
            "user_agent": "",
            "remote_addr": "1.2.3.4",
            "headers": {},
            "cookies": {},
            "form": {},
        }
        ch = e1.issue_challenge(10, request)
        got = e2.store.get(ch.id)
        assert got is not None
        assert got.id == ch.id


BLOCKLIST_SAMPLE = """
1.0.0.0/24
10.0.0.1-10.0.0.50
192.168.1.0/24
2001:db8::1
2001:db8:1::/48
"""


class TestRedisIPBlocklist:
    def test_load_and_contains(self, client):
        import tempfile
        from pathlib import Path

        from tollbooth.redis import RedisIPBlocklist

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            f.write(BLOCKLIST_SAMPLE)
            path = f.name

        bl = RedisIPBlocklist(client, PREFIX)
        bl.load(path)
        Path(path).unlink()

        assert bl.contains("1.0.0.100")
        assert bl.contains("10.0.0.25")
        assert bl.contains("192.168.1.1")
        assert not bl.contains("8.8.8.8")
        assert not bl.contains("10.0.0.51")

    def test_v6_lookup(self, client):
        import tempfile
        from pathlib import Path

        from tollbooth.redis import RedisIPBlocklist

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            f.write(BLOCKLIST_SAMPLE)
            path = f.name

        bl = RedisIPBlocklist(client, PREFIX)
        bl.load(path)
        Path(path).unlink()

        assert bl.contains("2001:db8::1")
        assert bl.contains("2001:db8:1::abcd")
        assert not bl.contains("2001:db8:2::1")

    def test_invalid_ip(self, client):
        from tollbooth.redis import RedisIPBlocklist

        bl = RedisIPBlocklist(client, PREFIX)
        assert not bl.contains("invalid")

    def test_len(self, client):
        import tempfile
        from pathlib import Path

        from tollbooth.redis import RedisIPBlocklist

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            f.write(BLOCKLIST_SAMPLE)
            path = f.name

        bl = RedisIPBlocklist(client, PREFIX)
        bl.load(path)
        Path(path).unlink()

        assert len(bl) > 0

    def test_lookup_speed(self, client):
        import tempfile
        from pathlib import Path

        from tollbooth.redis import RedisIPBlocklist

        lines = [f"{i}.{j}.0.0/16" for i in range(1, 21) for j in range(256)]
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            f.write("\n".join(lines))
            path = f.name

        bl = RedisIPBlocklist(client, PREFIX)
        bl.load(path)
        Path(path).unlink()

        ips = [f"{i}.{j}.1.1" for i in range(1, 21) for j in range(0, 256, 25)]
        start = time.perf_counter()
        for ip in ips:
            bl.contains(ip)
        elapsed = time.perf_counter() - start
        ops = len(ips) / elapsed
        print(f"\n  Redis Lua: {ops:,.0f} lookups/sec")
        assert ops > 500


@pytest.mark.slow
class TestRedisFullDataset:
    @pytest.fixture(scope="class")
    def redis_blocklist(self):
        from tollbooth.blocklist import BLOCKLIST_URL
        from tollbooth.redis import RedisIPBlocklist

        c = _redis_mod.Redis(host="127.0.0.1", port=6379, db=0)
        prefix = f"{PREFIX}:full"
        bl = RedisIPBlocklist(c, prefix)
        try:
            bl.load(BLOCKLIST_URL)
        except Exception as e:
            pytest.skip(f"Blocklist download failed: {e}")
        yield bl
        for key in c.scan_iter(f"{prefix}*"):
            c.delete(key)

    def test_load(self, redis_blocklist):
        count = len(redis_blocklist)
        assert count > 100_000
        print(f"\n  Redis entries: {count:,}")

    def test_ipv4_lookup_speed(self, redis_blocklist):
        random.seed(42)
        ips = [
            f"{random.randint(0,255)}"
            f".{random.randint(0,255)}"
            f".{random.randint(0,255)}"
            f".{random.randint(0,255)}"
            for _ in range(5_000)
        ]
        start = time.perf_counter()
        hits = sum(redis_blocklist.contains(ip) for ip in ips)
        elapsed = time.perf_counter() - start
        ops = len(ips) / elapsed
        print(
            f"\n  Redis IPv4:"
            f" {ops:,.0f} lookups/sec"
            f"  ({hits:,} hits / {len(ips):,})"
        )
        assert ops > 1_000

    def test_ipv6_lookup_speed(self, redis_blocklist):
        random.seed(42)
        ips = [
            f"2001:db8:{random.randint(0,0xffff):x}" f"::{random.randint(0,0xffff):x}"
            for _ in range(2_000)
        ]
        start = time.perf_counter()
        hits = sum(redis_blocklist.contains(ip) for ip in ips)
        elapsed = time.perf_counter() - start
        ops = len(ips) / elapsed
        print(
            f"\n  Redis IPv6:"
            f" {ops:,.0f} lookups/sec"
            f"  ({hits:,} hits / {len(ips):,})"
        )
        assert ops > 1_000
