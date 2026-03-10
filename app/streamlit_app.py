"""Entry point for the staged Gradiente Hidraulico Streamlit app."""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from page_views import (
    render_catalogo,
    render_cenarios,
    render_diagnostico,
    render_regime_permanente,
    render_solucao_final,
    render_tracado,
    render_transientes,
)
from ui_shared import apply_styles, init_state, render_sidebar

st.set_page_config(page_title="Gradiente Hidraulico", page_icon="GH", layout="wide", initial_sidebar_state="expanded")
apply_styles()
init_state()


def _wrap(stage_name: str, render_fn):
    def _runner():
        render_sidebar(stage_name)
        render_fn()
    return _runner


PAGES = [
    ("Tracado", "tracado", _wrap("Tracado", render_tracado)),
    ("Diagnostico", "diagnostico", _wrap("Diagnostico", render_diagnostico)),
    ("Regime permanente", "regime-permanente", _wrap("Regime permanente", render_regime_permanente)),
    ("Transientes e protecao", "transientes-protecao", _wrap("Transientes e protecao", render_transientes)),
    ("Cenarios de tubulacao", "cenarios-tubulacao", _wrap("Cenarios de tubulacao", render_cenarios)),
    ("Solucao final", "solucao-final", _wrap("Solucao final", render_solucao_final)),
]

REFERENCE_PAGES = [
    ("Catalogo e referencias", "catalogo-json", _wrap("Catalogo e referencias", render_catalogo)),
]

if hasattr(st, "Page") and hasattr(st, "navigation"):
    all_pages = [st.Page(render_fn, title=title, url_path=url_path) for title, url_path, render_fn in PAGES]
    all_pages += [st.Page(render_fn, title=title, url_path=url_path) for title, url_path, render_fn in REFERENCE_PAGES]
    try:
        navigator = st.navigation(all_pages, position="sidebar")
    except TypeError:
        navigator = st.navigation(all_pages)
    navigator.run()
else:
    all_nav = PAGES + REFERENCE_PAGES
    selected = st.sidebar.radio("Etapas", [title for title, _, _ in all_nav], index=0)
    page_map = {title: render_fn for title, _, render_fn in all_nav}
    page_map[selected]()
