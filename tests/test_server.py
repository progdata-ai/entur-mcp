import json
from datetime import datetime

import httpx
import pytest
from mcp.client.client import Client

from conftest import load_fixture, mock_transport
from entur_mcp.config import TZ
from entur_mcp.entur import EnturClient
from entur_mcp.server import build_server

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 30, 16, 30, tzinfo=TZ)
LINDEBERG = "NSR:StopPlace:58222"
DEFAULT_ROUTES = {
    "geocoder": load_fixture("geocoder_lindeberg"),
    "graphql": load_fixture("departures_lindeberg"),
}


def server_with(routes=None):
    transport = mock_transport(routes or DEFAULT_ROUTES)
    client = EnturClient(client_name="test-client", transport=transport)
    return build_server(client=client, clock=lambda: NOW), transport


def text_of(result) -> str:
    return " ".join(c.text for c in result.content if hasattr(c, "text"))


async def test_lists_both_tools():
    server, _ = server_with()
    async with Client(server) as c:
        tools = (await c.list_tools()).tools
    assert {t.name for t in tools} == {"find_stop", "next_departures"}


async def test_default_stop_is_lindeberg():
    server, transport = server_with()
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {})
    assert not r.is_error
    assert r.structured_content["stop"]["id"] == LINDEBERG
    assert r.structured_content["directions"]
    assert [req.url.path for req in transport.requests] == ["/journey-planner/v3/graphql"]
    assert json.loads(transport.requests[0].content)["variables"]["id"] == LINDEBERG


async def test_name_resolves_and_reports_other_matches():
    server, _ = server_with()
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {"stop": "Lindeberg"})
    assert not r.is_error
    assert r.structured_content["stop"]["id"] == LINDEBERG
    assert "NSR:StopPlace:62094" in [m["id"] for m in r.structured_content["other_matches"]]


async def test_no_geocoder_match_is_readable_error():
    server, _ = server_with({"geocoder": {"features": []}, "graphql": DEFAULT_ROUTES["graphql"]})
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {"stop": "Atlantis"})
    assert r.is_error
    assert "Fant ingen holdeplass" in text_of(r)


async def test_entur_down_is_readable_error():
    server, _ = server_with({"graphql": httpx.Response(503)})
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {})
    assert r.is_error
    assert "Entur svarer ikke" in text_of(r)
    assert "Traceback" not in text_of(r)


async def test_invalid_mode_is_error():
    server, _ = server_with()
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {"modes": ["tbane"]})
    assert r.is_error
    assert "metro" in text_of(r)


async def test_empty_window_has_message():
    empty = {"data": {"stopPlace": {"id": LINDEBERG, "name": "Lindeberg", "estimatedCalls": []}}}
    server, _ = server_with({"graphql": empty})
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {})
    assert not r.is_error
    assert r.structured_content["directions"] == []
    assert "Ingen avganger" in r.structured_content["message"]


async def test_find_stop_tool():
    server, _ = server_with()
    async with Client(server) as c:
        r = await c.call_tool("find_stop", {"name": "Lindeberg"})
    assert not r.is_error
    assert LINDEBERG in json.dumps(r.structured_content)


@pytest.mark.parametrize(
    "args", [{"limit": 0}, {"limit": -1}, {"minutes_ahead": 0}, {"minutes_ahead": -5}]
)
async def test_invalid_numbers_are_readable_errors(args):
    server, transport = server_with()
    async with Client(server) as c:
        r = await c.call_tool("next_departures", args)
    assert r.is_error
    assert "minst 1" in text_of(r)
    assert transport.requests == []


async def test_modes_are_validated_before_calling_entur():
    server, transport = server_with()
    async with Client(server) as c:
        r = await c.call_tool("next_departures", {"modes": ["tbane"]})
    assert r.is_error
    assert transport.requests == []
