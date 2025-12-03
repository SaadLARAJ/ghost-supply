"""RF propagation modeling using simplified Longley-Rice model."""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from ghost_supply.utils.constants import (
    RF_FREQUENCY_COMMS_MHZ,
    RF_FREQUENCY_DRONE_MHZ,
    RF_FRESNEL_CRITICAL,
    RF_FRESNEL_DEGRADED,
    RF_GOOD_SIGNAL_DBM,
    RF_JAMMING_THRESHOLD_DBM,
    RF_MIN_SIGNAL_DBM,
    RF_RX_ANTENNA_HEIGHT_M,
    RF_TX_ANTENNA_HEIGHT_M,
    RF_TX_POWER_DBM,
)
from ghost_supply.utils.geo import haversine_distance, latlon_to_meters


class RFPropagationModel:
    """RF propagation model for tactical communications analysis."""

    def __init__(
        self,
        elevation: np.ndarray,
        bounds: Dict[str, float],
        resolution_m: float = 30.0
    ):
        """
        Initialize RF propagation model.

        Args:
            elevation: 2D elevation array in meters
            bounds: Dict with north, south, east, west
            resolution_m: DEM resolution in meters
        """
        self.elevation = elevation
        self.bounds = bounds
        self.resolution_m = resolution_m
        self.height, self.width = elevation.shape

        logger.info(f"Initialized RFPropagationModel: {self.width}x{self.height} cells")

    def calculate_coverage_map(
        self,
        base_stations: List[Tuple[float, float]],
        frequency_mhz: float = RF_FREQUENCY_DRONE_MHZ,
        tx_power_dbm: float = RF_TX_POWER_DBM,
        tx_height_m: float = RF_TX_ANTENNA_HEIGHT_M,
        rx_height_m: float = RF_RX_ANTENNA_HEIGHT_M,
    ) -> np.ndarray:
        """
        Calculate RF coverage map from base stations.

        Args:
            base_stations: List of (lat, lon) transmitter positions
            frequency_mhz: Frequency in MHz
            tx_power_dbm: Transmit power in dBm
            tx_height_m: Transmitter antenna height in meters
            rx_height_m: Receiver antenna height in meters

        Returns:
            2D array of received signal strength in dBm
        """
        logger.info(f"Calculating RF coverage for {len(base_stations)} base stations at {frequency_mhz} MHz...")

        coverage_map = np.full((self.height, self.width), -200.0)

        for bs_lat, bs_lon in base_stations:
            bs_row, bs_col = self._latlon_to_rowcol(bs_lat, bs_lon)

            if not (0 <= bs_row < self.height and 0 <= bs_col < self.width):
                logger.warning(f"Base station ({bs_lat}, {bs_lon}) outside bounds")
                continue

            bs_elevation = self.elevation[bs_row, bs_col] + tx_height_m

            for row in range(self.height):
                for col in range(self.width):
                    rx_lat, rx_lon = self._rowcol_to_latlon(row, col)
                    distance_km = haversine_distance(bs_lat, bs_lon, rx_lat, rx_lon)

                    if distance_km < 0.01:
                        signal_dbm = tx_power_dbm
                    else:
                        rx_elevation = self.elevation[row, col] + rx_height_m

                        path_loss = self._calculate_path_loss(
                            bs_row, bs_col, bs_elevation,
                            row, col, rx_elevation,
                            distance_km, frequency_mhz
                        )

                        signal_dbm = tx_power_dbm - path_loss

                    coverage_map[row, col] = max(coverage_map[row, col], signal_dbm)

        logger.info(f"Coverage calculated: {(coverage_map > RF_MIN_SIGNAL_DBM).sum()} cells with signal")

        return coverage_map

    def _calculate_path_loss(
        self,
        tx_row: int, tx_col: int, tx_elevation: float,
        rx_row: int, rx_col: int, rx_elevation: float,
        distance_km: float,
        frequency_mhz: float
    ) -> float:
        """
        Calculate path loss using simplified Longley-Rice model.

        Args:
            tx_row, tx_col, tx_elevation: Transmitter position and elevation
            rx_row, rx_col, rx_elevation: Receiver position and elevation
            distance_km: Distance in kilometers
            frequency_mhz: Frequency in MHz

        Returns:
            Path loss in dB
        """
        free_space_loss = self._free_space_loss(distance_km, frequency_mhz)

        los_clear = self._check_line_of_sight(
            tx_row, tx_col, tx_elevation,
            rx_row, rx_col, rx_elevation
        )

        if los_clear:
            diffraction_loss = 0.0
        else:
            diffraction_loss = self._knife_edge_diffraction_loss(
                tx_row, tx_col, tx_elevation,
                rx_row, rx_col, rx_elevation,
                frequency_mhz
            )

        terrain_factor = self._terrain_irregularity_factor(
            tx_row, tx_col, rx_row, rx_col
        )

        total_loss = free_space_loss + diffraction_loss + terrain_factor

        return total_loss

    def _free_space_loss(self, distance_km: float, frequency_mhz: float) -> float:
        """
        Calculate free space path loss.

        Args:
            distance_km: Distance in km
            frequency_mhz: Frequency in MHz

        Returns:
            Loss in dB
        """
        if distance_km < 0.001:
            distance_km = 0.001

        loss_db = 32.45 + 20 * math.log10(frequency_mhz) + 20 * math.log10(distance_km)

        return loss_db

    def _check_line_of_sight(
        self,
        tx_row: int, tx_col: int, tx_elev: float,
        rx_row: int, rx_col: int, rx_elev: float,
        num_samples: int = 50
    ) -> bool:
        """
        Check if line of sight is clear for RF propagation.

        Args:
            tx_row, tx_col, tx_elev: Transmitter position and elevation
            rx_row, rx_col, rx_elev: Receiver position and elevation
            num_samples: Number of samples along path

        Returns:
            True if LOS is clear
        """
        if tx_row == rx_row and tx_col == rx_col:
            return True

        for i in range(1, num_samples):
            ratio = i / num_samples

            sample_row = int(tx_row + ratio * (rx_row - tx_row))
            sample_col = int(tx_col + ratio * (rx_col - tx_col))

            if not (0 <= sample_row < self.height and 0 <= sample_col < self.width):
                continue

            los_elev = tx_elev + ratio * (rx_elev - tx_elev)

            terrain_elev = self.elevation[sample_row, sample_col]

            if terrain_elev > los_elev - 5:
                return False

        return True

    def _knife_edge_diffraction_loss(
        self,
        tx_row: int, tx_col: int, tx_elev: float,
        rx_row: int, rx_col: int, rx_elev: float,
        frequency_mhz: float
    ) -> float:
        """
        Calculate knife-edge diffraction loss.

        Args:
            tx_row, tx_col, tx_elev: Transmitter
            rx_row, rx_col, rx_elev: Receiver
            frequency_mhz: Frequency in MHz

        Returns:
            Diffraction loss in dB
        """
        wavelength_m = 299.792458 / frequency_mhz

        max_obstruction = 0.0
        num_samples = 50

        for i in range(1, num_samples):
            ratio = i / num_samples

            sample_row = int(tx_row + ratio * (rx_row - tx_row))
            sample_col = int(tx_col + ratio * (rx_col - tx_col))

            if not (0 <= sample_row < self.height and 0 <= sample_col < self.width):
                continue

            los_elev = tx_elev + ratio * (rx_elev - tx_elev)
            terrain_elev = self.elevation[sample_row, sample_col]

            obstruction = terrain_elev - los_elev

            max_obstruction = max(max_obstruction, obstruction)

        if max_obstruction <= 0:
            return 0.0

        v = max_obstruction * math.sqrt(2 / wavelength_m)

        if v < -1:
            loss = 0
        elif v < 0:
            loss = 20 * math.log10(0.5 - 0.62 * v)
        elif v < 1:
            loss = 20 * math.log10(0.5 * math.exp(-0.95 * v))
        elif v < 2.4:
            loss = 20 * math.log10(0.4 - math.sqrt(0.1184 - (0.38 - 0.1 * v)**2))
        else:
            loss = 20 * math.log10(0.225 / v)

        return max(loss, 0)

    def _terrain_irregularity_factor(
        self,
        tx_row: int, tx_col: int,
        rx_row: int, rx_col: int
    ) -> float:
        """
        Calculate additional loss from terrain irregularity.

        Args:
            tx_row, tx_col: Transmitter position
            rx_row, rx_col: Receiver position

        Returns:
            Additional loss in dB
        """
        num_samples = 20
        elevations = []

        for i in range(num_samples + 1):
            ratio = i / num_samples

            sample_row = int(tx_row + ratio * (rx_row - tx_row))
            sample_col = int(tx_col + ratio * (rx_col - tx_col))

            if 0 <= sample_row < self.height and 0 <= sample_col < self.width:
                elevations.append(self.elevation[sample_row, sample_col])

        if len(elevations) < 2:
            return 0.0

        std_dev = np.std(elevations)

        irregularity_loss = min(std_dev / 10.0, 15.0)

        return irregularity_loss

    def identify_rf_shadow_zones(self, coverage_map: np.ndarray) -> np.ndarray:
        """
        Identify RF shadow zones where signal is weak or absent.

        Args:
            coverage_map: RF coverage map in dBm

        Returns:
            Binary array (1 = shadow zone, 0 = coverage)
        """
        shadow_zones = (coverage_map < RF_MIN_SIGNAL_DBM).astype(int)

        logger.info(f"Identified {shadow_zones.sum()} shadow zone cells")

        return shadow_zones

    def calculate_jamming_vulnerability(
        self,
        coverage_map: np.ndarray,
        jammer_positions: List[Tuple[float, float]],
        jammer_power_dbm: float = 40.0
    ) -> np.ndarray:
        """
        Calculate vulnerability to jamming.

        Args:
            coverage_map: Friendly RF coverage in dBm
            jammer_positions: Enemy jammer positions
            jammer_power_dbm: Jammer transmit power

        Returns:
            Vulnerability map (0-1, higher = more vulnerable)
        """
        logger.info(f"Calculating jamming vulnerability from {len(jammer_positions)} jammers...")

        jammer_coverage = self.calculate_coverage_map(
            jammer_positions,
            frequency_mhz=RF_FREQUENCY_DRONE_MHZ,
            tx_power_dbm=jammer_power_dbm,
            tx_height_m=10.0,
            rx_height_m=RF_RX_ANTENNA_HEIGHT_M,
        )

        signal_to_jammer_ratio = coverage_map - jammer_coverage

        vulnerability = 1.0 / (1.0 + np.exp(signal_to_jammer_ratio / 10.0))

        return vulnerability

    def get_signal_at(self, lat: float, lon: float, coverage_map: np.ndarray) -> float:
        """
        Get signal strength at specific position.

        Args:
            lat, lon: Position
            coverage_map: Coverage map

        Returns:
            Signal strength in dBm
        """
        row, col = self._latlon_to_rowcol(lat, lon)

        if 0 <= row < self.height and 0 <= col < self.width:
            return float(coverage_map[row, col])

        return -200.0

    def _latlon_to_rowcol(self, lat: float, lon: float) -> Tuple[int, int]:
        """Convert lat/lon to array indices."""
        x = (lon - self.bounds["west"]) / (self.bounds["east"] - self.bounds["west"])
        y = (self.bounds["north"] - lat) / (self.bounds["north"] - self.bounds["south"])

        col = int(x * self.width)
        row = int(y * self.height)

        return row, col

    def _rowcol_to_latlon(self, row: int, col: int) -> Tuple[float, float]:
        """Convert array indices to lat/lon."""
        x = col / self.width
        y = row / self.height

        lon = self.bounds["west"] + x * (self.bounds["east"] - self.bounds["west"])
        lat = self.bounds["north"] - y * (self.bounds["north"] - self.bounds["south"])

        return lat, lon
