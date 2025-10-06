#!/bin/bash

# Script de inicio para el Generador F5-TTS con Mejora Prosódica

echo "=================================================================="
echo "🎵 Generador F5-TTS con Mejora Prosódica - Iniciando"
echo "=================================================================="
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no encontrado. Por favor, instala Python 3.8+"
    exit 1
fi

# Cambiar al directorio del script
cd "$(dirname "$0")"

# Verificar archivos requeridos
echo "📋 Verificando archivos requeridos..."

if [ ! -f "texto.txt" ]; then
    echo "❌ No se encuentra 'texto.txt'"
    echo "   Creando archivo de ejemplo..."
    echo "Este es un texto de ejemplo para el generador prosódico." > texto.txt
    echo "✅ Archivo 'texto.txt' creado. Por favor, edítalo con tu contenido."
fi

if [ ! -f "segment_2955.wav" ]; then
    echo "❌ No se encuentra 'segment_2955.wav'"
    echo "   Este archivo debe existir para la clonación de voz."
    echo "   Por favor, coloca tu archivo de audio de referencia con este nombre."
    read -p "Presiona Enter para continuar o Ctrl+C para cancelar..."
fi

echo "✅ Verificación completada"
echo ""

# Verificar dependencias Python
echo "🔍 Verificando dependencias Python..."

# Lista de paquetes requeridos
PACKAGES=("numpy" "soundfile" "librosa" "gradio")

MISSING_PACKAGES=()

for package in "${PACKAGES[@]}"; do
    if ! python3 -c "import $package" 2>/dev/null; then
        MISSING_PACKAGES+=($package)
    fi
done

if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    echo "📦 Instalando paquetes faltantes..."
    pip3 install numpy soundfile librosa gradio
fi

# Mostrar información del sistema
echo ""
echo "📊 Información del sistema:"
echo "   Python: $(python3 --version)"
echo "   Directorio: $(pwd)"

if command -v nvidia-smi &> /dev/null; then
    echo "   GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -1)"
    echo "   VRAM: $(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1) MB"
else
    echo "   GPU: No detectada (se usará CPU)"
fi

echo ""
echo "🚀 Iniciando interfaz gráfica..."
echo ""

# Ejecutar el generador con interfaz Gradio
python3 modules/gradio_app.py

echo ""
echo "👋 Generador cerrado. ¡Hasta pronto!"