# -*- coding: utf-8 -*-
"""
    common.api.security_jwt
    ~~~~~~~~~~~~~~~~~~~~~~~

    API security utilities using JWT.
"""

import httpx
import jwt
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends
from fastapi.security import APIKeyHeader

from common.config import CONFIG

KEYCLOAK_URL = str(CONFIG.KEYCLOAK_URL).rstrip("/") if CONFIG.KEYCLOAK_URL else None
header = APIKeyHeader(name="Authorization", scheme_name="JWT", auto_error=False)


async def verify_jwt(token: str | None = Depends(header)):
    if KEYCLOAK_URL is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "JWT auth not set up")

    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Auth token missing")

    if not token.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid auth token")

    try:
        return jwt.decode(
            jwt=token.split(" ", 1)[1],
            key=await get_public_key(),
            algorithms=["RS256"],
            audience="account",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Auth token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid auth token")
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to decode auth token: {e}")


async def get_public_key() -> str:
    """Retrieve and format the public key from KeyCloak."""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{KEYCLOAK_URL}/realms/{CONFIG.KEYCLOAK_REALM}")
            response.raise_for_status()
        except httpx.RequestError as e:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Request failed: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(e.response.status_code, f"Error response: {e.response.text}")

    if not (public_key := response.json().get("public_key")):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Public key not found in KeyCloak response")

    return f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
