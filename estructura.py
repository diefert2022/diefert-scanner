# ============================================================
#  EMASCALPD SCANNER v2.1 — estructura.py
#
#  Detecta tendencia y estructura del mercado
#  Jerarquía: H1 → M15 → M5
#
#  NOVEDAD v2.1 — BOS ESTRUCTURAL REAL:
#  ─────────────────────────────────────
#  El BOS anterior comparaba el precio con el mínimo/máximo
#  de las últimas N velas. Eso NO es BOS estructural.
#
#  Un BOS estructural real requiere:
#  1. Swing previo válido formado con ventana de al menos 3 velas
#  2. El precio cierra MÁS ALLÁ de ese swing específico
#  3. El swing debe ser el ÚLTIMO swing de la secuencia
#     (no cualquier máximo/mínimo reciente)
#  4. La vela que rompe debe tener rango mínimo significativo
#
#  Diferencia clave:
#  ANTES: "¿el precio bajó más que en las últimas 20 velas?"
#  AHORA: "¿el precio rompió el último swing low estructural?"
#
#  CONCEPTOS:
#  ────────────────────────────────────────────────────────
#  Swing High (SH): vela cuyo high supera las N velas a cada lado
#  Swing Low  (SL): vela cuyo low  es menor que las N velas a cada lado
#
#  Tendencia alcista: secuencia HH (Higher High) + HL (Higher Low)
#  Tendencia bajista: secuencia LH (Lower High)  + LL (Lower Low)
#
#  BOS:   precio rompe en la MISMA dirección de la tendencia
#         → continuación confirmada
#
#  CHoCH: precio rompe en CONTRA de la tendencia (primer aviso)
#         → posible cambio de dirección
#
#  BOS estructural válido:
#         → rompe el ÚLTIMO swing de la secuencia
#         → vela de rotura con rango > MIN_RANGO_BOS pts
#         → cierre confirmado más allá del swing (no solo mecha)
# ============================================================

from config import TF_H1, TF_M15, TF_M5, VELAS_H1, VELAS_M15, VELAS_M5
from utils import obtener_df

# Rango mínimo de la vela que rompe el swing para ser BOS válido
MIN_RANGO_BOS = 8   # puntos — filtra microroturas falsas


# ── DETECCIÓN DE SWINGS ───────────────────────────────────

def detectar_swings(df, ventana=5):
    """
    Detecta swing highs y swing lows en un dataframe.

    Swing High: vela cuyo high supera las 'ventana' velas a cada lado.
    Swing Low:  vela cuyo low  es menor que las 'ventana' velas a cada lado.

    ventana recomendada por timeframe:
      H1  → 5  (swings más significativos)
      M15 → 4
      M5  → 3
      M1  → 2

    Retorna lista de swings ordenados por índice:
      [{"tipo": "SH"/"SL", "precio": float, "idx": int}, ...]
    """
    swings = []
    n      = len(df)

    for i in range(ventana, n - ventana):
        high_i = df.iloc[i]['high']
        low_i  = df.iloc[i]['low']

        es_sh = all(
            df.iloc[j]['high'] <= high_i
            for j in range(i - ventana, i + ventana + 1) if j != i
        )
        es_sl = all(
            df.iloc[j]['low'] >= low_i
            for j in range(i - ventana, i + ventana + 1) if j != i
        )

        if es_sh:
            swings.append({"tipo": "SH", "precio": round(high_i, 2), "idx": i})
        if es_sl:
            swings.append({"tipo": "SL", "precio": round(low_i,  2), "idx": i})

    swings.sort(key=lambda x: x["idx"])
    return swings


# ── DETECCIÓN DE TENDENCIA ────────────────────────────────

def detectar_tendencia(swings):
    """
    Determina la tendencia a partir de los swings.

    Alcista: HH (Higher High) + HL (Higher Low)
    Bajista: LH (Lower High)  + LL (Lower Low)
    Neutro:  sin patrón claro

    Usa los últimos 6 swings para evaluar.
    """
    if len(swings) < 4:
        return "neutro"

    recientes = swings[-6:]
    highs = [s["precio"] for s in recientes if s["tipo"] == "SH"]
    lows  = [s["precio"] for s in recientes if s["tipo"] == "SL"]

    if len(highs) < 2 or len(lows) < 2:
        return "neutro"

    hh = highs[-1] > highs[-2]
    hl = lows[-1]  > lows[-2]
    lh = highs[-1] < highs[-2]
    ll = lows[-1]  < lows[-2]

    if hh and hl:
        return "alcista"
    elif lh and ll:
        return "bajista"
    else:
        return "neutro"


# ── BOS ESTRUCTURAL REAL ──────────────────────────────────

def detectar_bos_estructural(df, swings, es_bajista):
    """
    NUEVO v2.1 — Detecta BOS estructural real.

    A diferencia del BOS anterior (que comparaba con N velas),
    este busca si el precio rompió el ÚLTIMO swing válido
    de la secuencia estructural.

    BAJISTA — busca rotura del último SL:
      El precio cierra por DEBAJO del último Swing Low
      → estructura bajista continúa o se confirma

    ALCISTA — busca rotura del último SH:
      El precio cierra por ENCIMA del último Swing High
      → estructura alcista continúa o se confirma

    La vela de rotura debe:
      - Tener rango > MIN_RANGO_BOS (no microrotura)
      - Cerrar más allá del swing (no solo mecha)

    Retorna dict con:
      detectado:   True/False
      idx:         índice de la vela que rompió
      nivel:       precio del swing roto
      tipo_swing:  "SL" o "SH"
      rango_vela:  tamaño de la vela de rotura en puntos
    """
    if not swings or df is None:
        return {"detectado": False, "idx": -1, "nivel": None,
                "tipo_swing": None, "rango_vela": 0}

    if es_bajista:
        # Buscar el último SL estructural
        ultimo_sl = next((s for s in reversed(swings) if s["tipo"] == "SL"), None)
        if ultimo_sl is None:
            return {"detectado": False, "idx": -1, "nivel": None,
                    "tipo_swing": "SL", "rango_vela": 0}

        nivel = ultimo_sl["precio"]

        # Buscar la primera vela que cierra por debajo del SL
        for i in range(ultimo_sl["idx"] + 1, len(df)):
            v          = df.iloc[i]
            rango_vela = v['high'] - v['low']

            if rango_vela < MIN_RANGO_BOS:
                continue   # microrotura — ignorar

            if v['close'] < nivel:
                return {
                    "detectado":  True,
                    "idx":        i,
                    "nivel":      nivel,
                    "tipo_swing": "SL",
                    "rango_vela": round(rango_vela, 2),
                }

    else:
        # Buscar el último SH estructural
        ultimo_sh = next((s for s in reversed(swings) if s["tipo"] == "SH"), None)
        if ultimo_sh is None:
            return {"detectado": False, "idx": -1, "nivel": None,
                    "tipo_swing": "SH", "rango_vela": 0}

        nivel = ultimo_sh["precio"]

        # Buscar la primera vela que cierra por encima del SH
        for i in range(ultimo_sh["idx"] + 1, len(df)):
            v          = df.iloc[i]
            rango_vela = v['high'] - v['low']

            if rango_vela < MIN_RANGO_BOS:
                continue

            if v['close'] > nivel:
                return {
                    "detectado":  True,
                    "idx":        i,
                    "nivel":      nivel,
                    "tipo_swing": "SH",
                    "rango_vela": round(rango_vela, 2),
                }

    return {"detectado": False, "idx": -1, "nivel": None,
            "tipo_swing": None, "rango_vela": 0}


# ── BOS / CHoCH (función original — usada por ema_strategy) ──

def detectar_bos_choch(df, swings, tendencia):
    """
    Detecta el BOS o CHoCH más reciente.

    BOS   = precio rompe en la MISMA dirección de la tendencia
    CHoCH = precio rompe en CONTRA de la tendencia

    Retorna dict con:
      tipo:      "BOS" o "CHoCH"
      direccion: "alcista" o "bajista"
      nivel:     precio donde ocurrió la rotura
      idx:       índice de la vela que rompió
    """
    if not swings or df is None:
        return None

    ultimo_sh = next((s for s in reversed(swings) if s["tipo"] == "SH"), None)
    ultimo_sl = next((s for s in reversed(swings) if s["tipo"] == "SL"), None)

    resultado = None

    # Rotura del último SH → BOS/CHoCH alcista
    if ultimo_sh:
        for i in range(ultimo_sh["idx"] + 1, len(df)):
            v          = df.iloc[i]
            rango_vela = v['high'] - v['low']
            if rango_vela < MIN_RANGO_BOS:
                continue
            if v['close'] > ultimo_sh["precio"]:
                tipo = "BOS" if tendencia == "alcista" else "CHoCH"
                resultado = {
                    "tipo":      tipo,
                    "direccion": "alcista",
                    "nivel":     ultimo_sh["precio"],
                    "idx":       i,
                }
                break

    # Rotura del último SL → BOS/CHoCH bajista
    if ultimo_sl:
        for i in range(ultimo_sl["idx"] + 1, len(df)):
            v          = df.iloc[i]
            rango_vela = v['high'] - v['low']
            if rango_vela < MIN_RANGO_BOS:
                continue
            if v['close'] < ultimo_sl["precio"]:
                tipo = "BOS" if tendencia == "bajista" else "CHoCH"
                if resultado is None or tipo == "CHoCH":
                    resultado = {
                        "tipo":      tipo,
                        "direccion": "bajista",
                        "nivel":     ultimo_sl["precio"],
                        "idx":       i,
                    }
                break

    return resultado


# ── ANÁLISIS COMPLETO ─────────────────────────────────────

def analizar_estructura(simbolo):
    """
    Analiza la estructura completa del mercado para un símbolo.
    Jerarquía H1 → M15 → M5.

    Retorna dict con:
      tendencia_h1/m15/m5:   alcista / bajista / neutro
      bos_choch_h1/m15/m5:   último BOS o CHoCH detectado
      bos_estructural_h1/m15/m5: BOS estructural real (NUEVO v2.1)
      swings_h1/m15/m5:      lista de swings
      precio:                precio actual
    """
    resultado = {
        "tendencia_h1":          "neutro",
        "tendencia_m15":         "neutro",
        "tendencia_m5":          "neutro",
        "bos_choch_h1":          None,
        "bos_choch_m15":         None,
        "bos_choch_m5":          None,
        "bos_estructural_h1":    None,   # NUEVO
        "bos_estructural_m15":   None,   # NUEVO
        "bos_estructural_m5":    None,   # NUEVO
        "swings_h1":             [],
        "swings_m15":            [],
        "swings_m5":             [],
        "precio":                None,
    }

    # ── H1 ────────────────────────────────────────────────
    df_h1 = obtener_df(simbolo, TF_H1, VELAS_H1)
    if df_h1 is not None and len(df_h1) >= 20:
        resultado["precio"]       = round(df_h1['close'].iloc[-1], 2)
        swings_h1                 = detectar_swings(df_h1, ventana=5)
        tendencia_h1              = detectar_tendencia(swings_h1)
        resultado["swings_h1"]    = swings_h1
        resultado["tendencia_h1"] = tendencia_h1
        resultado["bos_choch_h1"] = detectar_bos_choch(df_h1, swings_h1, tendencia_h1)

        # BOS estructural H1 — es_bajista según tendencia
        es_baj_h1 = tendencia_h1 == "bajista"
        resultado["bos_estructural_h1"] = detectar_bos_estructural(
            df_h1, swings_h1, es_baj_h1
        )

    # ── M15 ───────────────────────────────────────────────
    df_m15 = obtener_df(simbolo, TF_M15, VELAS_M15)
    if df_m15 is not None and len(df_m15) >= 20:
        swings_m15                 = detectar_swings(df_m15, ventana=4)
        tendencia_m15              = detectar_tendencia(swings_m15)
        resultado["swings_m15"]    = swings_m15
        resultado["tendencia_m15"] = tendencia_m15
        resultado["bos_choch_m15"] = detectar_bos_choch(df_m15, swings_m15, tendencia_m15)

        es_baj_m15 = tendencia_m15 == "bajista"
        resultado["bos_estructural_m15"] = detectar_bos_estructural(
            df_m15, swings_m15, es_baj_m15
        )

    # ── M5 ────────────────────────────────────────────────
    df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
    if df_m5 is not None and len(df_m5) >= 20:
        swings_m5                 = detectar_swings(df_m5, ventana=3)
        tendencia_m5              = detectar_tendencia(swings_m5)
        resultado["swings_m5"]    = swings_m5
        resultado["tendencia_m5"] = tendencia_m5
        resultado["bos_choch_m5"] = detectar_bos_choch(df_m5, swings_m5, tendencia_m5)

        es_baj_m5 = tendencia_m5 == "bajista"
        resultado["bos_estructural_m5"] = detectar_bos_estructural(
            df_m5, swings_m5, es_baj_m5
        )

    return resultado
