#!/bin/bash
# ============================================================================
# Script simple para crear ejecutable Linux (sin AppImage)
# Sistema F5-TTS con Mejora Prosódica para Español
# ============================================================================

set -e  # Salir si hay errores

echo "============================================================================"
echo "   Creando ejecutable para Linux (PyInstaller solo)"
echo "============================================================================"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Verificaciones previas
# ============================================================================

echo -e "${YELLOW}[1/5] Verificando requisitos...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 no encontrado${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python encontrado: $PYTHON_VERSION"

# ============================================================================
# Instalar dependencias
# ============================================================================

echo ""
echo -e "${YELLOW}[2/5] Instalando PyInstaller y dependencias...${NC}"

pip3 install --upgrade pip
pip3 install pyinstaller

# Usar requirements_full.txt si existe, sino usar requirements.txt
if [ -f "requirements_full.txt" ]; then
    echo "Usando requirements_full.txt..."
    pip3 install -r requirements_full.txt
else
    echo "Usando requirements.txt..."
    pip3 install -r requirements.txt
    pip3 install gradio numpy soundfile librosa scipy
    pip3 install f5-tts || echo "⚠️ F5-TTS no disponible, continuando..."
fi

echo "✓ Dependencias instaladas"

# ============================================================================
# Limpiar builds anteriores
# ============================================================================

echo ""
echo -e "${YELLOW}[3/5] Limpiando builds anteriores...${NC}"

rm -rf build dist
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "✓ Limpieza completada"

# ============================================================================
# Crear ejecutable con PyInstaller
# ============================================================================

echo ""
echo -e "${YELLOW}[4/5] Creando ejecutable con PyInstaller...${NC}"

pyinstaller --clean f5tts_prosody.spec

if [ ! -d "dist/F5-TTS-Spanish-Prosody" ]; then
    echo -e "${RED}ERROR: Fallo al crear el ejecutable${NC}"
    exit 1
fi

echo "✓ Ejecutable creado"

# ============================================================================
# Copiar archivos necesarios
# ============================================================================

echo ""
echo -e "${YELLOW}[5/5] Copiando archivos de documentación...${NC}"

cp README.md dist/F5-TTS-Spanish-Prosody/ 2>/dev/null || true
cp GUIA_DIALECTOS.md dist/F5-TTS-Spanish-Prosody/ 2>/dev/null || true
cp README_EJECUTABLES.md dist/F5-TTS-Spanish-Prosody/ 2>/dev/null || true

# Crear archivo de ejemplo
echo "Este es un texto de ejemplo para el generador prosódico." > "dist/F5-TTS-Spanish-Prosody/texto.txt"

echo "✓ Archivos copiados"

# ============================================================================
# Crear script de inicio fácil
# ============================================================================

cat > dist/F5-TTS-Spanish-Prosody/run.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./F5-TTS-Spanish-Prosody
EOF

chmod +x dist/F5-TTS-Spanish-Prosody/run.sh

# ============================================================================
# Resumen final
# ============================================================================

echo ""
echo "============================================================================"
echo -e "${GREEN}   COMPLETADO!${NC}"
echo "============================================================================"
echo ""
echo "Ejecutable creado en: dist/F5-TTS-Spanish-Prosody/"
echo ""
echo "Para ejecutar:"
echo "  cd dist/F5-TTS-Spanish-Prosody"
echo "  ./F5-TTS-Spanish-Prosody"
echo ""
echo "O usar el script de inicio:"
echo "  cd dist/F5-TTS-Spanish-Prosody"
echo "  ./run.sh"
echo ""
echo "IMPORTANTE:"
echo "  - Necesitas un archivo de audio de referencia (.wav o .mp3)"
echo "  - Los modelos de F5-TTS se descargarán en el primer uso"
echo "  - Se recomienda GPU NVIDIA para mejor rendimiento"
echo ""
echo "Para crear un AppImage completo, usa:"
echo "  ./build_appimage.sh"
echo ""
