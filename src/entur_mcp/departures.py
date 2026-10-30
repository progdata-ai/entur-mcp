import math
from datetime import datetime

from entur_mcp.models import Call, Departure, DirectionGroup

VALID_MODES: frozenset[str] = frozenset({"metro", "bus", "tram", "rail", "water", "coach", "air"})

# Rail-bound modes are listed before buses, so the metro is easy to find.
MODE_ORDER = {"metro": 0, "tram": 0, "rail": 0}


class InvalidMode(ValueError):
    pass


def group_departures(
    calls: list[Call], now: datetime, modes: list[str] | None = None, limit: int = 5
) -> list[DirectionGroup]:
    wanted = None
    if modes:
        wanted = {m.lower() for m in modes}
        unknown = wanted - VALID_MODES
        if unknown:
            raise InvalidMode(
                f"Ukjent modus: {', '.join(sorted(unknown))}. "
                f"Gyldige moduser: {', '.join(sorted(VALID_MODES))}"
            )

    by_quay: dict[str, list[Call]] = {}
    for call in calls:
        if call.expected < now:
            continue
        if wanted is not None and call.mode not in wanted:
            continue
        by_quay.setdefault(call.quay_id, []).append(call)

    groups = []
    for quay_id, quay_calls in by_quay.items():
        quay_calls = sorted(quay_calls, key=lambda c: c.expected)[:limit]
        first = quay_calls[0]
        groups.append(
            DirectionGroup(
                quay_id=quay_id,
                platform=first.platform,
                quay_name=first.quay_name,
                destinations=list(dict.fromkeys(c.destination for c in quay_calls)),
                departures=[_departure(c, now) for c in quay_calls],
            )
        )

    groups.sort(key=lambda g: (MODE_ORDER.get(g.departures[0].mode, 1), g.departures[0].expected))
    return groups


def _departure(call: Call, now: datetime) -> Departure:
    return Departure(
        line=call.line,
        mode=call.mode,
        destination=call.destination,
        aimed=call.aimed,
        expected=call.expected,
        minutes_until=math.floor((call.expected - now).total_seconds() / 60),
        realtime=call.realtime,
        cancelled=call.cancelled,
        notices=call.notices,
    )
