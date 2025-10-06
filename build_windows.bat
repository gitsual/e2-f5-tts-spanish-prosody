@echo off
REM ============================================================================
REM Script para crear ejecutable .exe para Windows
REM Sistema F5-TTS con Mejora Prosódica para Español
REM ============================================================================

echo ============================================================================
echo    Creando ejecutable .exe para Windows
echo ============================================================================
echo.

REM Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Por favor instala Python 3.8+
    pause
    exit /b 1
)

echo [1/5] Instalando PyInstaller y dependencias...
python -m pip install --upgrade pip
python -m pip install pyinstaller

REM Usar requirements_full.txt si existe, sino usar requirements.txt
if exist requirements_full.txt (
    echo Usando requirements_full.txt...
    python -m pip install -r requirements_full.txt
) else (
    echo Usando requirements.txt...
    python -m pip install -r requirements.txt
    python -m pip install gradio numpy soundfile librosa scipy torch torchaudio f5-tts
)

echo.
echo [2/5] Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

echo.
echo [3/5] Creando ejecutable con PyInstaller...
pyinstaller --clean f5tts_prosody.spec

if errorlevel 1 (
    echo.
    echo ERROR: Fallo al crear el ejecutable
    pause
    exit /b 1
)

echo.
echo [4/5] Copiando archivos necesarios...
if not exist "dist\F5-TTS-Spanish-Prosody" mkdir "dist\F5-TTS-Spanish-Prosody"
xcopy /E /I /Y modules dist\F5-TTS-Spanish-Prosody\modules
copy README.md dist\F5-TTS-Spanish-Prosody\
copy GUIA_DIALECTOS.md dist\F5-TTS-Spanish-Prosody\ 2>nul

echo.
echo [5/5] Creando archivo de ejemplo...
echo Este es un texto de ejemplo para el generador prosodico. > "dist\F5-TTS-Spanish-Prosody\texto.txt"

echo.
echo ============================================================================
echo    COMPLETADO!
echo ============================================================================
echo.
echo El ejecutable se encuentra en: dist\F5-TTS-Spanish-Prosody\
echo.
echo IMPORTANTE:
echo - Necesitas un archivo de audio de referencia (.wav o .mp3)
echo - Los modelos de F5-TTS se descargarán automáticamente en el primer uso
echo - Se recomienda tener una GPU NVIDIA para mejor rendimiento
echo.
echo Para ejecutar: dist\F5-TTS-Spanish-Prosody\F5-TTS-Spanish-Prosody.exe
echo.
pause
