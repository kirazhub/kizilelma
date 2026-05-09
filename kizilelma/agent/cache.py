"""Basit in-memory TTL cache - AI çağrıları ve veri scraping için.

Amaç:
    - Aynı veri kısa süre içinde tekrar istenirse, dış kaynağa (HTTP/scraping)
      gitmeden bellekteki kopyayı dön.
    - 5 dakikalık varsayılan süre (TTL = Time-To-Live), sonra otomatik geçersiz.

Tasarım:
    - Tek process içinde paylaşılan global cache (`_global_cache`).
    - Method'lara uygulamak için sınıfa ait `TTLCache` instance'ı kullan.
    - Async fonksiyonlara decorator ile takılabilir (`cached_async`).
    - Thread-safe DEĞİL — asyncio tek event loop varsayımıyla çalışır.
"""
from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Optional


class TTLCache:
    """Time-to-live in-memory cache.

    Aynı veri belirli süre içinde tekrar istenirse cache'den döner,
    yeni HTTP/scraping yapılmaz.

    Örnek:
        cache = TTLCache(ttl_seconds=300)  # 5 dakika
        cache.set("key", value)
        cached = cache.get("key")  # 5 dk içindeyse value döner, sonra None
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Cache'den değer al. TTL dolduysa None döner ve kaydı siler."""
        if key not in self._data:
            return None

        timestamp, value = self._data[key]
        if time.time() - timestamp > self._ttl:
            # Süresi dolmuş — temizle
            del self._data[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Cache'e değer yaz (timestamp ile birlikte)."""
        self._data[key] = (time.time(), value)

    def clear(self) -> None:
        """Tüm cache'i temizle."""
        self._data.clear()

    def __contains__(self, key: str) -> bool:
        # `key in cache` yazımı için — TTL kontrolünü de yapar
        return self.get(key) is not None


# Global instance — tüm modüller paylaşır (5 dakika varsayılan)
_global_cache = TTLCache(ttl_seconds=300)


def cached_async(key_prefix: str, ttl: int = 300) -> Callable:
    """Async fonksiyonları cache'leyen decorator.

    Kullanım:
        @cached_async("macro_data", ttl=300)
        async def fetch_macros():
            ...

    Not: Method'larda `self` argümanı hash'e dahil olur; aynı instance
    tekrar çağrılırsa cache hit, farklı instance ise cache miss olur.
    Method'larda sınıf-seviyesi `TTLCache` kullanmak daha güvenlidir.
    """
    cache = TTLCache(ttl_seconds=ttl)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Cache key: prefix + args/kwargs hash
            cache_key = (
                f"{key_prefix}:{hash(str(args) + str(sorted(kwargs.items())))}"
            )

            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Cache miss — gerçek fonksiyonu çağır
            result = await func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        # Test/debug için cache'e dışarıdan erişim
        wrapper._cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator


def get_global_cache() -> TTLCache:
    """Global cache instance'ına erişim."""
    return _global_cache
