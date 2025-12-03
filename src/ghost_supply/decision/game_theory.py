"""Game-theoretic route selection using Stackelberg equilibrium."""

from typing import Dict, List, Tuple

import nashpy as nash
import networkx as nx
import numpy as np
from loguru import logger

from ghost_supply.decision.cvar_routing import CVaRRouter, RouteResult
from ghost_supply.utils.constants import (
    GAME_NUM_DEFENDER_CONFIGS,
    GAME_NUM_ROUTES,
    GAME_PATROL_RADIUS_KM,
)
from ghost_supply.utils.geo import haversine_distance


class StackelbergRouter:
    """Stackelberg game-based route randomization."""

    def __init__(self, router: CVaRRouter):
        """
        Initialize Stackelberg router.

        Args:
            router: CVaRRouter instance
        """
        self.router = router
        self.graph = router.graph

        logger.info("Initialized StackelbergRouter")

    def solve(
        self,
        origin: int,
        destination: int,
        cargo_value: float = 7.0,
        k_routes: int = GAME_NUM_ROUTES,
        m_configs: int = GAME_NUM_DEFENDER_CONFIGS,
    ) -> Tuple[List[RouteResult], np.ndarray]:
        """
        Solve Stackelberg game for optimal route distribution.

        Args:
            origin: Origin node
            destination: Destination node
            cargo_value: Cargo value
            k_routes: Number of alternative routes (K)
            m_configs: Number of defender configurations (M)

        Returns:
            Tuple of (routes, mixed_strategy_distribution)
        """
        logger.info(f"Solving Stackelberg game: K={k_routes}, M={m_configs}")

        routes = self._generate_k_routes(origin, destination, cargo_value, k_routes)

        defender_configs = self._generate_defender_configs(routes, m_configs)

        payoff_matrix = self._build_payoff_matrix(routes, defender_configs, cargo_value)

        mixed_strategy = self._solve_zero_sum_game(payoff_matrix)

        logger.info(f"Computed mixed strategy: {mixed_strategy}")

        return routes, mixed_strategy

    def sample_route(
        self,
        routes: List[RouteResult],
        mixed_strategy: np.ndarray
    ) -> RouteResult:
        """
        Sample route according to mixed strategy distribution.

        Args:
            routes: List of alternative routes
            mixed_strategy: Probability distribution

        Returns:
            Sampled RouteResult
        """
        if len(routes) != len(mixed_strategy):
            raise ValueError("Routes and strategy dimensions must match")

        idx = np.random.choice(len(routes), p=mixed_strategy)

        return routes[idx]

    def _generate_k_routes(
        self,
        origin: int,
        destination: int,
        cargo_value: float,
        k: int
    ) -> List[RouteResult]:
        """
        Generate K diverse alternative routes.

        Args:
            origin: Origin node
            destination: Destination node
            cargo_value: Cargo value
            k: Number of routes

        Returns:
            List of K routes
        """
        routes = []

        baseline = self.router.optimize(origin, destination, cargo_value=cargo_value)
        routes.append(baseline)

        fastest = self.router.shortest_time(origin, destination)
        if fastest.node_path != baseline.node_path:
            routes.append(fastest)

        shortest = self.router.shortest_distance(origin, destination)
        if shortest.node_path not in [r.node_path for r in routes]:
            routes.append(shortest)

        mean_risk_route = self.router.mean_risk(origin, destination, cargo_value)
        if mean_risk_route.node_path not in [r.node_path for r in routes]:
            routes.append(mean_risk_route)

        while len(routes) < k:
            try:
                penalty_edges = set()
                for route in routes:
                    for i in range(len(route.node_path) - 1):
                        edge = (route.node_path[i], route.node_path[i + 1])
                        penalty_edges.add(edge)

                for u, v in penalty_edges:
                    if self.graph.has_edge(u, v):
                        self.graph[u][v]["temp_penalty"] = 100.0

                diverse_path = nx.shortest_path(
                    self.graph, origin, destination,
                    weight=lambda u, v, d: d.get("travel_time_hours", 1.0) + d.get("temp_penalty", 0.0)
                )

                for u, v in penalty_edges:
                    if self.graph.has_edge(u, v) and "temp_penalty" in self.graph[u][v]:
                        del self.graph[u][v]["temp_penalty"]

                scenarios = self.router._generate_scenarios()
                diverse_result = self.router._build_route_result(
                    diverse_path, scenarios, cargo_value, f"diverse_{len(routes)+1}"
                )

                if diverse_result.node_path not in [r.node_path for r in routes]:
                    routes.append(diverse_result)
                else:
                    break

            except Exception as e:
                logger.warning(f"Could not generate diverse route: {e}")
                break

        logger.info(f"Generated {len(routes)} alternative routes")

        return routes[:k]

    def _generate_defender_configs(
        self,
        routes: List[RouteResult],
        m: int
    ) -> List[Dict]:
        """
        Generate M defender patrol configurations.

        Args:
            routes: List of routes
            m: Number of configurations

        Returns:
            List of defender configurations
        """
        configs = []

        all_positions = []
        for route in routes:
            for lat, lon in route.path[::3]:
                all_positions.append((lat, lon))

        for _ in range(m):
            num_patrols = np.random.randint(2, 6)

            patrol_positions = []
            for _ in range(num_patrols):
                if all_positions:
                    pos = all_positions[np.random.randint(0, len(all_positions))]
                    patrol_positions.append(pos)

            config = {
                "patrols": patrol_positions,
                "effectiveness": np.random.uniform(0.7, 1.0),
            }

            configs.append(config)

        return configs

    def _build_payoff_matrix(
        self,
        routes: List[RouteResult],
        defender_configs: List[Dict],
        cargo_value: float
    ) -> np.ndarray:
        """
        Build K x M payoff matrix (attacker perspective).

        Args:
            routes: K routes
            defender_configs: M defender configurations
            cargo_value: Cargo value

        Returns:
            K x M payoff matrix (negative = better for attacker)
        """
        K = len(routes)
        M = len(defender_configs)

        payoff = np.zeros((K, M))

        for i, route in enumerate(routes):
            for j, config in enumerate(defender_configs):
                interception_prob = self._calculate_interception_prob(
                    route, config, cargo_value
                )

                payoff[i, j] = -interception_prob

        return payoff

    def _calculate_interception_prob(
        self,
        route: RouteResult,
        defender_config: Dict,
        cargo_value: float
    ) -> float:
        """
        Calculate interception probability for route against defender config.

        Args:
            route: Route
            defender_config: Defender configuration
            cargo_value: Cargo value

        Returns:
            Interception probability (0-1)
        """
        base_risk = route.mean_risk

        patrol_factor = 0.0

        for patrol_lat, patrol_lon in defender_config["patrols"]:
            min_distance = float("inf")

            for route_lat, route_lon in route.path:
                distance = haversine_distance(route_lat, route_lon, patrol_lat, patrol_lon)
                min_distance = min(min_distance, distance)

            if min_distance <= GAME_PATROL_RADIUS_KM:
                exposure = 1.0 - (min_distance / GAME_PATROL_RADIUS_KM)
                patrol_factor += exposure * defender_config["effectiveness"]

        total_prob = base_risk + patrol_factor * 0.3

        return min(total_prob, 1.0)

    def _solve_zero_sum_game(self, payoff_matrix: np.ndarray) -> np.ndarray:
        """
        Solve zero-sum game for mixed strategy Nash equilibrium.

        Args:
            payoff_matrix: K x M payoff matrix

        Returns:
            Mixed strategy probability distribution (K,)
        """
        K, M = payoff_matrix.shape

        if K == 1:
            return np.array([1.0])

        game = nash.Game(payoff_matrix, -payoff_matrix)

        equilibria = list(game.support_enumeration())

        if equilibria:
            attacker_strategy, _ = equilibria[0]
            return np.array(attacker_strategy)

        uniform = np.ones(K) / K
        return uniform
