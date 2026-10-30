import pytest
from mcp.client.client import Client

from entur_mcp.server import build_server

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def test_live_lindeberg_has_metro():
    """Calls the real Entur API. Fails at night, when the metro is not running."""
    async with Client(build_server()) as c:
        r = await c.call_tool("next_departures", {})
    assert not r.is_error
    modes = {d["mode"] for g in r.structured_content["directions"] for d in g["departures"]}
    assert "metro" in modes
