"""Geospatial utility functions."""

import math
from typing import List, Tuple

import numpy as np
from geopy.distance import geodesic


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate haversine distance between two points in kilometers.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in kilometers
    """
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate initial bearing from point 1 to point 2.

    Args:
        lat1, lon1: Start point coordinates
        lat2, lon2: End point coordinates

    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon_rad = math.radians(lon2 - lon1)

    y = math.sin(dlon_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)

    bearing_rad = math.atan2(y, x)
    bearing_deg = math.degrees(bearing_rad)

    return (bearing_deg + 360) % 360


def destination_point(
    lat: float, lon: float, bearing_deg: float, distance_km: float
) -> Tuple[float, float]:
    """
    Calculate destination point given start point, bearing, and distance.

    Args:
        lat, lon: Start point coordinates
        bearing_deg: Bearing in degrees
        distance_km: Distance in kilometers

    Returns:
        Tuple of (latitude, longitude)
    """
    R = 6371.0  # Earth radius in km

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_deg)

    lat2_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_km / R) +
        math.cos(lat_rad) * math.sin(distance_km / R) * math.cos(bearing_rad)
    )

    lon2_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_km / R) * math.cos(lat_rad),
        math.cos(distance_km / R) - math.sin(lat_rad) * math.sin(lat2_rad)
    )

    return math.degrees(lat2_rad), math.degrees(lon2_rad)


def calculate_slope(elevation1: float, elevation2: float, distance_m: float) -> float:
    """
    Calculate slope percentage between two points.

    Args:
        elevation1: First elevation in meters
        elevation2: Second elevation in meters
        distance_m: Horizontal distance in meters

    Returns:
        Slope as percentage
    """
    if distance_m == 0:
        return 0.0
    return abs((elevation2 - elevation1) / distance_m) * 100


def get_slope_category(slope_pct: float) -> str:
    """
    Categorize slope percentage.

    Args:
        slope_pct: Slope as percentage

    Returns:
        Category string
    """
    if slope_pct < 5:
        return "0-5"
    elif slope_pct < 10:
        return "5-10"
    elif slope_pct < 15:
        return "10-15"
    elif slope_pct < 20:
        return "15-20"
    else:
        return ">20"


def interpolate_path(
    path: List[Tuple[float, float]], num_points: int
) -> List[Tuple[float, float]]:
    """
    Interpolate additional points along a path.

    Args:
        path: List of (lat, lon) tuples
        num_points: Total number of points desired

    Returns:
        Interpolated path
    """
    if len(path) < 2:
        return path

    distances = [0.0]
    for i in range(1, len(path)):
        dist = haversine_distance(path[i-1][0], path[i-1][1], path[i][0], path[i][1])
        distances.append(distances[-1] + dist)

    total_distance = distances[-1]
    if total_distance == 0:
        return path

    interpolated = []
    target_distances = np.linspace(0, total_distance, num_points)

    for target_dist in target_distances:
        for i in range(len(distances) - 1):
            if distances[i] <= target_dist <= distances[i + 1]:
                ratio = (target_dist - distances[i]) / (distances[i + 1] - distances[i])
                lat = path[i][0] + ratio * (path[i + 1][0] - path[i][0])
                lon = path[i][1] + ratio * (path[i + 1][1] - path[i][1])
                interpolated.append((lat, lon))
                break

    return interpolated


def point_in_circle(
    point_lat: float, point_lon: float,
    center_lat: float, center_lon: float,
    radius_km: float
) -> bool:
    """
    Check if point is within circle.

    Args:
        point_lat, point_lon: Point coordinates
        center_lat, center_lon: Circle center coordinates
        radius_km: Circle radius in kilometers

    Returns:
        True if point is inside circle
    """
    distance = haversine_distance(point_lat, point_lon, center_lat, center_lon)
    return distance <= radius_km


def calculate_path_length(path: List[Tuple[float, float]]) -> float:
    """
    Calculate total length of a path in kilometers.

    Args:
        path: List of (lat, lon) tuples

    Returns:
        Total distance in kilometers
    """
    if len(path) < 2:
        return 0.0

    total = 0.0
    for i in range(1, len(path)):
        total += haversine_distance(path[i-1][0], path[i-1][1], path[i][0], path[i][1])

    return total


def latlon_to_meters(lat: float, lon: float, ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """
    Convert lat/lon to local x,y in meters relative to reference point.

    Args:
        lat, lon: Point to convert
        ref_lat, ref_lon: Reference point

    Returns:
        (x, y) in meters
    """
    R = 6371000  # Earth radius in meters

    x = R * math.radians(lon - ref_lon) * math.cos(math.radians(ref_lat))
    y = R * math.radians(lat - ref_lat)

    return x, y


def meters_to_latlon(x: float, y: float, ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """
    Convert local x,y in meters to lat/lon.

    Args:
        x, y: Coordinates in meters
        ref_lat, ref_lon: Reference point

    Returns:
        (lat, lon)
    """
    R = 6371000  # Earth radius in meters

    lat = ref_lat + math.degrees(y / R)
    lon = ref_lon + math.degrees(x / (R * math.cos(math.radians(ref_lat))))

    return lat, lon


def calculate_azimuth_elevation(
    observer_lat: float, observer_lon: float, observer_alt: float,
    target_lat: float, target_lon: float, target_alt: float
) -> Tuple[float, float]:
    """
    Calculate azimuth and elevation angle from observer to target.

    Args:
        observer_lat, observer_lon, observer_alt: Observer position and altitude (m)
        target_lat, target_lon, target_alt: Target position and altitude (m)

    Returns:
        (azimuth in degrees, elevation angle in degrees)
    """
    azimuth = bearing(observer_lat, observer_lon, target_lat, target_lon)

    distance_km = haversine_distance(observer_lat, observer_lon, target_lat, target_lon)
    distance_m = distance_km * 1000

    height_diff = target_alt - observer_alt

    elevation_angle = math.degrees(math.atan2(height_diff, distance_m))

    return azimuth, elevation_angle


def line_of_sight_clear(
    elevations: np.ndarray,
    observer_idx: int,
    target_idx: int,
    observer_height: float = 3.0,
    target_height: float = 2.5
) -> bool:
    """
    Check if line of sight is clear between observer and target.

    Args:
        elevations: Array of elevations along the path
        observer_idx: Index of observer position
        target_idx: Index of target position
        observer_height: Height of observer above ground (m)
        target_height: Height of target above ground (m)

    Returns:
        True if line of sight is clear
    """
    if observer_idx == target_idx:
        return True

    start = min(observer_idx, target_idx)
    end = max(observer_idx, target_idx)

    observer_elev = elevations[observer_idx] + observer_height
    target_elev = elevations[target_idx] + target_height

    for i in range(start + 1, end):
        ratio = (i - start) / (end - start)
        los_elev = observer_elev + ratio * (target_elev - observer_elev)

        if elevations[i] > los_elev:
            return False

    return True
