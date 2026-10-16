"""Isolated recurrence worker; executed as a script without importing HA."""

from __future__ import annotations

from datetime import datetime
import json
import resource
import sys
from typing import Any

MAX_OCCURRENCES = 10_000
MAX_OUTPUT_BYTES = 16 * 1024 * 1024


def run(request: dict[str, Any]) -> Any:
    """Compute within kernel-enforced CPU and address-space limits."""
    if request["operation"] == "validate":
        from dateutil.rrule import rrulestr

        rule = rrulestr(
            request["rule"], dtstart=datetime.fromisoformat(request["start"])
        )
        if next(iter(rule), None) is None:
            raise ValueError("rule produces no occurrences")
        return None

    import caldav

    item = caldav.Event(data=request["ics"])
    item.expand_rrule(
        datetime.fromisoformat(request["start"]),
        datetime.fromisoformat(request["end"]),
    )
    if len(item.icalendar_instance.walk("VEVENT")) > MAX_OCCURRENCES:
        raise MemoryError("too many occurrences")
    return item.data


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    try:
        request = json.load(sys.stdin)
        sys.path.extend(request.get("paths", []))
        answer = {"result": run(request)}
        encoded = json.dumps(answer).encode()
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise MemoryError("expanded document too large")
    except MemoryError:
        encoded = b'{"error":"rrule_too_dense"}'
    except Exception as err:  # noqa: BLE001
        encoded = json.dumps(
            {"error": "invalid_rrule", "reason": type(err).__name__}
        ).encode()
    sys.stdout.buffer.write(encoded)
