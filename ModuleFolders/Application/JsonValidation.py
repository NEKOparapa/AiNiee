"""Keep extension metadata valid JSON through file and application boundaries."""

import math


def reject_json_constant(value):
    raise ValueError("Non-finite JSON number")


def validate_finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite JSON number")
    if isinstance(value, dict):
        for item in value.values():
            validate_finite_json(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            validate_finite_json(item)
