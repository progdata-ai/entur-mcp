# Entur MCP

MCP server for real-time public transport departures in Norway, using the open [Entur](https://developer.entur.org/) API. Ask Claude "when does the next metro leave?" and get live departures, grouped by platform. Lindeberg T (Oslo) is the default stop.

Works with Claude Desktop (stdio) and with any MCP client over streamable HTTP, such as [progdata-agent](https://github.com/santhanc/progdata-agent).

## Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `next_departures` | `stop?`, `modes?`, `limit=5`, `minutes_ahead=60` | Next departures, grouped per platform (one direction each). `stop` is a name or an `NSR:StopPlace:` ID; empty means the default stop. `modes`: `metro`, `bus`, `tram`, `rail`, `water`, `coach`, `air`. `limit` is per platform. |
| `find_stop` | `name`, `limit=5` | Search stops by name. Returns ID, name, municipality and categories. |

Each departure has line, mode, destination, aimed and expected time, `minutes_until`, `realtime` (false means timetable only), `cancelled` and service notices. When a stop name is ambiguous ("Lindeberg" also matches Lindeberg stasjon in Lillestrøm), the other matches are returned in `other_matches`.

## Tech Stack

- **Python 3.11** with **uv**
- **MCP Python SDK** 2.x (`MCPServer`), stdio and streamable HTTP
- **httpx** — async client for Entur's geocoder and JourneyPlanner v3 (GraphQL)
- **Pydantic** — structured tool output
- **pytest** — tests against recorded Entur responses, no network needed
- **Docker** — HTTP mode in a container

## Getting Started

    git clone https://github.com/santhanc/entur-mcp
    cd entur-mcp
    uv sync

### Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

    {
      "mcpServers": {
        "entur": {
          "command": "uv",
          "args": ["--directory", "/absolute/path/to/entur-mcp", "run", "entur-mcp"]
        }
      }
    }

Restart Claude Desktop and ask "Når går neste T-bane?".

### HTTP

    uv run entur-mcp --http --port 8100

The MCP endpoint is `http://127.0.0.1:8100/mcp`. The server has no authentication, so it binds to localhost by default (`--host` changes that).

### Docker

    docker build -t entur-mcp .
    docker run --rm -p 127.0.0.1:8100:8100 entur-mcp

## Configuration

| Variable            | Default                | Description                                  |
|---------------------|------------------------|----------------------------------------------|
| `ENTUR_CLIENT_NAME` | `progdata-entur-mcp`   | Sent as `ET-Client-Name`, required by Entur  |
| `DEFAULT_STOP_ID`   | `NSR:StopPlace:58222`  | Stop used when none is given (Lindeberg T)   |
| `ENTUR_TIMEOUT_S`   | `10`                   | Timeout for Entur requests                   |

Entur's API is open and needs no key, but asks every client to identify itself with `ET-Client-Name`.

## Tests

    uv run pytest

Tests use recorded responses in `tests/fixtures/` and a fixed clock. To refresh the fixtures from Entur:

    uv run python scripts/capture_fixtures.py

The fixtures were hand-edited to include a cancelled departure and a service notice, so check the tests after refreshing.

A live test calls the real API and is skipped by default:

    uv run pytest -m live

It expects the metro to run at Lindeberg, so it fails at night.

## Roadmap

- [ ] Use from progdata-agent as an MCP client (step 2)
- [ ] Deploy to AWS together with progdata-agent
