"""Compensation is conditional on the exact version created by this operation."""

from caldav.elements import dav
from conftest import dav_calendar
from icalendar import Calendar
import pytest
from test_recurrence import TIMED_SERIES

from custom_components.ha_caldav.api import _undo, save_document
from custom_components.ha_caldav.recurrence import _discard


@pytest.mark.parametrize("cleanup", [_undo, _discard])
def test_cleanup_preserves_an_intervening_edit(cleanup) -> None:
    calendar = dav_calendar()
    stored = save_document(calendar, Calendar.from_ical(TIMED_SERIES), as_todo=False)
    url = str(stored.url)
    assert stored.props[dav.GetEtag.tag] == '"1"'
    calendar.client.stored[url] = ("changed elsewhere", '"external"')

    cleanup(stored)

    assert calendar.client.stored[url] == ("changed elsewhere", '"external"')


@pytest.mark.parametrize("tag", [None, 'W/"weak"'])
@pytest.mark.parametrize("cleanup", [_undo, _discard])
def test_cleanup_without_a_strong_creation_etag_preserves_the_resource(
    tag, cleanup
) -> None:
    calendar = dav_calendar()
    stored = save_document(calendar, Calendar.from_ical(TIMED_SERIES), as_todo=False)
    stored.props.clear()
    if tag is not None:
        stored.props[dav.GetEtag.tag] = tag
    before = dict(calendar.client.stored)

    cleanup(stored)

    assert calendar.client.stored == before
    assert not calendar.client.deletes


@pytest.mark.parametrize("cleanup", [_undo, _discard])
def test_cleanup_can_remove_the_unchanged_created_version(cleanup) -> None:
    calendar = dav_calendar()
    stored = save_document(calendar, Calendar.from_ical(TIMED_SERIES), as_todo=False)

    cleanup(stored)

    assert str(stored.url) not in calendar.client.stored
