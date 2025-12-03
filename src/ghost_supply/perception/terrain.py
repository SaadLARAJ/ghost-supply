"""Terrain analysis module for visibility and mobility calculations."""

from typing import Dict, List, Optional, Tuple

import numpy as np
try:
    import richdem as rd
    HAS_RICHDEM = True
except ImportError:
    HAS_RICHDEM = False
from loguru import logger
from scipy.ndimage import distance_transform_edt

from ghost_supply.utils.constants import (
    DEM_RESOLUTION_M,
    SLOPE_PENALTY,
    SPEED_OFFROAD_DRY,
    SPEED_PATH_DRY,
    SPEED_PRIMARY_DRY,
    SPEED_SECONDARY_DRY,
    SPEED_TERTIARY_DRY,
    SPEED_TRACK_DRY,
    VIEWSHED_MAX_DISTANCE_KM,
    VIEWSHED_OBSERVER_HEIGHT_M,
    VIEWSHED_TARGET_HEIGHT_M,
)
from ghost_supply.utils.geo import haversine_distance, latlon_to_meters


class TerrainAnalyzer:
    """Analyzes terrain for tactical route planning."""

    def __init__(self, elevation: np.ndarray, transform: any, bounds: Dict[str, float]):
        """
        Initialize terrain analyzer.

        Args:
            elevation: 2D array of elevation values in meters
            transform: Rasterio transform object
            bounds: Dict with north, south, east, west bounds
        """
        self.elevation = elevation
        self.transform = transform
        self.bounds = bounds
        self.height, self.width = elevation.shape

        self.slope_array: Optional[np.ndarray] = None
        self.viewshed_cache: Dict[Tuple[int, int], np.ndarray] = {}

        logger.info(f"Initialized TerrainAnalyzer: {self.width}x{self.height} cells")

    def calculate_slope(self) -> np.ndarray:
        """
        Calculate slope for entire terrain.
        Uses richdem if available, otherwise numpy gradient fallback.

        Returns:
            2D array of slope values in degrees
        """
        if self.slope_array is not None:
            return self.slope_array

        logger.info("Calculating terrain slope...")

        if HAS_RICHDEM:
            dem = rd.rdarray(self.elevation, no_data=-9999)
            slope = rd.TerrainAttribute(dem, attrib='slope_degrees')
            self.slope_array = np.array(slope)
        else:
            logger.warning("richdem not available, using numpy gradient fallback")
            dy, dx = np.gradient(self.elevation, DEM_RESOLUTION_M)
            slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
            self.slope_array = np.degrees(slope_rad)

        logger.info(f"Slope calculated: min={self.slope_array.min():.1f}°, max={self.slope_array.max():.1f}°")

        return self.slope_array

    def calculate_viewshed(
        self,
        observer_positions: List[Tuple[float, float]],
        observer_height: float = VIEWSHED_OBSERVER_HEIGHT_M,
        target_height: float = VIEWSHED_TARGET_HEIGHT_M,
        max_distance_km: float = VIEWSHED_MAX_DISTANCE_KM,
    ) -> np.ndarray:
        """
        Calculate composite viewshed from multiple observer positions.

        Args:
            observer_positions: List of (lat, lon) observer positions
            observer_height: Height of observer above ground (m)
            target_height: Height of target above ground (m)
            max_distance_km: Maximum observation distance (km)

        Returns:
            2D array where values range 0 (invisible) to 1 (visible by all)
        """
        logger.info(f"Calculating viewshed for {len(observer_positions)} observers...")

        composite_viewshed = np.zeros((self.height, self.width), dtype=float)

        for obs_lat, obs_lon in observer_positions:
            obs_row, obs_col = self._latlon_to_rowcol(obs_lat, obs_lon)

            if not (0 <= obs_row < self.height and 0 <= obs_col < self.width):
                logger.warning(f"Observer position ({obs_lat}, {obs_lon}) outside bounds")
                continue

            viewshed = self._calculate_single_viewshed(
                obs_row, obs_col, observer_height, target_height, max_distance_km
            )

            composite_viewshed += viewshed

        if len(observer_positions) > 0:
            composite_viewshed /= len(observer_positions)

        logger.info(f"Viewshed calculated: {(composite_viewshed > 0).sum()} visible cells")

        return composite_viewshed

    def _calculate_single_viewshed(
        self,
        obs_row: int,
        obs_col: int,
        observer_height: float,
        target_height: float,
        max_distance_km: float,
    ) -> np.ndarray:
        """
        Calculate viewshed from single observer using simplified algorithm.

        Args:
            obs_row, obs_col: Observer position in array coordinates
            observer_height: Height of observer (m)
            target_height: Height of target (m)
            max_distance_km: Maximum distance (km)

        Returns:
            Binary viewshed array
        """
        cache_key = (obs_row, obs_col)
        if cache_key in self.viewshed_cache:
            return self.viewshed_cache[cache_key]

        viewshed = np.zeros((self.height, self.width), dtype=float)

        observer_elevation = self.elevation[obs_row, obs_col] + observer_height

        max_distance_cells = int(max_distance_km * 1000 / DEM_RESOLUTION_M)

        row_min = max(0, obs_row - max_distance_cells)
        row_max = min(self.height, obs_row + max_distance_cells + 1)
        col_min = max(0, obs_col - max_distance_cells)
        col_max = min(self.width, obs_col + max_distance_cells + 1)

        for target_row in range(row_min, row_max):
            for target_col in range(col_min, col_max):
                if target_row == obs_row and target_col == obs_col:
                    viewshed[target_row, target_col] = 1.0
                    continue

                distance_cells = np.sqrt((target_row - obs_row)**2 + (target_col - obs_col)**2)

                if distance_cells > max_distance_cells:
                    continue

                target_elevation = self.elevation[target_row, target_col] + target_height

                visible = self._check_line_of_sight(
                    obs_row, obs_col, observer_elevation,
                    target_row, target_col, target_elevation
                )

                if visible:
                    viewshed[target_row, target_col] = 1.0

        self.viewshed_cache[cache_key] = viewshed

        return viewshed

    def _check_line_of_sight(
        self,
        obs_row: int, obs_col: int, obs_elev: float,
        target_row: int, target_col: int, target_elev: float,
        num_samples: int = 50
    ) -> bool:
        """
        Check if line of sight is clear between observer and target.

        Args:
            obs_row, obs_col: Observer position
            obs_elev: Observer elevation (including height)
            target_row, target_col: Target position
            target_elev: Target elevation (including height)
            num_samples: Number of points to sample along line

        Returns:
            True if line of sight is clear
        """
        for i in range(1, num_samples):
            ratio = i / num_samples

            sample_row = int(obs_row + ratio * (target_row - obs_row))
            sample_col = int(obs_col + ratio * (target_col - obs_col))

            if not (0 <= sample_row < self.height and 0 <= sample_col < self.width):
                continue

            los_elevation = obs_elev + ratio * (target_elev - obs_elev)

            terrain_elevation = self.elevation[sample_row, sample_col]

            if terrain_elevation > los_elevation:
                return False

        return True

    def get_mobility_speed(
        self,
        road_type: str,
        weather: str,
        slope_deg: Optional[float] = None
    ) -> float:
        """
        Calculate mobility speed based on road type, weather, and slope.

        Args:
            road_type: Road type (primary, secondary, tertiary, track, path, offroad)
            weather: Weather condition (clear, fog, rain, snow, rasputitsa)
            slope_deg: Slope in degrees (optional)

        Returns:
            Speed in km/h
        """
        from ghost_supply.utils.constants import WEATHER_IMPACT

        speed_map_dry = {
            "primary": SPEED_PRIMARY_DRY,
            "secondary": SPEED_SECONDARY_DRY,
            "tertiary": SPEED_TERTIARY_DRY,
            "track": SPEED_TRACK_DRY,
            "path": SPEED_PATH_DRY,
            "offroad": SPEED_OFFROAD_DRY,
        }

        base_speed = speed_map_dry.get(road_type, SPEED_TRACK_DRY)

        weather_factor = WEATHER_IMPACT.get(weather, {}).get("speed_road", 1.0)
        if road_type in ["track", "path", "offroad"]:
            weather_factor = WEATHER_IMPACT.get(weather, {}).get("speed_offroad", 1.0)

        speed = base_speed * weather_factor

        if slope_deg is not None:
            slope_pct = np.tan(np.radians(slope_deg)) * 100
            if slope_pct < 5:
                slope_factor = SLOPE_PENALTY["0-5"]
            elif slope_pct < 10:
                slope_factor = SLOPE_PENALTY["5-10"]
            elif slope_pct < 15:
                slope_factor = SLOPE_PENALTY["10-15"]
            elif slope_pct < 20:
                slope_factor = SLOPE_PENALTY["15-20"]
            else:
                slope_factor = SLOPE_PENALTY[">20"]

            speed *= slope_factor

        return max(speed, 1.0)

    def get_elevation_at(self, lat: float, lon: float) -> Optional[float]:
        """
        Get elevation at specific lat/lon coordinate.

        Args:
            lat, lon: Coordinates

        Returns:
            Elevation in meters or None if outside bounds
        """
        row, col = self._latlon_to_rowcol(lat, lon)

        if 0 <= row < self.height and 0 <= col < self.width:
            return float(self.elevation[row, col])

        return None

    def get_visibility_at(self, lat: float, lon: float, viewshed: np.ndarray) -> float:
        """
        Get viewshed value at specific lat/lon coordinate.

        Args:
            lat, lon: Coordinates
            viewshed: Viewshed array

        Returns:
            Visibility score (0-1)
        """
        row, col = self._latlon_to_rowcol(lat, lon)

        if 0 <= row < self.height and 0 <= col < self.width:
            return float(viewshed[row, col])

        return 0.0

    def _latlon_to_rowcol(self, lat: float, lon: float) -> Tuple[int, int]:
        """
        Convert lat/lon to array row/col indices.

        Args:
            lat, lon: Coordinates

        Returns:
            Tuple of (row, col)
        """
        x = (lon - self.bounds["west"]) / (self.bounds["east"] - self.bounds["west"])
        y = (self.bounds["north"] - lat) / (self.bounds["north"] - self.bounds["south"])

        col = int(x * self.width)
        row = int(y * self.height)

        return row, col

    def _rowcol_to_latlon(self, row: int, col: int) -> Tuple[float, float]:
        """
        Convert array row/col to lat/lon.

        Args:
            row, col: Array indices

        Returns:
            Tuple of (lat, lon)
        """
        x = col / self.width
        y = row / self.height

        lon = self.bounds["west"] + x * (self.bounds["east"] - self.bounds["west"])
        lat = self.bounds["north"] - y * (self.bounds["north"] - self.bounds["south"])

        return lat, lon
