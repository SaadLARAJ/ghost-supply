"""Weather impact modeling for tactical operations."""

from dataclasses import dataclass
from typing import Dict

from ghost_supply.utils.constants import WEATHER_CONDITIONS, WEATHER_IMPACT


@dataclass
class WeatherCondition:
    """Weather condition with tactical implications."""
    condition: str
    optical_drone_effectiveness: float
    thermal_drone_effectiveness: float
    road_speed_factor: float
    offroad_speed_factor: float
    rf_propagation_factor: float

    @property
    def is_favorable_for_movement(self) -> bool:
        """Check if weather favors movement (low drone effectiveness)."""
        return self.optical_drone_effectiveness < 0.5

    @property
    def tactical_advantage(self) -> str:
        """Describe tactical advantage of current weather."""
        if self.condition == "fog":
            return "Excellent - severely limits optical drones, thermal partially effective"
        elif self.condition == "rain":
            return "Good - reduces drone effectiveness, moderate speed impact"
        elif self.condition == "snow":
            return "Moderate - limits optical, slows movement"
        elif self.condition == "rasputitsa":
            return "Mixed - off-road impossible, but drones still effective"
        else:
            return "Poor - clear visibility favors enemy surveillance"


class WeatherModel:
    """Models weather impact on tactical operations."""

    def __init__(self):
        self.weather_impact = WEATHER_IMPACT
        self.conditions = WEATHER_CONDITIONS

    def get_weather_condition(self, weather: str) -> WeatherCondition:
        """
        Get weather condition with all impact factors.

        Args:
            weather: Weather type

        Returns:
            WeatherCondition object
        """
        if weather not in self.weather_impact:
            weather = "clear"

        impact = self.weather_impact[weather]

        return WeatherCondition(
            condition=weather,
            optical_drone_effectiveness=impact["optical_drone"],
            thermal_drone_effectiveness=impact["thermal_drone"],
            road_speed_factor=impact["speed_road"],
            offroad_speed_factor=impact["speed_offroad"],
            rf_propagation_factor=impact["rf_propagation"],
        )

    def get_detection_probability_modifier(self, weather: str, time_of_day: str) -> float:
        """
        Calculate detection probability modifier based on weather and time.

        Args:
            weather: Weather condition
            time_of_day: "day" or "night"

        Returns:
            Multiplier for detection probability (0-1)
        """
        condition = self.get_weather_condition(weather)

        if time_of_day == "night":
            effectiveness = condition.thermal_drone_effectiveness
        else:
            effectiveness = max(
                condition.optical_drone_effectiveness,
                condition.thermal_drone_effectiveness
            )

        return effectiveness

    def get_speed_modifier(self, weather: str, road_type: str) -> float:
        """
        Get speed modifier for given weather and road type.

        Args:
            weather: Weather condition
            road_type: Road type

        Returns:
            Speed multiplier (0-1)
        """
        condition = self.get_weather_condition(weather)

        if road_type in ["primary", "secondary", "tertiary"]:
            return condition.road_speed_factor
        else:
            return condition.offroad_speed_factor

    def recommend_departure_weather(self) -> Dict[str, str]:
        """
        Recommend best weather conditions for movement.

        Returns:
            Dict mapping weather to recommendation
        """
        recommendations = {}

        for weather in self.conditions:
            condition = self.get_weather_condition(weather)

            if condition.optical_drone_effectiveness < 0.3:
                recommendations[weather] = "Highly recommended - excellent concealment"
            elif condition.optical_drone_effectiveness < 0.5:
                recommendations[weather] = "Recommended - good concealment"
            elif condition.optical_drone_effectiveness < 0.7:
                recommendations[weather] = "Acceptable - moderate concealment"
            else:
                recommendations[weather] = "Not recommended - high visibility"

        return recommendations

    def get_window_of_opportunity(
        self,
        weather_forecast: Dict[int, str],
        min_duration_hours: int = 2
    ) -> list:
        """
        Identify optimal movement windows from weather forecast.

        Args:
            weather_forecast: Dict mapping hour to weather condition
            min_duration_hours: Minimum continuous favorable hours

        Returns:
            List of (start_hour, end_hour, weather) tuples
        """
        windows = []
        current_window_start = None
        current_weather = None

        for hour in sorted(weather_forecast.keys()):
            weather = weather_forecast[hour]
            condition = self.get_weather_condition(weather)

            if condition.is_favorable_for_movement:
                if current_window_start is None:
                    current_window_start = hour
                    current_weather = weather
            else:
                if current_window_start is not None:
                    duration = hour - current_window_start
                    if duration >= min_duration_hours:
                        windows.append((current_window_start, hour, current_weather))
                    current_window_start = None
                    current_weather = None

        if current_window_start is not None:
            last_hour = max(weather_forecast.keys())
            duration = last_hour - current_window_start + 1
            if duration >= min_duration_hours:
                windows.append((current_window_start, last_hour + 1, current_weather))

        return windows

    def calculate_mission_weather_risk(
        self,
        weather: str,
        duration_hours: float,
        time_of_day: str
    ) -> float:
        """
        Calculate overall weather risk for mission.

        Args:
            weather: Weather condition
            duration_hours: Mission duration
            time_of_day: "day" or "night"

        Returns:
            Risk score (0-1, higher is more risky)
        """
        detection_prob = self.get_detection_probability_modifier(weather, time_of_day)

        exposure_factor = min(duration_hours / 4.0, 1.0)

        risk = detection_prob * (0.7 + 0.3 * exposure_factor)

        return min(risk, 1.0)
