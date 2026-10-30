from datetime import datetime, timedelta

import pytest

from conftest import load_fixture
from entur_mcp.config import TZ
from entur_mcp.departures import InvalidMode, group_departures
from entur_mcp.entur import _parse_call
from entur_mcp.models import Call

NOW = datetime(2026, 10, 30, 16, 25, tzinfo=TZ)


@pytest.fixture
def calls() -> list[Call]:
    raw = load_fixture("departures_lindeberg")["data"]["stopPlace"]["estimatedCalls"]
    return [_parse_call(c) for c in raw]


@pytest.fixture
def now(calls) -> datetime:
    return min(c.aimed for c in calls)


def make_call(expected: datetime, **overrides) -> Call:
    fields = dict(
        line="2", mode="metro", destination="Østerås", aimed=expected, expected=expected,
        realtime=True, cancelled=False, notices=[], quay_id="NSR:Quay:10269",
        platform="2", quay_name="Lindeberg",
    )
    return Call(**(fields | overrides))


def test_groups_by_quay_with_destinations(calls, now):
    by_quay = {g.quay_id: g for g in group_departures(calls, now)}
    assert by_quay["NSR:Quay:10269"].platform == "2"
    assert "Østerås" in by_quay["NSR:Quay:10269"].destinations
    assert by_quay["NSR:Quay:10270"].destinations == ["Ellingsrudåsen"]


def test_metro_groups_come_before_bus(calls, now):
    groups = group_departures(calls, now)
    assert [g.departures[0].mode for g in groups][:2] == ["metro", "metro"]
    assert {g.departures[0].mode for g in groups[2:]} == {"bus"}


def test_limit_is_per_group_so_metro_is_not_crowded_out(calls, now):
    groups = group_departures(calls, now, limit=2)
    assert all(len(g.departures) <= 2 for g in groups)
    assert {"NSR:Quay:10269", "NSR:Quay:10270"} <= {g.quay_id for g in groups}


def test_mode_filter_case_insensitive(calls, now):
    groups = group_departures(calls, now, modes=["METRO"])
    assert groups
    assert all(d.mode == "metro" for g in groups for d in g.departures)


def test_unknown_mode_raises(calls, now):
    with pytest.raises(InvalidMode, match="metro"):
        group_departures(calls, now, modes=["tbane"])


def test_minutes_until_floors():
    groups = group_departures([make_call(NOW + timedelta(minutes=4, seconds=59))], NOW)
    assert groups[0].departures[0].minutes_until == 4


def test_drops_departures_already_gone():
    gone = make_call(NOW - timedelta(minutes=1))
    coming = make_call(NOW + timedelta(minutes=3))
    groups = group_departures([gone, coming], NOW)
    assert [d.expected for d in groups[0].departures] == [coming.expected]


def test_cancelled_kept_and_marked():
    groups = group_departures([make_call(NOW + timedelta(minutes=5), cancelled=True)], NOW)
    assert groups[0].departures[0].cancelled is True


def test_scheduled_only_has_realtime_false():
    t = NOW + timedelta(minutes=5)
    departure = group_departures([make_call(t, realtime=False)], NOW)[0].departures[0]
    assert departure.realtime is False
    assert departure.expected == departure.aimed == t


def test_no_departures_returns_empty_list():
    assert group_departures([], NOW) == []
