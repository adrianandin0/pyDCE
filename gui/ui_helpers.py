"""
gui/ui_helpers.py — Utilidades de dimensionamiento adaptativo para controles de interfaz (High-DPI y resoluciones bajas).
"""
from PyQt6.QtWidgets import QSizePolicy


def ajustar_tamano_spinbox(
    spin,
    sample_text: str = "9999",
    padding_x: int = 16,
    padding_y: int = 6,
    min_width: int = 38,
    min_height: int = 22,
    fijo: bool = False,
):
    """
    Configura el tamano minimo de un QSpinBox/QDoubleSpinBox usando QFontMetrics
    en lugar de dimensiones fijas, evitando texto recortado con escalado 125%-175% DPI.
    """
    fm = spin.fontMetrics()
    text_w = fm.horizontalAdvance(sample_text)
    calc_w = max(min_width, text_w + padding_x)
    calc_h = max(min_height, fm.height() + padding_y)
    if fijo:
        calc_h += 4  # holgura para borde QSS + descenso de fuente en Windows
        # En QToolBar (QWindows11Style + QSS) una politica Minimum/Expanding sin maximo
        # provoca campos colapsados o no clicables: se usa tamano fijo calculado por fuente.
        spin.setFixedSize(calc_w, calc_h)
        spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return
    spin.setMinimumWidth(calc_w)
    spin.setMinimumHeight(calc_h)
    spin.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)


def ajustar_altura_campo(widget, padding_y: int = 6, min_height: int = 22):
    """Configura una altura minima segura para campos de texto o combos segun QFontMetrics."""
    fm = widget.fontMetrics()
    calc_h = max(min_height, fm.height() + padding_y)
    widget.setMinimumHeight(calc_h)
