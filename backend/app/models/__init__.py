"""MongoDB document helpers.

Documents in this app are plain dicts persisted via Motor. The helpers
here normalize Mongo docs (ObjectId -> str, rename ``_id`` -> ``id``)
so response schemas declaring ``id: str`` accept them directly.
"""
from bson import ObjectId
from typing import Any


def doc_out(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    out = dict(doc)
    _id = out.pop("_id", None)
    if _id is not None:
        out["id"] = str(_id)
    for k, v in list(out.items()):
        if isinstance(v, ObjectId):
            out[k] = str(v)
    return out


def to_object_id(value: Any) -> ObjectId | None:
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None
