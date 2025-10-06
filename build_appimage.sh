#!/bin/bash
# ============================================================================
# Script para crear AppImage para Linux
# Sistema F5-TTS con Mejora Prosódica para Español
# ============================================================================

set -e  # Salir si hay errores

echo "============================================================================"
echo "   Creando AppImage para Linux"
echo "============================================================================"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
APP_NAME="F5-TTS-Spanish-Prosody"
APP_VERSION="1.0.0"
BUILD_DIR="build_appimage"
APPDIR="${BUILD_DIR}/${APP_NAME}.AppDir"

# ============================================================================
# Verificaciones previas
# ============================================================================

echo -e "${YELLOW}[1/8] Verificando requisitos...${NC}"

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 no encontrado${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python encontrado: $PYTHON_VERSION"

# Verificar pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}ERROR: pip3 no encontrado${NC}"
    exit 1
fi
echo "✓ pip3 encontrado"

# ============================================================================
# Instalar dependencias
# ============================================================================

echo ""
echo -e "${YELLOW}[2/8] Instalando PyInstaller y dependencias...${NC}"

pip3 install --upgrade pip
pip3 install pyinstaller

# Usar requirements_full.txt si existe, sino usar requirements.txt y completar
if [ -f "requirements_full.txt" ]; then
    echo "Usando requirements_full.txt..."
    pip3 install -r requirements_full.txt
else
    echo "Usando requirements.txt..."
    pip3 install -r requirements.txt
    # Instalar dependencias completas para el TTS
    pip3 install gradio numpy soundfile librosa scipy
    # Intentar instalar F5-TTS (puede fallar si no está disponible)
    pip3 install f5-tts || echo "⚠️ F5-TTS no disponible, continuando..."
fi

echo "✓ Dependencias instaladas"

# ============================================================================
# Limpiar builds anteriores
# ============================================================================

echo ""
echo -e "${YELLOW}[3/8] Limpiando builds anteriores...${NC}"

rm -rf build dist ${BUILD_DIR}
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "✓ Limpieza completada"

# ============================================================================
# Crear ejecutable con PyInstaller
# ============================================================================

echo ""
echo -e "${YELLOW}[4/8] Creando ejecutable con PyInstaller...${NC}"

pyinstaller --clean f5tts_prosody.spec

if [ ! -d "dist/${APP_NAME}" ]; then
    echo -e "${RED}ERROR: Fallo al crear el ejecutable${NC}"
    exit 1
fi

echo "✓ Ejecutable creado"

# ============================================================================
# Crear estructura AppDir
# ============================================================================

echo ""
echo -e "${YELLOW}[5/8] Creando estructura AppDir...${NC}"

mkdir -p ${APPDIR}/usr/bin
mkdir -p ${APPDIR}/usr/lib
mkdir -p ${APPDIR}/usr/share/applications
mkdir -p ${APPDIR}/usr/share/icons/hicolor/256x256/apps

# Copiar ejecutable
cp -r "dist/${APP_NAME}"/* ${APPDIR}/usr/bin/

# Crear script de inicio
cat > ${APPDIR}/AppRun << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
cd "${HERE}/usr/bin"
exec "${HERE}/usr/bin/F5-TTS-Spanish-Prosody" "$@"
EOF

chmod +x ${APPDIR}/AppRun

echo "✓ Estructura AppDir creada"

# ============================================================================
# Crear archivos de metadatos
# ============================================================================

echo ""
echo -e "${YELLOW}[6/8] Creando archivos de metadatos...${NC}"

# Crear .desktop file
cat > ${APPDIR}/${APP_NAME}.desktop << EOF
[Desktop Entry]
Type=Application
Name=F5-TTS Spanish Prosody
Comment=Sistema de síntesis de voz con mejoras prosódicas para español
Exec=F5-TTS-Spanish-Prosody
Icon=${APP_NAME}
Categories=AudioVideo;Audio;
Terminal=true
EOF

# Crear icono simple (placeholder - puedes reemplazarlo con un PNG real)
cat > ${APPDIR}/${APP_NAME}.png << 'EOF'
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==
EOF

cp ${APPDIR}/${APP_NAME}.png ${APPDIR}/usr/share/icons/hicolor/256x256/apps/
cp ${APPDIR}/${APP_NAME}.desktop ${APPDIR}/usr/share/applications/

# Copiar documentación
cp README.md ${APPDIR}/usr/bin/ 2>/dev/null || true
cp GUIA_DIALECTOS.md ${APPDIR}/usr/bin/ 2>/dev/null || true

echo "✓ Metadatos creados"

# ============================================================================
# Descargar appimagetool
# ============================================================================

echo ""
echo -e "${YELLOW}[7/8] Descargando appimagetool...${NC}"

APPIMAGETOOL="appimagetool-x86_64.AppImage"

if [ ! -f "${APPIMAGETOOL}" ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/${APPIMAGETOOL}"
    chmod +x ${APPIMAGETOOL}
    echo "✓ appimagetool descargado"
else
    echo "✓ appimagetool ya existe"
fi

# ============================================================================
# Crear AppImage
# ============================================================================

echo ""
echo -e "${YELLOW}[8/8] Creando AppImage...${NC}"

ARCH=x86_64 ./${APPIMAGETOOL} ${APPDIR} ${APP_NAME}-${APP_VERSION}-x86_64.AppImage

if [ ! -f "${APP_NAME}-${APP_VERSION}-x86_64.AppImage" ]; then
    echo -e "${RED}ERROR: Fallo al crear AppImage${NC}"
    exit 1
fi

chmod +x ${APP_NAME}-${APP_VERSION}-x86_64.AppImage

echo "✓ AppImage creado"

# ============================================================================
# Resumen final
# ============================================================================

echo ""
echo "============================================================================"
echo -e "${GREEN}   COMPLETADO!${NC}"
echo "============================================================================"
echo ""
echo "AppImage creado: ${APP_NAME}-${APP_VERSION}-x86_64.AppImage"
echo ""
echo "Para ejecutar:"
echo "  ./${APP_NAME}-${APP_VERSION}-x86_64.AppImage"
echo ""
echo "IMPORTANTE:"
echo "  - Necesitas un archivo de audio de referencia (.wav o .mp3)"
echo "  - Los modelos de F5-TTS se descargarán en el primer uso"
echo "  - Se recomienda GPU NVIDIA para mejor rendimiento"
echo ""
echo "Para instalar en el sistema:"
echo "  1. Mover a ~/Applications o /opt"
echo "  2. Hacer doble clic o ejecutar desde terminal"
echo ""
