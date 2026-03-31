import re
from pathlib import Path

from ..engine import ACCENT_COLOR as _DEFAULT_ACCENT

_DEFAULT_TEMPLATE = (Path(__file__).parent / "templates" / "error.html").read_text()

ERROR_CODES: dict[int, dict[str, str]] = {
    400: {
        "title": "Bad Request",
        "description": (
            "The server could not understand the request due to invalid syntax."
        ),
    },
    401: {
        "title": "Unauthorized",
        "description": "You must authenticate yourself to get the requested response.",
    },
    403: {
        "title": "Forbidden",
        "description": "You do not have access rights to the content.",
    },
    404: {
        "title": "Not Found",
        "description": "The server cannot find the requested resource.",
    },
    405: {
        "title": "Method Not Allowed",
        "description": (
            "The request method is known by the server but is not supported "
            "by the target resource."
        ),
    },
    406: {
        "title": "Not Acceptable",
        "description": (
            "The server cannot produce a response matching the acceptable "
            "values defined in your request headers."
        ),
    },
    408: {
        "title": "Request Timeout",
        "description": (
            "The server did not receive a complete request within the time "
            "it was prepared to wait."
        ),
    },
    409: {
        "title": "Conflict",
        "description": (
            "The request could not be completed due to a conflict with the "
            "current state of the target resource."
        ),
    },
    410: {
        "title": "Gone",
        "description": (
            "The requested resource is no longer available and will not be "
            "available again."
        ),
    },
    411: {
        "title": "Length Required",
        "description": (
            "The server refuses to accept the request without a defined "
            "Content-Length header."
        ),
    },
    412: {
        "title": "Precondition Failed",
        "description": (
            "The server does not meet one of the preconditions in your "
            "request header fields."
        ),
    },
    413: {
        "title": "Payload Too Large",
        "description": "The request entity is larger than limits defined by the server.",
    },
    414: {
        "title": "URI Too Long",
        "description": (
            "The URI requested is longer than the server is willing to interpret."
        ),
    },
    415: {
        "title": "Unsupported Media Type",
        "description": (
            "The media format of the requested data is not supported by the server."
        ),
    },
    416: {
        "title": "Range Not Satisfiable",
        "description": (
            "The range specified by the Range header field in the request "
            "cannot be fulfilled."
        ),
    },
    417: {
        "title": "Expectation Failed",
        "description": (
            "The expectation given in the request Expect header could not "
            "be met by the server."
        ),
    },
    418: {
        "title": "I'm a Teapot",
        "description": "The server refuses to brew coffee because it is a teapot.",
    },
    422: {
        "title": "Unprocessable Entity",
        "description": (
            "The request was well-formed but could not be followed due to "
            "semantic errors."
        ),
    },
    423: {
        "title": "Locked",
        "description": "The resource that is being accessed is locked.",
    },
    424: {
        "title": "Failed Dependency",
        "description": "The request failed due to failure of a previous request.",
    },
    428: {
        "title": "Precondition Required",
        "description": "The origin server requires the request to be conditional.",
    },
    429: {
        "title": "Too Many Requests",
        "description": "You have sent too many requests in a given amount of time.",
    },
    431: {
        "title": "Request Header Fields Too Large",
        "description": (
            "The server is unwilling to process the request because its "
            "header fields are too large."
        ),
    },
    451: {
        "title": "Unavailable For Legal Reasons",
        "description": (
            "The server is denying access to the resource as a consequence "
            "of a legal demand."
        ),
    },
    500: {
        "title": "Internal Server Error",
        "description": (
            "The server encountered a situation it does not know how to handle."
        ),
    },
    501: {
        "title": "Not Implemented",
        "description": (
            "The request method is not supported by the server and cannot "
            "be handled."
        ),
    },
    502: {
        "title": "Bad Gateway",
        "description": (
            "The server, acting as a gateway or proxy, received an invalid "
            "response from the upstream server."
        ),
    },
    503: {
        "title": "Service Unavailable",
        "description": "The server is not ready to handle the request.",
    },
    504: {
        "title": "Gateway Timeout",
        "description": (
            "The server, acting as a gateway or proxy, did not receive a "
            "timely response from the upstream server."
        ),
    },
    505: {
        "title": "HTTP Version Not Supported",
        "description": (
            "The HTTP version used in the request is not supported by the server."
        ),
    },
}


def _render(
    code: int,
    template: str,
    templates: dict[int, str],
    overrides: dict[int, dict],
    accent_color: str,
    **extra,
) -> str:
    info = overrides.get(code, ERROR_CODES.get(code, {}))
    tmpl = templates.get(code, template)
    ctx = {
        "status_code": str(code),
        "title": info.get("title", "Error"),
        "description": info.get("description", "An error occurred."),
        "ACCENT_COLOR": accent_color,
        **extra,
    }
    return re.sub(r"\{\{(\w+)\}\}", lambda m: ctx.get(m.group(1), m.group(0)), tmpl)


class ErrorHandler:
    """Standalone HTTP error handler with template rendering and multi-framework support.

    Renders HTML error pages for 30 HTTP error codes (400–505) using a customizable
    template. Template variables use ``{{key}}`` syntax: ``{{status_code}}``,
    ``{{title}}``, ``{{description}}``, ``{{ACCENT_COLOR}}``, plus any extra kwargs
    passed to ``render()``.

    Usage — Flask (auto-inherits accent color from Tollbooth if registered)::

        eh = ErrorHandler()
        eh.init_flask(app)

    Usage — Django middleware::

        ErrorPageMiddleware = eh.as_django_middleware()
        MIDDLEWARE = ["myapp.middleware.ErrorPageMiddleware", ...]

    Usage — Falcon::

        eh.init_falcon(app)

    Usage — Starlette / FastAPI::

        eh.init_starlette(app)

    Usage — WSGI / ASGI wrap::

        app = eh.wsgi_middleware(app)
        app = eh.asgi_middleware(app)

    Inherit accent color from a Tollbooth instance::

        eh = ErrorHandler(tollbooth=tb)

    Custom accent color::

        eh = ErrorHandler(accent_color="#ff6600")

    Custom global template (string or Path)::

        eh = ErrorHandler(template="<h1>{{status_code}} {{title}}</h1>")
        eh = ErrorHandler(template=Path("templates/error.html"))

    Per-status template (string or Path)::

        eh = ErrorHandler(templates={404: "<h1>Page not found</h1>"})
        eh = ErrorHandler(templates={404: Path("templates/404.html")})

    Override messages::

        eh = ErrorHandler(overrides={404: {"title": "Oops", "description": "..."}})

    Limit which codes are handled::

        eh = ErrorHandler(codes={404, 500})
    """

    def __init__(
        self,
        template: str | Path = _DEFAULT_TEMPLATE,
        templates: dict[int, str | Path] | None = None,
        overrides: dict[int, dict] | None = None,
        codes: set[int] | None = None,
        accent_color: str | None = None,
        tollbooth=None,
    ):
        self._template = (
            template.read_text() if isinstance(template, Path) else template
        )
        self._templates = {
            k: v.read_text() if isinstance(v, Path) else v
            for k, v in (templates or {}).items()
        }
        self._overrides = overrides or {}
        self._codes = codes if codes is not None else set(ERROR_CODES)
        self._accent_color = accent_color or (
            tollbooth.engine.policy.accent_color if tollbooth else None
        )

    def _accent(self, flask_app=None) -> str:
        if self._accent_color:
            return self._accent_color
        if flask_app is not None:
            tb = flask_app.extensions.get("tollbooth")
            if tb and hasattr(tb, "tb"):
                return tb.tb.engine.policy.accent_color
        return _DEFAULT_ACCENT

    def render(self, code: int, **extra) -> str:
        return _render(
            code,
            self._template,
            self._templates,
            self._overrides,
            self._accent_color or _DEFAULT_ACCENT,
            **extra,
        )

    def init_flask(self, app):
        accent = self._accent(app)
        tmpl, tmpls, ovrs = self._template, self._templates, self._overrides

        def handler(exc):
            code = getattr(exc, "code", 500)
            if not isinstance(code, int):
                code = 500
            body = _render(code, tmpl, tmpls, ovrs, accent)
            return body, code, {"Content-Type": "text/html; charset=utf-8"}

        for code in self._codes:
            app.register_error_handler(code, handler)

    def init_falcon(self, app):
        codes = self._codes
        accent = self._accent()
        tmpl, tmpls, ovrs = self._template, self._templates, self._overrides

        def handler(req, resp, exc, params):
            status = exc.status
            code = (
                status.value
                if hasattr(status, "value")
                else int(str(status).split()[0])
            )
            if code not in codes:
                return
            resp.status = status
            resp.content_type = "text/html; charset=utf-8"
            resp.text = _render(code, tmpl, tmpls, ovrs, accent)

        try:
            import falcon

            app.add_error_handler(falcon.HTTPError, handler)
        except ImportError:
            pass

    def init_starlette(self, app):
        codes = self._codes
        accent = self._accent()
        tmpl, tmpls, ovrs = self._template, self._templates, self._overrides

        async def handler(request, exc):
            from starlette.responses import HTMLResponse

            code = getattr(exc, "status_code", 500)
            if not isinstance(code, int):
                code = 500
            return HTMLResponse(
                content=_render(code, tmpl, tmpls, ovrs, accent).encode(),
                status_code=code,
            )

        try:
            from starlette.exceptions import HTTPException

            for code in codes:
                app.add_exception_handler(code, handler)
            app.add_exception_handler(Exception, handler)
        except ImportError:
            pass

    def as_django_middleware(self):
        codes = self._codes
        accent = self._accent()
        tmpl, tmpls, ovrs = self._template, self._templates, self._overrides

        class ErrorPageMiddleware:
            def __init__(self, get_response):
                self.get_response = get_response

            def __call__(self, request):
                response = self.get_response(request)
                if response.status_code not in codes:
                    return response
                from django.http import HttpResponse

                return HttpResponse(
                    _render(response.status_code, tmpl, tmpls, ovrs, accent).encode(),
                    status=response.status_code,
                    content_type="text/html; charset=utf-8",
                )

        return ErrorPageMiddleware

    def wsgi_middleware(self, app):
        codes = self._codes
        accent = self._accent()
        tmpl, tmpls, ovrs = self._template, self._templates, self._overrides

        def middleware(environ, start_response):
            captured = {}

            def fake_start_response(status, headers, exc_info=None):
                captured["status"] = status
                captured["headers"] = list(headers)
                captured["exc_info"] = exc_info
                return lambda data: None

            app_iter = app(environ, fake_start_response)

            if "status" not in captured:
                return app_iter

            status = captured["status"]
            code = int(status.split()[0])
            exc_info = captured.get("exc_info")

            if code not in codes:
                start_response(status, captured["headers"], exc_info)
                return app_iter

            body = _render(code, tmpl, tmpls, ovrs, accent).encode("utf-8")
            start_response(
                status,
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ],
                exc_info,
            )
            if hasattr(app_iter, "close"):
                app_iter.close()
            return [body]

        return middleware

    def asgi_middleware(self, app):
        codes = self._codes
        accent = self._accent()
        tmpl, tmpls, ovrs = self._template, self._templates, self._overrides

        async def middleware(scope, receive, send):
            if scope["type"] != "http":
                await app(scope, receive, send)
                return

            state = {}

            async def capture_send(event):
                if event["type"] == "http.response.start":
                    state["status"] = event["status"]
                    state["replaced"] = event["status"] in codes
                    if not state["replaced"]:
                        await send(event)
                    return

                if event["type"] == "http.response.body":
                    if not state.get("replaced"):
                        await send(event)
                        return
                    if state.get("sent"):
                        return
                    state["sent"] = True
                    body = _render(state["status"], tmpl, tmpls, ovrs, accent).encode(
                        "utf-8"
                    )
                    await send(
                        {
                            "type": "http.response.start",
                            "status": state["status"],
                            "headers": [
                                [b"content-type", b"text/html; charset=utf-8"],
                                [b"content-length", str(len(body)).encode()],
                            ],
                        }
                    )
                    await send({"type": "http.response.body", "body": body})
                    return

                await send(event)

            await app(scope, receive, capture_send)

        return middleware
