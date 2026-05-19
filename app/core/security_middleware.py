from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.logger import logger

# 尝试导入速率限制库，如果不可用则提供空实现
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    logger.warning("SlowAPI not available, rate limiting will be disabled")


def setup_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )


def setup_rate_limiter(app: FastAPI):
    if not SLOWAPI_AVAILABLE or not settings.RATE_LIMIT_ENABLED:
        logger.info("速率限制未启用或不可用")
        return None

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("速率限制已启用")
    return limiter


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if settings.CSP_ENABLED:
            csp_policy = "; ".join(
                [f"{k} {v}" for k, v in settings.CSP_DIRECTIVES.items()]
            )
            response.headers["Content-Security-Policy"] = csp_policy

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response


def setup_security_middleware(app: FastAPI):
    setup_cors(app)
    app.add_middleware(SecurityHeadersMiddleware)
    return setup_rate_limiter(app)
