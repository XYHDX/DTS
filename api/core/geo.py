"""Utilities for parsing PostGIS geometry values returned by Supabase/PostgREST."""

import re
import struct
from typing import Optional, Tuple


def parse_location(loc) -> Tuple[Optional[float], Optional[float]]:
    """Extract (latitude, longitude) from a PostGIS geometry value.

    Handles GeoJSON dicts and WKB hex strings as returned by PostgREST.
    Returns (lat, lon) or (None, None) if unparseable.
    """
    if loc is None:
        return None, None

    # GeoJSON: {"type": "Point", "coordinates": [lon, lat]}
    if isinstance(loc, dict):
        coords = loc.get("coordinates")
        if coords and len(coords) >= 2:
            return float(coords[1]), float(coords[0])
        return None, None

    # WKB hex string
    if isinstance(loc, str):
        # Try WKB hex first
        try:
            data = bytes.fromhex(loc)
            byte_order = "<" if data[0] == 1 else ">"
            wkb_type = struct.unpack(f"{byte_order}I", data[1:5])[0]

            offset = 5
            # Check if SRID is included (flag 0x20000000)
            if wkb_type & 0x20000000:
                offset += 4  # Skip SRID bytes
                wkb_type &= ~0x20000000

            if wkb_type == 1:  # Point
                x, y = struct.unpack(f"{byte_order}dd", data[offset : offset + 16])
                return y, x  # lat=Y, lon=X
        except (ValueError, struct.error, IndexError):
            pass

        # Try WKT: "POINT(lon lat)" or "SRID=4326;POINT(lon lat)"
        m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", loc, re.IGNORECASE)
        if m:
            return float(m.group(2)), float(m.group(1))

    return None, None
