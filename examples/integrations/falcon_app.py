from wsgiref.simple_server import make_server

import falcon

from tollbooth import Rule
from tollbooth.integrations.falcon import (
    TollboothMiddleware,
    VerifyResource,
    tollbooth_hook,
)

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]


class HelloResource:
    def on_get(self, req, resp):
        resp.text = "Hello from upstream!"


class ProtectedResource:
    def __init__(self):
        self._hook = tollbooth_hook(SECRET, rules=RULES)

    @falcon.before(tollbooth_hook(SECRET, rules=RULES))
    def on_get(self, req, resp):
        resp.text = f"Claims: {req.context.tollbooth}"


app = falcon.App(middleware=[TollboothMiddleware(SECRET, rules=RULES)])
app.add_route("/", HelloResource())
app.add_route("/protected", ProtectedResource())
app.add_route("/.tollbooth/verify", VerifyResource(SECRET, rules=RULES))

if __name__ == "__main__":
    print("Falcon WSGI on http://localhost:8000")
    make_server("0.0.0.0", 8000, app).serve_forever()
