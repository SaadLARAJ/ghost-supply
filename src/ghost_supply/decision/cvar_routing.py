"""Optimisation de routage basée sur CVaR avec comparaisons baseline."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
from loguru import logger
from pyomo.environ import (
    Binary,
    ConcreteModel,
    Constraint,
    NonNegativeReals,
    Objective,
    RangeSet,
    SolverFactory,
    Var,
    minimize,
    value,
)

from ghost_supply.utils.constants import (
    CVAR_DEFAULT_ALPHA,
    CVAR_NUM_SCENARIOS,
    CVAR_SOLVER,
    CVAR_TIME_LIMIT_SEC,
    CVAR_WEIGHT_RISK,
    CVAR_WEIGHT_TIME,
)
from ghost_supply.utils.geo import calculate_path_length


@dataclass
class Waypoint:
    """Point de passage avec informations tactiques."""
    latitude: float
    longitude: float
    name: str
    eta_hours: float
    instructions: str = ""
    risk_level: float = 0.0


@dataclass
class RouteResult:
    """Résultat de l'optimisation de route."""
    path: List[Tuple[float, float]]
    node_path: List[int]
    time_minutes: float
    distance_km: float
    mean_risk: float
    cvar_95: float
    cvar_99: float
    waypoints: List[Waypoint]
    method: str
    survival_probability: float = 0.0


class CVaRRouter:
    """Optimiseur de routes basé sur CVaR minimisant le risque de queue."""

    def __init__(
        self,
        graph: nx.DiGraph,
        alpha: float = CVAR_DEFAULT_ALPHA,
        num_scenarios: int = CVAR_NUM_SCENARIOS,
    ):
        """
        Initialise le routeur CVaR.

        Args:
            graph: Graphe de routage avec arcs enrichis
            alpha: Niveau de confiance CVaR (ex: 0.95 pour 95ème percentile)
            num_scenarios: Nombre de scénarios de risque
        """
        self.graph = graph
        self.alpha = alpha
        self.num_scenarios = num_scenarios

        logger.info(f"Routeur CVaR initialisé : alpha={alpha}, scenarios={num_scenarios}")

    def optimize(
        self,
        origin: int,
        destination: int,
        cargo_value: float = 7.0,
        weight_time: float = CVAR_WEIGHT_TIME,
        weight_risk: float = CVAR_WEIGHT_RISK,
        solver: str = CVAR_SOLVER,
    ) -> RouteResult:
        """
        Trouve la route minimisant la combinaison pondérée du temps et du risque CVaR.

        Args:
            origin: ID du nœud d'origine
            destination: ID du nœud de destination
            cargo_value: Valeur stratégique du cargo (1-10)
            weight_time: Poids pour l'objectif temps (0-1)
            weight_risk: Poids pour l'objectif risque CVaR (0-1)
            solver: Nom du solveur Pyomo

        Returns:
            Objet RouteResult
        """
        logger.info(f"Optimisation route CVaR de {origin} vers {destination}")

        scenarios = self._generate_scenarios()

        model = ConcreteModel()

        edges = list(self.graph.edges())
        edge_index = {e: i for i, e in enumerate(edges)}

        model.E = RangeSet(0, len(edges) - 1)
        model.S = RangeSet(0, self.num_scenarios - 1)

        model.x = Var(model.E, domain=Binary)

        model.eta = Var(domain=NonNegativeReals)
        model.z = Var(model.S, domain=NonNegativeReals)

        def flow_conservation_rule(m, node):
            if node == origin:
                return sum(
                    m.x[edge_index[(node, j)]]
                    for _, j in self.graph.out_edges(node)
                ) - sum(
                    m.x[edge_index[(i, node)]]
                    for i, _ in self.graph.in_edges(node)
                ) == 1
            elif node == destination:
                return sum(
                    m.x[edge_index[(i, node)]]
                    for i, _ in self.graph.in_edges(node)
                ) - sum(
                    m.x[edge_index[(node, j)]]
                    for _, j in self.graph.out_edges(node)
                ) == 1
            else:
                return sum(
                    m.x[edge_index[(i, node)]]
                    for i, _ in self.graph.in_edges(node)
                ) == sum(
                    m.x[edge_index[(node, j)]]
                    for _, j in self.graph.out_edges(node)
                )

        model.flow = Constraint(self.graph.nodes(), rule=flow_conservation_rule)

        def cvar_scenario_rule(m, s):
            scenario_risk = sum(
                m.x[i] * self._get_edge_risk(edges[i], scenarios[s], cargo_value)
                for i in m.E
            )
            return m.z[s] >= scenario_risk - m.eta

        model.cvar_constraint = Constraint(model.S, rule=cvar_scenario_rule)

        total_time = sum(
            model.x[i] * self.graph.edges[edges[i]].get("travel_time_hours", 1.0)
            for i in model.E
        )

        cvar = model.eta + (1.0 / (1.0 - self.alpha)) * sum(model.z[s] for s in model.S) / self.num_scenarios

        model.obj = Objective(
            expr=weight_time * total_time + weight_risk * cvar,
            sense=minimize
        )

        try:
            solver_instance = SolverFactory(solver)
            if solver in ["cbc", "highs"]:
                results = solver_instance.solve(model, timelimit=CVAR_TIME_LIMIT_SEC)
            else:
                results = solver_instance.solve(model)

        except Exception as e:
            logger.error(f"Échec du solveur : {e}. Repli sur Dijkstra")
            return self.shortest_time(origin, destination)

        if not hasattr(model, "x"):
            logger.error("L'optimisation a échoué. Utilisation du temps le plus court par défaut")
            return self.shortest_time(origin, destination)

        selected_edges = [edges[i] for i in model.E if value(model.x[i]) > 0.5]

        node_path = self._edges_to_path(selected_edges, origin, destination)

        if not node_path:
            logger.warning("Impossible de reconstruire le chemin. Utilisation de Dijkstra")
            return self.shortest_time(origin, destination)

        return self._build_route_result(node_path, scenarios, cargo_value, "cvar")

    def shortest_distance(self, origin: int, destination: int) -> RouteResult:
        """
        Trouve la route la plus courte (baseline).

        Note: C'est la route "GPS naïf" qui ignore les kill zones.

        Args:
            origin: Nœud d'origine
            destination: Nœud de destination

        Returns:
            RouteResult
        """
        logger.info(f"Calcul de la route la plus courte (distance) de {origin} vers {destination}")

        try:
            node_path = nx.shortest_path(
                self.graph, origin, destination, weight="distance_km"
            )
        except nx.NetworkXNoPath:
            logger.error("Aucun chemin trouvé")
            return self._empty_result("shortest_distance")

        scenarios = self._generate_scenarios()

        return self._build_route_result(node_path, scenarios, 7.0, "shortest_distance")

    def shortest_time(self, origin: int, destination: int) -> RouteResult:
        """
        Trouve la route la plus rapide (baseline).

        Args:
            origin: Nœud d'origine
            destination: Nœud de destination

        Returns:
            RouteResult
        """
        logger.info(f"Calcul de la route la plus rapide de {origin} vers {destination}")

        try:
            node_path = nx.shortest_path(
                self.graph, origin, destination, weight="travel_time_hours"
            )
        except nx.NetworkXNoPath:
            logger.error("Aucun chemin trouvé")
            return self._empty_result("shortest_time")

        scenarios = self._generate_scenarios()

        return self._build_route_result(node_path, scenarios, 7.0, "shortest_time")

    def mean_risk(
        self,
        origin: int,
        destination: int,
        cargo_value: float = 7.0
    ) -> RouteResult:
        """
        Trouve la route minimisant le risque moyen (baseline).

        Args:
            origin: Nœud d'origine
            destination: Nœud de destination
            cargo_value: Valeur du cargo

        Returns:
            RouteResult
        """
        logger.info(f"Calcul de la route à risque moyen de {origin} vers {destination}")

        for u, v, data in self.graph.edges(data=True):
            killzone_penalty = data.get("killzone_penalty", 1.0)
            risk = data.get("detection_base", 0.3) * cargo_value / 10.0 * killzone_penalty
            data["risk_weight"] = risk

        try:
            node_path = nx.shortest_path(
                self.graph, origin, destination, weight="risk_weight"
            )
        except nx.NetworkXNoPath:
            logger.error("Aucun chemin trouvé")
            return self._empty_result("mean_risk")

        scenarios = self._generate_scenarios()

        return self._build_route_result(node_path, scenarios, cargo_value, "mean_risk")

    def _generate_scenarios(self) -> List[Dict[str, float]]:
        """
        Génère des scénarios de risque en variant les paramètres de détection.

        Returns:
            Liste de dictionnaires de scénarios
        """
        scenarios = []

        for i in range(self.num_scenarios):
            scenario = {
                "visibility_mult": np.random.uniform(0.7, 1.3),
                "detection_mult": np.random.uniform(0.8, 1.2),
                "patrol_presence": np.random.choice([0.8, 1.0, 1.2, 1.5]),
            }
            scenarios.append(scenario)

        return scenarios

    def _get_edge_risk(
        self,
        edge: Tuple[int, int],
        scenario: Dict[str, float],
        cargo_value: float
    ) -> float:
        """
        Calcule le risque d'un arc pour un scénario donné.

        Args:
            edge: Tuple d'arc
            scenario: Paramètres du scénario
            cargo_value: Valeur du cargo

        Returns:
            Valeur de risque
        """
        data = self.graph.edges[edge]

        base_detection = data.get("detection_base", 0.3)
        visibility = data.get("visibility", 0.5)
        killzone_penalty = data.get("killzone_penalty", 1.0)

        scenario_risk = (
            base_detection * scenario["detection_mult"] *
            (1.0 + visibility * scenario["visibility_mult"] * 0.5) *
            scenario["patrol_presence"] *
            killzone_penalty
        )

        weighted_risk = scenario_risk * (cargo_value / 10.0)

        return min(weighted_risk, 10.0)

    def _edges_to_path(
        self,
        edges: List[Tuple[int, int]],
        origin: int,
        destination: int
    ) -> List[int]:
        """
        Reconstruit le chemin de nœuds depuis les arcs sélectionnés.

        Args:
            edges: Liste des arcs sélectionnés
            origin: Nœud d'origine
            destination: Nœud de destination

        Returns:
            Liste de nœuds
        """
        if not edges:
            return []

        edge_dict = {u: v for u, v in edges}

        path = [origin]
        current = origin

        for _ in range(len(edges) + 1):
            if current == destination:
                break

            if current not in edge_dict:
                return []

            next_node = edge_dict[current]
            path.append(next_node)
            current = next_node

        return path if path[-1] == destination else []

    def _build_route_result(
        self,
        node_path: List[int],
        scenarios: List[Dict],
        cargo_value: float,
        method: str
    ) -> RouteResult:
        """
        Construit un RouteResult depuis un chemin de nœuds.

        Args:
            node_path: Liste d'IDs de nœuds
            scenarios: Scénarios de risque
            cargo_value: Valeur du cargo
            method: Nom de la méthode

        Returns:
            RouteResult
        """
        path_coords = []
        waypoints = []
        total_time = 0.0
        total_distance = 0.0

        for i in range(len(node_path) - 1):
            u = node_path[i]
            v = node_path[i + 1]

            if not self.graph.has_edge(u, v):
                continue

            edge_data = self.graph.edges[u, v]

            if "geometry" in edge_data and edge_data["geometry"]:
                geom = edge_data["geometry"]
                try:
                    lons, lats = geom.xy
                    segment = list(zip(lats, lons))

                    if not segment:
                        logger.warning(f"L'arc ({u}, {v}) a une géométrie vide.")
                        if i == 0:
                            path_coords.append((self.graph.nodes[u]["y"], self.graph.nodes[u]["x"]))
                        path_coords.append((self.graph.nodes[v]["y"], self.graph.nodes[v]["x"]))
                    elif i == 0:
                        path_coords.extend(segment)
                    else:
                        path_coords.extend(segment[1:])

                except Exception as e:
                    logger.error(f"Impossible d'analyser la géométrie pour l'arc ({u}, {v}) : {e}")
                    if i == 0:
                        path_coords.append((self.graph.nodes[u]["y"], self.graph.nodes[u]["x"]))
                    path_coords.append((self.graph.nodes[v]["y"], self.graph.nodes[v]["x"]))
            else:
                if i == 0:
                    path_coords.append((self.graph.nodes[u]["y"], self.graph.nodes[u]["x"]))
                path_coords.append((self.graph.nodes[v]["y"], self.graph.nodes[v]["x"]))

            total_time += edge_data.get("travel_time_hours", 0)
            total_distance += edge_data.get("distance_km", 0)

        waypoint_interval = max(1, len(node_path) // 10)
        for i, node in enumerate(node_path):
            if i == 0 or i == len(node_path) - 1 or i % waypoint_interval == 0:
                lat = self.graph.nodes[node]["y"]
                lon = self.graph.nodes[node]["x"]

                if i == 0:
                    name = "Origin"
                elif i == len(node_path) - 1:
                    name = "Destination"
                else:
                    name = f"Waypoint {len(waypoints)}"

                waypoints.append(Waypoint(
                    latitude=lat,
                    longitude=lon,
                    name=name,
                    eta_hours=total_time,
                    instructions="",
                ))

        scenario_risks = []
        for scenario in scenarios:
            risk = 0.0
            for i in range(len(node_path) - 1):
                edge = (node_path[i], node_path[i + 1])
                if self.graph.has_edge(*edge):
                    risk += self._get_edge_risk(edge, scenario, cargo_value)
            scenario_risks.append(risk)

        mean_risk = np.mean(scenario_risks)
        cvar_95 = self._calculate_cvar(scenario_risks, 0.95)
        cvar_99 = self._calculate_cvar(scenario_risks, 0.99)

        survival_prob = self._calculate_survival_probability(cvar_95)

        return RouteResult(
            path=path_coords,
            node_path=node_path,
            time_minutes=total_time * 60,
            distance_km=total_distance,
            mean_risk=mean_risk,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            waypoints=waypoints,
            method=method,
            survival_probability=survival_prob,
        )

    def _calculate_cvar(self, risks: List[float], alpha: float) -> float:
        """
        Calcule le CVaR (Conditional Value at Risk).

        Args:
            risks: Liste des valeurs de risque
            alpha: Niveau de confiance

        Returns:
            Valeur CVaR
        """
        sorted_risks = sorted(risks)
        var_index = int(alpha * len(sorted_risks))
        var = sorted_risks[var_index] if var_index < len(sorted_risks) else sorted_risks[-1]

        tail_risks = [r for r in sorted_risks if r >= var]

        cvar = np.mean(tail_risks) if tail_risks else var

        return cvar

    def _calculate_survival_probability(self, risk_score: float, lambda_cal: float = 0.1) -> float:
        """
        Convertit le score de risque brut en probabilité de survie par décroissance exponentielle.

        Formule: P(survie) = exp(-λ × score_risque)

        Calibration:
        - λ = 0.1 donne des probabilités raisonnables:
          - score_risque ~5 → ~60% survie
          - score_risque ~15 → ~22% survie
          - score_risque ~30 → ~5% survie

        Args:
            risk_score: Score de risque cumulatif brut (peut être > 1)
            lambda_cal: Paramètre de calibration (défaut 0.1)

        Returns:
            Probabilité de survie entre 0 et 1
        """
        import math
        return math.exp(-lambda_cal * risk_score)

    def _empty_result(self, method: str) -> RouteResult:
        """Crée un résultat vide pour un routage échoué."""
        return RouteResult(
            path=[],
            node_path=[],
            time_minutes=0.0,
            distance_km=0.0,
            mean_risk=0.0,
            cvar_95=0.0,
            cvar_99=0.0,
            waypoints=[],
            method=method,
            survival_probability=0.0,
        )
