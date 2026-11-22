from PyQt6.QtGui import QImage, QPixmap, QPainter
from PyQt6.QtCore import Qt, QRect, QRectF
from core.i18n import t


class Layer:
    """Representa una capa individual con su propia imagen y estado."""
    def __init__(self, name, width, height, transparent=True, image=None):
        self.name = name
        self.visible = True
        self.locked = False
        self.opacity = 1.0
        self.transparent = transparent
        if image is not None and not image.isNull():
            # Copy-on-Write nativo de Qt6: comparte datos hasta que se modifique
            self.image = QImage(image)
        else:
            self.image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            if transparent:
                self.image.fill(Qt.GlobalColor.transparent)
            else:
                self.image.fill(Qt.GlobalColor.white)


class LayerManager:
    """Maneja el sistema de múltiples capas y su composición visual."""
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.active_stroke_alpha = 1.0

        nombre_inicial = t("Capa %1").replace("%1", "1")
        capa_base = Layer(nombre_inicial, width, height, transparent=True)
        self.capas = [capa_base]
        self._indice_activo = 0

        # Estado de cache de composicion por bloques (below/above) y dirty-rect
        self._cached_pixmap = None
        self._cached_pixmap_img_id = None
        self._cached_below_active = None
        self._cached_above_active = None
        self._cached_below_sig = None
        self._cached_above_sig = None
        self._cached_active_sig = None
        self._cached_temp_sig = None
        self._composite_buffer = None
        self._preview_buffer = None
        self._composite_valid = False
        self._pending_dirty_rect = None

    @property
    def indice_activo(self):
        return getattr(self, '_indice_activo', 0)

    @indice_activo.setter
    def indice_activo(self, val):
        if getattr(self, '_indice_activo', None) == val:
            return
        self._indice_activo = val
        self.invalidate_cache()

    def get_active_layer(self):
        idx = self.indice_activo
        if 0 <= idx < len(self.capas):
            return self.capas[idx]
        return None

    @property
    def buffer(self):
        return self.capas[self.indice_activo].image

    @buffer.setter
    def buffer(self, nueva_imagen):
        self.capas[self.indice_activo].image = nueva_imagen
        self.invalidate_active_layer_region()

    def preparar_para_modificacion(self):
        """
        Prepara la capa activa para modificacion manteniendo Copy-On-Write perezoso.
        En Qt6, cualquier escritura via QPainter/fill/bits() sobre una QImage compartida
        ejecuta QImage::detach() automaticamente, evitando copias profundas innecesarias en mouse_press.
        """
        active = self.get_active_layer()
        if active and active.image is not None:
            active.image = QImage(active.image)

    def agregar_capa(self, nombre="Nueva Capa"):
        nueva_capa = Layer(nombre, self.width, self.height, transparent=True)
        idx = max(0, self.indice_activo)
        self.capas.insert(idx, nueva_capa)
        self._indice_activo = idx
        self.invalidate_cache()

    def combinar_capas_indices(self, indices):
        """
        Combina los índices de capas seleccionadas.
        Mantiene el nombre de la capa ubicada más arriba (menor índice en lista visual).
        """
        if not indices or len(indices) < 2:
            return

        indices_ordenados = sorted(indices)
        top_idx = indices_ordenados[0]
        nombre_final = self.capas[top_idx].name

        capa_combinada = Layer(nombre_final, self.width, self.height, transparent=True)
        painter = QPainter(capa_combinada.image)

        for idx in reversed(indices_ordenados):
            capa = self.capas[idx]
            op = getattr(capa, 'opacity', 1.0)
            painter.setOpacity(op)
            painter.drawImage(0, 0, capa.image)
        painter.end()

        min_idx = indices_ordenados[0]
        self.capas[min_idx] = capa_combinada

        for idx in reversed(indices_ordenados[1:]):
            self.capas.pop(idx)

        self._indice_activo = min_idx
        self.invalidate_cache()

    def _notify_cache_invalidated(self):
        if hasattr(self, 'on_cache_invalidated') and callable(self.on_cache_invalidated):
            try:
                self.on_cache_invalidated()
            except Exception:
                pass

    def invalidate_cache(self):
        """Invalida completamente la cache de bloques, composicion y pixmap."""
        self._cached_pixmap = None
        self._cached_pixmap_img_id = None
        self._cached_below_active = None
        self._cached_above_active = None
        self._cached_below_sig = None
        self._cached_above_sig = None
        self._cached_active_sig = None
        self._cached_temp_sig = None
        self._composite_valid = False
        self._pending_dirty_rect = None
        self._notify_cache_invalidated()

    def invalidate_active_layer_region(self, dirty_rect=None):
        """
        Invalida unicamente la capa activa (o una sub-region dirty_rect en coordenadas de documento),
        preservando las caches de capas por debajo y por encima para trazos fluidos.
        """
        self._cached_pixmap = None
        self._cached_pixmap_img_id = None

        if dirty_rect is not None and self._composite_valid:
            r = dirty_rect.toAlignedRect() if isinstance(dirty_rect, QRectF) else QRect(dirty_rect)
            r = r.intersected(QRect(0, 0, self.width, self.height))
            if not r.isEmpty():
                if self._pending_dirty_rect is None:
                    self._pending_dirty_rect = r
                else:
                    self._pending_dirty_rect = self._pending_dirty_rect.united(r)
        else:
            self._composite_valid = False
            self._pending_dirty_rect = None

        self._notify_cache_invalidated()

    def _ensure_buffer(self, attr_name: str) -> QImage:
        buf = getattr(self, attr_name, None)
        if buf is None or buf.width() != self.width or buf.height() != self.height:
            buf = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
            buf.fill(Qt.GlobalColor.transparent)
            setattr(self, attr_name, buf)
            if attr_name == '_composite_buffer':
                self._composite_valid = False
        return buf

    def _rebuild_stack_slice(self, start_idx: int, end_idx: int) -> QImage:
        """Compone las capas visibles en el rango [start_idx, end_idx) (de abajo hacia arriba)."""
        img = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        for idx in range(end_idx - 1, start_idx - 1, -1):
            capa = self.capas[idx]
            if capa.visible:
                p.setOpacity(float(getattr(capa, 'opacity', 1.0)))
                p.drawImage(0, 0, capa.image)
        p.end()
        return img

    def _compose_region(
        self,
        target_img: QImage,
        rect: QRect,
        active_layer,
        capa_trazo_temp=None,
        draw_layer_preview_callback=None,
        selection_path=None,
    ):
        """Compone el rectangulo indicado combinando below + capa activa (+ trazo/preview) + above."""
        if rect.isEmpty():
            return

        p = QPainter(target_img)
        p.setClipRect(rect)

        # 1. Base: capas estrictamente por debajo de la capa activa
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        if self._cached_below_active is not None:
            p.drawImage(rect, self._cached_below_active, rect)
        else:
            p.fillRect(rect, Qt.GlobalColor.transparent)

        # 2. Capa activa + trazo temporal + preview interactivo
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if active_layer is not None and active_layer.visible:
            op = float(getattr(active_layer, 'opacity', 1.0))
            p.setOpacity(op)
            p.drawImage(rect, active_layer.image, rect)

            if capa_trazo_temp is not None and not capa_trazo_temp.isNull():
                p.save()
                if selection_path is not None and not selection_path.isEmpty():
                    p.setClipPath(selection_path, Qt.ClipOperation.IntersectClip)
                alpha_trazo = float(getattr(self, 'active_stroke_alpha', 1.0))
                p.setOpacity(op * alpha_trazo)
                p.drawImage(rect, capa_trazo_temp, rect)
                p.restore()

            if draw_layer_preview_callback is not None:
                p.save()
                p.setOpacity(op)
                draw_layer_preview_callback(p)
                p.restore()

        # 3. Capas estrictamente por encima de la capa activa
        if self._cached_above_active is not None:
            p.setOpacity(1.0)
            p.drawImage(rect, self._cached_above_active, rect)

        p.end()

    def get_qimage(self, capa_trazo_temp=None, draw_layer_preview_callback=None, selection_path=None):
        has_temp_stroke = bool(capa_trazo_temp is not None and not capa_trazo_temp.isNull())
        has_preview_callback = bool(draw_layer_preview_callback is not None)

        if not self.capas:
            empty = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
            empty.fill(Qt.GlobalColor.transparent)
            return empty

        idx_activo = max(0, min(self.indice_activo, len(self.capas) - 1))
        active = self.capas[idx_activo]

        # Firmas ligeras (O(num_capas)) para detectar cambios estructurales o de pixeles de forma infalible
        below_sig = tuple(
            (id(c), float(getattr(c, 'opacity', 1.0)), c.image.cacheKey())
            for i in range(idx_activo + 1, len(self.capas))
            for c in (self.capas[i],)
            if c.visible
        )
        above_sig = tuple(
            (id(c), float(getattr(c, 'opacity', 1.0)), c.image.cacheKey())
            for i in range(0, idx_activo)
            for c in (self.capas[i],)
            if c.visible
        )
        active_sig = (id(active), bool(active.visible), float(getattr(active, 'opacity', 1.0)), active.image.cacheKey())
        if has_temp_stroke:
            sel_sig = selection_path.boundingRect().getRect() if (selection_path is not None and not selection_path.isEmpty()) else None
            temp_sig = (capa_trazo_temp.cacheKey(), float(getattr(self, 'active_stroke_alpha', 1.0)), sel_sig)
        else:
            temp_sig = None

        # Fast-path: solo la capa activa es visible con opacidad 1.0, sin trazo temporal ni preview
        if (
            not below_sig
            and not above_sig
            and active.visible
            and active_sig[2] >= 0.9999
            and not has_temp_stroke
            and not has_preview_callback
        ):
            return active.image

        # Actualizar caches below/above solo cuando cambian sus capas
        if (
            below_sig != self._cached_below_sig
            or (below_sig and (self._cached_below_active is None or self._cached_below_active.width() != self.width or self._cached_below_active.height() != self.height))
        ):
            self._cached_below_active = self._rebuild_stack_slice(idx_activo + 1, len(self.capas)) if below_sig else None
            self._cached_below_sig = below_sig
            self._composite_valid = False

        if (
            above_sig != self._cached_above_sig
            or (above_sig and (self._cached_above_active is None or self._cached_above_active.width() != self.width or self._cached_above_active.height() != self.height))
        ):
            self._cached_above_active = self._rebuild_stack_slice(0, idx_activo) if above_sig else None
            self._cached_above_sig = above_sig
            self._composite_valid = False

        from core.perf_monitor import perf_monitor
        full_rect = QRect(0, 0, self.width, self.height)

        # Camino interactivo con preview (flotante, formas, linea, texto, transformacion): no ensucia _composite_buffer
        if has_preview_callback:
            preview_buf = self._ensure_buffer('_preview_buffer')
            self._compose_region(
                preview_buf,
                full_rect,
                active,
                capa_trazo_temp=capa_trazo_temp if has_temp_stroke else None,
                draw_layer_preview_callback=draw_layer_preview_callback,
                selection_path=selection_path,
            )
            perf_monitor.record_composite(partial=False)
            return preview_buf

        # Camino principal / trazos continuos con buffer persistente y actualizacion parcial dirty-rect
        comp_buf = self._ensure_buffer('_composite_buffer')

        active_changed = (active_sig != self._cached_active_sig) or (temp_sig != self._cached_temp_sig)
        if not self._composite_valid:
            self._compose_region(
                comp_buf,
                full_rect,
                active,
                capa_trazo_temp=capa_trazo_temp if has_temp_stroke else None,
                selection_path=selection_path,
            )
            self._composite_valid = True
            self._pending_dirty_rect = None
            self._cached_active_sig = active_sig
            self._cached_temp_sig = temp_sig
            perf_monitor.record_composite(partial=False)
        elif active_changed or self._pending_dirty_rect is not None:
            can_partial = (
                self._pending_dirty_rect is not None
                and not self._pending_dirty_rect.isEmpty()
                and self._cached_active_sig is not None
                and active_sig[:3] == self._cached_active_sig[:3]
                and (temp_sig is None) == (self._cached_temp_sig is None)
                and (
                    temp_sig is None
                    or (temp_sig[1] == self._cached_temp_sig[1] and temp_sig[2] == self._cached_temp_sig[2])
                )
            )
            if can_partial:
                self._compose_region(
                    comp_buf,
                    self._pending_dirty_rect,
                    active,
                    capa_trazo_temp=capa_trazo_temp if has_temp_stroke else None,
                    selection_path=selection_path,
                )
                perf_monitor.record_composite(partial=True)
            else:
                self._compose_region(
                    comp_buf,
                    full_rect,
                    active,
                    capa_trazo_temp=capa_trazo_temp if has_temp_stroke else None,
                    selection_path=selection_path,
                )
                perf_monitor.record_composite(partial=False)

            self._pending_dirty_rect = None
            self._cached_active_sig = active_sig
            self._cached_temp_sig = temp_sig

        return comp_buf

    def get_qpixmap(self, capa_trazo_temp=None, draw_layer_preview_callback=None, selection_path=None):
        img = self.get_qimage(
            capa_trazo_temp=capa_trazo_temp,
            draw_layer_preview_callback=draw_layer_preview_callback,
            selection_path=selection_path,
        )
        has_transient = bool(capa_trazo_temp or draw_layer_preview_callback)
        img_key = img.cacheKey() if hasattr(img, 'cacheKey') else id(img)
        if not has_transient and getattr(self, '_cached_pixmap', None) is not None and getattr(self, '_cached_pixmap_img_id', None) == img_key:
            return self._cached_pixmap

        pixmap = QPixmap.fromImage(img)
        if not has_transient:
            self._cached_pixmap = pixmap
            self._cached_pixmap_img_id = img_key
        return pixmap

    def resize_canvas(self, new_width, new_height):
        for capa in self.capas:
            nuevo_buffer = QImage(new_width, new_height, QImage.Format.Format_ARGB32_Premultiplied)
            nuevo_buffer.fill(Qt.GlobalColor.transparent)

            painter = QPainter(nuevo_buffer)
            painter.drawImage(0, 0, capa.image)
            painter.end()

            capa.image = nuevo_buffer

        self.width = new_width
        self.height = new_height
        self.invalidate_cache()

