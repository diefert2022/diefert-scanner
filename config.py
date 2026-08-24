# ============================================================
#  DIEFERT SCANNER v4.10 — config.py
#
#  CAMBIOS v4.10 (09-ago-2026 — actualización automática):
#  ─────────────────────────────────────────────────────────
#  [~] Perfiles de los 10 índices recalibrados con datos
#      reales de MT5 (3 meses, generado por
#      actualizar_perfiles_indices.py). Se actualizaron:
#      sl_minimo, rango_diario, rango_m15, ob_h4_min,
#      ob_h1_min, fvg_bull_fuerte, fvg_bear_fuerte,
#      horas_activas_utc, rango_saturado.
#  [i] es_bajista NO se tocó — se mantiene la regla fija
#      (PainX=True/venta, GainX=False/compra) sin importar
#      el sesgo medido en las velas recientes.
#  [i] tol_h1, tol_h4, reac_avg_h1, ob_maestro_low/high NO
#      se recalculan con este script — quedan igual que antes.
#  RESUMEN NUEVO (ago 2026, P90 Daily / avg M15 / SL):
#  ─────────────────────────────────────────────────────────
#  PainX 400:    847   51   70
#  PainX 600:    839   50   70
#  PainX 800:    550   33   54
#  PainX 999:    866   48   75
#  PainX 1200:   432   25   44
#  GainX 400:    836   51   72
#  GainX 600:    808   50   71
#  GainX 800:    554   34   53
#  GainX 999:    787   47   73
#  GainX 1200:   464   25   45
#
#  CAMBIOS v4.8:
#  ─────────────────────────────────────────────────────────
#  [~] PainX 400: parámetros calibrados con datos CSV reales
#      ob_h4_min=217, ob_h1_min=110, fvg_bear_fuerte=48pts
#      horas_activas_utc, rango_saturado
#  [~] GainX 600: ob_h4_min=232, ob_h1_min=108
#      OB MAESTRO 110320-110420 confirmado (4 TFs confluencia)
#      ob_maestro_low/high, horas_activas_utc
#  [~] GainX 1200: ob_h1_min=120, rango_diario=900
#      ob_maestro_low/high=91088-91130 (OB+Fib78.6%)
#  NUEVA LLAVE: ob_h4_min, ob_h1_min, fvg_bull/bear_fuerte,
#               horas_activas_utc, rango_saturado,
#               ob_maestro_low/high
#
#  CAMBIOS v4.7:
#  ─────────────────────────────────────────────────────────
#  [+] GainX 600 agregado (bias alcista D+H4+H1 confirmado)
#      Zonas institucionales calculadas desde datos reales
#      9 timeframes analizados (Monthly → M1, mayo 2026)
#      Score de confluencia por zona (FVG+OB+Swing, máx 20)
#      SL=75pts | TOL_H1=120 | TOL_M15=38
#
#  CAMBIOS v4.6:
#  ─────────────────────────────────────────────────────────
#  [+] GainX 1200: usar_ob=True activado con evidencia real
#      Análisis 21 mayo 2026 — OB H1 alcista sin retestear
#      rebotó exactamente en la zona identificada.
#      Backtest histórico (proxy PainX 1200, 871 días):
#        OB H1 alcista:  83% rebote (340 casos visitados)
#        SwingLow H1:    53% rebote (1001 casos visitados)
#      → OBs son 30 puntos porcentuales más confiables.
#      SwingLow se mantiene activo como zona secundaria.
#
#  CAMBIOS v4.5 (anterior):
#  ─────────────────────────────────────────────────────────
#  [+] PainX 1200 agregado (Daily=330, SL=49, EMAs H4=35%)
#
#  CAMBIOS v4.4 → v4.3 → v4.2 → v4.1 (anteriores):
#  ─────────────────────────────────────────────────────────
#  [+] PainX 999  agregado (v4.4 — más volátil, Daily=607)
#  [+] PainX 800  agregado (v4.3 — más lento,   Daily=406)
#  [+] PainX 600  agregado (v4.2 — similar P400, Daily=592)
#  [+] GainX 400  agregado (v4.1 — espejo alcista PainX 400)
#
#  FAMILIA COMPLETA — PARÁMETROS CALIBRADOS (mayo 2026):
#  ─────────────────────────────────────────────────────────
#  Índice       Daily  M15  p90   SL   H1tol M15tol EMAs_H4  OB%
#  PainX 400:    577   51   78    74   150    40     28%      —
#  PainX 600:    592   50   78    75   120    38     27%      —
#  PainX 800:    406   33   54    59    86    36     11%      —
#  PainX 999:    607   48   80    85   122    53     20%      —
#  PainX 1200:   330   25   44    49    70    29     35%      —
#  GainX 400:    580   52   78    74   150    40     —        —
#  GainX 1200:   328   25   44    48   100    25     —       83%
# ============================================================

import MetaTrader5 as mt5

# ── TELEGRAM ──────────────────────────────────────────────
TOKEN   = "8973627102:AAFIOcavSw_Ag18_0jqsT9-AmDtTGhTEheQ"
CHAT_ID = "-1003933298024"

# ── SÍMBOLOS ACTIVOS ───────────────────────────────────────
SIMBOLOS = [
    "PainX 400",
    "PainX 600",    # v4.2 — bajista, similar a PainX 400
    "PainX 800",    # v4.3 — bajista, mueve ~30% menos
    "PainX 999",    # v4.4 — bajista, el más volátil
    "PainX 1200",   # v4.5 — bajista, mueve poco pero muy frecuente
    "GainX 400",
    "GainX 600",    # v4.7 — alcista, bias D+H4+H1 confirmado
    "GainX 800",    # v4.9 — bidireccional, rango 415pts, pre-Londres activo
    "GainX 999",    # v4.9 — bear puro, rango 611pts, FVG bull más grande familia
    "GainX 1200",
    # ── FlipX — solo para EmaScalpD (no afecta scanner principal) ──
    "FlipX 1", "FlipX 2", "FlipX 3", "FlipX 4", "FlipX 5",
]

# ── NATURALEZA DE CADA ÍNDICE ──────────────────────────────
SIMBOLOS_BAJISTAS = {"PainX 400", "PainX 600", "PainX 800", "PainX 999", "PainX 1200"}
SIMBOLOS_ALCISTAS = {"GainX 400", "GainX 600", "GainX 800", "GainX 999", "GainX 1200"}

# ── BIDIRECCIONALES (desactivados por ahora) ───────────────
SIMBOLOS_BIDIRECCIONALES = {
    "FlipX 1", "FlipX 2", "FlipX 3", "FlipX 4", "FlipX 5",
    "FX Vol 20", "FX Vol 40", "FX Vol 60", "FX Vol 80", "FX Vol 99",
}

# ── TIMEFRAMES ────────────────────────────────────────────
TF_M1  = mt5.TIMEFRAME_M1
TF_M5  = mt5.TIMEFRAME_M5
TF_M6  = mt5.TIMEFRAME_M6
TF_M10 = mt5.TIMEFRAME_M10
TF_M12 = mt5.TIMEFRAME_M12
TF_M15 = mt5.TIMEFRAME_M15
TF_M20 = mt5.TIMEFRAME_M20
TF_M30 = mt5.TIMEFRAME_M30
TF_H1  = mt5.TIMEFRAME_H1
TF_H4  = mt5.TIMEFRAME_H4

# ── VELAS POR TIMEFRAME ───────────────────────────────────
VELAS_H1  = 100
VELAS_H4  = 100
VELAS_M30 = 150
VELAS_M20 = 200
VELAS_M15 = 200
VELAS_M12 = 250
VELAS_M10 = 300
VELAS_M6  = 400
VELAS_M5  = 400
VELAS_M1  = 300

# ── TOLERANCIAS GENERALES ─────────────────────────────────
TOL_OB  = 25
TOL_FVG = 10
TOL_LIQ = 15

# ── CICLO ─────────────────────────────────────────────────
CICLO_SEG = 3

# ── COOLDOWN TELEGRAM ─────────────────────────────────────
COOLDOWN_SEG     = 300
COOLDOWN_EMA_SEG = 180

# ── SL MÍNIMO POR ÍNDICE ──────────────────────────────────
# Recalibrado 09-ago-2026: promedio cuerpo H1 (3 meses) + 10 buffer.
SL_MINIMO = {
    "PainX 400":  70,
    "PainX 600":  70,
    "PainX 800":  54,
    "PainX 999":  75,
    "PainX 1200": 44,
    "GainX 400":  72,
    "GainX 600":  71,
    "GainX 800":  53,
    "GainX 999":  73,
    "GainX 1200": 45,
}
SL_MINIMO_DEFAULT = 60

# ── TOLERANCIAS DE ZONA POR ÍNDICE ────────────────────────
# TOL_H1_CERCA = H1 rng avg + 10 pts buffer
# TOL_M15_ZONA = M15 p75
TOL_H1_CERCA = {
    "PainX 400":  150,
    "PainX 600":  120,
    "PainX 800":  86,
    "PainX 999":  122,
    "PainX 1200": 70,    # H1 avg=60 + 10 buffer (dato real)
    "GainX 400":  150,
    "GainX 600":  120,  # H1 avg similar a PainX 600
    "GainX 800":  86,   # H1 avg=76 + 10 buffer
    "GainX 999":  122,  # H1 avg=112 + 10 buffer
    "GainX 1200": 100,
}
TOL_M15_ZONA = {
    "PainX 400":  40,
    "PainX 600":  38,
    "PainX 800":  36,
    "PainX 999":  53,
    "PainX 1200": 29,    # M15 p75=29 (dato real)
    "GainX 400":  40,
    "GainX 600":  38,   # M15 p75 calibrado
    "GainX 1200": 25,
}
TOL_H1_CERCA_DEFAULT = 150
TOL_M15_ZONA_DEFAULT  = 40

# ── COMPORTAMIENTO POR ÍNDICE ─────────────────────────────
INDICE_CONFIG = {
    # ── PainX 400 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=847 | M15=51 | SL=70 | recalibrado 3 meses reales
    # es_bajista se mantiene True (regla fija de venta, no bias medido)
    # ──────────────────────────────────────────────────────
    "PainX 400": {
        "es_bajista":        True,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            150,
        "tol_h4":            250,
        "reac_avg_h1":       200,
        "sl_minimo":         70,
        "rango_diario":      847,
        "rango_m15":         51,
        "ob_h4_min":         216,      # P85 cuerpos H4 real (ago 2026)
        "ob_h1_min":         110,      # P85 cuerpos H1 real
        "fvg_bull_fuerte":   20,       # avg real FVG alcistas M15
        "fvg_bear_fuerte":   26,       # avg real FVG bajistas M15
        "horas_activas_utc": [4,5,12,15,20,21,22,23],
        "rango_saturado":    762,      # 90% rango diario — no entrar si ya se movió
    },
    # ── PainX 600 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=839 | M15=50 | SL=70 | recalibrado 3 meses reales
    # ──────────────────────────────────────────────────────
    "PainX 600": {
        "es_bajista":        True,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            120,
        "tol_h4":            200,
        "reac_avg_h1":       160,
        "sl_minimo":         70,
        "rango_diario":      839,
        "rango_m15":         50,
        "ob_h4_min":         211,
        "ob_h1_min":         107,
        "fvg_bull_fuerte":   20,
        "fvg_bear_fuerte":   29,
        "horas_activas_utc": [0,1,10,12,13,15,16,17],
        "rango_saturado":    755,
    },
    # ── PainX 800 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=550 | M15=33 | SL=54 | recalibrado 3 meses reales
    # ──────────────────────────────────────────────────────
    "PainX 800": {
        "es_bajista":        True,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            86,
        "tol_h4":            160,
        "reac_avg_h1":       110,
        "sl_minimo":         54,
        "rango_diario":      550,
        "rango_m15":         33,
        "ob_h4_min":         157,
        "ob_h1_min":         75,
        "fvg_bull_fuerte":   14,
        "fvg_bear_fuerte":   21,
        "horas_activas_utc": [2,3,4,5,13,19,20,23],
        "rango_saturado":    495,
    },
    # ── PainX 999 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=866 | M15=48 | SL=75 | recalibrado 3 meses reales
    # ──────────────────────────────────────────────────────
    "PainX 999": {
        "es_bajista":        True,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            122,
        "tol_h4":            240,
        "reac_avg_h1":       170,
        "sl_minimo":         75,
        "rango_diario":      866,
        "rango_m15":         48,
        "ob_h4_min":         236,
        "ob_h1_min":         113,
        "fvg_bull_fuerte":   21,
        "fvg_bear_fuerte":   33,
        "horas_activas_utc": [7,9,10,11,14,18,19,21],
        "rango_saturado":    779,
    },
    # ── PainX 1200 — ACTUALIZADO v4.10 (09-ago-2026) ──────
    # Daily(P90)=432 | M15=25 | SL=44 | recalibrado 3 meses reales
    # ──────────────────────────────────────────────────────
    "PainX 1200": {
        "es_bajista":        True,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            70,     # H1 avg=60 + 10 buffer
        "tol_h4":            130,    # H4 avg=130 → buffer mínimo
        "reac_avg_h1":       90,     # reacción esperada H1
        "sl_minimo":         44,
        "rango_diario":      432,
        "rango_m15":         25,
        "ob_h4_min":         118,
        "ob_h1_min":         59,
        "fvg_bull_fuerte":   11,
        "fvg_bear_fuerte":   18,
        "horas_activas_utc": [1,7,8,11,13,17,18,21],
        "rango_saturado":    389,
    },
    # ── GainX 400 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=836 | M15=51 | SL=72 | recalibrado 3 meses reales
    # es_bajista se mantiene False (regla fija de compra, no bias medido)
    # ──────────────────────────────────────────────────────
    "GainX 400": {
        "es_bajista":        False,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            150,
        "tol_h4":            250,
        "reac_avg_h1":       200,
        "sl_minimo":         72,
        "rango_diario":      836,
        "rango_m15":         51,
        "ob_h4_min":         225,
        "ob_h1_min":         110,
        "fvg_bull_fuerte":   28,
        "fvg_bear_fuerte":   20,
        "horas_activas_utc": [1,4,5,7,10,11,12,23],
        "rango_saturado":    752,
    },
    # ── GainX 600 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=808 | M15=50 | SL=71 | recalibrado 3 meses reales
    # OB MAESTRO histórico se conserva como referencia informativa
    # ──────────────────────────────────────────────────────
    "GainX 600": {
        "es_bajista":        False,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     True,
        "tol_h1":            120,
        "tol_h4":            200,
        "reac_avg_h1":       160,
        "sl_minimo":         71,
        "rango_diario":      808,
        "rango_m15":         50,
        "ob_h4_min":         214,      # P85 cuerpos H4 real (ago 2026)
        "ob_h1_min":         111,      # P85 cuerpos H1 real
        "fvg_bull_fuerte":   29,       # avg real FVG alcistas M15
        "fvg_bear_fuerte":   20,       # avg real FVG bajistas M15
        "horas_activas_utc": [4,5,7,8,9,10,15,21],
        "rango_saturado":    727,      # 90% rango diario
        "ob_maestro_low":    110320,   # OB institucional histórico (referencia)
        "ob_maestro_high":   110420,   # zona de máxima confluencia
    },
    # ── GainX 999 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=787 | M15=47 | SL=73 | recalibrado 3 meses reales
    # ──────────────────────────────────────────────────────
    "GainX 999": {
        "es_bajista":        False,    # regla fija — GainX siempre compra
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            122,
        "tol_h4":            240,
        "reac_avg_h1":       170,
        "sl_minimo":         73,
        "rango_diario":      787,
        "rango_m15":         47,
        "ob_h4_min":         219,      # P85 cuerpos H4 real (ago 2026)
        "ob_h1_min":         112,      # P85 cuerpos H1 real
        "fvg_bull_fuerte":   32,
        "fvg_bear_fuerte":   22,
        "horas_activas_utc": [1,2,6,8,11,12,17,22],
        "rango_saturado":    708,      # 90% rango diario
        "ob_maestro_low":    83218,    # mínimo del ciclo mayo 2026 (referencia)
        "ob_maestro_high":   83512,    # soporte extremo clave
    },

    # ── GainX 800 — ACTUALIZADO v4.10 (09-ago-2026) ───────
    # Daily(P90)=554 | M15=34 | SL=53 | recalibrado 3 meses reales
    # ──────────────────────────────────────────────────────
    "GainX 800": {
        "es_bajista":        False,    # regla fija — GainX siempre compra
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     True,
        "tol_h1":            86,       # H1 avg=76 + 10 buffer
        "tol_h4":            160,      # H4 avg=162
        "reac_avg_h1":       110,      # reacción esperada conservadora
        "sl_minimo":         53,
        "rango_diario":      554,
        "rango_m15":         34,
        "ob_h4_min":         153,      # P85 cuerpos H4 real (ago 2026)
        "ob_h1_min":         76,       # P85 cuerpos H1 real
        "fvg_bull_fuerte":   21,
        "fvg_bear_fuerte":   14,
        "horas_activas_utc": [1,7,10,13,14,17,21,22],
        "rango_saturado":    499,      # 90% rango diario
        "ob_maestro_low":    91247,    # Bull OB H4 clave (referencia histórica)
        "ob_maestro_high":   91494,    # zona de máxima confluencia
    },

    # ── GainX 1200 — ACTUALIZADO v4.10 (09-ago-2026) ──────
    # Daily(P90)=464 | M15=25 | SL=45 | recalibrado 3 meses reales
    # OB H1: 83% rebote (backtest histórico) | SwingLow como respaldo
    # ──────────────────────────────────────────────────────
    "GainX 1200": {
        "es_bajista":        False,
        "usar_fvg":          False,    # FVGs muy pequeños — no confiables
        "usar_ob":           True,     # OB H1: 83% rebote (evidencia real)
        "usar_swinglow":     True,     # SwingLow como respaldo (53%)
        "tol_h1":            100,
        "tol_h4":            180,
        "reac_avg_h1":       140,
        "sl_minimo":         45,
        "rango_diario":      464,
        "rango_m15":         25,
        "ob_h4_min":         130,      # P85 cuerpos H4 real (ago 2026)
        "ob_h1_min":         58,       # P85 cuerpos H1 real
        "fvg_bull_fuerte":   19,
        "fvg_bear_fuerte":   12,
        "horas_activas_utc": [2,6,8,11,12,19,21,23],
        "rango_saturado":    418,      # 90% rango diario
        "ob_maestro_low":    91088,    # OB H4 + Fib 78.6% (referencia histórica)
        "ob_maestro_high":   91130,
    },
}
