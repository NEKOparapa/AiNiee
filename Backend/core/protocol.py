"""Transport serialization shared by HTTP responses and notifications."""

PROTOCOL_VERSION = 2


def to_wire(value):
    if hasattr(value, "to_dict"):
        return to_wire(value.to_dict())
    if isinstance(value, dict):
        return {str(k): to_wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_wire(v) for v in value]
    return value
