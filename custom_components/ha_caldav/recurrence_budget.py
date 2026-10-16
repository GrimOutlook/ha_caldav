"""Run untrusted recurrence computation outside Home Assistant's process."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import subprocess
import sys
from threading import BoundedSemaphore
from typing import Any

from .errors import Refused

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
WORKER_TIMEOUT = 8
_WORKER = Path(__file__).with_name("recurrence_worker.py")
_WORKERS = BoundedSemaphore(2)


def compute(request: dict[str, Any]) -> Any:
    """Return a bounded worker result, killing work that exceeds its deadline."""
    payload = json.dumps(
        {
            **request,
            "paths": [
                path for path in sys.path if path and Path(path) != _WORKER.parent
            ],
        }
    ).encode()
    if len(payload) > MAX_INPUT_BYTES:
        raise Refused("rrule_too_dense")
    try:
        with _WORKERS:
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import runpy,sys;runpy.run_path(sys.argv[1],run_name='__main__')",
                    str(_WORKER),
                ],
                input=payload,
                capture_output=True,
                timeout=WORKER_TIMEOUT,
                check=False,
            )
    except subprocess.TimeoutExpired as err:
        raise Refused("rrule_too_dense") from err
    if result.returncode or len(result.stdout) > MAX_OUTPUT_BYTES:
        raise Refused("rrule_too_dense")
    try:
        answer = json.loads(result.stdout)
    except (ValueError, UnicodeError) as err:
        raise Refused("rrule_too_dense") from err
    if error := answer.get("error"):
        raise Refused(error, reason=answer.get("reason", "resource limit"))
    return answer["result"]


@lru_cache(maxsize=512)
def validate(rule: str, start: str) -> None:
    """Validate each rule/start pair once, without an uninterruptible HA thread."""
    compute({"operation": "validate", "rule": rule, "start": start})
