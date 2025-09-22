# cache.py
import asyncio
import time

# Simple in-memory dict cache
_cache = {}

async def get_cached(key: str):
    if key in _cache:
        value, expiry = _cache[key]
        if expiry > time.time():
            return value
        else:
            _cache.pop(key, None)
    return None

async def set_cached(key: str, value: dict, ttl: int = 900):
    _cache[key] = (value, time.time() + ttl)

async def delete_cached(key: str):
    _cache.pop(key, None)

