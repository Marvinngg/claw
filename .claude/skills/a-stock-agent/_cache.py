"""TTL 缓存 — 交易/非交易时间分级"""
import time
from datetime import datetime, time as dtime

_store: dict[str, tuple[float, object]] = {}


def is_trading() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (dtime(9, 25) <= t <= dtime(11, 35)) or (dtime(12, 55) <= t <= dtime(15, 5))


def get(key: str):
    if key in _store:
        exp, val = _store[key]
        if time.time() < exp:
            return val
        del _store[key]
    return None


def put(key: str, val, ttl: int):
    _store[key] = (time.time() + ttl, val)


def ttl_quote() -> int:
    return 300 if is_trading() else 3600


def ttl_flow() -> int:
    return 180 if is_trading() else 3600


TTL_FUNDAMENTAL = 86400
TTL_STATIC = 14400
