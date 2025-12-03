"""Project-wide constants for Ghost Supply tactical optimizer."""

from typing import Dict

# =============================================================================
# STUDY AREA - Pokrovsk Region, Donbass
# =============================================================================

# STUDY AREA - A smaller test area centered on Pokrovsk
# The original area was too large and caused OSMnx to hang.
# This smaller box (~5x5km) should load quickly.
STUDY_AREA_BOUNDS = {
    "north": 48.325,
    "south": 48.275,
    "east": 37.275,
    "west": 37.225,
}

STUDY_AREA_CENTER = {
    "lat": (STUDY_AREA_BOUNDS["north"] + STUDY_AREA_BOUNDS["south"]) / 2,
    "lon": (STUDY_AREA_BOUNDS["east"] + STUDY_AREA_BOUNDS["west"]) / 2,
}

# =============================================================================
# RF PROPAGATION PARAMETERS
# =============================================================================

# Frequencies (MHz)
RF_FREQUENCY_DRONE_MHZ = 2400  # 2.4 GHz - civilian drone control
RF_FREQUENCY_COMMS_MHZ = 900   # 900 MHz - tactical communications

# Transmitter parameters
RF_TX_POWER_DBM = 30           # 1W transmitter
RF_TX_ANTENNA_HEIGHT_M = 10    # Base station antenna height
RF_RX_ANTENNA_HEIGHT_M = 50    # Drone/receiver height

# Signal thresholds
RF_MIN_SIGNAL_DBM = -90        # Minimum signal for control
RF_JAMMING_THRESHOLD_DBM = -70  # Vulnerability to jamming threshold
RF_GOOD_SIGNAL_DBM = -60       # Good signal threshold

# Fresnel zone obstruction limits
RF_FRESNEL_CRITICAL = 0.6      # >60% obstruction = critical
RF_FRESNEL_DEGRADED = 0.4      # >40% obstruction = degraded

# =============================================================================
# THREAT MODEL PARAMETERS
# =============================================================================

# Temporal patterns
THREAT_DAY_NIGHT_RATIO = 3.0   # 3x more dangerous during day
THREAT_DAWN_PEAK_MULTIPLIER = 1.5  # Peak activity 6-8h
THREAT_DUSK_PEAK_MULTIPLIER = 1.3  # Peak activity 16-18h

# Weather impact on threat detection
THREAT_RAIN_REDUCTION = 0.5    # 50% reduction in detection under rain
THREAT_FOG_REDUCTION = 0.3     # 70% reduction in optical detection
THREAT_SNOW_REDUCTION = 0.4    # 60% reduction under snow

# Threat clustering (DBSCAN)
THREAT_CLUSTER_EPS_KM = 2.0    # 2km radius for kill zone clustering
THREAT_CLUSTER_MIN_SAMPLES = 5 # Minimum incidents to form kill zone

# Base detection probabilities
THREAT_BASE_DETECTION_ROAD = 0.4    # 40% on major roads
THREAT_BASE_DETECTION_TRACK = 0.2   # 20% on tracks
THREAT_BASE_DETECTION_OFFROAD = 0.1 # 10% off-road

# =============================================================================
# MOBILITY PARAMETERS (km/h)
# =============================================================================

# Primary roads (paved highways)
SPEED_PRIMARY_DRY = 60
SPEED_PRIMARY_RAIN = 40
SPEED_PRIMARY_MUD = 20
SPEED_PRIMARY_SNOW = 30

# Secondary roads (paved)
SPEED_SECONDARY_DRY = 40
SPEED_SECONDARY_RAIN = 25
SPEED_SECONDARY_MUD = 10
SPEED_SECONDARY_SNOW = 20

# Tertiary roads (minor paved)
SPEED_TERTIARY_DRY = 35
SPEED_TERTIARY_RAIN = 20
SPEED_TERTIARY_MUD = 8
SPEED_TERTIARY_SNOW = 15

# Tracks (unpaved roads)
SPEED_TRACK_DRY = 30
SPEED_TRACK_RAIN = 15
SPEED_TRACK_MUD = 5
SPEED_TRACK_SNOW = 12

# Paths (trails)
SPEED_PATH_DRY = 20
SPEED_PATH_RAIN = 10
SPEED_PATH_MUD = 3
SPEED_PATH_SNOW = 8

# Off-road (fields)
SPEED_OFFROAD_DRY = 15
SPEED_OFFROAD_RAIN = 5
SPEED_OFFROAD_MUD = 1
SPEED_OFFROAD_SNOW = 5

# Slope penalty multiplier
SLOPE_PENALTY: Dict[str, float] = {
    "0-5": 1.0,     # No penalty
    "5-10": 0.9,    # 10% reduction
    "10-15": 0.7,   # 30% reduction
    "15-20": 0.5,   # 50% reduction
    ">20": 0.3,     # 70% reduction
}

# =============================================================================
# CVAR OPTIMIZATION PARAMETERS
# =============================================================================

CVAR_DEFAULT_ALPHA = 0.95      # 95th percentile risk
CVAR_NUM_SCENARIOS = 100       # Number of risk scenarios to generate
CVAR_SOLVER = "glpk"           # Default solver (glpk, cbc, highs)
CVAR_TIME_LIMIT_SEC = 300      # 5 minute solver timeout

# Objective function weights (default balanced)
CVAR_WEIGHT_TIME = 0.5
CVAR_WEIGHT_RISK = 0.5
CVAR_WEIGHT_FUEL = 0.0         # Optional fuel consideration

# =============================================================================
# CARGO STRATEGIC VALUES
# =============================================================================

CARGO_VALUES: Dict[str, int] = {
    "munitions": 9,   # Highest priority
    "medical": 7,     # Critical supplies
    "fuel": 6,        # Operational necessity
    "food": 5,        # Morale and sustenance
    "equipment": 6,   # General equipment
    "personnel": 10,  # Human lives (highest)
}

# =============================================================================
# WEATHER CONDITIONS
# =============================================================================

WEATHER_CONDITIONS = ["clear", "fog", "rain", "snow", "rasputitsa"]

WEATHER_IMPACT: Dict[str, Dict[str, float]] = {
    "clear": {
        "optical_drone": 1.0,
        "thermal_drone": 1.0,
        "speed_road": 1.0,
        "speed_offroad": 1.0,
        "rf_propagation": 1.0,
    },
    "fog": {
        "optical_drone": 0.1,   # Severely reduced optical
        "thermal_drone": 0.6,   # Thermal still works
        "speed_road": 0.8,
        "speed_offroad": 0.6,
        "rf_propagation": 0.9,
    },
    "rain": {
        "optical_drone": 0.4,
        "thermal_drone": 0.7,
        "speed_road": 0.7,
        "speed_offroad": 0.3,
        "rf_propagation": 0.85,
    },
    "snow": {
        "optical_drone": 0.3,
        "thermal_drone": 0.8,
        "speed_road": 0.5,
        "speed_offroad": 0.2,
        "rf_propagation": 0.8,
    },
    "rasputitsa": {  # Mud season - Spring/Autumn thaw
        "optical_drone": 0.6,
        "thermal_drone": 0.9,
        "speed_road": 0.4,      # Even paved roads affected
        "speed_offroad": 0.05,  # Off-road nearly impassable
        "rf_propagation": 1.0,
    },
}

# =============================================================================
# TERRAIN ANALYSIS
# =============================================================================

# Viewshed parameters
VIEWSHED_MAX_DISTANCE_KM = 10.0    # Maximum observation distance
VIEWSHED_OBSERVER_HEIGHT_M = 3.0   # Observer height (e.g., watchtower)
VIEWSHED_TARGET_HEIGHT_M = 2.5     # Vehicle height

# DEM resolution
DEM_RESOLUTION_M = 30  # SRTM 30m resolution

# =============================================================================
# MISSION PARAMETERS
# =============================================================================

# Tactical distances
DEPOT_MIN_DISTANCE_KM = 15  # Minimum safe distance from front
DEPOT_MAX_DISTANCE_KM = 25  # Maximum practical distance
FRONTLINE_BUFFER_KM = 5     # Distance to consider "frontline"

# Timing
NIGHT_START_HOUR = 20       # 8 PM
NIGHT_END_HOUR = 6          # 6 AM
DAWN_HOUR = 6
DUSK_HOUR = 18

# Fuel consumption (L/100km)
FUEL_CONSUMPTION_ROAD = 25
FUEL_CONSUMPTION_OFFROAD = 40

# =============================================================================
# GAME THEORY PARAMETERS
# =============================================================================

GAME_NUM_ROUTES = 5             # K best routes to consider
GAME_NUM_DEFENDER_CONFIGS = 5   # M defender configurations
GAME_PATROL_RADIUS_KM = 3.0     # Patrol coverage radius

# =============================================================================
# VISUALIZATION PARAMETERS
# =============================================================================

# Map colors
COLOR_ROUTE_OPTIMAL = "#00FF00"     # Green
COLOR_ROUTE_BASELINE = "#FF0000"    # Red
COLOR_KILLZONE = "#FF000040"        # Translucent red
COLOR_DEPOT = "#0000FF"             # Blue
COLOR_FRONTLINE = "#FF6600"         # Orange

# Map settings
MAP_TILE_PROVIDER = "CartoDB dark_matter"
MAP_ZOOM_DEFAULT = 11

# =============================================================================
# COT/ATAK EXPORT
# =============================================================================

COT_VERSION = "2.0"
COT_UID_PREFIX = "GHOST-SUPPLY"
COT_TYPE_CONVOY = "a-f-G-U-C"       # Friendly Ground Unit Convoy
COT_TYPE_WAYPOINT = "b-m-p-w"        # Map Point Waypoint
COT_TYPE_THREAT = "a-h-G"            # Hostile Ground
COT_TYPE_DEPOT = "a-f-G-E-S"        # Friendly Ground Equipment Supply

# =============================================================================
# PARETO FRONT GENERATION
# =============================================================================

PARETO_NUM_POINTS = 5  # Number of points on Pareto front
PARETO_WEIGHTS = [
    (1.0, 0.0),   # 100% time
    (0.75, 0.25),
    (0.5, 0.5),
    (0.25, 0.75),
    (0.0, 1.0),   # 100% risk
]

# =============================================================================
# SYNTHETIC DATA GENERATION
# =============================================================================

SYNTHETIC_NUM_INCIDENTS = 500      # 6 months of data
SYNTHETIC_DAYS_HISTORY = 180       # 6 months
SYNTHETIC_INCIDENT_TYPES = [
    "drone_strike",
    "artillery",
    "ambush",
    "mine",
    "sniper",
]

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
