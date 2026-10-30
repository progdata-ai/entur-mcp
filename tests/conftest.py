import json
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


class MockTransport(httpx.MockTransport):
    """Routes requests to 'geocoder' or 'graphql' by URL path and records them."""

    def __init__(self, routes: dict[str, httpx.Response | Exception | dict]):
        self.routes = routes
        self.requests: list[httpx.Request] = []
        super().__init__(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = "geocoder" if "geocoder" in request.url.path else "graphql"
        route = self.routes[key]
        if isinstance(route, Exception):
            raise route
        if isinstance(route, dict):
            return httpx.Response(200, json=route)
        return route


def mock_transport(routes: dict[str, httpx.Response | Exception | dict]) -> MockTransport:
    return MockTransport(routes)
