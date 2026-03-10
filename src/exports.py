"""Export helpers for tabular app outputs."""

from __future__ import annotations

import io

import pandas as pd


def to_excel_bytes(
    detail_df: pd.DataFrame,
    alternatives_df: pd.DataFrame,
    devices_df: pd.DataFrame,
    materials_df: pd.DataFrame,
    critical_points_df: pd.DataFrame,
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="Perfil", index=False)
        alternatives_df.to_excel(writer, sheet_name="Alternativas", index=False)
        devices_df.to_excel(writer, sheet_name="Dispositivos", index=False)
        materials_df.to_excel(writer, sheet_name="Materiais", index=False)
        critical_points_df.to_excel(writer, sheet_name="PontosCriticos", index=False)

        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"
            for column in sheet.columns:
                width = max(len(str(cell.value or "")) for cell in column)
                sheet.column_dimensions[column[0].column_letter].width = min(width + 3, 32)

    buffer.seek(0)
    return buffer.read()


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
