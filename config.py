# ============================================================
#  DIEFERT SCANNER v4.7 — config.py
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
# Calibrado: p90 rango M15 + 5 pts buffer.
#
#   PainX 400:  p90=~78 → SL 74pts
#   PainX 600:  p90= 78 → SL 75pts
#   PainX 800:  p90= 54 → SL 59pts
#   PainX 999:  p90= 80 → SL 85pts  ← más volátil
#   PainX 1200: p90= 44 → SL 49pts  ← mueve menos
#   GainX 400:  p90=~78 → SL 74pts
#   GainX 1200: p90=~28 → SL 48pts
SL_MINIMO = {
    "PainX 400":  74,
    "PainX 600":  75,
    "PainX 800":  59,
    "PainX 999":  85,
    "PainX 1200": 49,   # p90 M15=44 + 5 buffer (dato real)
    "GainX 400":  74,
    "GainX 600":  75,   # p90 M15 calibrado | análisis mayo 2026
    "GainX 800":  59,   # p90 M15=54 + 5 buffer (dato real)
    "GainX 999":  85,   # igual a PainX 999 (mismo rango diario)
    "GainX 1200": 48,
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
    # ── PainX 400 — ACTUALIZADO v4.8 ──────────────────────
    # Daily=577 | M15=51 | SL=74 | BEAR 53.6% Monthly
    # FVG bear prom=48pts > bull prom=34pts (fuerza bajista)
    # Horas top: 06,09,15,16 UTC | RSI invertido (>70=SELL)
    # ──────────────────────────────────────────────────────
    "PainX 400": {
        "es_bajista":        True,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            150,
        "tol_h4":            250,
        "reac_avg_h1":       200,
        "sl_minimo":         74,
        "rango_diario":      577,
        "rango_m15":         51,
        "ob_h4_min":         217,      # P85 cuerpos H4 real (CSV 872 velas)
        "ob_h1_min":         110,      # P85 cuerpos H1 real
        "fvg_bull_fuerte":   34,       # avg real FVG alcistas M15
        "fvg_bear_fuerte":   48,       # avg real FVG bajistas M15 (MAYOR)
        "horas_activas_utc": [6,7,8,9,15,16,17,20],
        "rango_saturado":    520,      # 90% rango diario — no entrar si ya se movió
    },
    # ── PainX 600 — v4.2 ──────────────────────────────────
    # Daily=592 | M15=50 | SL=75 | FVGs H4: 417 (avg 111pts)
    # ──────────────────────────────────────────────────────
    "PainX 600": {
        "es_bajista":    True,
        "usar_fvg":      True,
        "usar_ob":       True,
        "usar_swinglow": False,
        "tol_h1":        120,
        "tol_h4":        200,
        "reac_avg_h1":   160,
        "sl_minimo":     75,
        "rango_diario":  592,
        "rango_m15":     50,
    },
    # ── PainX 800 — v4.3 ──────────────────────────────────
    # Daily=406 | M15=33 | SL=59 | EMAs H4=11% (más selectivo)
    # ──────────────────────────────────────────────────────
    "PainX 800": {
        "es_bajista":    True,
        "usar_fvg":      True,
        "usar_ob":       True,
        "usar_swinglow": False,
        "tol_h1":        86,
        "tol_h4":        160,
        "reac_avg_h1":   110,
        "sl_minimo":     59,
        "rango_diario":  406,
        "rango_m15":     33,
    },
    # ── PainX 999 — v4.4 ──────────────────────────────────
    # Daily=607 | M15=48 | SL=85 | FVGs H4 más grandes (115pts)
    # OBs más fuertes (254pts) | Mejor día: mié(54%) y jue(51%)
    # ──────────────────────────────────────────────────────
    "PainX 999": {
        "es_bajista":    True,
        "usar_fvg":      True,
        "usar_ob":       True,
        "usar_swinglow": False,
        "tol_h1":        122,
        "tol_h4":        240,
        "reac_avg_h1":   170,
        "sl_minimo":     85,
        "rango_diario":  607,
        "rango_m15":     48,
    },
    # ── PainX 1200 — v4.5 ─────────────────────────────────
    # Daily=330 | M15=25 | SL=49 | EMAs H4=35% ← más frecuente
    # Winrate setup SHORT = 52% ← mejor de la familia
    # Muy similar a GainX 1200 en comportamiento (espejo bajista)
    # FVGs H4: 501 (avg 60pts) | OBs: 459 (impulso 135pts)
    # CHoCH M15: break avg=57pts | Mejor día: vie(56%) mar(52%)
    # ──────────────────────────────────────────────────────
    "PainX 1200": {
        "es_bajista":    True,
        "usar_fvg":      True,   # 501 FVGs H4 (avg 60 pts)
        "usar_ob":       True,   # 459 OBs H4 (impulso avg 135 pts)
        "usar_swinglow": False,
        "tol_h1":        70,     # H1 avg=60 + 10 buffer
        "tol_h4":        130,    # H4 avg=130 → buffer mínimo
        "reac_avg_h1":   90,     # reacción esperada H1
        "sl_minimo":     49,     # p90 M15=44 + 5 buffer
        "rango_diario":  330,    # dato real histórico
        "rango_m15":     25,     # dato real histórico avg
    },
    # ── GainX 400 ─────────────────────────────────────────
    # Daily=580 | M15=52 | SL=74 | espejo alcista PainX 400
    # ──────────────────────────────────────────────────────
    "GainX 400": {
        "es_bajista":    False,
        "usar_fvg":      True,
        "usar_ob":       True,
        "usar_swinglow": False,
        "tol_h1":        150,
        "tol_h4":        250,
        "reac_avg_h1":   200,
        "sl_minimo":     74,
        "rango_diario":  580,
        "rango_m15":     52,
    },
    # ── GainX 600 — ACTUALIZADO v4.8 ──────────────────────
    # Daily=587 | M15=50 | SL=75 | BULL 59% Monthly
    # OB MAESTRO: 110,320–110,420 (H4+H1+M30+M15 confluyen)
    # M1 mecánico dientes sierra 20-35pts → CHoCH preciso
    # Ciclos M30 amplitud 600-900pts muy definidos
    # ──────────────────────────────────────────────────────
    "GainX 600": {
        "es_bajista":        False,
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     True,
        "tol_h1":            120,
        "tol_h4":            200,
        "reac_avg_h1":       160,
        "sl_minimo":         75,
        "rango_diario":      587,      # dato real CSV (690 velas Daily)
        "rango_m15":         50,
        "ob_h4_min":         232,      # P85 cuerpos H4 real
        "ob_h1_min":         108,      # P85 cuerpos H1 real
        "fvg_bull_fuerte":   45,       # avg real FVG alcistas M15
        "fvg_bear_fuerte":   33,       # avg real FVG bajistas M15
        "horas_activas_utc": [9,10,11,12,13,14,15,16],
        "rango_saturado":    528,      # 90% rango diario
        "ob_maestro_low":    110320,   # OB institucional H4+H1+M30+M15
        "ob_maestro_high":   110420,   # zona de máxima confluencia
    },
    # ── GainX 999 — NUEVO v4.9 ───────────────────────────
    # Daily=611 | M15=47 | SL=85 | BEAR 59.1% Monthly
    # El más bajista de los GainX — comportamiento igual a PainX
    # FVG bull 49pts = más grande de toda la familia (rebotes explosivos)
    # Horas activas: Londres 12-16 UTC + nocturno 22 UTC
    # ──────────────────────────────────────────────────────
    "GainX 999": {
        "es_bajista":        False,    # en SIMBOLOS_ALCISTAS pero bear de facto
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     False,
        "tol_h1":            122,
        "tol_h4":            240,
        "reac_avg_h1":       170,
        "sl_minimo":         85,       # igual a PainX 999 (mismo rango)
        "rango_diario":      611,      # dato real CSV (690 velas)
        "rango_m15":         47,
        "ob_h4_min":         239,      # P85 cuerpos H4 real
        "ob_h1_min":         113,      # P85 cuerpos H1 real
        "fvg_bull_fuerte":   49,       # mayor de toda la familia
        "fvg_bear_fuerte":   30,
        "horas_activas_utc": [7,10,12,14,15,16,18,22],
        "rango_saturado":    550,      # 611 * 0.9
        "ob_maestro_low":    83218,    # mínimo del ciclo mayo 2026
        "ob_maestro_high":   83512,    # soporte extremo clave
    },

    # ── GainX 800 — NUEVO v4.9 ───────────────────────────
    # Daily=415 | M15=33 | SL=59 | BEAR 53.6% Monthly
    # ATENCIÓN: GainX en nombre pero behaves como BEAR macro
    # Rebotes alcistas son los trades principales (FVG bull 38pts)
    # FVG bear solo 24pts — bajadas más débiles que GainX 600
    # Horas activas: pre-Londres 05-07 UTC (diferente al resto)
    # Bidireccional: BUY en soportes, SELL en resistencias
    # ──────────────────────────────────────────────────────
    "GainX 800": {
        "es_bajista":        False,    # técnicamente en SIMBOLOS_ALCISTAS
        "usar_fvg":          True,
        "usar_ob":           True,
        "usar_swinglow":     True,
        "tol_h1":            86,       # H1 avg=76 + 10 buffer
        "tol_h4":            160,      # H4 avg=162
        "reac_avg_h1":       110,      # reacción esperada conservadora
        "sl_minimo":         59,       # ya calibrado en v4.3 (dato real)
        "rango_diario":      415,      # dato real CSV (872 velas Daily)
        "rango_m15":         33,       # dato real
        "ob_h4_min":         160,      # P85 cuerpos H4 real
        "ob_h1_min":         73,       # P85 cuerpos H1 real
        "fvg_bull_fuerte":   38,       # avg real FVG alcistas M15 (MAYOR)
        "fvg_bear_fuerte":   27,       # avg real FVG bajistas M15
        "horas_activas_utc": [5,6,7,10,14,15,17,18,23,0,1],
        "rango_saturado":    373,      # 415 * 0.9
        "ob_maestro_low":    91247,    # Bull OB H4 clave (may 17)
        "ob_maestro_high":   91494,    # zona de máxima confluencia
    },

    # ── GainX 1200 — ACTUALIZADO v4.8 ─────────────────────
    # Daily=~900pts | M15=25 | SL=48 | BULL alcista
    # V-shapes M5: 200-230pts (más agresivos que GainX 600)
    # Zona activa: OB H4 + Fib 78.6% = 91,088–91,130
    # OB H1: 83% rebote (340 casos backtest real)
    # SwingLow H1: 53% rebote (respaldo)
    # ──────────────────────────────────────────────────────
    "GainX 1200": {
        "es_bajista":        False,
        "usar_fvg":          False,    # FVGs muy pequeños — no confiables
        "usar_ob":           True,     # OB H1: 83% rebote (evidencia real)
        "usar_swinglow":     True,     # SwingLow como respaldo (53%)
        "tol_h1":            100,
        "tol_h4":            180,
        "reac_avg_h1":       140,
        "sl_minimo":         48,
        "rango_diario":      900,      # real — mayor que GainX 600
        "rango_m15":         25,
        "ob_h4_min":         250,      # calibrado (mayor que G600)
        "ob_h1_min":         120,      # calibrado
        "fvg_bull_fuerte":   50,
        "fvg_bear_fuerte":   40,
        "horas_activas_utc": [0,1,6,9,10,13,14,15,16,21,22,23],
        "rango_saturado":    810,      # 90% rango diario
        "ob_maestro_low":    91088,    # OB H4 + Fib 78.6% activo mayo 2026
        "ob_maestro_high":   91130,
    },
}
