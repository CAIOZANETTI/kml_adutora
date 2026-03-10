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
    ("Tracado", _wrap("Tracado", render_tracado)),
    ("Diagnostico", _wrap("Diagnostico", render_diagnostico)),
    ("Regime permanente", _wrap("Regime permanente", render_regime_permanente)),
    ("Transientes e protecao", _wrap("Transientes e protecao", render_transientes)),
    ("Cenarios de tubulacao", _wrap("Cenarios de tubulacao", render_cenarios)),
    ("Solucao final", _wrap("Solucao final", render_solucao_final)),
    ("Catalogo JSON", _wrap("Catalogo JSON", render_catalogo)),
]

if hasattr(st, "Page") and hasattr(st, "navigation"):
    pages = [st.Page(render_fn, title=title) for title, render_fn in PAGES]
    try:
        navigator = st.navigation(pages, position="sidebar")
    except TypeError:
        navigator = st.navigation(pages)
    navigator.run()
else:
    selected = st.sidebar.radio("Etapas", [title for title, _ in PAGES], index=0)
    page_map = dict(PAGES)
    page_map[selected]()
