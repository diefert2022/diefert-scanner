# ============================================================
#  institutional_setup_v6.py
#  Diefert Scanner — Módulo INDEPENDIENTE
#  Estrategia: Bias H4 → Swing Sweep → FVG reteste → CHoCH M1
#
#  FIXES v2:
#  [1] Sweep: tolerancia corregida (era invertida para GainX/PainX)
#  [2] FVG: ahora detecta RETESTE (precio llegando a la zona
#      desde afuera, no precio ya dentro hace rato)
#  [3] FVG antigüedad: solo FVGs de las últimas 20 velas M5
#
#  NO modifica ningún archivo existente del scanner.
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

# ── Tolerancias de sweep por índice (en puntos) ──────────────
SWEEP_TOLERANCIA = {
    "GainX 400":  15, "PainX 400":  15,
    "GainX 600":  20, "PainX 600":  20,
    "GainX 800":  18, "PainX 800":  18,
    "GainX 999":  30, "PainX 999":  30,
    "GainX 1200": 40, "PainX 1200": 40,
}

# ── FVG mínimo por índice (en puntos) ────────────────────────
FVG_MINIMO = {
    "GainX 400":  8,  "PainX 400":  8,
    "GainX 600": 12,  "PainX 600": 12,
    "GainX 800": 10,  "PainX 800": 10,
    "GainX 999": 20,  "PainX 999": 20,
    "GainX 1200":25,  "PainX 1200":25,
}

# ── Cuántas velas M5 atrás buscar FVGs ───────────────────────
FVG_MAX_VELAS = 20

# ── Tolerancia para considerar precio "tocando" el FVG ───────
# Precio debe estar dentro o a máx TOQUE_TOL pts del borde
TOQUE_TOL = 5


def _get_rates(simbolo, tf, n):
    rates = mt5.copy_rates_from_pos(simbolo, tf, 0, n)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


# ============================================================
#  PASO 1 — Bias H4 con EMA 21
# ============================================================
def _bias_h4(simbolo):
    df = _get_rates(simbolo, mt5.TIMEFRAME_H4, 50)
    if df is None:
        return False
    ema21    = df['close'].ewm(span=21, adjust=False).mean()
    precio   = df['close'].iloc[-1]
    ema_act  = ema21.iloc[-1]
    es_gainx = "GainX" in simbolo
    return precio > ema_act if es_gainx else precio < ema_act


# ============================================================
#  PASO 2 — Swing H4 más reciente
# ============================================================
def _swing_h4(simbolo):
    df = _get_rates(simbolo, mt5.TIMEFRAME_H4, 30)
    if df is None or len(df) < 5:
        return None
    es_gainx = "GainX" in simbolo
    niveles  = []
    for i in range(2, len(df) - 2):
        if es_gainx:
            # Swing LOW
            if (df['low'].iloc[i] < df['low'].iloc[i-1] and
                df['low'].iloc[i] < df['low'].iloc[i-2] and
                df['low'].iloc[i] < df['low'].iloc[i+1] and
                df['low'].iloc[i] < df['low'].iloc[i+2]):
                niveles.append(df['low'].iloc[i])
        else:
            # Swing HIGH
            if (df['high'].iloc[i] > df['high'].iloc[i-1] and
                df['high'].iloc[i] > df['high'].iloc[i-2] and
                df['high'].iloc[i] > df['high'].iloc[i+1] and
                df['high'].iloc[i] > df['high'].iloc[i+2]):
                niveles.append(df['high'].iloc[i])
    return niveles[-1] if niveles else None


# ============================================================
#  PASO 3 — Sweep confirmado
#  FIX: tolerancia correcta según dirección
#  GainX (busca sweep LOW):  mecha baja < swing_nivel
#                             cuerpo cierra > swing_nivel
#  PainX (busca sweep HIGH): mecha alta > swing_nivel
#                             cuerpo cierra < swing_nivel
# ============================================================
def _sweep_confirmado(simbolo, swing_nivel):
    if swing_nivel is None:
        return False
    df = _get_rates(simbolo, mt5.TIMEFRAME_M5, 15)
    if df is None:
        return False

    tol      = SWEEP_TOLERANCIA.get(simbolo, 20)
    es_gainx = "GainX" in simbolo

    for i in range(len(df) - 10, len(df) - 1):
        if i < 0:
            continue
        v = df.iloc[i]
        if es_gainx:
            # Mecha penetra BAJO el swing low, cuerpo cierra SOBRE él
            mecha_penetra  = v['low']  < swing_nivel
            cuerpo_adentro = min(v['open'], v['close']) > (swing_nivel - tol)
            if mecha_penetra and cuerpo_adentro:
                return True
        else:
            # Mecha penetra SOBRE el swing high, cuerpo cierra BAJO él
            mecha_penetra  = v['high'] > swing_nivel
            cuerpo_adentro = max(v['open'], v['close']) < (swing_nivel + tol)
            if mecha_penetra and cuerpo_adentro:
                return True
    return False


# ============================================================
#  PASO 4 — FVG: detectar RETESTE (no precio ya dentro)
#  FIX: el precio debe estar LLEGANDO al FVG desde afuera,
#       no flotando dentro desde hace velas.
#
#  Lógica:
#   - Busca FVGs en las últimas FVG_MAX_VELAS velas M5
#   - El FVG debe estar "fresco" (no mitigado = precio nunca
#     cerró dentro de él desde que se formó)
#   - El precio actual toca o está a TOQUE_TOL pts del borde
# ============================================================
def _fvg_reteste(simbolo, precio_actual):
    df = _get_rates(simbolo, mt5.TIMEFRAME_M5, FVG_MAX_VELAS + 3)
    if df is None or len(df) < 3:
        return None

    fvg_min  = FVG_MINIMO.get(simbolo, 12)
    es_gainx = "GainX" in simbolo
    fvgs     = []

    # Detectar todos los FVGs en la ventana
    for i in range(1, len(df) - 1):
        v1 = df.iloc[i - 1]
        v3 = df.iloc[i + 1]
        if es_gainx:
            gap = v3['low'] - v1['high']
            if gap >= fvg_min:
                fvgs.append({
                    'top': v3['low'],
                    'bot': v1['high'],
                    'mid': (v3['low'] + v1['high']) / 2,
                    'idx': i,
                    'tipo': 'BULL'
                })
        else:
            gap = v1['low'] - v3['high']
            if gap >= fvg_min:
                fvgs.append({
                    'top': v1['low'],
                    'bot': v3['high'],
                    'mid': (v1['low'] + v3['high']) / 2,
                    'idx': i,
                    'tipo': 'BEAR'
                })

    if not fvgs:
        return None

    # Verificar cuál FVG está siendo tocado AHORA (reteste)
    for fvg in reversed(fvgs):
        idx_fvg = fvg['idx']

        # Verificar que el FVG NO fue mitigado después de formarse
        # (ninguna vela posterior cerró dentro del gap)
        mitigado = False
        for j in range(idx_fvg + 2, len(df)):
            c = df.iloc[j]
            if es_gainx:
                # FVG alcista: mitigado si alguna vela cerró DENTRO (bajo el tope)
                if c['close'] < fvg['top'] and c['close'] > fvg['bot']:
                    mitigado = True
                    break
            else:
                # FVG bajista: mitigado si alguna vela cerró DENTRO (sobre el piso)
                if c['close'] > fvg['bot'] and c['close'] < fvg['top']:
                    mitigado = True
                    break

        if mitigado:
            continue

        # Verificar reteste: precio actual tocando el borde del FVG
        if es_gainx:
            # Precio llegando desde arriba hacia el FVG alcista
            tocando = (fvg['bot'] - TOQUE_TOL) <= precio_actual <= (fvg['top'] + TOQUE_TOL)
        else:
            # Precio llegando desde abajo hacia el FVG bajista
            tocando = (fvg['bot'] - TOQUE_TOL) <= precio_actual <= (fvg['top'] + TOQUE_TOL)

        if tocando:
            return fvg

    return None


# ============================================================
#  PASO 5 — Confirmación M1
# ============================================================
def _confirmacion_m1(simbolo):
    df = _get_rates(simbolo, mt5.TIMEFRAME_M1, 20)
    if df is None or len(df) < 4:
        return None

    es_gainx = "GainX" in simbolo
    ult  = df.iloc[-1]
    ant  = df.iloc[-2]

    rango = ult['high'] - ult['low']
    if rango == 0:
        return None

    mecha_inf = min(ult['open'], ult['close']) - ult['low']
    mecha_sup = ult['high'] - max(ult['open'], ult['close'])

    # Pin bar
    if es_gainx and mecha_inf / rango > 0.60:
        return "PIN_BAR"
    if not es_gainx and mecha_sup / rango > 0.60:
        return "PIN_BAR"

    # Engulfing
    rango_ant = ant['high'] - ant['low']
    if rango_ant > 0 and rango > rango_ant * 0.90:
        if es_gainx and ult['close'] > ult['open']:
            return "ENGULFING"
        if not es_gainx and ult['close'] < ult['open']:
            return "ENGULFING"

    # CHoCH M1
    if es_gainx and ult['close'] > ant['high']:
        return "CHOCH_M1"
    if not es_gainx and ult['close'] < ant['low']:
        return "CHOCH_M1"

    return None


# ============================================================
#  PASO 6 — SL / TP desde la zona FVG
# ============================================================
def _calcular_sl_tp(simbolo, precio_actual, fvg):
    es_gainx = "GainX" in simbolo
    tol = SWEEP_TOLERANCIA.get(simbolo, 20)
    if es_gainx:
        sl  = fvg['bot'] - tol
        tp1 = precio_actual + (precio_actual - sl) * 1.5
        tp2 = precio_actual + (precio_actual - sl) * 3.0
    else:
        sl  = fvg['top'] + tol
        tp1 = precio_actual - (sl - precio_actual) * 1.5
        tp2 = precio_actual - (sl - precio_actual) * 3.0
    return round(sl, 2), round(tp1, 2), round(tp2, 2)


# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================
def evaluar_setup_institucional(simbolo, precio_actual):
    """
    5 pasos institucionales:
      1. Bias H4 (EMA21)
      2. Swing H4 relevante
      3. Sweep confirmado (mecha + cuerpo adentro)
      4. FVG en reteste (precio llegando, no ya dentro)
      5. Confirmación M1 (pin bar / engulfing / CHoCH)
    """
    base = {
        'detectado':    False,
        'simbolo':      simbolo,
        'direccion':    'LONG' if 'GainX' in simbolo else 'SHORT',
        'entrada':      precio_actual,
        'sl':           None,
        'tp1':          None,
        'tp2':          None,
        'confirmacion': None,
        'descripcion':  '',
    }

    if not _bias_h4(simbolo):
        return base

    swing = _swing_h4(simbolo)
    if swing is None:
        return base

    if not _sweep_confirmado(simbolo, swing):
        return base

    # FIX: usa _fvg_reteste en lugar de _fvg_cercano
    fvg = _fvg_reteste(simbolo, precio_actual)
    if fvg is None:
        return base

    conf = _confirmacion_m1(simbolo)
    if conf is None:
        return base

    sl, tp1, tp2 = _calcular_sl_tp(simbolo, precio_actual, fvg)
    dir_txt = "📈 LONG" if 'GainX' in simbolo else "📉 SHORT"
    dist_sl = abs(precio_actual - sl)
    rr      = round(abs(tp1 - precio_actual) / dist_sl, 1) if dist_sl > 0 else 0

    base.update({
        'detectado':    True,
        'sl':           sl,
        'tp1':          tp1,
        'tp2':          tp2,
        'confirmacion': conf,
        'descripcion': (
            f"🏛 SETUP INSTITUCIONAL | {simbolo}\n"
            f"{dir_txt} | Conf: {conf}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Entrada: {precio_actual:.2f}\n"
            f"🛑 SL: {sl:.2f} ({dist_sl:.0f} pts)\n"
            f"🎯 TP1: {tp1:.2f}  RR {rr}:1\n"
            f"🎯 TP2: {tp2:.2f}  RR {rr*2:.1f}:1\n"
            f"📐 FVG zona: {fvg['bot']:.2f}–{fvg['top']:.2f}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    })

    return base
