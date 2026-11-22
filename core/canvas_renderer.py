"""
core/canvas_renderer.py — Motor de composición gráfica y dibujo para el lienzo de pyDCE.
"""
import math
from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt
from PyQt6.QtGui import QPainter, QImage, QPen, QColor, QBrush, QPixmap


class CanvasRenderer:
    """Encapsula las rutinas de composición gráfica, fondo de ajedrez y renderizado multicapa."""

    def __init__(self, canvas):
        self.canvas = canvas
        self._checker_cache_key = None
        self._checker_brush = None

        self._grid_pen_dark = QPen(QColor(0, 0, 0, 100), 0, Qt.PenStyle.SolidLine)
        self._grid_pen_dark.setCosmetic(True)
        self._grid_pen_light = QPen(QColor(255, 255, 255, 140), 0, Qt.PenStyle.DotLine)
        self._grid_pen_light.setCosmetic(True)

    def invalidate_checkerboard_cache(self):
        """Invalida el pincel cacheado del patron de ajedrez (por ejemplo, al cambiar el tema)."""
        self._checker_cache_key = None
        self._checker_brush = None

    def _get_checkerboard_brush(self, tile_size: int = 12) -> QBrush:
        """Devuelve un QBrush con textura nativa 2x2 cacheada segun el tema activo y tile_size."""
        from core.theme import ThemeManager
        c1, c2 = ThemeManager().colores_checkerboard()
        key = (c1.rgba(), c2.rgba(), tile_size)
        if self._checker_cache_key == key and self._checker_brush is not None:
            return self._checker_brush

        pattern_size = tile_size * 2
        tile_pm = QPixmap(pattern_size, pattern_size)
        tile_pm.fill(c1)
        tp = QPainter(tile_pm)
        tp.fillRect(tile_size, 0, tile_size, tile_size, c2)
        tp.fillRect(0, tile_size, tile_size, tile_size, c2)
        tp.end()

        self._checker_brush = QBrush(tile_pm)
        self._checker_cache_key = key
        return self._checker_brush

    def draw_checkerboard_pattern(self, painter: QPainter, rect_w: int, rect_h: int, tile_size: int = 12, visible_rect: QRectF = None):
        """Dibuja el fondo de tablero de ajedrez representativo de transparencia usando un QBrush cacheado."""
        full_rect = QRectF(0.0, 0.0, float(rect_w), float(rect_h))
        if visible_rect is not None:
            target = full_rect.intersected(QRectF(visible_rect))
        elif painter.hasClipping():
            target = full_rect.intersected(painter.clipBoundingRect())
        else:
            target = full_rect

        if target.isEmpty():
            return

        brush = self._get_checkerboard_brush(tile_size)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.fillRect(target, brush)
        painter.restore()

    def draw_pixel_grid(self, painter: QPainter, width: int, height: int, scale_factor: float, visible_rect: QRectF = None):
        """Dibuja una rejilla fina de píxeles recortada a la zona visible cuando el zoom es >= 200%."""
        if scale_factor < 2.0 or width <= 1 or height <= 1:
            return

        full_rect = QRectF(0.0, 0.0, float(width), float(height))
        if visible_rect is not None:
            target = full_rect.intersected(QRectF(visible_rect))
        elif painter.hasClipping():
            target = full_rect.intersected(painter.clipBoundingRect())
        else:
            target = full_rect

        if target.isEmpty():
            return

        x_min_f = max(0.0, float(math.floor(target.left())))
        y_min_f = max(0.0, float(math.floor(target.top())))
        x_max_f = min(float(width), float(math.ceil(target.right())))
        y_max_f = min(float(height), float(math.ceil(target.bottom())))

        x_start = max(1, int(math.ceil(x_min_f)))
        x_end = min(width, int(math.floor(x_max_f)) + 1)
        y_start = max(1, int(math.ceil(y_min_f)))
        y_end = min(height, int(math.floor(y_max_f)) + 1)

        if x_start >= x_end and y_start >= y_end:
            return

        lines = [QLineF(float(x), y_min_f, float(x), y_max_f) for x in range(x_start, x_end)]
        lines.extend(QLineF(x_min_f, float(y), x_max_f, float(y)) for y in range(y_start, y_end))

        if not lines:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(self._grid_pen_dark)
        painter.drawLines(lines)
        painter.setPen(self._grid_pen_light)
        painter.drawLines(lines)
        painter.restore()

    def render_layers_composite(self, layer_mgr, selection_engine, capa_trazo_temp=None) -> QImage:
        """Compone todas las capas del documento en una QImage final respetando opacidades y selección flotante."""
        w, h = layer_mgr.width, layer_mgr.height
        comp = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        comp.fill(Qt.GlobalColor.transparent)

        p = QPainter(comp)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        has_floating = bool(selection_engine and selection_engine.floating_image and not selection_engine.floating_image.isNull())

        for i, capa in enumerate(reversed(layer_mgr.capas)):
            if not getattr(capa, 'visible', True):
                continue

            idx_real = len(layer_mgr.capas) - 1 - i
            op = float(getattr(capa, 'opacity', 1.0))
            p.setOpacity(op)

            # Dibujar la imagen de la capa
            p.drawImage(0, 0, capa.image)

            # Si es la capa activa y hay trazo temporal de pincel activo
            if idx_real == layer_mgr.indice_activo and capa_trazo_temp and not capa_trazo_temp.isNull():
                stroke_alpha = float(getattr(layer_mgr, 'active_stroke_alpha', 1.0))
                p.setOpacity(op * stroke_alpha)
                p.drawImage(0, 0, capa_trazo_temp)
                p.setOpacity(op)

            # Si es la capa activa y hay selección flotante en movimiento
            if has_floating and idx_real == layer_mgr.indice_activo:
                p.drawImage(selection_engine.original_image_pos, selection_engine.floating_image)

        p.end()
        return comp
