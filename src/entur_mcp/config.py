import os
from zoneinfo import ZoneInfo

ENTUR_CLIENT_NAME = os.getenv("ENTUR_CLIENT_NAME", "progdata-entur-mcp")
DEFAULT_STOP_ID = os.getenv("DEFAULT_STOP_ID", "NSR:StopPlace:58222")
ENTUR_TIMEOUT_S = float(os.getenv("ENTUR_TIMEOUT_S", "10"))
TZ = ZoneInfo("Europe/Oslo")
