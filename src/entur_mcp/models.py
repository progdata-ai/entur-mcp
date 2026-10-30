from datetime import datetime

from pydantic import BaseModel


class StopMatch(BaseModel):
    id: str
    name: str
    locality: str | None
    categories: list[str]


class StopRef(BaseModel):
    id: str
    name: str


class Call(BaseModel):
    """One departure as returned by Entur, before filtering and grouping."""

    line: str
    mode: str
    destination: str
    aimed: datetime
    expected: datetime
    realtime: bool
    cancelled: bool
    notices: list[str]
    quay_id: str
    platform: str | None
    quay_name: str


class Departure(BaseModel):
    line: str
    mode: str
    destination: str
    aimed: datetime
    expected: datetime
    minutes_until: int
    realtime: bool
    cancelled: bool
    notices: list[str]


class DirectionGroup(BaseModel):
    """Departures from one platform (quay), which in practice is one direction."""

    quay_id: str
    platform: str | None
    quay_name: str
    destinations: list[str]
    departures: list[Departure]


class DeparturesResult(BaseModel):
    stop: StopRef
    other_matches: list[StopMatch]
    directions: list[DirectionGroup]
    message: str | None = None
