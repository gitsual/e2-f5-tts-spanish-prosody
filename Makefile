# ============================================================================
# Makefile para F5-TTS con Mejora Prosódica
# ============================================================================
# Uso:
#   make help          - Mostrar esta ayuda
#   make linux         - Crear ejecutable Linux
#   make appimage      - Crear AppImage
#   make clean         - Limpiar archivos de construcción
#   make install-deps  - Instalar dependencias
# ============================================================================

.PHONY: help linux appimage clean install-deps

# Configuración
PYTHON := python3
PIP := pip3

# ============================================================================
# Ayuda (default)
# ============================================================================

help:
	@echo "============================================================================"
	@echo "  F5-TTS con Mejora Prosódica - Sistema de Construcción"
	@echo "============================================================================"
	@echo ""
	@echo "Comandos disponibles:"
	@echo ""
	@echo "  make help          - Mostrar esta ayuda"
	@echo "  make linux         - Crear ejecutable Linux (PyInstaller)"
	@echo "  make appimage      - Crear AppImage completo"
	@echo "  make clean         - Limpiar archivos de construcción"
	@echo "  make install-deps  - Instalar dependencias Python"
	@echo ""
	@echo "En Windows, usa los scripts .bat directamente:"
	@echo "  build_windows.bat"
	@echo ""
	@echo "============================================================================"

# ============================================================================
# Instalación de dependencias
# ============================================================================

install-deps:
	@echo "Instalando dependencias..."
	$(PIP) install --upgrade pip
	$(PIP) install pyinstaller
	@if [ -f requirements_full.txt ]; then \
		echo "Usando requirements_full.txt..."; \
		$(PIP) install -r requirements_full.txt; \
	else \
		echo "Usando requirements.txt..."; \
		$(PIP) install -r requirements.txt; \
		$(PIP) install gradio numpy soundfile librosa scipy f5-tts; \
	fi
	@echo "✓ Dependencias instaladas"

# ============================================================================
# Construcción Linux
# ============================================================================

linux: install-deps
	@echo "Creando ejecutable Linux..."
	./build_linux.sh
	@echo "✓ Ejecutable creado en dist/F5-TTS-Spanish-Prosody/"

# ============================================================================
# Construcción AppImage
# ============================================================================

appimage: install-deps
	@echo "Creando AppImage..."
	./build_appimage.sh
	@echo "✓ AppImage creado"

# ============================================================================
# Limpieza
# ============================================================================

clean:
	@echo "Limpiando archivos de construcción..."
	rm -rf build dist build_appimage
	rm -f *.AppImage
	rm -f appimagetool-x86_64.AppImage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "✓ Limpieza completada"
