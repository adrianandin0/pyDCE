#!/usr/bin/env bash
# ==============================================================================
# pyDCE - Script de Compilación para macOS / Build Script for macOS (.app / .zip / .dmg)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="pyDCE"
BUNDLE_NAME="pyDCE.app"
DIST_DIR="dist_pkg"
BUILD_DIR="build_pkg"

# Leer versión unificada directamente desde version.txt
if [ ! -f "version.txt" ]; then
    echo "ERROR: No se encontró 'version.txt'."
    exit 1
fi
VERSION=$(tr -d '\r\n' < version.txt)

ARCH="$(uname -m)"
ZIP_NAME="${APP_NAME}-${VERSION}-macos.zip"
DMG_NAME="${APP_NAME}-${VERSION}-macos.dmg"

echo "================================================="
echo " pyDCE - Compilador de Aplicación macOS"
echo " Versión: ${VERSION} (${ARCH})"
echo "================================================="

# Verificar que se esté ejecutando en macOS
OS_TYPE="$(uname -s)"
if [ "$OS_TYPE" != "Darwin" ]; then
    echo "ERROR: build_macos.sh debe ejecutarse dentro de macOS (o en una VM con macOS)."
    echo "Sistema actual detectado: ${OS_TYPE} ($(uname -m))"
    echo ""
    echo "PyInstaller requiere el entorno nativo de Apple (Mach-O, Cocoa y Qt6 para macOS)"
    echo "y no permite compilación cruzada (cross-compilation) directa desde Linux a macOS."
    echo ""
    echo "Para compilar los paquetes de Linux usa:"
    echo "   ./build_all.sh"
    echo ""
    echo "Para compilar el .app de macOS, corre este script dentro de tu máquina virtual Big Sur."
    exit 1
fi

# 1. Verificar Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 no está instalado o no se encuentra en el PATH."
    echo "Instala Python 3 desde https://www.python.org/ o vía Homebrew (brew install python)."
    exit 1
fi

# 2. Entorno virtual
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creando entorno virtual Python en '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activando entorno virtual..."
source "$VENV_DIR/bin/activate"

# 3. Instalación de dependencias
echo "Instalando y verificando dependencias..."
pip install --upgrade pip

if [ -f "requirements_macos.txt" ]; then
    pip install --prefer-binary -r requirements_macos.txt
else
    pip install --prefer-binary -r requirements.txt
    pip install --prefer-binary pyinstaller>=6.0.0
fi

# 4. Limpieza de compilaciones previas
echo "Limpiando artefactos previos..."
rm -rf "$BUILD_DIR" "$DIST_DIR" build dist "$ZIP_NAME" "$DMG_NAME"

# 5. Compilación con PyInstaller
echo "Compilando aplicación nativa con PyInstaller y pyDCE.spec..."
pyinstaller --noconfirm --clean \
    --workpath "$BUILD_DIR" \
    --distpath "$DIST_DIR" \
    pyDCE.spec

APP_PATH="${DIST_DIR}/${BUNDLE_NAME}"

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: No se encontró '$APP_PATH' tras la compilación."
    exit 1
fi

# 6. Verificación y ajuste de recursos del bundle
RESOURCES_DIR="${APP_PATH}/Contents/Resources"
mkdir -p "$RESOURCES_DIR"

if [ -f "gui/pyDCE.icns" ] && [ ! -f "${RESOURCES_DIR}/pyDCE.icns" ]; then
    echo "Copiando icono pyDCE.icns a Resources..."
    cp "gui/pyDCE.icns" "${RESOURCES_DIR}/pyDCE.icns"
fi

# 7. Firma ad-hoc y limpieza de atributos extendidos de cuarentena
echo "Aplicando firma ad-hoc para permitir ejecución en macOS..."
xattr -cr "$APP_PATH" 2>/dev/null || true
if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || true
fi

# 8. Empaquetado en .zip para GitHub Releases
echo "Generando paquete ZIP para distribución: ${ZIP_NAME}..."
if command -v ditto &>/dev/null; then
    # ditto preserva atributos HFS+, enlaces simbólicos y permisos del bundle
    ditto -c -k --keepParent "$APP_PATH" "$ZIP_NAME"
else
    (cd "$DIST_DIR" && zip -r -y "../$ZIP_NAME" "$BUNDLE_NAME")
fi

# 9. Empaquetado en .dmg (si hdiutil está disponible)
if command -v hdiutil &>/dev/null; then
    echo "Generando imagen de disco DMG: ${DMG_NAME}..."
    hdiutil create -volname "${APP_NAME}" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG_NAME"
fi

echo "================================================="
echo " PROCESO FINALIZADO CON ÉXITO"
echo " Artefactos listos para publicar en Releases o probar en VM:"
if [ -f "$ZIP_NAME" ]; then
    echo "   1. ${ZIP_NAME}"
fi
if [ -f "$DMG_NAME" ]; then
    echo "   2. ${DMG_NAME}"
fi
echo "   Bundle local: ${APP_PATH}"
echo "================================================="
echo ""
echo "Instrucciones para probar en macOS Big Sur o superior:"
echo "1. Descomprimir ${ZIP_NAME} o abrir ${DMG_NAME}."
echo "2. Mover ${BUNDLE_NAME} a /Applications (o ejecutarlo directamente)."
echo "3. Si Gatekeeper indica que la aplicación no puede abrirse porque proviene"
echo "   de un desarrollador no identificado, ejecutar en Terminal:"
echo "   xattr -cr /Applications/${BUNDLE_NAME}"
echo "   o hacer clic derecho en la app y seleccionar 'Abrir'."
echo "================================================="
