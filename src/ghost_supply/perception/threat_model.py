"""Threat prediction using time series and spatial clustering."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger
from prophet import Prophet
from sklearn.cluster import DBSCAN

from ghost_supply.utils.constants import (
    STUDY_AREA_BOUNDS,
    SYNTHETIC_DAYS_HISTORY,
    SYNTHETIC_INCIDENT_TYPES,
    SYNTHETIC_NUM_INCIDENTS,
    THREAT_BASE_DETECTION_OFFROAD,
    THREAT_BASE_DETECTION_ROAD,
    THREAT_BASE_DETECTION_TRACK,
    THREAT_CLUSTER_EPS_KM,
    THREAT_CLUSTER_MIN_SAMPLES,
    THREAT_DAY_NIGHT_RATIO,
    THREAT_FOG_REDUCTION,
    THREAT_RAIN_REDUCTION,
    THREAT_SNOW_REDUCTION,
)
from ghost_supply.utils.geo import haversine_distance, latlon_to_meters


class ThreatPredictor:
    """Predicts threat levels using temporal and spatial analysis."""

    def __init__(self):
        self.incidents: Optional[pd.DataFrame] = None
        self.prophet_model: Optional[Prophet] = None
        self.kill_zones: List[Dict] = []
        self.study_area = STUDY_AREA_BOUNDS

    def generate_synthetic_incidents(
        self,
        num_incidents: int = SYNTHETIC_NUM_INCIDENTS,
        days_history: int = SYNTHETIC_DAYS_HISTORY,
        seed: int = 42
    ) -> pd.DataFrame:
        """
        Generate synthetic incident data with realistic patterns.

        Args:
            num_incidents: Number of incidents to generate
            days_history: Days of historical data
            seed: Random seed

        Returns:
            DataFrame with incident data
        """
        logger.info(f"Generating {num_incidents} synthetic incidents over {days_history} days...")

        np.random.seed(seed)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_history)

        incidents = []

        frontline_lat = (self.study_area["north"] + self.study_area["south"]) / 2
        frontline_variation = 0.05

        main_road_lats = [frontline_lat - 0.1, frontline_lat - 0.2, frontline_lat - 0.3]
        main_road_lons = [(self.study_area["east"] + self.study_area["west"]) / 2] * 3

        for _ in range(num_incidents):
            timestamp = start_date + timedelta(
                seconds=np.random.randint(0, int((end_date - start_date).total_seconds()))
            )

            hour = timestamp.hour
            is_daylight = 6 <= hour <= 20

            day_prob = 0.75
            night_prob = 0.25

            if is_daylight:
                prob_threshold = day_prob
            else:
                prob_threshold = night_prob

            if np.random.random() > prob_threshold:
                continue

            incident_type_probs = {
                "drone_strike": 0.35,
                "artillery": 0.30,
                "ambush": 0.15,
                "mine": 0.10,
                "sniper": 0.10,
            }

            incident_type = np.random.choice(
                list(incident_type_probs.keys()),
                p=list(incident_type_probs.values())
            )

            location_type = np.random.choice(
                ["road", "frontline", "random"],
                p=[0.5, 0.3, 0.2]
            )

            if location_type == "road":
                road_idx = np.random.randint(0, len(main_road_lats))
                lat = main_road_lats[road_idx] + np.random.normal(0, 0.01)
                lon = main_road_lons[road_idx] + np.random.normal(0, 0.02)
            elif location_type == "frontline":
                lat = frontline_lat + np.random.normal(0, frontline_variation)
                lon = np.random.uniform(self.study_area["west"], self.study_area["east"])
            else:
                lat = np.random.uniform(self.study_area["south"], self.study_area["north"])
                lon = np.random.uniform(self.study_area["west"], self.study_area["east"])

            incidents.append({
                "timestamp": timestamp,
                "type": incident_type,
                "latitude": lat,
                "longitude": lon,
                "casualties": np.random.choice([0, 1, 2, 3, 5], p=[0.4, 0.3, 0.15, 0.1, 0.05]),
            })

        df = pd.DataFrame(incidents)
        df = df.sort_values("timestamp").reset_index(drop=True)

        self.incidents = df

        logger.info(f"Generated {len(df)} incidents")
        logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

        return df

    def train_temporal_model(self, incidents: Optional[pd.DataFrame] = None) -> None:
        """
        Train Prophet model for temporal threat prediction.

        Args:
            incidents: Incident DataFrame (uses self.incidents if None)
        """
        if incidents is not None:
            self.incidents = incidents

        if self.incidents is None:
            raise ValueError("No incidents data available. Generate or load incidents first.")

        logger.info("Training Prophet temporal threat model...")

        hourly_counts = self.incidents.set_index("timestamp").resample("H").size().reset_index()
        hourly_counts.columns = ["ds", "y"]

        hourly_counts["hour"] = hourly_counts["ds"].dt.hour
        hourly_counts["day_of_week"] = hourly_counts["ds"].dt.dayofweek

        self.prophet_model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=True,
            changepoint_prior_scale=0.05,
        )

        self.prophet_model.add_regressor("hour")

        self.prophet_model.fit(hourly_counts)

        logger.info("Prophet model trained successfully")

    def identify_kill_zones(
        self,
        eps_km: float = THREAT_CLUSTER_EPS_KM,
        min_samples: int = THREAT_CLUSTER_MIN_SAMPLES
    ) -> List[Dict]:
        """
        Identify kill zones using DBSCAN clustering.

        Args:
            eps_km: Clustering radius in kilometers
            min_samples: Minimum incidents to form cluster

        Returns:
            List of kill zone dictionaries
        """
        if self.incidents is None:
            raise ValueError("No incidents data available")

        logger.info(f"Identifying kill zones (eps={eps_km}km, min_samples={min_samples})...")

        coords = self.incidents[["latitude", "longitude"]].values

        ref_lat = self.study_area["south"]
        ref_lon = self.study_area["west"]

        coords_meters = np.array([
            latlon_to_meters(lat, lon, ref_lat, ref_lon) for lat, lon in coords
        ])

        eps_meters = eps_km * 1000

        clustering = DBSCAN(eps=eps_meters, min_samples=min_samples, metric="euclidean")
        labels = clustering.fit_predict(coords_meters)

        self.kill_zones = []

        for cluster_id in set(labels):
            if cluster_id == -1:
                continue

            cluster_mask = labels == cluster_id
            cluster_incidents = self.incidents[cluster_mask]

            center_lat = cluster_incidents["latitude"].mean()
            center_lon = cluster_incidents["longitude"].mean()

            distances = [
                haversine_distance(center_lat, center_lon, row["latitude"], row["longitude"])
                for _, row in cluster_incidents.iterrows()
            ]

            radius_90pct = np.percentile(distances, 90)

            kill_zone = {
                "id": cluster_id,
                "center": (center_lat, center_lon),
                "radius_km": radius_90pct,
                "num_incidents": len(cluster_incidents),
                "incident_types": cluster_incidents["type"].value_counts().to_dict(),
                "avg_casualties": cluster_incidents["casualties"].mean(),
            }

            self.kill_zones.append(kill_zone)

        logger.info(f"Identified {len(self.kill_zones)} kill zones")

        return self.kill_zones

    def predict_threat_at_time(self, timestamp: datetime) -> float:
        """
        Predict threat level at specific time.

        Args:
            timestamp: Time to predict

        Returns:
            Threat multiplier (0-2, where 1.0 is baseline)
        """
        if self.prophet_model is None:
            logger.warning("Prophet model not trained, using baseline")
            return 1.0

        future_df = pd.DataFrame({
            "ds": [timestamp],
            "hour": [timestamp.hour],
        })

        forecast = self.prophet_model.predict(future_df)

        predicted_incidents = max(forecast["yhat"].values[0], 0)

        avg_incidents = self.incidents.groupby(self.incidents["timestamp"].dt.hour).size().mean()

        threat_multiplier = predicted_incidents / avg_incidents if avg_incidents > 0 else 1.0

        threat_multiplier = np.clip(threat_multiplier, 0.1, 2.0)

        return threat_multiplier

    def risk_at(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
        road_type: str = "track",
        weather: str = "clear"
    ) -> float:
        """
        Calculate risk at specific position and time.

        Args:
            lat, lon: Position
            timestamp: Time
            road_type: Road type
            weather: Weather condition

        Returns:
            Risk probability (0-1)
        """
        if road_type == "primary":
            base_risk = THREAT_BASE_DETECTION_ROAD
        elif road_type in ["secondary", "tertiary"]:
            base_risk = THREAT_BASE_DETECTION_ROAD * 0.8
        elif road_type in ["track", "path"]:
            base_risk = THREAT_BASE_DETECTION_TRACK
        else:
            base_risk = THREAT_BASE_DETECTION_OFFROAD

        temporal_mult = self.predict_threat_at_time(timestamp)

        hour = timestamp.hour
        if 6 <= hour <= 8 or 16 <= hour <= 18:
            temporal_mult *= 1.3

        is_night = hour < 6 or hour > 20
        if is_night:
            temporal_mult *= (1.0 / THREAT_DAY_NIGHT_RATIO)

        weather_mult = 1.0
        if weather == "rain":
            weather_mult = 1.0 - THREAT_RAIN_REDUCTION
        elif weather == "fog":
            weather_mult = 1.0 - THREAT_FOG_REDUCTION
        elif weather == "snow":
            weather_mult = 1.0 - THREAT_SNOW_REDUCTION

        spatial_mult = 1.0
        for kz in self.kill_zones:
            distance = haversine_distance(lat, lon, kz["center"][0], kz["center"][1])
            if distance <= kz["radius_km"]:
                intensity = kz["num_incidents"] / SYNTHETIC_NUM_INCIDENTS
                proximity = 1.0 - (distance / kz["radius_km"])
                spatial_mult += intensity * proximity

        total_risk = base_risk * temporal_mult * weather_mult * spatial_mult

        return min(total_risk, 1.0)

    def get_kill_zone_at(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Check if position is in a kill zone.

        Args:
            lat, lon: Position

        Returns:
            Kill zone dict or None
        """
        for kz in self.kill_zones:
            distance = haversine_distance(lat, lon, kz["center"][0], kz["center"][1])
            if distance <= kz["radius_km"]:
                return kz

        return None
