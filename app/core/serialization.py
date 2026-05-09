import orjson
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
    return orjson.dumps(data, default=default)


def json_loads(data: bytes | str) -> Any:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return orjson.loads(data)


def msgpack_dumps(data: Any) -> bytes:
    return msgpack.packb(data, default=default)


def msgpack_loads(data: bytes) -> Any:
    return msgpack.unpackb(data)


class ORJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, default=default)
