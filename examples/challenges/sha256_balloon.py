"""SHA256Balloon memory-hard proof-of-work challenge (default handler)."""

from collections.abc import Iterable
from typing import Any
from wsgiref.simple_server import make_server

from tollbooth import Rule, SHA256Balloon, TollboothWSGI

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]


def app(_environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello from upstream!"]


if __name__ == "__main__":
    wrapped = TollboothWSGI(app, SECRET, rules=RULES, challenge_handler=SHA256Balloon())
    print("SHA256Balloon challenge on http://localhost:8000")
    make_server("0.0.0.0", 8000, wrapped).serve_forever()
