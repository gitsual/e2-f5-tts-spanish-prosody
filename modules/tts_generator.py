#!/usr/bin/env python3
"""
====================================================================================================
GENERADOR HÍBRIDO F5-TTS CON MEJORAS PROSÓDICAS
====================================================================================================

Descripción:
    Sistema híbrido que combina el generador original (EstructuraComplejaMejorada) con
    mejoras prosódicas avanzadas. Mantiene toda la funcionalidad del sistema original
    mientras añade capacidades de análisis y mejora de la prosodia.

Arquitectura:
    - Hereda de EstructuraComplejaMejorada (generador base)
    - Integra ProsodyHintGenerator para guiar la generación
    - Incluye ProsodyAnalyzer para análisis post-generación
    - Utiliza SelectiveRegenerator para corregir problemas
    - Implementa concatenación inteligente con crossfade

Características:
    - Procesamiento en dos fases (generación + post-procesamiento)
    - Hints prosódicos contextuales por posición en el texto
    - Detección automática de problemas prosódicos
    - Regeneración selectiva de segmentos problemáticos
    - Configuración CUDA optimizada para evitar OOM

Autor: Sistema de generación prosódica F5-TTS
Versión: 2.0 (Híbrido)
====================================================================================================
"""

import os
import sys

# ====================================================================================================
# CONFIGURACIÓN DE ENTORNO CUDA
# ====================================================================================================
# Configuración optimizada de memoria CUDA para prevenir errores Out-Of-Memory (OOM)
# - expandable_segments: Permite expansión dinámica de segmentos de memoria
# - max_split_size_mb: Limita el tamaño de división de bloques a 64MB
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True,max_split_size_mb:64'
os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'          # Orden consistente de dispositivos
os.environ['CUDA_VISIBLE_DEVICES'] = '0'                # Usar solo GPU 0
import shutil
from pathlib import Path
import librosa
import soundfile as sf
import numpy as np
from tqdm import tqdm
import torch
from f5_tts.api import F5TTS
from scipy.signal import butter, filtfilt
import time
import warnings
import logging
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json

# Importar tu generador original
try:
    from complex_generator import EstructuraComplejaMejorada
    ORIGINAL_AVAILABLE = True
    print("✅ Generador original importado correctamente")
except ImportError as e:
    print(f"❌ No se pudo importar el generador original: {e}")
    print("⚠️ Por favor, verifica que complex_generator.py esté disponible")
    ORIGINAL_AVAILABLE = False

# Importar sistema de prosodia
from core.prosody_processor import (
    ProsodyHintGenerator,
    ProsodyAnalyzer,
    ProsodyProblemDetector,
    SelectiveRegenerator,
    smart_concatenate,
    export_prosody_report
)

warnings.filterwarnings("ignore")


class ProsodyEnhancedGenerator(EstructuraComplejaMejorada):
    """
    Generador mejorado con capacidades prosódicas avanzadas.

    Extiende la clase EstructuraComplejaMejorada añadiendo:
    - Sistema de hints prosódicos contextuales
    - Análisis automático de características prosódicas
    - Detección y corrección de problemas
    - Orquestación global para coherencia narrativa

    Esta clase mantiene 100% de compatibilidad con el sistema original,
    añadiendo funcionalidad opcional de mejora prosódica.

    Attributes:
        prosody_hint_gen (ProsodyHintGenerator): Generador de hints prosódicos
        analyzer (ProsodyAnalyzer): Analizador de características del audio
        detector (ProsodyProblemDetector): Detector de problemas prosódicos
        enable_prosody_hints (bool): Si aplicar hints durante generación
        enable_postprocessing (bool): Si aplicar post-procesamiento
        prosody_stats (dict): Estadísticas de aplicación de mejoras

    Hereda:
        Todos los atributos y métodos de EstructuraComplejaMejorada
    """

    def __init__(self, model_path="./model_943000.pt", texto_usuario=None, session_dir=None, reference_file="segment_2955.wav"):
        """
        Inicializa el generador híbrido con mejoras prosódicas.

        Args:
            model_path (str): Ruta al modelo F5-TTS (.pt)
            texto_usuario (str): Texto completo a sintetizar
            session_dir (str): Directorio para guardar resultados
            reference_file (str): Archivo de audio para clonación de voz

        Note:
            Primero inicializa la clase padre (generador original) y luego
            añade los componentes del sistema prosódico.
        """
        # Inicializar la clase padre con todos tus parámetros originales
        super().__init__(model_path, texto_usuario, session_dir)

        # Asegurar que reference_file esté configurado
        if self.reference_file is None:
            self.reference_file = Path(reference_file)
            print(f"📎 Archivo de referencia configurado: {self.reference_file}")

        # Añadir sistema de prosodia
        print(f"\n🎵 Inicializando Sistema de Mejora Prosódica...")
        self.prosody_hint_gen = ProsodyHintGenerator(usar_orquestador_maestro=True)
        self.analyzer = ProsodyAnalyzer(sample_rate=self.sample_rate)
        self.detector = ProsodyProblemDetector()

        # NUEVO: Inicializar Orquestador Maestro con el texto completo (si está disponible)
        self.orquestador_disponible = False
        if texto_usuario:
            try:
                print(f"🎭 Preparando Orquestador Maestro para arquitectura vocal completa...")
                self.prosody_hint_gen.inicializar_orquestador_maestro(texto_usuario, f0_base=185.0)
                self.orquestador_disponible = True
                print("✅ Orquestador Maestro inicializado")
            except Exception as e:
                # Si el módulo interno usa import relativo sin paquete, puede fallar en ejecución directa
                print(f"⚠️ Orquestador Maestro no disponible, usando sistema legacy: {e}")
                self.orquestador_disponible = False

        # Estadísticas prosódicas
        self.prosody_stats = {
            'hints_applied': 0,
            'critical_positions': 0,
            'problems_detected': 0,
            'problems_fixed': 0
        }

        # Configuración de prosodia
        self.enable_prosody_hints = True
        self.enable_postprocessing = False  # Por defecto solo Fase 1

        print(f"✅ Sistema híbrido listo: Generación original + Prosodia")

    def ensure_model_loaded(self):
        """Asegurar que el modelo F5TTS esté cargado con optimización de memoria"""
        if self.f5tts is None:
            print("🔄 Cargando modelo F5-TTS...")

            # Optimización agresiva de memoria CUDA
            if self.device == "cuda":
                try:
                    # Limpiar toda la caché de GPU
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    torch.cuda.ipc_collect()

                    # Obtener información de memoria
                    total_memory = torch.cuda.get_device_properties(0).total_memory
                    allocated_memory = torch.cuda.memory_allocated(0)
                    cached_memory = torch.cuda.memory_reserved(0)

                    print(f"🎮 GPU Memory: {total_memory/1024**3:.1f}GB total, {allocated_memory/1024**3:.1f}GB allocated, {cached_memory/1024**3:.1f}GB cached")

                    # Si hay poca memoria libre, forzar a CPU
                    free_memory = total_memory - max(allocated_memory, cached_memory)
                    if free_memory < 2 * 1024**3:  # Menos de 2GB libre
                        print(f"⚠️ Poca memoria GPU libre ({free_memory/1024**3:.1f}GB), cambiando a CPU...")
                        self.device = "cpu"
                except Exception as e:
                    print(f"⚠️ Error verificando memoria GPU: {e}, usando CPU...")
                    self.device = "cpu"

            try:
                if self.device == "cuda":
                    # Configurar para usar menos memoria
                    torch.backends.cudnn.benchmark = False
                    torch.backends.cuda.matmul.allow_tf32 = True

                    # Configurar torch.load para usar weights_only=False de forma segura
                    import importlib
                    importlib.import_module('torch.serialization')
                    original_load = torch.load

                    def safe_load_cuda(f, map_location=None, **kwargs):
                        if 'weights_only' not in kwargs:
                            kwargs['weights_only'] = False
                        if map_location is None:
                            map_location = "cuda:0"
                        return original_load(f, map_location=map_location, **kwargs)

                    torch.load = safe_load_cuda

                self.f5tts = F5TTS(
                    model_type="F5-TTS",
                    device=self.device,
                    ckpt_file=self.model_path
                )

                if self.device == "cuda":
                    torch.load = original_load  # Restaurar función original

                print(f"✅ Modelo F5-TTS cargado exitosamente en {self.device.upper()}")

            except torch.cuda.OutOfMemoryError as oom_error:
                print(f"⚠️ Error de memoria GPU: {oom_error}")
                print("🔄 Limpiando memoria y reintentando con CPU...")

                # Limpiar todo
                if hasattr(self, 'f5tts') and self.f5tts is not None:
                    del self.f5tts
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

                # Cambiar a CPU
                self.device = "cpu"
                self.f5tts = F5TTS(
                    model_type="F5-TTS",
                    device=self.device,
                    ckpt_file=self.model_path
                )
                print("✅ Modelo cargado en CPU (será más lento pero funcional)")

            except Exception as e:
                print(f"❌ Error cargando F5-TTS: {e}")
                raise

    def parse_text_and_prepare(self):
        """
        Método para preparar el texto (compatible con tests)
        En tu sistema original las frases ya están listas
        """
        # Las frases ya están procesadas en self.frases por el constructor original
        return len(self.frases)

    def generate_single_phrase_with_prosody(self, text, phrase_idx, total_phrases, paragraph_id=None, log_callback=None):
        """
        Versión mejorada de tu generate_single_phrase_with_validation
        Añade hints prosódicos ANTES de la generación, manteniendo toda tu lógica original
        """

        # Asegurar que el modelo esté cargado
        self.ensure_model_loaded()

        # Generar hints prosódicos si está habilitado
        if self.enable_prosody_hints:
            hints = self.prosody_hint_gen.prepare_text_for_generation(
                text, phrase_idx, total_phrases, paragraph_id
            )

            if hints['apply_modifications']:
                self.prosody_stats['hints_applied'] += 1

                # Modificar texto si es necesario
                text_to_generate = hints['text']

                # Guardar parámetros originales
                original_nfe = self.nfe_steps
                original_sway = self.sway_sampling_coef
                original_cfg = self.cfg_strength
                original_speed = self.speed

                # Aplicar ajustes prosódicos TEMPORALMENTE
                if 'extra_params' in hints:
                    if 'nfe_adjustment' in hints['extra_params']:
                        self.nfe_steps += hints['extra_params']['nfe_adjustment']
                    if 'sway_adjustment' in hints['extra_params']:
                        self.sway_sampling_coef += hints['extra_params']['sway_adjustment']
                    if 'cfg_adjustment' in hints['extra_params']:
                        self.cfg_strength += hints['extra_params']['cfg_adjustment']

                # Ajustar velocidad según párrafo
                if hints.get('speed'):
                    self.speed = (hints['speed'] / 145.0) * 0.95  # Mantener tu factor base

                msg = f"🎯 Frase {phrase_idx + 1}: Aplicando hints prosódicos"
                if paragraph_id is not None:
                    msg += f" (Párrafo {paragraph_id + 1})"

                if log_callback:
                    log_callback(msg)
                print(f"    {msg}")

                # Usar tu función original con texto modificado
                try:
                    engine_text = self._prepare_text_for_engine(text_to_generate)
                    # PROACTIVO: evitar bucles internos del motor con preguntas largas
                    if self._is_risky_text_for_engine(engine_text):
                        if log_callback:
                            reason = self._risky_reason(engine_text)
                            preview = engine_text[:120]
                            log_callback(f"⚠️ Texto arriesgado para motor: {reason} | len={len(engine_text)} | '{preview}...'")
                        audio = self._engine_generate_in_parts(engine_text, phrase_idx, log_callback)
                    else:
                        try:
                            audio = self.generate_single_phrase_with_validation(engine_text, phrase_idx)
                        except BaseException as e_primary:
                            # Si el motor quiere terminar (SystemExit), intentamos fallbacks antes de respetarlo
                            if log_callback:
                                log_callback(f"⚠️ Motor falló en intento primario: {e_primary}")
                            # Reintento con saneado agresivo
                            safe_text = self._prepare_text_for_engine(engine_text, aggressive=True)
                            try:
                                audio = self.generate_single_phrase_with_validation(safe_text, phrase_idx)
                            except BaseException as e_secondary:
                                # Fallback: dividir en partes y concatenar
                                if log_callback:
                                    log_callback(f"🔀 Dividiendo en partes por estabilidad del motor ({str(e_secondary)})")
                                audio = self._engine_generate_in_parts(engine_text, phrase_idx, log_callback)
                finally:
                    # RESTAURAR parámetros originales
                    self.nfe_steps = original_nfe
                    self.sway_sampling_coef = original_sway
                    self.cfg_strength = original_cfg
                    self.speed = original_speed

                    # Limpiar memoria después de la generación si usa CUDA
                    if self.device == "cuda":
                        torch.cuda.empty_cache()

                return audio
            else:
                # Posición no crítica, usar generación normal
                engine_text = self._prepare_text_for_engine(text)
                # PROACTIVO: evitar bucles con preguntas largas
                if self._is_risky_text_for_engine(engine_text):
                    if log_callback:
                        reason = self._risky_reason(engine_text)
                        preview = engine_text[:120]
                        log_callback(f"⚠️ Texto arriesgado para motor: {reason} | len={len(engine_text)} | '{preview}...'")
                    return self._engine_generate_in_parts(engine_text, phrase_idx, log_callback)
                try:
                    return self.generate_single_phrase_with_validation(engine_text, phrase_idx)
                except BaseException as e_primary:
                    # Reintento con texto aún más neutro si el motor falla
                    safe_text = self._prepare_text_for_engine(engine_text, aggressive=True)
                    if log_callback:
                        log_callback(f"🔁 Reintentando con texto saneado: '{safe_text[:60]}...' ({e_primary})")
                    try:
                        return self.generate_single_phrase_with_validation(safe_text, phrase_idx)
                    except BaseException as e_secondary:
                        # Fallback: dividir en partes y concatenar
                        if log_callback:
                            log_callback(f"🔀 Dividiendo en partes por estabilidad del motor ({str(e_secondary)})")
                        return self._engine_generate_in_parts(engine_text, phrase_idx, log_callback)
        else:
            # Sin prosodia, usar tu función original tal como es
            return self.generate_single_phrase_with_validation(text, phrase_idx)

    def is_critical_position(self, phrase_idx: int, total_phrases: int, text: str) -> bool:
        """
        Determina si es una posición crítica que necesita hints prosódicos
        """
        # Primeras 2 frases (establecer tono)
        if phrase_idx < 2:
            return True

        # Últimas 2 frases (cadencia final)
        if phrase_idx >= total_phrases - 2:
            return True

        # Preguntas
        if '?' in text:
            return True

        # Exclamaciones
        if '!' in text:
            return True

        # Posibles límites de párrafo (cada ~10 frases)
        if phrase_idx > 0 and phrase_idx % 10 == 0:
            return True

        # Frases largas con punto final (posibles finales de párrafo)
        if len(text) > 150 and text.strip().endswith('.'):
            return True

        return False

    def _prepare_text_for_engine(self, text: str, aggressive: bool = False) -> str:
        """
        Sanea el texto para el motor F5-TTS evitando puntuaciones que pueden provocar errores internos.
        - Elimina signos invertidos iniciales ('¿', '¡') pero preserva '?'/'!' finales.
        - Sustituye comas/';'/' :' finales por punto.
        - Colapsa múltiples signos.
        - En modo agresivo, elimina comillas y guiones y fuerza punto final.
        """
        import re

        s = (text or "").strip()

        # Normalizar ellipsis y variantes (… o ... -> .)
        s = s.replace('\u2026', '...')
        s = re.sub(r'\.{3,}', '.', s)

        # Correcciones típicas que desestabilizan el motor (solo para engine)
        replacements = {
            r"\bke\b": "que",
            r"\bk\b": "que",
            r"\beyos\b": "ellos",
            r"\bexijen\b": "exigen",
            r"\bnibel\b": "nivel",
            r"\bbida\b": "vida",
            r"\bboomer\b": "persona mayor",
        }
        for pattern, repl in replacements.items():
            s = re.sub(pattern, repl, s, flags=re.IGNORECASE)

        # Eliminar signos invertidos de apertura; mantener '?/!' finales para entonación
        s = re.sub(r'^[¡¿]+', '', s)

        # Quitar guion/raya inicial con espacios
        s = re.sub(r'^[\-–—]\s*', '', s)

        # Reemplazar puntuación final problemática por punto
        s = re.sub(r'[:,;]+\s*$', '.', s)

        # Colapsar repeticiones de signos
        s = re.sub(r'([.!?])\1{1,}', r'\1', s)

        # Evitar frases que terminen en coma
        s = re.sub(r',\s*$', '.', s)

        # Completar cláusulas que terminan en preposición o 'que'
        if re.search(r'(\b(que|a|de|para|por|con|sin|sobre|hasta|entre|según|tras))\.$', s, re.IGNORECASE):
            s = re.sub(r'\.$', ' hacerlo.', s)

        if aggressive:
            # Retirar comillas, dobles y tipográficas
            s = re.sub(r'["“”]', '', s)
            # Retirar guiones/rayas en medio sueltos
            s = re.sub(r'\s[\-–—]\s', ' ', s)
            # Forzar punto final si no hay puntuación
            if not s.endswith(('.', '!', '?')):
                s = s.rstrip() + '.'

        # Asegurar que no quede vacío
        if not s.strip():
            s = '...'

        return s.strip()

    def _engine_generate_in_parts(self, text: str, phrase_idx: int, log_callback=None):
        """
        Genera el audio en varias partes para textos que causan inestabilidad en el motor.
        """
        parts = self._split_text_for_engine(text)
        if log_callback:
            log_callback(f"✂️ División en {len(parts)} partes (chars/words): " + 
                         ", ".join([f"{len(p)}c/{len((p or '').split())}w" for p in parts]))
        audio_segments = []
        strict_err = False
        for i, p in enumerate(parts):
            try:
                # Preparar cada parte
                p_prepared = self._prepare_text_for_engine(p)
                if log_callback and p_prepared != p:
                    log_callback(f"   ↪️ Parte {i+1}: saneada '{p_prepared[:80]}...'")
                seg = self.generate_single_phrase_with_validation(p_prepared, phrase_idx)
                if seg is not None and len(seg) > 0:
                    audio_segments.append(seg)
                    continue
                # Reintento agresivo por parte
                p_safe = self._prepare_text_for_engine(p_prepared, aggressive=True)
                if log_callback:
                    log_callback(f"   🔁 Parte {i+1}: agresivo '{p_safe[:80]}...'")
                seg = self.generate_single_phrase_with_validation(p_safe, phrase_idx)
                if seg is not None and len(seg) > 0:
                    audio_segments.append(seg)
                    continue
                # Reintentos con parámetros muy seguros
                if log_callback:
                    log_callback(f"   🛡️ Parte {i+1}: intentando con parámetros seguros (preset A)")
                seg = self._generate_with_safe_params(p_prepared, phrase_idx, log_callback, preset='safe1')
                if seg is not None and len(seg) > 0:
                    audio_segments.append(seg)
                    continue
                if log_callback:
                    log_callback(f"   🛡️ Parte {i+1}: intentando con parámetros extra conservadores (preset B)")
                seg = self._generate_with_safe_params(p_prepared, phrase_idx, log_callback, preset='safe2')
                if seg is not None and len(seg) > 0:
                    audio_segments.append(seg)
                    continue
                # Completar cláusula si termina en preposición/'que' y reintentar
                import re as _re
                if _re.search(r'(\b(que|a|de|para|por|con|sin|sobre|hasta|entre|según|tras))\.$', p_prepared, _re.IGNORECASE):
                    p_completed = _re.sub(r'\.$', ' hacerlo.', p_prepared)
                    if log_callback:
                        log_callback(f"   🧩 Parte {i+1}: completando cláusula → '{p_completed[:80]}...'")
                    seg = self._generate_with_safe_params(p_completed, phrase_idx, log_callback, preset='safe2')
                    if seg is not None and len(seg) > 0:
                        audio_segments.append(seg)
                        continue
                # Último recurso: intentar en CPU con preset conservador
                if self.device == 'cuda':
                    try:
                        if log_callback:
                            log_callback(f"   🧪 Parte {i+1}: intento en CPU con preset conservador")
                        seg = self._generate_on_cpu_with_safe_params(p_prepared, phrase_idx, log_callback)
                        if seg is not None and len(seg) > 0:
                            audio_segments.append(seg)
                            continue
                    except BaseException as e_cpu:
                        if isinstance(e_cpu, SystemExit) or 't must be strictly increasing or decreasing' in str(e_cpu):
                            strict_err = True
                        if log_callback:
                            log_callback(f"   ❌ CPU fallback falló: {e_cpu}")
                        # continuar con otras partes
                        pass
                # Fallback con padding y recorte del núcleo
                try:
                    if log_callback:
                        log_callback(f"   🧷 Parte {i+1}: generando con prefijo/sufijo neutro y recortando núcleo")
                    seg = self._generate_padded_and_trim(p_prepared, phrase_idx, log_callback)
                    if seg is not None and len(seg) > 0:
                        audio_segments.append(seg)
                        continue
                except BaseException as e_pad:
                    if isinstance(e_pad, SystemExit) or 't must be strictly increasing or decreasing' in str(e_pad):
                        strict_err = True
                    if log_callback:
                        log_callback(f"   ❌ Padding fallback falló: {e_pad}")
            except BaseException as e:
                # Incluir SystemExit como error crítico pero permitir continuar con otras partes
                if isinstance(e, SystemExit) or 't must be strictly increasing or decreasing' in str(e):
                    strict_err = True
                if log_callback:
                    log_callback(f"❌ Parte {i+1}/{len(parts)} falló: {e}")
                continue

        # Si no conseguimos nada y solo era 1 parte, intentar micro-división por palabras
        if not audio_segments and len(parts) == 1:
            words = (parts[0] or '').split()
            if len(words) > 1:
                if log_callback:
                    log_callback("🔬 Reintentando con micro-división en trozos de 3-4 palabras y parámetros seguros")
                micro_segments = []
                for start in range(0, len(words), 4):
                    chunk = ' '.join(words[start:start+4]).strip()
                    if not chunk:
                        continue
                    chunk = self._prepare_text_for_engine(chunk, aggressive=True)
                    try:
                        seg = self._generate_with_safe_params(chunk, phrase_idx, log_callback, preset='safe2')
                        if seg is not None and len(seg) > 0:
                            micro_segments.append(seg)
                    except BaseException as e:
                        if isinstance(e, SystemExit) or 't must be strictly increasing or decreasing' in str(e):
                            strict_err = True
                        if log_callback:
                            log_callback(f"   ❌ Micro-parte falló: {e}")
                        continue
                if micro_segments:
                    audio_segments = micro_segments

        if not audio_segments:
            # Todos los fallbacks fallaron: guardar estado, liberar GPU y abortar
            if log_callback:
                log_callback("🛑 Todos los fallbacks han fallado. Guardando estado y deteniendo ejecución…")
            try:
                import json
                from pathlib import Path as _Path
                resume_state = {
                    'context': 'prosody_enhanced_generator',
                    'phrase_idx': phrase_idx,
                    'reference_file': str(self.reference_file) if hasattr(self, 'reference_file') else '',
                    'session_dir': str(self.output_dir) if hasattr(self, 'output_dir') else '',
                    'device': self.device,
                }
                _Path('resume_state.json').write_text(json.dumps(resume_state, indent=2), encoding='utf-8')
            except Exception:
                pass
            self._shutdown_gpu(log_callback)
            raise SystemExit("ENGINE_STRICT_T_ERROR")

        # Concatenar con crossfade para suavizar
        try:
            if log_callback:
                log_callback(f"🔗 Concatenando {len(audio_segments)} segmentos parciales con crossfade")
            return self.apply_crossfade_and_concatenate(audio_segments)
        except Exception:
            return np.concatenate(audio_segments)

    def _split_text_for_engine(self, text: str, max_words: int = 12) -> list:
        """
        Divide el texto en 2-3 partes buscando comas o el centro.
        Asegura puntuación final en la parte inicial y conserva '?'/'!' en la final.
        """
        import re
        s = (text or '').strip()
        # Si está por debajo del umbral de palabras, devolver tal cual
        if len(s.split()) <= max_words:
            return [s]

        def _avoid_bad_endings(left: str, right: str) -> tuple:
            bad_tokens = {"que","a","de","para","por","con","sin","sobre","hasta","entre","según","tras"}
            left_tokens = (left.rstrip('.,!?') or '').split()
            if left_tokens:
                last = left_tokens[-1].lower()
                if last in bad_tokens and right:
                    r_words = right.split()
                    # mover una palabra (o dos si es muy corta) al left
                    take = 2 if len(r_words) > 4 else 1
                    moved = ' '.join(r_words[:take])
                    right = ' '.join(r_words[take:])
                    left = left.rstrip('.,!?') + ' ' + moved
                    if not left.endswith(('.', '!', '?')):
                        left += '.'
            return left.strip(), right.strip()

        # Intentar dividir por coma cercana al centro
        commas = [m.start() for m in re.finditer(r',', s)]
        target = len(s) // 2
        if commas:
            split_pos = min(commas, key=lambda x: abs(x - target))
            left = s[:split_pos+1].strip()
            right = s[split_pos+1:].strip()
            # Asegurar puntuación
            if not left.endswith(('.', '!', '?')):
                left = left.rstrip(',') + '.'
            left, right = _avoid_bad_endings(left, right)
            # Evitar right demasiado corto
            if len(right.split()) < 3:
                return [s]
            # Asegurar que cada parte no exceda max_words
            final = []
            for part in [left, right]:
                if len(part.split()) > max_words:
                    final.extend(self._split_text_for_engine(part, max_words))
                else:
                    final.append(part)
            return final
        # Intentar dividir por conectores
        connector = re.search(r'\s(y|pero|porque|aunque|entonces|así que|o)\s', s)
        if connector:
            pos = connector.start(0) + 1
            left = s[:pos].strip()
            right = s[pos:].strip()
            if not left.endswith(('.', '!', '?')):
                left += '.'
            left, right = _avoid_bad_endings(left, right)
            if len(right.split()) < 3:
                return [s]
            final = []
            for part in [left, right]:
                if len(part.split()) > max_words:
                    final.extend(self._split_text_for_engine(part, max_words))
                else:
                    final.append(part)
            return final
        # Último recurso: dividir por espacio en el medio
        words = s.split()
        mid = len(words) // 2
        left = ' '.join(words[:mid]).strip()
        right = ' '.join(words[mid:]).strip()
        if not left.endswith(('.', '!', '?')):
            left += '.'
        left, right = _avoid_bad_endings(left, right)
        if len(right.split()) < 3:
            return [s]
        final = []
        for part in [left, right]:
            if len(part.split()) > max_words:
                final.extend(self._split_text_for_engine(part, max_words))
            else:
                final.append(part)
        return final

    def _is_risky_text_for_engine(self, s: str) -> bool:
        """Heurística para detectar textos que disparan bucles/errores en el motor."""
        s_clean = (s or '').strip()
        if len(s_clean) == 0:
            return True
        # Preguntas largas o con múltiples cláusulas sin coma
        if s_clean.endswith('?') and len(s_clean) > 90:
            return True
        # Exceso de signos seguidos
        if '??' in s_clean or '!!' in s_clean:
            return True
        # Mucha puntuación o símbolos especiales
        bad_chars = [';', ':', '—', '–']
        if any(c in s_clean for c in bad_chars) and len(s_clean) > 80:
            return True
        return False

    def _risky_reason(self, s: str) -> str:
        s_clean = (s or '').strip()
        if len(s_clean) == 0:
            return 'vacío'
        reasons = []
        if s_clean.endswith('?') and len(s_clean) > 90:
            reasons.append('pregunta larga')
        if '??' in s_clean or '!!' in s_clean:
            reasons.append('signos repetidos')
        if any(c in s_clean for c in [';', ':', '—', '–']) and len(s_clean) > 80:
            reasons.append('puntuación pesada')
        return ', '.join(reasons) or 'heurística general'

    def _shutdown_gpu(self, log_callback=None):
        """Libera memoria GPU (sin reset para no afectar GPU primaria)."""
        try:
            if self.device == 'cuda':
                if log_callback:
                    log_callback('🔻 Liberando memoria GPU (sin reset)…')
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                torch.cuda.ipc_collect()
        except Exception as e:
            if log_callback:
                log_callback(f'⚠️ No se pudo liberar memoria GPU: {e}')

    def generate_all_phrases_with_prosody(self, enable_postprocessing=False, log_callback=None):
        """
        Versión mejorada de tu generate_all_phrases que añade arquitectura prosódica
        """

        if log_callback:
            log_callback(f"🎵 Iniciando generación con mejoras prosódicas")
        print(f"\n🎵 GENERACIÓN CON MEJORA PROSÓDICA")
        print(f"{'='*50}")

        # Detectar estructura de párrafos
        paragraph_boundaries = self.detect_paragraph_structure()
        total_phrases = len(self.frases)

        if log_callback:
            log_callback(f"📚 Párrafos detectados: {len(paragraph_boundaries)}")
        print(f"📚 Estructura detectada: {len(paragraph_boundaries)} párrafos")

        # Contar posiciones críticas
        critical_count = 0
        for i, frase in enumerate(self.frases):
            if self.is_critical_position(i, total_phrases, frase):
                critical_count += 1

        self.prosody_stats['critical_positions'] = critical_count

        if log_callback:
            log_callback(f"🎯 Posiciones críticas identificadas: {critical_count}/{total_phrases} ({critical_count/total_phrases*100:.1f}%)")
        print(f"🎯 Posiciones críticas: {critical_count}/{total_phrases} ({critical_count/total_phrases*100:.1f}%)")

        # FASE 1: Generación con hints prosódicos
        print(f"\n📝 FASE 1: Generación con hints prosódicos")

        generated_audios = []
        start_time = time.time()

        for i, frase in enumerate(self.frases):
            if log_callback:
                log_callback(f"Procesando frase {i+1}/{total_phrases}")

            # Determinar párrafo actual
            paragraph_id = self.get_paragraph_id(i, paragraph_boundaries)

            try:
                # Usar versión con prosodia
                audio = self.generate_single_phrase_with_prosody(
                    frase, i, total_phrases, paragraph_id, log_callback
                )

                if audio is not None and len(audio) > 0:
                    generated_audios.append((i, audio))
                    if log_callback:
                        log_callback(f"✅ Frase {i+1} generada exitosamente")
                else:
                    if log_callback:
                        log_callback(f"❌ Frase {i+1} falló en generación")

            except Exception as e:
                error_msg = f"❌ Error en frase {i+1}: {e}"
                if log_callback:
                    log_callback(error_msg)
                print(f"    {error_msg}")

        generation_time = time.time() - start_time

        if log_callback:
            log_callback(f"✅ Fase 1 completada: {len(generated_audios)} frases generadas")
            log_callback(f"📊 Hints aplicados: {self.prosody_stats['hints_applied']}/{total_phrases}")

        print(f"\n✅ Fase 1 completada:")
        print(f"   Frases generadas: {len(generated_audios)}/{total_phrases}")
        print(f"   Hints prosódicos aplicados: {self.prosody_stats['hints_applied']}")
        print(f"   Tiempo de generación: {generation_time:.1f}s")

        # FASE 2: Post-procesamiento (opcional)
        if enable_postprocessing and len(generated_audios) > 0:
            if log_callback:
                log_callback("\n🔧 FASE 2: Post-procesamiento prosódico")
            print(f"\n🔧 FASE 2: Post-procesamiento prosódico")

            # Extraer audios y textos
            audio_segments = [audio for _, audio in generated_audios]
            text_segments = [self.frases[idx] for idx, _ in generated_audios]

            # Analizar prosodia
            if log_callback:
                log_callback("📊 Analizando prosodia...")
            analysis = self.analyzer.analyze_complete_audio(audio_segments, text_segments)

            # Detectar problemas
            problems = self.detector.identify_problems(analysis)
            self.prosody_stats['problems_detected'] = len(problems)

            if log_callback:
                log_callback(f"🔍 Problemas detectados: {len(problems)}")
            print(f"   Problemas detectados: {len(problems)}")

            if problems:
                critical_problems = [p for p in problems if p['severity'] > 0.3][:5]

                if critical_problems:
                    if log_callback:
                        log_callback(f"🔧 Corrigiendo {len(critical_problems)} problemas críticos...")
                    print(f"   Corrigiendo {len(critical_problems)} problemas críticos...")

                    # Usar regenerador con tu modelo F5TTS
                    # Asegurar que el regenerador tenga acceso a la referencia de audio
                    regenerator = SelectiveRegenerator(self.f5tts, max_fixes=5)

                    # Configurar regenerador con contexto de referencia
                    if hasattr(regenerator, 'set_reference_context'):
                        regenerator.set_reference_context(str(self.reference_file), "")

                    corrected_segments, fix_report = regenerator.fix_critical_problems(
                        problems, audio_segments, text_segments, severity_threshold=0.3
                    )

                    # Reemplazar segmentos originales por los corregidos
                    audio_segments = corrected_segments
                    for i, corrected_audio in enumerate(corrected_segments):
                        if i < len(generated_audios):
                            generated_audios[i] = (generated_audios[i][0], corrected_audio)

                    self.prosody_stats['problems_fixed'] = fix_report['successful']

                    if log_callback:
                        log_callback(f"✅ Problemas corregidos: {fix_report['successful']}/{fix_report['attempted']}")
                    print(f"   ✅ Corregidos: {fix_report['successful']}/{fix_report['attempted']}")

        return generated_audios

    def detect_paragraph_structure(self):
        """
        Detecta la estructura de párrafos en las frases
        """
        boundaries = [0]

        # Detectar por tus marcadores originales si existen
        if hasattr(self, 'paragraph_breaks') and self.paragraph_breaks:
            for break_point in self.paragraph_breaks:
                if 0 < break_point < len(self.frases):
                    boundaries.append(break_point)
        else:
            # Heurística: dividir en tercios para arquitectura de 3 párrafos
            total = len(self.frases)
            if total > 6:
                boundaries.extend([total // 3, 2 * total // 3])

        return sorted(list(set(boundaries)))

    def get_paragraph_id(self, phrase_idx: int, boundaries: list) -> int:
        """
        Determina el ID del párrafo para una frase dada
        """
        for i in range(len(boundaries) - 1):
            if boundaries[i] <= phrase_idx < boundaries[i + 1]:
                return i
        return min(2, len(boundaries) - 1)  # Máximo 3 párrafos

    def apply_crossfade_and_concatenate(self, audio_segments):
        """
        Concatena segmentos de audio usando crossfade suave
        Método requerido por el sistema de generación prosódica

        VERSIÓN 2.0: Incluye pausas inteligentes entre párrafos
        """
        if not audio_segments:
            return np.array([])

        if len(audio_segments) == 1:
            return audio_segments[0]

        # Usar crossfade de 150ms por defecto
        crossfade_samples = int(0.15 * self.sample_rate)

        result = audio_segments[0]

        for i in range(1, len(audio_segments)):
            current_segment = audio_segments[i]

            # NUEVO: Detectar si necesitamos pausa entre párrafos
            pausa_extra = self._calcular_pausa_entre_segmentos(i, len(audio_segments))

            # Añadir silencio si es necesario
            if pausa_extra > 0:
                silencio_samples = int(pausa_extra * self.sample_rate)
                silencio = np.zeros(silencio_samples)
                result = np.concatenate([result, silencio])

            # Aplicar crossfade
            if len(result) >= crossfade_samples and len(current_segment) >= crossfade_samples:
                # Crear rampas de fade
                fade_out = np.linspace(1.0, 0.0, crossfade_samples)
                fade_in = np.linspace(0.0, 1.0, crossfade_samples)

                # Aplicar fades
                result_end = result[-crossfade_samples:] * fade_out
                segment_start = current_segment[:crossfade_samples] * fade_in

                # Mezclar la región de overlap
                overlap = result_end + segment_start

                # Concatenar
                result = np.concatenate([
                    result[:-crossfade_samples],
                    overlap,
                    current_segment[crossfade_samples:]
                ])
            else:
                # Si los segmentos son muy cortos, concatenar directamente
                result = np.concatenate([result, current_segment])

        return result

    def _calcular_pausa_entre_segmentos(self, indice_segmento: int, total_segmentos: int) -> float:
        """
        Calcula pausa adicional entre segmentos según el contexto
        Añade pausas especiales entre párrafos si el orquestador maestro está disponible
        """
        # Si hay orquestador maestro disponible, usar sus pausas calculadas
        if (hasattr(self.prosody_hint_gen, 'control_matrix') and
            self.prosody_hint_gen.control_matrix and
            indice_segmento < len(self.prosody_hint_gen.control_matrix)):

            # Obtener parámetros del segmento anterior
            params_anterior = self.prosody_hint_gen.control_matrix[indice_segmento - 1]

            # Si la pausa calculada es superior a 1.2s, probablemente es final de párrafo
            if params_anterior.pausa_final > 1.2:
                return min(params_anterior.pausa_final - 0.8, 1.0)  # Añadir pausa extra hasta 1s max

        # Fallback: pausas heurísticas simples
        # Cada ~10 segmentos, añadir pausa (aproximación de párrafos)
        if indice_segmento > 0 and indice_segmento % 10 == 0:
            return 0.4  # 400ms extra entre párrafos

        return 0.0  # Sin pausa extra

    def apply_smart_concatenation(self, generated_audios):
        """
        Aplica concatenación inteligente usando la lógica original del generador
        Método requerido para compatibilidad con GUI
        """
        if not generated_audios:
            return np.array([])

        # Extraer solo los audios de las tuplas (índice, audio)
        audio_segments = [audio for _, audio in generated_audios]

        # Usar el método de crossfade
        return self.apply_crossfade_and_concatenate(audio_segments)

    def save_prosody_report(self, output_path: Path):
        """
        Guarda reporte de mejoras prosódicas aplicadas
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_phrases': len(self.frases),
            'prosody_stats': self.prosody_stats,
            'original_params': {
                'nfe_steps': self.nfe_steps,
                'sway_sampling_coef': self.sway_sampling_coef,
                'cfg_strength': self.cfg_strength,
                'speed': self.speed
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def _generate_with_safe_params(self, text: str, phrase_idx: int, log_callback=None, preset: str = 'safe1'):
        """Genera usando parámetros conservadores temporales, restaurando después."""
        original_nfe = self.nfe_steps
        original_sway = self.sway_sampling_coef
        original_cfg = self.cfg_strength
        original_speed = self.speed
        try:
            if preset == 'safe1':
                self.nfe_steps = max(20, min(32, 28))
                self.sway_sampling_coef = -0.3
                self.cfg_strength = 1.5
                self.speed = 1.0
            else:  # safe2 más conservador
                self.nfe_steps = max(16, min(28, 24))
                self.sway_sampling_coef = -0.15
                self.cfg_strength = 1.2
                self.speed = 1.0
            t = self._prepare_text_for_engine(text, aggressive=True)
            return self.generate_single_phrase_with_validation(t, phrase_idx)
        except BaseException as e:
            if log_callback:
                log_callback(f"   ⚠️ Falló preset {'A' if preset=='safe1' else 'B'}: {e}")
            raise
        finally:
            self.nfe_steps = original_nfe
            self.sway_sampling_coef = original_sway
            self.cfg_strength = original_cfg
            self.speed = original_speed

    def _generate_on_cpu_with_safe_params(self, text: str, phrase_idx: int, log_callback=None):
        """Reintento extremo: cambia temporalmente a CPU con parámetros muy conservadores."""
        original_device = self.device
        original_model = self.f5tts if hasattr(self, 'f5tts') else None
        original_nfe = self.nfe_steps
        original_sway = self.sway_sampling_coef
        original_cfg = self.cfg_strength
        original_speed = self.speed
        try:
            # Cambiar a CPU y recargar modelo
            self.device = 'cpu'
            self.f5tts = None
            self.ensure_model_loaded()
            # Parámetros extra conservadores
            self.nfe_steps = 24
            self.sway_sampling_coef = -0.1
            self.cfg_strength = 1.2
            self.speed = 1.0
            t = self._prepare_text_for_engine(text, aggressive=True)
            return self.generate_single_phrase_with_validation(t, phrase_idx)
        finally:
            # Restaurar
            self.nfe_steps = original_nfe
            self.sway_sampling_coef = original_sway
            self.cfg_strength = original_cfg
            self.speed = original_speed
            self.device = original_device
            self.f5tts = original_model
            # No forzar recarga aquí; se recargará on-demand si es necesario

    def _generate_padded_and_trim(self, text: str, phrase_idx: int, log_callback=None):
        """Genera con prefijo/sufijo neutro para estabilizar y recorta para conservar solo el núcleo de la frase."""
        # Construir texto acolchado
        core = (text or '').strip().rstrip('.!?')
        padded = f"Por favor, {core}. Gracias."
        # Intento con parámetros seguros
        try:
            audio = self._generate_with_safe_params(padded, phrase_idx, log_callback, preset='safe2')
        except BaseException:
            # Intento en CPU si falla
            audio = self._generate_on_cpu_with_safe_params(padded, phrase_idx, log_callback)
        if audio is None or len(audio) == 0:
            return None
        # Recorte heurístico: buscar región central no silenciosa
        try:
            import numpy as _np
            import librosa as _lib
            sr = self.sample_rate
            # Ignorar primeros/últimos 0.4s para evitar prefijo/sufijo
            start_guard = int(0.4 * sr)
            end_guard = int(0.4 * sr)
            y = audio.copy()
            if len(y) <= start_guard + end_guard:
                return audio
            y_mid = y[start_guard: len(y) - end_guard]
            # Detectar intervalos no silenciosos
            intervals = _lib.effects.split(y_mid, top_db=30)
            if intervals is None or len(intervals) == 0:
                return y_mid
            # Seleccionar el intervalo más largo (núcleo probable)
            lengths = [(i[1] - i[0]) for i in intervals]
            idx_max = int(_np.argmax(lengths))
            seg = y_mid[intervals[idx_max][0]: intervals[idx_max][1]]
            # Pequeño margen de ataque/caída
            pad = int(0.02 * sr)
            a = max(0, intervals[idx_max][0] - pad)
            b = min(len(y_mid), intervals[idx_max][1] + pad)
            return y_mid[a:b]
        except Exception:
            # Si el recorte falla, devolver parte central sin guardas
            return audio[start_guard: len(audio) - end_guard]


class ProsodyGUI:
    """
    GUI simplificada para tu generador con prosodia
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎵 Tu Generador + Mejora Prosódica")
        self.root.geometry("1000x800")

        # Variables
        self.processing_mode = tk.StringVar(value="fast")
        self.is_processing = False
        self.generator = None

        # Archivos
        self.text_file = Path("texto.txt")
        self.check_reference_files()

        self.setup_ui()

    def check_reference_files(self):
        """Busca automáticamente archivos .wav como tu sistema original"""
        script_dir = Path.cwd()
        wav_files = list(script_dir.glob("*.wav"))

        if not wav_files:
            messagebox.showerror("Sin audio de referencia",
                               "No se encontraron archivos .wav en el directorio.\n"
                               "Por favor, coloca al menos un archivo de audio de referencia.")
            return

        # Usar el primero encontrado o segment_2955.wav si existe
        self.reference_files = wav_files
        if any(f.name == "segment_2955.wav" for f in wav_files):
            self.primary_ref = Path("segment_2955.wav")
        else:
            self.primary_ref = wav_files[0]

        print(f"🎤 Referencias encontradas: {[f.name for f in wav_files]}")
        print(f"🎯 Referencia principal: {self.primary_ref.name}")

    def setup_ui(self):
        """Configura la interfaz"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Título
        title_label = ttk.Label(main_frame,
                               text="🎵 Tu Generador Original + Mejora Prosódica",
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)

        # Info archivos
        info_frame = ttk.LabelFrame(main_frame, text="📁 Archivos Detectados", padding="10")
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(info_frame, text="📝 Texto:").grid(row=0, column=0, sticky=tk.W)
        text_status = "✅ Encontrado" if self.text_file.exists() else "❌ Faltante"
        ttk.Label(info_frame, text=f"{self.text_file} - {text_status}").grid(row=0, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_frame, text="🎤 Referencias:").grid(row=1, column=0, sticky=tk.W)
        ref_text = f"{len(self.reference_files)} archivos .wav encontrados"
        ttk.Label(info_frame, text=ref_text).grid(row=1, column=1, sticky=tk.W, padx=10)

        # Opciones de prosodia
        prosody_frame = ttk.LabelFrame(main_frame, text="🎵 Mejoras Prosódicas", padding="10")
        prosody_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Radiobutton(prosody_frame, text="🚀 Rápido (Solo hints prosódicos en posiciones críticas)",
                       variable=self.processing_mode, value="fast").grid(row=0, column=0, sticky=tk.W)

        ttk.Radiobutton(prosody_frame, text="🔧 Completo (Con post-procesamiento + correcciones)",
                       variable=self.processing_mode, value="full").grid(row=1, column=0, sticky=tk.W)

        # Descripción
        desc_text = """
🎯 Tu sistema original mantenido al 100%:
• Validación anti-truncamiento
• Parámetros optimizados (NFE=64, Sway=-1.0, etc.)
• Calidad de audio preservada

➕ Mejoras prosódicas añadidas:
• Arquitectura vocal de 3 párrafos (BBC)
• Arco prosódico (Lieberman)
• Cadencias naturales en finales
• Énfasis en preguntas/exclamaciones
        """
        desc_label = ttk.Label(prosody_frame, text=desc_text, foreground="gray")
        desc_label.grid(row=2, column=0, pady=10)

        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)

        self.generate_button = ttk.Button(button_frame, text="🎵 Generar con Prosodia",
                                         command=self.start_generation,
                                         style="Accent.TButton")
        self.generate_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(button_frame, text="⏹️ Detener",
                                     command=self.stop_generation,
                                     state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)

        # Progreso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var,
                                           maximum=100, length=900)
        self.progress_bar.grid(row=4, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))

        self.status_label = ttk.Label(main_frame, text="Listo para generar")
        self.status_label.grid(row=5, column=0, columnspan=3)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="📋 Registro", padding="10")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=120, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configurar expansión
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def log(self, message):
        """Añade mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, full_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def start_generation(self):
        """Inicia la generación"""
        if self.is_processing:
            return

        if not self.text_file.exists():
            messagebox.showerror("Error", f"No se encuentra {self.text_file}")
            return

        self.is_processing = True
        self.generate_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)

        # Iniciar en thread separado
        thread = threading.Thread(target=self.run_generation)
        thread.daemon = True
        thread.start()

    def run_generation(self):
        """Ejecuta la generación"""
        try:
            # Leer texto
            with open(self.text_file, 'r', encoding='utf-8') as f:
                texto_usuario = f.read()

            # Crear generador híbrido
            self.log("🔄 Inicializando generador híbrido...")
            self.generator = ProsodyEnhancedGenerator(texto_usuario=texto_usuario)

            # Configurar modo
            enable_postprocessing = (self.processing_mode.get() == "full")
            self.generator.enable_postprocessing = enable_postprocessing

            mode_text = "completo con post-procesamiento" if enable_postprocessing else "rápido con hints"
            self.log(f"⚙️ Modo seleccionado: {mode_text}")

            # Procesar cada referencia de audio (como tu sistema original)
            for ref_file in self.reference_files:
                if not self.is_processing:
                    break

                self.log(f"\n🎤 Procesando con referencia: {ref_file.name}")

                # Configurar referencia
                self.generator.reference_file = ref_file.name
                self.generator.output_dir = self.generator.session_dir / ref_file.stem
                self.generator.output_dir.mkdir(exist_ok=True)

                # Inicializar modelo
                self.generator.initialize_model()

                # Generar con prosodia
                generated_audios = self.generator.generate_all_phrases_with_prosody(
                    enable_postprocessing=enable_postprocessing,
                    log_callback=self.log
                )

                if generated_audios:
                    # Concatenar usando tu método original
                    self.log("🔗 Concatenando audio final...")
                    final_audio = self.generator.apply_smart_concatenation(generated_audios)

                    # Guardar resultado
                    output_name = f"estructura_compleja_prosody_nfe{self.generator.nfe_steps}.wav"
                    output_path = self.generator.output_dir / output_name
                    sf.write(output_path, final_audio, self.generator.sample_rate)

                    self.log(f"✅ Audio final guardado: {output_name}")

                    # Guardar reporte prosódico
                    report_path = self.generator.output_dir / "reporte_prosodia.json"
                    self.generator.save_prosody_report(report_path)

            self.log(f"\n🎉 ¡Generación completada exitosamente!")
            self.log(f"📁 Resultados en: {self.generator.session_dir}")

            messagebox.showinfo("Éxito", f"Generación completada.\nResultados en: {self.generator.session_dir}")

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.log(error_msg)
            messagebox.showerror("Error", error_msg)

        finally:
            self.is_processing = False
            self.generate_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_label.config(text="Generación completada")

    def stop_generation(self):
        """Detiene la generación"""
        self.is_processing = False
        self.log("⏹️ Deteniendo generación...")

    def run(self):
        """Ejecuta la aplicación"""
        self.root.mainloop()


def main():
    """Función principal"""
    if not ORIGINAL_AVAILABLE:
        print("❌ No se puede ejecutar sin el generador original")
        print("📥 Por favor, asegúrate de que generar_estructura_compleja_v3.py esté disponible")
        sys.exit(1)

    print("="*70)
    print("🎵 GENERADOR HÍBRIDO: Tu Sistema Original + Mejoras Prosódicas")
    print("="*70)
    print()
    print("✅ Tu generador original preservado al 100%:")
    print("   • Validación anti-truncamiento")
    print("   • Parámetros optimizados (NFE=64, Sway=-1.0, etc.)")
    print("   • Calidad de audio mantenida")
    print()
    print("➕ Mejoras prosódicas añadidas:")
    print("   • Arquitectura vocal documentada")
    print("   • Cadencias naturales")
    print("   • Énfasis automático en preguntas")
    print()

    # Crear y ejecutar GUI
    app = ProsodyGUI()
    app.run()


if __name__ == "__main__":
    main()