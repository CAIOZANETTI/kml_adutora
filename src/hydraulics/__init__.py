"""NumPy-first hydraulic core."""

from .core import (
    calc_area,
    calc_velocidade,
    calc_reynolds,
    calc_fator_atrito,
    calc_perda_darcy,
    calc_perda_localizada,
    calc_hf_acumulada,
    calc_hgl,
    calc_pressao_mca,
    run_hydraulic_scenarios,
)

__all__ = [
    "calc_area",
    "calc_velocidade",
    "calc_reynolds",
    "calc_fator_atrito",
    "calc_perda_darcy",
    "calc_perda_localizada",
    "calc_hf_acumulada",
    "calc_hgl",
    "calc_pressao_mca",
    "run_hydraulic_scenarios",
]
