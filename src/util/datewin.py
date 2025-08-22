
from __future__ import annotations
import datetime as dt
from typing import Tuple

def berlin_bounds_for_date(d: dt.date) -> Tuple[dt.datetime, dt.datetime]:
    # midnight-to-midnight Europe/Berlin (naive, for APIs that take local or ISO strings)
    start = dt.datetime(d.year, d.month, d.day, 0, 0, 0)
    end = start + dt.timedelta(days=1)
    return start, end
