from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import AppError

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _client


def close_redis() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_download_rate_limit(ip: str) -> None:
    key = f"rate_limit:{ip}"
    window = settings.download_rate_window_seconds
    try:
        pipe = get_redis().pipeline()
        pipe.set(key, 0, ex=window, nx=True)
        pipe.incr(key)
        pipe.ttl(key)
        _, count, ttl = pipe.execute()
    except RedisError as exc:
        raise AppError(503, "rate_limit_unavailable", "Rate limiter is unavailable") from exc

    if int(count) > settings.download_rate_limit:
        raise AppError(
            429,
            "rate_limited",
            "Too many download requests",
            headers={"Retry-After": str(max(int(ttl), 1))},
        )


def rate_limit_downloads(request: Request) -> None:
    enforce_download_rate_limit(client_ip(request))
