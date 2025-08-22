
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

def compute_norm(values: List[float]) -> Optional[float]:
    arr = np.array([v for v in values if v is not None])
    arr = arr[~np.isnan(arr)]
    if len(arr) < 14:
        return None
    return float(np.median(arr))

def classify(value: Optional[float], history: List[float]) -> Tuple[str, Optional[float]]:
    """Return ('green'|'red'|'none', norm) according to ±35% around median norm."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ("none", None)
    norm = compute_norm(history)
    if norm is None or norm == 0:
        return ("none", norm)
    delta = (value - norm) / norm
    if delta > 0.35:
        return ("green", norm)
    if delta < -0.35:
        return ("red", norm)
    return ("none", norm)
