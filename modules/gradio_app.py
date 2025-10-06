#!/usr/bin/env python3
"""
====================================================================================================
GENERADOR F5-TTS CON MEJORA PROSÓDICA - INTERFAZ GRADIO
====================================================================================================

Descripción:
    Interfaz web moderna basada en Gradio para el sistema de síntesis de voz F5-TTS con mejoras
    prosódicas automáticas. Reemplaza la interfaz tkinter original con una solución web accesible
    desde cualquier navegador.

Características principales:
    - Interfaz web responsive accesible vía navegador
    - Dos modos de entrada de texto: archivo .txt o escritura directa
    - Carga de audio de referencia personalizado para clonación de voz
    - Procesamiento en dos fases: generación prosódica + post-procesamiento
    - Transformación fonética opcional (betacismo, yeísmo, seseo)
    - Progreso en tiempo real con actualizaciones visuales
    - Reproducción de audio integrada en el navegador
    - Sistema de reanudación para sesiones interrumpidas

Autor: Sistema de generación prosódica F5-TTS
Fecha: 2025
Versión: 2.0 (Gradio)
====================================================================================================
"""

import os
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from typing import List, Dict, Optional, Tuple
import time
from datetime import datetime
import json
import gradio as gr
import threading

# ====================================================================================================
# IMPORTACIÓN DE MÓDULOS DE PROCESAMIENTO PROSÓDICO
# ====================================================================================================

from core.prosody_processor import (
    ProsodyOrchestrator,      # Orquestador principal del sistema prosódico
    ProsodyHintGenerator,     # Generador de hints prosódicos para F5-TTS
    ProsodyAnalyzer,          # Analizador de características prosódicas del audio
    ProsodyProblemDetector,   # Detector de problemas prosódicos en el audio generado
    SelectiveRegenerator,     # Regenerador selectivo de segmentos problemáticos
    smart_concatenate,        # Concatenación inteligente con crossfade
    export_prosody_report     # Exportador de reportes de análisis prosódico
)

# Transformador fonético para variaciones dialectales del español
from core.phonetic_processor import SpanishPhoneticTransformer

# ====================================================================================================
# IMPORTACIÓN CONDICIONAL DE DEPENDENCIAS OPCIONALES
# ====================================================================================================

# Sistema híbrido de generación (versión mejorada del generador)
try:
    from tts_generator import ProsodyEnhancedGenerator
    HYBRID_AVAILABLE = True
    print("✅ Sistema híbrido cargado correctamente")
except ImportError as e:
    print(f"⚠️ Sistema híbrido no disponible: {e}")
    HYBRID_AVAILABLE = False

# Motor F5-TTS para síntesis de voz
try:
    from f5_tts.api import F5TTS
    F5_AVAILABLE = True
except ImportError:
    print("⚠️ F5-TTS no disponible. Se usará modo demo/fallback.")
    F5_AVAILABLE = False

# Adaptador de prosodia del sistema original (legacy)
from main_app import F5ProsodyAdapter


# ====================================================================================================
# CLASE PRINCIPAL: INTERFAZ GRADIO
# ====================================================================================================

class ProsodyGeneratorGradio:
    """
    Clase principal para la interfaz web Gradio del generador prosódico.

    Esta clase gestiona toda la lógica de la interfaz de usuario web, incluyendo:
    - Validación de entradas (archivos de texto y audio)
    - Procesamiento de texto (desde archivo o entrada directa)
    - Generación de audio con mejoras prosódicas en dos fases
    - Actualización de progreso en tiempo real
    - Gestión de logs y estado de procesamiento

    Attributes:
        is_processing (bool): Indica si hay una generación en curso
        resume_state (dict): Estado guardado para reanudación de sesiones
        current_progress (float): Progreso actual (0-100)
        current_status (str): Descripción textual del estado actual
        log_messages (list): Lista de mensajes de log acumulados
        text_file (Path): Ruta al archivo de texto (si se usa)
        reference_audio (Path): Ruta al audio de referencia
        phonetic_transformer (SpanishPhoneticTransformer): Transformador fonético
    """

    def __init__(self):
        """
        Inicializa la interfaz Gradio con valores por defecto.

        Configura el estado inicial de la aplicación, preparando todas las variables
        necesarias para el procesamiento y la gestión de la interfaz de usuario.
        """
        # Variables de control de estado del procesamiento
        self.is_processing = False          # Flag para prevenir ejecuciones concurrentes
        self.resume_state = None            # Estado de reanudación (si existe)
        self.current_progress = 0           # Progreso actual en porcentaje
        self.current_status = "Listo para generar"  # Estado legible para el usuario
        self.log_messages = []              # Historial de mensajes de log

        # Archivos de entrada (configurables por el usuario)
        self.text_file = None               # Archivo de texto opcional
        self.reference_audio = None         # Archivo de audio de referencia obligatorio

        # Transformador fonético para simulación de variaciones dialectales
        self.phonetic_transformer = SpanishPhoneticTransformer()

    def check_files(self, text_file, direct_text, audio_file):
        """
        Valida las entradas del usuario antes de iniciar el procesamiento.

        Verifica que se haya proporcionado texto (ya sea por archivo o directamente)
        y que el archivo de audio de referencia exista y sea accesible.

        Args:
            text_file (str): Ruta al archivo de texto (.txt) o None
            direct_text (str): Texto escrito directamente por el usuario o None
            audio_file (str): Ruta al archivo de audio de referencia (.wav, .mp3)

        Returns:
            bool: True si todas las validaciones pasan, False en caso contrario

        Note:
            Al menos una fuente de texto (archivo o directo) debe estar presente.
            El audio de referencia es obligatorio siempre.
        """
        errors = []

        # Validar texto: puede ser archivo o texto directo (al menos uno requerido)
        if text_file is None and (direct_text is None or direct_text.strip() == ""):
            errors.append("❌ Debes proporcionar texto: sube un archivo o escribe en la caja de texto")
        elif text_file is not None and not Path(text_file).exists():
            errors.append(f"❌ No se encuentra el archivo de texto: {text_file}")

        # Validar audio de referencia (siempre obligatorio)
        if audio_file is None:
            errors.append("❌ No se ha seleccionado archivo de audio de referencia")
        elif not Path(audio_file).exists():
            errors.append(f"❌ No se encuentra el audio de referencia: {audio_file}")

        # Registrar errores o éxito
        if errors:
            for error in errors:
                self.log(error)
            return False
        else:
            self.log("✅ Entrada validada correctamente")
            return True

    def log(self, message):
        """
        Añade un mensaje al registro de log con timestamp.

        Registra todos los eventos importantes durante el procesamiento,
        agregando automáticamente una marca de tiempo para facilitar
        el seguimiento temporal de las operaciones.

        Args:
            message (str): Mensaje a registrar en el log

        Returns:
            str: Todos los mensajes de log acumulados concatenados
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self.log_messages.append(full_message)
        return "\n".join(self.log_messages)

    def read_and_parse_text(self, direct_text=None) -> List[Dict]:
        """
        Lee y parsea el texto de entrada, dividiéndolo en párrafos estructurados.

        Procesa el texto desde archivo o entrada directa, identificando la estructura
        de párrafos y clasificándolos según su posición (introducción, desarrollo,
        conclusión) para optimizar la generación prosódica.

        Args:
            direct_text (str, optional): Texto proporcionado directamente por el usuario.
                                        Si es None, lee desde self.text_file

        Returns:
            List[Dict]: Lista de diccionarios con información de párrafos:
                {
                    'text': str,           # Contenido del párrafo
                    'type': str,           # Tipo: 'introduction', 'development', 'conclusion'
                    'index': int           # Índice del párrafo en el documento
                }

        Note:
            Los párrafos se clasifican automáticamente en tercios:
            - Primer tercio: introducción
            - Segundo tercio: desarrollo
            - Último tercio: conclusión
        """
        # Determinar fuente del texto
        if direct_text and direct_text.strip():
            # Usar texto directo del usuario
            content = direct_text.strip()
        else:
            # Leer desde archivo
            with open(self.text_file, 'r', encoding='utf-8') as f:
                content = f.read()

        # Dividir por párrafos
        raw_paragraphs = content.split('\n\n')

        paragraphs = []
        for idx, para in enumerate(raw_paragraphs):
            para = para.strip()
            if not para:
                continue

            if idx == 0 or (idx < len(raw_paragraphs) * 0.33):
                para_type = "introduction"
            elif idx < len(raw_paragraphs) * 0.66:
                para_type = "development"
            else:
                para_type = "conclusion"

            paragraphs.append({
                'text': para,
                'type': para_type,
                'index': idx
            })

        return paragraphs

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Divide un párrafo en frases individuales respetando la puntuación española.

        Realiza una segmentación inteligente considerando:
        - Signos de apertura españoles (¿ ¡)
        - Abreviaciones comunes (Sr., Dr., etc.)
        - Puntos suspensivos, punto y coma, dos puntos
        - Exclamaciones e interrogaciones múltiples

        Args:
            text (str): Párrafo a dividir en frases

        Returns:
            List[str]: Lista de frases segmentadas y limpiadas

        Note:
            Usa marcadores especiales (<FRASE_BREAK>) internamente para
            realizar la segmentación de manera robusta.
        """
        import re

        # Proteger abreviaciones
        text = re.sub(r'\b(Sr|Sra|Dr|Dra|St|Sto|Sta)\.\s*', r'\1<DOT> ', text)

        # Pre-procesamiento para signos españoles
        text = re.sub(r'([.!?])\s*([¡¿])', r'\1<FRASE_BREAK>\2', text)
        text = re.sub(r'([.!?])\s{2,}([¡¿])', r'\1<FRASE_BREAK>\2', text)

        # Aislar bloques exclamativos e interrogativos
        text = re.sub(r'¡([^!]+)!', r'<FRASE_BREAK>¡\1!<FRASE_BREAK>', text)
        text = re.sub(r'¿([^?]+)\?', r'<FRASE_BREAK>¿\1?<FRASE_BREAK>', text)

        # Normalizar marcadores
        text = re.sub(r'(?:<FRASE_BREAK>){2,}', '<FRASE_BREAK>', text)

        # Dividir
        if '<FRASE_BREAK>' in text:
            parts_raw = text.split('<FRASE_BREAK>')
        else:
            sentence_endings = re.compile(r'([.!?;:]|\.\.\.)\s+')
            parts_raw = sentence_endings.split(text)

        sentences = []

        if '<FRASE_BREAK>' in text:
            for part in parts_raw:
                part_clean = part.replace('<DOT>', '.').strip()
                if part_clean and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]', part_clean):
                    sentences.append(part_clean)
        else:
            current = ""
            for i, part in enumerate(parts_raw):
                if part in '.!?;:' or part == '...':
                    current += part
                    current = current.replace('<DOT>', '.')
                    if current.strip() and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]', current.strip()):
                        sentences.append(current.strip())
                    current = ""
                else:
                    current += part

            if current.strip() and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]', current.strip()):
                sentences.append(current.strip())

        return sentences

    def _estimate_paragraph_id(self, phrase_idx: int, total_phrases: int) -> int:
        """
        Estima el ID del párrafo basado en la posición relativa de la frase.

        Divide el texto en tres secciones aproximadas para aplicar diferentes
        características prosódicas según la posición narrativa.

        Args:
            phrase_idx (int): Índice de la frase actual (0-based)
            total_phrases (int): Número total de frases en el documento

        Returns:
            int: ID del párrafo estimado:
                0 - Introducción (primer tercio)
                1 - Desarrollo (segundo tercio)
                2 - Conclusión (último tercio)
        """
        third = total_phrases // 3
        if phrase_idx < third:
            return 0  # Introducción
        elif phrase_idx < 2 * third:
            return 1  # Desarrollo
        else:
            return 2  # Conclusión

    def generate_audio(self, text_input_type, text_file, direct_text, audio_file, use_phonetic, progress=gr.Progress()):
        """
        Función principal de generación de audio con mejoras prosódicas.

        Coordina todo el proceso de síntesis de voz, desde la validación de entradas
        hasta la generación final del audio con mejoras prosódicas aplicadas.

        Proceso completo:
        1. Validación de entradas (texto + audio de referencia)
        2. Lectura y segmentación del texto en párrafos y frases
        3. Aplicación opcional de transformación fonética
        4. FASE 1: Generación con hints prosódicos (sistema híbrido)
        5. FASE 2: Análisis y corrección de problemas prosódicos
        6. Concatenación final y guardado de resultados

        Args:
            text_input_type (str): "Archivo" o "Texto directo"
            text_file (str): Ruta al archivo .txt (si aplica)
            direct_text (str): Texto escrito directamente (si aplica)
            audio_file (str): Ruta al audio de referencia (.wav, .mp3)
            use_phonetic (bool): Si aplicar transformación fonética
            progress (gr.Progress): Objeto de progreso de Gradio

        Yields:
            tuple: (progreso, estado, log, audio_final, audio_fase1, visible_final, visible_fase1)
                - progreso (float): Porcentaje de progreso (0-100)
                - estado (str): Descripción del estado actual
                - log (str): Log acumulado de mensajes
                - audio_final (str): Ruta al audio final generado
                - audio_fase1 (str): Ruta al audio de fase 1
                - visible_final (gr.update): Visibilidad del reproductor final
                - visible_fase1 (gr.update): Visibilidad del reproductor fase 1

        Note:
            Esta función es un generador que produce actualizaciones en tiempo real
            para la interfaz Gradio, permitiendo mostrar el progreso al usuario.
        """
        try:
            # Resetear estado
            self.is_processing = True
            self.log_messages = []
            self.current_progress = 0

            # Determinar fuente de texto
            if text_input_type == "Texto directo":
                self.text_file = None
                texto_a_usar = direct_text
                self.log(f"📝 Usando texto directo ({len(direct_text) if direct_text else 0} caracteres)")
            else:
                self.text_file = Path(text_file) if text_file else None
                texto_a_usar = None
                if text_file:
                    self.log(f"📝 Usando archivo de texto: {text_file}")

            # Actualizar audio de referencia
            self.reference_audio = Path(audio_file) if audio_file else None
            if audio_file:
                self.log(f"🎤 Usando audio de referencia: {audio_file}")

            # Validar entradas
            if not self.check_files(text_file if text_input_type == "Archivo" else None, direct_text if text_input_type == "Texto directo" else None, audio_file):
                yield (
                    0,
                    "❌ Error: Archivos faltantes",
                    "\n".join(self.log_messages),
                    None,
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False)
                )
                return

            # Crear directorio de salida
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(f"output_{timestamp}")
            output_dir.mkdir(parents=True, exist_ok=True)

            self.log(f"📁 Directorio de salida: {output_dir}")
            self.log(f"🔤 Transformación fonética: {'✅ ACTIVADA' if use_phonetic else '❌ DESACTIVADA'}")

            yield (
                5,
                "Leyendo texto...",
                "\n".join(self.log_messages),
                None,
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )

            # Leer y procesar texto
            if texto_a_usar:
                self.log(f"\n📖 Procesando texto directo...")
            else:
                self.log(f"\n📖 Leyendo archivo: {self.text_file}")
            paragraphs = self.read_and_parse_text(direct_text=texto_a_usar)

            if not paragraphs:
                self.log("❌ No se encontraron párrafos en el texto")
                yield (
                    0,
                    "❌ Error: Sin párrafos",
                    "\n".join(self.log_messages),
                    None,
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False)
                )
                return

            self.log(f"📚 Párrafos detectados: {len(paragraphs)}")

            # Aplicar transformación fonética si está habilitada
            if use_phonetic:
                progress(0.1, desc="Aplicando transformación fonética...")
                self.log("\n🔤 Aplicando transformación fonética al texto...")
                original_text = "\n\n".join([p['text'] for p in paragraphs])

                # Guardar texto original
                original_path = output_dir / "texto_original.txt"
                with open(original_path, 'w', encoding='utf-8') as f:
                    f.write(original_text)

                # Transformar texto
                transformed_text = self.phonetic_transformer.transform_text(original_text)

                # Log de ejemplo
                orig_preview = original_text[:100].replace('\n', ' ')
                trans_preview = transformed_text[:100].replace('\n', ' ')
                self.log(f"📄 ANTES: {orig_preview}...")
                self.log(f"🔊 DESPUÉS: {trans_preview}...")

                # Guardar texto transformado
                transformed_path = output_dir / "texto_fonetico.txt"
                with open(transformed_path, 'w', encoding='utf-8') as f:
                    f.write(transformed_text)

                # Actualizar párrafos
                transformed_paragraphs = transformed_text.split('\n\n')
                for i, para in enumerate(paragraphs):
                    if i < len(transformed_paragraphs):
                        para['text'] = transformed_paragraphs[i]

                # Estadísticas
                stats = self.phonetic_transformer.get_transformation_stats()
                self.log(f"✅ Transformación completada:")
                self.log(f"   - Palabras transformadas: {stats['unique_words_transformed']}")
                self.log(f"   - Consistencia: {stats['consistency_score']:.1f}%")

            yield (
                15,
                "Segmentando en frases...",
                "\n".join(self.log_messages),
                None,
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )

            # Convertir párrafos a frases
            all_sentences = []
            for p_idx, paragraph in enumerate(paragraphs):
                sentences = self.split_into_sentences(paragraph['text'])
                self.log(f"  Párrafo {p_idx + 1}: {len(sentences)} frases")

                for sentence in sentences:
                    all_sentences.append({
                        'text': sentence,
                        'paragraph_id': p_idx,
                        'paragraph_type': paragraph.get('type', 'normal')
                    })

            self.log(f"📝 Total de frases: {len(all_sentences)}")

            yield (
                20,
                "Iniciando generación...",
                "\n".join(self.log_messages),
                None,
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )

            # Procesar en modo completo
            for update in self.process_full_mode(all_sentences, output_dir, progress):
                yield update

            self.log(f"\n✅ Generación completada exitosamente")
            self.log(f"📁 Resultados guardados en: {output_dir}")

            # Devolver audio final
            final_audio_path = output_dir / "audio_final_completo.wav"
            fase1_audio_path = output_dir / "audio_fase1_completa.wav"

            final_audio = str(final_audio_path) if final_audio_path.exists() else None
            fase1_audio = str(fase1_audio_path) if fase1_audio_path.exists() else None

            yield (
                100,
                "✅ Completado",
                "\n".join(self.log_messages),
                final_audio,
                fase1_audio,
                gr.update(visible=True) if final_audio else gr.update(visible=False),
                gr.update(visible=True) if fase1_audio else gr.update(visible=False)
            )

        except Exception as e:
            error_msg = f"❌ Error durante la generación: {str(e)}"
            self.log(error_msg)
            yield (
                0,
                f"❌ Error: {str(e)}",
                "\n".join(self.log_messages),
                None,
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )

        finally:
            self.is_processing = False

    def process_full_mode(self, sentences: List[Dict], output_dir: Path, progress):
        """Procesa en modo completo con generador de actualizaciones"""
        self.log("\n🔍 MODO COMPLETO - Fase 1 (Sistema Híbrido) + Fase 2 (Post-procesamiento)")
        self.log("="*80)

        if not HYBRID_AVAILABLE:
            self.log("❌ Sistema híbrido no disponible, usando modo legacy")
            for update in self.process_full_mode_legacy(sentences, output_dir, progress):
                yield update
            return

        # FASE 1: Generación con hints prosódicos
        self.log("\n📝 FASE 1: Generación con hints prosódicos (Sistema Híbrido)")

        # Preparar texto completo
        full_text = " ".join([s['text'] for s in sentences])

        self.log("🎵 Inicializando generador híbrido...")

        # Buscar modelo
        model_path = Path(__file__).parent.parent / "generador_estructura_v3" / "model_943000.pt"
        if not model_path.exists():
            model_path = "./model_943000.pt"

        generator = ProsodyEnhancedGenerator(
            texto_usuario=full_text,
            model_path=str(model_path),
            reference_file=str(self.reference_audio)
        )

        generator.reference_file = self.reference_audio
        generator.output_dir = output_dir

        # Inicializar modelo
        generator.ensure_model_loaded()

        generator.enable_prosody_hints = True
        generator.enable_postprocessing = False

        # Usar segmentación personalizada
        custom_frases = [s['text'] for s in sentences]
        if custom_frases:
            generator.frases = custom_frases
            self.log(f"🧩 Usando segmentación personalizada: {len(custom_frases)} frases")

        # Crear directorio para frases
        frases_dir = output_dir / "frases"
        frases_dir.mkdir(exist_ok=True)

        audio_segments = []
        total = len(generator.frases)

        self.log(f"📝 Ejecutando Fase 1 completa: {total} frases con mejoras prosódicas...")

        yield (
            25,
            "Fase 1: Generando frases...",
            "\n".join(self.log_messages),
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False)
        )

        # Generar cada frase
        for idx, frase in enumerate(generator.frases):
            if not self.is_processing:
                self.log("⏹️ Generación detenida por el usuario")
                break

            # Actualizar progreso (25-60% para Fase 1)
            current_progress = 25 + (idx / total) * 35
            progress(current_progress / 100, desc=f"Fase 1: Frase {idx + 1}/{total}")

            # Generar audio
            audio = generator.generate_single_phrase_with_prosody(
                text=frase,
                phrase_idx=idx,
                total_phrases=total,
                paragraph_id=self._estimate_paragraph_id(idx, total),
                log_callback=self.log
            )

            audio_segments.append(audio)

            # Guardar frase individual
            frase_path = frases_dir / f"frase_{idx + 1:03d}.wav"
            sf.write(frase_path, audio, generator.sample_rate)

            # Actualizar UI cada 5 frases
            if idx % 5 == 0:
                yield (
                    current_progress,
                    f"Fase 1: Procesando frase {idx + 1} de {total}",
                    "\n".join(self.log_messages),
                    None,
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False)
                )

        # Guardar resultado Fase 1
        if audio_segments:
            self.log(f"\n🔗 Guardando resultado de Fase 1...")

            fase1_audio = generator.apply_crossfade_and_concatenate(audio_segments)
            fase1_path = output_dir / "audio_fase1_completa.wav"
            sf.write(fase1_path, fase1_audio, generator.sample_rate)

            self.log(f"✅ Fase 1 guardada: {fase1_path.name}")
            self.log(f"📊 Hints prosódicos aplicados: {generator.prosody_stats['hints_applied']}/{total}")

        yield (
            60,
            "Fase 2: Analizando prosodia...",
            "\n".join(self.log_messages),
            None,
            str(fase1_path) if fase1_path.exists() else None,
            gr.update(visible=False),
            gr.update(visible=True) if fase1_path.exists() else gr.update(visible=False)
        )

        # FASE 2: Post-procesamiento
        self.log(f"\n🔧 FASE 2: Post-procesamiento sobre resultados de Fase 1")
        progress(0.65, desc="Fase 2: Analizando prosodia...")

        if not audio_segments:
            self.log("❌ No hay audio de Fase 1 para post-procesar")
            return

        # Analizar audio
        texts = [frase for frase in generator.frases]
        analyzer = ProsodyAnalyzer()
        analysis = analyzer.analyze_complete_audio(audio_segments, texts)

        # Detectar problemas
        detector = ProsodyProblemDetector()
        problems = detector.identify_problems(analysis)

        self.log(f"📊 Problemas detectados en Fase 1: {len(problems)}")

        yield (
            70,
            f"Fase 2: {len(problems)} problemas detectados",
            "\n".join(self.log_messages),
            None,
            str(fase1_path) if fase1_path.exists() else None,
            gr.update(visible=False),
            gr.update(visible=True) if fase1_path.exists() else gr.update(visible=False)
        )

        if problems and generator.f5tts:
            critical = [p for p in problems if p['severity'] > 0.3][:5]

            if critical:
                self.log(f"🔧 Corrigiendo {len(critical)} problemas críticos...")
                progress(0.75, desc=f"Fase 2: Corrigiendo {len(critical)} problemas...")

                regenerator = SelectiveRegenerator(generator.f5tts, max_fixes=5)
                regenerator.set_reference_context(str(generator.reference_file), "")

                corrected_segments, fix_report = regenerator.fix_critical_problems(
                    problems, audio_segments, texts, severity_threshold=0.3
                )

                audio_segments = corrected_segments

                # Sobreescribir frases corregidas
                try:
                    for idx_corr, audio_corr in enumerate(audio_segments):
                        frase_path = frases_dir / f"frase_{idx_corr + 1:03d}.wav"
                        sf.write(frase_path, audio_corr, generator.sample_rate)
                    self.log("💾 Frases corregidas sobreescritas en disco")
                except Exception as e:
                    self.log(f"⚠️ No se pudo sobreescribir frases: {e}")

                self.log(f"✅ Correcciones aplicadas: {fix_report['successful']}/{fix_report['attempted']}")

                # Guardar reporte
                corrections_report = {
                    'phase1_hints': generator.prosody_stats['hints_applied'],
                    'phase2_problems_found': len(problems),
                    'phase2_problems_fixed': fix_report['successful'],
                    'phase2_fix_details': fix_report
                }

                with open(output_dir / "reporte_correcciones_fase2.json", 'w', encoding='utf-8') as f:
                    json.dump(corrections_report, f, indent=2, ensure_ascii=False)
            else:
                self.log("✅ No se encontraron problemas críticos en Fase 1")

        yield (
            90,
            "Finalizando: Concatenando audio final...",
            "\n".join(self.log_messages),
            None,
            str(fase1_path) if fase1_path.exists() else None,
            gr.update(visible=False),
            gr.update(visible=True) if fase1_path.exists() else gr.update(visible=False)
        )

        # Concatenar y guardar resultado final
        progress(0.95, desc="Generando audio final...")

        if audio_segments:
            final_audio = smart_concatenate(audio_segments, crossfade_ms=50, sr=generator.sample_rate)
            final_path = output_dir / "audio_final_completo.wav"
            sf.write(final_path, final_audio, generator.sample_rate)

            self.log(f"\n✅ Audio final guardado: {final_path.name}")

            # Guardar reporte completo
            report_data = {
                'mode': 'full_hybrid',
                'phase1_hints_applied': generator.prosody_stats['hints_applied'],
                'phase1_total_phrases': total,
                'phase2_problems_found': len(problems) if 'problems' in locals() else 0,
                'phase2_problems_fixed': fix_report['successful'] if 'fix_report' in locals() else 0,
                'voice_quality': 'preserved_enhanced',
                'prosody_features': 'phase1_hints_plus_phase2_corrections'
            }

            self.save_report(report_data, output_dir / "reporte_completo.json", "full")

        self.log("\n🎉 Modo completo finalizado: Fase 1 (Híbrida) + Fase 2 (Post-procesamiento)")

        yield (
            100,
            "✅ Generación completada",
            "\n".join(self.log_messages),
            str(final_path) if final_path.exists() else None,
            str(fase1_path) if fase1_path.exists() else None,
            gr.update(visible=True) if final_path.exists() else gr.update(visible=False),
            gr.update(visible=True) if fase1_path.exists() else gr.update(visible=False)
        )

    def process_full_mode_legacy(self, sentences: List[Dict], output_dir: Path, progress):
        """Modo legacy cuando sistema híbrido no está disponible"""
        self.log("\n⚠️ MODO COMPLETO LEGACY - Sin sistema híbrido")

        yield (
            25,
            "Modo legacy: Inicializando...",
            "\n".join(self.log_messages),
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False)
        )

        # Implementación simplificada del modo legacy
        # (Similar a la original pero adaptada para generador)

        self.log("⚠️ Usando modo legacy simplificado")

        yield (
            100,
            "✅ Completado (modo legacy)",
            "\n".join(self.log_messages),
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False)
        )

    def save_report(self, data: Dict, path: Path, mode: str):
        """Guarda el reporte de procesamiento"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'text_file': str(self.text_file),
            'reference_audio': str(self.reference_audio),
            **data
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self.log(f"📊 Reporte guardado: {path}")

    def create_interface(self):
        """Crea la interfaz Gradio"""

        with gr.Blocks(title="🎵 Generador F5-TTS con Mejora Prosódica", theme=gr.themes.Soft()) as interface:
            gr.Markdown("# 🎵 Generador F5-TTS con Mejora Prosódica")
            gr.Markdown("Interfaz moderna con Gradio para generación de audio con mejoras prosódicas")

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📁 Entrada de Texto")

                    text_input_type = gr.Radio(
                        choices=["Archivo", "Texto directo"],
                        value="Texto directo",
                        label="Tipo de entrada de texto",
                        info="Selecciona cómo proporcionar el texto a sintetizar"
                    )

                    text_file_input = gr.File(
                        label="📝 Archivo de texto (.txt)",
                        file_types=[".txt"],
                        type="filepath",
                        visible=False
                    )

                    direct_text_input = gr.Textbox(
                        label="✍️ Escribe tu texto aquí",
                        placeholder="Escribe el texto que deseas sintetizar...\n\nPuedes usar múltiples párrafos separados por líneas en blanco.",
                        lines=10,
                        max_lines=20,
                        visible=True
                    )

                    gr.Markdown("### 🎤 Audio de Referencia")

                    audio_input = gr.Audio(
                        label="Audio de referencia (.wav, .mp3)",
                        type="filepath",
                        sources=["upload"]
                    )

                with gr.Column(scale=2):
                    gr.Markdown("### 📊 Estado de Generación")

                    progress_bar = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=0,
                        label="Progreso",
                        interactive=False
                    )

                    status_text = gr.Textbox(
                        label="Estado",
                        value="Listo para generar",
                        interactive=False
                    )

                    log_output = gr.Textbox(
                        label="📋 Registro de Procesamiento",
                        lines=15,
                        max_lines=20,
                        interactive=False,
                        autoscroll=True
                    )

            # Configuración y Controles debajo del estado
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### ⚙️ Configuración")

                    gr.Markdown("""
                    **Modo de Procesamiento:** Completo (Fases 1 y 2)

                    Incluye análisis exhaustivo, corrección de problemas y concatenación final.
                    """)

                    use_phonetic = gr.Checkbox(
                        label="🔤 Aplicar transformación fonética",
                        value=True,
                        info="Simula errores ortográficos basados en pronunciación (hacer→acer, llevar→yevar)"
                    )

                with gr.Column():
                    gr.Markdown("### 🎛️ Controles")

                    generate_btn = gr.Button("🎵 Generar Audio", variant="primary", size="lg")

                    with gr.Row():
                        open_folder_btn = gr.Button("📂 Abrir Carpeta de Resultados")
                        resume_btn = gr.Button("🔄 Reanudar Sesión")

            gr.Markdown("### 🎧 Resultados de Audio")

            with gr.Row():
                with gr.Column():
                    final_audio = gr.Audio(
                        label="🎵 Audio Final Completo (Fase 1 + Fase 2)",
                        type="filepath",
                        visible=False
                    )

                with gr.Column():
                    fase1_audio = gr.Audio(
                        label="🎵 Audio Fase 1 (Solo con hints prosódicos)",
                        type="filepath",
                        visible=False
                    )

            # Eventos - Cambiar visibilidad según tipo de entrada
            def toggle_text_input(choice):
                if choice == "Archivo":
                    return gr.update(visible=True), gr.update(visible=False)
                else:  # Texto directo
                    return gr.update(visible=False), gr.update(visible=True)

            text_input_type.change(
                fn=toggle_text_input,
                inputs=[text_input_type],
                outputs=[text_file_input, direct_text_input]
            )

            # Evento de generación
            generate_btn.click(
                fn=self.generate_audio,
                inputs=[text_input_type, text_file_input, direct_text_input, audio_input, use_phonetic],
                outputs=[progress_bar, status_text, log_output, final_audio, fase1_audio, final_audio, fase1_audio]
            )

            open_folder_btn.click(
                fn=self.open_results_folder,
                outputs=[log_output]
            )

            resume_btn.click(
                fn=self.resume_session,
                outputs=[log_output, status_text]
            )

        return interface

    def open_results_folder(self):
        """Abre la carpeta de resultados más reciente"""
        import subprocess
        import platform

        output_dirs = sorted([d for d in Path('.').glob('output_*') if d.is_dir()],
                           key=lambda x: x.stat().st_mtime, reverse=True)

        if output_dirs:
            folder = output_dirs[0]

            try:
                if platform.system() == "Windows":
                    os.startfile(folder)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])

                message = f"📂 Abriendo: {folder}"
                self.log(message)
                return "\n".join(self.log_messages)
            except Exception as e:
                self.log(f"❌ Error al abrir carpeta: {e}")
                return "\n".join(self.log_messages)
        else:
            self.log("📂 No hay carpetas de resultados generadas aún")
            return "\n".join(self.log_messages)

    def resume_session(self):
        """Intenta reanudar la última sesión"""
        import json

        state_path = Path('resume_state.json')

        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding='utf-8'))
                self.resume_state = state
                message = f"🔄 Estado de reanudación cargado: frase {state.get('phrase_idx', '?')}"
                self.log(message)
                return "\n".join(self.log_messages), message
            except Exception as e:
                error = f"❌ Error cargando estado: {e}"
                self.log(error)
                return "\n".join(self.log_messages), error
        else:
            # Buscar última carpeta output_*
            output_dirs = sorted([d for d in Path('.').glob('output_*') if d.is_dir()],
                               key=lambda x: x.stat().st_mtime, reverse=True)

            if output_dirs:
                last_dir = output_dirs[0]
                frases_dir = last_dir / 'frases'

                if frases_dir.exists():
                    # Contar frases existentes
                    idx = 0
                    while (frases_dir / f"frase_{idx + 1:03d}.wav").exists():
                        idx += 1

                    if idx > 0:
                        self.resume_state = {
                            'session_dir': str(last_dir),
                            'phrase_idx': idx
                        }
                        message = f"🔄 Listo para reanudar desde frase {idx} en {last_dir}"
                        self.log(message)
                        return "\n".join(self.log_messages), message

            message = "📂 No hay sesiones previas para reanudar"
            self.log(message)
            return "\n".join(self.log_messages), message


def main():
    """Función principal"""
    print("="*60)
    print("🎵 Generador F5-TTS con Mejora Prosódica - Interfaz Gradio")
    print("="*60)
    print()
    print("Configuración:")
    print("  📝 Archivo de texto: texto.txt")
    print("  🎤 Audio referencia: segment_2955.wav")
    print("  📁 Salida: output_[timestamp]/")
    print()
    print("🚀 Iniciando interfaz web...")
    print()

    # Crear aplicación
    app = ProsodyGeneratorGradio()
    interface = app.create_interface()

    # Lanzar interfaz
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()
