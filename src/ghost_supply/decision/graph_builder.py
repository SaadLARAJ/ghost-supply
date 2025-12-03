"""Construction de graphe depuis les données OSM et analyse de terrain."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import osmnx as ox
from loguru import logger

from ghost_supply.perception.terrain import TerrainAnalyzer
from ghost_supply.perception.threat_model import ThreatPredictor
from ghost_supply.perception.weather import WeatherModel
from ghost_supply.utils.constants import STUDY_AREA_BOUNDS
from ghost_supply.utils.geo import haversine_distance


class GraphBuilder:
    """Construit le graphe de routage depuis les données OSM avec attributs tactiques."""

    def __init__(
        self,
        terrain: Optional[TerrainAnalyzer] = None,
        threat_predictor: Optional[ThreatPredictor] = None,
        weather_model: Optional[WeatherModel] = None,
    ):
        """
        Initialise le constructeur de graphe.

        Args:
            terrain: Instance de TerrainAnalyzer
            threat_predictor: Instance de ThreatPredictor
            weather_model: Instance de WeatherModel
        """
        self.terrain = terrain
        self.threat_predictor = threat_predictor
        self.weather_model = weather_model or WeatherModel()

        self.graph: Optional[nx.MultiDiGraph] = None
        self.simplified_graph: Optional[nx.DiGraph] = None

        logger.info("Initialized GraphBuilder")

    def build_from_osm(
        self,
        bounds: Optional[Dict[str, float]] = None,
        network_type: str = "drive",
        simplify: bool = True,
    ) -> nx.DiGraph:
        """
        Construit le graphe depuis les données OpenStreetMap avec cache local.

        Args:
            bounds: Dict avec north, south, east, west
            network_type: Type de réseau OSM
            simplify: Simplifier le graphe ou non

        Returns:
            NetworkX DiGraph
        """
        if bounds is None:
            bounds = STUDY_AREA_BOUNDS

        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        bounds_str = "_".join(map(str, [bounds['north'], bounds['south'], bounds['east'], bounds['west']]))
        cache_file = cache_dir / f"osm_graph_{bounds_str}_{network_type}.graphml"

        if cache_file.exists():
            logger.info(f"Loading cached OSM graph from {cache_file}...")
            try:
                self.graph = ox.load_graphml(cache_file)
                logger.info("Cached graph loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load cached graph: {e}. Re-downloading...")
                self.graph = None
        
        if self.graph is None:
            logger.info(f"Fetching OSM data for bounds: {bounds}")
            try:
                self.graph = ox.graph_from_bbox(
                    bbox=(bounds["north"], bounds["south"], bounds["east"], bounds["west"]),
                    network_type=network_type,
                    simplify=simplify,
                )
                logger.info(f"Downloaded OSM graph with {len(self.graph.nodes())} nodes and {len(self.graph.edges())} edges.")
                ox.save_graphml(self.graph, filepath=cache_file)
                logger.info(f"Saved OSM graph to cache: {cache_file}")

            except Exception as e:
                logger.warning(f"Failed to download OSM data: {e}. Creating synthetic graph as fallback.")
                self.graph = self._create_synthetic_graph(bounds)

        self.simplified_graph = self._simplify_to_digraph(self.graph)
        logger.info(f"Simplified to {len(self.simplified_graph.nodes)} nodes, {len(self.simplified_graph.edges)} edges")
        return self.simplified_graph

    def _create_synthetic_graph(self, bounds: Dict[str, float]) -> nx.MultiDiGraph:
        """
        Crée un réseau routier synthétique pour les tests.

        Args:
            bounds: Limites géographiques

        Returns:
            MultiDiGraph synthétique
        """
        logger.info("Creating synthetic road network...")

        G = nx.MultiDiGraph()

        lat_center = (bounds["north"] + bounds["south"]) / 2
        lon_center = (bounds["east"] + bounds["west"]) / 2

        grid_size = 7
        lat_step = (bounds["north"] - bounds["south"]) / (grid_size - 1)
        lon_step = (bounds["east"] - bounds["west"]) / (grid_size - 1)

        node_id = 0
        node_positions = {}

        for i in range(grid_size):
            for j in range(grid_size):
                lat = bounds["south"] + i * lat_step
                lon = bounds["west"] + j * lon_step

                G.add_node(node_id, y=lat, x=lon)
                node_positions[(i, j)] = node_id
                node_id += 1

        for i in range(grid_size):
            for j in range(grid_size):
                current = node_positions[(i, j)]

                if j < grid_size - 1:
                    neighbor = node_positions[(i, j + 1)]
                    road_type = "primary" if i == grid_size // 2 else "secondary"
                    G.add_edge(current, neighbor, highway=road_type, length=lon_step * 111000)
                    G.add_edge(neighbor, current, highway=road_type, length=lon_step * 111000)

                if i < grid_size - 1:
                    neighbor = node_positions[(i + 1, j)]
                    road_type = "primary" if j == grid_size // 2 else "secondary"
                    G.add_edge(current, neighbor, highway=road_type, length=lat_step * 111000)
                    G.add_edge(neighbor, current, highway=road_type, length=lat_step * 111000)

        logger.info(f"Created synthetic graph: {len(G.nodes)} nodes, {len(G.edges)} edges")

        return G

    def _simplify_to_digraph(self, multi_graph: nx.MultiDiGraph) -> nx.DiGraph:
        """
        Convertit MultiDiGraph en DiGraph en préservant la géométrie des routes.

        Quand plusieurs arcs existent entre deux nœuds, sélectionne intelligemment
        lequel garder en priorisant ceux avec attribut 'geometry' (courbe de route)
        puis en prenant le plus court.

        Args:
            multi_graph: Graphe OSMnx avec potentiellement plusieurs arcs entre nœuds

        Returns:
            DiGraph simplifié avec un arc par direction, géométrie préservée
        """
        G = nx.DiGraph()

        for node, data in multi_graph.nodes(data=True):
            G.add_node(node, **data)

        edges_grouped = {}
        for u, v, data in multi_graph.edges(data=True):
            if (u, v) not in edges_grouped:
                edges_grouped[(u, v)] = []
            edges_grouped[(u, v)].append(data)

        for (u, v), edge_data_list in edges_grouped.items():
            if not edge_data_list:
                continue

            best_data = None
            if len(edge_data_list) == 1:
                best_data = edge_data_list[0]
            else:
                edges_with_geom = [d for d in edge_data_list if "geometry" in d]

                if edges_with_geom:
                    best_data = min(
                        edges_with_geom, key=lambda d: d.get("length", float("inf"))
                    )
                else:
                    best_data = min(
                        edge_data_list, key=lambda d: d.get("length", float("inf"))
                    )

            if best_data:
                G.add_edge(u, v, **best_data)

        return G

    def enrich_graph(
        self,
        viewshed: Optional[Any] = None,
        rf_coverage: Optional[Any] = None,
        weather: str = "clear",
        timestamp: Optional[datetime] = None,
        kill_zones: Optional[List[Dict]] = None,
    ) -> None:
        """
        Enrichit les arcs du graphe avec des attributs tactiques.

        Args:
            viewshed: Tableau viewshed de TerrainAnalyzer
            rf_coverage: Carte de couverture RF
            weather: Condition météo
            timestamp: Horodatage de la mission
            kill_zones: Liste de dicts de kill zones avec 'center' et 'radius_km'
        """
        if self.simplified_graph is None:
            raise ValueError("Graph not built. Call build_from_osm first.")

        if timestamp is None:
            timestamp = datetime.now()

        logger.info("Enriching graph with tactical attributes...")

        for u, v, data in self.simplified_graph.edges(data=True):
            u_lat = self.simplified_graph.nodes[u]["y"]
            u_lon = self.simplified_graph.nodes[u]["x"]
            v_lat = self.simplified_graph.nodes[v]["y"]
            v_lon = self.simplified_graph.nodes[v]["x"]

            mid_lat = (u_lat + v_lat) / 2
            mid_lon = (u_lon + v_lon) / 2

            distance_km = haversine_distance(u_lat, u_lon, v_lat, v_lon)
            data["distance_km"] = distance_km

            road_type = self._classify_road_type(data.get("highway", "track"))
            data["road_type"] = road_type

            if self.terrain:
                base_speed = self.terrain.get_mobility_speed(road_type, weather)
            else:
                base_speed = 40.0

            data["base_speed_kmh"] = base_speed

            if viewshed is not None and self.terrain:
                visibility = self.terrain.get_visibility_at(mid_lat, mid_lon, viewshed)
            else:
                visibility = 0.5

            data["visibility"] = visibility

            if rf_coverage is not None and hasattr(self, "_get_rf_signal"):
                rf_signal = self._get_rf_signal(mid_lat, mid_lon, rf_coverage)
            else:
                rf_signal = -80.0

            data["rf_coverage_dbm"] = rf_signal

            if self.threat_predictor:
                detection_prob = self.threat_predictor.risk_at(
                    mid_lat, mid_lon, timestamp, road_type, weather
                )
            else:
                detection_prob = visibility * 0.3

            data["detection_base"] = detection_prob

            killzone_penalty = self._compute_killzone_penalty(
                mid_lat, mid_lon, kill_zones
            )
            data["killzone_penalty"] = killzone_penalty

            travel_time_hours = distance_km / base_speed if base_speed > 0 else 999.0
            data["travel_time_hours"] = travel_time_hours

        logger.info("Graph enrichment complete")

    def _classify_road_type(self, highway: Any) -> str:
        """
        Classifie le tag highway OSM en type de route simplifié.

        Args:
            highway: Tag highway OSM

        Returns:
            Type de route
        """
        if isinstance(highway, list):
            highway = highway[0]

        highway = str(highway).lower()

        if highway in ["motorway", "trunk", "primary"]:
            return "primary"
        elif highway in ["secondary"]:
            return "secondary"
        elif highway in ["tertiary", "unclassified", "residential"]:
            return "tertiary"
        elif highway in ["track", "service"]:
            return "track"
        elif highway in ["path", "footway", "cycleway"]:
            return "path"
        else:
            return "track"

    def find_nearest_node(self, lat: float, lon: float) -> int:
        """
        Trouve le nœud du graphe le plus proche des coordonnées données.

        Args:
            lat, lon: Coordonnées

        Returns:
            ID du nœud
        """
        if self.simplified_graph is None:
            raise ValueError("Graph not built")

        nearest_node = None
        min_distance = float("inf")

        for node, data in self.simplified_graph.nodes(data=True):
            node_lat = data["y"]
            node_lon = data["x"]

            distance = haversine_distance(lat, lon, node_lat, node_lon)

            if distance < min_distance:
                min_distance = distance
                nearest_node = node

        return nearest_node

    def get_node_coordinates(self, node: int) -> Tuple[float, float]:
        """
        Obtient les coordonnées lat/lon d'un nœud.

        Args:
            node: ID du nœud

        Returns:
            Tuple (lat, lon)
        """
        if self.simplified_graph is None:
            raise ValueError("Graph not built")

        data = self.simplified_graph.nodes[node]
        return data["y"], data["x"]

    def add_custom_nodes(
        self,
        depots: List[Tuple[float, float]],
        frontline_positions: List[Tuple[float, float]],
    ) -> None:
        """
        Ajoute des nœuds personnalisés (dépôts et front) au graphe.

        Args:
            depots: Liste de positions (lat, lon) des dépôts
            frontline_positions: Liste de positions (lat, lon) du front
        """
        if self.simplified_graph is None:
            raise ValueError("Graph not built")

        original_nodes = list(self.simplified_graph.nodes())

        max_node_id = max(self.simplified_graph.nodes())

        for i, (lat, lon) in enumerate(depots):
            node_id = max_node_id + i + 1
            self.simplified_graph.add_node(node_id, y=lat, x=lon, node_type="depot")

            nearest = self._find_nearest_original_node(lat, lon, original_nodes)
            distance_km = haversine_distance(lat, lon, *self.get_node_coordinates(nearest))

            self.simplified_graph.add_edge(
                node_id, nearest,
                distance_km=distance_km,
                road_type="track",
                travel_time_hours=distance_km / 30.0,
                base_speed_kmh=30.0,
                detection_base=0.2,
            )
            self.simplified_graph.add_edge(
                nearest, node_id,
                distance_km=distance_km,
                road_type="track",
                travel_time_hours=distance_km / 30.0,
                base_speed_kmh=30.0,
                detection_base=0.2,
            )

        max_node_id = max(self.simplified_graph.nodes())

        for i, (lat, lon) in enumerate(frontline_positions):
            node_id = max_node_id + i + 1
            self.simplified_graph.add_node(node_id, y=lat, x=lon, node_type="frontline")

            nearest = self._find_nearest_original_node(lat, lon, original_nodes)
            distance_km = haversine_distance(lat, lon, *self.get_node_coordinates(nearest))

            self.simplified_graph.add_edge(
                node_id, nearest,
                distance_km=distance_km,
                road_type="path",
                travel_time_hours=distance_km / 20.0,
                base_speed_kmh=20.0,
                detection_base=0.15,
            )
            self.simplified_graph.add_edge(
                nearest, node_id,
                distance_km=distance_km,
                road_type="path",
                travel_time_hours=distance_km / 20.0,
                base_speed_kmh=20.0,
                detection_base=0.15,
            )

        logger.info(f"Added {len(depots)} depots and {len(frontline_positions)} frontline nodes")

    def _find_nearest_original_node(self, lat: float, lon: float, original_nodes: List[int]) -> int:
        """Trouve le nœud le plus proche parmi les nœuds originaux du graphe."""
        nearest_node = None
        min_distance = float("inf")

        for node in original_nodes:
            data = self.simplified_graph.nodes[node]
            node_lat = data["y"]
            node_lon = data["x"]

            distance = haversine_distance(lat, lon, node_lat, node_lon)

            if distance < min_distance:
                min_distance = distance
                nearest_node = node

        return nearest_node

    def _compute_killzone_penalty(
        self,
        lat: float,
        lon: float,
        kill_zones: Optional[List[Dict]] = None,
    ) -> float:
        """
        Calcule la pénalité EXPONENTIELLE pour la proximité aux kill zones.

        Zones de pénalité:
        - Dans la kill zone (< rayon): 1000.0 (quasi-interdit)
        - Proche (< 1.5× rayon): 50-200 (très dangereux, exponentiel)
        - Buffer (< 2× rayon): 10.0 (zone de prudence)
        - Loin (>= 2× rayon): 1.0 (baseline)

        Args:
            lat, lon: Coordonnées du milieu de l'arc
            kill_zones: Liste de dicts de kill zones

        Returns:
            Multiplicateur de pénalité (>= 1.0)
        """
        if not kill_zones:
            return 1.0

        import math

        min_penalty = 1.0

        for kz in kill_zones:
            center_lat, center_lon = kz["center"]
            radius_km = kz["radius_km"]

            distance_km = haversine_distance(lat, lon, center_lat, center_lon)

            if distance_km < radius_km:
                penalty = 1000.0
            elif distance_km < radius_km * 1.5:
                proximity = 1.0 - (distance_km - radius_km) / (radius_km * 0.5)
                penalty = 50.0 * math.exp(3.0 * proximity)
            elif distance_km < radius_km * 2.0:
                penalty = 10.0
            else:
                penalty = 1.0

            min_penalty = max(min_penalty, penalty)

        return min_penalty
