#!/usr/bin/env python3
"""
Generador F5-TTS con Mejora Prosódica - Versión Simplificada con GUI
Usa siempre segment_2955.wav como referencia y texto.txt como entrada
Crea directorio único con timestamp para cada generación
GUI para seleccionar modo de procesamiento
"""

import os
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from typing import List, Dict, Optional, Tuple
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json

# Importar módulos necesarios
from core.prosody_processor import (
    ProsodyOrchestrator,
    ProsodyHintGenerator,
    ProsodyAnalyzer,
    ProsodyProblemDetector,
    SelectiveRegenerator,
    smart_concatenate,
    export_prosody_report
)

# Importar transformador fonético
from core.phonetic_processor import SpanishPhoneticTransformer

# Importar sistema híbrido
try:
    from tts_generator import ProsodyEnhancedGenerator
    HYBRID_AVAILABLE = True
    print("✅ Sistema híbrido cargado")
except ImportError as e:
    print(f"⚠️ Sistema híbrido no disponible: {e}")
    HYBRID_AVAILABLE = False

# Intentar importar F5-TTS
try:
    from f5_tts.api import F5TTS
    F5_AVAILABLE = True
except ImportError:
    print("⚠️ F5-TTS no disponible. Usando modo demo.")
    F5_AVAILABLE = False


class F5ProsodyAdapter:
    """
    Adaptador que conecta el sistema de mejora prosódica con F5-TTS
    """

    def __init__(self,
                 reference_audio: str = "segment_2955.wav",
                 model_type: str = "F5-TTS",
                 device: str = "cuda",
                 sample_rate: int = 44100):
        """
        Args:
            reference_audio: Siempre segment_2955.wav
            model_type: Tipo de modelo F5
            device: Dispositivo de procesamiento
            sample_rate: Frecuencia de muestreo
        """

        self.reference_audio = Path(reference_audio)
        self.sample_rate = sample_rate
        self.device = device

        # Verificar que existe el audio de referencia
        if not self.reference_audio.exists():
            raise FileNotFoundError(f"❌ Audio de referencia no encontrado: {self.reference_audio}")

        # Inicializar F5-TTS si está disponible
        if F5_AVAILABLE:
            print(f"🎤 Inicializando F5-TTS con referencia: {self.reference_audio.name}")
            self.f5tts = F5TTS(
                model_type=model_type,
                device=device
            )
        else:
            print("⚠️ Usando generador demo")
            self.f5tts = None

        # Inicializar generador de hints prosódicos
        self.hint_generator = ProsodyHintGenerator()

        # Parámetros F5 base (RESTAURADOS a valores originales)
        self.base_params = {
            'nfe_step': 32,
            'sway_sampling_coef': -0.5,
            'cfg_strength': 2.0,
            'speed': 1.0,
            'remove_silence': False,
            'seed': -1
        }

        # Parámetros de fallback para cuando aparece el error específico
        self.fallback_params = {
            'nfe_step': 24,  # Valor muy conservador
            'sway_sampling_coef': -0.1,  # Valor mínimo
            'cfg_strength': 1.5,  # Valor conservador
            'speed': 1.0,
            'remove_silence': False,
            'seed': -1
        }

    def _handle_critical_error(self, error_msg: str, context: str = "", log_callback=None, allow_continue: bool = False):
        """
        Maneja el error crítico 't must be strictly increasing'.
        Si allow_continue=True, solo registra y devuelve sin terminar el proceso para permitir fallbacks.
        """
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        critical_log = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           🚨 ERROR CRÍTICO DETECTADO 🚨                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Timestamp: {timestamp}                                              ║
║ Contexto:  {context:<60} ║
║ Error:     {error_msg[:60]:<60} ║
║                                                                               ║
║ 📋 INFORMACIÓN DEL ERROR:                                                     ║
║ • Problemas de interpolación temporal en F5-TTS                               ║
║ • Generalmente causado por parámetros extremos o texto problemático          ║
║ • {'Se permite continuar con fallbacks' if allow_continue else 'Se recomienda terminar'}                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

        print(critical_log)

        if log_callback:
            log_callback("🚨 ERROR CRÍTICO: 't must be strictly increasing or decreasing'")
            if allow_continue:
                log_callback("↪️ Continuando con fallbacks seguros…")
            else:
                log_callback("🛑 TERMINANDO EJECUCIÓN para evitar bucle infinito")
            log_callback(f"⏰ Tiempo: {timestamp}")
            log_callback(f"📍 Contexto: {context}")

        # Guardar log en archivo
        try:
            log_file = "/home/lorty/m2/ROYERBIN/Spanish-F5/generador_estructura_v3_previo/error_critico.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(critical_log + "\n\n")
            print(f"📄 Log guardado en: {log_file}")
            if log_callback:
                log_callback(f"📄 Log guardado en: {log_file}")
        except:
            pass

        if not allow_continue:
            import sys
            sys.exit(1)

        # Estadísticas
        self.stats = {
            'generation_times': [],
            'hints_applied': 0,
            'total_phrases': 0
        }

    def generate_single_with_prosody(self,
                                    text: str,
                                    phrase_idx: int,
                                    total_phrases: int,
                                    paragraph_id: Optional[int] = None,
                                    log_callback=None) -> np.ndarray:
        """
        Genera una frase con hints prosódicos aplicados
        VERSIÓN CORREGIDA: Manejo robusto del error 't must be strictly increasing'
        """

        start_time = time.time()
        self.stats['total_phrases'] += 1

        # NUEVO: Límite de reintentos para evitar bucles infinitos
        MAX_RETRIES = 3
        retry_count = 0

        # Detectar y corregir texto problemático ANTES de procesar
        original_text = text

        # Corregir "bibienda" -> "vivienda" si existe
        text = text.replace("bibienda", "vivienda")

        # Asegurar signos de interrogación españoles
        if text.endswith('?') and '¿' not in text:
            text = '¿' + text

        # Si es una pregunta larga sin comas, dividirla preventivamente
        if '?' in text and len(text) > 80 and ',' not in text:
            # Buscar punto natural de división
            palabras = text.split()
            if len(palabras) > 8:
                # Dividir aproximadamente a la mitad
                punto_division = len(palabras) // 2
                parte1 = ' '.join(palabras[:punto_division])
                parte2 = ' '.join(palabras[punto_division:])

                # Generar cada parte por separado
                if log_callback:
                    log_callback(f"⚠️ Dividiendo pregunta larga preventivamente: {len(text)} chars")
                    log_callback(f"   Parte 1: {parte1}")
                    log_callback(f"   Parte 2: {parte2}")

                audio1 = self._generate_safe_audio(parte1, phrase_idx, log_callback, retry_count)
                audio2 = self._generate_safe_audio(parte2, phrase_idx, log_callback, retry_count)

                # Concatenar con pequeña pausa
                pausa = np.zeros(int(0.2 * self.sample_rate))
                return np.concatenate([audio1, pausa, audio2])

        # Obtener hints prosódicos
        hints = self.hint_generator.prepare_text_for_generation(
            text,
            phrase_idx,
            total_phrases,
            paragraph_id
        )

        # Preparar parámetros de generación
        generation_params = self.base_params.copy()

        # Aplicar modificaciones si es posición crítica
        if hints['apply_modifications']:
            self.stats['hints_applied'] += 1
            text_to_generate = hints['text']

            # Aplicar ajustes de parámetros PERO con límites seguros
            if 'extra_params' in hints:
                if 'nfe_adjustment' in hints['extra_params']:
                    # Limitar ajuste para evitar valores problemáticos
                    adjustment = max(-8, min(8, hints['extra_params']['nfe_adjustment']))
                    generation_params['nfe_step'] = max(24, min(40, generation_params['nfe_step'] + adjustment))

                if 'sway_adjustment' in hints['extra_params']:
                    adjustment = max(-0.2, min(0.2, hints['extra_params']['sway_adjustment']))
                    generation_params['sway_sampling_coef'] = max(-0.6, min(-0.2, generation_params['sway_sampling_coef'] + adjustment))

                if 'cfg_adjustment' in hints['extra_params']:
                    adjustment = max(-0.3, min(0.3, hints['extra_params']['cfg_adjustment']))
                    generation_params['cfg_strength'] = max(1.5, min(2.2, generation_params['cfg_strength'] + adjustment))

            msg = f"🎯 Frase {phrase_idx + 1}: Aplicando hints prosódicos (Párrafo {paragraph_id + 1})"
            if log_callback:
                log_callback(msg)
        else:
            text_to_generate = text

        # Intentar generar con reintentos limitados
        while retry_count < MAX_RETRIES:
            try:
                # Limpiar texto antes de enviar al motor
                text_to_generate = self._clean_text_for_engine(text_to_generate)

                if self.f5tts is None:
                    return self._generate_fallback(text_to_generate)

                # Usar parámetros cada vez más conservadores en cada reintento
                if retry_count > 0:
                    params_to_use = self._get_retry_params(retry_count)
                    if log_callback:
                        log_callback(f"🔄 Reintento {retry_count} con parámetros conservadores")
                else:
                    params_to_use = generation_params

                wav, sr, _ = self.f5tts.infer(
                    ref_file=str(self.reference_audio),
                    ref_text="",
                    gen_text=text_to_generate,
                    **params_to_use
                )

                if wav is not None and len(wav) > 0:
                    if np.max(np.abs(wav)) > 0:
                        wav = wav / np.max(np.abs(wav)) * 0.9

                    generation_time = time.time() - start_time
                    self.stats['generation_times'].append(generation_time)
                    return wav
                else:
                    return self._generate_fallback(text_to_generate)

            except Exception as e:
                error_msg = str(e)

                if "must be strictly increasing" in error_msg:
                    # Si tenemos un fallback planificado, permitir continuar
                    self._handle_critical_error(
                        error_msg,
                        f"generate_single_with_prosody - frase {phrase_idx + 1} - intento {retry_count + 1}",
                        log_callback,
                        allow_continue=True
                    )
                    # Intentar ruta segura inmediatamente
                    try:
                        return self._generate_safe_audio(text_to_generate, phrase_idx, log_callback, retry_count)
                    except Exception:
                        # Si la ruta segura también falla, entonces abortar definitivamente
                        self._handle_critical_error(
                            error_msg,
                            f"safe_fallback_failed - frase {phrase_idx + 1}",
                            log_callback,
                            allow_continue=False
                        )
                        return self._generate_fallback(text_to_generate)
                else:
                    # Otros errores, usar fallback
                    if log_callback:
                        log_callback(f"❌ Error no recuperable: {error_msg}")
                    return self._generate_fallback(text_to_generate)

        # Si llegamos aquí, usar fallback
        return self._generate_fallback(text_to_generate)

    def _make_safe_params(self, params: dict) -> dict:
        """Limita los parámetros a valores seguros para evitar error 't must be strictly increasing'"""
        safe = params.copy()

        # Limitar cada parámetro crítico a rangos seguros
        if 'nfe_step' in safe:
            safe['nfe_step'] = min(32, max(16, int(safe['nfe_step'])))  # Entre 16 y 32

        if 'speed' in safe:
            safe['speed'] = max(0.85, min(1.15, float(safe['speed'])))  # Entre 0.85 y 1.15

        if 'sway_sampling_coef' in safe:
            safe['sway_sampling_coef'] = max(-0.4, min(0.4, float(safe['sway_sampling_coef'])))  # Entre -0.4 y 0.4

        if 'cfg_strength' in safe:
            safe['cfg_strength'] = max(1.0, min(2.2, float(safe['cfg_strength'])))  # Entre 1.0 y 2.2

        return safe

    def _clean_text_for_engine(self, text: str) -> str:
        """Limpia el texto para evitar problemas con el motor"""
        import re

        # Normalizar puntos suspensivos (… o ... -> .)
        text = text.replace('\u2026', '...')
        text = re.sub(r'\.{3,}', '.', text)

        # Correcciones básicas de ortografía abreviada/común que desestabiliza el motor
        # (Se aplican sólo al texto enviado al motor; el texto mostrado puede conservarse aparte)
        replacements = {
            r"\bke\b": "que",
            r"\bk\b": "que",
            r"\beyos\b": "ellos",
            r"\bexijen\b": "exigen",
        }
        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

        # Eliminar signos de apertura españoles que pueden causar problemas
        text = re.sub(r'^[¿¡]+', '', text)

        # Asegurar que no termine en coma o punto y coma
        text = re.sub(r'[,;]+$', '.', text)

        # Eliminar puntuación duplicada
        text = re.sub(r'([.!?]){2,}', r'\1', text)

        # Si es pregunta muy larga, convertir a afirmación
        if text.endswith('?') and len(text) > 100:
            text = text.rstrip('?') + '.'

        # Asegurar puntuación final válida
        if not re.search(r'[.!?]$', text.strip()):
            text = text.strip() + '.'

        return text.strip()

    def _get_retry_params(self, retry_count: int) -> dict:
        """Obtiene parámetros cada vez más conservadores para reintentos"""
        if retry_count == 1:
            return {
                'nfe_step': 28,
                'sway_sampling_coef': -0.3,
                'cfg_strength': 1.8,
                'speed': 1.0,
                'remove_silence': False,
                'seed': 42  # Seed fijo para reproducibilidad
            }
        elif retry_count == 2:
            return {
                'nfe_step': 24,
                'sway_sampling_coef': -0.2,
                'cfg_strength': 1.5,
                'speed': 1.0,
                'remove_silence': False,
                'seed': 123
            }
        else:  # retry_count >= 3
            return {
                'nfe_step': 20,  # Mínimo absoluto
                'sway_sampling_coef': -0.1,
                'cfg_strength': 1.2,
                'speed': 1.0,
                'remove_silence': False,
                'seed': 456
            }

    def _generate_safe_audio(self, text: str, phrase_idx: int, log_callback, retry_count: int) -> np.ndarray:
        """Genera audio de forma segura con parámetros conservadores"""
        safe_params = {
            'nfe_step': 24,
            'sway_sampling_coef': -0.2,
            'cfg_strength': 1.5,
            'speed': 1.0,
            'remove_silence': False,
            'seed': 42
        }

        try:
            text_clean = self._clean_text_for_engine(text)

            wav, sr, _ = self.f5tts.infer(
                ref_file=str(self.reference_audio),
                ref_text="",
                gen_text=text_clean,
                **safe_params
            )

            if wav is not None and len(wav) > 0:
                if np.max(np.abs(wav)) > 0:
                    wav = wav / np.max(np.abs(wav)) * 0.9
                return wav
        except Exception as e:
            if "must be strictly increasing" in str(e):
                self._handle_critical_error(
                    str(e),
                    f"_generate_safe_audio - texto: {text[:30]}...",
                    log_callback
                )

        return self._generate_fallback(text)

    def _generate_fallback(self, text: str) -> np.ndarray:
        """Genera audio de fallback para testing"""
        duration = len(text) * 0.05
        samples = int(duration * self.sample_rate)
        t = np.linspace(0, duration, samples)
        frequency = 200 + np.random.randn() * 20
        audio = np.sin(2 * np.pi * frequency * t) * 0.3
        return audio

    # === Salvaguardas adicionales para estabilidad del motor en modo legacy ===
    def _prepare_text_for_engine(self, text: str, aggressive: bool = False) -> str:
        import re
        s = (text or '').strip()
        # Quitar signos invertidos al inicio; mantener ?/! finales
        s = re.sub(r'^[¡¿]+', '', s)
        # Limpiar puntuación final conflictiva
        s = re.sub(r'[,:;]+\s*$', '.', s)
        # Colapsar signos repetidos
        s = re.sub(r'([.!?])\1{1,}', r'\1', s)
        # Evitar terminar en coma
        s = re.sub(r',\s*$', '.', s)
        if aggressive:
            s = re.sub(r'["""]', '', s)
            s = re.sub(r'\s[\-–—]\s', ' ', s)
            if not s.endswith(('.', '!', '?')):
                s = s.rstrip() + '.'
        return s.strip()

    def _is_risky_text_for_engine(self, s: str) -> bool:
        s_clean = (s or '').strip()
        if len(s_clean) == 0:
            return True
        if s_clean.endswith('?') and len(s_clean) > 90:
            return True
        if '??' in s_clean or '!!' in s_clean:
            return True
        if any(c in s_clean for c in [';', ':', '—', '–']) and len(s_clean) > 80:
            return True
        return False

    def _split_text_for_engine(self, text: str, max_words: int = 12) -> list:
        import re
        s = (text or '').strip()
        if len(s.split()) <= max_words:
            return [s]
        commas = [m.start() for m in re.finditer(r',', s)]
        target = len(s) // 2
        if commas:
            split_pos = min(commas, key=lambda x: abs(x - target))
            left = s[:split_pos+1].strip()
            right = s[split_pos+1:].strip()
            if not left.endswith(('.', '!', '?')):
                left = left.rstrip(',') + '.'
            result = [left, right]
        else:
            connector = re.search(r'\s(y|pero|porque|aunque|entonces|así que|o)\s', s)
            if connector:
                pos = connector.start(0) + 1
                left = s[:pos].strip()
                right = s[pos:].strip()
                if not left.endswith(('.', '!', '?')):
                    left += '.'
                result = [left, right]
            else:
                words = s.split()
                mid = len(words) // 2
                left = ' '.join(words[:mid]).strip()
                right = ' '.join(words[mid:]).strip()
                if not left.endswith(('.', '!', '?')):
                    left += '.'
                result = [left, right]
        final = []
        for part in result:
            if len(part.split()) > max_words:
                final.extend(self._split_text_for_engine(part, max_words))
            else:
                final.append(part)
        return final

    def _engine_generate_in_parts(self, text: str, generation_params: dict, log_callback=None):
        parts = self._split_text_for_engine(text)
        audio_segments = []
        for i, p in enumerate(parts):
            try:
                p_prepared = self._prepare_text_for_engine(p)
                # Intentar con parámetros normales primero
                wav, sr, _ = self.f5tts.infer(
                    ref_file=str(self.reference_audio),
                    ref_text="",
                    gen_text=p_prepared,
                    **generation_params
                )
                if wav is None or len(wav) == 0 or not np.isfinite(wav).all():
                    # Reintento agresivo
                    p_safe = self._prepare_text_for_engine(p_prepared, aggressive=True)
                    wav, sr, _ = self.f5tts.infer(
                        ref_file=str(self.reference_audio),
                        ref_text="",
                        gen_text=p_safe,
                        **generation_params
                    )
                if wav is not None and len(wav) > 0:
                    if np.max(np.abs(wav)) > 0:
                        wav = wav / np.max(np.abs(wav)) * 0.9
                    audio_segments.append(wav)
            except Exception as e:
                if log_callback:
                    log_callback(f"❌ Parte {i+1}/{len(parts)} falló (legacy): {e}")

                # Si es el error específico, TERMINAR INMEDIATAMENTE
                if "must be strictly increasing" in str(e):
                    self._handle_critical_error(
                        str(e),
                        f"_engine_generate_in_parts - parte {i+1}/{len(parts)}",
                        log_callback
                    )
                    # Esta línea nunca se ejecuta
                    continue

                continue
        if not audio_segments:
            return self._generate_fallback(text)
        try:
            return np.concatenate(audio_segments)
        except Exception:
            return audio_segments[0]


class ProsodyGeneratorGUI:
    """
    GUI para el generador con mejora prosódica
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎵 Generador F5-TTS con Mejora Prosódica")
        self.root.geometry("900x750")

        # Variables
        self.processing_mode = tk.StringVar(value="full")
        self.use_phonetic = tk.BooleanVar(value=True)  # Nueva variable para transformación fonética - HABILITADA POR DEFECTO
        self.is_processing = False
        self.current_thread = None
        self.resume_state = None  # Estado de reanudación si existe

        # Paths predeterminados
        self.text_file = Path("texto.txt")
        self.reference_audio = Path("segment_2955.wav")

        # Transformador fonético
        self.phonetic_transformer = SpanishPhoneticTransformer()

        self.setup_ui()
        self.check_files()

    def setup_ui(self):
        """Configura la interfaz gráfica"""

        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Título
        title_label = ttk.Label(main_frame, text="🎵 Generador F5-TTS con Mejora Prosódica",
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)

        # Información de archivos
        info_frame = ttk.LabelFrame(main_frame, text="📁 Archivos de Entrada", padding="10")
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(info_frame, text="📝 Texto:").grid(row=0, column=0, sticky=tk.W)
        self.text_label = ttk.Label(info_frame, text=str(self.text_file), foreground="blue")
        self.text_label.grid(row=0, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_frame, text="🎤 Audio Referencia:").grid(row=1, column=0, sticky=tk.W)
        self.audio_label = ttk.Label(info_frame, text=str(self.reference_audio), foreground="blue")
        self.audio_label.grid(row=1, column=1, sticky=tk.W, padx=10)

        # Modo de procesamiento
        mode_frame = ttk.LabelFrame(main_frame, text="⚙️ Modo de Procesamiento", padding="10")
        mode_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        # Modo único: Completo (Fases 1 y 2)
        ttk.Label(mode_frame,
                  text="🔍 Modo único: Completo (Fases 1 y 2 - Con post-procesamiento)",
                  foreground="black").grid(row=0, column=0, sticky=tk.W)
        self.mode_description = ttk.Label(mode_frame,
                                          text="Incluye análisis exhaustivo, corrección de problemas y concatenación final.",
                                          foreground="gray", wraplength=800)
        self.mode_description.grid(row=1, column=0, pady=10)

        # Opción de transformación fonética
        phonetic_frame = ttk.LabelFrame(main_frame, text="🔤 Transformación Fonética", padding="10")
        phonetic_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        self.phonetic_checkbox = ttk.Checkbutton(
            phonetic_frame,
            text="Aplicar transformación fonética al texto (simula errores ortográficos basados en pronunciación)",
            variable=self.use_phonetic,
            command=self.on_phonetic_change
        )
        self.phonetic_checkbox.grid(row=0, column=0, sticky=tk.W)

        self.phonetic_description = ttk.Label(
            phonetic_frame,
            text="Transforma: hacer→acer, llevar→yevar, vez→bes (betacismo/yeísmo/seseo)",
            foreground="gray",
            font=('Arial', 9)
        )
        self.phonetic_description.grid(row=1, column=0, sticky=tk.W, padx=20, pady=5)

        # Botones de control
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=20)

        self.generate_button = ttk.Button(button_frame, text="🎵 Generar Audio",
                                         command=self.start_generation,
                                         style="Accent.TButton")
        self.generate_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(button_frame, text="⏹️ Detener",
                                      command=self.stop_generation,
                                      state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)

        ttk.Button(button_frame, text="📂 Abrir Resultados",
                  command=self.open_results_folder).grid(row=0, column=2, padx=5)

        ttk.Button(button_frame, text="🔄 Reanudar Sesión",
                  command=self.load_and_resume_session).grid(row=0, column=3, padx=5)

        # Barra de progreso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var,
                                           maximum=100, length=800)
        self.progress_bar.grid(row=5, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))

        self.progress_label = ttk.Label(main_frame, text="Listo para generar")
        self.progress_label.grid(row=6, column=0, columnspan=3)

        # Log de salida
        log_frame = ttk.LabelFrame(main_frame, text="📋 Registro de Procesamiento", padding="10")
        log_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=100, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configurar expansión
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def update_mode_description(self):
        """Actualiza la descripción del modo seleccionado"""
        self.mode_description.config(text="🔧 Incluye análisis exhaustivo y regeneración de problemas severos.")

    def on_phonetic_change(self):
        """Callback cuando cambia la opción de transformación fonética"""
        if self.use_phonetic.get():
            self.log("🔤 Transformación fonética activada")
            self.phonetic_description.config(
                text="✅ El texto será transformado fonéticamente antes de la síntesis",
                foreground="green"
            )
        else:
            self.log("📝 Transformación fonética desactivada")
            self.phonetic_description.config(
                text="Transforma: hacer→acer, llevar→yevar, vez→bes (betacismo/yeísmo/seseo)",
                foreground="gray"
            )

    def check_files(self):
        """Verifica que existan los archivos necesarios"""
        errors = []

        if not self.text_file.exists():
            errors.append(f"❌ No se encuentra el archivo de texto: {self.text_file}")

        if not self.reference_audio.exists():
            errors.append(f"❌ No se encuentra el audio de referencia: {self.reference_audio}")

        if errors:
            error_msg = "\n".join(errors)
            error_msg += "\n\n⚠️ Por favor, asegúrate de tener estos archivos en el directorio del script."
            messagebox.showerror("Archivos Faltantes", error_msg)
            self.generate_button.config(state=tk.DISABLED)
        else:
            self.log("✅ Archivos verificados correctamente")
            self.text_label.config(foreground="green")
            self.audio_label.config(foreground="green")

    def log(self, message):
        """Añade un mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, full_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def start_generation(self):
        """Inicia el proceso de generación"""
        if self.is_processing:
            messagebox.showwarning("Procesando", "Ya hay una generación en curso")
            return

        self.is_processing = True
        self.generate_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_var.set(0)

        # Limpiar log
        self.log_text.delete(1.0, tk.END)

        # Iniciar en thread separado
        self.current_thread = threading.Thread(target=self.run_generation)
        self.current_thread.daemon = True
        self.current_thread.start()

    def run_generation(self):
        """Ejecuta la generación en un thread separado"""
        try:
            mode = "full"

            # Directorio de salida: nuevo o reanudación
            if self.resume_state and self.resume_state.get('session_dir'):
                output_dir = Path(self.resume_state['session_dir'])
                output_dir.mkdir(parents=True, exist_ok=True)
                start_idx_resume = int(self.resume_state.get('phrase_idx', 0))
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = Path(f"output_{timestamp}")
                output_dir.mkdir(parents=True, exist_ok=True)
                start_idx_resume = 0

            self.log(f"📁 Directorio de salida: {output_dir}")
            self.log(f"⚙️ Modo seleccionado: {mode}")
            self.log(f"🔤 Transformación fonética: {'✅ ACTIVADA' if self.use_phonetic.get() else '❌ DESACTIVADA'}")

            # Leer y procesar el texto
            self.log(f"\n📖 Leyendo archivo: {self.text_file}")
            paragraphs = self.read_and_parse_text()

            if not paragraphs:
                self.log("❌ No se encontraron párrafos en el texto")
                return

            self.log(f"📚 Párrafos detectados: {len(paragraphs)}")

            # Aplicar transformación fonética si está habilitada
            if self.use_phonetic.get():
                self.log("\n🔤 Aplicando transformación fonética al texto...")
                original_text = "\n\n".join([p['text'] for p in paragraphs])

                # Guardar texto original
                original_path = output_dir / "texto_original.txt"
                with open(original_path, 'w', encoding='utf-8') as f:
                    f.write(original_text)

                # Transformar texto
                transformed_text = self.phonetic_transformer.transform_text(original_text)

                # Log de ejemplo de transformación
                orig_preview = original_text[:100].replace('\n', ' ')
                trans_preview = transformed_text[:100].replace('\n', ' ')
                self.log(f"📄 ANTES: {orig_preview}...")
                self.log(f"🔊 DESPUÉS: {trans_preview}...")

                # Guardar texto transformado
                transformed_path = output_dir / "texto_fonetico.txt"
                with open(transformed_path, 'w', encoding='utf-8') as f:
                    f.write(transformed_text)

                # Actualizar los párrafos con el texto transformado
                transformed_paragraphs = transformed_text.split('\n\n')
                for i, para in enumerate(paragraphs):
                    if i < len(transformed_paragraphs):
                        para['text'] = transformed_paragraphs[i]

                # Mostrar estadísticas de transformación
                stats = self.phonetic_transformer.get_transformation_stats()
                self.log(f"✅ Transformación completada:")
                self.log(f"   - Palabras transformadas: {stats['unique_words_transformed']}")
                self.log(f"   - Consistencia: {stats['consistency_score']:.1f}%")

                # Mostrar algunas transformaciones de ejemplo
                if stats['most_common_transformations']:
                    self.log("   - Ejemplos de transformaciones:")
                    for original, transformed in stats['most_common_transformations'][:3]:
                        self.log(f"     • {original} → {transformed}")

                self.log(f"   - Texto original guardado en: {original_path.name}")
                self.log(f"   - Texto fonético guardado en: {transformed_path.name}")

            # Convertir párrafos a lista de frases
            all_sentences = []
            paragraph_boundaries = [0]

            for p_idx, paragraph in enumerate(paragraphs):
                sentences = self.split_into_sentences(paragraph['text'])
                self.log(f"  Párrafo {p_idx + 1}: {len(sentences)} frases")

                for sentence in sentences:
                    all_sentences.append({
                        'text': sentence,
                        'paragraph_id': p_idx,
                        'paragraph_type': paragraph.get('type', 'normal')
                    })

                if p_idx < len(paragraphs) - 1:
                    paragraph_boundaries.append(len(all_sentences))

            self.log(f"📝 Total de frases: {len(all_sentences)}")

            # Procesar siempre en modo completo (Fases 1 y 2)
            self.process_full_mode(all_sentences, output_dir, start_idx=start_idx_resume)

            self.log(f"\n✅ Generación completada exitosamente")
            self.log(f"📁 Resultados guardados en: {output_dir}")

            messagebox.showinfo("Éxito", f"Generación completada.\nResultados en: {output_dir}")

        except Exception as e:
            error_msg = f"❌ Error durante la generación: {str(e)}"
            self.log(error_msg)
            if 'ENGINE_STRICT_T_ERROR' in str(e):
                self.log("🛑 Error crítico del motor detectado. Puede reanudar la ejecución cuando esté listo.")
                messagebox.showerror("Error crítico del motor",
                                     "Se detectó un error crítico del motor y la ejecución se detuvo.\n\n"
                                     "Use 'Reanudar última sesión' para continuar desde el último punto.")
            else:
                messagebox.showerror("Error", error_msg)

        finally:
            self.is_processing = False
            self.generate_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.progress_label.config(text="Generación completada")

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """
        Divide frases largas (>120 chars) por comas seguidas de conectores naturales
        para evitar errores de interpolación en F5-TTS
        """
        import re

        if len(sentence) <= 120:
            return [sentence]

        # Conectores y palabras que indican buen lugar para dividir
        connectors = [
            r',\s+(y|pero|sin embargo|además|también|cuando|donde|que|como si|mientras)',
            r',\s+(después|antes|luego|entonces|así que|por eso)',
            r',\s+(aunque|a pesar de|excepto|salvo)',
        ]

        # Intentar dividir por conectores
        for connector_pattern in connectors:
            matches = list(re.finditer(connector_pattern, sentence, re.IGNORECASE))

            # Buscar el mejor punto de división (cerca del centro)
            target_position = len(sentence) // 2
            best_match = None
            best_distance = float('inf')

            for match in matches:
                distance = abs(match.start() - target_position)
                if distance < best_distance:
                    best_distance = distance
                    best_match = match

            if best_match:
                # Dividir en el conector, manteniendo la coma con la primera parte
                split_pos = best_match.start() + 1  # Después de la coma
                part1 = sentence[:split_pos].strip()
                part2 = sentence[split_pos:].strip()

                if len(part1) > 30 and len(part2) > 30:  # Evitar partes muy pequeñas
                    # Recursivamente dividir si alguna parte sigue siendo muy larga
                    result = []
                    for part in [part1, part2]:
                        if len(part) > 120:
                            result.extend(self._split_long_sentence(part))
                        else:
                            result.append(part)
                    return result

        # Si no se encontraron conectores, dividir por comas simples cerca del centro
        comma_positions = [m.start() for m in re.finditer(r',', sentence)]
        if comma_positions:
            target_pos = len(sentence) // 2
            best_comma = min(comma_positions, key=lambda x: abs(x - target_pos))

            part1 = sentence[:best_comma + 1].strip()  # Incluir la coma
            part2 = sentence[best_comma + 1:].strip()

            if len(part1) > 30 and len(part2) > 30:
                # Recursivamente dividir si alguna parte sigue siendo muy larga
                result = []
                for part in [part1, part2]:
                    if len(part) > 120:
                        result.extend(self._split_long_sentence(part))
                    else:
                        result.append(part)
                return result

        # Último recurso: dividir por espacios cerca del centro
        words = sentence.split()
        if len(words) > 6:  # Solo si hay suficientes palabras
            mid_point = len(words) // 2
            part1 = ' '.join(words[:mid_point])
            part2 = ' '.join(words[mid_point:])
            return [part1, part2]

        # Si nada funciona, devolver la frase original
        return [sentence]

    def read_and_parse_text(self) -> List[Dict]:
        """
        Lee y parsea el archivo de texto, identificando párrafos
        """
        with open(self.text_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Dividir por párrafos (doble salto de línea)
        raw_paragraphs = content.split('\n\n')

        paragraphs = []
        for idx, para in enumerate(raw_paragraphs):
            para = para.strip()
            if not para:
                continue

            # Determinar tipo de párrafo según posición (arquitectura 3 párrafos)
            if idx == 0 or (idx < len(raw_paragraphs) * 0.33):
                para_type = "introduction"  # Párrafo 1: establecer
            elif idx < len(raw_paragraphs) * 0.66:
                para_type = "development"   # Párrafo 2: tensión
            else:
                para_type = "conclusion"    # Párrafo 3: resolución

            paragraphs.append({
                'text': para,
                'type': para_type,
                'index': idx
            })

        return paragraphs

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Divide un párrafo en frases considerando signos de apertura españoles
        Separa correctamente "¡-!" y "¿-?" como frases independientes
        """
        import re

        # Proteger abreviaciones comunes
        text = re.sub(r'\b(Sr|Sra|Dr|Dra|St|Sto|Sta)\.\s*', r'\1<DOT> ', text)

        # NUEVO: Pre-procesamiento para signos de apertura españoles
        # Insertar marcadores antes de signos de apertura cuando no están al inicio
        text = re.sub(r'([.!?])\s*([¡¿])', r'\1<FRASE_BREAK>\2', text)

        # También manejar casos donde hay espacios múltiples
        text = re.sub(r'([.!?])\s{2,}([¡¿])', r'\1<FRASE_BREAK>\2', text)

        # NUEVO: Aislar explícitamente bloques exclamativos e interrogativos como frases
        # Inserta ruptura ANTES y DESPUÉS de cualquier "¡...!" y "¿...?"
        text = re.sub(r'¡([^!]+)!', r'<FRASE_BREAK>¡\1!<FRASE_BREAK>', text)
        text = re.sub(r'¿([^?]+)\?', r'<FRASE_BREAK>¿\1?<FRASE_BREAK>', text)

        # NUEVO: Aislar bloques entre comillas dobles como frases independientes
        text = re.sub(r'"([^"\n]+)"', r'<FRASE_BREAK>"\1"<FRASE_BREAK>', text)

        # NUEVO: Insertar ruptura antes de cualquier '¡' o '¿' que no esté al inicio
        text = re.sub(r'(?<!^)¡', r'<FRASE_BREAK>¡', text)
        text = re.sub(r'(?<!^)¿', r'<FRASE_BREAK>¿', text)

        # NUEVO: Insertar ruptura tras '!' y '?'
        text = re.sub(r'!\s*', r'!<FRASE_BREAK>', text)
        text = re.sub(r'\?\s*', r'?<FRASE_BREAK>', text)

        # Normalizar posibles duplicados de marcadores
        text = re.sub(r'(?:<FRASE_BREAK>){2,}', '<FRASE_BREAK>', text)

        # NUEVO: Manejar puntos suspensivos como separadores de frase
        # Dividir después de cualquier "..." (independientemente de lo que siga)
        text = re.sub(r'\.\.\.\s*', '...<FRASE_BREAK>', text)

        # NUEVO: Dividir por punto y coma como separador de frase
        text = re.sub(r';\s*', '<FRASE_BREAK>', text)

        # NUEVO: Dividir por dos puntos como separador de frase (no si va seguido de ")
        text = re.sub(r':\s*(?!\")', ':<FRASE_BREAK>', text)

        # NUEVO: Separar por guion/raya en medio de la oración (con espacios alrededor)
        # Cubre '-', '–' (en dash), '—' (em dash) con espacios a ambos lados
        text = re.sub(r'\s[–—-]\s', '<FRASE_BREAK>', text)

        # Normalizar posibles duplicados de marcadores tras todas las inserciones
        text = re.sub(r'(?:<FRASE_BREAK>){2,}', '<FRASE_BREAK>', text)

        # Dividir por marcadores de ruptura de frase
        if '<FRASE_BREAK>' in text:
            parts_raw = text.split('<FRASE_BREAK>')
        else:
            # Fallback al método original si no hay marcadores
            # Incluir puntos suspensivos, punto y coma y dos puntos como finales de frase
            sentence_endings = re.compile(r'([.!?;:]|\.\.\.)\s+')
            parts_raw = sentence_endings.split(text)

        sentences = []

        if '<FRASE_BREAK>' in text:
            # Procesamiento con marcadores
            for part in parts_raw:
                part_clean = part.replace('<DOT>', '.').strip()
                if part_clean:
                    # Procesar cada parte para separar exclamaciones/interrogaciones múltiples
                    sub_sentences = self._separate_exclamations_questions(part_clean)
                    sentences.extend(sub_sentences)
        else:
            # Procesamiento original
            current = ""
            for i, part in enumerate(parts_raw):
                if part in '.!?;:' or part == '...':
                    current += part
                    current = current.replace('<DOT>', '.')
                    if current.strip():
                        # Procesar para separar exclamaciones/interrogaciones
                        sub_sentences = self._separate_exclamations_questions(current.strip())
                        sentences.extend(sub_sentences)
                    current = ""
                else:
                    current += part

            if current.strip():
                current = current.replace('<DOT>', '.')
                sub_sentences = self._separate_exclamations_questions(current.strip())
                sentences.extend(sub_sentences)

        # Filtrar frases vacías o que sean sólo puntuación/comillas
        cleaned_sentences = []
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            # Rechazar si no contiene letras o dígitos (evita ":" "." etc.)
            import re as _re
            if not _re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]', s_clean):
                continue
            cleaned_sentences.append(s_clean)
        sentences = cleaned_sentences

        # NUEVO: Dividir frases excesivamente largas (>120 chars) por comas naturales
        final_sentences = []
        for sentence in sentences:
            if len(sentence) > 120:
                # Dividir por comas seguidas de conectores o pausas naturales
                sub_parts = self._split_long_sentence(sentence)
                final_sentences.extend(sub_parts)
            else:
                final_sentences.append(sentence)

        # NUEVO: Fusionar frases demasiado cortas (<3 palabras) con la siguiente
        final_sentences = self._merge_short_sentences(final_sentences, min_words=3)

        # NUEVO: Asegurar apertura de interrogación en frases que terminan en '?'
        final_sentences = self._normalize_spanish_question_opening(final_sentences)

        return final_sentences

    def _separate_exclamations_questions(self, text: str) -> List[str]:
        """
        Separa exclamaciones e interrogaciones que están juntas recursivamente
        Ejemplo: "¡Hola! ¿Cómo estás?" → ["¡Hola!", "¿Cómo estás?"]
        """
        import re

        # Aplicar separación recursiva hasta que no haya más cambios
        current_sentences = [text]
        changes = True

        while changes:
            changes = False
            new_sentences = []

            for sentence in current_sentences:
                divided_sentences = self._divide_simple_sentence(sentence)
                if len(divided_sentences) > 1:
                    changes = True
                new_sentences.extend(divided_sentences)

            current_sentences = new_sentences

        # Limpiar y finalizar frases
        final_sentences = []
        for sentence in current_sentences:
            clean_sentence = sentence.strip()
            if clean_sentence:
                # Eliminar combinaciones de puntuación redundante al final (:. ;. -- etc.)
                import re as _re2
                clean_sentence = _re2.sub(r'([:;\-–—,"])\.+$', '.', clean_sentence)
                clean_sentence = _re2.sub(r'[:;\-–—,"]+$', '', clean_sentence).strip()
            if clean_sentence:
                # Asegurar puntuación final
                if not clean_sentence[-1] in '.!?':
                    # Determinar qué puntuación añadir según el contenido
                    if clean_sentence.startswith('¡') or '¡' in clean_sentence:
                        clean_sentence += '!'
                    elif clean_sentence.startswith('¿') or '¿' in clean_sentence:
                        clean_sentence += '?'
                    else:
                        clean_sentence += '.'
                final_sentences.append(clean_sentence)

        return final_sentences

    def _divide_simple_sentence(self, text: str) -> List[str]:
        """
        Divide una frase simple en el primer punto de separación encontrado
        """
        import re

        # Buscar patrones de separación en orden de prioridad

        # 1. Separación por exclamación/interrogación seguida de apertura
        pattern1 = r'([!?])\s*([¡¿])'
        match1 = re.search(pattern1, text)
        if match1:
            pos = match1.start(2)  # Posición del signo de apertura
            part1 = text[:pos].strip()
            part2 = text[pos:].strip()
            if part1 and part2:
                return [part1, part2]

        # 2. Separación por final de oración seguida de apertura (sin espacio requerido)
        pattern2 = r'([.!?])\s*([¡¿])'
        match2 = re.search(pattern2, text)
        if match2 and match2.start() > 0:  # No dividir si está al inicio
            pos = match2.start(2)
            part1 = text[:pos].strip()
            part2 = text[pos:].strip()
            if part1 and part2:
                return [part1, part2]

        # 3. Separación por exclamación/interrogación seguida de oración normal
        pattern3 = r'([!?])\s+([A-ZÁÉÍÓÚÑ])'
        match3 = re.search(pattern3, text)
        if match3:
            pos = match3.start(2)
            part1 = text[:pos].strip()
            part2 = text[pos:].strip()
            if part1 and part2:
                return [part1, part2]

        # 4. Separación por punto seguido de mayúscula (frases declarativas)
        pattern4 = r'(\.\s+)([A-ZÁÉÍÓÚÑ])'
        match4 = re.search(pattern4, text)
        if match4:
            pos = match4.start(2)
            part1 = text[:pos].strip()
            part2 = text[pos:].strip()
            if part1 and part2 and len(part1) > 3:  # Evitar divisiones muy cortas
                return [part1, part2]

        # Si no se puede dividir, devolver como está
        return [text]

    def _merge_short_sentences(self, sentences: List[str], min_words: int = 3) -> List[str]:
        """
        Fusiona frases con menos de min_words palabras con la siguiente frase.
        Reglas:
        - Interjecciones (oye/eh/ey/hey): se unen a la ANTERIOR con coma y exclamación
          ("Les dices, ¡oye!") si hay anterior; si no, se unen a la siguiente.
        - Si la siguiente frase es una pregunta (empieza por '¿' o termina en '?'),
          no unir hacia delante; unir a la anterior si existe.
        - El resto de cortas se unen a la siguiente.
        """
        import re as _re

        merged = []
        i = 0
        while i < len(sentences):
            current = sentences[i].strip()
            current_words = len(current.split())

            # Helper para unir a anterior con coma y respetar puntuación
            def _append_to_previous_with_comma(prev: str, addon: str) -> str:
                prev_core = _re.sub(r'[.!?]+$', '', prev).strip()
                return f"{prev_core}, {addon}".strip()

            if current_words < min_words:
                interjections = {"oye", "eh", "ey", "hey"}
                is_interj = current.lower().strip('¡!').strip().strip(',') in interjections

                next_sentence = sentences[i + 1].strip() if i + 1 < len(sentences) else ""
                next_is_question = next_sentence.startswith('¿') or next_sentence.endswith('?')

                if is_interj and len(merged) > 0:
                    # Formatear interjección con exclamación
                    interj = current.strip('¡!').strip().strip(',')
                    interj_formatted = f"¡{interj}!"
                    combined = _append_to_previous_with_comma(merged[-1], interj_formatted)
                    merged[-1] = combined
                    i += 1
                    continue

                if next_is_question and len(merged) > 0:
                    # Evitar unir a la pregunta; unir a la anterior
                    combined = _append_to_previous_with_comma(merged[-1], current)
                    merged[-1] = combined
                    i += 1
                    continue

                if i + 1 < len(sentences):
                    # Unir hacia delante (por defecto)
                    combined = f"{current} {next_sentence}".strip()
                    merged.append(combined)
                    i += 2
                    continue

                # Si no hay siguiente, unir a anterior si existe
                if len(merged) > 0:
                    combined = _append_to_previous_with_comma(merged[-1], current)
                    merged[-1] = combined
                else:
                    merged.append(current)
                i += 1
            else:
                merged.append(current)
                i += 1

        return merged

    def _normalize_spanish_question_opening(self, sentences: List[str]) -> List[str]:
        """
        Asegura que toda frase que termina en '?' tenga signo de apertura '¿' si falta.
        """
        normalized = []
        for s in sentences:
            s_clean = s.strip()
            if s_clean.endswith('?') and '¿' not in s_clean:
                s_clean = f"¿{s_clean}"
            normalized.append(s_clean)
        return normalized

    def _estimate_paragraph_id(self, phrase_idx: int, total_phrases: int) -> int:
        """Estima el ID del párrafo basado en la posición de la frase"""
        # Dividir en 3 párrafos aproximadamente
        third = total_phrases // 3
        if phrase_idx < third:
            return 0
        elif phrase_idx < 2 * third:
            return 1
        else:
            return 2

    def process_full_mode(self, sentences: List[Dict], output_dir: Path, start_idx: int = 0):
        """Procesa en modo completo (Fases 1 y 2): Fase 1 COMPLETA + Post-procesamiento"""
        self.log("\n🔍 MODO COMPLETO - Fase 1 (Sistema Híbrido) + Fase 2 (Post-procesamiento)")
        self.log("="*80)

        if not HYBRID_AVAILABLE:
            self.log("❌ Sistema híbrido no disponible, usando modo legacy")
            return self.process_full_mode_legacy(sentences, output_dir)

        # FASE 1: Usar exactamente la misma lógica que el modo rápido
        self.log("\n📝 FASE 1: Generación con hints prosódicos (Sistema Híbrido)")

        # Preparar texto completo para el generador híbrido
        full_text = " ".join([s['text'] for s in sentences])

        # Crear instancia del generador híbrido (igual que modo rápido)
        self.log("🎵 Inicializando generador híbrido...")

        # Buscar el modelo en el directorio correcto
        model_path = Path(__file__).parent.parent / "generador_estructura_v3" / "model_943000.pt"
        if not model_path.exists():
            model_path = "./model_943000.pt"  # Fallback al directorio actual

        generator = ProsodyEnhancedGenerator(
            texto_usuario=full_text,
            model_path=str(model_path),
            reference_file="segment_2955.wav"
        )

        # Configurar referencia y output
        generator.reference_file = Path("segment_2955.wav")
        generator.output_dir = output_dir

        # Inicializar el modelo F5TTS
        generator.ensure_model_loaded()

        # IMPORTANTE: Solo Fase 1 aquí, la Fase 2 viene después
        generator.enable_prosody_hints = True
        generator.enable_postprocessing = False  # Fase 2 se maneja por separado

        # USAR nuestra segmentación ya calculada en 'sentences'
        custom_frases = [s['text'] for s in sentences]
        if custom_frases:
            generator.frases = custom_frases
            self.log(f"🧩 Usando segmentación personalizada: {len(custom_frases)} frases")

        # Crear directorio para frases individuales
        frases_dir = output_dir / "frases"
        frases_dir.mkdir(exist_ok=True)

        audio_segments = []
        total = len(generator.frases)

        self.log(f"📝 Ejecutando Fase 1 completa: {total} frases con mejoras prosódicas...")

        # Reanudación: precargar segmentos existentes
        if start_idx > 0:
            self.log(f"🔄 Reanudación: saltando {start_idx} frases ya generadas")
            for i in range(start_idx):
                pre_path = frases_dir / f"frase_{i + 1:03d}.wav"
                if pre_path.exists():
                    try:
                        seg, sr = sf.read(pre_path)
                        audio_segments.append(seg)
                    except Exception:
                        audio_segments.append(np.zeros(int(0.1 * generator.sample_rate)))
            self.progress_var.set((start_idx / total) * 60)
            self.progress_label.config(text=f"Fase 1: Reanudación {start_idx}/{total}")

        # Ejecutar EXACTAMENTE la misma Fase 1 que el modo rápido
        for idx, frase in enumerate(generator.frases):
            if idx < start_idx:
                continue
            if not self.is_processing:
                self.log("⏹️ Generación detenida por el usuario")
                break

            # Actualizar progreso (0-60% para Fase 1 completa)
            progress = (idx / total) * 60
            self.progress_var.set(progress)
            self.progress_label.config(text=f"Fase 1: Procesando frase {idx + 1} de {total}")

            # Usar generación híbrida con prosodia (IGUAL que modo rápido)
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

        # Guardar resultado de Fase 1 (para comparación)
        if audio_segments:
            self.log(f"\n🔗 Guardando resultado de Fase 1...")

            # Usar la concatenación del generador original
            fase1_audio = generator.apply_crossfade_and_concatenate(audio_segments)
            fase1_path = output_dir / "audio_fase1_completa.wav"
            sf.write(fase1_path, fase1_audio, generator.sample_rate)

            self.log(f"✅ Fase 1 guardada: {fase1_path.name}")
            self.log(f"📊 Hints prosódicos aplicados: {generator.prosody_stats['hints_applied']}/{total}")

        # FASE 2: Post-procesamiento SOBRE los resultados de Fase 1
        self.log(f"\n🔧 FASE 2: Post-procesamiento sobre resultados de Fase 1")
        self.progress_label.config(text="Fase 2: Analizando prosodia de Fase 1...")

        if not audio_segments:
            self.log("❌ No hay audio de Fase 1 para post-procesar")
            return

        # Extraer textos para análisis
        texts = [frase for frase in generator.frases]

        # Analizar el audio generado en Fase 1
        analyzer = ProsodyAnalyzer()
        analysis = analyzer.analyze_complete_audio(audio_segments, texts)

        # Detectar problemas en el audio de Fase 1
        detector = ProsodyProblemDetector()
        problems = detector.identify_problems(analysis)

        self.log(f"📊 Problemas detectados en Fase 1: {len(problems)}")

        # Progreso 60-90% para análisis y corrección
        self.progress_var.set(70)

        if problems and generator.f5tts:
            critical = [p for p in problems if p['severity'] > 0.3][:5]

            if critical:
                self.log(f"🔧 Corrigiendo {len(critical)} problemas críticos encontrados en Fase 1...")
                self.progress_label.config(text=f"Fase 2: Corrigiendo {len(critical)} problemas...")

                # Configurar regenerador con el mismo contexto que Fase 1
                regenerator = SelectiveRegenerator(generator.f5tts, max_fixes=5)
                regenerator.set_reference_context(str(generator.reference_file), "")

                # Corregir problemas detectados
                corrected_segments, fix_report = regenerator.fix_critical_problems(
                    problems, audio_segments, texts, severity_threshold=0.3
                )

                # Actualizar audio_segments con las correcciones
                audio_segments = corrected_segments

                # SOBREESCRIBIR archivos de frases con las versiones corregidas
                try:
                    for idx_corr, audio_corr in enumerate(audio_segments):
                        frase_path = frases_dir / f"frase_{idx_corr + 1:03d}.wav"
                        sf.write(frase_path, audio_corr, generator.sample_rate)
                    self.log("💾 Frases corregidas sobreescritas en disco")
                except Exception as e:
                    self.log(f"⚠️ No se pudo sobreescribir frases corregidas: {e}")

                self.log(f"✅ Correcciones aplicadas: {fix_report['successful']}/{fix_report['attempted']}")

                # Guardar reporte de correcciones
                corrections_report = {
                    'phase1_hints': generator.prosody_stats['hints_applied'],
                    'phase2_problems_found': len(problems),
                    'phase2_problems_fixed': fix_report['successful'],
                    'phase2_fix_details': fix_report
                }

                with open(output_dir / "reporte_correcciones_fase2.json", 'w', encoding='utf-8') as f:
                    import json
                    json.dump(corrections_report, f, indent=2, ensure_ascii=False)

            else:
                self.log("✅ No se encontraron problemas críticos en Fase 1")

        # Concatenar y guardar resultado final (Fase 1 + Fase 2)
        self.progress_var.set(90)
        self.progress_label.config(text="Finalizando: Concatenando audio final...")

        if audio_segments:
            # Usar concatenación inteligente para el resultado final
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

        self.progress_var.set(100)
        self.log("\n🎉 Modo completo finalizado: Fase 1 (Híbrida) + Fase 2 (Post-procesamiento)")

    def process_full_mode_legacy(self, sentences: List[Dict], output_dir: Path):
        """Modo completo legacy cuando el sistema híbrido no está disponible"""
        self.log("\n⚠️ MODO COMPLETO LEGACY - Sin sistema híbrido")
        self.log("="*50)

        # Fase 1 con F5ProsodyAdapter
        self.log("\n📝 FASE 1: Generación con hints prosódicos (Legacy)")

        adapter = F5ProsodyAdapter(
            reference_audio=str(self.reference_audio),
            sample_rate=44100
        )

        audio_segments = []
        texts = []
        total = len(sentences)

        for idx, sentence_data in enumerate(sentences):
            if not self.is_processing:
                self.log("⏹️ Generación detenida por el usuario")
                break

            # Actualizar progreso (0-60% para Fase 1)
            progress = (idx / total) * 60
            self.progress_var.set(progress)
            self.progress_label.config(text=f"Fase 1 Legacy: Procesando frase {idx + 1} de {total}")

            # Generar
            audio = adapter.generate_single_with_prosody(
                text=sentence_data['text'],
                phrase_idx=idx,
                total_phrases=total,
                paragraph_id=sentence_data['paragraph_id'],
                log_callback=self.log
            )

            audio_segments.append(audio)
            texts.append(sentence_data['text'])

        # Fase 2: Post-procesamiento
        self.log("\n🔧 FASE 2: Análisis y corrección prosódica")
        self.progress_label.config(text="Fase 2: Analizando prosodia...")

        # Analizar
        analyzer = ProsodyAnalyzer()
        analysis = analyzer.analyze_complete_audio(audio_segments, texts)

        # Detectar problemas
        detector = ProsodyProblemDetector()
        problems = detector.identify_problems(analysis)

        self.log(f"📊 Problemas detectados: {len(problems)}")

        if problems and adapter.f5tts:
            critical = [p for p in problems if p['severity'] > 0.3][:5]

            if critical:
                self.log(f"🔧 Corrigiendo {len(critical)} problemas críticos...")

                regenerator = SelectiveRegenerator(adapter.f5tts, max_fixes=5)
                audio_segments, fix_report = regenerator.fix_critical_problems(
                    problems, audio_segments, texts, severity_threshold=0.3
                )

                self.log(f"✅ Correcciones aplicadas: {fix_report['successful']}/{fix_report['attempted']}")

        # Concatenar y guardar
        if audio_segments:
            final_audio = smart_concatenate(audio_segments, crossfade_ms=50, sr=adapter.sample_rate)
            final_path = output_dir / "audio_final_completo_legacy.wav"
            sf.write(final_path, final_audio, adapter.sample_rate)

            self.log(f"\n✅ Audio final guardado: {final_path}")

            # Guardar reporte
            report_data = {
                **adapter.stats,
                'problems_found': len(problems),
                'problems_fixed': fix_report['successful'] if 'fix_report' in locals() else 0
            }
            self.save_report(report_data, output_dir / "reporte_completo_legacy.json", "full_legacy")

        self.progress_var.set(100)

    def process_both_modes(self, sentences: List[Dict], output_dir: Path):
        """Procesa ambos modos para comparación"""
        self.log("\n🎯 MODO DUAL - Generando ambas versiones")
        self.log("="*50)

        # Primero modo rápido
        self.log("\n--- Versión 1: Solo Fase 1 ---")
        fast_dir = output_dir / "version_rapida"
        fast_dir.mkdir(exist_ok=True)
        self.process_fast_mode(sentences, fast_dir)

        if self.is_processing:
            # Luego modo completo
            self.log("\n--- Versión 2: Completa con Fase 2 ---")
            full_dir = output_dir / "version_completa"
            full_dir.mkdir(exist_ok=True)
            self.process_full_mode(sentences, full_dir)

        self.log("\n📊 Ambas versiones generadas para comparación")

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

    def stop_generation(self):
        """Detiene la generación en curso"""
        if self.is_processing:
            self.is_processing = False
            self.log("⏹️ Deteniendo generación...")
            messagebox.showinfo("Detenido", "La generación se detendrá después de la frase actual")

    def open_results_folder(self):
        """Abre la carpeta de resultados más reciente"""
        import subprocess
        import platform

        # Buscar la carpeta más reciente
        output_dirs = sorted([d for d in Path('.').glob('output_*') if d.is_dir()],
                            key=lambda x: x.stat().st_mtime, reverse=True)

        if output_dirs:
            folder = output_dirs[0]

            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", folder])
            else:  # Linux
                subprocess.Popen(["xdg-open", folder])

            self.log(f"📂 Abriendo: {folder}")
        else:
            messagebox.showinfo("Sin resultados", "No hay carpetas de resultados generadas aún")

    def resume_last_session(self):
        """Reanuda la ejecución desde el último estado guardado (si existe)."""
        import json
        from pathlib import Path as _Path
        state_path = _Path('resume_state.json')
        if not state_path.exists():
            messagebox.showinfo("Reanudar", "No hay estado de reanudación disponible")
            return
        try:
            state = json.loads(state_path.read_text(encoding='utf-8'))
            self.log(f"🔄 Reanudando desde frase {state.get('phrase_idx', '?')}")
            messagebox.showinfo("Reanudar", f"Reanudación preparada desde frase {state.get('phrase_idx', '?')}.\n"
                                           "Por ahora, reinicie la generación para continuar.")
        except Exception as e:
            messagebox.showerror("Reanudar", f"No se pudo cargar el estado de reanudación: {e}")

    def load_and_resume_session(self):
        """Carga automáticamente la última sesión output_* o resume_state.json y prepara reanudación."""
        from pathlib import Path as _Path
        import json as _json
        # 1) Intentar resume_state.json
        state_path = _Path('resume_state.json')
        if state_path.exists():
            try:
                self.resume_state = _json.loads(state_path.read_text(encoding='utf-8'))
                self.log(f"🔄 Cargado estado de reanudación: frase {self.resume_state.get('phrase_idx','?')}")
                messagebox.showinfo("Reanudar", "Estado de reanudación cargado. Inicie 'Generar Audio' para continuar.")
                return
            except Exception as e:
                self.log(f"⚠️ No se pudo leer resume_state.json: {e}")
        # 2) Buscar última carpeta output_*
        output_dirs = sorted([d for d in _Path('.').glob('output_*') if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
        if not output_dirs:
            messagebox.showinfo("Reanudar", "No hay sesiones previas para reanudar")
            return
        last_dir = output_dirs[0]
        frases_dir = last_dir / 'frases'
        if not frases_dir.exists():
            messagebox.showinfo("Reanudar", f"La última sesión no contiene 'frases': {last_dir}")
            return
        # Calcular índice de reanudación por número de wav existentes consecutivos
        idx = 0
        while True:
            path = frases_dir / f"frase_{idx + 1:03d}.wav"
            if path.exists():
                idx += 1
            else:
                break
        if idx == 0:
            messagebox.showinfo("Reanudar", f"No se encontraron frases previas en {last_dir}")
            return
        # Preparar resume_state simulado
        self.resume_state = {
            'session_dir': str(last_dir),
            'phrase_idx': idx
        }
        self.log(f"🔄 Detección automática: reanudar desde {last_dir} en frase {idx}")
        messagebox.showinfo("Reanudar", f"Listo para reanudar desde frase {idx} en {last_dir}.\nPulsa 'Generar Audio'.")

    def run(self):
        """Ejecuta la aplicación"""
        self.root.mainloop()


def main():
    """Función principal"""
    print("="*60)
    print("🎵 Generador F5-TTS con Mejora Prosódica")
    print("="*60)
    print()
    print("Configuración:")
    print("  📝 Archivo de texto: texto.txt")
    print("  🎤 Audio referencia: segment_2955.wav")
    print("  📁 Salida: output_[timestamp]/")
    print()

    # Crear y ejecutar GUI
    app = ProsodyGeneratorGUI()
    app.run()


if __name__ == "__main__":
    main()