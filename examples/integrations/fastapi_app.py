from typing import Annotated

import fastapi

from tollbooth import Rule
from tollbooth.integrations.fastapi import (
    TollboothDep,
    TollboothMiddleware,
    mount_verify,
)

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]

app = fastapi.FastAPI()
app.add_middleware(TollboothMiddleware, secret=SECRET, rules=RULES)
mount_verify(app, SECRET, rules=RULES)

tb_dep = TollboothDep(SECRET, rules=RULES)


@app.get("/")
def index():
    return {"message": "Hello from upstream!"}


@app.get("/per-route", dependencies=[fastapi.Depends(tb_dep)])
def per_route():
    return {"message": "Per-route protection"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
