#!/usr/bin/env python3
"""
====================================================================================================
DIALECTOS DEL ESPAÑOL - REGLAS FONÉTICAS POR REGIÓN
====================================================================================================

Descripción:
    Define las reglas de transformación fonética específicas para diferentes dialectos
    del español, permitiendo simular variaciones regionales en la pronunciación.

Dialectos Incluidos:
    - Castilla-La Mancha (Toledano): Sin seseo, con distinción z/s
    - Andaluz: Seseo, aspiración de s final, pérdida de d intervocálica
    - Rioplatense (Argentina/Uruguay): Yeísmo rehilado (ll/y → sh/zh)
    - Caribeño: Aspiración/pérdida de s final, debilitamiento consonántico
    - Mexicano: Conservador, mantiene distinciones fonéticas
    - Canario: Similar al caribeño con influencias andaluzas

Autor: Sistema de transformación fonética dialectal
Versión: 1.0
====================================================================================================
"""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class DialectConfig:
    """
    Configuración de un dialecto del español.

    Attributes:
        id (str): Identificador único del dialecto
        name (str): Nombre descriptivo del dialecto
        description (str): Descripción breve de las características
        rules (List[Dict]): Lista de reglas fonéticas específicas
    """
    id: str
    name: str
    description: str
    rules: List[Dict]


# ====================================================================================================
# DEFINICIÓN DE DIALECTOS
# ====================================================================================================

SPANISH_DIALECTS = {

    # ================================================================================================
    # CASTILLA-LA MANCHA (TOLEDANO)
    # ================================================================================================
    "castilla": {
        "id": "castilla",
        "name": "Castilla-La Mancha (Toledano)",
        "description": "Español de Castilla-La Mancha. Mantiene distinción z/s/c. Yeísmo moderado.",
        "rules": [
            # H muda - prioridad alta
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # Betacismo (b/v)
            {"pattern": r'mb', "replacement": 'mb', "priority": 8},
            {"pattern": r'nv', "replacement": 'nb', "priority": 8},
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # G/J ante e,i
            {"pattern": r'g([ei])', "replacement": r'j\1', "priority": 6},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},

            # X inicial → S
            {"pattern": r'\bx', "replacement": 's', "priority": 4},

            # CC → C
            {"pattern": r'cc', "replacement": 'c', "priority": 3},

            # Relajación -ado/-ada
            {"pattern": r'ado\b', "replacement": 'ao', "priority": 3},
            {"pattern": r'ada\b', "replacement": 'á', "priority": 3},
        ]
    },

    # ================================================================================================
    # ANDALUZ
    # ================================================================================================
    "andaluz": {
        "id": "andaluz",
        "name": "Andaluz",
        "description": "Español andaluz. Seseo, aspiración de s final, pérdida de consonantes.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # SESEO (característica principal andaluza)
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Aspiración de S final (s → h o pérdida)
            {"pattern": r's\b', "replacement": 'h', "priority": 7},
            {"pattern": r's([^aeiou])', "replacement": r'h\1', "priority": 7},

            # Pérdida de D intervocálica (muy característico)
            {"pattern": r'([aeiou])d([aeiou])', "replacement": r'\1\2', "priority": 7},

            # Pérdida de D final
            {"pattern": r'd\b', "replacement": '', "priority": 6},

            # Betacismo
            {"pattern": r'mb', "replacement": 'mb', "priority": 8},
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # L final → R (neutralización líquidas)
            {"pattern": r'l\b', "replacement": 'r', "priority": 5},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},

            # Pérdida de R final en infinitivos
            {"pattern": r'r\b', "replacement": '', "priority": 3},
        ]
    },

    # ================================================================================================
    # RIOPLATENSE (ARGENTINA/URUGUAY)
    # ================================================================================================
    "rioplatense": {
        "id": "rioplatense",
        "name": "Rioplatense (Argentina/Uruguay)",
        "description": "Español rioplatense. Yeísmo rehilado (ll/y → sh), entonación italiana.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # YEÍSMO REHILADO (característico rioplatense)
            # ll/y → sh/zh (representado como 'sh')
            {"pattern": r'll', "replacement": 'sh', "priority": 10},
            {"pattern": r'y([aeiou])', "replacement": r'sh\1', "priority": 10},
            {"pattern": r'\by', "replacement": 'sh', "priority": 10},

            # Seseo (común en Argentina)
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Betacismo
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Aspiración de S final (en algunas regiones)
            {"pattern": r's\b', "replacement": 'h', "priority": 5},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},

            # Voseo (cambios en conjugación, no fonéticos pero característicos)
            # Este es más morfológico que fonético
        ]
    },

    # ================================================================================================
    # CARIBEÑO (CUBA, PUERTO RICO, REP. DOMINICANA, VENEZUELA, COLOMBIA CARIBE)
    # ================================================================================================
    "caribeno": {
        "id": "caribeno",
        "name": "Caribeño",
        "description": "Español caribeño. Aspiración/pérdida de s, debilitamiento consonántico.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # ASPIRACIÓN/PÉRDIDA DE S (muy característico)
            {"pattern": r's\b', "replacement": '', "priority": 9},  # pérdida completa
            {"pattern": r's([^aeiou])', "replacement": r'h\1', "priority": 8},  # aspiración

            # Seseo total
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Pérdida/debilitamiento de D intervocálica
            {"pattern": r'([aeiou])d([aeiou])', "replacement": r'\1\2', "priority": 8},
            {"pattern": r'd\b', "replacement": '', "priority": 7},

            # Neutralización R/L final
            {"pattern": r'r\b', "replacement": 'l', "priority": 6},
            {"pattern": r'l\b', "replacement": 'r', "priority": 6},

            # Betacismo
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # Pérdida de N final (nasalización vocálica)
            {"pattern": r'n\b', "replacement": '', "priority": 5},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},
        ]
    },

    # ================================================================================================
    # MEXICANO
    # ================================================================================================
    "mexicano": {
        "id": "mexicano",
        "name": "Mexicano (Centro)",
        "description": "Español mexicano central. Conservador, mantiene distinciones.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # Seseo (mayoritario en México)
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Betacismo (menos marcado)
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo (común en México)
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},

            # El mexicano es relativamente conservador
            # Mantiene S final, consonantes finales, etc.
        ]
    },

    # ================================================================================================
    # CANARIO
    # ================================================================================================
    "canario": {
        "id": "canario",
        "name": "Canario",
        "description": "Español canario. Similar al caribeño con influencias andaluzas.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # Seseo
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Aspiración de S (moderada)
            {"pattern": r's\b', "replacement": 'h', "priority": 7},
            {"pattern": r's([^aeiou])', "replacement": r'h\1', "priority": 6},

            # Pérdida de D intervocálica
            {"pattern": r'([aeiou])d([aeiou])', "replacement": r'\1\2', "priority": 7},
            {"pattern": r'd\b', "replacement": '', "priority": 6},

            # Betacismo
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # Aspiración de J/G (suave)
            {"pattern": r'j', "replacement": 'h', "priority": 5},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},
        ]
    },

    # ================================================================================================
    # CHILENO
    # ================================================================================================
    "chileno": {
        "id": "chileno",
        "name": "Chileno",
        "description": "Español chileno. Aspiración de s, asibilación de r̄.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # Aspiración/pérdida de S final (muy marcado)
            {"pattern": r's\b', "replacement": 'h', "priority": 9},
            {"pattern": r's([^aeiou])', "replacement": r'h\1', "priority": 8},

            # Seseo
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Pérdida de D intervocálica
            {"pattern": r'([aeiou])d([aeiou])', "replacement": r'\1\2', "priority": 7},

            # Betacismo
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},
        ]
    },

    # ================================================================================================
    # GALLEGO (Español con influencia gallega)
    # ================================================================================================
    "gallego": {
        "id": "gallego",
        "name": "Gallego",
        "description": "Español de Galicia. Gheada, seseo, conservación de -n final, entonación característica.",
        "rules": [
            # H muda (el gallego no tiene H aspirada en español)
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # GHEADA (característica distintiva gallega: g suave → h/x)
            # g/gu antes de e,i → j/x (más suave)
            {"pattern": r'g([ei])', "replacement": r'j\1', "priority": 10},
            {"pattern": r'gu([ei])', "replacement": r'j\1', "priority": 10},

            # Seseo (muy extendido en Galicia)
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 8},
            {"pattern": r'ce', "replacement": 'se', "priority": 8},
            {"pattern": r'ci', "replacement": 'si', "priority": 8},
            {"pattern": r'z\b', "replacement": 's', "priority": 8},

            # Conservación de consonantes finales (característica gallega)
            # No pérdida de -s final (a diferencia del andaluz)
            # No pérdida de -n final (mantiene nasales)

            # Betacismo moderado
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo (común en gallego-hablantes de español)
            {"pattern": r'll', "replacement": 'y', "priority": 7},

            # Tendencia a cerrar vocales finales (influencia gallega)
            # -o final puede sonar más cerrado
            # (difícil de representar en texto, se mantiene)

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},

            # Mantenimiento de grupos consonánticos (no simplificación)
            # El gallego es más conservador
        ]
    },

    # ================================================================================================
    # ANDALUZ DE GRANADA
    # ================================================================================================
    "granada": {
        "id": "granada",
        "name": "Andaluz de Granada",
        "description": "Español granadino. Seseo, aspiración moderada de s, pérdida de d intervocálica marcada.",
        "rules": [
            # H muda
            {"pattern": r'\bhab', "replacement": 'ab', "priority": 10},
            {"pattern": r'\bhac', "replacement": 'ac', "priority": 10},
            {"pattern": r'\bha([^s])', "replacement": r'a\1', "priority": 9},
            {"pattern": r'\bhe', "replacement": 'e', "priority": 9},
            {"pattern": r'\bhi', "replacement": 'i', "priority": 9},
            {"pattern": r'\bho', "replacement": 'o', "priority": 9},
            {"pattern": r'\bhu', "replacement": 'u', "priority": 9},

            # SESEO (total en Granada)
            {"pattern": r'z([aeiou])', "replacement": r's\1', "priority": 9},
            {"pattern": r'ce', "replacement": 'se', "priority": 9},
            {"pattern": r'ci', "replacement": 'si', "priority": 9},
            {"pattern": r'z\b', "replacement": 's', "priority": 9},

            # Aspiración de S (moderada, menos que en Cádiz o Sevilla)
            # S implosiva → h (antes de consonante y final)
            {"pattern": r's([ptkcfgxbdñlrmn])', "replacement": r'h\1', "priority": 8},
            {"pattern": r's\b', "replacement": 'h', "priority": 7},

            # PÉRDIDA DE D INTERVOCÁLICA (muy marcada en Granada)
            {"pattern": r'([aeiou])d([aeiou])', "replacement": r'\1\2', "priority": 9},

            # Pérdida de D final (participios, etc.)
            {"pattern": r'd\b', "replacement": '', "priority": 8},

            # Apertura de vocales en sílaba final (fenómeno granadino)
            # -ado → -ao con vocal abierta
            {"pattern": r'ado\b', "replacement": 'ao', "priority": 6},
            {"pattern": r'ada\b', "replacement": 'á', "priority": 6},
            {"pattern": r'idos\b', "replacement": 'íos', "priority": 6},

            # Betacismo
            {"pattern": r'mb', "replacement": 'mb', "priority": 8},
            {"pattern": r'nv', "replacement": 'nb', "priority": 8},
            {"pattern": r'\bv', "replacement": 'b', "priority": 7},
            {"pattern": r'([aeiou])v([aeiou])', "replacement": r'\1b\2', "priority": 6},

            # Yeísmo (universal en Granada)
            {"pattern": r'll', "replacement": 'y', "priority": 8},

            # Neutralización L/R final (presente pero menos que en costa)
            {"pattern": r'l\b', "replacement": 'r', "priority": 4},

            # Pérdida parcial de R final en infinitivos
            {"pattern": r'([aei])r\b', "replacement": r'\1', "priority": 3},

            # QU → K
            {"pattern": r'qu', "replacement": 'k', "priority": 4},

            # CC → C
            {"pattern": r'cc', "replacement": 'c', "priority": 3},
        ]
    },
}


def get_dialect(dialect_id: str) -> Dict:
    """
    Obtiene la configuración de un dialecto específico.

    Args:
        dialect_id: Identificador del dialecto

    Returns:
        Diccionario con la configuración del dialecto

    Raises:
        ValueError: Si el dialecto no existe
    """
    if dialect_id not in SPANISH_DIALECTS:
        available = ", ".join(SPANISH_DIALECTS.keys())
        raise ValueError(f"Dialecto '{dialect_id}' no encontrado. Disponibles: {available}")

    return SPANISH_DIALECTS[dialect_id]


def get_available_dialects() -> List[Dict[str, str]]:
    """
    Retorna lista de dialectos disponibles con su información.

    Returns:
        Lista de diccionarios con id, name y description de cada dialecto
    """
    return [
        {
            "id": config["id"],
            "name": config["name"],
            "description": config["description"]
        }
        for config in SPANISH_DIALECTS.values()
    ]


def get_dialect_names() -> List[str]:
    """
    Retorna lista de nombres de dialectos para uso en interfaces.

    Returns:
        Lista de nombres de dialectos
    """
    return [config["name"] for config in SPANISH_DIALECTS.values()]


def get_dialect_id_by_name(name: str) -> str:
    """
    Obtiene el ID de un dialecto a partir de su nombre.

    Args:
        name: Nombre del dialecto

    Returns:
        ID del dialecto

    Raises:
        ValueError: Si no se encuentra el dialecto
    """
    for config in SPANISH_DIALECTS.values():
        if config["name"] == name:
            return config["id"]

    raise ValueError(f"Dialecto con nombre '{name}' no encontrado")
