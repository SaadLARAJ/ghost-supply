"""Cursor-on-Target (CoT) export for ATAK/WinTAK integration."""

import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET

from loguru import logger

from ghost_supply.decision.cvar_routing import RouteResult, Waypoint
from ghost_supply.utils.constants import (
    COT_TYPE_CONVOY,
    COT_TYPE_DEPOT,
    COT_TYPE_THREAT,
    COT_TYPE_WAYPOINT,
    COT_UID_PREFIX,
    COT_VERSION,
)


def export_to_cot(
    route: RouteResult,
    output_path: str,
    mission_name: str = "Ghost Supply Mission",
    callsign: str = "CONVOY-1",
) -> str:
    """
    Export route to Cursor-on-Target XML format.

    Args:
        route: RouteResult to export
        output_path: Output file path (.cot or .xml)
        mission_name: Mission name
        callsign: Convoy callsign

    Returns:
        Path to exported file
    """
    logger.info(f"Exporting route to CoT: {output_path}")

    root = ET.Element("events")

    convoy_uid = f"{COT_UID_PREFIX}-{callsign}"

    now = datetime.utcnow()
    start_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_time = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    convoy_event = ET.SubElement(root, "event")
    convoy_event.set("version", COT_VERSION)
    convoy_event.set("uid", convoy_uid)
    convoy_event.set("type", COT_TYPE_CONVOY)
    convoy_event.set("time", start_time)
    convoy_event.set("start", start_time)
    convoy_event.set("stale", stale_time)
    convoy_event.set("how", "h-e")

    if route.path:
        start_lat, start_lon = route.path[0]
        point = ET.SubElement(convoy_event, "point")
        point.set("lat", f"{start_lat:.6f}")
        point.set("lon", f"{start_lon:.6f}")
        point.set("hae", "0.0")
        point.set("ce", "10.0")
        point.set("le", "10.0")

    detail = ET.SubElement(convoy_event, "detail")

    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", callsign)

    remarks = ET.SubElement(detail, "remarks")
    remarks.text = (
        f"{mission_name}\n"
        f"Distance: {route.distance_km:.1f} km\n"
        f"ETA: {route.time_minutes:.0f} minutes\n"
        f"Risk (CVaR 95%): {route.cvar_95:.3f}\n"
        f"Method: {route.method}"
    )

    for i, waypoint in enumerate(route.waypoints):
        wp_event = _create_waypoint_event(waypoint, i, convoy_uid, now)
        root.append(wp_event)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    logger.info(f"Exported CoT to {output_path}")

    return str(output_path)


def _create_waypoint_event(
    waypoint: Waypoint,
    index: int,
    convoy_uid: str,
    base_time: datetime
) -> ET.Element:
    """
    Create CoT event for waypoint.

    Args:
        waypoint: Waypoint object
        index: Waypoint index
        convoy_uid: Parent convoy UID
        base_time: Base timestamp

    Returns:
        XML Element
    """
    wp_uid = f"{convoy_uid}-WP{index}"

    eta = base_time + timedelta(hours=waypoint.eta_hours)
    start_time = eta.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_time = (eta + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    event = ET.Element("event")
    event.set("version", COT_VERSION)
    event.set("uid", wp_uid)
    event.set("type", COT_TYPE_WAYPOINT)
    event.set("time", start_time)
    event.set("start", start_time)
    event.set("stale", stale_time)
    event.set("how", "h-e")

    point = ET.SubElement(event, "point")
    point.set("lat", f"{waypoint.latitude:.6f}")
    point.set("lon", f"{waypoint.longitude:.6f}")
    point.set("hae", "0.0")
    point.set("ce", "10.0")
    point.set("le", "10.0")

    detail = ET.SubElement(event, "detail")

    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", waypoint.name)

    remarks_text = f"ETA: +{waypoint.eta_hours:.1f}h"
    if waypoint.instructions:
        remarks_text += f"\n{waypoint.instructions}"
    if waypoint.risk_level > 0:
        remarks_text += f"\nRisk: {waypoint.risk_level:.3f}"

    remarks = ET.SubElement(detail, "remarks")
    remarks.text = remarks_text

    link = ET.SubElement(detail, "link")
    link.set("uid", convoy_uid)
    link.set("relation", "p-p")
    link.set("type", COT_TYPE_CONVOY)

    return event


def export_kill_zones_cot(
    kill_zones: List[dict],
    output_path: str
) -> str:
    """
    Export kill zones as CoT threat markers.

    Args:
        kill_zones: List of kill zone dicts
        output_path: Output file path

    Returns:
        Path to exported file
    """
    logger.info(f"Exporting {len(kill_zones)} kill zones to CoT")

    root = ET.Element("events")

    now = datetime.utcnow()
    start_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_time = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for kz in kill_zones:
        kz_uid = f"{COT_UID_PREFIX}-THREAT-{kz['id']}"

        event = ET.SubElement(root, "event")
        event.set("version", COT_VERSION)
        event.set("uid", kz_uid)
        event.set("type", COT_TYPE_THREAT)
        event.set("time", start_time)
        event.set("start", start_time)
        event.set("stale", stale_time)
        event.set("how", "h-e")

        center_lat, center_lon = kz["center"]

        point = ET.SubElement(event, "point")
        point.set("lat", f"{center_lat:.6f}")
        point.set("lon", f"{center_lon:.6f}")
        point.set("hae", "0.0")
        point.set("ce", f"{kz['radius_km'] * 1000:.0f}")
        point.set("le", "999999.0")

        detail = ET.SubElement(event, "detail")

        contact = ET.SubElement(detail, "contact")
        contact.set("callsign", f"KILLZONE-{kz['id']}")

        remarks = ET.SubElement(detail, "remarks")
        remarks.text = (
            f"Kill Zone {kz['id']}\n"
            f"Incidents: {kz['num_incidents']}\n"
            f"Radius: {kz['radius_km']:.1f} km\n"
            f"Avg casualties: {kz.get('avg_casualties', 0):.1f}"
        )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    logger.info(f"Exported kill zones to {output_path}")

    return str(output_path)


def export_mission_package(
    route: RouteResult,
    alternate_route: Optional[RouteResult],
    kill_zones: List[dict],
    output_zip: str,
    mission_name: str = "Ghost Supply",
) -> str:
    """
    Export complete mission package as ZIP.

    Args:
        route: Primary route
        alternate_route: Alternate/fallback route
        kill_zones: Kill zones
        output_zip: Output ZIP path
        mission_name: Mission name

    Returns:
        Path to ZIP file
    """
    logger.info(f"Creating mission package: {output_zip}")

    output_path = Path(output_zip)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_path.parent / "temp_mission"
    temp_dir.mkdir(exist_ok=True)

    primary_cot = temp_dir / "primary_route.cot"
    export_to_cot(route, str(primary_cot), mission_name, "PRIMARY")

    if alternate_route:
        alternate_cot = temp_dir / "alternate_route.cot"
        export_to_cot(alternate_route, str(alternate_cot), f"{mission_name} (Alternate)", "ALTERNATE")

    if kill_zones:
        threats_cot = temp_dir / "threat_zones.cot"
        export_kill_zones_cot(kill_zones, str(threats_cot))

    briefing = temp_dir / "BRIEFING.txt"
    with open(briefing, "w") as f:
        f.write(f"{mission_name.upper()} - MISSION BRIEFING\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Primary Route:\n")
        f.write(f"  Distance: {route.distance_km:.1f} km\n")
        f.write(f"  Duration: {route.time_minutes:.0f} minutes\n")
        f.write(f"  Risk (CVaR 95%): {route.cvar_95:.3f}\n")
        f.write(f"  Waypoints: {len(route.waypoints)}\n\n")

        if alternate_route:
            f.write(f"Alternate Route:\n")
            f.write(f"  Distance: {alternate_route.distance_km:.1f} km\n")
            f.write(f"  Duration: {alternate_route.time_minutes:.0f} minutes\n\n")

        f.write(f"Threat Assessment:\n")
        f.write(f"  Kill zones identified: {len(kill_zones)}\n\n")

        f.write("EXECUTE WITH CAUTION. STAY ALERT.\n")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in temp_dir.glob("*"):
            zf.write(file, file.name)

    import shutil
    shutil.rmtree(temp_dir)

    logger.info(f"Mission package created: {output_path}")

    return str(output_path)
