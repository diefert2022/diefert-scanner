# ============================================================
#  DIEFERT SCANNER v6 — contexto_inicial.py
#
#  MÓDULO INDEPENDIENTE — NO modifica ningún archivo existente.
#  Principio de adición: solo suma información, nunca bloquea.
#
#  QUÉ HACE:
#  ─────────────────────────────────────────────────────────
#  Corre UNA SOLA VEZ al arrancar el scanner, ANTES del loop
#  de 3 segundos. Analiza cada índice de mayor a menor TF:
#
#    D1  → tendencia macro, rango del día, PDH/PDL
#    H4  → estructura intermedia, bias
#    H1  → rango P/D real (alimenta pd_filter_v6)
#    M15 → CHoCH/BOS reciente
#    M5  → contexto inmediato
#
#  EL PROBLEMA QUE RESUELVE:
#  ─────────────────────────────────────────────────────────
#  Al apagar en la noche y reiniciar en la mañana, los
#  sintéticos siguieron moviéndose. Si el scanner calcula
#  el rango P/D solo con swings recientes puede capturar
#  un swing de 2 horas que no representa el rango real.
#
#  La solución: al arrancar, calcular el contexto macro
#  completo y guardarlo en CONTEXTO[simbolo]. El ciclo de
#  3s solo actualiza M1/M5 — no recalcula D1/H4/H1 cada vez.
#
#  ACTUALIZACIÓN PERIÓDICA:
#  ─────────────────────────────────────────────────────────
#  El contexto macro no es estático. Se refresca cada
#  REFRESH_MINUTOS (default 60 min) para capturar cambios
#  de tendencia en H1/H4 sin tener que reiniciar el scanner.
#
#  CONTENIDO DE CONTEXTO[simbolo]:
#  ─────────────────────────────────────────────────────────
#  {
#    # ── Macro D1 ──────────────────────────────────────────
#    'tendencia_d1':    'alcista' / 'bajista' / 'neutro'
#    'rango_d1':        pts del rango del día actual
#    'pdh':             Previous Day High
#    'pdl':             Previous Day Low
#    'precio_apertura': apertura del día actual
#
#    # ── Intermedio H4 ─────────────────────────────────────
#    'tendencia_h4':    'alcista' / 'bajista' / 'neutro'
#    'swing_high_h4':   último SH en H4
#    'swing_low_h4':    último SL en H4
#    'ob_h4':           True/False — hay OB H4 cercano al precio
#
#    # ── Rango P/D real H1 ─────────────────────────────────
#    'swing_high_h1':   SH del rango P/D (alimenta pd_filter_v6)
#    'swing_low_h1':    SL del rango P/D
#    'equilibrium_h1':  50% del rango H1
#    'rango_h1':        pts del rango H1
#
#    # ── Estructura M15 ────────────────────────────────────
#    'tendencia_m15':   'alcista' / 'bajista' / 'neutro'
#    'ultimo_bos_m15':  'alcista' / 'bajista' / None
#
#    # ── Contexto M5 ───────────────────────────────────────
#    'tendencia_m5':    'alcista' / 'bajista' / 'neutro'
#
#    # ── Resumen ejecutivo ─────────────────────────────────
#    'bias_general':    'ALCISTA' / 'BAJISTA' / 'MIXTO' / 'NEUTRO'
#    'alineado':        True si D1+H4+M15 apuntan en la misma dirección
#    'precio_actual':   último precio conocido
#    'timestamp':       cuando se calculó este contexto
#  }
#
#  USO EN main_v5.py:
#  ─────────────────────────────────────────────────────────
#  # Al arrancar (antes del loop):
#  from contexto_inicial import inicializar_contexto, obtener_contexto, refrescar_si_necesario
#  inicializar_contexto()   # corre una vez, tarda ~30s
#
#  # En cada ciclo:
#  refrescar_si_necesario()  # solo actúa si pasaron 60 min
#  ctx = obtener_contexto('GainX 600')
#  print(ctx['bias_general'])   # → 'ALCISTA'
#  print(ctx['alineado'])       # → True/False
# ============================================================

import time
from datetime import datetime
from utils import obtener_df
from estructura import detectar_swings, detectar_tendencia, detectar_bos_choch
# imports corregidos — TF_D1 no existe en config.py
import MetaTrader5 as mt5
TF_D1 = mt5.TIMEFRAME_D1   # definido aqui directamente
from config import (
    SIMBOLOS,
    TF_H4, TF_H1, TF_M15, TF_M5,
    VELAS_H4, VELAS_H1, VELAS_M15, VELAS_M5,
)

# ── Parámetros ────────────────────────────────────────────
REFRESH_MINUTOS = 60     # refrescar contexto macro cada 60 min
VELAS_D1        = 10     # últimos 10 días para D1
VELAS_H4_CTX    = 200    # ~33 días para H4

# ── Almacén global ────────────────────────────────────────
CONTEXTO = {}            # {simbolo: dict_contexto}
_ultimo_refresh = 0      # timestamp del último cálculo


# ============================================================
#  HELPERS INTERNOS
# ============================================================

def _tendencia_simple(df, ventana_swing=5):
    """
    Detecta tendencia desde un dataframe.
    Retorna 'alcista', 'bajista' o 'neutro'.
    """
    if df is None or len(df) < ventana_swing * 2 + 5:
        return 'neutro'
    swings = detectar_swings(df, ventana=ventana_swing)
    return detectar_tendencia(swings)


def _pdh_pdl(df_d1):
    """
    Previous Day High y Previous Day Low desde D1.
    Retorna (pdh, pdl, apertura_hoy, rango_hoy).
    """
    if df_d1 is None or len(df_d1) < 2:
        return None, None, None, None

    # Penúltima vela = día anterior completo
    ayer      = df_d1.iloc[-2]
    hoy       = df_d1.iloc[-1]
    pdh       = round(float(ayer['high']), 2)
    pdl       = round(float(ayer['low']),  2)
    apertura  = round(float(hoy['open']),  2)
    rango_hoy = round(float(hoy['high']) - float(hoy['low']), 2)

    return pdh, pdl, apertura, rango_hoy


def _rango_h1(df_h1, simbolo):
    """
    Calcula swing_high y swing_low H1 con validación de rango
    usando los mismos límites de pd_filter_v6.
    Retorna (swing_high, swing_low, equilibrium, rango_pts).
    """
    RANGO_MINIMO = {
        'PainX 1200': 1200, 'GainX 1200': 1200,
        'PainX 999':  2500, 'GainX 999':  2500,
        'PainX 800':   350, 'GainX 800':   350,
        'PainX 600':   600, 'GainX 600':   600,
        'PainX 400':   450, 'GainX 400':   450,
    }
    RANGO_MAXIMO = {
        'PainX 1200': 2000, 'GainX 1200': 2000,
        'PainX 999':  5000, 'GainX 999':  5000,
        'PainX 800':   600, 'GainX 800':   600,
        'PainX 600':   900, 'GainX 600':   900,
        'PainX 400':   700, 'GainX 400':   700,
    }

    if df_h1 is None or len(df_h1) < 20:
        return None, None, None, None

    swings = detectar_swings(df_h1, ventana=5)
    sh = next((s for s in reversed(swings) if s['tipo'] == 'SH'), None)
    sl = next((s for s in reversed(swings) if s['tipo'] == 'SL'), None)

    if sh is None or sl is None:
        return None, None, None, None

    swing_high = sh['precio']
    swing_low  = sl['precio']

    rango_min = RANGO_MINIMO.get(simbolo, 100)
    rango_max = RANGO_MAXIMO.get(simbolo, 99999)
    rango     = swing_high - swing_low

    # Si el rango está fuera de los límites esperados → fallback 50 velas
    if rango < rango_min or rango > rango_max:
        swing_high = round(df_h1.tail(50)['high'].max(), 2)
        swing_low  = round(df_h1.tail(50)['low'].min(),  2)
        rango      = swing_high - swing_low

    if rango <= 0:
        return None, None, None, None

    equilibrium = round(swing_low + rango * 0.5, 2)
    return swing_high, swing_low, equilibrium, round(rango, 2)


def _bias_general(t_d1, t_h4, t_m15, es_bajista):
    """
    Determina el bias combinando D1 + H4 + M15.
    Para PainX (es_bajista=True) el bias "correcto" es bajista.
    Para GainX (es_bajista=False) el bias "correcto" es alcista.

    Retorna:
      bias_general: 'ALCISTA' / 'BAJISTA' / 'MIXTO' / 'NEUTRO'
      alineado:     True si los 3 TF apuntan en dirección del índice
    """
    tendencias = [t_d1, t_h4, t_m15]
    alcistas   = tendencias.count('alcista')
    bajistas   = tendencias.count('bajista')

    if alcistas >= 2:
        bias = 'ALCISTA'
    elif bajistas >= 2:
        bias = 'BAJISTA'
    elif alcistas == 0 and bajistas == 0:
        bias = 'NEUTRO'
    else:
        bias = 'MIXTO'

    # Alineación con la dirección natural del índice
    if es_bajista:
        alineado = bias == 'BAJISTA'
    else:
        alineado = bias == 'ALCISTA'

    return bias, alineado


# ============================================================
#  FUNCIÓN PRINCIPAL — calcular contexto de un símbolo
# ============================================================

def _calcular_contexto_simbolo(simbolo):
    """
    Analiza un símbolo de D1 a M5 y retorna su contexto completo.
    Tarda ~3-5 segundos por símbolo (peticiones a MT5).
    """
    es_bajista = simbolo.startswith('PainX')

    ctx = {
        # D1
        'tendencia_d1':    'neutro',
        'rango_d1':        None,
        'pdh':             None,
        'pdl':             None,
        'precio_apertura': None,
        # H4
        'tendencia_h4':    'neutro',
        'swing_high_h4':   None,
        'swing_low_h4':    None,
        # H1
        'swing_high_h1':   None,
        'swing_low_h1':    None,
        'equilibrium_h1':  None,
        'rango_h1':        None,
        # M15
        'tendencia_m15':   'neutro',
        'ultimo_bos_m15':  None,
        # M5
        'tendencia_m5':    'neutro',
        # Resumen
        'bias_general':    'NEUTRO',
        'alineado':        False,
        'precio_actual':   None,
        'timestamp':       datetime.now().strftime('%H:%M:%S'),
    }

    try:
        # ── D1 ────────────────────────────────────────────
        df_d1 = obtener_df(simbolo, TF_D1, VELAS_D1)
        if df_d1 is not None and len(df_d1) >= 3:
            ctx['tendencia_d1'] = _tendencia_simple(df_d1, ventana_swing=2)
            pdh, pdl, apertura, rango_hoy = _pdh_pdl(df_d1)
            ctx['pdh']             = pdh
            ctx['pdl']             = pdl
            ctx['precio_apertura'] = apertura
            ctx['rango_d1']        = rango_hoy

        # ── H4 ────────────────────────────────────────────
        df_h4 = obtener_df(simbolo, TF_H4, VELAS_H4_CTX)
        if df_h4 is not None and len(df_h4) >= 20:
            ctx['tendencia_h4'] = _tendencia_simple(df_h4, ventana_swing=5)
            swings_h4 = detectar_swings(df_h4, ventana=5)
            sh4 = next((s for s in reversed(swings_h4) if s['tipo'] == 'SH'), None)
            sl4 = next((s for s in reversed(swings_h4) if s['tipo'] == 'SL'), None)
            if sh4:
                ctx['swing_high_h4'] = sh4['precio']
            if sl4:
                ctx['swing_low_h4']  = sl4['precio']

        # ── H1 (rango P/D) ────────────────────────────────
        df_h1 = obtener_df(simbolo, TF_H1, VELAS_H1)
        if df_h1 is not None:
            sh1, sl1, eq1, rng1 = _rango_h1(df_h1, simbolo)
            ctx['swing_high_h1']  = sh1
            ctx['swing_low_h1']   = sl1
            ctx['equilibrium_h1'] = eq1
            ctx['rango_h1']       = rng1

        # ── M15 ───────────────────────────────────────────
        df_m15 = obtener_df(simbolo, TF_M15, VELAS_M15)
        if df_m15 is not None and len(df_m15) >= 20:
            ctx['tendencia_m15'] = _tendencia_simple(df_m15, ventana_swing=4)
            swings_m15 = detectar_swings(df_m15, ventana=4)
            bos = detectar_bos_choch(df_m15, swings_m15, ctx['tendencia_m15'])
            if bos:
                ctx['ultimo_bos_m15'] = bos['direccion']

        # ── M5 ────────────────────────────────────────────
        df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
        if df_m5 is not None and len(df_m5) >= 20:
            ctx['tendencia_m5'] = _tendencia_simple(df_m5, ventana_swing=3)
            ctx['precio_actual'] = round(float(df_m5['close'].iloc[-1]), 2)

        # ── Bias general ──────────────────────────────────
        bias, alineado = _bias_general(
            ctx['tendencia_d1'],
            ctx['tendencia_h4'],
            ctx['tendencia_m15'],
            es_bajista,
        )
        ctx['bias_general'] = bias
        ctx['alineado']     = alineado

    except Exception as e:
        print(f"  [contexto] Error calculando {simbolo}: {e}")

    return ctx


# ============================================================
#  API PÚBLICA
# ============================================================

def inicializar_contexto():
    """
    Corre UNA VEZ al arrancar el scanner.
    Analiza todos los símbolos de D1 a M5.
    Muestra progreso en consola.
    Tarda ~30-60 segundos total.
    """
    global _ultimo_refresh
    print("\n  📊 Analizando contexto macro de todos los índices...")
    print(f"  {'─' * 70}")

    for simbolo in SIMBOLOS:
        print(f"  🔍 [{simbolo}] D1 → H4 → H1 → M15 → M5...", end=' ', flush=True)
        t0  = time.time()
        ctx = _calcular_contexto_simbolo(simbolo)
        CONTEXTO[simbolo] = ctx
        seg = time.time() - t0

        # Resumen en una línea
        bias     = ctx['bias_general']
        alineado = '✅' if ctx['alineado'] else '⚠️'
        pdh      = f"PDH={ctx['pdh']:.0f}" if ctx['pdh'] else 'PDH=?'
        pdl      = f"PDL={ctx['pdl']:.0f}" if ctx['pdl'] else 'PDL=?'
        eq       = f"EQ={ctx['equilibrium_h1']:.0f}" if ctx['equilibrium_h1'] else 'EQ=?'
        rng      = f"Rango={ctx['rango_h1']:.0f}pts" if ctx['rango_h1'] else ''

        print(f"{alineado} {bias} | {pdh} {pdl} | {eq} {rng} ({seg:.1f}s)")

    _ultimo_refresh = time.time()
    print(f"  {'─' * 70}")
    print(f"  ✅ Contexto macro listo — {len(SIMBOLOS)} índices analizados\n")


def obtener_contexto(simbolo):
    """
    Retorna el contexto calculado de un símbolo.
    Si no existe (no se llamó inicializar_contexto), retorna dict vacío.
    """
    return CONTEXTO.get(simbolo, {})


def refrescar_si_necesario():
    """
    Llama esto en cada ciclo del loop principal.
    Solo actúa si pasaron REFRESH_MINUTOS desde el último cálculo.
    No bloquea el ciclo — corre en el mismo hilo pero es rápido
    porque actualiza de a un símbolo por vez en ciclos distintos.

    Para no congelar el scanner, actualiza 1 símbolo por llamada
    en orden rotativo. Con 10 símbolos y ciclos de 3s → cada
    símbolo se refresca cada 30s dentro de la ventana de 60min.
    """
    global _ultimo_refresh

    ahora = time.time()
    if ahora - _ultimo_refresh < REFRESH_MINUTOS * 60:
        return   # aún no es hora

    # Refrescar todos de una vez (corre cada 60 min)
    print(f"\n  🔄 Refrescando contexto macro ({datetime.now().strftime('%H:%M')})...")
    for simbolo in SIMBOLOS:
        try:
            CONTEXTO[simbolo] = _calcular_contexto_simbolo(simbolo)
        except Exception as e:
            print(f"  [contexto] Error refrescando {simbolo}: {e}")

    _ultimo_refresh = ahora
    print(f"  ✅ Contexto actualizado\n")


def imprimir_resumen_contexto():
    """
    Imprime tabla de contexto macro de todos los índices.
    Útil para debugging o comando Telegram /contexto.
    """
    print(f"\n  {'═' * 90}")
    print(f"  ║  CONTEXTO MACRO — {datetime.now().strftime('%H:%M:%S')}")
    print(f"  {'═' * 90}")
    print(f"  {'SÍMBOLO':<14} {'BIAS':<8} {'D1':<8} {'H4':<8} {'M15':<8} {'EQ H1':>8} {'RANGO':>7} {'PDH':>8} {'PDL':>8}")
    print(f"  {'─' * 90}")

    for simbolo in SIMBOLOS:
        ctx = CONTEXTO.get(simbolo, {})
        if not ctx:
            print(f"  {simbolo:<14} SIN DATOS")
            continue

        icono    = '⚠️ ' if not ctx.get('alineado') else '✅ '
        bias     = ctx.get('bias_general', '?')[:7]
        t_d1     = ctx.get('tendencia_d1', '?')[:6]
        t_h4     = ctx.get('tendencia_h4', '?')[:6]
        t_m15    = ctx.get('tendencia_m15', '?')[:6]
        eq       = f"{ctx['equilibrium_h1']:.0f}" if ctx.get('equilibrium_h1') else '?'
        rng      = f"{ctx['rango_h1']:.0f}" if ctx.get('rango_h1') else '?'
        pdh      = f"{ctx['pdh']:.0f}" if ctx.get('pdh') else '?'
        pdl      = f"{ctx['pdl']:.0f}" if ctx.get('pdl') else '?'

        print(f"  {icono}{simbolo:<12} {bias:<8} {t_d1:<8} {t_h4:<8} {t_m15:<8} {eq:>8} {rng:>7} {pdh:>8} {pdl:>8}")

    print(f"  {'═' * 90}\n")
