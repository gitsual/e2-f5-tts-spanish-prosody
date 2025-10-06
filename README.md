# 🎵 Generador F5-TTS con Mejora Prosódica

Generador de texto a voz avanzado que utiliza F5-TTS con un sistema de mejoras prosódicas específicamente diseñado para español. Incluye análisis semántico, transformación fonética y orquestación prosódica para generar audio natural y expresivo.

## 🚀 Inicio Rápido

```bash
# Clonar el repositorio
git clone [URL_DEL_REPO]
cd prosodic_version

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el generador
bash backup_bueno.sh
```

## 📋 Requisitos del Sistema

### Hardware Recomendado
- **GPU**: RTX 4080 SUPER (16GB VRAM) o superior
- **RAM**: 16GB+ recomendados
- **Almacenamiento**: 10GB+ disponibles para modelo

### Software
- **SO**: Linux (Ubuntu 20.04+, Arch Linux, etc.)
- **Python**: 3.8 o superior
- **CUDA**: 12.0+ con drivers NVIDIA actualizados

## 📁 Estructura del Proyecto

```
prosodic_version/
├── backup_bueno.sh                    # Script principal de ejecución
├── generate_prosody_enhanced.py       # Interfaz gráfica y lógica principal
├── prosody_enhancement.py             # Sistema de mejora prosódica
├── prosody_enhanced_generator.py      # Generador híbrido
├── prosody_orchestrator_master.py     # Orquestador maestro de arquitectura vocal
├── phonetic_transformer.py           # Transformaciones fonéticas
├── generar_estructura_compleja_v3.py  # Generador estructural
├── texto.txt                         # Archivo de texto de entrada
├── segment_2955.wav                  # Audio de referencia
├── model_943000.pt                   # Enlace al modelo F5-TTS
└── requirements.txt                  # Dependencias Python
```

## 🎯 Características Principales

### Sistema Híbrido de Generación
- **Generación Original**: Motor F5-TTS base optimizado
- **Mejoras Prosódicas**: Sistema avanzado de hints prosódicos
- **Arquitectura Vocal**: Orquestador maestro para control completo

### Validación Anti-Truncamiento
- **Reintentos Ilimitados**: Sistema robusto contra errores
- **Validación de Pitch**: Análisis automático de estabilidad
- **Fallbacks Seguros**: Recuperación automática de errores

### Optimización GPU
- **CUDA Nativo**: Aprovecha toda la potencia de la GPU
- **Gestión de Memoria**: Optimización automática de VRAM
- **Monitoreo en Tiempo Real**: Estadísticas de rendimiento

## 🎮 Uso del Sistema

### Modo Básico
1. Coloca tu texto en `texto.txt`
2. Asegúrate de tener `segment_2955.wav` como audio de referencia
3. Ejecuta: `bash backup_bueno.sh`
4. El sistema abrirá una interfaz gráfica

### Configuración de Archivos

**texto.txt**: Archivo de entrada con el texto a convertir
```text
Mira, te voy a contar la mayor estafa de nuestra época.
Y no, no es una criptomoneda ni una reducción.
Es algo peor.
```

**segment_2955.wav**: Audio de referencia para clonación de voz
- Formato: WAV, 44.1kHz recomendado
- Duración: 10-30 segundos óptimo
- Calidad: Audio limpio, sin ruido de fondo

## 🔧 Sistema de Mejoras Prosódicas

### Orquestador Maestro
- **Análisis Estructural**: Identificación automática de párrafos y frases
- **Centro Dramático**: Ubicación inteligente del clímax narrativo  
- **Funciones de Párrafo**: Apertura, desarrollo, clímax, cierre

### Hints Prosódicos
- **Entonación Adaptativa**: Ajuste según contexto semántico
- **Pausas Inteligentes**: Respiración natural entre frases
- **Énfasis Selectivo**: Resaltado de palabras clave

### Validación de Calidad
- **Análisis de Pitch**: Detección de inestabilidades
- **Control de Silencio**: Prevención de pausas excesivas
- **Validación Temporal**: Verificación de coherencia temporal

## 📊 Rendimiento Esperado

### RTX 4080 SUPER (16GB)
- **Velocidad**: ~2 segundos por frase corta
- **Memoria**: ~6-8GB VRAM utilizada
- **Calidad**: NFE Steps 64 (máxima calidad)
- **Temperatura**: 75-80°C bajo carga

### Configuración de Calidad
- **NFE Steps**: 64 (máxima), 32 (rápida), 24 (fallback)
- **Validación**: Activada por defecto
- **Reintentos**: Ilimitados con fallback a 50 intentos

## 🛠️ Solución de Problemas

### Error: "No such file or directory: './model_943000.pt'"
```bash
# Verificar que el enlace simbólico existe
ls -la model_943000.pt

# Si no existe, recrear el enlace
ln -sf /ruta/al/modelo/model_943000.pt ./model_943000.pt
```

### Error: "CUDA out of memory"
- Reducir NFE steps a 32 o 24
- Cerrar aplicaciones que usen GPU
- Verificar memoria disponible: `nvidia-smi`

### Audio de baja calidad
- Verificar calidad del archivo de referencia
- Aumentar NFE steps (sacrifica velocidad)
- Revisar configuración de validación

## 🔬 Desarrollo y Contribución

### Estructura de Módulos
- **generate_prosody_enhanced.py**: Interfaz principal y lógica GUI
- **prosody_enhancement.py**: Core del sistema prosódico
- **prosody_orchestrator_master.py**: Arquitectura vocal avanzada
- **prosody_enhanced_generator.py**: Generador híbrido

### Variables de Entorno
```bash
export CUDA_VISIBLE_DEVICES=0        # Selección de GPU
export NUMEXPR_MAX_THREADS=16        # Optimización NumExpr
```

## 📝 Licencia

Este proyecto está bajo licencia [especificar licencia].

## 🤝 Contribución

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📧 Soporte

Para soporte técnico o preguntas, por favor abre un issue en GitHub.

---

**Nota**: Este proyecto requiere el modelo F5-TTS que debe descargarse por separado debido a su tamaño.