"""Splitting a series must never replace an existing destination version."""

from conftest import dav_calendar
from icalendar import Calendar
import pytest
from test_recurrence import (
    ADDED_DATE,
    DATED_SERIES,
    SECOND_OCCURRENCE,
    TIMED_SERIES,
    FakeEvent,
)

from custom_components.ha_caldav.api import save_document
from custom_components.ha_caldav.errors import Refused
from custom_components.ha_caldav.recurrence import update_event


@pytest.mark.parametrize(
    ("ics", "uid", "slot", "destination"),
    [
        (TIMED_SERIES, "timed-1", SECOND_OCCURRENCE, "timed-1-20260713T090000Z"),
        (DATED_SERIES, "dated-1", ADDED_DATE, "dated-1-20260709T090000Z"),
    ],
)
def test_a_split_collision_preserves_both_existing_resources(
    ics: str, uid: str, slot: str, destination: str
) -> None:
    calendar = dav_calendar()
    source = FakeEvent(ics)
    calendar.event_by_uid.return_value = source
    tail = Calendar.from_ical(TIMED_SERIES)
    tail.walk("VEVENT")[0]["UID"] = destination
    tail.walk("VEVENT")[0]["SUMMARY"] = "Edited by another calendar client"
    existing = save_document(calendar, tail, as_todo=False)
    before = dict(calendar.client.stored)

    for _ in range(2):
        with pytest.raises(Refused, match="uid_clash"):
            update_event(
                calendar,
                uid,
                {"summary": "New tail"},
                recurrence_id=slot,
                this_and_future=True,
            )

    assert calendar.client.stored == before
    assert not source.saved
    assert str(existing.url) in calendar.client.stored
    assert calendar.client.put_headers[-1]["If-None-Match"] == "*"
