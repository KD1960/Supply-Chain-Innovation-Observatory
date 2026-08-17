"""US state centroids for the Build Map.

USAspending reports a place of performance as a state code, so a dot needs
coordinates from somewhere. State resolution answers the question the Build Map
asks — which states are gaining logistics capability — without vendoring a
megabyte of ZIP centroids.
"""

from __future__ import annotations

STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "AL": (32.79, -86.83), "AK": (64.07, -152.28), "AZ": (34.27, -111.66),
    "AR": (34.90, -92.44), "CA": (37.18, -119.47), "CO": (38.997, -105.55),
    "CT": (41.62, -72.73), "DE": (38.99, -75.51), "DC": (38.90, -77.02),
    "FL": (28.63, -82.45), "GA": (32.64, -83.44), "HI": (20.29, -156.37),
    "ID": (44.39, -114.66), "IL": (40.06, -89.19), "IN": (39.89, -86.28),
    "IA": (42.07, -93.50), "KS": (38.49, -98.38), "KY": (37.53, -85.30),
    "LA": (31.07, -92.00), "ME": (45.37, -69.24), "MD": (39.04, -76.79),
    "MA": (42.26, -71.81), "MI": (44.35, -85.41), "MN": (46.28, -94.31),
    "MS": (32.74, -89.66), "MO": (38.37, -92.48), "MT": (47.05, -109.63),
    "NE": (41.53, -99.80), "NV": (39.35, -116.63), "NH": (43.68, -71.58),
    "NJ": (40.19, -74.67), "NM": (34.41, -106.11), "NY": (42.95, -75.53),
    "NC": (35.56, -79.39), "ND": (47.45, -100.47), "OH": (40.29, -82.79),
    "OK": (35.59, -97.49), "OR": (43.94, -120.56), "PA": (40.88, -77.80),
    "RI": (41.68, -71.56), "SC": (33.92, -80.90), "SD": (44.44, -100.23),
    "TN": (35.86, -86.35), "TX": (31.43, -99.33), "UT": (39.33, -111.68),
    "VT": (44.07, -72.67), "VA": (37.52, -78.85), "WA": (47.38, -120.45),
    "WV": (38.64, -80.62), "WI": (44.62, -89.99), "WY": (42.998, -107.55),
}

# Continental bounds, used to frame the Build Map. Alaska and Hawaii fall
# outside and are drawn clamped to the edge rather than dropped.
CONUS_BOUNDS = (24.5, 49.5, -125.0, -66.5)


def centroid(state_code: str | None) -> tuple[float, float] | None:
    if not state_code:
        return None
    return STATE_CENTROIDS.get(state_code.strip().upper())
