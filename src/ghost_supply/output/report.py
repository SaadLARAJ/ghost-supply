"""Mission briefing report generation."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ghost_supply.decision.cvar_routing import RouteResult


def generate_mission_briefing(
    route: RouteResult,
    baseline_route: RouteResult,
    weather: str,
    departure_time: datetime,
    cargo_type: str,
    cargo_value: int,
    kill_zones: Optional[List[Dict]] = None,
) -> str:
    """
    Generate comprehensive mission briefing document.

    Args:
        route: Optimized route
        baseline_route: Baseline comparison route
        weather: Weather condition
        departure_time: Planned departure time
        cargo_type: Type of cargo
        cargo_value: Strategic value (1-10)
        kill_zones: Known kill zones

    Returns:
        Formatted briefing text
    """
    briefing = []

    briefing.append("=" * 80)
    briefing.append("GHOST SUPPLY - TACTICAL MISSION BRIEFING".center(80))
    briefing.append("=" * 80)
    briefing.append("")

    eta = departure_time + timedelta(minutes=route.time_minutes)
    survival_prob = (1.0 - route.cvar_95) * 100

    briefing.append("EXECUTIVE SUMMARY")
    briefing.append("-" * 80)
    briefing.append(f"  Departure:        {departure_time.strftime('%Y-%m-%d %H:%M')}")
    briefing.append(f"  ETA:              {eta.strftime('%Y-%m-%d %H:%M')} (+{route.time_minutes:.0f} minutes)")
    briefing.append(f"  Distance:         {route.distance_km:.1f} km")
    briefing.append(f"  Cargo:            {cargo_type.title()} (Priority: {cargo_value}/10)")
    briefing.append(f"  Survival Prob:    {survival_prob:.1f}% (CVaR 95%)")
    briefing.append("")

    briefing.append("MISSION CONDITIONS")
    briefing.append("-" * 80)
    briefing.append(f"  Weather:          {weather.upper()}")

    time_of_day = "DAY" if 6 <= departure_time.hour <= 20 else "NIGHT"
    briefing.append(f"  Time of Day:      {time_of_day}")

    if weather == "fog":
        briefing.append("  ⚠ Fog provides excellent concealment from optical drones")
    elif weather == "rasputitsa":
        briefing.append("  ⚠ Mud season: off-road movement severely restricted")

    briefing.append("")

    briefing.append("ROUTE ANALYSIS")
    briefing.append("-" * 80)
    briefing.append(f"  Optimized Route:  {route.method}")
    briefing.append(f"    - Distance:     {route.distance_km:.1f} km")
    briefing.append(f"    - Duration:     {route.time_minutes:.0f} min")
    briefing.append(f"    - Mean Risk:    {route.mean_risk:.3f}")
    briefing.append(f"    - CVaR 95%:     {route.cvar_95:.3f}")
    briefing.append(f"    - CVaR 99%:     {route.cvar_99:.3f}")
    briefing.append("")

    briefing.append(f"  Baseline ({baseline_route.method}):")
    briefing.append(f"    - Distance:     {baseline_route.distance_km:.1f} km")
    briefing.append(f"    - Duration:     {baseline_route.time_minutes:.0f} min")
    briefing.append(f"    - CVaR 95%:     {baseline_route.cvar_95:.3f}")
    briefing.append("")

    time_diff = route.time_minutes - baseline_route.time_minutes
    risk_reduction = (baseline_route.cvar_95 - route.cvar_95) / baseline_route.cvar_95 * 100 if baseline_route.cvar_95 > 0 else 0

    briefing.append(f"  Optimization Gain:")
    briefing.append(f"    - Time overhead: +{time_diff:.0f} min ({time_diff/baseline_route.time_minutes*100:.1f}%)")
    briefing.append(f"    - Risk reduction: {risk_reduction:.1f}%")
    briefing.append("")

    briefing.append("WAYPOINTS & INSTRUCTIONS")
    briefing.append("-" * 80)

    for i, wp in enumerate(route.waypoints):
        briefing.append(f"  {i+1}. {wp.name}")
        briefing.append(f"     Position: {wp.latitude:.5f}, {wp.longitude:.5f}")
        briefing.append(f"     ETA:      +{wp.eta_hours:.2f} hours")

        if wp.risk_level > 0.5:
            briefing.append(f"     ⚠ HIGH RISK AREA - Increase vigilance")
        elif wp.risk_level > 0.3:
            briefing.append(f"     ⚠ Moderate risk")

        if wp.instructions:
            briefing.append(f"     Action:   {wp.instructions}")

        briefing.append("")

    if kill_zones:
        briefing.append("THREAT ASSESSMENT")
        briefing.append("-" * 80)
        briefing.append(f"  Identified Kill Zones: {len(kill_zones)}")
        briefing.append("")

        route_intersects_kz = False

        for kz in kill_zones:
            from ghost_supply.utils.geo import haversine_distance

            min_distance = float("inf")
            for lat, lon in route.path:
                distance = haversine_distance(lat, lon, kz["center"][0], kz["center"][1])
                min_distance = min(min_distance, distance)

            if min_distance <= kz["radius_km"]:
                route_intersects_kz = True
                briefing.append(f"  ⚠ Kill Zone {kz['id']}: ROUTE PASSES THROUGH")
                briefing.append(f"     Center:     {kz['center'][0]:.4f}, {kz['center'][1]:.4f}")
                briefing.append(f"     Radius:     {kz['radius_km']:.1f} km")
                briefing.append(f"     Incidents:  {kz['num_incidents']}")
                briefing.append(f"     Distance:   {min_distance:.1f} km from route")
                briefing.append("")

        if route_intersects_kz:
            briefing.append("  ⚠⚠⚠ WARNING: Route passes through identified kill zones")
            briefing.append("  Recommend: Increase speed, minimize stops, maintain vigilance")
        else:
            briefing.append("  ✓ Route avoids all identified kill zones")

        briefing.append("")

    briefing.append("RECOMMENDATIONS")
    briefing.append("-" * 80)

    if time_of_day == "NIGHT":
        briefing.append("  ✓ Night movement reduces detection risk")
    else:
        briefing.append("  ⚠ Daylight movement increases drone detection risk")

    if weather in ["fog", "rain"]:
        briefing.append("  ✓ Weather conditions favor movement (reduced visibility)")
    elif weather == "clear":
        briefing.append("  ⚠ Clear weather optimal for enemy surveillance")

    if route.cvar_95 < 0.3:
        briefing.append("  ✓ Low risk route - proceed with standard protocols")
    elif route.cvar_95 < 0.6:
        briefing.append("  ⚠ Moderate risk - enhanced vigilance required")
    else:
        briefing.append("  ⚠⚠⚠ HIGH RISK MISSION - Consider postponement or alternate route")

    briefing.append("")
    briefing.append("  Equipment Recommendations:")
    briefing.append("    - Electronic warfare suite (anti-drone)")
    briefing.append("    - Smoke grenades for concealment")
    briefing.append("    - Emergency satellite communications")
    briefing.append("    - First aid / MEDEVAC capability")
    briefing.append("")

    briefing.append("=" * 80)
    briefing.append("EXECUTE WITH CAUTION. MAINTAIN OPSEC. STAY ALERT.".center(80))
    briefing.append("=" * 80)

    return "\n".join(briefing)
