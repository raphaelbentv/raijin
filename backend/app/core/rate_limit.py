"""Rate limiting léger via slowapi (in-memory par défaut).

Pour prod multi-instances, il faudrait un backend Redis :
    Limiter(key_func=get_remote_address, storage_uri="redis://redis:6379/4")

Mais avec 1-2 workers uvicorn derrière Nginx, l'in-memory suffit au MVP.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _key_func(request):
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func, default_limits=[])


def login_rate() -> str:
    s = get_settings()
    return f"{s.rate_limit_login_per_min}/minute"


def register_rate() -> str:
    s = get_settings()
    return f"{s.rate_limit_register_per_min}/minute"
