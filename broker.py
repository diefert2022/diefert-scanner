# ============================================================
#  broker.py — Detección y traducción de broker
#
#  Módulo independiente para evitar imports circulares.
#  Todos los módulos (utils, resistencias, zonas_manual, etc.)
#  importan nombre_real() desde aquí, no desde main_v4.
# ============================================================

CUENTAS_BRIDGE = {
    899795,     # cuenta Bridge Markets (detectada 25 may 2026)
}

SERVIDORES_BRIDGE = {"bridgemarkets", "bridge markets", "bridge"}

EQUIVALENCIAS = {
    "weltrade": {
        "GainX 400":   "GainX 400",
        "GainX 600":   "GainX 600",
        "GainX 800":   "GainX 800",
        "GainX 999":   "GainX 999",
        "GainX 1200":  "GainX 1200",
        "PainX 400":   "PainX 400",
        "PainX 600":   "PainX 600",
        "PainX 800":   "PainX 800",
        "PainX 999":   "PainX 999",
        "PainX 1200":  "PainX 1200",
    },
    "bridge": {
        "GainX 400":   "StepDrop400.",
        "GainX 600":   "StepDrop600.",
        "GainX 800":   "StepDrop800.",
        "GainX 999":   "StepDrop999.",
        "GainX 1200":  "StepDrop1200.",
        "PainX 400":   "StepRise400.",
        "PainX 600":   "StepRise600.",
        "PainX 800":   "StepRise800.",
        "PainX 999":   "StepRise999.",
        "PainX 1200":  "StepRise1200.",
        "B 1000 Idx.": "B 1000 Idx.",
    }
}

# Variable global — se actualiza en detectar_y_configurar()
BROKER_ACTIVO = "weltrade"


def detectar_y_configurar(mt5):
    """
    Llama a MT5 para detectar el broker activo.
    Debe llamarse DESPUÉS de mt5.initialize().
    """
    global BROKER_ACTIVO
    try:
        info = mt5.account_info()
        if info is None:
            BROKER_ACTIVO = "weltrade"
            return "weltrade"
        if info.login in CUENTAS_BRIDGE:
            BROKER_ACTIVO = "bridge"
            return "bridge"
        servidor = info.server.lower()
        if any(s in servidor for s in SERVIDORES_BRIDGE):
            BROKER_ACTIVO = "bridge"
            return "bridge"
        BROKER_ACTIVO = "weltrade"
        return "weltrade"
    except Exception:
        BROKER_ACTIVO = "weltrade"
        return "weltrade"


def nombre_real(simbolo):
    """
    Convierte nombre interno (GainX 600) al nombre del broker activo.
    Weltrade → sin cambio. Bridge → StepDrop600. etc.
    """
    return EQUIVALENCIAS.get(BROKER_ACTIVO, {}).get(simbolo, simbolo)
