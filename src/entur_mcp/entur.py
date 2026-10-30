import httpx

from entur_mcp.config import ENTUR_CLIENT_NAME, ENTUR_TIMEOUT_S
from entur_mcp.models import Call, StopMatch, StopRef

GEOCODER_URL = "https://api.entur.io/geocoder/v1/autocomplete"
GRAPHQL_URL = "https://api.entur.io/journey-planner/v3/graphql"

DEPARTURES_QUERY = """
query($id: String!, $n: Int!, $tr: Int!, $modes: [TransportMode]) {
  stopPlace(id: $id) {
    id
    name
    estimatedCalls(numberOfDepartures: $n, timeRange: $tr, whiteListedModes: $modes, includeCancelledTrips: true, arrivalDeparture: departures) {
      realtime
      cancellation
      aimedDepartureTime
      expectedDepartureTime
      quay { id publicCode name }
      destinationDisplay { frontText }
      serviceJourney { line { publicCode transportMode } }
      situations { summary { value language } }
    }
  }
}
"""


class EnturUnavailable(Exception):
    """Entur did not answer, or answered with an error."""


class StopNotFound(Exception):
    """No stop place with the given ID."""


class EnturClient:
    def __init__(
        self,
        client_name: str = ENTUR_CLIENT_NAME,
        timeout_s: float = ENTUR_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client_name = client_name
        self.timeout_s = timeout_s
        self.transport = transport

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(
                headers={"ET-Client-Name": self.client_name},
                timeout=self.timeout_s,
                transport=self.transport,
            ) as http:
                response = await http.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise EnturUnavailable(str(e)) from e

    async def find_stops(self, text: str, size: int = 5) -> list[StopMatch]:
        data = await self._request(
            "GET", GEOCODER_URL, params={"text": text, "layers": "venue", "size": size}
        )
        return [
            StopMatch(
                id=f["properties"]["id"],
                name=f["properties"]["name"],
                locality=f["properties"].get("locality"),
                categories=f["properties"].get("category", []),
            )
            for f in data.get("features", [])
            # The venue layer can also return groups of stops, which have no departures
            if f["properties"]["id"].startswith("NSR:StopPlace:")
        ]

    async def estimated_calls(
        self, stop_id: str, minutes_ahead: int, number: int = 50, modes: list[str] | None = None
    ) -> tuple[StopRef, list[Call]]:
        data = await self._request(
            "POST",
            GRAPHQL_URL,
            json={
                "query": DEPARTURES_QUERY,
                "variables": {"id": stop_id, "n": number, "tr": minutes_ahead * 60, "modes": modes},
            },
        )
        if data.get("errors"):
            raise EnturUnavailable(data["errors"][0].get("message", "GraphQL error"))
        stop_place = (data.get("data") or {}).get("stopPlace")
        if stop_place is None:
            raise StopNotFound(stop_id)
        stop = StopRef(id=stop_place["id"], name=stop_place["name"])
        calls = (_parse_call(c) for c in stop_place["estimatedCalls"])
        return stop, [c for c in calls if c is not None]


def _parse_call(call: dict) -> Call | None:
    """Parse one departure, or return None if Entur left out a field we need."""
    try:
        return _parse_complete_call(call)
    except (KeyError, TypeError):
        return None


def _parse_complete_call(call: dict) -> Call:
    line = call["serviceJourney"]["line"]
    quay = call["quay"]
    return Call(
        line=line["publicCode"],
        mode=line["transportMode"],
        destination=call["destinationDisplay"]["frontText"],
        aimed=call["aimedDepartureTime"],
        expected=call["expectedDepartureTime"],
        realtime=call["realtime"],
        cancelled=call["cancellation"],
        notices=[s["summary"][0]["value"] for s in call["situations"] if s.get("summary")],
        quay_id=quay["id"],
        platform=quay.get("publicCode") or None,
        quay_name=quay["name"],
    )
