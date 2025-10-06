#!/usr/bin/env python3
"""
====================================================================================================
SISTEMA DE MEJORA PROSÓDICA PARA F5-TTS
====================================================================================================

Descripción:
    Módulo central del sistema de mejoras prosódicas. Implementa una arquitectura
    vocal completa basada en principios lingüísticos y acústicos documentados.

Fundamentos Teóricos:
    - Arco Prosódico (Lieberman, 1967; Pierrehumbert, 1980)
      Modelado natural de curvas de entonación en el habla

    - Regla del 3-5-8 (BBC Broadcasting, años 50)
      Patrones rítmicos óptimos para narrativa hablada

    - Sincronización Respiratoria-Sintáctica
      Alineación de pausas con estructura gramatical

Arquitectura del Sistema:

    PARTE 1: GENERACIÓN CON HINTS (Fase ligera)
    --------------------------------------------
    - ProsodyHintGenerator: Genera hints para guiar a F5-TTS
    - Operación rápida, mínimo overhead temporal
    - Mejora la prosodia durante la generación inicial

    PARTE 2: POST-PROCESAMIENTO (Fase exhaustiva)
    ----------------------------------------------
    - ProsodyAnalyzer: Analiza características acústicas del audio generado
    - ProsodyProblemDetector: Identifica problemas prosódicos
    - SelectiveRegenerator: Regenera selectivamente segmentos problemáticos
    - Operación más costosa pero con resultados superiores

Componentes Principales:
    - ProsodyHintGenerator: Generación de hints contextuales
    - ProsodyAnalyzer: Análisis espectral y temporal
    - ProsodyProblemDetector: Detección de anomalías prosódicas
    - SelectiveRegenerator: Corrección selectiva
    - ProsodyOrchestrator: Orquestación global (opcional)

Autor: Sistema de generación prosódica F5-TTS
Versión: 2.0
====================================================================================================
"""

import numpy as np
import librosa
import soundfile as sf
from typing import List, Dict, Tuple, Optional, Any
import re
import time
from dataclasses import dataclass
from pathlib import Path
import logging
import sys

# ====================================================================================================
# CONFIGURACIÓN DE LOGGING
# ====================================================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _import_orquestador_maestro():
    """Intenta importar ArquitecturaVocalMaestra de forma robusta.
    1) Import absoluto si el módulo está en PYTHONPATH
    2) Import relativo si se ejecuta como paquete
    3) Fallback: añadir el directorio actual al sys.path y reintentar absoluto
    """
    from pathlib import Path as _Path
    module_dir = _Path(__file__).parent.resolve()
    # 1. Absoluto
    try:
        from prosody_orchestrator_master import ArquitecturaVocalMaestra  # type: ignore
        return ArquitecturaVocalMaestra
    except Exception as e_abs:
        # 2. Relativo (cuando es paquete)
        try:
            from .prosody_orchestrator_master import ArquitecturaVocalMaestra  # type: ignore
            return ArquitecturaVocalMaestra
        except Exception:
            # 3. Fallback sys.path
            try:
                if str(module_dir) not in sys.path:
                    sys.path.insert(0, str(module_dir))
                from prosody_orchestrator_master import ArquitecturaVocalMaestra  # type: ignore
                return ArquitecturaVocalMaestra
            except Exception as e_fb:
                logger.warning(f"⚠️ No se pudo cargar Orquestador Maestro: {e_fb}")
                return None


# ============================================
# PARTE 1: GENERACIÓN MEJORADA (LIGERA)
# ============================================

class ProsodyHintGenerator:
    """
    Genera hints/modificaciones para la generación inicial
    NO añade mucho tiempo, solo modifica puntos críticos
    Basado en arquitectura vocal para lectura documentada

    VERSIÓN 2.0: Integra el Orquestador Maestro para N párrafos con M frases
    """

    def __init__(self, usar_orquestador_maestro: bool = True):
        self.paragraph_count = 0
        self.sentence_count = 0
        self.rules = self._load_harmonic_rules()
        self.fibonacci_positions = [1, 2, 3, 5, 8, 13, 21]  # Para énfasis natural

        # NUEVO: Orquestador maestro
        self.usar_orquestador_maestro = usar_orquestador_maestro
        self.ArquitecturaVocalMaestra = None
        self.orquestador = None
        self.control_matrix = None
        self.texto_completo = None
        if usar_orquestador_maestro:
            self.ArquitecturaVocalMaestra = _import_orquestador_maestro()
            if self.ArquitecturaVocalMaestra is not None:
                logger.info("✅ Orquestador Maestro habilitado")
            else:
                logger.warning("⚠️ Orquestador Maestro no disponible, usando sistema legacy")
                self.usar_orquestador_maestro = False

    def _load_harmonic_rules(self):
        """
        Reglas armónicas basadas en investigación prosódica
        - Arco prosódico: inicio medio-alto → descenso gradual → cierre -30-50Hz
        - Espiral descendente de 3 párrafos
        - Sincronización respiratoria (12-16 resp/min = pausas de 3.75-5s)
        """
        return {
            # Arquitectura de 3 párrafos (Espiral Descendente)
            'paragraph_tones': [1.0, 1.05, 0.92],  # Base, +3 semitonos, -2 semitonos
            'paragraph_speeds': [145, 160, 130],   # PPM para cada párrafo

            # Reglas de frases (Arco Prosódico)
            'sentence_endings': {
                '.': {'pitch': 0.92, 'pause': 700},   # Descenso definitivo
                '?': {'pitch': 1.18, 'pause': 500},   # Subida 15-20%
                '!': {'pitch': 1.10, 'pause': 600},   # Énfasis moderado
                ',': {'pitch': 1.02, 'pause': 300},   # Micro-ascenso
                ';': {'pitch': 0.98, 'pause': 400},   # Leve descenso
                ':': {'pitch': 1.00, 'pause': 400},   # Mantener
                '...': {'pitch': 0.95, 'pause': 800}, # Suspensivo
            },

            # Control de resonancia por párrafo
            'resonance_modes': {
                1: 'chest_balanced',     # Voz de pecho equilibrada
                2: 'chest_nasal_bright', # Añadir brillantez nasal (urgencia)
                3: 'deep_chest'          # Máxima resonancia de pecho (conclusión)
            },

            # Parámetros F5-TTS específicos para control prosódico
            'f5_params': {
                'nfe_adjustment': {1: 0, 2: 4, 3: -2},  # Ajuste NFE por párrafo
                'sway_adjustment': {1: 0, 2: -0.1, 3: 0.1},  # Ajuste Sway
                'cfg_adjustment': {1: 0, 2: 0.2, 3: -0.1},  # Ajuste CFG
            }
        }

    def prepare_text_for_generation(self,
                                   text: str,
                                   phrase_idx: int,
                                   total_phrases: int,
                                   paragraph_id: Optional[int] = None) -> Dict:
        """
        Prepara el texto con hints para F5-TTS siguiendo arquitectura vocal

        VERSIÓN 2.0: Usa Orquestador Maestro si está disponible,
        fallback al sistema legacy en caso contrario

        Args:
            text: Texto de la frase
            phrase_idx: Índice de la frase actual
            total_phrases: Total de frases en el documento
            paragraph_id: ID del párrafo (0, 1, 2...)

        Returns:
            Dict con texto modificado y parámetros de generación
        """

        # NUEVO: Intentar usar Orquestador Maestro primero
        if self.usar_orquestador_maestro and self.control_matrix:
            params_maestro = self.obtener_parametros_maestros(phrase_idx)
            if params_maestro:
                logger.debug(f"🎭 Usando Orquestador Maestro para frase {phrase_idx + 1}")
                return params_maestro

        # FALLBACK: Sistema legacy (original)
        logger.debug(f"📝 Usando sistema legacy para frase {phrase_idx + 1}")

        # Detectar posición en la estructura
        is_paragraph_start = self._is_paragraph_start(text, phrase_idx)
        is_paragraph_end = self._is_paragraph_end(text, phrase_idx, total_phrases)
        sentence_type = self._detect_sentence_type(text)

        # Determinar párrafo si no se proporciona
        if paragraph_id is None:
            paragraph_id = self._estimate_paragraph_id(phrase_idx, total_phrases)

        # Calcular parámetros base según arquitectura de 3 párrafos
        base_pitch = self.rules['paragraph_tones'][min(paragraph_id, 2)]
        base_speed = self.rules['paragraph_speeds'][min(paragraph_id, 2)]

        # Ajustes F5-TTS específicos
        nfe_adjust = self.rules['f5_params']['nfe_adjustment'].get(min(paragraph_id + 1, 3), 0)
        sway_adjust = self.rules['f5_params']['sway_adjustment'].get(min(paragraph_id + 1, 3), 0)
        cfg_adjust = self.rules['f5_params']['cfg_adjustment'].get(min(paragraph_id + 1, 3), 0)

        # Preparar hints base
        generation_hints = {
            'text': text,
            'pitch_factor': base_pitch,
            'speed': base_speed,
            'extra_params': {
                'nfe_adjustment': nfe_adjust,
                'sway_adjustment': sway_adjust,
                'cfg_adjustment': cfg_adjust,
            },
            'apply_modifications': False,  # Por defecto no modificar
            'maestro_source': False  # Indica que viene del sistema legacy
        }

        # SOLO MODIFICAR PUNTOS CRÍTICOS (Arco Prosódico)

        # Inicio de párrafo: captar atención (+2% pitch)
        if is_paragraph_start:
            generation_hints['extra_params']['energy'] = 1.1
            generation_hints['pitch_factor'] *= 1.02
            generation_hints['apply_modifications'] = True
            logger.info(f"📍 Inicio de párrafo detectado: pitch {generation_hints['pitch_factor']:.2f}")

        # Final de párrafo declarativo: cadencia descendente (-8%)
        elif is_paragraph_end and sentence_type == 'declarative':
            generation_hints['text'] = self._add_prosody_hint(text, 'falling')
            generation_hints['pitch_factor'] *= 0.92
            generation_hints['extra_params']['energy'] = 0.9
            generation_hints['apply_modifications'] = True
            logger.info(f"📍 Final de párrafo declarativo: cadencia descendente")

        # Preguntas: subida clara (+15-20%)
        elif sentence_type == 'interrogative':
            generation_hints['text'] = self._add_prosody_hint(text, 'rising')
            generation_hints['pitch_factor'] *= 1.15
            generation_hints['apply_modifications'] = True
            logger.info(f"❓ Pregunta detectada: subida prosódica")

        # Exclamaciones: énfasis moderado
        elif sentence_type == 'exclamative':
            generation_hints['pitch_factor'] *= 1.10
            generation_hints['extra_params']['energy'] = 1.15
            generation_hints['apply_modifications'] = True
            logger.info(f"❗ Exclamación detectada: énfasis aplicado")

        # Aplicar énfasis en posiciones Fibonacci si es palabra clave
        if self._is_fibonacci_position(phrase_idx, total_phrases):
            generation_hints['extra_params']['energy'] = \
                generation_hints['extra_params'].get('energy', 1.0) * 1.08
            logger.debug(f"🔢 Posición Fibonacci {phrase_idx}: énfasis sutil")

        return generation_hints

    def _add_prosody_hint(self, text: str, hint_type: str) -> str:
        """
        Añade hints sutiles al texto para guiar F5-TTS
        Estrategias no invasivas que el modelo puede interpretar
        """
        strategies = {
            'falling': [
                text,  # Original
                text.replace('.', '...') if '.' in text else text,  # Puntos suspensivos para cadencia
                text + ' ' if not text.endswith(' ') else text,  # Espacio extra
            ],
            'rising': [
                text,  # Original
                text.replace('?', '?!') if '?' in text else text,  # Énfasis en pregunta
                text.replace('?', '??') if '?' in text else text,  # Doble interrogación
            ]
        }

        # Usar la primera estrategia válida
        options = strategies.get(hint_type, [text])
        return options[0]

    def _detect_sentence_type(self, text: str) -> str:
        """Detecta el tipo de frase basándose en puntuación"""
        text = text.strip()
        if text.endswith('?') or '¿' in text:
            return 'interrogative'
        elif text.endswith('!') or '¡' in text:
            return 'exclamative'
        elif text.endswith('...'):
            return 'suspensive'
        else:
            return 'declarative'

    def _is_paragraph_start(self, text: str, phrase_idx: int) -> bool:
        """Detecta si es inicio de párrafo"""
        # Primera frase siempre es inicio
        if phrase_idx == 0:
            return True
        # Detectar por formato (tabulación, espacios)
        if text.strip().startswith(('\t', '    ', '•', '-', '1.', '2.')):
            return True
        # Detectar por mayúscula después de punto y aparte
        if re.match(r'^[A-ZÁÉÍÓÚÑ]', text.strip()):
            return phrase_idx % 10 == 0  # Aproximación: cada 10 frases nuevo párrafo
        return False

    def _is_paragraph_end(self, text: str, phrase_idx: int, total_phrases: int) -> bool:
        """Detecta si es final de párrafo"""
        # Última frase siempre es final
        if phrase_idx >= total_phrases - 1:
            return True
        # Detectar por puntuación fuerte y longitud
        if text.strip().endswith(('.', '!', '?')) and len(text) > 100:
            return True
        # Aproximación por posición
        return (phrase_idx + 1) % 10 == 0

    def _estimate_paragraph_id(self, phrase_idx: int, total_phrases: int) -> int:
        """Estima el párrafo actual basándose en la posición"""
        if total_phrases <= 3:
            return phrase_idx

        # División en tercios para arquitectura de 3 párrafos
        third = total_phrases // 3
        if phrase_idx < third:
            return 0  # Primer párrafo
        elif phrase_idx < 2 * third:
            return 1  # Segundo párrafo
        else:
            return 2  # Tercer párrafo

    def _is_fibonacci_position(self, phrase_idx: int, total_phrases: int) -> bool:
        """Verifica si la posición corresponde a la secuencia Fibonacci"""
        # Normalizar a escala de 21 (máximo Fibonacci en nuestra lista)
        if total_phrases <= 21:
            return phrase_idx in self.fibonacci_positions
        else:
            # Escalar proporcionalmente
            scaled_idx = int((phrase_idx / total_phrases) * 21)
            return scaled_idx in self.fibonacci_positions

    def inicializar_orquestador_maestro(self, texto_completo: str, f0_base: float = 185.0):
        """
        Inicializa el orquestador maestro con el texto completo
        Debe llamarse ANTES de procesar frases individuales
        """
        if not self.usar_orquestador_maestro:
            return

        try:
            if getattr(self, 'ArquitecturaVocalMaestra', None) is None:
                self.ArquitecturaVocalMaestra = _import_orquestador_maestro()
            if self.ArquitecturaVocalMaestra is None:
                raise ImportError("ArquitecturaVocalMaestra no disponible")

            self.texto_completo = texto_completo
            self.orquestador = self.ArquitecturaVocalMaestra(f0_base=f0_base)

            # Generar matriz de control completa
            self.control_matrix = self.orquestador.orquestar_lectura_completa(texto_completo)

            logger.info(f"🎭 Orquestador Maestro inicializado: {len(self.control_matrix)} frases planificadas")

        except Exception as e:
            logger.error(f"❌ Error inicializando Orquestador Maestro: {e}")
            self.usar_orquestador_maestro = False

    def obtener_parametros_maestros(self, phrase_idx: int) -> Optional[Dict]:
        """
        Obtiene los parámetros del orquestador maestro para una frase específica
        """
        if not self.usar_orquestador_maestro or not self.control_matrix:
            return None

        if 0 <= phrase_idx < len(self.control_matrix):
            params_maestro = self.control_matrix[phrase_idx]

            # Convertir a formato compatible con el sistema actual
            return {
                'apply_modifications': True,
                'text': params_maestro.texto,
                'pitch_factor': params_maestro.tono_base / 185.0,  # Factor relativo
                'speed': params_maestro.velocidad,
                'extra_params': {
                    'nfe_adjustment': max(0, int(params_maestro.tono_base / 185.0 * 4 - 4)),
                    'sway_adjustment': -0.05 if params_maestro.curva == 'cadencia' else 0.0,
                    'cfg_adjustment': 0.1 if params_maestro.intensidad > 1.1 else 0.0,
                    'energy': params_maestro.intensidad,
                    'pause_after': params_maestro.pausa_final,
                    'contour': params_maestro.curva
                },
                'maestro_source': True,
                'parrafo_id': params_maestro.parrafo_id,
                'funcion_narrativa': self._obtener_funcion_narrativa(params_maestro),
                'enfasis_palabras': params_maestro.enfasis_palabras
            }

        return None

    def _obtener_funcion_narrativa(self, params_maestro) -> str:
        """Determina la función narrativa basada en los parámetros del maestro"""
        if params_maestro.curva == 'ataque':
            return 'apertura'
        elif params_maestro.curva == 'cadencia':
            return 'cierre'
        elif params_maestro.intensidad > 1.2:
            return 'pivote'
        else:
            return 'desarrollo'


# ============================================
# PARTE 2: ANÁLISIS Y CORRECCIÓN (EXHAUSTIVO)
# ============================================

class ProsodyAnalyzer:
    """
    Análisis exhaustivo del audio por ventanas de 250ms
    Basado en investigación de prosodia y cadencias naturales
    """

    def __init__(self, window_size_ms: int = 250, sample_rate: int = 44100):
        self.window_size_ms = window_size_ms
        self.sample_rate = sample_rate
        self.window_samples = int(sample_rate * window_size_ms / 1000)

    def analyze_complete_audio(self,
                              audio_segments: List[np.ndarray],
                              texts: List[str]) -> List[Dict]:
        """
        Analiza todos los segmentos divididos en ventanas
        Evalúa cumplimiento del Arco Prosódico
        """
        analysis_map = []

        for i, (audio, text) in enumerate(zip(audio_segments, texts)):
            # Dividir en ventanas de 250ms con 50% overlap
            windows = self._split_into_windows(audio)

            segment_analysis = {
                'segment_id': i,
                'text': text,
                'text_length': len(text),
                'windows': [],
                'is_paragraph_end': self._is_paragraph_end(text),
                'is_question': '?' in text,
                'is_exclamation': '!' in text,
                'sentence_type': self._detect_sentence_type(text)
            }

            # Analizar cada ventana
            for w_idx, window in enumerate(windows):
                position = w_idx / max(len(windows) - 1, 1)  # 0.0 a 1.0

                window_data = {
                    'window_id': w_idx,
                    'position': position,
                    'position_type': self._classify_position(position),
                    'pitch_mean': self._extract_pitch(window),
                    'energy': np.sqrt(np.mean(window**2)),
                    'spectral_centroid': self._extract_spectral_centroid(window)
                }
                segment_analysis['windows'].append(window_data)

            # Calcular métricas del Arco Prosódico
            if segment_analysis['windows']:
                all_pitches = [w['pitch_mean'] for w in segment_analysis['windows'] if w['pitch_mean'] > 0]
                if all_pitches:
                    # Inicio, medio y final según Arco Prosódico
                    segment_analysis['pitch_start'] = np.mean(all_pitches[:max(2, len(all_pitches)//5)])
                    segment_analysis['pitch_middle'] = np.mean(all_pitches[len(all_pitches)//3:2*len(all_pitches)//3])
                    segment_analysis['pitch_end'] = np.mean(all_pitches[-max(2, len(all_pitches)//5):])

                    # Calcular pendiente del arco
                    segment_analysis['arc_slope'] = (segment_analysis['pitch_end'] - segment_analysis['pitch_start']) / segment_analysis['pitch_start']

            analysis_map.append(segment_analysis)

        return analysis_map

    def _split_into_windows(self, audio: np.ndarray) -> List[np.ndarray]:
        """Divide audio en ventanas con 50% overlap"""
        windows = []
        hop = self.window_samples // 2  # 50% overlap

        for i in range(0, len(audio) - self.window_samples, hop):
            windows.append(audio[i:i + self.window_samples])

        return windows

    def _extract_pitch(self, window: np.ndarray) -> float:
        """Extrae pitch fundamental usando librosa piptrack"""
        try:
            # Asegurar que el audio sea float
            window_float = window.astype(float)

            # Usar piptrack para extraer pitch
            pitches, magnitudes = librosa.piptrack(
                y=window_float,
                sr=self.sample_rate,
                fmin=50,   # Mínimo para voz humana
                fmax=500,  # Máximo para voz hablada
                threshold=0.1
            )

            # Obtener el pitch con mayor magnitud en cada frame
            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)

            return float(np.mean(pitch_values)) if pitch_values else 0.0

        except Exception as e:
            logger.warning(f"Error extrayendo pitch: {e}")
            return 0.0

    def _extract_spectral_centroid(self, window: np.ndarray) -> float:
        """Extrae centroide espectral (brillantez)"""
        try:
            centroid = librosa.feature.spectral_centroid(
                y=window.astype(float),
                sr=self.sample_rate
            )
            return float(np.mean(centroid))
        except:
            return 0.0

    def _classify_position(self, position: float) -> str:
        """Clasifica posición según el Arco Prosódico"""
        if position < 0.15:
            return 'attack'  # Inicio (captar atención)
        elif position < 0.7:
            return 'sustain'  # Desarrollo
        elif position < 0.85:
            return 'decay'   # Pre-cadencia
        else:
            return 'release'  # Cadencia final

    def _is_paragraph_end(self, text: str) -> bool:
        """Detecta final de párrafo por puntuación"""
        return bool(re.search(r'[.!?]\s*$', text.strip()))

    def _detect_sentence_type(self, text: str) -> str:
        """Clasifica tipo de oración"""
        text = text.strip()
        if '?' in text or text.endswith('?'):
            return 'interrogative'
        elif '!' in text or text.endswith('!'):
            return 'exclamative'
        elif text.endswith('...'):
            return 'suspensive'
        else:
            return 'declarative'


class ProsodyProblemDetector:
    """
    Detecta problemas específicos en la prosodia según reglas documentadas
    Evalúa cumplimiento del Arco Prosódico y la Regla del 3-5-8

    VERSIÓN 2.0: Detecta patrones prosódicos específicos más sutiles
    """

    def __init__(self):
        self.rules = {
            # Basado en Arco Prosódico (Pierrehumbert, 1980)
            'paragraph_end_drop': -0.08,      # Caída del 8% al final
            'question_rise': 0.15,            # Subida 15-20% en preguntas
            'transition_max_jump': 0.25,      # Máximo salto entre frases
            'arc_slope_ideal': -0.05,         # Pendiente ideal del arco
            'start_energy_boost': 0.02,       # Boost inicial del 2%

            # NUEVO: Reglas específicas del texto ejemplo
            'micro_ascenso_esperado': 0.03,   # +3% en palabras clave
            'enfasis_especial': 0.08,         # +8% en palabras importantes
            'mantener_tension': -0.02,        # Máximo -2% de caída cuando debe mantenerse
            'descenso_final_fuerte': -0.12,   # -12% en finales definitivos
            'velocidad_variacion': 0.15,      # 15% variación de velocidad entre párrafos
        }

        # Umbrales de severidad REDUCIDOS para ser más agresivo
        self.severity_thresholds = {
            'critical': 0.3,   # Era 0.5, ahora más agresivo
            'moderate': 0.2,   # Era 0.3, ahora más agresivo
            'minor': 0.1       # Era 0.15, ahora más agresivo
        }

        # NUEVO: Palabras clave que requieren patrones específicos (del texto ejemplo)
        self.palabras_especiales = {
            'enfasis_alto': ['diferente', 'increíble', 'importante', 'fundamental', 'crucial'],
            'micro_ascenso': ['jazmín', 'sal marina', 'marina', 'olvidadas', 'amanecer', 'esperanza', 'doraron'],
            'mantener_grave': ['oscuridad', 'sombras', 'silencio', 'profundidad', 'niebla'],
            'finales_definitivos': ['definitivo', 'final', 'siempre', 'nunca', 'eternidad', 'silencio', 'vigilia']
        }

    def identify_problems(self, analysis_map: List[Dict]) -> List[Dict]:
        """
        Identifica problemas prosódicos y su severidad
        Prioriza según impacto en la naturalidad

        VERSIÓN 2.0: Detecta patrones prosódicos específicos más sutiles
        """
        problems = []

        for i, segment in enumerate(analysis_map):
            # Solo verificar ventanas finales para cadencias
            ending_windows = [w for w in segment['windows'] if w['position_type'] == 'release']

            if not ending_windows:
                continue

            last_window = ending_windows[-1]

            # Problema 1: Final de párrafo sin caída (crítico para naturalidad)
            if segment['is_paragraph_end'] and segment['sentence_type'] == 'declarative':
                if 'pitch_start' in segment and 'pitch_end' in segment:
                    expected_drop = segment['pitch_start'] * (1 + self.rules['paragraph_end_drop'])
                    actual = segment['pitch_end']

                    if actual > expected_drop and actual > 0:
                        severity = abs(actual - expected_drop) / max(expected_drop, 1)
                        problems.append({
                            'segment_id': i,
                            'window_id': last_window['window_id'],
                            'type': 'missing_paragraph_cadence',
                            'severity': severity,
                            'current_pitch': actual,
                            'expected_pitch': expected_drop,
                            'description': f"Falta cadencia descendente en final de párrafo"
                        })

            # Problema 2: Pregunta sin subida (crítico para comprensión)
            elif segment['is_question']:
                if 'pitch_middle' in segment and 'pitch_end' in segment:
                    expected_rise = segment['pitch_middle'] * (1 + self.rules['question_rise'])
                    actual = segment['pitch_end']

                    if actual < expected_rise and actual > 0:
                        severity = abs(expected_rise - actual) / max(expected_rise, 1)
                        problems.append({
                            'segment_id': i,
                            'window_id': last_window['window_id'],
                            'type': 'missing_question_rise',
                            'severity': severity,
                            'current_pitch': actual,
                            'expected_pitch': expected_rise,
                            'description': f"Falta subida tonal en pregunta"
                        })

            # NUEVO: Problema 3: Micro-ascensos faltantes en palabras clave
            texto_segment = segment.get('text', '').lower()
            for palabra in self.palabras_especiales['micro_ascenso']:
                if palabra in texto_segment:
                    # Buscar ventanas que contengan la palabra
                    for window in segment['windows']:
                        if palabra in window.get('text_snippet', '').lower():
                            pitch_actual = window.get('pitch_mean', 0)
                            pitch_esperado = pitch_actual * (1 + self.rules['micro_ascenso_esperado'])

                            if pitch_actual < pitch_esperado * 0.95:  # Tolerancia del 5%
                                severity = abs(pitch_esperado - pitch_actual) / max(pitch_esperado, 1)
                                problems.append({
                                    'segment_id': i,
                                    'window_id': window['window_id'],
                                    'type': 'missing_micro_ascenso',
                                    'severity': severity * 1.2,  # Más crítico
                                    'current_pitch': pitch_actual,
                                    'expected_pitch': pitch_esperado,
                                    'palabra_clave': palabra,
                                    'description': f"Falta micro-ascenso en '{palabra}'"
                                })

            # NUEVO: Problema 4: Énfasis especial insuficiente
            for palabra in self.palabras_especiales['enfasis_alto']:
                if palabra in texto_segment:
                    for window in segment['windows']:
                        if palabra in window.get('text_snippet', '').lower():
                            pitch_actual = window.get('pitch_mean', 0)
                            pitch_esperado = pitch_actual * (1 + self.rules['enfasis_especial'])

                            if pitch_actual < pitch_esperado * 0.9:  # Tolerancia del 10%
                                severity = abs(pitch_esperado - pitch_actual) / max(pitch_esperado, 1)
                                problems.append({
                                    'segment_id': i,
                                    'window_id': window['window_id'],
                                    'type': 'insufficient_emphasis',
                                    'severity': severity * 1.5,  # Muy crítico
                                    'current_pitch': pitch_actual,
                                    'expected_pitch': pitch_esperado,
                                    'palabra_clave': palabra,
                                    'description': f"Énfasis insuficiente en '{palabra}'"
                                })

            # NUEVO: Problema 5: Finales definitivos sin descenso fuerte
            for palabra in self.palabras_especiales['finales_definitivos']:
                if palabra in texto_segment and segment.get('is_paragraph_end', False):
                    if 'pitch_start' in segment and 'pitch_end' in segment:
                        expected_drop = segment['pitch_start'] * (1 + self.rules['descenso_final_fuerte'])
                        actual = segment['pitch_end']

                        if actual > expected_drop * 1.1:  # Tolerancia del 10%
                            severity = abs(actual - expected_drop) / max(expected_drop, 1)
                            problems.append({
                                'segment_id': i,
                                'type': 'missing_definitive_ending',
                                'severity': severity * 1.3,  # Muy crítico
                                'current_pitch': actual,
                                'expected_pitch': expected_drop,
                                'palabra_clave': palabra,
                                'description': f"Final definitivo sin descenso fuerte en '{palabra}'"
                            })

            # Problema 6: Arco prosódico invertido (antinatural)
            if 'arc_slope' in segment:
                if segment['arc_slope'] > 0.1:  # Subida en lugar de bajada
                    severity = min(abs(segment['arc_slope'] - self.rules['arc_slope_ideal']), 1.0)
                    problems.append({
                        'segment_id': i,
                        'type': 'inverted_prosodic_arc',
                        'severity': severity * 0.8,  # Menos crítico que cadencias
                        'current_slope': segment['arc_slope'],
                        'expected_slope': self.rules['arc_slope_ideal'],
                        'description': f"Arco prosódico invertido (sube en vez de bajar)"
                    })

            # NUEVO: Problema 4: Palabras clave sin énfasis especial
            text_lower = segment['text'].lower()
            for categoria, palabras in self.palabras_especiales.items():
                for palabra in palabras:
                    if palabra in text_lower:
                        # Verificar si la palabra tiene el énfasis adecuado
                        problema_enfasis = self._verificar_enfasis_palabra(segment, palabra, categoria)
                        if problema_enfasis:
                            problems.append(problema_enfasis)

            # NUEVO: Problema 5: Falta de variación de velocidad entre párrafos
            if i > 0:  # No para el primer segmento
                problema_velocidad = self._verificar_variacion_velocidad(analysis_map, i)
                if problema_velocidad:
                    problems.append(problema_velocidad)

            # NUEVO: Problema 6: Finales definitivos sin descenso fuerte
            if self._es_final_definitivo(segment):
                problema_final = self._verificar_final_definitivo(segment, i)
                if problema_final:
                    problems.append(problema_final)

        # Ordenar por severidad (más severos primero)
        return sorted(problems, key=lambda x: x['severity'], reverse=True)

    def _verificar_enfasis_palabra(self, segment: Dict, palabra: str, categoria: str) -> Optional[Dict]:
        """Verifica si una palabra clave tiene el énfasis prosódico adecuado"""
        if 'pitch_mean' not in segment or segment['pitch_mean'] <= 0:
            return None

        expected_boost = {
            'enfasis_alto': self.rules['enfasis_especial'],
            'micro_ascenso': self.rules['micro_ascenso_esperado'],
            'mantener_grave': -self.rules['mantener_tension'],
            'finales_definitivos': self.rules['descenso_final_fuerte']
        }.get(categoria, 0)

        # Calcular si el énfasis actual es suficiente
        # (Simplificado - en implementación real sería más complejo)
        pitch_variation = segment.get('pitch_end', segment['pitch_mean']) - segment.get('pitch_start', segment['pitch_mean'])
        expected_variation = segment['pitch_mean'] * expected_boost

        if abs(pitch_variation - expected_variation) > abs(expected_variation * 0.5):
            severity = abs(pitch_variation - expected_variation) / max(abs(expected_variation), 1)
            return {
                'segment_id': segment.get('segment_id', 0),
                'type': f'missing_emphasis_{categoria}',
                'severity': min(severity, 1.0),
                'palabra': palabra,
                'current_variation': pitch_variation,
                'expected_variation': expected_variation,
                'description': f"Palabra '{palabra}' necesita énfasis {categoria}"
            }

        return None

    def _verificar_variacion_velocidad(self, analysis_map: List[Dict], current_index: int) -> Optional[Dict]:
        """Verifica si hay suficiente variación de velocidad entre párrafos"""
        # Implementación simplificada - en real sería más sofisticada
        return None  # Por ahora deshabilitado

    def _es_final_definitivo(self, segment: Dict) -> bool:
        """Determina si un segmento es un final definitivo que necesita descenso fuerte"""
        text = segment.get('text', '').lower()

        # Indicadores de final definitivo
        finales_definitivos = ['final', 'siempre', 'nunca', 'definitivo', 'eternidad', 'para siempre']
        if any(palabra in text for palabra in finales_definitivos):
            return True

        # Final de documento con punto
        if segment.get('is_paragraph_end', False) and text.endswith('.'):
            return True

        return False

    def _verificar_final_definitivo(self, segment: Dict, segment_id: int) -> Optional[Dict]:
        """Verifica si un final definitivo tiene el descenso fuerte requerido"""
        if 'pitch_start' not in segment or 'pitch_end' not in segment:
            return None

        expected_drop = segment['pitch_start'] * (1 + self.rules['descenso_final_fuerte'])
        actual = segment['pitch_end']

        if actual > expected_drop and actual > 0:
            severity = abs(actual - expected_drop) / max(abs(expected_drop), 1)
            return {
                'segment_id': segment_id,
                'type': 'missing_definitive_ending',
                'severity': min(severity, 1.0),
                'current_pitch': actual,
                'expected_pitch': expected_drop,
                'description': f"Final definitivo necesita descenso más fuerte"
            }

        return None


class SelectiveRegenerator:
    """
    Regenera SOLO segmentos con problemas severos
    VERSIÓN 2.0: Más agresivo y específico para patrones prosódicos

    Máximo 8 regeneraciones con estrategias más específicas
    """

    def __init__(self, f5_generator, max_attempts: int = 25, max_fixes: int = 8):
        self.generator = f5_generator
        self.max_attempts = max_attempts
        self.max_fixes = max_fixes  # Aumentado de 5 a 8 para ser más agresivo
        self.hint_generator = ProsodyHintGenerator()

        # Contexto de referencia para F5-TTS
        self.reference_file = None
        self.reference_text = ""

    def set_reference_context(self, ref_file: str, ref_text: str = ""):
        """Configura el contexto de referencia para regeneraciones"""
        self.reference_file = ref_file
        self.reference_text = ref_text

    def fix_critical_problems(self,
                              problems: List[Dict],
                              audio_segments: List[np.ndarray],
                              texts: List[str],
                              severity_threshold: float = 0.3) -> Tuple[List[np.ndarray], Dict]:
        """
        Corrige solo problemas con severity > threshold
        Limitado a max_fixes para mantener velocidad

        Returns:
            Tuple de (audio_segments corregidos, reporte de fixes)
        """
        fixed_segments = audio_segments.copy()
        fix_report = {
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'fixes': []
        }

        # Filtrar y limitar problemas a corregir
        critical_problems = [p for p in problems if p['severity'] > severity_threshold][:self.max_fixes]

        if not critical_problems:
            logger.info("✅ No se encontraron problemas críticos")
            return fixed_segments, fix_report

        logger.info(f"🔧 Corrigiendo {len(critical_problems)} problemas críticos...")

        for problem in critical_problems:
            seg_id = problem['segment_id']
            fix_report['attempted'] += 1

            logger.info(f"  🎯 Segmento {seg_id}: {problem['type']} (severidad: {problem['severity']:.2f})")

            # Preparar hints específicos para el tipo de problema
            hints = self._prepare_correction_hints(problem, texts[seg_id])

            # Intentar regenerar con estrategias progresivas
            best_candidate = None
            best_score = 0

            # LÍMITE ESTRICTO para evitar bucles infinitos
            max_safe_attempts = min(self.max_attempts, 5)  # Máximo 5 intentos por problema
            consecutive_failures = 0

            for attempt in range(max_safe_attempts):
                try:
                    # Ajustar parámetros F5-TTS según el intento
                    generation_params = self._adjust_generation_params(problem, attempt)

                    # Validar parámetros antes de usar
                    if not self._validate_generation_params(generation_params):
                        logger.warning(f"    ⚠️ Parámetros inválidos en intento {attempt + 1}, usando valores por defecto")
                        generation_params = {
                            'nfe_step': 32,
                            'sway_sampling_coef': -0.5,
                            'cfg_strength': 2.0,
                            'speed': 1.0
                        }

                    # Generar con hints y parámetros ajustados
                    new_audio = self._generate_with_params(
                        hints['text'],
                        generation_params
                    )

                    # Si el audio está vacío, es un fallo
                    if len(new_audio) == 0:
                        consecutive_failures += 1
                        logger.warning(f"    ⚠️ Audio vacío en intento {attempt + 1}")

                        # Si fallan 3 consecutivos, abandonar
                        if consecutive_failures >= 3:
                            logger.warning(f"    ❌ Abandonando después de {consecutive_failures} fallos consecutivos")
                            break
                        continue

                    # Reset contador de fallos si se genera audio
                    consecutive_failures = 0

                    # Evaluar si mejora el problema
                    score = self._evaluate_fix(new_audio, problem)

                    if score > best_score:
                        best_score = score
                        best_candidate = new_audio

                    # Si es suficientemente bueno, parar
                    if score > 0.8:
                        logger.info(f"    ✅ Corregido en intento {attempt + 1} (score: {score:.2f})")
                        break

                except Exception as e:
                    consecutive_failures += 1
                    logger.warning(f"    ⚠️ Error en intento {attempt + 1}: {e}")

                    # Si es el error específico de F5-TTS, TERMINAR INMEDIATAMENTE
                    if "must be strictly increasing" in str(e):
                        logger.error(f"    🚨 ERROR CRÍTICO F5-TTS DETECTADO: {e}")
                        logger.error(f"    💀 Texto problemático: {hints['text']}")
                        logger.error(f"    🛑 TERMINANDO EJECUCIÓN PARA EVITAR BUCLE INFINITO")

                        # Guardar información del error
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        error_info = f"""
TERMINATION LOG - {timestamp}
==============================
Error: {e}
Texto: {hints['text']}
Contexto: prosody_enhancement.py - _try_fix_segment_problem
Intento: {attempt + 1}
==============================
"""

                        try:
                            with open("/home/lorty/m2/ROYERBIN/Spanish-F5/generador_estructura_v3_previo/error_critico.log", "a") as f:
                                f.write(error_info)
                        except:
                            pass

                        # Terminar inmediatamente
                        import sys
                        sys.exit(1)

                    # Si fallan 3 consecutivos, abandonar
                    if consecutive_failures >= 3:
                        logger.warning(f"    ❌ Abandonando después de {consecutive_failures} errores consecutivos")
                        break

                    continue

            # Aplicar mejor candidato si mejora significativamente
            if best_candidate is not None and best_score > 0.5:
                fixed_segments[seg_id] = best_candidate
                fix_report['successful'] += 1
                fix_report['fixes'].append({
                    'segment_id': seg_id,
                    'problem_type': problem['type'],
                    'improvement_score': best_score
                })
                logger.info(f"    ✅ Aplicado fix con score {best_score:.2f}")
            else:
                fix_report['failed'] += 1
                logger.warning(f"    ❌ No se pudo mejorar suficientemente")

        return fixed_segments, fix_report

    def _prepare_correction_hints(self, problem: Dict, text: str) -> Dict:
        """Prepara hints específicos para cada tipo de problema"""

        hints = {'text': text, 'modifications': []}

        if problem['type'] == 'missing_paragraph_cadence':
            # Forzar cadencia descendente
            hints['text'] = text.replace('.', '...')  # Alargar final
            if not text.endswith('...'):
                hints['text'] = hints['text'].rstrip('.') + '...'
            hints['modifications'].append('extended_ending')

        elif problem['type'] == 'missing_question_rise':
            # Forzar subida en pregunta
            hints['text'] = text.replace('?', '?!')  # Añadir énfasis
            if not '¿' in text:
                hints['text'] = '¿' + hints['text']  # Asegurar apertura
            hints['modifications'].append('emphasized_question')

        elif problem['type'] == 'missing_micro_ascenso':
            # Micro-ascenso en palabra clave
            palabra = problem.get('palabra_clave', '')
            if palabra:
                # Enfatizar la palabra específica con marcas de énfasis
                hints['text'] = text.replace(palabra, f'*{palabra}*')
                hints['modifications'].append(f'micro_ascenso_{palabra}')
                # Parámetros específicos para micro-ascenso
                hints['pitch_adjustment'] = '+3%'
                hints['target_word'] = palabra

        elif problem['type'] == 'insufficient_emphasis':
            # Énfasis especial insuficiente
            palabra = problem.get('palabra_clave', '')
            if palabra:
                # Enfatizar fuertemente la palabra
                hints['text'] = text.replace(palabra, f'**{palabra}**')
                hints['modifications'].append(f'enfasis_especial_{palabra}')
                # Parámetros específicos para énfasis especial
                hints['pitch_adjustment'] = '+8%'
                hints['energy_boost'] = '+15%'
                hints['target_word'] = palabra

        elif problem['type'] == 'missing_definitive_ending':
            # Final definitivo sin descenso fuerte
            palabra = problem.get('palabra_clave', '')
            # Forzar descenso definitivo muy marcado
            hints['text'] = text.rstrip('.!') + '...'
            if palabra:
                hints['text'] = hints['text'].replace(palabra, f'{palabra}...')
            hints['modifications'].append('descenso_definitivo')
            hints['pitch_adjustment'] = '-12%'
            hints['final_drop'] = 'strong'

        elif problem['type'] == 'inverted_prosodic_arc':
            # Intentar normalizar el arco
            # Dividir en partes y ajustar puntuación
            parts = text.split(',')
            if len(parts) > 1:
                # Añadir pausas intermedias
                hints['text'] = ', '.join(parts[:-1]) + '... ' + parts[-1]
            hints['modifications'].append('arc_normalization')

        return hints

    def _adjust_generation_params(self, problem: Dict, attempt: int) -> Dict:
        """
        Ajusta parámetros F5-TTS progresivamente según el intento
        VERSIÓN 2.0: Parámetros más específicos y agresivos
        """

        base_params = {
            'nfe_step': 40,  # Aumentado de 32 para más control
            'sway_sampling_coef': -0.5,
            'cfg_strength': 2.2,  # Aumentado para más adherencia
            'speed': 1.0
        }

        # Ajustes específicos por tipo de problema
        if problem['type'] == 'missing_paragraph_cadence':
            # Parámetros AGRESIVOS para cadencias descendentes
            base_params['nfe_step'] = 48 + (attempt * 3)  # Mucho más control
            base_params['sway_sampling_coef'] = -0.7 - (attempt * 0.08)  # Muy negativo
            base_params['cfg_strength'] = 2.5 + (attempt * 0.15)  # Mayor adherencia
            base_params['speed'] = 0.88 - (attempt * 0.03)  # Ralentizar más

        elif problem['type'] == 'missing_question_rise':
            # Parámetros AGRESIVOS para subidas tonales
            base_params['nfe_step'] = 44 + (attempt * 2)
            base_params['cfg_strength'] = 2.8 + (attempt * 0.2)  # Muy alta adherencia
            base_params['sway_sampling_coef'] = -0.3 - (attempt * 0.06)
            base_params['speed'] = 1.05 + (attempt * 0.02)  # Acelerar ligeramente

        elif problem['type'] == 'inverted_prosodic_arc':
            # Parámetros para corregir arcos invertidos
            base_params['nfe_step'] = 36 + (attempt * 5)
            base_params['sway_sampling_coef'] = -0.8 + (attempt * 0.03)
            base_params['cfg_strength'] = 2.3 + (attempt * 0.1)

        # NUEVO: Parámetros para nuevos tipos de problemas
        elif problem['type'] == 'missing_micro_ascenso':
            # Parámetros específicos para micro-ascensos
            base_params['nfe_step'] = 44 + (attempt * 2)
            base_params['cfg_strength'] = 2.4 + (attempt * 0.1)
            base_params['sway_sampling_coef'] = -0.35 - (attempt * 0.04)
            base_params['speed'] = 1.02 + (attempt * 0.01)  # Ligeramente más rápido

        elif problem['type'] == 'insufficient_emphasis':
            # Parámetros AGRESIVOS para énfasis especial
            base_params['nfe_step'] = 46 + (attempt * 3)
            base_params['cfg_strength'] = 2.7 + (attempt * 0.15)  # Mayor adherencia
            base_params['sway_sampling_coef'] = -0.45 - (attempt * 0.06)
            base_params['speed'] = 0.95 - (attempt * 0.02)  # Más lento para énfasis

        elif problem['type'] == 'missing_definitive_ending':
            # Parámetros EXTREMOS para finales definitivos
            base_params['nfe_step'] = 52 + (attempt * 4)  # Máximo control
            base_params['sway_sampling_coef'] = -0.9 - (attempt * 0.1)  # Extremadamente negativo
            base_params['cfg_strength'] = 3.0 + (attempt * 0.2)  # Máxima adherencia
            base_params['speed'] = 0.82 - (attempt * 0.04)  # Muy lento para énfasis

        # LIMITAR valores extremos para evitar el error "t must be strictly increasing" (MÁS CONSERVADOR)
        base_params['nfe_step'] = max(16, min(base_params['nfe_step'], 32))  # Entre 16-32 (era 8-48)
        base_params['sway_sampling_coef'] = max(-0.4, min(base_params['sway_sampling_coef'], 0.4))  # Entre -0.4 y 0.4 (era -0.9 a 0.5)
        base_params['cfg_strength'] = max(1.0, min(base_params['cfg_strength'], 2.2))  # Entre 1.0-2.2 (era 1.0-3.0)
        base_params['speed'] = max(0.85, min(base_params['speed'], 1.15))  # Entre 0.85-1.15 (era 0.8-1.2)

        return base_params

    def _validate_generation_params(self, params: Dict) -> bool:
        """
        Valida que los parámetros estén en rangos seguros para F5-TTS
        """
        try:
            # Validar nfe_step
            nfe_step = params.get('nfe_step', 32)
            if not isinstance(nfe_step, (int, float)) or nfe_step < 4 or nfe_step > 100:
                logger.warning(f"nfe_step inválido: {nfe_step}")
                return False

            # Validar sway_sampling_coef
            sway = params.get('sway_sampling_coef', -0.5)
            if not isinstance(sway, (int, float)) or sway < -2.0 or sway > 2.0:
                logger.warning(f"sway_sampling_coef inválido: {sway}")
                return False

            # Validar cfg_strength
            cfg = params.get('cfg_strength', 2.0)
            if not isinstance(cfg, (int, float)) or cfg < 0.5 or cfg > 10.0:
                logger.warning(f"cfg_strength inválido: {cfg}")
                return False

            # Validar speed
            speed = params.get('speed', 1.0)
            if not isinstance(speed, (int, float)) or speed < 0.1 or speed > 3.0:
                logger.warning(f"speed inválido: {speed}")
                return False

            return True

        except Exception as e:
            logger.warning(f"Error validando parámetros: {e}")
            return False

    def _split_long_sentence(self, sentence: str) -> list:
        """
        Divide frases largas (>120 chars) para evitar errores de interpolación F5-TTS
        """
        import re

        if len(sentence) <= 120:
            return [sentence]

        # Dividir por puntos suspensivos seguidos de minúscula
        ellipsis_pattern = r'(\.\.\.)(\s+)([a-záéíóúüñ])'
        if re.search(ellipsis_pattern, sentence):
            parts = re.split(ellipsis_pattern, sentence)
            result = []
            current = ""
            for i, part in enumerate(parts):
                if part == '...':
                    current += part
                    if current.strip():
                        result.append(current.strip())
                    current = ""
                elif re.match(r'\s+', part):
                    continue  # Saltar espacios
                else:
                    current += part
            if current.strip():
                result.append(current.strip())

            # Recursivamente dividir partes largas
            final_result = []
            for part in result:
                if len(part) > 120:
                    final_result.extend(self._split_long_sentence(part))
                else:
                    final_result.append(part)
            return final_result

        # División por conectores
        connectors = [
            r',\s+(y|pero|cuando|donde|que|como si|mientras)',
            r',\s+(después|antes|luego|entonces|así que|por eso)',
        ]

        for pattern in connectors:
            matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
            if matches:
                # Buscar división cerca del centro
                target = len(sentence) // 2
                best_match = min(matches, key=lambda m: abs(m.start() - target))

                split_pos = best_match.start() + 1
                part1 = sentence[:split_pos].strip()
                part2 = sentence[split_pos:].strip()

                if len(part1) > 30 and len(part2) > 30:
                    result = []
                    for part in [part1, part2]:
                        if len(part) > 120:
                            result.extend(self._split_long_sentence(part))
                        else:
                            result.append(part)
                    return result

        # División por comas cerca del centro
        comma_positions = [m.start() for m in re.finditer(r',', sentence)]
        if comma_positions:
            target = len(sentence) // 2
            best_comma = min(comma_positions, key=lambda x: abs(x - target))

            part1 = sentence[:best_comma + 1].strip()
            part2 = sentence[best_comma + 1:].strip()

            if len(part1) > 30 and len(part2) > 30:
                return [part1, part2]

        # División por espacios como último recurso
        words = sentence.split()
        if len(words) > 6:
            mid = len(words) // 2
            part1 = ' '.join(words[:mid])
            part2 = ' '.join(words[mid:])
            return [part1, part2]

        return [sentence]

    def _generate_with_params(self, text: str, params: Dict) -> np.ndarray:
        """
        Genera audio con parámetros específicos usando el generador F5-TTS real
        """

        # NUEVO: Dividir texto largo antes de enviarlo a F5-TTS
        if len(text) > 120:
            logger.info(f"🔧 Dividiendo texto largo ({len(text)} chars) para evitar errores")
            sentences = self._split_long_sentence(text)

            if len(sentences) > 1:
                logger.info(f"📊 Texto dividido en {len(sentences)} partes:")
                for i, sentence in enumerate(sentences, 1):
                    logger.info(f"   {i}. [{len(sentence):3d} chars] {sentence[:60]}...")

                # Generar audio para cada parte y concatenar
                audio_parts = []
                for sentence in sentences:
                    part_audio = self._generate_with_params(sentence, params)
                    if len(part_audio) > 0:
                        audio_parts.append(part_audio)

                if audio_parts:
                    return np.concatenate(audio_parts)
                else:
                    return np.array([])

        if self.generator is None:
            logger.error("Error: No hay generador F5-TTS disponible para regeneración")
            # Retornar array vacío en lugar de ruido aleatorio
            return np.array([])

        try:
            # Usar el generador F5-TTS real con los parámetros especificados
            if self.reference_file:
                wav, sr, _ = self.generator.infer(
                    ref_file=self.reference_file,
                    ref_text=self.reference_text,
                    gen_text=text,
                    nfe_step=params.get('nfe_step', 32),
                    sway_sampling_coef=params.get('sway_sampling_coef', -0.5),
                    cfg_strength=params.get('cfg_strength', 2.0),
                    speed=params.get('speed', 1.0),
                    remove_silence=False,
                    seed=-1
                )
            else:
                # Fallback sin referencia específica
                wav, sr, _ = self.generator.infer(
                    gen_text=text,
                    nfe_step=params.get('nfe_step', 32),
                    sway_sampling_coef=params.get('sway_sampling_coef', -0.5),
                    cfg_strength=params.get('cfg_strength', 2.0),
                    speed=params.get('speed', 1.0),
                    remove_silence=False,
                    seed=-1
                )

            if wav is not None and len(wav) > 0:
                # Normalizar para evitar clipping
                if np.max(np.abs(wav)) > 0:
                    wav = wav / np.max(np.abs(wav)) * 0.9
                return wav
            else:
                logger.warning("F5-TTS retornó audio vacío")
                return np.array([])

        except Exception as e:
            logger.error(f"Error en generación F5-TTS: {e}")
            return np.array([])

    def _evaluate_fix(self, audio: np.ndarray, problem: Dict) -> float:
        """
        Evalúa si el audio corrige el problema
        Score de 0 a 1 (1 = perfectamente corregido)
        """

        analyzer = ProsodyAnalyzer()

        # Analizar el segmento corregido
        if problem['type'] in ['missing_paragraph_cadence', 'missing_question_rise']:
            # Analizar el final del audio
            last_quarter = audio[-len(audio)//4:]
            pitch = analyzer._extract_pitch(last_quarter)

            if pitch <= 0:
                return 0.0

            # Calcular proximidad al objetivo
            target = problem['expected_pitch']
            current = problem['current_pitch']

            # Score basado en mejora relativa
            improvement = abs(pitch - target) / abs(current - target)
            score = max(0, 1 - improvement)

        elif problem['type'] == 'inverted_prosodic_arc':
            # Analizar el arco completo
            windows = analyzer._split_into_windows(audio)
            pitches = [analyzer._extract_pitch(w) for w in windows]
            valid_pitches = [p for p in pitches if p > 0]

            if len(valid_pitches) < 3:
                return 0.0

            # Calcular nueva pendiente
            new_slope = (valid_pitches[-1] - valid_pitches[0]) / valid_pitches[0]
            target_slope = problem['expected_slope']

            # Score basado en cercanía a pendiente ideal
            score = max(0, 1 - abs(new_slope - target_slope) / 0.2)

        else:
            score = 0.5  # Score neutral para problemas no definidos

        return min(max(score, 0.0), 1.0)


# ============================================
# ORQUESTADOR PRINCIPAL
# ============================================

class ProsodyOrchestrator:
    """
    Orquesta todo el proceso de mejora prosódica:
    1. Generación mejorada con hints (rápida)
    2. Post-procesamiento selectivo (opcional)

    Diseñado para integrarse con tu generador F5-TTS actual
    """

    def __init__(self, f5_generator=None):
        """
        Args:
            f5_generator: Tu instancia de F5TTS o generador compatible
        """
        self.generator = f5_generator
        self.hint_generator = ProsodyHintGenerator()
        self.analyzer = ProsodyAnalyzer()
        self.detector = ProsodyProblemDetector()
        self.regenerator = SelectiveRegenerator(f5_generator) if f5_generator else None

        # Estadísticas de procesamiento
        self.stats = {
            'total_processed': 0,
            'hints_applied': 0,
            'problems_detected': 0,
            'problems_fixed': 0,
            'processing_time': 0
        }

    def generate_with_prosody(self,
                             texts: List[str],
                             apply_postprocess: bool = True,
                             reference_audio: Optional[str] = None) -> Tuple[List[np.ndarray], Dict]:
        """
        Genera audio con mejoras prosódicas

        Args:
            texts: Lista de frases a generar
            apply_postprocess: Si aplicar post-procesamiento (Fase 2)
            reference_audio: Audio de referencia para clonación

        Returns:
            Tuple de (lista de audios generados, reporte de procesamiento)
        """

        start_time = time.time()

        print("🎵 FASE 1: Generación con hints prosódicos...")
        audio_segments = []

        # Detectar estructura de párrafos
        paragraph_boundaries = self._detect_paragraph_boundaries(texts)
        total_phrases = len(texts)

        for i, text in enumerate(texts):
            self.stats['total_processed'] += 1

            # Determinar párrafo actual
            paragraph_id = self._get_paragraph_id(i, paragraph_boundaries)

            # Generar hints SOLO para frases críticas
            if self._is_critical_position(i, texts):
                hints = self.hint_generator.prepare_text_for_generation(
                    text, i, total_phrases, paragraph_id
                )

                if hints['apply_modifications']:
                    self.stats['hints_applied'] += 1
                    logger.info(f"  📝 Frase {i+1}/{total_phrases}: Aplicando hints prosódicos")

                    # Generar con modificaciones
                    audio = self._generate_with_hints(hints, reference_audio)
                else:
                    # Generar normal
                    audio = self._generate_normal(text, reference_audio)
            else:
                # Generación normal para la mayoría de frases
                audio = self._generate_normal(text, reference_audio)

            audio_segments.append(audio)

            # Mostrar progreso
            if (i + 1) % 10 == 0:
                print(f"  Progreso: {i+1}/{total_phrases} frases")

        # Preparar reporte
        report = {
            'phase1_complete': True,
            'segments_generated': len(audio_segments),
            'hints_applied': self.stats['hints_applied'],
            'critical_positions': sum(1 for i in range(len(texts)) if self._is_critical_position(i, texts))
        }

        # FASE 2: Post-procesamiento (opcional)
        if apply_postprocess and self.regenerator:
            print("\n🔍 FASE 2: Análisis y corrección selectiva...")

            # Analizar prosodia
            analysis = self.analyzer.analyze_complete_audio(audio_segments, texts)
            problems = self.detector.identify_problems(analysis)

            self.stats['problems_detected'] = len(problems)
            report['problems_found'] = len(problems)
            report['critical_problems'] = len([p for p in problems if p['severity'] > 0.3])

            if problems and report['critical_problems'] > 0:
                print(f"  ⚠️ Encontrados {report['critical_problems']} problemas críticos")

                # Corregir solo los críticos
                audio_segments, fix_report = self.regenerator.fix_critical_problems(
                    problems, audio_segments, texts
                )

                self.stats['problems_fixed'] = fix_report['successful']
                report['phase2_complete'] = True
                report['segments_fixed'] = fix_report['successful']
                report['fix_details'] = fix_report
            else:
                print("  ✅ No se encontraron problemas críticos de prosodia")
                report['phase2_complete'] = True
                report['segments_fixed'] = 0

        # Tiempo total
        self.stats['processing_time'] = time.time() - start_time
        report['total_time'] = self.stats['processing_time']
        report['stats'] = self.stats.copy()

        print(f"\n✅ Procesamiento completado en {report['total_time']:.1f} segundos")

        return audio_segments, report

    def _is_critical_position(self, index: int, texts: List[str]) -> bool:
        """
        Identifica si es una posición crítica que necesita hints
        Solo ~20% de las frases son críticas para mantener velocidad
        """
        text = texts[index]
        total = len(texts)

        # Criterios para posición crítica:

        # 1. Primeras 2 frases (inicio, establecer tono)
        if index < 2:
            return True

        # 2. Últimas 2 frases (cierre, cadencia final)
        if index >= total - 2:
            return True

        # 3. Preguntas (necesitan subida tonal)
        if '?' in text:
            return True

        # 4. Exclamaciones (necesitan énfasis)
        if '!' in text:
            return True

        # 5. Posibles inicios de párrafo (cada ~10 frases)
        if index > 0 and index % 10 == 0:
            return True

        # 6. Posibles finales de párrafo (frases largas con punto)
        if len(text) > 150 and text.strip().endswith('.'):
            return True

        return False

    def _detect_paragraph_boundaries(self, texts: List[str]) -> List[int]:
        """Detecta dónde empiezan los párrafos en el texto"""
        boundaries = [0]

        for i, text in enumerate(texts[1:], 1):
            # Heurísticas para detectar nuevo párrafo

            # 1. Empieza con mayúscula después de punto final largo
            if i > 0 and texts[i-1].strip().endswith('.') and len(texts[i-1]) > 100:
                if re.match(r'^[A-ZÁÉÍÓÚÑ]', text.strip()):
                    boundaries.append(i)

            # 2. Formato especial (listas, títulos)
            elif text.strip().startswith(('•', '-', '1.', '2.', '3.')):
                boundaries.append(i)

            # 3. Salto grande en longitud (posible cambio de sección)
            elif i > 0:
                prev_len = len(texts[i-1])
                curr_len = len(text)
                if prev_len > 150 and curr_len < 50:  # Párrafo largo seguido de corto
                    boundaries.append(i)

        return sorted(list(set(boundaries)))

    def _get_paragraph_id(self, sentence_idx: int, boundaries: List[int]) -> int:
        """Determina a qué párrafo pertenece una frase"""
        for i in range(len(boundaries) - 1):
            if boundaries[i] <= sentence_idx < boundaries[i + 1]:
                return i
        return len(boundaries) - 1

    def _generate_with_hints(self, hints: Dict, reference_audio: Optional[str]) -> np.ndarray:
        """
        Genera audio con hints prosódicos aplicados
        ADAPTAR a tu generador F5-TTS específico
        """

        if self.generator:
            # Adaptar a tu implementación
            # Por ejemplo:
            # return self.generator.generate(
            #     text=hints['text'],
            #     speed=hints.get('speed', 1.0),
            #     pitch_factor=hints.get('pitch_factor', 1.0),
            #     **hints.get('extra_params', {})
            # )
            pass

        # Placeholder: genera audio dummy
        return self._generate_dummy_audio(hints['text'])

    def _generate_normal(self, text: str, reference_audio: Optional[str]) -> np.ndarray:
        """
        Generación normal sin modificaciones
        ADAPTAR a tu generador F5-TTS
        """

        if self.generator:
            # Adaptar a tu implementación
            # return self.generator.generate(text)
            pass

        # Placeholder: genera audio dummy
        return self._generate_dummy_audio(text)

    def _generate_dummy_audio(self, text: str) -> np.ndarray:
        """Genera audio dummy para testing (ELIMINAR en producción)"""
        duration = len(text) * 0.06  # ~60ms por carácter
        samples = int(duration * 44100)

        # Simular audio con algo de estructura
        t = np.linspace(0, duration, samples)
        frequency = 200 + np.random.randn() * 50  # Frecuencia base variable
        audio = np.sin(2 * np.pi * frequency * t) * 0.3
        audio *= np.exp(-t / duration)  # Envelope descendente

        return audio


# ============================================
# UTILIDADES Y HELPERS
# ============================================

def smart_concatenate(segments: List[np.ndarray], crossfade_ms: int = 50, sr: int = 44100) -> np.ndarray:
    """
    Concatena segmentos de audio con crossfade suave
    Preserva las pausas naturales entre frases
    """
    if not segments:
        return np.array([])

    if len(segments) == 1:
        return segments[0]

    result = segments[0]
    crossfade_samples = int(crossfade_ms * sr / 1000)

    for next_seg in segments[1:]:
        if len(result) > crossfade_samples and len(next_seg) > crossfade_samples:
            # Aplicar crossfade tipo coseno (más natural)
            t = np.linspace(0, np.pi/2, crossfade_samples)
            fade_out = np.cos(t)
            fade_in = np.sin(t)

            # Aplicar fades
            result[-crossfade_samples:] *= fade_out
            overlap = result[-crossfade_samples:] + next_seg[:crossfade_samples] * fade_in

            # Concatenar
            result = np.concatenate([
                result[:-crossfade_samples],
                overlap,
                next_seg[crossfade_samples:]
            ])
        else:
            # Sin crossfade si los segmentos son muy cortos
            result = np.concatenate([result, next_seg])

    return result


def export_prosody_report(report: Dict, output_path: str):
    """Exporta reporte de procesamiento prosódico"""

    import json
    from datetime import datetime

    report['timestamp'] = datetime.now().isoformat()
    report['version'] = '1.0.0'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"📊 Reporte exportado a: {output_path}")


# ============================================
# FUNCIÓN PRINCIPAL DE INTEGRACIÓN
# ============================================

def enhance_f5_tts_generation(
    texts: List[str],
    f5_generator,
    reference_audio: Optional[str] = None,
    apply_postprocess: bool = True,
    save_report: bool = True
) -> Tuple[List[np.ndarray], np.ndarray]:
    """
    Función principal para mejorar generación F5-TTS con prosodia

    Args:
        texts: Lista de frases a generar
        f5_generator: Tu instancia de F5TTS
        reference_audio: Path al audio de referencia
        apply_postprocess: Si aplicar corrección exhaustiva (Fase 2)
        save_report: Si guardar reporte de procesamiento

    Returns:
        Tuple de (segmentos individuales, audio concatenado final)
    """

    # Crear orquestador
    orchestrator = ProsodyOrchestrator(f5_generator)

    # Generar con mejoras prosódicas
    audio_segments, report = orchestrator.generate_with_prosody(
        texts,
        apply_postprocess=apply_postprocess,
        reference_audio=reference_audio
    )

    # Concatenar inteligentemente
    final_audio = smart_concatenate(audio_segments)

    # Guardar reporte si se solicita
    if save_report:
        export_prosody_report(report, 'prosody_enhancement_report.json')

    # Mostrar resumen
    print("\n" + "="*50)
    print("📊 RESUMEN DE MEJORA PROSÓDICA")
    print("="*50)
    print(f"✅ Frases procesadas: {report['segments_generated']}")
    print(f"📝 Hints aplicados: {report['hints_applied']}")

    if 'problems_found' in report:
        print(f"🔍 Problemas detectados: {report['problems_found']}")
        print(f"🔧 Problemas corregidos: {report.get('segments_fixed', 0)}")

    print(f"⏱️ Tiempo total: {report['total_time']:.1f} segundos")
    print(f"⚡ Promedio por frase: {report['total_time']/len(texts):.2f} segundos")

    return audio_segments, final_audio


if __name__ == "__main__":
    # Ejemplo de uso
    print("Sistema de Mejora Prosódica para F5-TTS")
    print("Basado en arquitectura vocal documentada")
    print("-" * 50)

    # Textos de ejemplo
    example_texts = [
        "El viento nocturno atravesaba los callejones de la ciudad antigua.",
        "Las piedras centenarias parecían susurrar historias olvidadas.",
        "¿Acaso no era esa la magia del lugar?",
        "Pero esa noche era diferente.",
        "Algo indefinible vibraba en el aire.",
        "Los gatos se agrupaban en los tejados como centinelas silenciosos.",
        "Al amanecer, cuando los primeros rayos doraron las cúpulas.",
        "La ciudad exhaló un suspiro colectivo.",
        "Todo se disolvió con la niebla matutina."
    ]

    # Simular generación
    orchestrator = ProsodyOrchestrator()
    segments, report = orchestrator.generate_with_prosody(
        example_texts,
        apply_postprocess=False  # Solo Fase 1 para demo
    )

    print("\n✅ Demo completada. Sistema listo para integración.")