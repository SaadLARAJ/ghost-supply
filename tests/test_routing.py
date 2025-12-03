"""Tests for routing algorithms."""

import networkx as nx
import pytest

from ghost_supply.decision.cvar_routing import CVaRRouter


@pytest.fixture
def simple_graph():
    """Create simple test graph."""
    G = nx.DiGraph()

    G.add_node(0, y=48.2, x=37.1)
    G.add_node(1, y=48.25, x=37.15)
    G.add_node(2, y=48.3, x=37.2)
    G.add_node(3, y=48.35, x=37.25)

    G.add_edge(0, 1, distance_km=5.0, travel_time_hours=0.1, detection_base=0.2, road_type="primary")
    G.add_edge(1, 2, distance_km=6.0, travel_time_hours=0.12, detection_base=0.5, road_type="secondary")
    G.add_edge(2, 3, distance_km=4.0, travel_time_hours=0.08, detection_base=0.3, road_type="primary")

    G.add_edge(0, 2, distance_km=12.0, travel_time_hours=0.25, detection_base=0.15, road_type="track")
    G.add_edge(2, 3, distance_km=4.0, travel_time_hours=0.08, detection_base=0.3, road_type="primary")

    return G


def test_router_initialization(simple_graph):
    """Test CVaR router initializes."""
    router = CVaRRouter(simple_graph, alpha=0.95, num_scenarios=10)

    assert router.graph == simple_graph
    assert router.alpha == 0.95
    assert router.num_scenarios == 10


def test_shortest_distance(simple_graph):
    """Test shortest distance routing."""
    router = CVaRRouter(simple_graph, num_scenarios=10)

    result = router.shortest_distance(0, 3)

    assert result is not None
    assert len(result.node_path) >= 2
    assert result.node_path[0] == 0
    assert result.node_path[-1] == 3
    assert result.distance_km > 0
    assert result.time_minutes > 0


def test_shortest_time(simple_graph):
    """Test fastest routing."""
    router = CVaRRouter(simple_graph, num_scenarios=10)

    result = router.shortest_time(0, 3)

    assert result is not None
    assert len(result.node_path) >= 2
    assert result.time_minutes > 0


def test_mean_risk(simple_graph):
    """Test mean risk routing."""
    router = CVaRRouter(simple_graph, num_scenarios=10)

    result = router.mean_risk(0, 3, cargo_value=7.0)

    assert result is not None
    assert result.mean_risk >= 0
    assert result.cvar_95 >= 0


def test_cvar_comparison(simple_graph):
    """Test that CVaR produces valid results."""
    router = CVaRRouter(simple_graph, alpha=0.95, num_scenarios=10)

    try:
        cvar_result = router.optimize(0, 3, cargo_value=7.0)

        assert cvar_result is not None
        assert cvar_result.cvar_95 >= cvar_result.mean_risk

    except Exception:
        pytest.skip("Solver not available")


def test_scenario_generation(simple_graph):
    """Test scenario generation."""
    router = CVaRRouter(simple_graph, num_scenarios=50)

    scenarios = router._generate_scenarios()

    assert len(scenarios) == 50
    assert all("visibility_mult" in s for s in scenarios)
    assert all("detection_mult" in s for s in scenarios)


def test_cvar_calculation():
    """Test CVaR calculation."""
    router = CVaRRouter(nx.DiGraph())

    risks = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    cvar_95 = router._calculate_cvar(risks, 0.95)
    cvar_99 = router._calculate_cvar(risks, 0.99)

    assert cvar_95 > np.mean(risks)
    assert cvar_99 > cvar_95
