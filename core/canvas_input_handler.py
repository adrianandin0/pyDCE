"""
core/canvas_input_handler.py — Manejador de eventos de entrada y despacho de herramientas del lienzo.
"""
import math
from PyQt6.QtCore import QObject, QPoint, QPointF, QRect, Qt, QEvent
from PyQt6.QtGui import QMouseEvent, QCursor, QPixmap, QPainter, QPen, QColor


class CanvasInputHandler(QObject):
    """Manejador especializado de eventos de entrada del usuario (ratón, cursor y navegación)."""

    _BRUSH_OVERLAY_TOOLS = (
        'BrushTool', 'PencilTool', 'EraserTool', 'SprayTool', 'SmudgeTool', 'StampTool'
    )

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._last_cursor_overlay_rect: QRect | None = None

    def reset_cursor_overlay_rect(self):
        self._last_cursor_overlay_rect = None

    def _compute_cursor_overlay_rect(self) -> QRect | None:
        """
        Calcula el rectangulo en coordenadas de widget ocupado por el anillo/preview
        del cursor de la herramienta activa, o None si la herramienta no dibuja cursor en hover.
        """
        tool = getattr(self.canvas, 'active_tool_obj', None)
        pos_doc = getattr(self.canvas, 'cursor_pos', None)
        if tool is None or pos_doc is None:
            return None

        tool_cls = tool.__class__.__name__
        off_x, off_y = self.canvas.obtener_offset_canvas()
        sf = self.canvas.scale_factor if self.canvas.scale_factor > 0 else 1.0

        if tool_cls in self._BRUSH_OVERLAY_TOOLS or (tool_cls == 'LineTool' and getattr(tool, 'state', 0) == 0):
            wx = float(off_x) + (float(math.floor(pos_doc.x())) + 0.5) * sf
            wy = float(off_y) + (float(math.floor(pos_doc.y())) + 0.5) * sf
            w_doc = max(1.0, float(getattr(self.canvas, 'grosor_pincel', getattr(self.canvas, 'ancho_pincel', 5))))
            half_px = int(math.ceil((w_doc * 0.5 + 1.5) * sf)) + 8
            r = QRect(int(wx) - half_px, int(wy) - half_px, half_px * 2 + 2, half_px * 2 + 2)
            # Incluir tambien widget_cursor_pos en caso de LineTool (bloque 5 centrado en puntero exacto)
            wpos = getattr(self.canvas, 'widget_cursor_pos', None)
            if wpos is not None:
                r2 = QRect(int(wpos.x()) - half_px, int(wpos.y()) - half_px, half_px * 2 + 2, half_px * 2 + 2)
                r = r.united(r2)
            return r

        if tool_cls == 'EyedropperTool':
            wx = float(off_x) + (float(math.floor(pos_doc.x())) + 0.5) * sf
            wy = float(off_y) + (float(math.floor(pos_doc.y())) + 0.5) * sf
            half_px = 20
            return QRect(int(wx) - half_px, int(wy) - half_px, half_px * 2 + 2, half_px * 2 + 2)

        return None

    def map_canvas_event(self, event) -> QMouseEvent:
        """Traduce las coordenadas físicas del widget a coordenadas lógicas del lienzo (tomando en cuenta offset y zoom)."""
        off_x, off_y = self.canvas.obtener_offset_canvas()
        raw = event.position() - QPointF(float(off_x), float(off_y))
        sf = self.canvas.scale_factor if self.canvas.scale_factor > 0 else 1.0
        pos_mapped = QPointF(raw.x() / sf, raw.y() / sf)
        return QMouseEvent(
            event.type(),
            pos_mapped,
            event.button(),
            event.buttons(),
            event.modifiers()
        )

    def handle_leave_event(self, event):
        prev_overlay = self._last_cursor_overlay_rect
        self._last_cursor_overlay_rect = None
        self.canvas.cursor_pos = None
        self.canvas.widget_cursor_pos = None
        self.notify_cursor_position()
        if prev_overlay is not None and not prev_overlay.isEmpty():
            self.canvas.update(prev_overlay)

    def handle_mouse_press(self, event):
        self.canvas.setFocus()
        self.canvas.widget_cursor_pos = event.position()
        ev = self.map_canvas_event(event)
        self.canvas.cursor_pos = ev.position()
        self.notify_cursor_position()

        if hasattr(self.canvas.selection_engine, 'original_selection_region'):
            self.canvas.selection_engine.original_selection_region = None

        if ev.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.canvas.drawing = True
            color_activo = self.canvas.color_primario if ev.button() == Qt.MouseButton.LeftButton else self.canvas.color_secundario

            tool_name = self.canvas.active_tool_obj.__class__.__name__ if self.canvas.active_tool_obj else ""
            es_herramienta_lectura = tool_name in (
                'ZoomTool', 'EyedropperTool', 'SelectRectTool', 'SelectEllipseTool',
                'SelectFreeTool', 'MagicWandTool', 'MoveSelectOnlyTool'
            )

            if not es_herramienta_lectura and hasattr(self.canvas, 'layer_mgr') and hasattr(self.canvas.layer_mgr, 'preparar_para_modificacion'):
                self.canvas.layer_mgr.preparar_para_modificacion()

            tool = getattr(self.canvas, 'active_tool_obj', None)
            if tool and hasattr(tool, 'mouse_press'):
                try:
                    tool.mouse_press(self.canvas, ev, color_activo)
                except TypeError:
                    tool.mouse_press(self.canvas, ev)
            self._last_cursor_overlay_rect = self._compute_cursor_overlay_rect()
            if tool_name not in self._BRUSH_OVERLAY_TOOLS:
                self.canvas.update()

    def handle_mouse_move(self, event):
        from core.perf_monitor import perf_monitor
        _t0 = None
        if perf_monitor.enabled:
            import time
            _t0 = time.perf_counter()
        try:
            prev_overlay = self._last_cursor_overlay_rect
            self.canvas.widget_cursor_pos = event.position()
            ev = self.map_canvas_event(event)
            self.canvas.cursor_pos = ev.position()
            self.notify_cursor_position()
            color_activo = self.canvas.color_primario if (ev.buttons() & Qt.MouseButton.LeftButton) else self.canvas.color_secundario

            tool = getattr(self.canvas, 'active_tool_obj', None)
            if tool and hasattr(tool, 'mouse_move'):
                try:
                    tool.mouse_move(self.canvas, ev, color_activo)
                except TypeError:
                    tool.mouse_move(self.canvas, ev)

            curr_overlay = self._compute_cursor_overlay_rect()
            self._last_cursor_overlay_rect = curr_overlay

            if self.canvas.drawing:
                if self.canvas.callback_modificado:
                    self.canvas.callback_modificado()

                tool_cls = tool.__class__.__name__ if tool else ""
                if tool_cls in self._BRUSH_OVERLAY_TOOLS:
                    # La herramienta ya solicito actualizar_region_sucia para el trazo;
                    # actualizar tambien la union de las posiciones anterior y actual del anillo del cursor
                    cursor_dirty = None
                    if prev_overlay is not None and curr_overlay is not None:
                        cursor_dirty = prev_overlay.united(curr_overlay)
                    elif curr_overlay is not None:
                        cursor_dirty = curr_overlay
                    elif prev_overlay is not None:
                        cursor_dirty = prev_overlay
                    if cursor_dirty is not None and not cursor_dirty.isEmpty():
                        self.canvas.update(cursor_dirty)
                else:
                    self.canvas.update()
            else:
                # Hover sin clic: repintar solo el rectangulo del cursor overlay si la herramienta usa uno
                hover_dirty = None
                if prev_overlay is not None and curr_overlay is not None:
                    hover_dirty = prev_overlay.united(curr_overlay)
                elif curr_overlay is not None:
                    hover_dirty = curr_overlay
                elif prev_overlay is not None:
                    hover_dirty = prev_overlay

                if hover_dirty is not None and not hover_dirty.isEmpty():
                    self.canvas.update(hover_dirty)
        finally:
            if _t0 is not None:
                import time
                perf_monitor.record_mouse_move((time.perf_counter() - _t0) * 1000.0)

    def handle_mouse_release(self, event):
        ev = self.map_canvas_event(event)
        self.notify_cursor_position()
        if self.canvas.drawing:
            color_activo = self.canvas.color_primario if ev.button() == Qt.MouseButton.LeftButton else self.canvas.color_secundario

            tool = getattr(self.canvas, 'active_tool_obj', None)
            if tool and hasattr(tool, 'mouse_release'):
                try:
                    tool.mouse_release(self.canvas, ev, color_activo)
                except TypeError:
                    tool.mouse_release(self.canvas, ev)

            self.canvas.drawing = False
            tool_name = self.canvas.active_tool_obj.__class__.__name__ if self.canvas.active_tool_obj else ""
            tools_que_gestionan_su_historial = (
                'BucketTool', 'EyedropperTool', 'ZoomTool', 'TransformTool',
                'MoveSelectPixelsTool', 'MoveSelectOnlyTool', 'SelectRectTool',
                'SelectEllipseTool', 'SelectFreeTool', 'MagicWandTool', 'TextTool',
                'GradientTool', 'ShapesTool', 'LineTool'
            )
            if tool_name not in tools_que_gestionan_su_historial:
                self.canvas.push_document_state(getattr(self.canvas.active_tool_obj, 'name', "Trazo"))
        self.canvas.update()

    def notify_cursor_position(self):
        main_win = getattr(self.canvas, 'main_window', None)
        if main_win and hasattr(main_win, 'bottom_bar') and main_win.bottom_bar:
            pos = getattr(self.canvas, 'cursor_pos', None)
            if pos is not None and hasattr(self.canvas, 'layer_mgr') and self.canvas.layer_mgr:
                cx, cy = int(pos.x()), int(pos.y())
                if 0 <= cx <= self.canvas.layer_mgr.width and 0 <= cy <= self.canvas.layer_mgr.height:
                    main_win.bottom_bar.actualizar_posicion_cursor(cx, cy)
                    return
            main_win.bottom_bar.actualizar_posicion_cursor(None, None)
