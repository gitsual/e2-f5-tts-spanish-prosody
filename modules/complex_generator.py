#!/usr/bin/env python3
"""
====================================================================================================
GENERADOR BASE - ESTRUCTURA COMPLEJA MEJORADA (v3)
====================================================================================================

Descripción:
    Clase base para la generación de audio con F5-TTS. Proporciona la infraestructura
    fundamental para la síntesis de voz con clonación vocal y procesamiento por frases.

Funcionamiento:
    Sistema autónomo que:
    - Busca automáticamente archivos .wav de referencia en el directorio
    - Lee texto desde archivos predefinidos (texto.txt, ejemplo_texto.txt, etc.)
    - Genera audio segmentado por frases con crossfade
    - Organiza resultados en estructura de directorios con timestamp

Arquitectura de Salida:
    generaciones/
    ├── YYYY-MM-DD_HH-MM-SS_estructura_compleja/
    │   ├── referencia_1/
    │   │   ├── estructura_compleja_mejorada_nfeXX.wav  # Audio final
    │   │   ├── frase_01.wav                            # Frases individuales
    │   │   ├── frase_02.wav
    │   │   ├── ...
    │   │   └── analisis_tecnico.txt                    # Métricas técnicas
    │   └── resumen_ejecucion.txt                       # Resumen global

Características Técnicas:
    - Segmentación automática de texto en frases
    - Concatenación con crossfade configurable
    - Normalización de volumen por frase
    - Filtrado opcional de DC offset
    - Optimización de parámetros F5-TTS por contexto
    - Gestión de memoria CUDA optimizada

Parámetros de Generación:
    - nfe_step: Pasos de flow matching (default: 32)
    - cfg_strength: Fuerza de classifier-free guidance (default: 2.0)
    - sway_sampling_coef: Coeficiente de muestreo sway (default: -1.0)
    - speed: Velocidad de habla relativa (default: 1.0)

Autor: Sistema base F5-TTS
Versión: 3.0
====================================================================================================
"""

import os
import sys
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

# Suprimir warnings de librerías externas
warnings.filterwarnings("ignore")

# ====================================================================================================
# CONFIGURACIÓN DE ENTORNO
# ====================================================================================================
# Configuración CUDA para orden consistente de dispositivos
os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
os.environ['CUDA_VISIBLE_DEVICES'] = '0'

# Inicializar CUDA correctamente
if torch.cuda.is_available():
    torch.cuda.init()
    print(f"🎮 CUDA inicializada: {torch.cuda.get_device_name(0)}")
else:
    print("⚠️ CUDA no disponible, usando CPU")

# Configurar logging para análisis técnico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EstructuraComplejaMejorada:
    def __init__(self, model_path="./model_943000.pt", texto_usuario=None, session_dir=None):
        self.model_path = model_path
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.sample_rate = 24000

        # Configuración optimizada para contenido provocativo
        self.crossfade_duration = 0.15     # 150ms de crossfade
        self.base_pause_duration = 0.125   # Pausas base entre frases
        self.paragraph_pause = 0.25        # Pausas entre párrafos

        # CONFIGURACIÓN ANTI-TRUNCAMIENTO MEJORADA
        self.nfe_steps = 64  # SIEMPRE 64 para máxima calidad
        self.sway_sampling_coef = -1.0  # Bias hacia t→0 para mejor alineación
        self.cfg_strength = 2.0  # Balance estabilidad/expresividad
        self.speed = 0.95  # Ligeramente más lento para completitud

        # Parámetros de validación anti-truncamiento
        self.max_validation_attempts = None  # None = reintentos ilimitados hasta validación exitosa
        self.fallback_after_attempts = 50    # Después de 50 intentos, usar el mejor candidato
        self.quality_metrics = {
            'min_duration_ratio': 0.7,
            'max_duration_ratio': 1.5,
            'min_energy_threshold': 0.001,
            'max_silence_ratio': 0.25,
            'pitch_stability_threshold': 0.05
        }

        # Características específicas del español para anti-truncamiento
        self.problematic_finals = ['s', 'd', 'r', 'n', 'l']
        self.sinalefa_patterns = [
            r'[aeiouáéíóú]\s+[aeiouáéíóú]',  # vocales entre palabras
            r'[aeiou]n\s+[aeiou]',
            r'[aeiou]r\s+[aeiou]',
        ]

        # Directorios dinámicos (se establecen por referencia)
        self.script_dir = Path(__file__).parent.resolve()
        self.reference_dir = self.script_dir  # Referencias en el mismo directorio
        self.reference_file = None

        # Directorio de sesión con timestamp
        self.session_dir = session_dir if session_dir else self.create_session_directory()
        self.output_dir = None  # Se define por referencia

        # Lista de frases del discurso provocativo (default)
        self.frases = [
            "Eres una piba, son las 11 de la noche y estás en el sofá.",
            "Tu teléfono vibra.",
            "Es un audio de WhatsApp de una conocida del trabajo.",
            "Veintisiete años, como la mayoría del grupo.",
            "La voz le tiembla ligeramente.",
            "Tía, es que ya sé cómo identificar a un machista.",
            "Es súper fácil.",
            "Cuando hay una movida entre un tío y una tía, si se pone del lado del tío... ahí lo tienes.",
            "Es un machista."
        ]

        # Si el usuario proporciona texto, procesarlo correctamente
        if texto_usuario is not None and isinstance(texto_usuario, str):
            texto_limpio = texto_usuario.strip()
            if texto_limpio:
                partes = re.split(r'(?<!\.)\.(?!\.)', texto_limpio)
                frases_usuario = []
                for parte in partes:
                    parte_limpia = parte.strip()
                    if parte_limpia:
                        if not parte_limpia.endswith('.') and not parte_limpia.endswith('!') and not parte_limpia.endswith('?'):
                            parte_limpia += '.'
                        frases_usuario.append(parte_limpia)

                if len(frases_usuario) > 0:
                    self.frases = frases_usuario
                    print(f"📝 Texto dividido en {len(self.frases)} frases:")
                    for idx, frase in enumerate(self.frases, 1):
                        print(f"   {idx}. {frase[:60]}{'...' if len(frase) > 60 else ''}")

        # Marcadores de párrafos y pausas especiales
        self.paragraph_breaks = [1, 3, 7, 10]

        # FUSIÓN DE FRASES MÍNIMAS: unir frases cortas (<4 palabras) con la anterior si no excede longitud
        self._merge_minimum_phrases(min_words=4, max_merged_chars=160)

        print(f"🎭 Generador Mejorado v3 - Multi-referencia con Timestamp")
        print(f"📱 Device: {self.device}")
        print(f"🎯 Frases por discurso: {len(self.frases)}")
        print(f"📁 Sesión: {self.session_dir.name}")
        print(f"🔬 NFE Steps: {self.nfe_steps} (máxima calidad)")
        print(f"🛡️ Validación anti-truncamiento: ACTIVADA (reintentos ilimitados)")
        print(f"🛟 Fallback después de {self.fallback_after_attempts} intentos")
        print(f"⏱️ Pausas configuradas: base={self.base_pause_duration}s, párrafo={self.paragraph_pause}s")
        print(f"🔗 Crossfade: {self.crossfade_duration*1000:.0f}ms")

        self.f5tts = None  # Se inicializa bajo demanda
        self.session_stats = {
            'inicio': datetime.now(),
            'referencias_procesadas': 0,
            'total_referencias': 0,
            'errores': [],
            'tiempo_total': 0
        }

    def create_session_directory(self):
        """Crea un directorio único para esta sesión con timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_name = f"{timestamp}_estructura_compleja"
        
        generaciones_dir = self.script_dir / "generaciones"
        generaciones_dir.mkdir(exist_ok=True)
        
        session_dir = generaciones_dir / session_name
        session_dir.mkdir(exist_ok=True)
        
        return session_dir

    def initialize_model(self):
        """Inicializa el modelo F5-TTS si no está ya cargado"""
        if getattr(self, 'f5tts', None) is not None:
            return

        print("🔄 Cargando modelo F5-TTS...")
        
        # Asegurar que CUDA esté disponible
        if self.device == "cuda" and not torch.cuda.is_available():
            print("⚠️ CUDA no disponible, cambiando a CPU")
            self.device = "cpu"
        
        try:
            # Configurar torch.load para usar weights_only=False
            # Nota: evitamos 'import torch.serialization' aquí para no crear una variable local 'torch'
            import importlib
            importlib.import_module('torch.serialization')
            original_load = torch.load
            
            def safe_load(f, map_location=None, **kwargs):
                if 'weights_only' not in kwargs:
                    kwargs['weights_only'] = False
                if map_location is None and self.device == "cuda":
                    map_location = "cuda:0"
                elif map_location is None:
                    map_location = "cpu"
                return original_load(f, map_location=map_location, **kwargs)
            
            torch.load = safe_load
            
            self.f5tts = F5TTS(
                model_type="F5-TTS",
                ckpt_file=str(self.model_path),
                vocab_file="./vocab.txt",
                ode_method="euler",
                use_ema=True,
                vocoder_name="vocos",
                device=self.device
            )
            
            # Restaurar torch.load original
            torch.load = original_load
            
            print(f"✅ Modelo cargado exitosamente en {self.device.upper()}")
            
            if self.device == "cuda":
                print(f"🎮 GPU Memory: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f}GB")
                
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            
            # Intentar con CPU como fallback
            if self.device == "cuda":
                print("🔄 Intentando con CPU como fallback...")
                self.device = "cpu"
                try:
                    torch.load = safe_load
                    self.f5tts = F5TTS(
                        model_type="F5-TTS",
                        ckpt_file=str(self.model_path),
                        vocab_file="../data/my_speak_pinyin/vocab.txt",
                        ode_method="euler",
                        use_ema=True,
                        vocoder_name="vocos",
                        device=self.device
                    )
                    torch.load = original_load
                    print("✅ Modelo cargado en CPU (fallback)")
                    return
                except Exception as e2:
                    torch.load = original_load
                    print(f"❌ Error también en CPU: {e2}")
            
            self.session_stats['errores'].append(f"Error cargando modelo: {e}")
            sys.exit(1)

    def set_reference(self, ref_path: Path):
        """Configura la referencia actual y su carpeta de salida."""
        self.reference_dir = ref_path.parent
        self.reference_file = ref_path.name

        # Subcarpeta por referencia dentro de la sesión
        ref_stem = ref_path.stem
        self.output_dir = self.session_dir / ref_stem
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def detect_spanish_features(self, text):
        analysis = {
            'sinalefas': [],
            'problematic_finals': [],
            'total_chars': len(text),
            'estimated_syllables': 0,
            'complexity_score': 0.0
        }

        # Detectar sinalefas
        for pattern in self.sinalefa_patterns:
            matches = list(re.finditer(pattern, text.lower()))
            analysis['sinalefas'].extend(matches)

        # Detectar consonantes finales problemáticas
        words = re.findall(r'\b\w+\b', text.lower())
        for word in words:
            if word and word[-1] in self.problematic_finals:
                analysis['problematic_finals'].append(word)

        # Estimación de sílabas
        vowel_groups = len(re.findall(r'[aeiouáéíóú]+', text.lower()))
        analysis['estimated_syllables'] = max(vowel_groups, len(text.split()) * 2)

        # Score de complejidad
        sinalefa_factor = len(analysis['sinalefas']) * 0.1
        finals_factor = len(analysis['problematic_finals']) * 0.02
        analysis['complexity_score'] = min(1.0, sinalefa_factor + finals_factor)

        return analysis

    def validate_audio_anti_truncation(self, audio, text, attempt_num=1):
        if audio is None or len(audio) == 0:
            return False, "Audio vacío"

        try:
            duration = len(audio) / self.sample_rate
            spanish_features = self.detect_spanish_features(text)

            # Duración esperada (español ~8-15 chars/s)
            expected_min = len(text) / 15 * self.quality_metrics['min_duration_ratio']
            expected_max = len(text) / 8 * self.quality_metrics['max_duration_ratio']

            # Ajustar por complejidad
            if spanish_features['complexity_score'] > 0.3:
                expected_min *= 0.9
                expected_max *= 1.2

            if duration < expected_min:
                return False, f"Duración insuficiente: {duration:.2f}s < {expected_min:.2f}s (posible truncamiento)"
            if duration > expected_max:
                return False, f"Duración excesiva: {duration:.2f}s > {expected_max:.2f}s"

            # Energía mínima
            rms = np.sqrt(np.mean(audio**2))
            if rms < self.quality_metrics['min_energy_threshold']:
                return False, f"Energía insuficiente: {rms:.6f}"

            # Extremos no cortados
            window_samples = int(0.05 * self.sample_rate)
            if len(audio) > window_samples * 2:
                inicio_energy = np.mean(audio[:window_samples]**2)
                final_energy = np.mean(audio[-window_samples:]**2)
                avg_energy = np.mean(audio**2)
                if inicio_energy > avg_energy * 4 or final_energy > avg_energy * 4:
                    return False, f"Posible audio cortado en extremos"

            # Consonantes finales problemáticas
            has_problematic_finals = any(text.lower().strip().endswith(c) for c in self.problematic_finals)
            if has_problematic_finals:
                final_portion = audio[-int(0.2 * self.sample_rate):]
                try:
                    final_f0 = librosa.yin(final_portion, fmin=75, fmax=400, sr=self.sample_rate)
                    final_f0_valid = final_f0[final_f0 > 0]
                    if len(final_f0_valid) < 3:
                        return False, f"Posible consonante final cortada (texto termina en '{text.lower().strip()[-1]}')"
                except Exception:
                    pass

            # Silencio interno
            frame_length = int(0.025 * self.sample_rate)
            hop_length = frame_length // 4
            rms_frames = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
            silent_frames = np.sum(rms_frames < self.quality_metrics['min_energy_threshold'])
            silence_ratio = silent_frames / len(rms_frames) if len(rms_frames) > 0 else 0
            if silence_ratio > self.quality_metrics['max_silence_ratio']:
                return False, f"Exceso de silencio interno: {silence_ratio:.1%}"

            # Estabilidad del pitch
            try:
                f0 = librosa.yin(audio, fmin=75, fmax=400, sr=self.sample_rate)
                f0_valid = f0[f0 > 0]
                if len(f0_valid) > 10:
                    f0_jumps = np.abs(np.diff(f0_valid))
                    extreme_jumps = np.sum(f0_jumps > 50)
                    instability = extreme_jumps / len(f0_valid) if len(f0_valid) > 0 else 0
                    if instability > self.quality_metrics['pitch_stability_threshold']:
                        return False, f"Pitch inestable: {extreme_jumps} saltos extremos ({instability:.1%})"
            except Exception:
                pass

            # Verificación específica de sinalefas
            if len(spanish_features['sinalefas']) > 0:
                try:
                    stft = librosa.stft(audio, hop_length=512)
                    spectral_centroids = librosa.feature.spectral_centroid(S=np.abs(stft), sr=self.sample_rate)[0]
                    centroid_diff = np.abs(np.diff(spectral_centroids))
                    extreme_drops = np.sum(centroid_diff > np.std(centroid_diff) * 3)
                    drop_ratio = extreme_drops / len(centroid_diff) if len(centroid_diff) > 0 else 0
                    if drop_ratio > 0.1:
                        return False, f"Posibles sinalefas cortadas: {extreme_drops} caídas espectrales"
                except Exception:
                    pass

            return True, f"✅ Validación exitosa (intento {attempt_num})"

        except Exception as e:
            logger.error(f"Error en validación: {e}")
            return False, f"Error en validación: {e}"

    def generate_single_phrase_with_validation(self, text, phrase_idx):
        ref_path = self.reference_dir / self.reference_file

        best_candidate = None  # (audio, score)
        attempt = 1

        # MICRO-AJUSTE PARA FRASES CORTAS NO FUSIONADAS
        import re as _re_short
        # Limpieza simple de puntuación conflictiva antes de enviar al motor
        text = self._clean_text_simple(text)
        num_words = len(_re_short.findall(r'\b\w+\b', text))
        short_phrase = (num_words < 7) or (len(text) < 35)
        # Guardar parámetros originales
        original_nfe = self.nfe_steps
        original_sway = self.sway_sampling_coef
        original_speed = self.speed
        try:
            if short_phrase:
                # Aplicar parámetros más estables SOLO para esta frase
                self.nfe_steps = 28
                self.sway_sampling_coef = -0.3
                self.speed = 0.95

            while True:
                try:
                    if attempt > 1:
                        if attempt % 10 == 0:
                            print(f"    🔄 Reintento {attempt}/∞")
                    else:
                        print(f"  🎯 Generando frase {phrase_idx + 1}: '{text[:50]}...'")

                    wav, sr, spect = self.f5tts.infer(
                        ref_file=str(ref_path),
                        ref_text="",
                        gen_text=text,
                        nfe_step=self.nfe_steps,
                        sway_sampling_coef=self.sway_sampling_coef,
                        cfg_strength=self.cfg_strength,
                        speed=self.speed,
                        remove_silence=False,
                        seed=-1
                    )

                    if wav is None or len(wav) == 0:
                        print(f"    ❌ Audio vacío en intento {attempt}")
                        attempt += 1
                        continue

                    is_valid, validation_msg = self.validate_audio_anti_truncation(wav, text, attempt)

                    if is_valid:
                        if np.max(np.abs(wav)) > 0:
                            wav = wav / np.max(np.abs(wav)) * 0.9

                        phrase_path = self.output_dir / f"frase_{phrase_idx+1:02d}.wav"
                        sf.write(phrase_path, wav, sr)

                        print(f"    {validation_msg}")
                        return wav
                    else:
                        print(f"    ❌ Validación falló: {validation_msg}")

                        quality_score = self.evaluate_audio_quality(wav, text)
                        if best_candidate is None or quality_score < best_candidate[1]:
                            best_candidate = (wav.copy(), quality_score)

                        if self.fallback_after_attempts and attempt >= self.fallback_after_attempts:
                            print(f"    ⚠️ Usando mejor candidato tras {attempt} intentos (fallback)")
                            wav = best_candidate[0]
                            if np.max(np.abs(wav)) > 0:
                                wav = wav / np.max(np.abs(wav)) * 0.9
                            phrase_path = self.output_dir / f"frase_{phrase_idx+1:02d}.wav"
                            sf.write(phrase_path, wav, sr)
                            return wav

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"    ❌ Error en intento {attempt}: {e}")
                    # Manejo especial: tratar el error de interpolación del motor con fallbacks específicos
                    if 't must be strictly increasing or decreasing' in str(e):
                        print("    ⚠️ Activando fallbacks para frase de riesgo…")
                        # 1) Reintento con extensión neutra y parámetros estables
                        ext_text = self._extend_text_for_engine(text)
                        try:
                            wav_ext, sr, _ = self.f5tts.infer(
                                ref_file=str(ref_path),
                                ref_text="",
                                gen_text=ext_text,
                                nfe_step=28,
                                sway_sampling_coef=-0.3,
                                cfg_strength=self.cfg_strength,
                                speed=0.95,
                                remove_silence=False,
                                seed=-1
                            )
                            if wav_ext is not None and len(wav_ext) > 0:
                                valid_ext, msg_ext = self.validate_audio_anti_truncation(wav_ext, ext_text, attempt)
                                if valid_ext:
                                    if np.max(np.abs(wav_ext)) > 0:
                                        wav_ext = wav_ext / np.max(np.abs(wav_ext)) * 0.9
                                    phrase_path = self.output_dir / f"frase_{phrase_idx+1:02d}.wav"
                                    sf.write(phrase_path, wav_ext, sr)
                                    print(f"    ✅ Fallback (extensión) exitoso: {msg_ext}")
                                    return wav_ext
                        except Exception as e1:
                            print(f"    ⚠️ Fallback extensión falló: {e1}")
                        # 2) Reintento dividiendo en 2 partes y concatenando
                        try:
                            parts = self._split_text_for_engine_short(text)
                            if len(parts) > 1:
                                segs = []
                                for pi, ptxt in enumerate(parts, 1):
                                    ptxt_clean = self._clean_text_simple(ptxt)
                                    wav_p, sr, _ = self.f5tts.infer(
                                        ref_file=str(ref_path),
                                        ref_text="",
                                        gen_text=ptxt_clean,
                                        nfe_step=28,
                                        sway_sampling_coef=-0.3,
                                        cfg_strength=self.cfg_strength,
                                        speed=0.95,
                                        remove_silence=False,
                                        seed=-1
                                    )
                                    if wav_p is not None and len(wav_p) > 0:
                                        if np.max(np.abs(wav_p)) > 0:
                                            wav_p = wav_p / np.max(np.abs(wav_p)) * 0.9
                                        segs.append(wav_p)
                                if segs:
                                    # Concatenar con crossfade igual potencia si hay 2 segmentos
                                    combined = segs[0]
                                    fade_samples = int(self.crossfade_duration * self.sample_rate)
                                    for s in segs[1:]:
                                        combined = self.apply_equal_power_crossfade(combined, s, fade_samples)
                                    valid_comb, msg_comb = self.validate_audio_anti_truncation(combined, text, attempt)
                                    if valid_comb:
                                        phrase_path = self.output_dir / f"frase_{phrase_idx+1:02d}.wav"
                                        sf.write(phrase_path, combined, self.sample_rate)
                                        print(f"    ✅ Fallback (división) exitoso: {msg_comb}")
                                        return combined
                        except Exception as e2:
                            print(f"    ⚠️ Fallback división falló: {e2}")
                        # Si fallan fallbacks, detener como crítico
                        print("    🛑 Error crítico del motor detectado: deteniendo y liberando GPU…")
                        # Guardar estado de reanudación
                        try:
                            import json
                            from pathlib import Path as _Path
                            resume_state = {
                                'context': 'estructura_compleja_v3',
                                'phrase_idx': phrase_idx,
                                'reference_file': str(self.reference_dir / self.reference_file),
                                'session_dir': str(self.output_dir),
                                'device': self.device,
                            }
                            _Path('resume_state.json').write_text(json.dumps(resume_state, indent=2), encoding='utf-8')
                        except Exception:
                            pass
                        self._shutdown_gpu()
                        raise SystemExit("ENGINE_STRICT_T_ERROR")

                    if attempt >= 10 and best_candidate is not None:
                        print(f"    ⚠️ Usando mejor candidato tras múltiples errores")
                        wav = best_candidate[0]
                        if np.max(np.abs(wav)) > 0:
                            wav = wav / np.max(np.abs(wav)) * 0.9
                        return wav

                attempt += 1
                time.sleep(0.5)
        finally:
            # Restaurar parámetros originales
            self.nfe_steps = original_nfe
            self.sway_sampling_coef = original_sway
            self.speed = original_speed

    def evaluate_audio_quality(self, audio, text):
        try:
            duration = len(audio) / self.sample_rate
            spanish_features = self.detect_spanish_features(text)

            expected_min = len(text) / 15 * self.quality_metrics['min_duration_ratio']
            expected_max = len(text) / 8 * self.quality_metrics['max_duration_ratio']
            if spanish_features['complexity_score'] > 0.3:
                expected_min *= 0.9
                expected_max *= 1.2
            expected_mid = (expected_min + expected_max) / 2

            rms = np.sqrt(np.mean(audio**2))

            frame_length = int(0.025 * self.sample_rate)
            hop_length = frame_length // 4
            rms_frames = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
            silence_ratio = np.sum(rms_frames < self.quality_metrics['min_energy_threshold']) / len(rms_frames)

            duration_penalty = abs(duration - expected_mid) / expected_mid
            energy_penalty = max(0, (self.quality_metrics['min_energy_threshold'] - rms) / self.quality_metrics['min_energy_threshold'])
            silence_penalty = max(0, silence_ratio - self.quality_metrics['max_silence_ratio'])

            score = 2.0 * duration_penalty + 1.0 * energy_penalty + 1.0 * silence_penalty

            return score
        except Exception:
            return 999.0

    def add_natural_pause(self, duration_seconds):
        silence_samples = int(duration_seconds * self.sample_rate)
        pause = np.zeros(silence_samples, dtype=np.float32)

        noise_level = 0.0001
        pink_noise = np.random.normal(0, noise_level, silence_samples)

        b, a = butter(1, 0.1, btype='low')
        pink_noise = filtfilt(b, a, pink_noise)

        pause += pink_noise.astype(np.float32)

        return pause

    def apply_equal_power_crossfade(self, audio1, audio2, fade_samples):
        if len(audio1) < fade_samples or len(audio2) < fade_samples:
            return np.concatenate([audio1, audio2])

        t = np.linspace(0, np.pi/2, fade_samples)
        fade_out = np.cos(t)
        fade_in = np.sin(t)

        audio1_faded = audio1.copy()
        audio1_faded[-fade_samples:] *= fade_out

        audio2_faded = audio2.copy()
        audio2_faded[:fade_samples] *= fade_in

        overlap = audio1_faded[-fade_samples:] + audio2_faded[:fade_samples]

        result = np.concatenate([
            audio1_faded[:-fade_samples],
            overlap,
            audio2_faded[fade_samples:]
        ])

        return result

    def concatenate_with_dramatic_transitions(self, generated_audios):
        print("🎭 Aplicando transiciones...")

        if not generated_audios:
            print("❌ No hay audios para concatenar")
            return None

        final_audio = generated_audios[0][1].copy()
        fade_samples = int(self.crossfade_duration * self.sample_rate)

        for i in range(1, len(generated_audios)):
            phrase_idx, current_audio = generated_audios[i]

            pause_duration = self.base_pause_duration
            natural_pause = self.add_natural_pause(pause_duration)
            final_audio = np.concatenate([final_audio, natural_pause])

            final_audio = self.apply_equal_power_crossfade(final_audio, current_audio, fade_samples)

            print(f"    🔗 Transición aplicada: frase {phrase_idx + 1}")

        final_audio = self.apply_professional_normalization(final_audio)

        return final_audio

    def apply_professional_normalization(self, audio):
        current_rms = np.sqrt(np.mean(audio**2))
        if current_rms > 0:
            target_rms = 10**(-20 / 20)
            audio = audio * (target_rms / current_rms)

        peak = np.max(np.abs(audio))
        peak_limit = 10**(-3 / 20)
        if peak > peak_limit:
            audio = audio * (peak_limit / peak)

        return audio.astype(np.float32)

    def _shutdown_gpu(self):
        """Libera memoria GPU (sin reset para no afectar GPU primaria)."""
        try:
            if self.device == 'cuda':
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                torch.cuda.ipc_collect()
        except Exception as e:
            print(f"    ⚠️ No se pudo liberar memoria GPU: {e}")

    def generate_all_phrases(self):
        print("🎭 Iniciando generación con validación anti-truncamiento...")
        print(f"   • NFE Steps: {self.nfe_steps}")
        print(f"   • Reintentos: ilimitados hasta validación exitosa")
        print(f"   • Fallback después de {self.fallback_after_attempts} intentos")
        print(f"   • Pausas base: {self.base_pause_duration}s")
        print(f"   • Crossfade: {self.crossfade_duration*1000:.0f}ms")

        generated_audios = []
        validation_stats = {'exitosas': 0, 'con_reintentos': 0, 'fallidas': 0}

        for i, frase in enumerate(tqdm(self.frases, desc="Generando con anti-truncamiento")):
            audio = self.generate_single_phrase_with_validation(frase, i)
            if audio is not None:
                generated_audios.append((i, audio))
                validation_stats['exitosas'] += 1
            else:
                print(f"    ⚠️ Frase {i+1} falló completamente")
                validation_stats['fallidas'] += 1

        print(f"\n📊 Estadísticas de validación:")
        print(f"   • Exitosas: {validation_stats['exitosas']}/{len(self.frases)}")
        print(f"   • Fallidas: {validation_stats['fallidas']}")

        return generated_audios

    def save_technical_analysis(self, final_audio, generated_count):
        analysis_path = self.output_dir / "analisis_tecnico.txt"

        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write("ANÁLISIS TÉCNICO - ESTRUCTURA COMPLEJA MEJORADA (v3)\n")
            f.write("=" * 60 + "\n\n")

            f.write("CONFIGURACIÓN ANTI-TRUNCAMIENTO:\n")
            f.write(f"- NFE Steps: {self.nfe_steps} (máxima calidad)\n")
            f.write(f"- Sway Sampling: {self.sway_sampling_coef}\n")
            f.write(f"- CFG Strength: {self.cfg_strength}\n")
            f.write(f"- Speed: {self.speed}\n")
            f.write(f"- Max reintentos: ilimitados (fallback tras {self.fallback_after_attempts})\n\n")

            duration = len(final_audio) / self.sample_rate
            rms = np.sqrt(np.mean(final_audio**2))
            peak = np.max(np.abs(final_audio))

            f.write("ANÁLISIS DE AUDIO:\n")
            f.write(f"- Duración: {duration:.2f} segundos\n")
            f.write(f"- RMS Level: {20*np.log10(rms):.1f} dBFS\n")
            f.write(f"- Peak Level: {20*np.log10(peak):.1f} dBFS\n")
            f.write(f"- Dynamic Range: {20*np.log10(peak/(rms+1e-10)):.1f} dB\n\n")

            f.write(f"FRASES PROCESADAS: {generated_count}/{len(self.frases)}\n\n")

            for i, frase in enumerate(self.frases, 1):
                features = self.detect_spanish_features(frase)
                f.write(f"{i}. \"{frase}\"\n")
                f.write(f"   - Sílabas estimadas: {features['estimated_syllables']}\n")
                f.write(f"   - Complejidad: {features['complexity_score']:.2f}\n")
                f.write(f"   - Consonantes finales problemáticas: {features['problematic_finals']}\n\n")

        print(f"📄 Análisis técnico guardado: {analysis_path.name}")

    def generate_complete_speech_for_reference(self, ref_path: Path):
        print("🎭 Iniciando generación mejorada con anti-truncamiento")
        print("=" * 65)

        self.set_reference(ref_path)

        print(f"🎙️ Referencia: {self.reference_file}")
        print(f"📂 Carpeta de salida: {self.output_dir}")

        start_time = time.time()

        if not ref_path.exists():
            print(f"❌ No se encuentra la referencia: {ref_path}")
            error_msg = f"Referencia no encontrada: {ref_path}"
            self.session_stats['errores'].append(error_msg)
            return

        generated_audios = self.generate_all_phrases()

        if not generated_audios:
            print("❌ No se pudieron generar audios")
            error_msg = f"No se pudieron generar audios para {self.reference_file}"
            self.session_stats['errores'].append(error_msg)
            return

        print(f"✅ Generadas {len(generated_audios)} de {len(self.frases)} frases")

        final_speech = self.concatenate_with_dramatic_transitions(generated_audios)

        if final_speech is None:
            print("❌ Error en la concatenación")
            error_msg = f"Error en concatenación para {self.reference_file}"
            self.session_stats['errores'].append(error_msg)
            return

        output_filename = "estructura_compleja_mejorada_nfe64.wav"
        output_path = self.output_dir / output_filename
        sf.write(output_path, final_speech, self.sample_rate)

        self.save_technical_analysis(final_speech, len(generated_audios))

        end_time = time.time()
        duration_minutes = len(final_speech) / self.sample_rate / 60
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        generation_time = end_time - start_time

        print("\n🎊 ¡Generación completada exitosamente!")
        print("=" * 65)
        print(f"📁 Archivo guardado: {output_path.name}")
        print(f"⏱️ Duración del audio: {duration_minutes:.2f} minutos")
        print(f"💾 Tamaño del archivo: {file_size_mb:.1f} MB")
        print(f"🎯 Frases incluidas: {len(generated_audios)}")
        print(f"🎙️ Referencia utilizada: {self.reference_file}")
        print(f"🔄 Tiempo de generación: {generation_time:.1f} segundos")
        print(f"⚡ Promedio por frase: {generation_time/len(generated_audios):.1f} segundos")

        # Actualizar estadísticas de sesión
        self.session_stats['referencias_procesadas'] += 1
        self.session_stats['tiempo_total'] += generation_time

        print(f"\n🔧 Configuración técnica:")
        print(f"   • NFE Steps: {self.nfe_steps} (máxima calidad)")
        print(f"   • Sway Sampling: {self.sway_sampling_coef}")
        print(f"   • CFG Strength: {self.cfg_strength}")
        print(f"   • Speed: {self.speed}")
        print(f"   • Sample rate: {self.sample_rate} Hz")
        print(f"   • Crossfade: {self.crossfade_duration * 1000:.0f}ms")
        print(f"   • Pausas base: {self.base_pause_duration}s")
        print(f"   • Pausas párrafo: {self.paragraph_pause}s")
        print(f"   • Validación anti-truncamiento: ACTIVADA")
        print(f"   • Reintentos: ilimitados (fallback tras {self.fallback_after_attempts} intentos)")
        print(f"   • Normalización: -20dBFS target, -3dB peak")

    def save_session_summary(self):
        """Guarda un resumen de toda la sesión"""
        summary_path = self.session_dir / "resumen_ejecucion.txt"
        fin = datetime.now()
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("RESUMEN DE EJECUCIÓN - GENERADOR ESTRUCTURA COMPLEJA v3\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("INFORMACIÓN DE SESIÓN:\n")
            f.write(f"- Inicio: {self.session_stats['inicio'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- Fin: {fin.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- Duración total: {(fin - self.session_stats['inicio']).total_seconds():.1f} segundos\n")
            f.write(f"- Directorio de sesión: {self.session_dir.name}\n\n")
            
            f.write("ESTADÍSTICAS DE PROCESAMIENTO:\n")
            f.write(f"- Referencias totales: {self.session_stats['total_referencias']}\n")
            f.write(f"- Referencias procesadas: {self.session_stats['referencias_procesadas']}\n")
            f.write(f"- Tasa de éxito: {(self.session_stats['referencias_procesadas']/max(1,self.session_stats['total_referencias']))*100:.1f}%\n")
            f.write(f"- Tiempo total de generación: {self.session_stats['tiempo_total']:.1f} segundos\n")
            f.write(f"- Promedio por referencia: {self.session_stats['tiempo_total']/max(1,self.session_stats['referencias_procesadas']):.1f} segundos\n\n")
            
            f.write("CONFIGURACIÓN UTILIZADA:\n")
            f.write(f"- NFE Steps: {self.nfe_steps}\n")
            f.write(f"- Sway Sampling: {self.sway_sampling_coef}\n")
            f.write(f"- CFG Strength: {self.cfg_strength}\n")
            f.write(f"- Speed: {self.speed}\n")
            f.write(f"- Fallback después de: {self.fallback_after_attempts} intentos\n\n")
            
            f.write(f"TEXTO PROCESADO ({len(self.frases)} frases):\n")
            for i, frase in enumerate(self.frases, 1):
                f.write(f"{i}. {frase}\n")
            f.write("\n")
            
            if self.session_stats['errores']:
                f.write("ERRORES ENCONTRADOS:\n")
                for i, error in enumerate(self.session_stats['errores'], 1):
                    f.write(f"{i}. {error}\n")
            else:
                f.write("✅ No se encontraron errores durante la ejecución.\n")
        
        print(f"📋 Resumen de sesión guardado: {summary_path.name}")

    def _merge_minimum_phrases(self, min_words: int = 4, max_merged_chars: int = 160):
        """Une frases con menos de min_words con la anterior si el resultado no supera max_merged_chars."""
        import re as _re_m
        if not self.frases:
            return
        merged = []
        for idx, frase in enumerate(self.frases):
            words = len(_re_m.findall(r'\b\w+\b', frase))
            if words < min_words and len(merged) > 0:
                prev = merged[-1]
                # Decidir separador adecuado
                sep = ', ' if not prev.endswith((',', ';', ':')) else ' '
                candidate = prev.rstrip().rstrip('.') + sep + frase.lstrip()
                if len(candidate) <= max_merged_chars:
                    merged[-1] = candidate
                    continue
            merged.append(frase)
        if len(merged) != len(self.frases):
            print(f"🔗 Frases cortas fusionadas: {len(self.frases)} → {len(merged)}")
        self.frases = merged

    def _clean_text_simple(self, text: str) -> str:
        """Limpieza mínima de puntuación conflictiva para el motor."""
        import re
        s = (text or '').strip()
        # Colapsar puntos/espacios duplicados
        s = re.sub(r'\s*\.\s*\.', '.', s)
        s = re.sub(r'\.\s+\.', '.', s)
        s = re.sub(r'\s{2,}', ' ', s)
        # Arreglar comillas y punto final duplicado
        s = re.sub(r'"\s*\.', '."', s)
        s = re.sub(r'\.(\s*\.)+$', '.', s)
        # Un único signo final
        s = re.sub(r'([.!?]){2,}$', r'\1', s)
        return s.strip()

    def _extend_text_for_engine(self, text: str) -> str:
        """Extiende ligeramente frases para dar tiempo al motor (solo para motor)."""
        s = (text or '').strip()
        if not s:
            return s
        if s.endswith('?'):
            return s + '...'
        if s.endswith('!'):
            return s + '...'
        if not s.endswith('.'):
            return s + '...'
        return s[:-1] + '...'

    def _split_text_for_engine_short(self, text: str) -> list:
        """Divide en 2 partes por coma/conector o por mitad de palabras."""
        import re
        s = (text or '').strip()
        commas = [m.start() for m in re.finditer(r',', s)]
        if commas:
            target = len(s) // 2
            split_pos = min(commas, key=lambda x: abs(x - target))
            left = s[:split_pos+1].strip()
            right = s[split_pos+1:].strip()
            if not left.endswith(('.', '!', '?')):
                left = left.rstrip(',') + '.'
            return [left, right]
        m = re.search(r'\s(y|pero|porque|aunque|entonces|así que|o)\s', s)
        if m:
            pos = m.start(0) + 1
            left = s[:pos].strip()
            right = s[pos:].strip()
            if not left.endswith(('.', '!', '?')):
                left += '.'
            return [left, right]
        words = s.split()
        if len(words) > 6:
            mid = len(words) // 2
            left = ' '.join(words[:mid]).strip()
            right = ' '.join(words[mid:]).strip()
            if not left.endswith(('.', '!', '?')):
                left += '.'
            return [left, right]
        return [s]


def listar_referencias_wav(refs_dir: Path):
    """Devuelve una lista de rutas a .wav en el directorio indicado (no recursivo)."""
    if not refs_dir.exists() or not refs_dir.is_dir():
        return []
    wavs = [p for p in sorted(refs_dir.iterdir()) if p.suffix.lower() == ".wav" and p.is_file()]
    return wavs


def main():
    # Directorio del script (contiene las referencias y el texto)
    script_dir = Path(__file__).parent.resolve()
    
    # Buscar archivo de texto en el directorio del script
    texto_usuario = None
    posibles_archivos_texto = [
        "texto.txt",
        "ejemplo_texto.txt", 
        "contenido.txt",
        "frases.txt"
    ]
    
    archivo_texto_encontrado = None
    for nombre_archivo in posibles_archivos_texto:
        archivo_path = script_dir / nombre_archivo
        if archivo_path.exists():
            archivo_texto_encontrado = archivo_path
            break
    
    if archivo_texto_encontrado:
        try:
            texto_usuario = archivo_texto_encontrado.read_text(encoding="utf-8")
            print(f"📖 Texto cargado desde: {archivo_texto_encontrado.name}")
        except Exception as e:
            print(f"❌ Error leyendo {archivo_texto_encontrado.name}: {e}")
            print("🔄 Usando texto por defecto...")
            texto_usuario = None
    else:
        print(f"📝 No se encontró archivo de texto en {script_dir}")
        print(f"   Archivos buscados: {', '.join(posibles_archivos_texto)}")
        print("🔄 Usando texto por defecto...")

    # Buscar referencias .wav en el directorio del script
    referencias = listar_referencias_wav(script_dir)
    
    if len(referencias) == 0:
        print(f"❌ No se encontraron .wav de referencia en: {script_dir}")
        print("   Coloca los .wav de referencia en el mismo directorio del script")
        sys.exit(1)

    print(f"🔎 Referencias encontradas ({len(referencias)}):")
    for r in referencias:
        print(f"   • {r.name}")

    # Crear generador con timestamp único para esta sesión
    generator = EstructuraComplejaMejorada(texto_usuario=texto_usuario)
    generator.session_stats['total_referencias'] = len(referencias)
    
    # Inicializar modelo una sola vez
    generator.initialize_model()

    print(f"\n📁 Sesión iniciada: {generator.session_dir.name}")
    print(f"🎯 Se generarán {len(referencias)} versiones completas")

    # Generar para cada referencia
    for ref_path in referencias:
        print("\n" + "#" * 80)
        print(f"▶️ Generando versión completa usando referencia: {ref_path.name}")
        print("#" * 80)
        try:
            generator.generate_complete_speech_for_reference(ref_path)
        except KeyboardInterrupt:
            print("⏹️ Proceso interrumpido por el usuario.")
            break
        except Exception as e:
            print(f"❌ Error generando con referencia {ref_path.name}: {e}")
            generator.session_stats['errores'].append(f"Error con {ref_path.name}: {e}")

    # Guardar resumen final de la sesión
    generator.save_session_summary()
    
    print(f"\n🏁 Sesión completada: {generator.session_dir.name}")
    print(f"📊 Referencias procesadas: {generator.session_stats['referencias_procesadas']}/{generator.session_stats['total_referencias']}")
    if generator.session_stats['errores']:
        print(f"⚠️ Errores: {len(generator.session_stats['errores'])}")
    print(f"📂 Resultados en: {generator.session_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true', help='Reanuda desde el último estado guardado')
    args = parser.parse_args()

    if args.resume:
        # Modo reanudar (placeholder informativo)
        try:
            import json
            from pathlib import Path as _Path
            state = json.loads(_Path('resume_state.json').read_text(encoding='utf-8'))
            print(f"🔄 Reanudar desde frase {state.get('phrase_idx','?')} con referencia {state.get('reference_file','?')}")
            # En una siguiente iteración se puede saltar directamente a esa frase con lógica adicional
        except Exception as e:
            print(f"❌ No se pudo reanudar: {e}")
        sys.exit(0)
    else:
        main()
