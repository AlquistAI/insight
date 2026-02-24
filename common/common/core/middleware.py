# -*- coding: utf-8 -*-
"""
    common.core.middleware
    ~~~~~~~~~~~~~~~~~~~~~~

    Logging middleware.
"""

import functools
import logging
import time
import uuid
from contextlib import suppress
from contextvars import ContextVar, Token
from typing import Any, Callable, Sequence

from fastapi import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp, Scope

X_CORRELATION_ID = "X-Correlation-Id"
X_REQUEST_ID = "X-Request-Id"
X_RESPONSE_TIME = "X-Response-Time"

_CONTEXT: ContextVar = ContextVar("starlette_context", default=None)


def get_context() -> dict:
    try:
        return _CONTEXT.get()
    except LookupError:
        _CONTEXT.set({})
        return _CONTEXT.get()


def get_context_var(var: str) -> Any:
    return c.get(var) if (c := get_context()) else None


def set_context(v: dict | None) -> Token | None:
    return _CONTEXT.set(v) if v else None


def reset_context(token: Token) -> None:
    return _CONTEXT.reset(token) if token else None


def add_to_context(v: dict) -> Token:
    """
    Data will be logged for every application log within one request.

    A new token is created, therefore the response log will not contain the added data.
    """

    if ctx := _CONTEXT.get():
        v.update(ctx)
    return _CONTEXT.set(v)


def wrap_with_context(func):
    """Decorator that is passing context into individual threads, e.g. for use with the concurrent futures."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _t = set_context(kwargs.pop("context", None))
        result = func(*args, **kwargs)
        reset_context(_t)
        return result

    return wrapper


def update_headers_with_ctx(headers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Update request headers with context."""

    headers = headers.copy() if headers else {}
    headers[X_CORRELATION_ID] = c.get(X_CORRELATION_ID) if (c := get_context()) else uuid.uuid4().hex
    headers[X_REQUEST_ID] = uuid.uuid4().hex
    return headers


async def extract_header_by_key(key: str, request: Request) -> str | None:
    """Helper method to extract value of header by key."""
    return request.headers.get(key) or request.headers.get(key.lower()) or uuid.uuid4().hex


class ParamToContext:
    """
    Class for plugins to extract information from query and path parameters and include them into context.

    :param param_name: parameter name to extract
    :param context_name: save to context with context_name
    :param fmt_callable: function to format the result
    """

    def __init__(self, param_name: str, context_name: str | None = None, fmt_callable: Callable | None = None):
        self.param_name = param_name
        self.context_name = context_name or param_name
        self.f = fmt_callable


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling log context information.

    For each request extract x-correlation-id, x-request-id and compute x-response-time.
    If the correlation id and request id are not present generate uuid.
    Append this information into response headers and scope (for response logging).
    """

    def __init__(
            self,
            app: ASGIApp,
            logger: logging.Logger | None = None,
            router: APIRouter | None = None,
            extractors: Sequence[ParamToContext] | None = None,
            **kwargs,
    ):

        super().__init__(app, **kwargs)
        self.logger = logger
        self.router = router
        self.extractors = extractors or ()

        for ex in self.extractors:
            if not isinstance(ex, ParamToContext):
                raise TypeError("This is not a valid instance of ParamToContext")
            if ex.f and not callable(ex.f):
                raise TypeError("This function is not callable")

    async def get_path_params(self, request: Request) -> dict:

        if self.router:
            scope: Scope = request.scope
            for route in self.router.routes:
                match, child_scope = route.matches(scope)
                if match == Match.FULL:
                    return child_scope.get("path_params", {})

        return {}

    async def extract_params(self, params: Any) -> dict:
        """Using the list of extractors (ParamToContext) get and format extractor_param_name parameters."""

        if not params:
            return {}

        c = {}
        for extractor in self.extractors:
            if not (v := params.get(extractor.param_name)):
                continue

            if extractor.f:
                with suppress(Exception):
                    c[extractor.context_name] = extractor.f(v)
            else:
                c[extractor.context_name] = v

        return c

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):

        values_to_ctx = {
            X_CORRELATION_ID: await extract_header_by_key(X_CORRELATION_ID, request),
            X_REQUEST_ID: await extract_header_by_key(X_REQUEST_ID, request),
        }

        # put query or path params into context
        r_params = dict(request.query_params)
        r_params.update(await self.get_path_params(request))
        values_to_ctx.update(await self.extract_params(r_params))
        token: Token = _CONTEXT.set(values_to_ctx)

        try:
            before_time = time.perf_counter()
            response: Response = await call_next(request)
            response_time = int(1000 * (time.perf_counter() - before_time))
            ctx = _CONTEXT.get()

            # update request scope (for logging)
            if hasattr(request, "scope") and request.scope and ctx:
                request.scope.update(ctx)
                request.scope["request_url"] = str(request.url)
                request.scope[X_RESPONSE_TIME] = response_time

            # update response headers
            if hasattr(response, "headers") and response.headers and ctx:
                response.headers[X_CORRELATION_ID] = ctx.get(X_CORRELATION_ID)
                response.headers[X_REQUEST_ID] = ctx.get(X_REQUEST_ID)
                response.headers[X_RESPONSE_TIME] = str(response_time)

                v = response.headers.get("content-length")
                ctx["content_length"] = int(v) if isinstance(v, str) and v.isdigit() else v

            client = request.scope.get("client")
            if client and len(client) == 2:
                client = f"{client[0]}:{client[1]}"

            ctx.update({"log_type": "response", "scope": request.scope, "status_code": response.status_code})
            self.logger.info(
                '%s - "%s %s %s/%s" %s',
                client,
                request.scope.get("method"),
                request.scope.get("path"),
                request.scope.get("type").upper(),
                request.scope.get("http_version"),
                response.status_code,
                extra=ctx,
            )

        finally:
            # reset context with token
            _CONTEXT.reset(token)

        return response
