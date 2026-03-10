"""Utilities for parsing KML alignments."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

_NS = [
    "{http://www.opengis.net/kml/2.2}",
    "{http://earth.google.com/kml/2.2}",
    "{http://earth.google.com/kml/2.1}",
    "",
]


def _find(element: ET.Element, tag: str) -> Optional[ET.Element]:
    for ns in _NS:
        found = element.find(f".//{ns}{tag}")
        if found is not None:
            return found
    return None


def _findall(element: ET.Element, tag: str) -> List[ET.Element]:
    for ns in _NS:
        found = element.findall(f".//{ns}{tag}")
        if found:
            return found
    return []


def _parse_coordinates(coord_text: str) -> List[Dict[str, Optional[float]]]:
    points: List[Dict[str, Optional[float]]] = []
    for token in coord_text.strip().split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
            z_kml_m = float(parts[2]) if len(parts) >= 3 and parts[2] != "" else None
        except ValueError:
            continue
        points.append({"lat": lat, "lon": lon, "z_kml_m": z_kml_m})
    return points


def _placemark_name(placemark: ET.Element, index: int) -> str:
    for ns in _NS:
        name_el = placemark.find(f"{ns}name")
        if name_el is not None and name_el.text:
            return name_el.text.strip()
    return f"alinhamento_{index + 1:02d}"


def parse_kml_file(file_content: bytes, file_name: str) -> List[Dict]:
    try:
        root = ET.fromstring(file_content)
    except ET.ParseError as exc:
        raise ValueError(f"Arquivo KML invalido '{file_name}': {exc}") from exc

    alignments: List[Dict] = []
    placemarks = _findall(root, "Placemark")
    ls_index = 0

    for placemark in placemarks:
        for line_string in _findall(placemark, "LineString"):
            coord_el = _find(line_string, "coordinates")
            if coord_el is None or not coord_el.text:
                continue
            points = _parse_coordinates(coord_el.text)
            if len(points) < 2:
                continue
            alignments.append(
                {
                    "file_name": file_name,
                    "alignment_id": _placemark_name(placemark, ls_index),
                    "points": points,
                }
            )
            ls_index += 1

    if not alignments:
        raise ValueError(f"Nenhuma geometria LineString valida foi encontrada em '{file_name}'.")

    return alignments


def parse_multiple_kml(files: List[Dict]) -> List[Dict]:
    all_alignments: List[Dict] = []
    for file_data in files:
        all_alignments.extend(parse_kml_file(file_data["content"], file_data["name"]))
    return all_alignments
