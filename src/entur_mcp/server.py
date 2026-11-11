import argparse
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from entur_mcp.config import DEFAULT_STOP_ID, TZ
from entur_mcp.departures import InvalidMode, group_departures, validate_modes
from entur_mcp.entur import EnturClient, EnturUnavailable, StopNotFound
from entur_mcp.models import DeparturesResult, StopMatch

ENTUR_DOWN = "Entur svarer ikke akkurat nå. Prøv igjen om litt."

# MCP Apps (io.modelcontextprotocol/ui): a host that supports it renders
# next_departures results with this HTML view instead of plain text.
DEPARTURES_APP_URI = "ui://entur/departures"
MCP_APP_MIME_TYPE = "text/html;profile=mcp-app"
DEPARTURES_APP_HTML = (Path(__file__).parent / "departures_app.html").read_text(encoding="utf-8")


def build_server(
    client: EnturClient | None = None,
    clock: Callable[[], datetime] | None = None,
    default_stop_id: str = DEFAULT_STOP_ID,
) -> MCPServer:
    client = client or EnturClient()
    clock = clock or (lambda: datetime.now(TZ))
    server = MCPServer(
        "entur",
        instructions="Sanntidsavganger for kollektivtrafikk i Norge via Entur.",
    )

    @server.tool()
    async def find_stop(name: str, limit: int = 5) -> list[StopMatch]:
        """Søk etter holdeplasser i Norge etter navn.

        Bruk denne når brukeren vil velge mellom flere holdeplasser med likt navn,
        eller trenger ID-en til en holdeplass.
        """
        _require_positive(limit=limit)
        try:
            return await client.find_stops(name, size=limit)
        except EnturUnavailable as e:
            raise ToolError(ENTUR_DOWN) from e

    @server.resource(
        DEPARTURES_APP_URI,
        name="departures_app",
        title="Avgangstavle",
        description="Viser resultatet fra next_departures som en avgangstavle.",
        mime_type=MCP_APP_MIME_TYPE,
    )
    def departures_app() -> str:
        return DEPARTURES_APP_HTML

    @server.tool(meta={"ui": {"resourceUri": DEPARTURES_APP_URI}})
    async def next_departures(
        stop: str | None = None,
        modes: list[str] | None = None,
        limit: int = 5,
        minutes_ahead: int = 60,
    ) -> DeparturesResult:
        """Neste avganger fra en holdeplass, med sanntid når den finnes.

        Uten `stop` brukes brukerens standardholdeplass, Lindeberg T i Oslo.
        `stop` kan være et holdeplassnavn eller en ID som NSR:StopPlace:58222.
        Avgangene er gruppert per plattform; destinasjonene i hver gruppe viser
        retningen (for eksempel mot sentrum). `modes` filtrerer på transporttype:
        metro (T-bane), bus, tram, rail, water, coach, air. `limit` er antall
        avganger per plattform. Innstilte avganger har cancelled=true, og
        realtime=false betyr at tiden er fra ruteplanen.
        """
        _require_positive(limit=limit, minutes_ahead=minutes_ahead)
        try:
            wanted_modes = validate_modes(modes)
            other_matches: list[StopMatch] = []
            if stop is None:
                stop_id = default_stop_id
            elif stop.startswith("NSR:StopPlace:"):
                stop_id = stop
            else:
                matches = await client.find_stops(stop)
                if not matches:
                    raise ToolError(f"Fant ingen holdeplass som heter «{stop}»")
                stop_id, other_matches = matches[0].id, matches[1:]

            stop_ref, calls = await client.estimated_calls(
                stop_id, minutes_ahead=minutes_ahead, modes=wanted_modes
            )
            directions = group_departures(calls, clock(), modes=wanted_modes, limit=limit)
        except EnturUnavailable as e:
            raise ToolError(ENTUR_DOWN) from e
        except StopNotFound as e:
            raise ToolError(f"Ukjent holdeplass-ID {e}") from e
        except InvalidMode as e:
            raise ToolError(str(e)) from e

        return DeparturesResult(
            stop=stop_ref,
            other_matches=other_matches,
            directions=directions,
            message=None if directions else f"Ingen avganger de neste {minutes_ahead} minuttene.",
        )

    return server


def _require_positive(**values: int) -> None:
    for name, value in values.items():
        if value < 1:
            raise ToolError(f"{name} må være minst 1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Entur MCP server")
    parser.add_argument("--http", action="store_true", help="Kjør med streamable HTTP i stedet for stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    server = build_server()
    if args.http:
        server.run("streamable-http", host=args.host, port=args.port)
    else:
        server.run("stdio")
