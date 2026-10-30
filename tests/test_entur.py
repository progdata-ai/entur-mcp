import json

import httpx
import pytest

from conftest import load_fixture, mock_transport
from entur_mcp.entur import EnturClient, EnturUnavailable, StopNotFound
from entur_mcp.models import StopMatch, StopRef

pytestmark = pytest.mark.anyio

LINDEBERG = "NSR:StopPlace:58222"


def client_with(routes):
    transport = mock_transport(routes)
    return EnturClient(client_name="test-client", transport=transport), transport


async def test_find_stops_parses_geocoder():
    client, _ = client_with({"geocoder": load_fixture("geocoder_lindeberg")})
    stops = await client.find_stops("Lindeberg")
    assert stops[0] == StopMatch(
        id=LINDEBERG, name="Lindeberg", locality="Oslo", categories=["metroStation", "onstreetBus"]
    )
    assert any(s.id == "NSR:StopPlace:62094" for s in stops)


async def test_sends_client_name_header():
    client, transport = client_with(
        {"geocoder": load_fixture("geocoder_lindeberg"), "graphql": load_fixture("departures_lindeberg")}
    )
    await client.find_stops("Lindeberg")
    await client.estimated_calls(LINDEBERG, minutes_ahead=60)
    assert len(transport.requests) == 2
    assert all(r.headers["ET-Client-Name"] == "test-client" for r in transport.requests)


async def test_estimated_calls_parses_calls():
    client, _ = client_with({"graphql": load_fixture("departures_lindeberg")})
    stop, calls = await client.estimated_calls(LINDEBERG, minutes_ahead=60)
    assert stop == StopRef(id=LINDEBERG, name="Lindeberg")
    metro = [c for c in calls if c.mode == "metro"]
    assert {c.platform for c in metro} == {"1", "2"}
    assert all(c.platform is None for c in calls if c.quay_id in {"NSR:Quay:10272", "NSR:Quay:10274"})
    assert all(c.expected.tzinfo is not None for c in calls)
    assert any(c.cancelled for c in calls)
    assert any("Buss for bane" in c.notices for c in calls)


async def test_graphql_variables():
    client, transport = client_with({"graphql": load_fixture("departures_lindeberg")})
    await client.estimated_calls(LINDEBERG, minutes_ahead=60)
    body = json.loads(transport.requests[0].content)
    assert body["variables"] == {"id": LINDEBERG, "n": 50, "tr": 3600, "modes": None}


async def test_unknown_stop_raises_stop_not_found():
    client, _ = client_with({"graphql": {"data": {"stopPlace": None}}})
    with pytest.raises(StopNotFound):
        await client.estimated_calls("NSR:StopPlace:999999999", minutes_ahead=60)


async def test_graphql_errors_raise_unavailable():
    client, _ = client_with({"graphql": {"errors": [{"message": "x"}], "data": None}})
    with pytest.raises(EnturUnavailable):
        await client.estimated_calls(LINDEBERG, minutes_ahead=60)


async def test_http_500_raises_unavailable():
    client, _ = client_with({"graphql": httpx.Response(500)})
    with pytest.raises(EnturUnavailable):
        await client.estimated_calls(LINDEBERG, minutes_ahead=60)


async def test_timeout_raises_unavailable():
    client, _ = client_with({"geocoder": httpx.ReadTimeout("slow")})
    with pytest.raises(EnturUnavailable):
        await client.find_stops("Lindeberg")


async def test_skips_malformed_calls():
    data = load_fixture("departures_lindeberg")
    raw = data["data"]["stopPlace"]["estimatedCalls"]
    raw[0]["destinationDisplay"] = None
    raw[1]["quay"] = None
    client, _ = client_with({"graphql": data})
    _, calls = await client.estimated_calls(LINDEBERG, minutes_ahead=60)
    assert len(calls) == len(raw) - 2


async def test_modes_are_sent_to_entur():
    client, transport = client_with({"graphql": load_fixture("departures_lindeberg")})
    await client.estimated_calls(LINDEBERG, minutes_ahead=60, modes=["metro"])
    body = json.loads(transport.requests[0].content)
    assert body["variables"]["modes"] == ["metro"]
    assert "whiteListedModes: $modes" in body["query"]


async def test_find_stops_only_returns_stop_places():
    data = load_fixture("geocoder_lindeberg")
    group = json.loads(json.dumps(data["features"][0]))
    group["properties"]["id"] = "NSR:GroupOfStopPlaces:1"
    data["features"].insert(0, group)
    client, _ = client_with({"geocoder": data})
    stops = await client.find_stops("Lindeberg")
    assert all(s.id.startswith("NSR:StopPlace:") for s in stops)
