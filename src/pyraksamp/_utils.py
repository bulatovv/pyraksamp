"""Internal filter helpers shared by _bus and _streams."""

import asyncio
from collections.abc import Callable


# Return a filter callable(obj)->bool, or None if no filtering is requested.
def _make_obj_filter(predicate, kwargs):
    kw = {k: v for k, v in kwargs.items() if v is not None}
    if predicate is None and not kw:
        return None

    def filt(obj):
        if predicate is not None and not predicate(obj):
            return False
        return all(getattr(obj, k) == v for k, v in kw.items())

    return filt


# Wrap a single-arg event callback with a predicate guard.
def _wrap_obj(fn, filt):
    async def wrapper(obj):
        if filt(obj):
            if asyncio.iscoroutinefunction(fn):
                await fn(obj)
            else:
                fn(obj)

    return wrapper
