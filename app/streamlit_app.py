"""Ghost Supply Streamlit Dashboard - Tactical Route Optimizer."""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ghost_supply.decision.cvar_routing import CVaRRouter
from ghost_supply.decision.facility_location import (
    generate_candidate_depots,
    select_depots,
)
from ghost_supply.decision.game_theory import StackelbergRouter
from ghost_supply.decision.graph_builder import GraphBuilder
from ghost_supply.decision.pareto import ParetoFrontGenerator
from ghost_supply.output.cot_export import export_mission_package
from ghost_supply.output.report import generate_mission_briefing
from ghost_supply.output.visualization import (
    create_comparison_chart,
    create_pareto_plot,
    create_tactical_map_2d,
    create_terrain_3d,
)
from ghost_supply.perception.rf_propagation import RFPropagationModel
from ghost_supply.perception.terrain import TerrainAnalyzer
from ghost_supply.perception.threat_model import ThreatPredictor
from ghost_supply.perception.weather import WeatherModel
from ghost_supply.utils.constants import (
    CARGO_VALUES,
    STUDY_AREA_BOUNDS,
    WEATHER_CONDITIONS,
)
from ghost_supply.utils.data_loader import DataLoader

st.set_page_config(
    page_title="Ghost Supply 2.0",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def initialize_system():
    """Initialize and cache system components."""
    data_loader = DataLoader()

    dem_result = data_loader.load_dem()
    if dem_result is None:
        st.info("No DEM found. Generating synthetic terrain...")
        elevation, transform = data_loader.create_synthetic_dem(STUDY_AREA_BOUNDS, save=True)
    else:
        elevation, transform = dem_result

    terrain = TerrainAnalyzer(elevation, transform, STUDY_AREA_BOUNDS)

    threat_predictor = ThreatPredictor()
    incidents = data_loader.load_incidents()
    if incidents is None:
        st.info("Generating synthetic threat data...")
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
    """Main Streamlit application."""
    st.title("👻 Ghost Supply 2.0")
    st.caption("Tactical Logistics Optimizer for Contested Environments")

    system = initialize_system()

    terrain = system["terrain"]
    elevation = system["elevation"]
    threat_predictor = system["threat_predictor"]
    graph_builder = system["graph_builder"]
    graph = system["graph"]
    depots = system["depots"]
    frontline_positions = system["frontline_positions"]

    with st.sidebar:
        st.header("⚙️ Mission Configuration")

        st.subheader("Route Parameters")

        depot_options = {f"{d.name}": i for i, d in enumerate(depots)}
        origin_name = st.selectbox("Origin Depot", list(depot_options.keys()))
        origin_idx = depot_options[origin_name]
        origin_depot = depots[origin_idx]

        frontline_options = {
            f"Position {chr(65+i)}": i for i in range(len(frontline_positions))
        }
        dest_name = st.selectbox("Destination", list(frontline_options.keys()))
        dest_idx = frontline_options[dest_name]

        st.subheader("Cargo Details")

        cargo_type = st.selectbox("Cargo Type", list(CARGO_VALUES.keys()))
        cargo_value = st.slider(
            "Strategic Value",
            min_value=1,
            max_value=10,
            value=CARGO_VALUES[cargo_type],
        )

        st.subheader("Conditions")

        weather = st.selectbox("Weather", WEATHER_CONDITIONS, index=0)

        departure_hour = st.slider("Departure Hour", min_value=0, max_value=23, value=14)

        risk_tolerance = st.slider(
            "CVaR Confidence Level",
            min_value=0.90,
            max_value=0.99,
            value=0.95,
            step=0.01,
        )

        st.divider()

        optimize_button = st.button("🎯 Optimize Route", type="primary", use_container_width=True)

    if optimize_button:
        with st.spinner("Optimizing tactical route..."):
            origin_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "depot"]
            frontline_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "frontline"]

            if not origin_nodes or not frontline_nodes:
                st.error("Graph nodes not properly configured")
                return

            origin_node = origin_nodes[origin_idx]
            dest_node = frontline_nodes[dest_idx]

            departure_time = datetime.now().replace(hour=departure_hour, minute=0, second=0)

            observer_positions = [(48.3, 37.2), (48.25, 37.35)]
            viewshed = terrain.calculate_viewshed(observer_positions)

            # Get kill zones from threat predictor
            kill_zones = threat_predictor.kill_zones if hasattr(threat_predictor, 'kill_zones') else []

            graph_builder.enrich_graph(
                viewshed=viewshed,
                rf_coverage=None,
                weather=weather,
                timestamp=departure_time,
                kill_zones=kill_zones,
            )

            router = CVaRRouter(graph, alpha=risk_tolerance)

            cvar_route = router.optimize(origin_node, dest_node, cargo_value=cargo_value)

            baseline_route = router.shortest_time(origin_node, dest_node)

            mean_risk_route = router.mean_risk(origin_node, dest_node, cargo_value)

            shortest_route = router.shortest_distance(origin_node, dest_node)

        st.session_state["cvar_route"] = cvar_route
        st.session_state["baseline_route"] = baseline_route
        st.session_state["mean_risk_route"] = mean_risk_route
        st.session_state["shortest_route"] = shortest_route
        st.session_state["departure_time"] = departure_time
        st.session_state["weather"] = weather
        st.session_state["cargo_type"] = cargo_type
        st.session_state["cargo_value"] = cargo_value
        st.session_state["terrain"] = terrain
        st.session_state["elevation"] = elevation
        st.session_state["threat_predictor"] = threat_predictor
        st.session_state["router"] = router
        st.session_state["origin_node"] = origin_node
        st.session_state["dest_node"] = dest_node
        st.session_state["depots"] = depots

    if "cvar_route" in st.session_state:
        cvar_route = st.session_state["cvar_route"]
        baseline_route = st.session_state["baseline_route"]
        mean_risk_route = st.session_state["mean_risk_route"]
        shortest_route = st.session_state["shortest_route"]

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📍 Tactical Map",
            "🗻 3D Terrain",
            "📊 Risk Analysis",
            "⚖️ Comparison",
            "🎲 Game Theory"
        ])

        with tab1:
            st.subheader("2D Tactical Map")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Distance", f"{cvar_route.distance_km:.1f} km")
            with col2:
                st.metric("Duration", f"{cvar_route.time_minutes:.0f} min")
            with col3:
                survival_prob = cvar_route.survival_probability * 100
                st.metric("Survival Prob", f"{survival_prob:.1f}%")

            kill_zones = st.session_state["threat_predictor"].kill_zones

            depot_list = [(d.latitude, d.longitude, d.name) for d in st.session_state["depots"]]

            tactical_map = create_tactical_map_2d(
                cvar_route,
                baseline_route,
                kill_zones,
                depot_list,
            )

            st.components.v1.html(tactical_map._repr_html_(), height=600)

        with tab2:
            st.subheader("3D Terrain View")

            terrain_3d = create_terrain_3d(
                st.session_state["elevation"],
                STUDY_AREA_BOUNDS,
                cvar_route.path,
            )

            st.plotly_chart(terrain_3d, use_container_width=True)

        with tab3:
            st.subheader("Pareto Front Analysis")

            if st.button("Generate Pareto Front"):
                with st.spinner("Computing Pareto optimal solutions..."):
                    pareto_gen = ParetoFrontGenerator(st.session_state["router"])
                    pareto_front = pareto_gen.generate(
                        st.session_state["origin_node"],
                        st.session_state["dest_node"],
                        st.session_state["cargo_value"],
                        num_points=5,
                    )

                    st.session_state["pareto_front"] = pareto_front

            if "pareto_front" in st.session_state:
                pareto_plot = create_pareto_plot(
                    st.session_state["pareto_front"],
                    [baseline_route, mean_risk_route, shortest_route],
                )

                st.plotly_chart(pareto_plot, use_container_width=True)

        with tab4:
            st.subheader("Method Comparison")

            results_dict = {
                "CVaR 95%": cvar_route,
                "Fastest": baseline_route,
                "Mean Risk": mean_risk_route,
                "Shortest": shortest_route,
            }

            comparison_chart = create_comparison_chart(results_dict)

            st.plotly_chart(comparison_chart, use_container_width=True)

            st.dataframe({
                "Method": list(results_dict.keys()),
                "Time (min)": [f"{r.time_minutes:.0f}" for r in results_dict.values()],
                "Distance (km)": [f"{r.distance_km:.1f}" for r in results_dict.values()],
                "Risk Score": [f"{r.cvar_95:.2f}" for r in results_dict.values()],
                "Survival Prob (%)": [f"{r.survival_probability * 100:.1f}" for r in results_dict.values()],
            })

        with tab5:
            st.subheader("Stackelberg Game Theory")

            if st.button("Compute Mixed Strategy"):
                with st.spinner("Solving game..."):
                    stackelberg = StackelbergRouter(st.session_state["router"])
                    routes, strategy = stackelberg.solve(
                        st.session_state["origin_node"],
                        st.session_state["dest_node"],
                        st.session_state["cargo_value"],
                    )

                    st.session_state["game_routes"] = routes
                    st.session_state["game_strategy"] = strategy

            if "game_strategy" in st.session_state:
                st.write("**Mixed Strategy Distribution:**")

                st.bar_chart({
                    f"Route {i+1}": prob
                    for i, prob in enumerate(st.session_state["game_strategy"])
                })

                st.info("Use different routes for each mission to remain unpredictable")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📦 Download ATAK Package", use_container_width=True):
                with st.spinner("Generating mission package..."):
                    output_zip = "outputs/mission_package.zip"

                    export_mission_package(
                        cvar_route,
                        baseline_route,
                        st.session_state["threat_predictor"].kill_zones,
                        output_zip,
                        f"Ghost Supply - {st.session_state['cargo_type'].title()}",
                    )

                    with open(output_zip, "rb") as f:
                        st.download_button(
                            "⬇️ Download ZIP",
                            f,
                            file_name="ghost_supply_mission.zip",
                            mime="application/zip",
                        )

        with col2:
            if st.button("📄 Generate Briefing", use_container_width=True):
                briefing = generate_mission_briefing(
                    cvar_route,
                    baseline_route,
                    st.session_state["weather"],
                    st.session_state["departure_time"],
                    st.session_state["cargo_type"],
                    st.session_state["cargo_value"],
                    st.session_state["threat_predictor"].kill_zones,
                )

                st.text_area("Mission Briefing", briefing, height=400)

                st.download_button(
                    "⬇️ Download Briefing",
                    briefing,
                    file_name="mission_briefing.txt",
                    mime="text/plain",
                )

    else:
        st.info("👈 Configure mission parameters and click 'Optimize Route' to begin")

        st.markdown("""
        ## About Ghost Supply 2.0

        **Ghost Supply** is a tactical logistics optimizer designed for contested environments.
        It uses advanced operations research techniques to plan supply routes that minimize
        the risk of interception rather than just minimizing distance or time.

        ### Key Features

        - **CVaR Optimization**: Minimizes tail risk (worst-case scenarios) instead of average risk
        - **RF Propagation Modeling**: Accounts for radio coverage and communication dead zones
        - **Threat Prediction**: Uses Prophet + DBSCAN to identify high-risk areas
        - **Weather Integration**: Factors in weather impact on mobility and detection
        - **Pareto Analysis**: Shows time vs risk trade-offs
        - **Game Theory**: Stackelberg equilibrium for route randomization
        - **ATAK Export**: Generates mission packages compatible with military planning tools

        ### How It Works

        1. Configure your mission parameters (origin, destination, cargo, weather)
        2. Click "Optimize Route" to compute the safest path
        3. View the tactical map with kill zones and optimal route
        4. Compare with baseline methods (GPS shortest, fastest, etc.)
        5. Download mission package for field use

        ---

        **Built for**: Defense portfolio | **Tech Stack**: Python, Pyomo, Prophet, NetworkX, Streamlit
        """)


if __name__ == "__main__":
    main()
