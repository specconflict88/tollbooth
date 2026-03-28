"""
General tollbooth example — WSGI and ASGI in one file.

Usage:
    python examples/general.py wsgi   # http://localhost:8000 (default)
    python examples/general.py asgi   # requires: pip install uvicorn

Try with curl to trigger a challenge:
    curl -v http://localhost:8000/
"""

import sys
from collections.abc import Iterable
from typing import Any

from tollbooth import Rule, TollboothASGI, TollboothWSGI

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]


def wsgi_app(_environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello from upstream!"]


async def asgi_app(scope: dict[str, Any], _receive: Any, send: Any) -> None:
    if scope["type"] != "http":
        return
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        }
    )
    await send({"type": "http.response.body", "body": b"Hello from upstream!"})


def run_wsgi() -> None:
    from wsgiref.simple_server import make_server

    wrapped = TollboothWSGI(wsgi_app, SECRET, rules=RULES)
    print("WSGI on http://localhost:8000")
    make_server("0.0.0.0", 8000, wrapped).serve_forever()


def run_asgi() -> None:
    import asyncio

    try:
        import uvicorn
    except ImportError:
        print("pip install uvicorn")
        return

    wrapped = TollboothASGI(asgi_app, SECRET, rules=RULES)

    async def serve() -> None:
        await uvicorn.Server(uvicorn.Config(wrapped, host="0.0.0.0", port=8000)).serve()

    asyncio.run(serve())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "wsgi"
    run_asgi() if mode == "asgi" else run_wsgi()
