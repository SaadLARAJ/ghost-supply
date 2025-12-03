"""Facility location optimization for depot selection."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from ghost_supply.utils.constants import (
    DEPOT_MAX_DISTANCE_KM,
    DEPOT_MIN_DISTANCE_KM,
    FRONTLINE_BUFFER_KM,
)
from ghost_supply.utils.geo import haversine_distance


@dataclass
class DepotCandidate:
    """Depot candidate location with attributes."""
    id: int
    latitude: float
    longitude: float
    name: str
    protection_score: float
    accessibility_score: float
    rf_coverage_score: float
    distance_to_front_km: float
    total_score: float = 0.0


def select_depots(
    candidates: List[Tuple[float, float, str, float, float]],
    frontline_lat: float,
    frontline_lon: float,
    num_depots: int = 3,
    min_separation_km: float = 5.0,
) -> List[DepotCandidate]:
    """
    Select optimal depot locations from candidates.

    Args:
        candidates: List of (lat, lon, name, protection, accessibility) tuples
        frontline_lat, frontline_lon: Approximate frontline position
        num_depots: Number of depots to select
        min_separation_km: Minimum separation between depots

    Returns:
        List of selected DepotCandidate objects
    """
    logger.info(f"Selecting {num_depots} depots from {len(candidates)} candidates")

    depot_candidates = []

    for i, (lat, lon, name, protection, accessibility) in enumerate(candidates):
        distance_to_front = haversine_distance(lat, lon, frontline_lat, frontline_lon)

        distance_score = _score_distance_to_front(distance_to_front)

        rf_coverage_score = np.random.uniform(0.6, 1.0)

        total_score = (
            0.3 * distance_score +
            0.3 * protection +
            0.25 * accessibility +
            0.15 * rf_coverage_score
        )

        depot = DepotCandidate(
            id=i,
            latitude=lat,
            longitude=lon,
            name=name,
            protection_score=protection,
            accessibility_score=accessibility,
            rf_coverage_score=rf_coverage_score,
            distance_to_front_km=distance_to_front,
            total_score=total_score,
        )

        depot_candidates.append(depot)

    depot_candidates.sort(key=lambda d: d.total_score, reverse=True)

    selected = []

    for candidate in depot_candidates:
        if len(selected) >= num_depots:
            break

        too_close = False
        for existing in selected:
            distance = haversine_distance(
                candidate.latitude, candidate.longitude,
                existing.latitude, existing.longitude
            )

            if distance < min_separation_km:
                too_close = True
                break

        if not too_close:
            selected.append(candidate)

    logger.info(f"Selected {len(selected)} depots")

    for i, depot in enumerate(selected):
        logger.info(
            f"  Depot {i+1}: {depot.name} - "
            f"score={depot.total_score:.2f}, "
            f"distance={depot.distance_to_front_km:.1f}km"
        )

    return selected


def _score_distance_to_front(distance_km: float) -> float:
    """
    Score depot based on distance to frontline.

    Optimal range is DEPOT_MIN_DISTANCE_KM to DEPOT_MAX_DISTANCE_KM.

    Args:
        distance_km: Distance to frontline in km

    Returns:
        Score (0-1)
    """
    if distance_km < DEPOT_MIN_DISTANCE_KM:
        score = distance_km / DEPOT_MIN_DISTANCE_KM * 0.5

    elif distance_km <= DEPOT_MAX_DISTANCE_KM:
        score = 1.0

    else:
        excess = distance_km - DEPOT_MAX_DISTANCE_KM
        penalty = min(excess / 10.0, 0.7)
        score = 1.0 - penalty

    return max(score, 0.0)


def generate_candidate_depots(
    bounds: Dict[str, float],
    frontline_lat: float,
    num_candidates: int = 20,
    seed: int = 42
) -> List[Tuple[float, float, str, float, float]]:
    """
    Generate synthetic depot candidates for testing.

    Args:
        bounds: Geographic bounds
        frontline_lat: Frontline latitude
        num_candidates: Number of candidates
        seed: Random seed

    Returns:
        List of (lat, lon, name, protection, accessibility) tuples
    """
    np.random.seed(seed)

    candidates = []

    facility_types = [
        ("Warehouse", 0.6, 0.9),
        ("Underground bunker", 0.95, 0.5),
        ("Factory", 0.7, 0.8),
        ("Cave", 0.9, 0.4),
        ("Parking garage", 0.5, 0.95),
    ]

    for i in range(num_candidates):
        lat = frontline_lat - np.random.uniform(0.1, 0.4)

        lon = np.random.uniform(bounds["west"], bounds["east"])

        facility_type, base_protection, base_accessibility = facility_types[i % len(facility_types)]

        protection = base_protection + np.random.normal(0, 0.1)
        protection = np.clip(protection, 0.0, 1.0)

        accessibility = base_accessibility + np.random.normal(0, 0.1)
        accessibility = np.clip(accessibility, 0.0, 1.0)

        name = f"{facility_type} {chr(65 + i)}"

        candidates.append((lat, lon, name, protection, accessibility))

    logger.info(f"Generated {num_candidates} candidate depot locations")

    return candidates
