"""Utilitaires de chargement de données pour Ghost Supply."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import rasterio
from loguru import logger


@dataclass
class MissionScenario:
    """Configuration de scénario de mission."""
    name: str
    origin: Tuple[float, float]
    destination: Tuple[float, float]
    cargo_type: str
    cargo_value: int
    weather: str
    departure_hour: int
    risk_tolerance: float


class DataLoader:
    """Gère le chargement des données DEM, OSM et scénarios."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.dem_dir = self.data_dir / "dem"
        self.osm_dir = self.data_dir / "osm"
        self.scenarios_dir = self.data_dir / "scenarios"
        self.synthetic_dir = self.data_dir / "synthetic"

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Crée les répertoires de données s'ils n'existent pas."""
        for directory in [self.dem_dir, self.osm_dir, self.scenarios_dir, self.synthetic_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def load_dem(self, filename: Optional[str] = None) -> Optional[Tuple[np.ndarray, Any]]:
        """
        Load Digital Elevation Model.

        Args:
            filename: DEM file name, if None looks for first .tif file

        Returns:
            Tuple of (elevation_array, transform) or None if not found
        """
        if filename is None:
            tif_files = list(self.dem_dir.glob("*.tif"))
            if not tif_files:
                logger.warning(f"No DEM files found in {self.dem_dir}")
                return None
            filename = tif_files[0].name

        dem_path = self.dem_dir / filename

        if not dem_path.exists():
            logger.warning(f"DEM file not found: {dem_path}")
            return None

        try:
            with rasterio.open(dem_path) as src:
                elevation = src.read(1)
                transform = src.transform
                logger.info(f"Loaded DEM: {dem_path} ({elevation.shape})")
                return elevation, transform
        except Exception as e:
            logger.error(f"Failed to load DEM: {e}")
            return None

    def create_synthetic_dem(
        self,
        bounds: Dict[str, float],
        resolution: int = 30,
        save: bool = True
    ) -> Tuple[np.ndarray, Any]:
        """
        Create synthetic DEM for testing when real data unavailable.

        Args:
            bounds: Dict with north, south, east, west
            resolution: Resolution in meters
            save: Whether to save the synthetic DEM

        Returns:
            Tuple of (elevation_array, transform)
        """
        from rasterio.transform import from_bounds

        lat_range = bounds["north"] - bounds["south"]
        lon_range = bounds["east"] - bounds["west"]

        height = int(lat_range * 111000 / resolution)
        width = int(lon_range * 111000 / resolution)

        x = np.linspace(0, 2 * np.pi, width)
        y = np.linspace(0, 2 * np.pi, height)
        X, Y = np.meshgrid(x, y)

        elevation = (
            200 +
            50 * np.sin(X) * np.cos(Y) +
            30 * np.sin(2 * X) +
            20 * np.cos(3 * Y) +
            10 * np.random.randn(height, width)
        )

        elevation = np.maximum(elevation, 0)

        transform = from_bounds(
            bounds["west"], bounds["south"],
            bounds["east"], bounds["north"],
            width, height
        )

        if save:
            output_path = self.dem_dir / "synthetic_dem.tif"
            self._save_geotiff(elevation, transform, output_path)
            logger.info(f"Saved synthetic DEM to {output_path}")

        return elevation, transform

    def _save_geotiff(
        self,
        array: np.ndarray,
        transform: Any,
        output_path: Path,
        crs: str = "EPSG:4326"
    ) -> None:
        """Save array as GeoTIFF."""
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=array.shape[0],
            width=array.shape[1],
            count=1,
            dtype=array.dtype,
            crs=crs,
            transform=transform,
        ) as dst:
            dst.write(array, 1)

    def load_scenario(self, scenario_name: str) -> Optional[MissionScenario]:
        """
        Load mission scenario from JSON.

        Args:
            scenario_name: Name of scenario file (without .json)

        Returns:
            MissionScenario object or None
        """
        scenario_path = self.scenarios_dir / f"{scenario_name}.json"

        if not scenario_path.exists():
            logger.warning(f"Scenario not found: {scenario_path}")
            return None

        try:
            with open(scenario_path) as f:
                data = json.load(f)

            return MissionScenario(
                name=data["name"],
                origin=tuple(data["origin"]),
                destination=tuple(data["destination"]),
                cargo_type=data["cargo_type"],
                cargo_value=data["cargo_value"],
                weather=data["weather"],
                departure_hour=data["departure_hour"],
                risk_tolerance=data.get("risk_tolerance", 0.95),
            )
        except Exception as e:
            logger.error(f"Failed to load scenario: {e}")
            return None

    def save_scenario(self, scenario: MissionScenario) -> None:
        """Save mission scenario to JSON."""
        scenario_path = self.scenarios_dir / f"{scenario.name}.json"

        data = {
            "name": scenario.name,
            "origin": list(scenario.origin),
            "destination": list(scenario.destination),
            "cargo_type": scenario.cargo_type,
            "cargo_value": scenario.cargo_value,
            "weather": scenario.weather,
            "departure_hour": scenario.departure_hour,
            "risk_tolerance": scenario.risk_tolerance,
        }

        with open(scenario_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved scenario to {scenario_path}")

    def load_incidents(self, filename: str = "incidents.csv") -> Optional[pd.DataFrame]:
        """
        Load historical incident data.

        Args:
            filename: CSV filename

        Returns:
            DataFrame with incident data or None
        """
        incidents_path = self.synthetic_dir / filename

        if not incidents_path.exists():
            logger.warning(f"Incidents file not found: {incidents_path}")
            return None

        try:
            df = pd.read_csv(incidents_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            logger.info(f"Loaded {len(df)} incidents from {incidents_path}")
            return df
        except Exception as e:
            logger.error(f"Failed to load incidents: {e}")
            return None

    def save_incidents(self, incidents: pd.DataFrame, filename: str = "incidents.csv") -> None:
        """Save incident data to CSV."""
        incidents_path = self.synthetic_dir / filename
        incidents.to_csv(incidents_path, index=False)
        logger.info(f"Saved {len(incidents)} incidents to {incidents_path}")

    def list_scenarios(self) -> List[str]:
        """List available scenario files."""
        return [f.stem for f in self.scenarios_dir.glob("*.json")]
