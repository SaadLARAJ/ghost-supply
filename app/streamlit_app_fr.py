"""Ghost Supply - Tableau de Bord ."""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ghost_supply.decision.cvar_routing import CVaRRouter
from ghost_supply.decision.facility_location import generate_candidate_depots, select_depots
from ghost_supply.decision.graph_builder import GraphBuilder
from ghost_supply.output.visualization import create_tactical_map_2d
from ghost_supply.perception.terrain import TerrainAnalyzer
from ghost_supply.perception.threat_model import ThreatPredictor
from ghost_supply.perception.weather import WeatherModel
from ghost_supply.utils.constants import CARGO_VALUES, STUDY_AREA_BOUNDS, WEATHER_CONDITIONS
from ghost_supply.utils.data_loader import DataLoader

st.set_page_config(
    page_title="Ghost Supply 2.0",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Traductions
CARGO_FR = {
    "munitions": "Munitions",
    "medical": "Médical",
    "fuel": "Carburant",
    "food": "Nourriture",
    "equipment": "Équipement",
}

WEATHER_FR = {
    "clear": "Dégagé",
    "fog": "Brouillard",
    "rain": "Pluie",
    "snow": "Neige",
    "rasputitsa": "Rasputitsa (Boue)",
}


@st.cache_resource
def initialize_system():
    """Initialise le système."""
    data_loader = DataLoader()

    dem_result = data_loader.load_dem()
    if dem_result is None:
        st.info("🔄 Génération du terrain synthétique...")
        elevation, transform = data_loader.create_synthetic_dem(STUDY_AREA_BOUNDS, save=True)
    else:
        elevation, transform = dem_result

    terrain = TerrainAnalyzer(elevation, transform, STUDY_AREA_BOUNDS)

    threat_predictor = ThreatPredictor()
    incidents = data_loader.load_incidents()
    if incidents is None:
        st.info("🔄 Génération des données de menace...")
        incidents = threat_predictor.generate_synthetic_incidents()
        data_loader.save_incidents(incidents)

    threat_predictor.train_temporal_model(incidents)
    threat_predictor.identify_kill_zones()

    graph_builder = GraphBuilder(terrain, threat_predictor, WeatherModel())
    graph = graph_builder.build_from_osm(STUDY_AREA_BOUNDS)

    frontline_lat = (STUDY_AREA_BOUNDS["north"] + STUDY_AREA_BOUNDS["south"]) / 2
    frontline_lon = (STUDY_AREA_BOUNDS["east"] + STUDY_AREA_BOUNDS["west"]) / 2

    candidates = generate_candidate_depots(STUDY_AREA_BOUNDS, frontline_lat, num_candidates=20)
    depots = select_depots(candidates, frontline_lat, frontline_lon, num_depots=3)

    depot_positions = [(d.latitude, d.longitude) for d in depots]
    frontline_positions = [
        (frontline_lat + 0.02, frontline_lon - 0.1),
        (frontline_lat + 0.01, frontline_lon),
        (frontline_lat - 0.01, frontline_lon + 0.1),
    ]

    graph_builder.add_custom_nodes(depot_positions, frontline_positions)

    return {
        "terrain": terrain,
        "elevation": elevation,
        "threat_predictor": threat_predictor,
        "graph_builder": graph_builder,
        "graph": graph,
        "depots": depots,
        "frontline_positions": frontline_positions,
        "data_loader": data_loader,
    }


def main():
    """Application principale."""
    st.title("👻 Ghost Supply 2.0")
    st.caption("Optimiseur Logistique Tactique pour Environnements Contestés")

    system = initialize_system()

    terrain = system["terrain"]
    elevation = system["elevation"]
    threat_predictor = system["threat_predictor"]
    graph_builder = system["graph_builder"]
    graph = system["graph"]
    depots = system["depots"]
    frontline_positions = system["frontline_positions"]

    with st.sidebar:
        st.header("⚙️ Configuration de Mission")

        st.subheader("Paramètres de Route")

        depot_options = {f"{d.name}": i for i, d in enumerate(depots)}
        origin_name = st.selectbox("Dépôt d'Origine", list(depot_options.keys()))
        origin_idx = depot_options[origin_name]
        origin_depot = depots[origin_idx]

        frontline_options = {
            f"Position {chr(65+i)}": i for i in range(len(frontline_positions))
        }
        dest_name = st.selectbox("Destination", list(frontline_options.keys()))
        dest_idx = frontline_options[dest_name]

        st.subheader("Détails du Chargement")

        cargo_type = st.selectbox("Type de Cargo", list(CARGO_FR.values()))
        cargo_type_en = [k for k, v in CARGO_FR.items() if v == cargo_type][0]
        
        cargo_value = st.slider(
            "Valeur Stratégique",
            min_value=1,
            max_value=10,
            value=CARGO_VALUES.get(cargo_type_en, 7),
        )

        st.subheader("Conditions")

        weather = st.selectbox("Météo", list(WEATHER_FR.values()), index=0)
        weather_en = [k for k, v in WEATHER_FR.items() if v == weather][0]

        departure_hour = st.slider("Heure de Départ (24h)", min_value=0, max_value=23, value=14)

        st.divider()

        optimize_button = st.button("🎯 Optimiser la Route", type="primary", use_container_width=True)

    if optimize_button:
        with st.spinner("⏳ Optimisation de la route tactique..."):
            origin_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "depot"]
            frontline_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "frontline"]

            if not origin_nodes or not frontline_nodes:
                st.error("❌ Erreur: nœuds du graphe mal configurés")
                return

            origin_node = origin_nodes[origin_idx]
            dest_node = frontline_nodes[dest_idx]

            departure_time = datetime.now().replace(hour=departure_hour, minute=0, second=0)

            observer_positions = [(48.3, 37.2), (48.25, 37.35)]
            viewshed = terrain.calculate_viewshed(observer_positions)

            kill_zones = threat_predictor.kill_zones if hasattr(threat_predictor, 'kill_zones') else []

            graph_builder.enrich_graph(
                viewshed=viewshed,
                rf_coverage=None,
                weather=weather_en,
                timestamp=departure_time,
                kill_zones=kill_zones,
            )

            router = CVaRRouter(graph, alpha=0.95, num_scenarios=50)

            # Utilise seulement les méthodes Dijkstra (pas de MILP)
            st.info("ℹ️ Utilisation des algorithmes de Dijkstra (pas de CVaR MILP)")

            # Essaie plusieurs méthodes jusqu'à ce qu'une fonctionne
            baseline_route = router.shortest_time(origin_node, dest_node)
            shortest_route = router.shortest_distance(origin_node, dest_node)

            # Vérifie que les routes ont des chemins
            if not baseline_route.path:
                st.error("❌ Impossible de trouver le chemin le plus rapide")
                return

            if not shortest_route.path:
                st.error("❌ Impossible de trouver le chemin le plus court")
                return

            # Essaie mean_risk, sinon utilise shortest_time comme fallback
            try:
                mean_risk_route = router.mean_risk(origin_node, dest_node, cargo_value=cargo_value)
                if not mean_risk_route.path:
                    st.warning("⚠️ Le calcul du risque moyen a échoué, repli sur le temps le plus court")
                    mean_risk_route = baseline_route
            except Exception as e:
                st.warning(f"⚠️ Le calcul du risque moyen a échoué ({e}), repli sur le temps le plus court")
                mean_risk_route = baseline_route

        st.session_state["optimal_route"] = mean_risk_route
        st.session_state["baseline_route"] = baseline_route
        st.session_state["shortest_route"] = shortest_route
        st.session_state["departure_time"] = departure_time
        st.session_state["weather"] = weather
        st.session_state["cargo_type"] = cargo_type
        st.session_state["cargo_value"] = cargo_value
        st.session_state["threat_predictor"] = threat_predictor
        st.session_state["depots"] = depots

    if "optimal_route" in st.session_state:
        optimal_route = st.session_state["optimal_route"]
        baseline_route = st.session_state["baseline_route"]

        st.subheader("📍 Carte Tactique")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Distance", f"{optimal_route.distance_km:.1f} km")
        with col2:
            st.metric("Durée", f"{optimal_route.time_minutes:.0f} min")
        with col3:
            survival_prob = optimal_route.survival_probability * 100
            st.metric("Prob. Survie", f"{survival_prob:.1f}%")

        kill_zones = st.session_state["threat_predictor"].kill_zones
        depot_list = [(d.latitude, d.longitude, d.name) for d in st.session_state["depots"]]

        tactical_map = create_tactical_map_2d(
            optimal_route,
            baseline_route,
            kill_zones,
            depot_list,
        )

        st.components.v1.html(tactical_map._repr_html_(), height=600)

        st.subheader("📊 Comparaison des Méthodes")
        
        results_dict = {
            "Risque Minimum": optimal_route,
            "Le Plus Rapide": baseline_route,
            "Le Plus Court": st.session_state["shortest_route"],
        }

        st.dataframe({
            "Méthode": list(results_dict.keys()),
            "Temps (min)": [f"{r.time_minutes:.0f}" for r in results_dict.values()],
            "Distance (km)": [f"{r.distance_km:.1f}" for r in results_dict.values()],
            "Score Risque": [f"{r.cvar_95:.2f}" for r in results_dict.values()],
            "Prob. Survie (%)": [f"{r.survival_probability * 100:.1f}" for r in results_dict.values()],
        })

        time_overhead = (optimal_route.time_minutes - baseline_route.time_minutes) / baseline_route.time_minutes * 100
        risk_reduction = (baseline_route.mean_risk - optimal_route.mean_risk) / baseline_route.mean_risk * 100

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Surcoût Temps", f"+{time_overhead:.1f}%")
        with col2:
            st.metric("Réduction Risque", f"-{risk_reduction:.1f}%")

    else:
        st.info("👈 Configurez les paramètres de mission et cliquez sur 'Optimiser la Route'")

        st.markdown("""
        ## À Propos de Ghost Supply 2.0

        **Ghost Supply** est un optimiseur logistique tactique pour environnements contestés.
        Il minimise le risque d'interception plutôt que la distance.

        ### Fonctionnalités Principales

        - ✅ **Optimisation de Risque** : Minimise le risque moyen sur la route
        - 🗺️ **Modélisation du Terrain** : Analyse de visibilité et de mobilité
        - ⚠️ **Prédiction de Menace** : Identification des zones dangereuses (Prophet + DBSCAN)
        - 🌦️ **Impact Météo** : Prise en compte de la météo sur la détection et la mobilité
        - 📊 **Comparaisons** : Montre les gains vs routes GPS standard

        ### Comment Utiliser

        1. Sélectionnez un **dépôt d'origine** et une **destination**
        2. Choisissez le **type de cargo** et les **conditions** (météo, heure)
        3. Cliquez sur **"Optimiser la Route"**
        4. Visualisez la carte et les métriques

        ---

        **Note**: Cette version utilise les algorithmes de Dijkstra.  
        Pour la version complète avec CVaR et théorie des jeux, installez les solveurs d'optimisation.
        """)


if __name__ == "__main__":
    main()
