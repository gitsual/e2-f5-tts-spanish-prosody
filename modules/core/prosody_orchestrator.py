#!/usr/bin/env python3
"""
Orquestador Maestro de Arquitectura Vocal para N Párrafos con M Frases Variables

Implementa el algoritmo completo de arquitectura vocal para lectura basado en:
- Arco Prosódico (Lieberman, 1967; Pierrehumbert, 1980)
- Regla del 3-5-8 (BBC, años 50) generalizada a N párrafos
- Sincronización respiratoria-sintáctica

Autor: Implementación del algoritmo maestro prosódico
Versión: 2.0 - Genérico para cualquier N párrafos, M frases
"""

import numpy as np
import re
import math
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProsodyParams:
    """Parámetros prosódicos para una frase específica"""
    parrafo_id: int
    frase_id: int
    texto: str
    tono_base: float
    velocidad: float
    curva: str
    tono_inicial: Optional[float] = None
    tono_final: Optional[float] = None
    intensidad: float = 1.0
    pausa_final: float = 0.5
    enfasis_palabras: Dict[str, Dict] = None
    modificadores_especiales: Dict = None

    def __post_init__(self):
        if self.enfasis_palabras is None:
            self.enfasis_palabras = {}
        if self.modificadores_especiales is None:
            self.modificadores_especiales = {}


class ArquitecturaVocalMaestra:
    """
    Orquestador maestro que implementa arquitectura vocal documentada
    para cualquier número de párrafos y frases
    """

    def __init__(self,
                 f0_base: float = 185.0,
                 velocidad_natural: float = 145.0,
                 idioma: str = "es"):
        """
        Args:
            f0_base: Frecuencia fundamental base en Hz
            velocidad_natural: Velocidad natural en palabras por minuto
            idioma: Código de idioma para análisis sintáctico
        """

        self.f0_base = f0_base
        self.velocidad_natural = velocidad_natural
        self.idioma = idioma

        # Configuración de arquitectura vocal
        self.configuracion = {
            # Arco prosódico base
            'arco_global': {
                'inicio_boost': 0.08,      # +8% en apertura
                'desarrollo_peak': 0.15,   # Máximo +15% en pivote
                'cierre_drop': -0.08,      # -8% en cierre final
                'transicion_suave': 0.05   # Factor de suavizado
            },

            # Curvas melódicas por posición en párrafo
            'curvas_frase': {
                'ataque': {
                    'boost_inicial': 0.08,
                    'velocidad_factor': 0.95,
                    'contorno': "(0%,+5%) (20%,+8%) (80%,+3%) (100%,0%)"
                },
                'meseta_modulada': {
                    'oscilacion_max': 0.03,
                    'velocidad_factor': 1.0,
                    'contorno': "(0%,0%) (50%,+2%) (100%,0%)"
                },
                'cadencia': {
                    'descenso_exp': 0.95,
                    'velocidad_factor': 0.88,
                    'contorno': "(0%,0%) (70%,-2%) (100%,-8%)"
                }
            },

            # Modificadores por tipo de frase
            'tipos_frase': {
                'pregunta': {
                    'tono_final_boost': 0.20,
                    'curva_especial': 'ascendente_final',
                    'velocidad_factor': 1.05,
                    'contorno': "(0%,0%) (60%,0%) (100%,+20%)"
                },
                'exclamacion': {
                    'tono_inicial_boost': 0.15,
                    'intensidad_factor': 1.3,
                    'velocidad_factor': 1.1,
                    'contorno': "(0%,+15%) (30%,+10%) (100%,+5%)"
                },
                'subordinada_larga': {
                    'mantener_tono': True,
                    'velocidad_factor': 0.92,
                    'pausas_internas': True
                },
                'enumeracion': {
                    'patron': 'escalera_ascendente',
                    'incremento_por_elemento': 0.02,
                    'pausa_entre_elementos': 0.3
                },
                'cita': {
                    'tono_factor': 0.95,
                    'velocidad_factor': 0.90,
                    'reverb': 0.15
                }
            },

            # Palabras clave que requieren énfasis
            'palabras_enfasis': {
                'importancia': ['fundamental', 'crucial', 'esencial', 'importante', 'clave'],
                'contraste': ['sin embargo', 'pero', 'no obstante', 'aunque', 'mientras'],
                'conclusion': ['finalmente', 'por lo tanto', 'en conclusión', 'así pues'],
                'temporal': ['entonces', 'después', 'antes', 'mientras tanto', 'posteriormente'],
                'causal': ['porque', 'debido a', 'por esta razón', 'consecuentemente']
            }
        }

    def orquestar_lectura_completa(self, texto: str) -> List[ProsodyParams]:
        """
        Orquesta la lectura completa aplicando arquitectura vocal documentada

        Args:
            texto: Texto completo a procesar

        Returns:
            Lista de parámetros prosódicos por frase
        """
        logger.info("🎭 Iniciando orquestación maestra de arquitectura vocal")

        # ANÁLISIS INICIAL
        parrafos = self._segmentar_parrafos(texto)
        N = len(parrafos)
        M = [len(self._segmentar_frases(p)) for p in parrafos]

        logger.info(f"📊 Análisis estructural: {N} párrafos, {M} frases por párrafo")

        # CÁLCULO DE ARQUITECTURA GLOBAL
        centro_gravitacional = self._calcular_centro_dramatico(parrafos)
        arco_global = self._generar_arco_narrativo(N, centro_gravitacional)

        logger.info(f"🎯 Centro dramático en párrafo {centro_gravitacional + 1}/{N}")

        # MATRIZ DE CONTROL PROSÓDICO
        control_matrix = []

        for i, parrafo in enumerate(parrafos):
            # CALCULAR FUNCIÓN DE PÁRRAFO
            funcion = self._determinar_funcion_parrafo(i, N, centro_gravitacional)
            logger.info(f"📝 Párrafo {i+1}: función '{funcion}'")

            # TONO BASE DEL PÁRRAFO
            tono_base_p = self._calcular_tono_base_parrafo(i, N, funcion, centro_gravitacional)

            # PROCESAR CADA FRASE DEL PÁRRAFO
            frases = self._segmentar_frases(parrafo)
            M_actual = len(frases)

            for j, frase in enumerate(frases):
                # Crear parámetros prosódicos para esta frase
                params = self._procesar_frase_individual(
                    frase, i, j, M_actual, tono_base_p, funcion, frases,
                    es_ultimo_parrafo=(i == N - 1)
                )
                control_matrix.append(params)

        # POST-PROCESAMIENTO ARMÓNICO
        control_matrix = self._aplicar_suavizado_transiciones(control_matrix)
        control_matrix = self._verificar_coherencia_tonal(control_matrix)

        logger.info(f"✅ Orquestación completa: {len(control_matrix)} frases procesadas")

        return control_matrix

    def _segmentar_parrafos(self, texto: str) -> List[str]:
        """Segmenta el texto en párrafos usando dobles saltos de línea principalmente"""
        # Dividir principalmente por dobles saltos de línea
        parrafos_raw = re.split(r'\n\s*\n', texto)

        parrafos = []
        for p in parrafos_raw:
            p_clean = p.strip()
            if p_clean and len(p_clean) > 10:  # Filtrar párrafos muy cortos
                # Limpiar espacios extra y saltos de línea simples
                p_clean = re.sub(r'\s+', ' ', p_clean)

                # Asegurar que termine en punto si no tiene puntuación final
                if not p_clean[-1] in '.!?':
                    p_clean += '.'
                parrafos.append(p_clean)

        return parrafos

    def _segmentar_frases(self, parrafo: str) -> List[str]:
        """
        Segmenta un párrafo en frases considerando signos de apertura españoles
        Separa correctamente "¡-!" y "¿-?" como frases independientes
        """
        # Proteger abreviaciones comunes
        texto_protegido = re.sub(r'\b(Sr|Sra|Dr|Dra|St|Sto|Sta)\.\s*', r'\1<DOT> ', parrafo)

        # NUEVO: Pre-procesamiento para signos de apertura españoles
        # Insertar marcadores antes de signos de apertura cuando no están al inicio
        texto_protegido = re.sub(r'([.!?])\s*([¡¿])', r'\1<FRASE_BREAK>\2', texto_protegido)

        # También manejar casos donde hay espacios múltiples
        texto_protegido = re.sub(r'([.!?])\s{2,}([¡¿])', r'\1<FRASE_BREAK>\2', texto_protegido)

        # Dividir por marcadores de ruptura de frase
        if '<FRASE_BREAK>' in texto_protegido:
            frases_raw = texto_protegido.split('<FRASE_BREAK>')
        else:
            # Fallback al método original si no hay marcadores
            frases_raw = re.split(r'[.!?]+\s+', texto_protegido)

        frases = []
        for i, f in enumerate(frases_raw):
            f_clean = f.replace('<DOT>', '.').strip()
            if f_clean:
                # Procesar cada frase para separar exclamaciones/interrogaciones múltiples
                sub_frases = self._separar_exclamaciones_interrogaciones(f_clean)
                frases.extend(sub_frases)

        return [f for f in frases if f.strip()]

    def _separar_exclamaciones_interrogaciones(self, texto: str) -> List[str]:
        """
        Separa exclamaciones e interrogaciones que están juntas recursivamente
        Ejemplo: "¡Hola! ¿Cómo estás?" → ["¡Hola!", "¿Cómo estás?"]
        """
        # Aplicar separación recursiva hasta que no haya más cambios
        frases_actuales = [texto]
        cambios = True

        while cambios:
            cambios = False
            nuevas_frases = []

            for frase in frases_actuales:
                frases_divididas = self._dividir_frase_simple(frase)
                if len(frases_divididas) > 1:
                    cambios = True
                nuevas_frases.extend(frases_divididas)

            frases_actuales = nuevas_frases

        # Limpiar y finalizar frases
        frases_finales = []
        for frase in frases_actuales:
            frase_limpia = frase.strip()
            if frase_limpia:
                # Asegurar puntuación final
                if not frase_limpia[-1] in '.!?':
                    # Determinar qué puntuación añadir según el contenido
                    if frase_limpia.startswith('¡') or '¡' in frase_limpia:
                        frase_limpia += '!'
                    elif frase_limpia.startswith('¿') or '¿' in frase_limpia:
                        frase_limpia += '?'
                    else:
                        frase_limpia += '.'
                frases_finales.append(frase_limpia)

        return frases_finales

    def _dividir_frase_simple(self, texto: str) -> List[str]:
        """
        Divide una frase simple en el primer punto de separación encontrado
        """
        # Buscar patrones de separación en orden de prioridad

        # 1. Separación por exclamación/interrogación seguida de apertura
        patron1 = r'([!?])\s*([¡¿])'
        match1 = re.search(patron1, texto)
        if match1:
            pos = match1.start(2)  # Posición del signo de apertura
            parte1 = texto[:pos].strip()
            parte2 = texto[pos:].strip()
            if parte1 and parte2:
                return [parte1, parte2]

        # 2. Separación por final de oración seguida de apertura (sin espacio requerido)
        patron2 = r'([.!?])\s*([¡¿])'
        match2 = re.search(patron2, texto)
        if match2 and match2.start() > 0:  # No dividir si está al inicio
            pos = match2.start(2)
            parte1 = texto[:pos].strip()
            parte2 = texto[pos:].strip()
            if parte1 and parte2:
                return [parte1, parte2]

        # 3. Separación por exclamación/interrogación seguida de oración normal
        patron3 = r'([!?])\s+([A-ZÁÉÍÓÚÑ])'
        match3 = re.search(patron3, texto)
        if match3:
            pos = match3.start(2)
            parte1 = texto[:pos].strip()
            parte2 = texto[pos:].strip()
            if parte1 and parte2:
                return [parte1, parte2]

        # 4. Separación por punto seguido de mayúscula (frases declarativas)
        patron4 = r'(\.\s+)([A-ZÁÉÍÓÚÑ])'
        match4 = re.search(patron4, texto)
        if match4:
            pos = match4.start(2)
            parte1 = texto[:pos].strip()
            parte2 = texto[pos:].strip()
            if parte1 and parte2 and len(parte1) > 3:  # Evitar divisiones muy cortas
                return [parte1, parte2]

        # Si no se puede dividir, devolver como está
        return [texto]

    def _calcular_centro_dramatico(self, parrafos: List[str]) -> int:
        """
        Encuentra el punto de máxima tensión/importancia semántica
        """
        indicadores_peso = {
            'giros': ['sin embargo', 'pero', 'no obstante', 'aunque', 'mientras que'],
            'importancia': ['fundamental', 'crucial', 'esencial', 'importante', 'clave'],
            'conclusiones': ['finalmente', 'por lo tanto', 'en conclusión', 'así pues'],
            'contraste': ['diferente', 'opuesto', 'contrario', 'distinto'],
            'causalidad': ['porque', 'debido a', 'por esta razón', 'consecuentemente']
        }

        pesos_parrafos = []

        for i, parrafo in enumerate(parrafos):
            peso = 0
            texto_lower = parrafo.lower()

            # Contar indicadores semánticos
            for categoria, palabras in indicadores_peso.items():
                for palabra in palabras:
                    peso += texto_lower.count(palabra) * {
                        'giros': 3,
                        'importancia': 2,
                        'conclusiones': 2,
                        'contraste': 2,
                        'causalidad': 1
                    }[categoria]

            # Peso por longitud (párrafos más largos suelen ser más importantes)
            peso += len(parrafo) / 100

            # Peso por posición (centro-final suelen ser más importantes)
            if 0.3 <= i/len(parrafos) <= 0.8:
                peso *= 1.2

            pesos_parrafos.append(peso)

        # Retornar índice del párrafo con mayor peso
        return pesos_parrafos.index(max(pesos_parrafos))

    def _generar_arco_narrativo(self, N: int, centro: int) -> List[float]:
        """
        Genera el arco tonal global del documento
        """
        arco = []

        for i in range(N):
            if i < centro:
                # Ascenso gradual hacia el centro
                factor = 1.0 + (i / centro) * self.configuracion['arco_global']['desarrollo_peak']
            elif i == centro:
                # Punto máximo
                factor = 1.0 + self.configuracion['arco_global']['desarrollo_peak']
            else:
                # Descenso hacia el final
                descenso_restante = N - centro - 1
                if descenso_restante > 0:
                    pos_en_descenso = (i - centro) / descenso_restante
                    factor = (1.0 + self.configuracion['arco_global']['desarrollo_peak']) * \
                            (1.0 - pos_en_descenso) + \
                            (1.0 + self.configuracion['arco_global']['cierre_drop']) * pos_en_descenso
                else:
                    factor = 1.0 + self.configuracion['arco_global']['cierre_drop']

            arco.append(factor)

        return arco

    def _determinar_funcion_parrafo(self, indice: int, total: int, centro: int) -> str:
        """
        Asigna rol narrativo según posición, proporción y centro dramático
        """
        proporcion = indice / total

        if indice == 0:
            return 'apertura'
        elif indice == centro:
            return 'pivote'
        elif indice == total - 1:
            return 'cierre'
        elif indice < centro:
            return 'desarrollo_ascendente'
        else:
            return 'desarrollo_descendente'

    def _calcular_tono_base_parrafo(self, indice: int, total: int, funcion: str, centro: int) -> float:
        """
        Calcula el tono base del párrafo según su función narrativa
        """
        modificadores_funcion = {
            'apertura': 1.0,
            'desarrollo_ascendente': 1.0 + 0.05 * (indice / max(centro, 1)),  # Evitar división por cero
            'pivote': 1.0 + self.configuracion['arco_global']['desarrollo_peak'],
            'desarrollo_descendente': 1.0 + self.configuracion['arco_global']['desarrollo_peak'] * \
                                    (1.0 - (indice - centro) / max(total - centro, 1)),  # Evitar división por cero
            'cierre': 1.0 + self.configuracion['arco_global']['cierre_drop']
        }

        return self.f0_base * modificadores_funcion[funcion]

    def _procesar_frase_individual(self, frase: str, parrafo_id: int, frase_id: int,
                                 total_frases: int, tono_base_p: float,
                                 funcion_parrafo: str, todas_frases: List[str],
                                 es_ultimo_parrafo: bool = False) -> ProsodyParams:
        """
        Procesa una frase individual calculando todos sus parámetros prosódicos
        """
        # POSICIÓN RELATIVA EN PÁRRAFO
        posicion_relativa = frase_id / max(total_frases - 1, 1)

        # DETERMINAR CURVA MELÓDICA
        if posicion_relativa < 0.25:
            curva = 'ataque'
            config_curva = self.configuracion['curvas_frase']['ataque']
        elif posicion_relativa < 0.75:
            curva = 'meseta_modulada'
            config_curva = self.configuracion['curvas_frase']['meseta_modulada']
        else:
            curva = 'cadencia'
            config_curva = self.configuracion['curvas_frase']['cadencia']

        # TONO Y VELOCIDAD BASE
        if curva == 'ataque':
            tono_frase = tono_base_p * (1 + config_curva['boost_inicial'])
        elif curva == 'meseta_modulada':
            # Oscilación sinusoidal suave
            oscilacion = config_curva['oscilacion_max'] * math.sin(2 * math.pi * frase_id / total_frases)
            tono_frase = tono_base_p * (1 + oscilacion)
        else:  # cadencia
            # Descenso exponencial
            factor_descenso = config_curva['descenso_exp'] ** (frase_id - 0.75 * total_frases)
            tono_frase = tono_base_p * factor_descenso

        velocidad = self.velocidad_natural * config_curva['velocidad_factor']

        # ANÁLISIS SINTÁCTICO-SEMÁNTICO
        tipo_frase = self._analizar_tipo_frase(frase)
        palabras_enfasis = self._detectar_palabras_importantes(frase)

        # APLICAR MODIFICADORES POR TIPO
        modificadores = {}
        if tipo_frase in self.configuracion['tipos_frase']:
            tipo_config = self.configuracion['tipos_frase'][tipo_frase]

            if 'tono_final_boost' in tipo_config:
                tono_final = tono_frase * (1 + tipo_config['tono_final_boost'])
                modificadores['tono_final'] = tono_final

            if 'tono_inicial_boost' in tipo_config:
                tono_inicial = tono_frase * (1 + tipo_config['tono_inicial_boost'])
                modificadores['tono_inicial'] = tono_inicial

            if 'velocidad_factor' in tipo_config:
                velocidad *= tipo_config['velocidad_factor']

            if 'intensidad_factor' in tipo_config:
                modificadores['intensidad'] = tipo_config['intensidad_factor']

            if 'contorno' in tipo_config:
                curva = tipo_config['contorno']

        # GESTIÓN DE TRANSICIONES Y PAUSAS
        pausa_final = self._calcular_pausa_transicion(frase, frase_id, total_frases, todas_frases, es_ultimo_parrafo)

        # CREAR PARÁMETROS
        params = ProsodyParams(
            parrafo_id=parrafo_id,
            frase_id=frase_id,
            texto=frase,
            tono_base=tono_frase,
            velocidad=velocidad,
            curva=curva,
            pausa_final=pausa_final,
            enfasis_palabras=palabras_enfasis,
            modificadores_especiales=modificadores
        )

        # Aplicar tonos inicial/final si están definidos
        if 'tono_inicial' in modificadores:
            params.tono_inicial = modificadores['tono_inicial']
        if 'tono_final' in modificadores:
            params.tono_final = modificadores['tono_final']
        if 'intensidad' in modificadores:
            params.intensidad = modificadores['intensidad']

        return params

    def _analizar_tipo_frase(self, frase: str) -> str:
        """Detecta el tipo de frase basándose en patrones sintácticos"""
        frase_clean = frase.strip()

        if '?' in frase_clean or frase_clean.startswith('¿'):
            return 'pregunta'
        elif '!' in frase_clean or frase_clean.startswith('¡'):
            return 'exclamacion'
        elif len(frase_clean) > 150 and ('que' in frase_clean.lower() or 'donde' in frase_clean.lower()):
            return 'subordinada_larga'
        elif frase_clean.count(',') >= 2 and any(word in frase_clean.lower() for word in ['y', 'o', 'además']):
            return 'enumeracion'
        elif '"' in frase_clean or "'" in frase_clean:
            return 'cita'
        else:
            return 'declarativa'

    def _detectar_palabras_importantes(self, frase: str) -> Dict[str, Dict]:
        """Detecta palabras que requieren énfasis especial"""
        enfasis_dict = {}
        texto_lower = frase.lower()

        for categoria, palabras in self.configuracion['palabras_enfasis'].items():
            for palabra in palabras:
                if palabra in texto_lower:
                    enfasis_dict[palabra] = {
                        'tono_boost': 0.08,      # +8%
                        'duracion_boost': 0.15,  # +15%
                        'pausa_antes': 0.1,      # 100ms
                        'categoria': categoria
                    }

        return enfasis_dict

    def _calcular_pausa_transicion(self, frase: str, frase_id: int, total_frases: int,
                                 todas_frases: List[str], es_ultimo_parrafo: bool = False) -> float:
        """
        Calcula la pausa apropiada después de una frase
        Incluye pausas especiales para separación entre párrafos
        """
        # Pausa base según puntuación
        if frase.strip().endswith('.'):
            pausa_base = 0.8
        elif frase.strip().endswith('!'):
            pausa_base = 0.6
        elif frase.strip().endswith('?'):
            pausa_base = 0.5
        elif frase.strip().endswith(','):
            pausa_base = 0.3
        else:
            pausa_base = 0.5

        # NUEVO: Pausas diferenciadas para finales de párrafo
        if frase_id == total_frases - 1:  # Última frase del párrafo
            if es_ultimo_parrafo:
                # Final del documento: pausa más larga para cierre definitivo
                pausa_base *= 2.0  # Pausa de cierre definitivo
            else:
                # Final de párrafo intermedio: pausa moderada para separar párrafos
                pausa_base *= 1.8  # Un poco más de pausa entre párrafos

        # Modificar según transición semántica (solo dentro del párrafo)
        elif frase_id < total_frases - 1:
            siguiente_frase = todas_frases[frase_id + 1]
            transicion = self._detectar_tipo_transicion(frase, siguiente_frase)

            if transicion == 'contraste':
                pausa_base *= 1.3  # Pausa para contraste dentro del párrafo
            elif transicion == 'continuidad':
                pausa_base *= 0.8  # Menor pausa para continuidad
            elif transicion == 'conclusion_parcial':
                pausa_base *= 1.1  # Pausa moderada para conclusión parcial

        # Limitar pausas extremas
        return min(max(pausa_base, 0.2), 3.0)  # Entre 0.2s y 3.0s máximo

    def _detectar_tipo_transicion(self, frase_actual: str, frase_siguiente: str) -> str:
        """Detecta el tipo de transición entre dos frases"""
        actual_lower = frase_actual.lower()
        siguiente_lower = frase_siguiente.lower()

        # Indicadores de contraste
        if any(ind in siguiente_lower for ind in ['sin embargo', 'pero', 'no obstante', 'aunque']):
            return 'contraste'

        # Indicadores de continuidad
        if any(ind in siguiente_lower for ind in ['además', 'también', 'asimismo', 'igualmente']):
            return 'continuidad'

        # Indicadores de conclusión parcial
        if any(ind in actual_lower for ind in ['por tanto', 'así pues', 'en resumen']):
            return 'conclusion_parcial'

        return 'normal'

    def _aplicar_suavizado_transiciones(self, control_matrix: List[ProsodyParams]) -> List[ProsodyParams]:
        """Aplica suavizado tipo Bézier para transiciones naturales entre frases"""
        if len(control_matrix) < 2:
            return control_matrix

        # Suavizar transiciones tonales bruscas
        for i in range(1, len(control_matrix)):
            actual = control_matrix[i]
            anterior = control_matrix[i - 1]

            # Calcular diferencia tonal
            diff_tonal = abs(actual.tono_base - anterior.tono_base)
            umbral_suavizado = self.f0_base * 0.1  # 10% de la frecuencia base

            if diff_tonal > umbral_suavizado:
                # Aplicar suavizado
                factor_suavizado = self.configuracion['arco_global']['transicion_suave']
                nuevo_tono = anterior.tono_base + (actual.tono_base - anterior.tono_base) * (1 - factor_suavizado)
                control_matrix[i].tono_base = nuevo_tono

        return control_matrix

    def _verificar_coherencia_tonal(self, control_matrix: List[ProsodyParams]) -> List[ProsodyParams]:
        """Verifica y corrige la coherencia tonal global"""
        if not control_matrix:
            return control_matrix

        # Verificar que no haya saltos extremos
        for i in range(len(control_matrix)):
            # Limitar tonos extremos
            tono_min = self.f0_base * 0.75  # -25%
            tono_max = self.f0_base * 1.35  # +35%

            if control_matrix[i].tono_base < tono_min:
                control_matrix[i].tono_base = tono_min
            elif control_matrix[i].tono_base > tono_max:
                control_matrix[i].tono_base = tono_max

            # Verificar velocidades extremas
            vel_min = self.velocidad_natural * 0.75  # -25%
            vel_max = self.velocidad_natural * 1.25  # +25%

            if control_matrix[i].velocidad < vel_min:
                control_matrix[i].velocidad = vel_min
            elif control_matrix[i].velocidad > vel_max:
                control_matrix[i].velocidad = vel_max

        return control_matrix

    def generar_parametros_f5tts(self, control_matrix: List[ProsodyParams]) -> List[Dict]:
        """
        Convierte la matriz de control en parámetros específicos para F5-TTS
        """
        parametros_f5 = []

        for params in control_matrix:
            # Convertir a parámetros F5-TTS
            f5_params = {
                'text': params.texto,
                'speed': params.velocidad / self.velocidad_natural,  # Factor relativo
                'nfe_step': self._calcular_nfe_steps(params),
                'sway_sampling_coef': self._calcular_sway_coef(params),
                'cfg_strength': self._calcular_cfg_strength(params),
                'pitch_adjustment': params.tono_base / self.f0_base,  # Factor relativo
                'pause_after': params.pausa_final
            }

            # Añadir modificadores especiales
            if params.modificadores_especiales:
                f5_params.update(params.modificadores_especiales)

            parametros_f5.append(f5_params)

        return parametros_f5

    def _calcular_nfe_steps(self, params: ProsodyParams) -> int:
        """Calcula NFE steps según la complejidad prosódica de la frase"""
        base_nfe = 32

        # Más steps para frases complejas
        if params.enfasis_palabras:
            base_nfe += len(params.enfasis_palabras) * 2

        # Más steps para curvas especiales
        if params.curva in ['ascendente_final', 'cadencia']:
            base_nfe += 8

        return min(base_nfe, 64)  # Máximo 64

    def _calcular_sway_coef(self, params: ProsodyParams) -> float:
        """Calcula sway coefficient según el tipo de curva"""
        base_sway = -0.5

        if params.curva == 'ataque':
            return base_sway - 0.1  # Más negativo para ataques
        elif params.curva == 'cadencia':
            return base_sway + 0.1  # Menos negativo para cadencias

        return base_sway

    def _calcular_cfg_strength(self, params: ProsodyParams) -> float:
        """Calcula CFG strength según la intensidad requerida"""
        base_cfg = 2.0

        if params.intensidad > 1.2:
            return base_cfg + 0.3
        elif params.intensidad < 0.9:
            return base_cfg - 0.2

        return base_cfg

    def exportar_reporte_arquitectura(self, control_matrix: List[ProsodyParams],
                                    output_path: str) -> None:
        """Exporta un reporte detallado de la arquitectura vocal aplicada"""
        import json
        from datetime import datetime

        reporte = {
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'algoritmo': 'Arquitectura Vocal Maestro N-Paragrafos M-Frases',
            'configuracion_base': {
                'f0_base': self.f0_base,
                'velocidad_natural': self.velocidad_natural,
                'idioma': self.idioma
            },
            'estadisticas': {
                'total_parrafos': len(set(p.parrafo_id for p in control_matrix)),
                'total_frases': len(control_matrix),
                'frases_por_parrafo': {},
                'tipos_frase': {},
                'palabras_enfasis_total': sum(len(p.enfasis_palabras) for p in control_matrix)
            },
            'parametros_detallados': []
        }

        # Estadísticas por párrafo
        for params in control_matrix:
            pid = params.parrafo_id
            if pid not in reporte['estadisticas']['frases_por_parrafo']:
                reporte['estadisticas']['frases_por_parrafo'][pid] = 0
            reporte['estadisticas']['frases_por_parrafo'][pid] += 1

        # Detalles de cada frase
        for params in control_matrix:
            reporte['parametros_detallados'].append({
                'parrafo': params.parrafo_id,
                'frase': params.frase_id,
                'texto': params.texto[:100] + '...' if len(params.texto) > 100 else params.texto,
                'tono_base_hz': round(params.tono_base, 1),
                'velocidad_ppm': round(params.velocidad, 1),
                'curva': params.curva,
                'pausa_final': round(params.pausa_final, 2),
                'enfasis_palabras': len(params.enfasis_palabras),
                'modificadores': bool(params.modificadores_especiales)
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)

        logger.info(f"📊 Reporte de arquitectura vocal exportado: {output_path}")


# FUNCIÓN PRINCIPAL DE INTEGRACIÓN
def aplicar_arquitectura_vocal_maestra(texto: str,
                                     f0_base: float = 185.0,
                                     velocidad_natural: float = 145.0) -> Tuple[List[ProsodyParams], List[Dict]]:
    """
    Función principal para aplicar arquitectura vocal maestra

    Args:
        texto: Texto completo a procesar
        f0_base: Frecuencia fundamental base
        velocidad_natural: Velocidad base en PPM

    Returns:
        Tuple de (parámetros prosódicos detallados, parámetros F5-TTS)
    """

    # Crear orquestador maestro
    orquestador = ArquitecturaVocalMaestra(f0_base, velocidad_natural)

    # Generar matriz de control prosódico
    control_matrix = orquestador.orquestar_lectura_completa(texto)

    # Convertir a parámetros F5-TTS
    parametros_f5 = orquestador.generar_parametros_f5tts(control_matrix)

    return control_matrix, parametros_f5


if __name__ == "__main__":
    # Ejemplo de uso
    texto_ejemplo = """
    La inteligencia artificial representa una revolución tecnológica sin precedentes.
    Sus aplicaciones abarcan desde la medicina hasta la exploración espacial.

    Sin embargo, esta tecnología también plantea desafíos éticos fundamentales.
    ¿Cómo podemos asegurar que su desarrollo beneficie a toda la humanidad?
    La respuesta requiere un enfoque multidisciplinario y colaborativo.

    En conclusión, el futuro de la IA depende de las decisiones que tomemos hoy.
    Debemos actuar con sabiduría y responsabilidad para construir un mundo mejor.
    """

    print("🎭 ORQUESTADOR MAESTRO DE ARQUITECTURA VOCAL")
    print("=" * 60)

    # Aplicar arquitectura vocal
    control_matrix, parametros_f5 = aplicar_arquitectura_vocal_maestra(texto_ejemplo)

    print(f"\n✅ Procesamiento completado:")
    print(f"   📊 {len(control_matrix)} frases procesadas")
    print(f"   🎵 Arquitectura vocal aplicada")
    print(f"   ⚙️ Parámetros F5-TTS generados")

    # Mostrar ejemplo de parámetros generados
    print(f"\n📝 Ejemplo de parámetros generados:")
    for i, params in enumerate(control_matrix[:3]):
        print(f"   Frase {i+1}: {params.texto[:50]}...")
        print(f"     Tono: {params.tono_base:.1f}Hz, Velocidad: {params.velocidad:.1f}PPM")
        print(f"     Curva: {params.curva}, Pausa: {params.pausa_final:.2f}s")