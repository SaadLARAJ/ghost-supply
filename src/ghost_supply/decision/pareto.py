"""Génération du front de Pareto pour l'analyse compromis temps vs risque."""

from typing import List, Tuple

from loguru import logger

from ghost_supply.decision.cvar_routing import CVaRRouter, RouteResult
from ghost_supply.utils.constants import PARETO_NUM_POINTS, PARETO_WEIGHTS


class ParetoFrontGenerator:
    """Génère le front de Pareto pour l'optimisation multi-objectifs des routes."""

    def __init__(self, router: CVaRRouter):
        """
        Initialise le générateur de front de Pareto.

        Args:
            router: Instance CVaRRouter
        """
        self.router = router

        logger.info("Initialized ParetoFrontGenerator")

    def generate(
        self,
        origin: int,
        destination: int,
        cargo_value: float = 7.0,
        num_points: int = PARETO_NUM_POINTS,
    ) -> List[RouteResult]:
        """
        Génère le front de Pareto en variant les poids temps/risque.

        Args:
            origin: Nœud d'origine
            destination: Nœud de destination
            cargo_value: Valeur du cargo
            num_points: Nombre de points Pareto

        Returns:
            Liste d'objets RouteResult sur le front de Pareto
        """
        logger.info(f"Generating Pareto front with {num_points} points")

        results = []

        weights = PARETO_WEIGHTS if len(PARETO_WEIGHTS) >= num_points else self._generate_weights(num_points)

        for i, (weight_time, weight_risk) in enumerate(weights[:num_points]):
            logger.info(f"Computing point {i+1}/{num_points}: time={weight_time:.2f}, risk={weight_risk:.2f}")

            try:
                result = self.router.optimize(
                    origin,
                    destination,
                    cargo_value=cargo_value,
                    weight_time=weight_time,
                    weight_risk=weight_risk,
                )

                result.method = f"pareto_{i+1} (t={weight_time:.2f}, r={weight_risk:.2f})"

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to compute Pareto point {i+1}: {e}")
                continue

        pareto_results = self._filter_dominated(results)

        logger.info(f"Generated Pareto front with {len(pareto_results)} non-dominated points")

        return pareto_results

    def _generate_weights(self, num_points: int) -> List[Tuple[float, float]]:
        """
        Génère des poids temps/risque espacés linéairement.

        Args:
            num_points: Nombre de points

        Returns:
            Liste de tuples (weight_time, weight_risk)
        """
        weights = []

        for i in range(num_points):
            ratio = i / (num_points - 1) if num_points > 1 else 0.5

            weight_time = 1.0 - ratio
            weight_risk = ratio

            weights.append((weight_time, weight_risk))

        return weights

    def _filter_dominated(self, results: List[RouteResult]) -> List[RouteResult]:
        """
        Filtre les solutions dominées pour garder seulement les routes Pareto-optimales.

        Args:
            results: Liste de résultats de routes

        Returns:
            Liste de résultats non-dominés
        """
        if len(results) <= 1:
            return results

        pareto = []

        for i, result_i in enumerate(results):
            dominated = False

            for j, result_j in enumerate(results):
                if i == j:
                    continue

                if self._dominates(result_j, result_i):
                    dominated = True
                    break

            if not dominated:
                pareto.append(result_i)

        return pareto

    def _dominates(self, a: RouteResult, b: RouteResult) -> bool:
        """
        Vérifie si la route A domine la route B (dominance Pareto).

        A domine B si A est meilleure ou égale sur tous les objectifs et strictement meilleure sur au moins un.

        Args:
            a: Première route
            b: Seconde route

        Returns:
            True si A domine B
        """
        time_better = a.time_minutes <= b.time_minutes
        risk_better = a.cvar_95 <= b.cvar_95

        time_strictly_better = a.time_minutes < b.time_minutes
        risk_strictly_better = a.cvar_95 < b.cvar_95

        if time_better and risk_better and (time_strictly_better or risk_strictly_better):
            return True

        return False

    def recommend_solution(
        self,
        pareto_front: List[RouteResult],
        urgency: float = 0.5,
        risk_aversion: float = 0.5
    ) -> RouteResult:
        """
        Recommande une solution du front de Pareto selon les paramètres de mission.

        Args:
            pareto_front: Liste de routes Pareto-optimales
            urgency: Niveau d'urgence (0-1, plus élevé = prioriser le temps)
            risk_aversion: Aversion au risque (0-1, plus élevé = prioriser la sécurité)

        Returns:
            RouteResult recommandé
        """
        if not pareto_front:
            raise ValueError("Empty Pareto front")

        if len(pareto_front) == 1:
            return pareto_front[0]

        time_values = [r.time_minutes for r in pareto_front]
        risk_values = [r.cvar_95 for r in pareto_front]

        time_min, time_max = min(time_values), max(time_values)
        risk_min, risk_max = min(risk_values), max(risk_values)

        time_range = time_max - time_min if time_max > time_min else 1.0
        risk_range = risk_max - risk_min if risk_max > risk_min else 1.0

        best_result = None
        best_score = float("inf")

        for result in pareto_front:
            time_norm = (result.time_minutes - time_min) / time_range
            risk_norm = (result.cvar_95 - risk_min) / risk_range

            score = urgency * time_norm + risk_aversion * risk_norm

            if score < best_score:
                best_score = score
                best_result = result

        return best_result
