from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from tollbooth import Rule
from tollbooth.integrations.starlette import TollboothMiddleware

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]


async def homepage(request: Request):
    return PlainTextResponse("Hello from upstream!")


app = Starlette(routes=[Route("/", homepage)])
app.add_middleware(TollboothMiddleware, secret=SECRET, rules=RULES)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
