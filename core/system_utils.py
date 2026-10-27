"""
core/system_utils.py — Utilidades de integración con el sistema operativo para pyDCE.

Proporciona funciones para interactuar con el entorno del sistema de forma segura,
evitando interferencias causadas por librerías dinámicas empaquetadas (PyInstaller)
al invocar navegadores o herramientas externas.
"""
import os
import sys
import shutil
import subprocess
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QMessageBox
from core.i18n import t


def obtener_env_limpio() -> dict:
    """
    Devuelve una copia del entorno de variables de sistema sin la contaminación de
    rutas internas de PyInstaller o módulos como OpenCV (cv2).
    Específicamente elimina QT_QPA_PLATFORM_PLUGIN_PATH (que cv2 sobreescribe y causa
    que kde-open falle fatalmente), QT_PLUGIN_PATH y LD_LIBRARY_PATH.
    """
    env = os.environ.copy()

    # Si PyInstaller guardó el LD_LIBRARY_PATH previo, restaurarlo; si no, eliminarlo
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
    else:
        env.pop("LD_LIBRARY_PATH", None)

    # Variables de Qt que PyInstaller o OpenCV inyectan y provocan fallos fatales en kde-open
    variables_qt_a_limpiar = [
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM",
        "QML_IMPORT_PATH",
        "QML2_IMPORT_PATH",
        "QT_QUICK_CONTROLS_CONF",
    ]
    for var in variables_qt_a_limpiar:
        env.pop(var, None)

    # Limpiar variables de Python si apuntan al entorno empaquetado
    for var in ("PYTHONPATH", "PYTHONHOME"):
        if var in env and ("_internal" in env[var] or "_MEI" in env[var]):
            env.pop(var, None)

    # Eliminar cualquier variable cuyo valor contenga rutas de cv2/qt o plugins internos
    for k, v in list(env.items()):
        if "cv2/qt" in v or ("_internal" in v and "plugin" in k.lower()):
            env.pop(k, None)

    return env


def abrir_url_externa(url: str, parent=None) -> bool:
    """
    Abre una URL en el navegador del usuario de manera confiable en Linux, Windows y macOS.
    Maneja entornos compilados (PyInstaller), escritorios Wayland/X11 y fallbacks sucesivos.
    """
    if not url or not str(url).strip():
        return False

    url_str = str(url).strip()
    clean_env = obtener_env_limpio()

    # Neutralizar en el proceso actual la contaminación de OpenCV si existe
    if "QT_QPA_PLATFORM_PLUGIN_PATH" in os.environ and "cv2" in os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"]:
        del os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"]

    # 1. En sistemas Linux: intentar lanzadores de escritorio y navegadores con entorno limpio
    if sys.platform.startswith("linux"):
        # Priorizar gio open si está disponible (utiliza portales FreeDesktop directamente y no depende de kde-open)
        if shutil.which("gio"):
            try:
                proc = subprocess.Popen(
                    ["gio", "open", url_str],
                    env=clean_env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if proc.poll() is None or proc.returncode == 0:
                    return True
            except Exception as e:
                print(f"[system_utils] Error ejecutando gio open: {e}")

        # Intentar con xdg-open con entorno limpio
        if shutil.which("xdg-open"):
            try:
                proc = subprocess.Popen(
                    ["xdg-open", url_str],
                    env=clean_env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if proc.poll() is None or proc.returncode == 0:
                    return True
            except Exception as e:
                print(f"[system_utils] Error ejecutando xdg-open: {e}")

        # Intentar directamente navegadores conocidos en PATH
        navegadores = (
            "brave-browser",
            "brave",
            "google-chrome-stable",
            "google-chrome",
            "firefox",
            "chromium",
            "microsoft-edge"
        )
        for nav in navegadores:
            if shutil.which(nav):
                try:
                    subprocess.Popen(
                        [nav, url_str],
                        env=clean_env,
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return True
                except Exception:
                    continue

    # 2. En Windows: usar os.startfile
    elif sys.platform == "win32":
        try:
            os.startfile(url_str)
            return True
        except Exception as e:
            print(f"[system_utils] Error ejecutando os.startfile: {e}")

    # 3. En macOS: usar open con entorno limpio
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(
                ["open", url_str],
                env=clean_env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception as e:
            print(f"[system_utils] Error ejecutando open en macOS: {e}")

    # 4. Fallback estándar de Python (webbrowser)
    try:
        import webbrowser
        if webbrowser.open(url_str):
            return True
    except Exception as e:
        print(f"[system_utils] Error con webbrowser.open: {e}")

    # 5. Fallback con QDesktopServices de Qt
    try:
        if QDesktopServices.openUrl(QUrl.fromUserInput(url_str)):
            return True
    except Exception as e:
        print(f"[system_utils] Error con QDesktopServices.openUrl: {e}")

    # 6. Fallback final: copiar URL al portapapeles y avisar al usuario
    try:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(url_str)

        msg_body = f"{t('No se pudo abrir el navegador automáticamente. El enlace ha sido copiado al portapapeles:')}\n\n{url_str}"
        if parent:
            QMessageBox.information(parent, t("Enlace copiado"), msg_body)
        else:
            print(f"[system_utils] {msg_body}")
        return True
    except Exception as e:
        print(f"[system_utils] Error copiando enlace al portapapeles: {e}")

    return False
