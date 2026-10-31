import sys
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction
from gui.dialogo_acerca import DialogoAcerca


class MenuAcerca:
    """Clase para construir el menú 'Ayuda' / 'Acerca de...' en la barra principal."""
    def __init__(self, main_window):
        self.main_window = main_window

    def crear_menu(self, menu_bar):
        self.menu_bar = menu_bar
        self.retraducir_menu()

    def retraducir_menu(self):
        from core.i18n import t
        if hasattr(self, 'menu') and self.menu:
            self.menu_bar.removeAction(self.menu.menuAction())
        elif hasattr(self, 'action') and self.action:
            self.menu_bar.removeAction(self.action)

        if sys.platform == "darwin":
            # En macOS Cocoa, la barra global NSMenu descarta las QAction directas en la raíz.
            # Los elementos raíz deben ser obligatoriamente QMenu (como 'Ayuda').
            self.menu = self.menu_bar.addMenu(t("Ayuda"))

            # 1. Acción con AboutRole: Qt Cocoa la vincula al menú nativo de la app (pyDCE -> Acerca de pyDCE)
            self.action_app_about = self.menu.addAction(t("Acerca de pyDCE..."))
            self.action_app_about.setMenuRole(QAction.MenuRole.AboutRole)
            self.action_app_about.triggered.connect(self._abrir_acerca)

            # 2. Acción permanente en el menú desplegable 'Ayuda' con NoRole para que siempre
            # esté disponible y visible directamente en la barra de menús en macOS.
            self.action = self.menu.addAction(t("Acerca de pyDCE..."))
            self.action.setMenuRole(QAction.MenuRole.NoRole)
            self.action.triggered.connect(self._abrir_acerca)

            self.action_atajos = self.menu.addAction(t("Atajos de teclado..."))
            self.action_atajos.triggered.connect(self._abrir_atajos)
        else:
            self.action = self.menu_bar.addAction(t("Acerca de..."))
            self.action.triggered.connect(self._abrir_acerca)

    def _abrir_acerca(self):
        dlg = DialogoAcerca(self.main_window)
        dlg.exec()

    def _abrir_atajos(self):
        from gui.dialogo_atajos import DialogoAtajos
        dlg = DialogoAtajos(self.main_window)
        if dlg.exec():
            if hasattr(self.main_window, 'tool_panel'):
                self.main_window.tool_panel.actualizar_insignias_atajos()
