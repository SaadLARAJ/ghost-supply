"""Tests for terrain analysis module."""

import numpy as np
import pytest

from ghost_supply.perception.terrain import TerrainAnalyzer
from ghost_supply.utils.constants import STUDY_AREA_BOUNDS


@pytest.fixture
def simple_terrain():
    """Create simple synthetic terrain for testing."""
    elevation = np.random.rand(100, 100) * 200 + 100
    bounds = STUDY_AREA_BOUNDS

    class MockTransform:
        pass

    transform = MockTransform()

    return TerrainAnalyzer(elevation, transform, bounds)


def test_terrain_initialization(simple_terrain):
    """Test terrain analyzer initializes correctly."""
    assert simple_terrain.height == 100
    assert simple_terrain.width == 100
    assert simple_terrain.elevation.shape == (100, 100)


def test_calculate_slope(simple_terrain):
    """Test slope calculation."""
    slope = simple_terrain.calculate_slope()

    assert slope is not None
    assert slope.shape == (100, 100)
    assert np.all(slope >= 0)
    assert np.all(slope <= 90)


def test_viewshed_calculation(simple_terrain):
    """Test viewshed calculation."""
    observer_positions = [(48.3, 37.25)]

    viewshed = simple_terrain.calculate_viewshed(observer_positions)

    assert viewshed is not None
    assert viewshed.shape == (100, 100)
    assert np.all(viewshed >= 0)
    assert np.all(viewshed <= 1)


def test_mobility_speed():
    """Test mobility speed calculation."""
    elevation = np.zeros((50, 50))
    bounds = STUDY_AREA_BOUNDS

    class MockTransform:
        pass

    terrain = TerrainAnalyzer(elevation, MockTransform(), bounds)

    speed_primary = terrain.get_mobility_speed("primary", "clear")
    assert speed_primary > 0

    speed_rain = terrain.get_mobility_speed("primary", "rain")
    assert speed_rain < speed_primary

    speed_mud = terrain.get_mobility_speed("track", "rasputitsa")
    assert speed_mud < speed_rain


def test_elevation_lookup(simple_terrain):
    """Test elevation lookup at coordinates."""
    lat = (STUDY_AREA_BOUNDS["north"] + STUDY_AREA_BOUNDS["south"]) / 2
    lon = (STUDY_AREA_BOUNDS["east"] + STUDY_AREA_BOUNDS["west"]) / 2

    elevation = simple_terrain.get_elevation_at(lat, lon)

    assert elevation is not None
    assert elevation > 0


def test_visibility_lookup(simple_terrain):
    """Test visibility lookup."""
    viewshed = np.random.rand(100, 100)

    lat = (STUDY_AREA_BOUNDS["north"] + STUDY_AREA_BOUNDS["south"]) / 2
    lon = (STUDY_AREA_BOUNDS["east"] + STUDY_AREA_BOUNDS["west"]) / 2

    visibility = simple_terrain.get_visibility_at(lat, lon, viewshed)

    assert 0 <= visibility <= 1
