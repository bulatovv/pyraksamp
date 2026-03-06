"""Internal filter helpers."""


def _make_obj_filter(predicate, kwargs=None, *, instance_of=None):
    """Return a filter callable(obj)->bool, or None if no filtering is needed."""
    kw = {k: v for k, v in (kwargs or {}).items() if v is not None}
    type_check = (lambda obj: isinstance(obj, instance_of)) if instance_of else None

    if predicate is None and not kw and type_check is None:
        return None

    def filt(obj):
        if type_check is not None and not type_check(obj):
            return False
        if predicate is not None and not predicate(obj):
            return False
        return all(getattr(obj, k) == v for k, v in kw.items())

    return filt
