from typing import Any

from tollbooth import Rule, TollboothASGI

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]


async def app(scope: dict[str, Any], _receive: Any, send: Any) -> None:
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


wrapped = TollboothASGI(app, SECRET, rules=RULES)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(wrapped, host="0.0.0.0", port=8000)
