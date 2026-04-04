import json
from typing import Unpack

from fastapi import Request

from ..engine import Policy, Rule
from ..middleware import TollboothASGI, _parse_scope
from .base import TollboothBase, TollboothKwargs, resolve_base


class TollboothMiddleware(TollboothASGI):
    def __init__(self, app, secret, **kwargs: Unpack[TollboothKwargs]):
        kwargs.setdefault("json_mode", True)
        super().__init__(app, secret, **kwargs)


class TollboothDep:
    def __init__(self, tb_or_secret, **kwargs: Unpack[TollboothKwargs]):
        kwargs.setdefault("json_mode", True)
        self._tb = resolve_base(tb_or_secret, kwargs)

    async def __call__(self, request: Request):
        from fastapi import HTTPException

        req = _parse_scope(request.scope)
        result = self._tb.process_request(req)
        if not result:
            return

        try:
            detail = json.loads(result.body)
        except (json.JSONDecodeError, TypeError):
            detail = result.body

        raise HTTPException(
            status_code=result.status,
            detail=detail,
        )


def mount_verify(app, tb_or_secret, **kwargs: Unpack[TollboothKwargs]):
    tb = resolve_base(tb_or_secret, kwargs)

    @app.post(tb.verify_path)
    async def verify(request: Request):
        from fastapi.responses import JSONResponse

        req = _parse_scope(request.scope)
        form = await request.form()
        req["form"] = dict(form)
        result = tb.process_request(req)
        if not result:
            return JSONResponse({"ok": True})
        return JSONResponse(
            json.loads(result.body),
            status_code=result.status,
        )


class TollboothChallengeDep:
    def __init__(self, tb_or_secret, **kwargs: Unpack[TollboothKwargs]):
        kwargs.setdefault("json_mode", True)
        self._tb = resolve_base(tb_or_secret, kwargs)

    async def __call__(self, request: Request):
        from fastapi import HTTPException

        req = _parse_scope(request.scope)
        override = TollboothBase(engine=self._tb.engine)
        override.engine.policy = Policy(
            rules=[Rule(name="always_challenge", action="challenge")],
            challenge_handler=(self._tb.engine.policy.challenge_handler),
            cookie_name=self._tb.engine.policy.cookie_name,
            verify_path=self._tb.engine.policy.verify_path,
            cookie_ttl=self._tb.engine.policy.cookie_ttl,
            challenge_ttl=self._tb.engine.policy.challenge_ttl,
        )
        result = override.process_request(req)
        if not result:
            return

        try:
            detail = json.loads(result.body)
        except (json.JSONDecodeError, TypeError):
            detail = result.body

        raise HTTPException(status_code=result.status, detail=detail)


class TollboothBlockDep:
    def __init__(self, tb_or_secret, **kwargs: Unpack[TollboothKwargs]):
        kwargs.setdefault("json_mode", True)
        self._tb = resolve_base(tb_or_secret, kwargs)

    async def __call__(self, request: Request):
        from fastapi import HTTPException

        req = _parse_scope(request.scope)
        result = self._tb.process_request(req)
        if result:
            try:
                detail = json.loads(result.body)
            except (json.JSONDecodeError, TypeError):
                detail = result.body
            raise HTTPException(status_code=result.status, detail=detail)

        claims = req.get("_claims")
        if claims and claims.is_crawler:
            raise HTTPException(status_code=403, detail="Forbidden")
