"""Type stubs for orjson.

orjson is a fast, correct JSON library for Python 3.8+.
"""

from typing import Any

def dumps(
    obj: Any,
    default: Any | None = None,
    option: int | None = None,
) -> bytes:
    """Serialize obj to a JSON-encoded bytes object.

    Args:
        obj: Object to serialize.
        default: Callable for non-serializable types.
        option: Serialization options.

    Returns:
        JSON as bytes.
    """
    ...

def loads(__obj: bytes | bytearray | memoryview | str) -> Any:
    """Deserialize a JSON string or bytes to a Python object.

    Args:
        __obj: JSON data as bytes or string.

    Returns:
        Deserialized Python object.
    """
    ...

# Options for dumps
OPT_APPEND_NEWLINE: int
OPT_INDENT_2: int
OPT_NAIVE_UTC: int
OPT_NON_STR_KEYS: int
OPT_OMIT_MICROSECONDS: int
OPT_PASSTHROUGH_DATACLASS: int
OPT_PASSTHROUGH_DATETIME: int
OPT_PASSTHROUGH_SUBCLASS: int
OPT_SERIALIZE_DATACLASS: int
OPT_SERIALIZE_NUMPY: int
OPT_SERIALIZE_UUID: int
OPT_SORT_KEYS: int
OPT_STRICT_INTEGER: int
OPT_UTC_Z: int
