"""Tests for CVaR optimization correctness."""

import numpy as np
import pytest

from ghost_supply.decision.cvar_routing import CVaRRouter


def test_cvar_always_greater_than_mean():
    """Test mathematical property: CVaR >= Mean Risk."""
    router = CVaRRouter(None)

    for _ in range(10):
        risks = np.random.uniform(0, 1, 100).tolist()

        mean_risk = np.mean(risks)
        cvar_95 = router._calculate_cvar(risks, 0.95)
        cvar_99 = router._calculate_cvar(risks, 0.99)

        assert cvar_95 >= mean_risk - 0.001
        assert cvar_99 >= cvar_95 - 0.001


def test_cvar_with_uniform_risk():
    """Test CVaR with uniform risk distribution."""
    router = CVaRRouter(None)

    risks = [0.5] * 100

    cvar_95 = router._calculate_cvar(risks, 0.95)

    assert abs(cvar_95 - 0.5) < 0.001


def test_cvar_with_extreme_tail():
    """Test CVaR captures tail risk."""
    router = CVaRRouter(None)

    risks = [0.1] * 95 + [1.0] * 5

    cvar_95 = router._calculate_cvar(risks, 0.95)

    assert cvar_95 > 0.8


def test_cvar_different_alphas():
    """Test CVaR increases with alpha."""
    router = CVaRRouter(None)

    risks = np.random.uniform(0, 1, 100).tolist()

    cvar_90 = router._calculate_cvar(risks, 0.90)
    cvar_95 = router._calculate_cvar(risks, 0.95)
    cvar_99 = router._calculate_cvar(risks, 0.99)

    assert cvar_90 <= cvar_95 <= cvar_99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
