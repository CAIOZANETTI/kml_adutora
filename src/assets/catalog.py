"""Catalog loading utilities backed by curated JSON assets."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

CATALOG_PATH = Path(__file__).with_name("pipe_catalog.json")
REFERENCE_LIBRARY_PATH = Path(__file__).with_name("reference_documents.json")


@lru_cache(maxsize=1)
def load_reference_library() -> pd.DataFrame:
    payload = json.loads(REFERENCE_LIBRARY_PATH.read_text())
    references = pd.DataFrame(payload["references"])
    return references.sort_values(["category", "reference_id"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def load_reference_library_payload() -> dict:
    return json.loads(REFERENCE_LIBRARY_PATH.read_text())


@lru_cache(maxsize=1)
def load_pipe_catalog() -> pd.DataFrame:
    payload = load_pipe_catalog_payload()
    catalog = pd.DataFrame(payload["items"])
    numeric_cols = [
        "dn_mm",
        "pressure_class_bar",
        "inner_diameter_m",
        "roughness_mm",
        "wave_speed_m_s",
        "cost_brl_per_m",
        "wall_thickness_mm",
    ]
    for column in numeric_cols:
        catalog[column] = pd.to_numeric(catalog[column], errors="coerce")

    reference_df = load_reference_library()
    title_map = dict(zip(reference_df["reference_id"], reference_df["title"]))

    def _join_reference_titles(values):
        if not values:
            return ""
        return " / ".join(title_map.get(value, value) for value in values)

    def _join_reference_ids(values):
        if not values:
            return ""
        return " | ".join(values)

    catalog["spec_reference_ids"] = catalog["references"].map(lambda payload: _join_reference_ids((payload or {}).get("spec", [])))
    catalog["cost_reference_ids"] = catalog["references"].map(lambda payload: _join_reference_ids((payload or {}).get("cost", [])))
    catalog["spec_source"] = catalog["references"].map(lambda payload: _join_reference_titles((payload or {}).get("spec", [])))
    catalog["cost_source"] = catalog["references"].map(lambda payload: _join_reference_titles((payload or {}).get("cost", [])))
    catalog["scenario_label"] = (
        catalog["material"]
        + " | DN "
        + catalog["dn_mm"].astype(int).astype(str)
        + " | "
        + catalog["series_label"]
    )
    catalog["catalog_group"] = catalog["manufacturer"] + " - " + catalog["product_line"]
    return catalog.sort_values(["material", "dn_mm", "pressure_class_bar"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def load_pipe_catalog_payload() -> dict:
    return json.loads(CATALOG_PATH.read_text())


def filter_catalog(catalog: pd.DataFrame, enabled_materials: Iterable[str]) -> pd.DataFrame:
    enabled_materials = list(enabled_materials or [])
    if not enabled_materials:
        return catalog.copy()
    return catalog[catalog["material"].isin(enabled_materials)].reset_index(drop=True)
