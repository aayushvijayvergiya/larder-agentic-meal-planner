"""Supabase JWT verification (LLD §4.1)."""

import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from larder.config import Settings
from larder.errors import unauthorized


@dataclass(frozen=True)
class TokenClaims:
    sub: uuid.UUID
    email: str


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str, apikey: str) -> PyJWKClient:
    headers = {"apikey": apikey} if apikey else None
    return PyJWKClient(jwks_url, cache_keys=True, headers=headers)


def verify_token(token: str, settings: Settings) -> TokenClaims:
    try:
        if settings.auth_mode == "hs256":
            payload = jwt.decode(
                token, settings.supabase_jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience
            )
        else:
            jwks = _jwks_client(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", settings.supabase_anon_key)
            key = jwks.get_signing_key_from_jwt(token)
            payload = jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience=settings.jwt_audience)
        return TokenClaims(sub=uuid.UUID(str(payload["sub"])), email=str(payload.get("email") or ""))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise unauthorized() from exc
