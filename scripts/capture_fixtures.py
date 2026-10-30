"""Fetch real Entur responses and save them as test fixtures."""
import json
from pathlib import Path

import httpx

from entur_mcp.entur import DEPARTURES_QUERY, GEOCODER_URL, GRAPHQL_URL

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
HEADERS = {"ET-Client-Name": "progdata-entur-mcp"}


def save(name: str, data: dict) -> None:
    path = FIXTURES / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {path}")


def main() -> None:
    geocoder = httpx.get(
        GEOCODER_URL,
        params={"text": "Lindeberg", "layers": "venue", "size": 5},
        headers=HEADERS,
    )
    geocoder.raise_for_status()
    save("geocoder_lindeberg.json", geocoder.json())

    departures = httpx.post(
        GRAPHQL_URL,
        json={
            "query": DEPARTURES_QUERY,
            "variables": {"id": "NSR:StopPlace:58222", "n": 50, "tr": 3600},
        },
        headers=HEADERS,
    )
    departures.raise_for_status()
    save("departures_lindeberg.json", departures.json())


if __name__ == "__main__":
    main()
