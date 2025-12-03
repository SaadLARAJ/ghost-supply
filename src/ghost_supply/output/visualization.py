"""Visualization functions for routes, terrain, and tactical overlays."""

from typing import Any, Dict, List, Optional, Tuple

import folium
import numpy as np
import plotly.graph_objects as go
from loguru import logger

from ghost_supply.decision.cvar_routing import RouteResult
from ghost_supply.utils.constants import (
    COLOR_DEPOT,
    COLOR_FRONTLINE,
    COLOR_KILLZONE,
    COLOR_ROUTE_BASELINE,
    COLOR_ROUTE_OPTIMAL,
    MAP_TILE_PROVIDER,
    MAP_ZOOM_DEFAULT,
)


def create_tactical_map_2d(
    optimal_route: RouteResult,
    baseline_route: Optional[RouteResult] = None,
    kill_zones: Optional[List[Dict]] = None,
    depots: Optional[List[Tuple[float, float, str]]] = None,
    frontline: Optional[List[Tuple[float, float]]] = None,
) -> folium.Map:
    """
    Create 2D tactical map with Folium.

    Args:
        optimal_route: Optimized route
        baseline_route: Baseline route for comparison
        kill_zones: List of kill zone dicts
        depots: List of (lat, lon, name) depot tuples
        frontline: List of frontline positions

    Returns:
        Folium Map object
    """
    logger.info("Creating 2D tactical map")

    if not optimal_route.path:
        raise ValueError("Optimal route has no path")

    center_lat = np.mean([p[0] for p in optimal_route.path])
    center_lon = np.mean([p[1] for p in optimal_route.path])

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=MAP_ZOOM_DEFAULT,
        tiles="CartoDB dark_matter",
    )

    if baseline_route and baseline_route.path:
        folium.PolyLine(
            baseline_route.path,
            color="#FF4444",
            weight=4,
            opacity=0.8,
            dash_array="10, 10",
            popup=f"Baseline ({baseline_route.method})<br>"
                  f"Distance: {baseline_route.distance_km:.1f} km<br>"
                  f"Time: {baseline_route.time_minutes:.0f} min<br>"
                  f"CVaR: {baseline_route.cvar_95:.3f}",
        ).add_to(m)

    folium.PolyLine(
        optimal_route.path,
        color=COLOR_ROUTE_OPTIMAL,
        weight=5,
        opacity=0.9,
        popup=f"Optimized Route ({optimal_route.method})<br>"
              f"Distance: {optimal_route.distance_km:.1f} km<br>"
              f"Time: {optimal_route.time_minutes:.0f} min<br>"
              f"CVaR: {optimal_route.cvar_95:.3f}",
    ).add_to(m)

    for i, waypoint in enumerate(optimal_route.waypoints):
        icon_color = "green" if i == 0 else ("red" if i == len(optimal_route.waypoints) - 1 else "blue")

        folium.Marker(
            [waypoint.latitude, waypoint.longitude],
            popup=f"{waypoint.name}<br>ETA: +{waypoint.eta_hours:.1f}h",
            tooltip=waypoint.name,
            icon=folium.Icon(color=icon_color, icon="info-sign"),
        ).add_to(m)

    if kill_zones:
        for kz in kill_zones:
            center_lat, center_lon = kz["center"]

            folium.Circle(
                [center_lat, center_lon],
                radius=kz["radius_km"] * 1000,
                color=COLOR_KILLZONE,
                fill=True,
                fillColor=COLOR_KILLZONE,
                fillOpacity=0.3,
                popup=f"Kill Zone {kz['id']}<br>"
                      f"Incidents: {kz['num_incidents']}<br>"
                      f"Radius: {kz['radius_km']:.1f} km",
            ).add_to(m)

    if depots:
        for lat, lon, name in depots:
            folium.Marker(
                [lat, lon],
                popup=f"Depot: {name}",
                tooltip=name,
                icon=folium.Icon(color="darkgreen", icon="home", prefix="glyphicon"),
            ).add_to(m)

    if frontline:
        folium.PolyLine(
            frontline,
            color=COLOR_FRONTLINE,
            weight=3,
            opacity=0.7,
            dash_array="5, 5",
            popup="Frontline (approximate)",
        ).add_to(m)

    # Légende tactique
    legend_html = '''
    <div style="position: fixed;
                bottom: 50px; right: 50px; width: 280px; height: auto;
                background-color: rgba(40, 40, 40, 0.95);
                border: 2px solid #555;
                border-radius: 8px;
                z-index: 9999;
                font-size: 14px;
                padding: 15px;
                color: #eee;
                font-family: monospace;">
        <h4 style="margin-top:0; color: #0f0; text-align: center;">🎯 LÉGENDE TACTIQUE</h4>
        <p style="margin: 8px 0;">
            <span style="color: #00FF00; font-weight: bold;">━━━</span> Route optimisée (Ghost Supply)
        </p>
        <p style="margin: 8px 0;">
            <span style="color: #FF4444; font-weight: bold;">┄┄┄</span> Route GPS directe (dangereuse)
        </p>
        <p style="margin: 8px 0;">
            <span style="color: #FF0000; font-weight: bold;">●</span> Kill zones (zones de danger)
        </p>
        <p style="margin: 8px 0;">
            <span style="color: #0a6e0a; font-weight: bold;">🏠</span> Dépôts / Bunkers
        </p>
        <p style="margin: 8px 0;">
            <span style="color: #4444FF; font-weight: bold;">📍</span> Waypoints
        </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    logger.info("2D tactical map created")

    return m


def create_terrain_3d(
    elevation: np.ndarray,
    bounds: Dict[str, float],
    route_path: Optional[List[Tuple[float, float]]] = None,
    risk_overlay: Optional[np.ndarray] = None,
) -> go.Figure:
    """
    Create 3D terrain visualization with Plotly.

    Args:
        elevation: 2D elevation array
        bounds: Geographic bounds
        route_path: Optional route to overlay
        risk_overlay: Optional risk heatmap

    Returns:
        Plotly Figure
    """
    logger.info("Creating 3D terrain visualization")

    height, width = elevation.shape

    lats = np.linspace(bounds["south"], bounds["north"], height)
    lons = np.linspace(bounds["west"], bounds["east"], width)

    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")

    if risk_overlay is not None:
        colorscale = "Reds"
        surfacecolor = risk_overlay
        colorbar_title = "Risk Level"
    else:
        colorscale = "Earth"
        surfacecolor = elevation
        colorbar_title = "Elevation (m)"

    fig = go.Figure()

    fig.add_trace(go.Surface(
        x=lon_grid,
        y=lat_grid,
        z=elevation,
        surfacecolor=surfacecolor,
        colorscale=colorscale,
        name="Terrain",
        colorbar=dict(title=colorbar_title),
    ))

    if route_path:
        route_lats = [p[0] for p in route_path]
        route_lons = [p[1] for p in route_path]

        route_elevations = []
        for lat, lon in route_path:
            row = int((lat - bounds["south"]) / (bounds["north"] - bounds["south"]) * (height - 1))
            col = int((lon - bounds["west"]) / (bounds["east"] - bounds["west"]) * (width - 1))
            row = np.clip(row, 0, height - 1)
            col = np.clip(col, 0, width - 1)
            route_elevations.append(elevation[row, col] + 50)

        fig.add_trace(go.Scatter3d(
            x=route_lons,
            y=route_lats,
            z=route_elevations,
            mode="lines+markers",
            line=dict(color="lime", width=6),
            marker=dict(size=4, color="yellow"),
            name="Route",
        ))

    fig.update_layout(
        title="Tactical 3D Terrain View",
        scene=dict(
            xaxis_title="Longitude",
            yaxis_title="Latitude",
            zaxis_title="Elevation (m)",
            aspectmode="manual",
            aspectratio=dict(x=2, y=2, z=0.5),
        ),
        height=700,
    )

    logger.info("3D terrain created")

    return fig


def create_rf_coverage_map(
    rf_coverage: np.ndarray,
    bounds: Dict[str, float],
    route_path: Optional[List[Tuple[float, float]]] = None,
) -> go.Figure:
    """
    Create RF coverage heatmap.

    Args:
        rf_coverage: 2D RF coverage array (dBm)
        bounds: Geographic bounds
        route_path: Optional route overlay

    Returns:
        Plotly Figure
    """
    logger.info("Creating RF coverage map")

    height, width = rf_coverage.shape

    lats = np.linspace(bounds["south"], bounds["north"], height)
    lons = np.linspace(bounds["west"], bounds["east"], width)

    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        x=lons,
        y=lats,
        z=rf_coverage,
        colorscale="RdYlGn",
        colorbar=dict(title="Signal (dBm)"),
        name="RF Coverage",
    ))

    if route_path:
        route_lats = [p[0] for p in route_path]
        route_lons = [p[1] for p in route_path]

        fig.add_trace(go.Scatter(
            x=route_lons,
            y=route_lats,
            mode="lines+markers",
            line=dict(color="white", width=3),
            marker=dict(size=6, color="cyan"),
            name="Route",
        ))

    fig.update_layout(
        title="RF Coverage Map",
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        height=600,
    )

    logger.info("RF coverage map created")

    return fig


def create_pareto_plot(
    pareto_front: List[RouteResult],
    baseline_results: Optional[List[RouteResult]] = None,
) -> go.Figure:
    """
    Create Pareto front visualization.

    Args:
        pareto_front: List of Pareto-optimal routes
        baseline_results: Optional baseline routes

    Returns:
        Plotly Figure
    """
    logger.info("Creating Pareto front plot")

    fig = go.Figure()

    pareto_times = [r.time_minutes for r in pareto_front]
    pareto_risks = [r.cvar_95 for r in pareto_front]
    pareto_labels = [r.method for r in pareto_front]

    fig.add_trace(go.Scatter(
        x=pareto_times,
        y=pareto_risks,
        mode="lines+markers+text",
        line=dict(color="green", width=3),
        marker=dict(size=12, color="green"),
        text=pareto_labels,
        textposition="top center",
        name="Pareto Front",
    ))

    if baseline_results:
        baseline_times = [r.time_minutes for r in baseline_results]
        baseline_risks = [r.cvar_95 for r in baseline_results]
        baseline_labels = [r.method for r in baseline_results]

        fig.add_trace(go.Scatter(
            x=baseline_times,
            y=baseline_risks,
            mode="markers+text",
            marker=dict(size=10, color="red", symbol="x"),
            text=baseline_labels,
            textposition="top center",
            name="Baselines",
        ))

    fig.update_layout(
        title="Pareto Front: Time vs Risk Trade-off",
        xaxis_title="Travel Time (minutes)",
        yaxis_title="CVaR 95% Risk",
        height=600,
        showlegend=True,
    )

    logger.info("Pareto plot created")

    return fig


def create_comparison_chart(results_dict: Dict[str, RouteResult]) -> go.Figure:
    """
    Create comparison bar chart for different routing methods.

    Args:
        results_dict: Dict mapping method name to RouteResult

    Returns:
        Plotly Figure
    """
    logger.info("Creating comparison chart")

    methods = list(results_dict.keys())
    times = [results_dict[m].time_minutes for m in methods]
    distances = [results_dict[m].distance_km for m in methods]
    mean_risks = [results_dict[m].mean_risk for m in methods]
    cvars = [results_dict[m].cvar_95 for m in methods]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Time (min)",
        x=methods,
        y=times,
        yaxis="y",
    ))

    fig.add_trace(go.Bar(
        name="CVaR 95%",
        x=methods,
        y=cvars,
        yaxis="y2",
    ))

    fig.update_layout(
        title="Routing Methods Comparison",
        xaxis=dict(title="Method"),
        yaxis=dict(title="Time (minutes)", side="left"),
        yaxis2=dict(title="CVaR Risk", overlaying="y", side="right"),
        barmode="group",
        height=500,
    )

    logger.info("Comparison chart created")

    return fig
