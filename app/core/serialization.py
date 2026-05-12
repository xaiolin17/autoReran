try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    HAS_ORJSON = False

import msgpack
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from fastapi.responses import Response


def default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def json_dumps(data: Any) -> bytes:
    if HAS_ORJSON:
        return orjson.dumps(data, default=default)
    else:
        return json.dumps(data, default=default, ensure_ascii=False).encode("utf-8")


def json_loads(data: bytes | str) -> Any:
    if HAS_ORJSON:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return orjson.loads(data)
    else:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)


def msgpack_dumps(data: Any) -> bytes:
    return msgpack.packb(data, default=default)


def msgpack_loads(data: bytes) -> Any:
    return msgpack.unpackb(data)


class ORJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        if HAS_ORJSON:
            return orjson.dumps(content, default=default)
        else:
            return json.dumps(content, default=default, ensure_ascii=False).encode("utf-8")
