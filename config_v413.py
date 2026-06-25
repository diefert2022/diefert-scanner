# ============================================================
# config_v413.py — Scanner Diefert v4.9
# Actualizado: 02 Junio 2026
# Cambios vs v412:
#   - TODOS los índices: agregado sl_minimo (pts mínimos de SL)
#     Calculado como p75 del rango H1 real por CSV.
#     El scanner NO enviará señal si SL calculado < sl_minimo.
#   - PainX 800: recalibrado con CSV real 02 Jun 2026
#     · rango_h4_avg: 170 → 160 | rango_h1_avg: 68 → 76
#     · ob_h4_min: 135 → 153 (p85 body real)
#     · ob_h1_min: 68 → 75 (p85 body real)
#     · fvg_bull/bear_fuerte: 11 → 47/62 (p85 M5 real)
#     · horas_activas_utc: top 6 real [7,8,10,12,14,23]
#     · ob_maestro: zona 118,756–118,856 (132 toques H4)
#     · sl_minimo: 87 pts (p75 rango H1)
#     · rango_saturado: 926 → 472 (p75 daily real)
#   - PainX 400: sl_minimo=98 (p75 rango H1 real)
#   - topdown.py: SL ya no es hardcoded 30pts — usa sl_minimo del config
#   - topdown.py: _analizar_h4 ahora verifica tendencia H4
#     Si H4 va en contra → bloquea la señal
# ============================================================

INDICES_CONFIG = {

    # ══════════════════════════════════════════════════════════
    # PAINX 400  —  BEAR 52.8% hist / 56.7% rec90 | rango 545pts | CSV REAL 25 MAY 2026
    # ══════════════════════════════════════════════════════════
    "PainX 400": {
        "simbolo":           "PainX 400",
        "tipo":              "Growing Index (400 ticks/salto)",  # ojo: PainX es Growing
        "sesgo_macro":       "BEAR",
        "sesgo_diario":      "NEUTRAL",     # últimas 20: 55% bear pero rebote +968pts hoy
        "sesgo_h4":          "NEUTRAL",     # H4 imágenes: rebote alcista desde 91,800

        # Rangos reales CSV (875 velas Daily)
        "rango_daily_avg":   545,           # mediana real (antes 577)
        "rango_daily_max":   818,           # P90 real (antes 900)
        "rango_h4_avg":      221,           # mediana real (antes 217) — casi igual ✅
        "rango_h1_avg":      105,           # mediana real (antes 100)
        "rango_m30_avg":     71,            # mediana real (antes 65)
        "rango_saturado":    818,           # P90 real (antes 800) — casi igual ✅

        # OB thresholds — P70 real
        "ob_h4_min":         157,           # P70 real (antes 150)
        "ob_h1_min":         79,            # P70 real
        "ob_m1_min":         6,             # cuerpo mín vela M1
        "sl_minimo":         98,            # p75 rango H1 real — SL mínimo aceptado
        "noise_candle_min":  3.5,           # vela mínima spike M1 (medida real PainX 400)
        "ob_h4_fuerte":      216,           # P85 real
        "ob_h1_fuerte":      110,           # P85 real

        # FVG thresholds — P70 M5 real
        "fvg_bull_fuerte":   18,            # M5 P70 real (antes 40)
        "fvg_bear_fuerte":   18,            # M5 P70 real (antes 48)
        "fvg_m15_fuerte":    30,            # M15 P70 real

        # Horas activas — 24h uniforme, picos 08h/15h/21h UTC
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       8,             # apertura Londres ✅ (sin cambio)
        "hora_peak_2":       15,            # NY overlap (antes 13)
        "hora_peak_3":       21,            # cierre NY (antes 20)

        # OB Maestro — zona actual precio ~92,220 (rebote desde 91,880)
        # Fibonacci swing 90d: SH=96,526 (04-Mar) → SL=90,736 (14-Apr)
        # Precio en Fib 78.6% = 91,975 — zona de resistencia-soporte
        "ob_maestro_low":    91770,         # soporte institucional — sin cambio ✅
        "ob_maestro_high":   92350,         # actualizado: Fib 61.8% = 92,947 sigue arriba

        # Fibonacci swing bajista (04-Mar → 14-Apr 2026)
        "fib_swing_high":    96525.61,
        "fib_swing_low":     90735.57,
        "fib_23_6":          95159.0,       # resistencia lejana
        "fib_38_2":          94314.0,       # resistencia fuerte
        "fib_50":            93631.0,       # resistencia media
        "fib_61_8":          92947.0,       # resistencia próxima (~727pts arriba)
        "fib_78_6":          91975.0,       # zona actual — precio lo acaba de superar

        # Zonas clave actualizadas
        "resistencia_1":     92350,         # zona reciente de distribución 23-May
        "resistencia_2":     92604,         # máximo 24-May (techo del rebote)
        "resistencia_3":     92947,         # Fib 61.8% — resistencia mayor
        "soporte_1":         91872,         # OB H4 bull activo 25-May
        "soporte_2":         91692,         # OB H4 bull activo 22-May
        "soporte_3":         91375,         # OB H4 bull activo 20-May

        # OBs críticos H4 activos (25 Mayo 2026)
        # BULL activos (soporte si retrocede):
        #   25-May 16h: 91,872–92,149 body=277 — más fuerte reciente ✅
        #   22-May 16h: 91,692–91,964 body=273 ✅
        #   21-May 12h: 91,206–91,467 body=261 ✅
        #   20-May 08h: 91,184–91,375 body=191 ✅
        #   16-May 12h: 91,102–91,321 body=218 ✅
        # BEAR activo (resistencia):
        #   24-May 12h: 92,319–92,604 body=285 ✅ — zona de venta
        "ob_critico_bull_h4_low":   91872,
        "ob_critico_bull_h4_high":  92149,  # 25-May body=277 — más reciente
        "ob_critico_bear_h4_low":   92319,
        "ob_critico_bear_h4_high":  92604,  # 24-May body=285 — resistencia activa

        # FVGs H4 activos (25 Mayo 2026)
        # BULL: 25-May 16h: 92,079–92,149 gap=70pts ✅
        # BEAR: 24-May 12h: 92,343–92,388 gap=45pts ✅
        "fvg_bull_activo_low":      92079,
        "fvg_bull_activo_high":     92149,  # 70pts — soporte inmediato
        "fvg_bear_activo_low":      92343,
        "fvg_bear_activo_high":     92388,  # 45pts — resistencia cercana

        # Timeframes
        "tf_principal":      "M15",
        "tf_entrada":        "M5",
        "tf_confirmacion":   "M1",
    },

    # ══════════════════════════════════════════════════════════
    # PAINX 600  —  CSV REAL 25 MAY 2026
    # ══════════════════════════════════════════════════════════
    "PainX 600": {
        "simbolo":           "PainX 600",
        "tipo":              "Growing Index (600 ticks/salto) — solo VENTAS",
        "sesgo_macro":       "BEAR",
        "sesgo_diario":      "BEAR",
        "sesgo_h4":          "NEUTRAL",

        "rango_daily_avg":   592,             # actualizado CSV real
        "rango_daily_max":   1276,
        "rango_h4_avg":      220,
        "rango_h1_avg":      100,
        "rango_m30_avg":     68,
        "rango_saturado":    852,

        "ob_h4_min":         199,             # p80 real (era 165)
        "ob_h1_min":         99,              # p80 real (era 75)
        "ob_m1_min":         6,             # cuerpo mín vela M1
        "fvg_bull_fuerte":   17,              # p85 M5 real (era 45)
        "fvg_bear_fuerte":   17,              # (era 55)

        "horas_activas_utc": list(range(0, 24)),   # real CSV (era range 0-24)
        "hora_peak_1":       5,
        "hora_peak_2":       12,
        "hora_peak_3":       20,

        "ob_maestro_low":    106149,          # zona más respetada H4 (era 0)
        "ob_maestro_high":   106199,

        "fib_swing_high":    0,
        "fib_swing_low":     0,
        "fib_38_2":          0,
        "fib_50":            0,
        "fib_61_8":          0,
        "fib_78_6":          0,

        "resistencia_1":     0,
        "resistencia_2":     0,
        "soporte_1":         0,
        "soporte_2":         0,

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },


    # ══════════════════════════════════════════════════════════
    # PAINX 600  —  CSV REAL 31-May-2026 | 699 velas Daily
    # ══════════════════════════════════════════════════════════
    "PainX 600": {
        "simbolo":           "PainX 600",
        "tipo":              "Growing Index (600 ticks/salto)",

        # ATENCIÓN: PainX 600 es GROWING INDEX — sube por defecto
        # El scanner lo opera como SHORT (buscamos vender en resistencias)
        # porque el sesgo estadístico favorece las caídas desde zonas altas
        "sesgo_macro":       "BEAR",        # Daily BULL 52.4% pero operamos SHORT desde zonas
        "sesgo_diario":      "BULL",         # Últimas 20 Daily: BULL fuerte (15B/5b) drift +706pts
        "sesgo_h4":          "BULL",         # H4 60v: BULL (36B/24b) drift +730pts

        # Rangos reales CSV (699 velas Daily)
        "rango_daily_avg":   592,
        "rango_daily_max":   1276,
        "rango_h4_avg":      236,
        "rango_h1_avg":      111,
        "rango_m30_avg":     75,
        "rango_m15_avg":     50,
        "rango_saturado":    852,           # P90 Daily

        # OB thresholds — P70 real CSV
        "ob_h4_min":         263,           # P70 H4
        "ob_h1_min":         123,           # P70 H1
        "ob_m1_min":         5,             # ATR M1 = 4.6pts
        "ob_h4_fuerte":      336,           # P90 H4
        "ob_h1_fuerte":      159,           # P90 H1

        # FVG thresholds — P70 CSV
        "fvg_bull_fuerte":   48,
        "fvg_bear_fuerte":   48,
        "fvg_m15_fuerte":    48,

        # Horas activas — prácticamente 24h (diferencia < 3pts)
        # Pico leve: 05h, 12h, 09h UTC
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       5,             # Frankfurt apertura
        "hora_peak_2":       12,            # Londres mid
        "hora_peak_3":       9,             # Londres apertura

        # Filtro impulso M1
        "impulso_max_vela_m1": 10,          # ATR M1=4.6 × 2 ≈ 10pts
        "sl_minimo":         90,            # p75 rango H1 PainX 600
        "noise_candle_min":  3.0,           # vela mínima spike M1 (medida real PainX 600)

        # Score mínimo
        "score_minimo_entrada": 7,

        # OB Maestro — zona oferta H4 (resistencia principal)
        # Impulso bajista: SH=109,965 → SL=105,574 (4390pts)
        "ob_maestro_low":    108231,        # primer OB bajista sin mitigar
        "ob_maestro_high":   108365,        # techo OB bajista

        # Fibonacci bajista (entrada SHORT en retroceso)
        # SH=109,965 → SL=105,574 rango=4,390pts
        "fib_swing_high":    109965,
        "fib_swing_low":     105574,
        "fib_23_6":          106610,        # ya pasado
        "fib_38_2":          107251,        # precio actual — ZONA SHORT principal
        "fib_50":            107769,        # zona SHORT media
        "fib_61_8":          108287,        # zona SHORT fuerte (cerca OB maestro)
        "fib_78_6":          109025,        # zona SHORT máxima

        # Resistencias activas (zonas de venta)
        "resistencia_1":     107251,        # Fib 38.2% — precio actual
        "resistencia_2":     107769,        # Fib 50%
        "resistencia_3":     108287,        # Fib 61.8% + OB H4

        # Soportes activos (invalidación de SHORT)
        "soporte_1":         106984,        # SH H4 29-May — soporte inmediato
        "soporte_2":         106517,        # SL H4 30-May
        "soporte_3":         105574,        # mínimo del impulso — invalidación

        # OBs críticos H4
        "ob_critico_bear_h4_low":   108231,  # OB bajista principal
        "ob_critico_bear_h4_high":  108365,
        "ob_critico_bear_h4_2_low": 108503,  # OB bajista 2
        "ob_critico_bear_h4_2_high":108561,
        "ob_critico_bull_h4_low":   106517,  # soporte H4
        "ob_critico_bull_h4_high":  106984,

        # FVGs activos
        "fvg_bear_activo_low":      107251,  # Fib 38.2% zona oferta
        "fvg_bear_activo_high":     107769,
        "fvg_bull_activo_low":      106517,
        "fvg_bull_activo_high":     106984,

        # Tolerancia M15 dinámica
        "tol_zona_m15":             120,     # ATR M15=47 × 2.5

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # PAINX 800  —  CSV REAL 02 JUN 2026 | RECALIBRADO COMPLETO
    # Causa señal fallida 02/jun: SL hardcoded 30pts, H4 alcista ignorado
    # Fixes: sl_minimo=87, rangos y OBs actualizados con datos reales
    # ══════════════════════════════════════════════════════════
    "PainX 800": {
        "simbolo":           "PainX 800",
        "tipo":              "Growing Index (800 ticks/salto) — solo VENTAS",
        "sesgo_macro":       "BEAR",        # operamos SHORT siempre en PainX
        "sesgo_diario":      "BEAR",
        "sesgo_h4":          "NEUTRAL",

        # Rangos reales CSV 02/Jun 2026
        "rango_daily_avg":   405,           # avg real
        "rango_daily_median":384,           # mediana real
        "rango_daily_max":   531,           # P85 real (antes 926=P90)
        "rango_h4_avg":      160,           # mediana real (antes 170)
        "rango_h4_p75":      187,           # p75 real
        "rango_h1_avg":      76,            # mediana real (antes 68) ← CORREGIDO
        "rango_h1_p75":      87,            # p75 real
        "rango_m15_avg":     33,            # mediana real
        "rango_m5_avg":      15,            # mediana real
        "rango_saturado":    472,           # P75 daily — umbral saturación (antes 572)

        # OB thresholds — p85 body real CSV
        "ob_h4_min":         153,           # p85 body H4 real (antes 135)
        "ob_h1_min":         75,            # p85 body H1 real (antes 68)
        "ob_m1_min":         5,             # cuerpo mín vela M1
        "ob_h4_fuerte":      209,           # p85 rango H4
        "ob_h1_fuerte":      99,            # p85 rango H1

        # SL MÍNIMO — clave nueva para bloquear SLs ridículos
        # = p75 rango H1 real. Scanner rechaza señal si SL < este valor.
        "sl_minimo":         87,            # pts mínimos de SL para PainX 800
        "noise_candle_min":  2.0,           # vela mínima spike M1 (medida real PainX 800)

        # FVG thresholds — real CSV
        "fvg_bull_fuerte":   47,            # p85 FVG H1 (antes 11 — era M5 mal calculado)
        "fvg_bear_fuerte":   62,            # p85 FVG H4
        "fvg_m15_fuerte":    27,            # p85 FVG M15

        # Horas activas — top 6 por rango H1 (CSV real)
        # Todas las horas son casi iguales (76–77pts) pero top6:
        "horas_activas_utc": list(range(0, 24)),       # v4.16: 24/7 sintéticos
        "hora_peak_1":       23,            # 77.3 pts avg
        "hora_peak_2":       12,            # 76.8 pts avg
        "hora_peak_3":       8,             # 76.5 pts avg

        # OB Maestro — zona más testeada H4 (132 toques, últimas 500 velas)
        "ob_maestro_low":    118756,        # zona 132 toques (antes 118806)
        "ob_maestro_high":   118906,        # techo zona extendida

        # Impulso bajista típico H4 (para calibrar TPs)
        # BEAR avg=322pts, median=259pts, p75=428pts, max=1379pts
        "impulso_bear_h4_avg":   322,
        "impulso_bear_h4_p75":   428,

        # Fibonacci — pendiente actualizar con swing actual
        "fib_swing_high":    0,
        "fib_swing_low":     0,
        "fib_38_2":          0,
        "fib_50":            0,
        "fib_61_8":          0,
        "fib_78_6":          0,

        # Zonas clave actuales (02/Jun 2026)
        "resistencia_1":     119285,        # máximo H4 02/jun (pre-señal)
        "resistencia_2":     119350,        # zona distribución reciente
        "soporte_1":         118756,        # OB maestro low
        "soporte_2":         118550,        # zona soporte profundo

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # PAINX 999
    # ══════════════════════════════════════════════════════════
    "PainX 999": {
        "simbolo":           "PainX 999",
        "tipo":              "Decreasing Index (999 ticks/salto)",
        "sesgo_macro":       "BEAR",
        "sesgo_diario":      "BEAR",
        "sesgo_h4":          "BEAR",

        "rango_daily_avg":   750,
        "rango_daily_max":   1300,
        "rango_h4_avg":      280,
        "rango_h1_avg":      130,
        "rango_m30_avg":     85,
        "rango_saturado":    1100,

        "ob_h4_min":         195,
        "ob_h1_min":         90,
        "ob_m1_min":         7,             # cuerpo mín vela M1
        "sl_minimo":         120,           # p75 rango H1 estimado PainX 999
        "noise_candle_min":  2.5,           # vela mínima spike M1 (medida real PainX 999)
        "fvg_bull_fuerte":   55,
        "fvg_bear_fuerte":   65,

        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       8,
        "hora_peak_2":       13,
        "hora_peak_3":       20,

        "ob_maestro_low":    0,
        "ob_maestro_high":   0,

        "fib_swing_high":    0,
        "fib_swing_low":     0,
        "fib_38_2":          0,
        "fib_50":            0,
        "fib_61_8":          0,
        "fib_78_6":          0,

        "resistencia_1":     0,
        "resistencia_2":     0,
        "soporte_1":         0,
        "soporte_2":         0,

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # PAINX 1200
    # ══════════════════════════════════════════════════════════
    "PainX 1200": {
        "simbolo":           "PainX 1200",
        "tipo":              "Decreasing Index (1200 ticks/salto)",
        "sesgo_macro":       "BEAR",
        "sesgo_diario":      "BEAR",
        "sesgo_h4":          "BEAR",

        "rango_daily_avg":   800,
        "rango_daily_max":   1400,
        "rango_h4_avg":      300,
        "rango_h1_avg":      140,
        "rango_m30_avg":     90,
        "rango_saturado":    1200,

        "ob_h4_min":         210,
        "ob_h1_min":         95,
        "ob_m1_min":         7,             # cuerpo mín vela M1
        "sl_minimo":         140,           # p75 rango H1 estimado PainX 1200
        "noise_candle_min":  1.5,           # vela mínima spike M1 (medida real PainX 1200)
        "fvg_bull_fuerte":   60,
        "fvg_bear_fuerte":   70,

        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       8,
        "hora_peak_2":       13,
        "hora_peak_3":       20,

        "ob_maestro_low":    0,
        "ob_maestro_high":   0,

        "fib_swing_high":    0,
        "fib_swing_low":     0,
        "fib_38_2":          0,
        "fib_50":            0,
        "fib_61_8":          0,
        "fib_78_6":          0,

        "resistencia_1":     0,
        "resistencia_2":     0,
        "soporte_1":         0,
        "soporte_2":         0,

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # GAINX 400  —  BEAR 51.3% hist / 62.2% reciente | rango 543pts | CSV REAL 25 MAY 2026
    # ══════════════════════════════════════════════════════════
    "GainX 400": {
        "simbolo":           "GainX 400",
        "tipo":              "Decreasing Index (400 ticks/salto)",
        "sesgo_macro":       "BEAR",       # Monthly rebote bajista desde nov 2025
        "sesgo_diario":      "BEAR",       # Daily 62.2% bear | drift -5474pts últimos 90d
        "sesgo_h4":          "BEAR",

        # Rangos (datos reales CSV — 875 velas Daily, 21004 H1, 5254 H4)
        "rango_daily_avg":   543,           # mediana real (antes 572 estimado)
        "rango_daily_max":   1330,          # máximo real (antes 1071)
        "rango_h4_avg":      220,           # mediana real (antes 243)
        "rango_h1_avg":      104,           # mediana real (antes 112)
        "rango_m30_avg":     70,            # mediana real (antes 75)
        "rango_saturado":    750,           # P90 daily = 843, umbral = 750 (antes 900)

        # Thresholds OB (P70 real del CSV)
        "ob_h4_min":         157,           # P70 real (antes 160)
        "ob_h1_min":         79,            # P70 real (antes 80)

        # Thresholds FVG (P70 M5 real = 18pts)
        "fvg_bull_fuerte":   18,            # M5 P70 real (antes 70 — era estimado H4)
        "fvg_bear_fuerte":   18,            # M5 P70 real (antes 70)

        # Horas activas — CONSTANTE 24h confirmado por CSV (diferencia <1pt entre horas)
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       11,            # overlap Londres-NY (antes 21)
        "hora_peak_2":       4,             # pre-Londres (igual)
        "hora_peak_3":       15,            # NY (antes 17)

        # OB Maestro — zona actual precio ~100,454
        "ob_maestro_low":    99700,         # soporte zona actual (antes 100500)
        "ob_maestro_high":   100700,        # resistencia zona actual (antes 101200)

        # Fibonacci swing bajista (Feb 22 → May 17, 2026) — sin cambios
        "fib_swing_high":    106806.69,
        "fib_swing_low":     99606.24,
        "fib_23_6":          105107.38,
        "fib_38_2":          104056.12,
        "fib_50":            103206.46,
        "fib_61_8":          102356.81,
        "fib_78_6":          101147.14,     # ← zona clave resistencia

        # Zonas de soporte/resistencia — sin cambios
        "resistencia_1":     103500,
        "resistencia_2":     103800,
        "resistencia_3":     102000,

        "soporte_1":         100000,        # nivel psicológico fuerte (inicio dataset)
        "soporte_2":         99700,         # soporte zona actual confirmado
        "soporte_3":         99000,

        # OBs críticos H4 activos zona actual (25 Mayo 2026)
        # Bear recientes: 100,874-100,589 (24 May) | 100,605-100,432 (24 May)
        # Bull recientes: 100,400-100,587 (25 May) | 100,373-100,685 (23 May)
        "ob_critico_bear_h4_low":   100432,
        "ob_critico_bear_h4_high":  100874,
        "ob_critico_bull_h4_low":   100373,
        "ob_critico_bull_h4_high":  100685,

        # FVG activos zona actual (25 Mayo 2026)
        "fvg_bear_activo_low":      100432,
        "fvg_bear_activo_high":     100874,
        "fvg_bull_activo_low":      100373,
        "fvg_bull_activo_high":     100587,

        # Timeframes — sin cambios
        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },


    # ══════════════════════════════════════════════════════════
    # GAINX 400  —  CSV REAL 31-May-2026 | 881 velas Daily
    # ══════════════════════════════════════════════════════════
    "GainX 400": {
        "simbolo":           "GainX 400",
        "tipo":              "Decreasing Index (400 ticks/salto)",
        "sesgo_macro":       "BEAR",        # Daily 51.3% bear · drift bajista largo plazo
        "sesgo_diario":      "NEUTRO",      # Últimas 20 Daily: BEAR leve (8B/12b) pero drift +726pts
        "sesgo_h4":          "NEUTRO",      # H4 50/50 exacto · precio en 62% del rango mensual

        # Rangos reales CSV (881 velas Daily)
        "rango_daily_avg":   580,
        "rango_daily_max":   1330,
        "rango_h4_avg":      233,
        "rango_h1_avg":      111,
        "rango_m30_avg":     75,
        "rango_m15_avg":     51,
        "rango_saturado":    842,           # P90 Daily — rango excepcional

        # OB thresholds — P70 real CSV
        "ob_h4_min":         261,           # P70 H4
        "ob_h1_min":         123,           # P70 H1
        "ob_m1_min":         9,             # P70 M1 estimado (ATR M1 = 8.9)
        "ob_h4_fuerte":      331,           # P90 H4
        "ob_h1_fuerte":      160,           # P90 H1

        # FVG thresholds — P70 CSV
        "fvg_bull_fuerte":   54,            # P70 M15
        "fvg_bear_fuerte":   54,            # P70 M15
        "fvg_m15_fuerte":    54,            # mismo

        # Horas activas — prácticamente 24h (diferencia < 2pts entre horas)
        # Picos leves: 21h, 19h, 04h, 23h UTC
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       21,            # NY cierre
        "hora_peak_2":       4,             # Asia/Frankfurt
        "hora_peak_3":       19,            # NY apertura

        # Filtro impulso M1
        "impulso_max_vela_m1": 18,          # ATR M1=8.9 × 2 ≈ 18pts

        # Score mínimo
        "score_minimo_entrada": 7,

        # OB Maestro — zona demanda H4 activa (impulso desde 99,865)
        "ob_maestro_low":    100010,        # mínimo swing H4 23-May
        "ob_maestro_high":   100294,        # OB H4 activo sin mitigar

        # Fibonacci — swing alcista reciente
        # SL=99,606 (mínimo H4 17-May) → SH=101,268 (máximo 30-May)
        # Rango=1,661pts
        "fib_swing_high":    101268,
        "fib_swing_low":     99606,
        "fib_23_6":          100875,        # retroceso leve — zona actual
        "fib_38_2":          100633,        # FVG H1 activo 100,649–100,735
        "fib_50":            100437,        # soporte medio
        "fib_61_8":          100241,        # OB H4 activo 100,075–100,294
        "fib_78_6":          99962,         # mínimo swing H4 26-May

        # Resistencias activas
        "resistencia_1":     101268,        # SH H4 actual — techo
        "resistencia_2":     101581,        # máximo H4 del mes
        "resistencia_3":     102500,        # objetivo si rompe 101268

        # Soportes activos
        "soporte_1":         100875,        # Fib 23.6% + FVG H1 cercano
        "soporte_2":         100633,        # Fib 38.2% + FVG H1 activo
        "soporte_3":         100241,        # Fib 61.8% + OB H4 activo
        "soporte_4":         99865,         # mínimo H4 26-May — invalidación

        # OBs críticos H4 activos
        "ob_critico_bull_h4_low":   100075,  # OB H4 alcista sin mitigar
        "ob_critico_bull_h4_high":  100294,
        "ob_critico_bull_h4_2_low": 100010,  # OB H4 alcista 23-May
        "ob_critico_bull_h4_2_high":100294,
        "ob_critico_bear_h4_low":   101268,  # resistencia principal
        "ob_critico_bear_h4_high":  101581,

        # FVGs H1 activos (sin mitigar)
        "fvg_bull_activo_low":      100849,  # FVG más cercano — 55pts abajo
        "fvg_bull_activo_high":     100885,
        "fvg_bull_2_low":           100649,  # FVG amplio — 205pts abajo
        "fvg_bull_2_high":          100735,
        "fvg_bear_activo_low":      101268,
        "fvg_bear_activo_high":     101581,

        # Tolerancia M15 dinámica
        "tol_zona_m15":             125,     # ATR M15=50 × 2.5

        # Spike trailing stop — medida real Diego (Jun 2026)
        "noise_candle_min":  4.0,           # vela mínima spike M1 (medida real GainX 400)

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # GAINX 600  —  BULL 59% | rango 587pts | CSV REAL
    # ══════════════════════════════════════════════════════════
    "GainX 600": {
        "simbolo":           "GainX 600",
        "tipo":              "Decreasing Index (600 ticks/salto)",
        "sesgo_macro":       "BULL",
        "sesgo_diario":      "BULL",
        "sesgo_h4":          "BULL",

        "rango_daily_avg":   587,
        "rango_daily_max":   1000,
        "rango_h4_avg":      232,
        "rango_h1_avg":      105,
        "rango_m30_avg":     70,
        "rango_saturado":    900,

        "ob_h4_min":         160,
        "ob_h1_min":         75,
        "ob_m1_min":         6,             # cuerpo mín vela M1
        "sl_minimo":         90,            # p75 rango H1 GainX 600
        "noise_candle_min":  3.0,           # vela mínima spike M1 (medida real GainX 600)
        "fvg_bull_fuerte":   45,
        "fvg_bear_fuerte":   45,

        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       8,
        "hora_peak_2":       13,
        "hora_peak_3":       20,

        "ob_maestro_low":    110320,
        "ob_maestro_high":   110420,

        "fib_swing_high":    0,
        "fib_swing_low":     0,
        "fib_38_2":          0,
        "fib_50":            0,
        "fib_61_8":          0,
        "fib_78_6":          0,

        "resistencia_1":     0,
        "resistencia_2":     0,
        "soporte_1":         0,
        "soporte_2":         0,

        "ob_critico_bear_h4_low":   0,
        "ob_critico_bear_h4_high":  0,
        "ob_critico_bull_h4_low":   0,
        "ob_critico_bull_h4_high":  0,
        "fvg_bear_activo_low":      0,
        "fvg_bear_activo_high":     0,
        "fvg_bull_activo_low":      0,
        "fvg_bull_activo_high":     0,

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # GAINX 800  —  BEAR 51.2% hist / 56.7% rec90 | rango 394pts | CSV REAL 25 MAY 2026
    # ══════════════════════════════════════════════════════════
    "GainX 800": {
        "simbolo":           "GainX 800",
        "tipo":              "Decreasing Index (800 ticks/salto)",
        "sesgo_macro":       "BEAR",        # ¡nombre GainX pero sesgo BEAR!
        "sesgo_diario":      "NEUTRAL",     # últimas 20: 40% bear, drift +1309pts (rebote)
        "sesgo_h4":          "BEAR",        # H4 bajando desde 92,307 → 91,669 hoy

        # Rangos reales CSV (875 velas Daily)
        "rango_daily_avg":   394,           # mediana real (antes 415 estimado)
        "rango_daily_max":   594,           # P90 real (antes 800)
        "rango_h4_avg":      153,           # mediana real (antes 160)
        "rango_h1_avg":      70,            # mediana real (antes 75)
        "rango_m30_avg":     47,            # mediana real (antes 50)
        "rango_saturado":    594,           # P90 daily = umbral saturación (antes 700)

        # OB thresholds — P70 real
        "ob_h4_min":         113,           # P70 real (antes 110)
        "ob_h1_min":         55,
        "ob_m1_min":         5,             # cuerpo mín vela M1
        "sl_minimo":         72,            # p75 rango H1 GainX 800
        "noise_candle_min":  2.0,           # vela mínima spike M1 (medida real GainX 800)
        "ob_h4_fuerte":      154,           # P85 real
        "ob_h1_fuerte":      75,            # P85 real

        # FVG thresholds — P70 M5 real
        "fvg_bull_fuerte":   9,             # M5 P70 real (antes 38 — era estimado)
        "fvg_bear_fuerte":   9,             # M5 P70 real (antes 42)
        "fvg_m15_fuerte":    24,            # M15 P70 real

        # Horas activas — CONSTANTE 24h (diferencia <4pts entre horas)
        # Ligero pico: 23h/00h/07h UTC (diferencia mínima)
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       23,
        "hora_peak_2":       0,
        "hora_peak_3":       7,

        # OB Maestro — zona de máxima concentración histórica
        # Daily: 41-47 toques entre 92,564–94,781 (zona arriba del precio)
        # Soporte actual: Fib 61.8% swing = 91,419
        "ob_maestro_low":    91419,         # Fib 61.8% swing Mar-May 2026
        "ob_maestro_high":   91948,         # Fib 50.0% swing = resistencia clave

        # Fibonacci swing bajista (07-Mar → 07-May 2026)
        # SH=94,190 → SL=89,706
        "fib_swing_high":    94190.22,
        "fib_swing_low":     89706.04,
        "fib_23_6":          93132.0,       # primera resistencia
        "fib_38_2":          92477.0,       # resistencia media
        "fib_50":            91948.0,       # resistencia fuerte — cerca precio actual
        "fib_61_8":          91419.0,       # soporte actual — precio operando cerca
        "fib_78_6":          90666.0,       # soporte profundo

        # Zonas clave por toques
        "resistencia_1":     91948,         # Fib 50% — techo del rebote
        "resistencia_2":     92477,         # Fib 38.2% — resistencia mayor
        "resistencia_3":     93132,         # Fib 23.6% — resistencia fuerte
        "soporte_1":         91419,         # Fib 61.8% — soporte actual
        "soporte_2":         90666,         # Fib 78.6% — soporte profundo
        "soporte_3":         89706,         # mínimo swing — soporte absoluto

        # OBs críticos H4 activos (25 Mayo 2026)
        # BEAR activos (zonas de venta si rebota):
        #   25-May 16h: 91,669–91,798 body=129 — precio aquí ahora
        #   25-May 08h: 91,793–91,916 body=124
        #   24-May 08h: 92,104–92,226 body=123 — FVG bear encima
        # BULL activos sin retestear (soporte si baja):
        #   19-May 04h: 91,491–91,799 body=308 — EL MÁS FUERTE
        #   14-May 16h: 91,130–91,416 body=285 — soporte profundo
        "ob_critico_bear_h4_low":   91669,
        "ob_critico_bear_h4_high":  91916,  # zona actual 25-May
        "ob_critico_bull_h4_low":   91491,
        "ob_critico_bull_h4_high":  91799,  # 19-May body=308 — más fuerte

        # FVGs H4 activos (25 Mayo 2026)
        # Bear sin mitigar (resistencia):
        #   24-May 08h: 92,123–92,200 gap=77pts
        #   25-May 08h: 91,811–91,847 gap=36pts
        # Bull sin mitigar (soporte):
        #   13-May 20h: 90,734–90,879 gap=146pts — más fuerte y más lejano
        #   17-May 12h: 91,435–91,477 gap=42pts
        "fvg_bear_activo_low":      91811,
        "fvg_bear_activo_high":     91847,  # más cercano al precio
        "fvg_bear_activo_2_low":    92123,
        "fvg_bear_activo_2_high":   92200,  # zona resistencia superior
        "fvg_bull_activo_low":      91435,
        "fvg_bull_activo_high":     91477,  # 17-May — soporte cercano
        "fvg_bull_activo_2_low":    90734,
        "fvg_bull_activo_2_high":   90879,  # 13-May 146pts — soporte profundo fuerte

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

    # ══════════════════════════════════════════════════════════
    # GAINX 999  —  CAMBIO DE SESGO | CHoCH H4 ALCISTA CONFIRMADO 30 MAY 2026
    # ══════════════════════════════════════════════════════════
    # CAMBIOS v4.13:
    #   [UPD] sesgo_h4: BEAR → BULL — CHoCH H4 confirmado, precio rompió
    #         último swing high bajista, EQH roto, estructura cambió
    #   [UPD] sesgo_diario: BEAR → NEUTRO — Daily aún no confirma HH+HL
    #         completo, esperar 2 HH diarios para pasar a BULL
    #   [UPD] ob_maestro: zona demanda activa H4 (83,485–83,600)
    #   [UPD] resistencias activas con niveles reales del chart
    #   NOTA: sesgo_macro sigue BEAR hasta que Daily confirme giro completo
    #         Precio actual: 84,039 | CHoCH H4 en ~84,040 | EQH roto
    # ══════════════════════════════════════════════════════════
    "GainX 999": {
        "simbolo":           "GainX 999",
        "tipo":              "Decreasing Index (999 ticks/salto)",
        "sesgo_macro":       "BEAR",        # Macro sigue bajista — Daily no confirmó giro
        "sesgo_diario":      "NEUTRO",      # Daily en transición — esperar 2 HH confirmados
        "sesgo_h4":          "BULL",        # CHoCH H4 confirmado 30-May — EQH roto

        # Rangos reales CSV (693 velas Daily)
        "rango_daily_avg":   584,
        "rango_daily_max":   855,
        "rango_h4_avg":      226,
        "rango_h1_avg":      103,
        "rango_m30_avg":     70,
        "rango_saturado":    855,

        # OB thresholds — P70 real
        "ob_h4_min":         168,
        "ob_h1_min":         84,
        "ob_m1_min":         6,
        "sl_minimo":         95,            # p75 rango H1 GainX 999
        "noise_candle_min":  2.5,           # vela mínima spike M1 (medida real GainX 999)
        "ob_h4_fuerte":      229,
        "ob_h1_fuerte":      114,

        # FVG thresholds — P70 M5 real
        "fvg_bull_fuerte":   12,
        "fvg_bear_fuerte":   12,
        "fvg_m15_fuerte":    36,

        # Horas activas — 24h (sintético, no aplica filtro de sesión)
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       12,            # pico histórico Londres
        "hora_peak_2":       16,            # pico NY overlap
        "hora_peak_3":       21,            # cierre NY

        # [NEW v4.12] Filtro de impulso M1 — distingue retroceso de impulso
        # Si la última vela M1 bajó MÁS de este valor → es impulso, NO retroceso
        # → bloquear entrada grid. Origen: 7-mayo -$16.90 por entrar en impulso -115pts
        "impulso_max_vela_m1":  15,         # pts máximos de caída en vela M1 para entrar

        # [NEW v4.12] Score mínimo elevado — índice errático, exigir mayor confluencia
        "score_minimo_entrada":  8,         # antes 7 — requiere más criterios alineados

        # OB Maestro actualizado 30-May-2026 — CHoCH H4 alcista
        # Zona de demanda que impulsó el CHoCH = OB bull H4
        "ob_maestro_low":    83485,         # zona gris H4 soporte — base del impulso CHoCH
        "ob_maestro_high":   83600,         # techo zona demanda H4

        # Fibonacci — ahora swing ALCISTA desde mínimo reciente
        # SL=83,280 (mínimo H4 actual) → SH=84,467 (resistencia amarilla visible)
        # rango=1,187pts
        "fib_swing_high":    84467.03,      # resistencia amarilla H4 (nivel visible)
        "fib_swing_low":     83280.33,      # mínimo H4 reciente
        "fib_23_6":          84187.0,       # retroceso leve
        "fib_38_2":          84013.0,       # zona actual — soporte inmediato
        "fib_50":            83873.0,       # soporte medio
        "fib_61_8":          83733.0,       # soporte fuerte
        "fib_78_6":          83546.0,       # soporte zona OB maestro

        # Resistencias activas (lo que frena la subida)
        "resistencia_1":     84467,         # nivel amarillo H4 — resistencia inmediata
        "resistencia_2":     84705,         # techo zona gris superior H4
        "resistencia_3":     85091,         # OB diario anterior — target grande

        # Soportes activos (lo que sostiene la subida)
        "soporte_1":         83947,         # nivel horizontal H4 (línea negra)
        "soporte_2":         83600,         # techo OB maestro — primer soporte
        "soporte_3":         83280,         # mínimo H4 reciente — invalidación

        # OBs críticos H4 activos — perspectiva alcista
        "ob_critico_bull_h4_low":   83485,  # zona demanda base CHoCH — la más fuerte
        "ob_critico_bull_h4_high":  83600,
        "ob_critico_bull_h4_2_low": 83729,  # zona gris H4 intermedia
        "ob_critico_bull_h4_2_high":83826,
        "ob_critico_bear_h4_low":   84467,  # resistencia amarilla — zona oferta
        "ob_critico_bear_h4_high":  84705,  # techo zona gris superior

        # FVGs actualizados — alcista
        "fvg_bull_activo_low":      83947,  # FVG bull activo — zona entrada
        "fvg_bull_activo_high":     84039,  # precio actual dentro de FVG
        "fvg_bear_activo_low":      84467,  # resistencia — FVG bear
        "fvg_bear_activo_high":     84705,

        "tf_principal":      "H4",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",

        # ── DIRECCIÓN ACTIVA v4.14 ──────────────────────────
        # Operar LONG aunque sesgo_macro=BEAR
        # Activar cuando hay CHoCH H4 confirmado (retroceso alcista)
        # Desactivar si precio cierra H1 bajo direccion_valida_hasta
        "direccion_activa":       "LONG",   # LONG | SHORT | None
        "direccion_valida_hasta":  83280,    # invalidación — mínimo H4 reciente
        "zona_retroceso_low":      83947,    # Zona B — FVG bull H1 activo
        "zona_retroceso_high":     84039,    # Zona B — techo FVG
        "tol_zona_m15":            95,       # tolerancia M15 = ATR_M15 × 2.5
    },

    # ══════════════════════════════════════════════════════════
    # GAINX 1200  —  BULL FUERTE CORTO | CSV REAL 25 MAY 2026
    # ══════════════════════════════════════════════════════════
    "GainX 1200": {
        "simbolo":           "GainX 1200",
        "tipo":              "Decreasing Index (1200 ticks/salto)",
        "sesgo_macro":       "BEAR",         # Monthly tendencia primaria bajista
        "sesgo_diario":      "BULL",         # Daily últimas 20 velas: 70% alcistas, drift +484pts
        "sesgo_h4":          "BULL",         # H4 impulso alcista desde 90,486 → 92,247 sin parar

        # Rangos (datos reales CSV — sin cambios, siguen vigentes)
        "rango_daily_avg":   324,
        "rango_daily_max":   617,
        "rango_h4_avg":      128,
        "rango_h1_avg":      60,
        "rango_m30_avg":     40,
        "rango_saturado":    550,

        # Thresholds OB — sin cambios
        "ob_h4_min":         90,
        "ob_h1_min":         40,
        "ob_m1_min":         5,             # cuerpo mín vela M1
        "sl_minimo":         55,            # p75 rango H1 GainX 1200
        "noise_candle_min":  1.2,           # vela mínima spike M1 (medida real GainX 1200)

        # Thresholds FVG — sin cambios
        "fvg_bull_fuerte":   75,
        "fvg_bear_fuerte":   50,

        # Horas activas — sin cambios
        "horas_activas_utc": list(range(0, 24)),
        "hora_peak_1":       5,
        "hora_peak_2":       7,
        "hora_peak_3":       9,

        # OB Maestro — actualizado: precio subió a 92,141, zona maestro sigue como soporte
        "ob_maestro_low":    90486,          # soporte absoluto vigente
        "ob_maestro_high":   90950,          # base del impulso alcista

        # Fibonacci swing bajista (Ene 23 → May 16, 2026) — sin cambios
        "fib_swing_high":    94225.31,
        "fib_swing_low":     90486.81,
        "fib_23_6":          91367.78,       # ← superada ✅
        "fib_38_2":          91914.92,       # ← superada ✅
        "fib_50":            92356.06,       # ← PRÓXIMA resistencia (~215pts)
        "fib_61_8":          92797.20,       # ← objetivo si rompe fib_50
        "fib_78_6":          91286.85,       # ya debajo del precio

        # Soportes — actualizados con precio en 92,141
        "soporte_1_low":     90400,          # ZONA A — soporte base, vigente
        "soporte_1_high":    90800,
        "soporte_2_low":     91250,          # ZONA B — nuevo soporte tras impulso
        "soporte_2_high":    91650,          # H4 múltiples toques en mayo
        "soporte_3_low":     91800,          # ZONA C — soporte más cercano (FVG H4 activo)
        "soporte_3_high":    91980,          # FVG H4 24-May sin mitigar

        # Resistencias — actualizadas
        "resistencia_1":     92247,          # máximo de hoy 25-May — nivel inmediato
        "resistencia_2":     92356,          # Fib 50% = resistencia clave
        "resistencia_3":     92797,          # Fib 61.8% = techo del rebote macro

        # OBs críticos activos H4 (25 Mayo 2026)
        # BULL sin retestear — zona de recompra si price retrocede:
        #   H4 OB Bull 24-May 08h: 91,764–91,983 (body=219pts, el más fuerte)
        #   H4 OB Bull 24-May 04h: 91,638–91,764 (body=126pts)
        #   H4 OB Bull 24-May 00h: 91,520–91,638 (body=118pts)
        # BEAR activo — zona de venta si price rebota:
        #   H4 OB Bear 25-May 16h: 92,144–92,239 (body=95pts) — PRECIO AQUÍ
        "ob_critico_bull_h4_low":   91764,
        "ob_critico_bull_h4_high":  91983,   # el más fuerte — body 219pts
        "ob_critico_bear_h4_low":   92144,
        "ob_critico_bear_h4_high":  92239,   # precio en esta zona ahora

        # OBs H1 activos sin retestear (25 Mayo 2026)
        "ob_critico_bull_h1_low":   91363,
        "ob_critico_bull_h1_high":  91532,   # 23-May 11h body=169pts — más fuerte H1
        "ob_critico_bear_h1_low":   92177,
        "ob_critico_bear_h1_high":  92227,   # 25-May 17h body=51pts — activo

        # FVGs H4 sin mitigar (25 Mayo 2026)
        "fvg_bull_activo_1_low":    91799,
        "fvg_bull_activo_1_high":   91976,   # H4 24-May — 177pts — EL MÁS FUERTE
        "fvg_bull_activo_2_low":    91643,
        "fvg_bull_activo_2_high":   91711,   # H4 24-May — 68pts
        "fvg_bull_activo_3_low":    91566,
        "fvg_bull_activo_3_high":   91638,   # H4 24-May — 71pts
        "fvg_bull_activo_4_low":    91282,
        "fvg_bull_activo_4_high":   91337,   # H4 22-May — 55pts — soporte lejano

        # Módulo M15 — precio cayendo desde 92,247, buscando soporte
        # Precio actual: 92,141 (bajando desde máximo del día)
        "modulo_m15_ob_low":        92086,   # base vela alcista 25-May 12h
        "modulo_m15_ob_high":       92144,   # cierre — zona soporte inmediata
        "modulo_m15_bos":           92247,   # máximo del día — BOS a vigilar

        # Soporte absoluto (mínimo histórico reciente) — sin cambios
        "soporte_absoluto":         90486,

        # Timeframes — sin cambios
        "tf_principal":      "H1",
        "tf_entrada":        "M15",
        "tf_confirmacion":   "M5",
    },

}

# ============================================================
# HELPERS DE ACCESO RÁPIDO
# ============================================================

def get_config(simbolo: str) -> dict:
    """Retorna la config de un símbolo. Ejemplo: get_config('GainX 1200')"""
    return INDICES_CONFIG.get(simbolo, {})


def get_direccion_activa(simbolo: str, precio_actual: float = None) -> str:
    """
    Retorna la dirección que el scanner debe operar para este símbolo.

    Si existe 'direccion_activa' en el config Y el precio no ha
    invalidado la zona → retorna esa dirección.
    Si no existe → usa sesgo_macro (BEAR=SHORT, BULL=LONG).

    Retorna: 'LONG' | 'SHORT'
    """
    cfg = get_config(simbolo)
    dir_activa  = cfg.get("direccion_activa", None)
    valida_hasta = cfg.get("direccion_valida_hasta", None)

    if dir_activa is not None:
        # Verificar invalidación por precio
        if precio_actual is not None and valida_hasta is not None:
            if dir_activa == "LONG" and precio_actual < valida_hasta:
                return "SHORT"    # precio rompió el soporte → vuelve SHORT
            if dir_activa == "SHORT" and precio_actual > valida_hasta:
                return "LONG"     # precio rompió la resistencia → vuelve LONG
        return dir_activa

    # Sin direccion_activa → usar sesgo_macro
    sesgo = cfg.get("sesgo_macro", "BEAR")
    return "LONG" if "BULL" in sesgo else "SHORT"


def es_bajista_config(simbolo: str, precio_actual: float = None) -> bool:
    """Helper: True si el scanner debe buscar SHORT en este símbolo ahora."""
    return get_direccion_activa(simbolo, precio_actual) == "SHORT"


def get_tol_zona_m15(simbolo: str, atr_m15: float = None) -> float:
    """
    Tolerancia de zona M15 para el símbolo.
    Si existe tol_zona_m15 en el config → usa ese valor.
    Si no → usa atr_m15 × 2.5 como fallback dinámico.
    """
    cfg = get_config(simbolo)
    tol_cfg = cfg.get("tol_zona_m15", None)
    if tol_cfg is not None:
        return float(tol_cfg)
    if atr_m15 is not None and atr_m15 > 0:
        return round(atr_m15 * 2.5, 1)
    return 40.0    # fallback original

def get_sesgo(simbolo: str, timeframe: str = "diario") -> str:
    """Retorna sesgo macro/diario/h4 de un símbolo"""
    cfg = get_config(simbolo)
    return cfg.get(f"sesgo_{timeframe}", "UNKNOWN")

def get_ob_maestro(simbolo: str) -> tuple:
    """Retorna (low, high) del OB Maestro"""
    cfg = get_config(simbolo)
    return cfg.get("ob_maestro_low", 0), cfg.get("ob_maestro_high", 0)

def precio_en_ob_maestro(simbolo: str, precio: float, tolerancia: float = 50) -> bool:
    """True si el precio está dentro o cerca del OB maestro"""
    low, high = get_ob_maestro(simbolo)
    if low == 0 or high == 0:
        return False
    return (low - tolerancia) <= precio <= (high + tolerancia)

def hora_activa(simbolo: str, hora_utc: int) -> bool:
    """True si la hora UTC está en la ventana activa del símbolo"""
    cfg = get_config(simbolo)
    horas = cfg.get("horas_activas_utc", list(range(0, 24)))
    return hora_utc in horas

def rango_saturado(simbolo: str, rango_actual: float) -> bool:
    """True si el rango actual supera el umbral de saturación"""
    cfg = get_config(simbolo)
    return rango_actual >= cfg.get("rango_saturado", 9999)

def ob_es_valido(simbolo: str, rango_ob: float, timeframe: str = "h4") -> bool:
    """True si el tamaño del OB supera el mínimo para ese TF"""
    cfg = get_config(simbolo)
    umbral = cfg.get(f"ob_{timeframe}_min", 0)
    return rango_ob >= umbral

def fvg_es_fuerte(simbolo: str, tamano_fvg: float, tipo: str = "bull") -> bool:
    """True si el FVG supera el umbral de 'fuerte' para el símbolo"""
    cfg = get_config(simbolo)
    umbral = cfg.get(f"fvg_{tipo}_fuerte", 0)
    return tamano_fvg >= umbral


# ============================================================
# LISTA DE SÍMBOLOS ACTIVOS EN EL SCANNER
# ============================================================
SIMBOLOS_ACTIVOS = [
    "PainX 400",
    "PainX 600",
    "PainX 800",
    "PainX 999",
    "PainX 1200",
    "GainX 400",
    "GainX 600",
    "GainX 800",
    "GainX 999",
    "GainX 1200",
]

# ============================================================
# METADATOS DE VERSIÓN
# ============================================================
VERSION = "4.13"
FECHA_ACTUALIZACION = "2026-06-02"
INDICES_CON_CSV_REAL = [
    "PainX 400",    # CSV real
    "PainX 600",    # CSV real — 31 May 2026 (699 velas Daily)
    "PainX 800",    # CSV real — 02 Jun 2026 (recalibrado completo)
    "GainX 400",    # CSV real — 31 May 2026 (881 velas Daily)
    "GainX 600",    # CSV real — actualizado 25 May 2026
    "GainX 800",    # CSV real — sesgo BEAR (no confundir con nombre)
    "GainX 999",    # CSV real + CHoCH H4 alcista 30-May-2026
    "GainX 1200",   # CSV real — 22 May 2026
    "B 1000 Idx.",  # CSV real — 25 May 2026 (Bridge)
]
INDICES_SIN_CSV = [
    "PainX 999",    # pendiente — pasar CSV
    "PainX 1200",   # pendiente — pasar CSV
]

# ============================================================
# SÍMBOLOS EXCLUSIVOS DE BRIDGE (no existen en Weltrade)
# Se agregan al scanner solo cuando BROKER_ACTIVO == "bridge"
# Agregar aquí cada nuevo índice Bridge que se perfila.
# ============================================================
SIMBOLOS_BRIDGE_EXTRA = [
    "B 1000 Idx.",   # Boom 1000 — Bull, spikes alcistas, perfilado 25 May 2026
    # "B 300 Idx.",  # pendiente perfilado
    # "B 500 Idx.",  # pendiente perfilado
    # "C 300 Idx.",  # pendiente perfilado
    # "C 500 Idx.",  # pendiente perfilado
    # "C 1000 Idx.", # pendiente perfilado
]

if __name__ == "__main__":
    print(f"Config v{VERSION} cargado — {len(INDICES_CONFIG)} índices")
    print(f"Con CSV real: {INDICES_CON_CSV_REAL}")
    print(f"Sin CSV: {INDICES_SIN_CSV}")
    for s in SIMBOLOS_ACTIVOS:
        cfg = get_config(s)
        print(f"  {s}: sesgo_macro={cfg.get('sesgo_macro')} | ob_h4_min={cfg.get('ob_h4_min')} | fvg_bull={cfg.get('fvg_bull_fuerte')}")

