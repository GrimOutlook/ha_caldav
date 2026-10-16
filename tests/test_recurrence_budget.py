"""Resource limits apply to local validation and remotely supplied series alike."""

from datetime import UTC, datetime
import subprocess
from unittest.mock import patch

from icalendar import vRecur
import pytest

from custom_components.ha_caldav.errors import Refused
from custom_components.ha_caldav.event import check_rule
from custom_components.ha_caldav.recurrence_budget import compute


def test_impossible_hourly_rule_is_terminated() -> None:
    with pytest.raises(Refused, match="rrule_too_dense"):
        check_rule(
            vRecur.from_ical("FREQ=HOURLY;BYMONTH=2;BYMONTHDAY=30"),
            datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_worker_timeout_is_reported_as_a_resource_limit() -> None:
    with (
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 8)),
        pytest.raises(Refused, match="rrule_too_dense"),
    ):
        compute({"operation": "validate", "rule": "FREQ=DAILY", "start": "2026-01-01"})


def test_dense_hourly_expansion_is_rejected() -> None:
    rule = (
        "FREQ=HOURLY;BYMINUTE="
        + ",".join(map(str, range(60)))
        + ";BYSECOND="
        + ",".join(map(str, range(60)))
    )
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:dense\r\n"
        "DTSTART:20260101T000000Z\r\nDTEND:20260101T000001Z\r\n"
        f"RRULE:{rule}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    with pytest.raises(Refused, match="rrule_too_dense"):
        compute(
            {
                "operation": "expand",
                "ics": ics,
                "start": "2026-01-01T00:00:00+00:00",
                "end": "2026-01-02T00:00:00+00:00",
            }
        )
