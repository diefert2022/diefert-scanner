# ============================================================
#  DIEFERT SCANNER — analisis_demanda.py
#  Versión: 1.0
#
#  PARA QUÉ SIRVE:
#  ─────────────────────────────────────────────────────────
#  Análisis completo bajo demanda para un índice específico.
#  Evalúa el mercado actual con todos los parámetros del
#  scanner y produce un reporte con entradas posibles para:
#    → SCALPING  (M1/M5, entrada rápida, SL ajustado)
#    → INTRADÍA  (M15/H1, entrada en zona, TP2)
#    → SWING     (H4, tendencia mayor, TP amplio)
#
#  CÓMO ACTIVARLO:
#  ─────────────────────────────────────────────────────────
#  1. CONSOLA: mientras el scanner corre, escribe en otra
#     terminal:
#       python analisis_demanda.py GainX 600
#       python analisis_demanda.py PainX 400
#
#  2. TELEGRAM: envía al bot del scanner:
#       /analisis GainX 600
#       /analisis PainX 400
#
#  Para recibir por Telegram mientras el scanner corre,
#  agrega en main_v4.py dentro del loop:
#       from analisis_demanda import verificar_comando_telegram
#       verificar_comando_telegram()
#
#  RESULTADO en Telegram:
#  ─────────────────────────────────────────────────────────
#  📊 ANÁLISIS DIEFERT — GainX 600
#  ──────────────────────────────────
#  💰 Precio actual: 110,542
#  📐 Sesgo macro: BULL | H1=alcista ✅
#  ──────────────────────────────────
#  🔵 OB H1: 110,450–110,650 (a 92pts)
#  🔵 FVG H1: 110,380–110,420
#  🟡 OB M15: 110,510–110,530 ← precio en zona
#  🟡 FVG M15: 110,490–110,510
#  🔴 OB M1: 110,538–110,545 ← trigger
#  ──────────────────────────────────
#  📈 Score POI: 8/10 — FUERTE
#  ──────────────────────────────────
#  ⚡ SCALP:
#     Entrada: 110,538 | SL: 110,490 (48pts)
#     TP1: 110,625 RR 1.8 | TP2: 110,720 RR 3.8
#  🎯 INTRADÍA:
#     Entrada: 110,520 | SL: 110,450 (70pts)
#     TP1: 110,650 RR 1.9 | TP2: 110,780 RR 3.7
#  📅 SWING:
#     Entrada: 110,500 | SL: 110,380 (120pts)
#     TP1: 110,750 RR 2.1 | TP2: 111,100 RR 5.0
#  ──────────────────────────────────
#  ⏰ 15:42:10 UTC-5
# ============================================================

import sys
import time
import threading
import requests
from datetime import datetime

# ── Importar módulos del scanner ──────────────────────────
import MetaTrader5 as mt5
from config import (
    TF_M1, TF_M5, TF_M15, TF_H1,
    VELAS_M1, VELAS_M5, VELAS_M15, VELAS_H1,
    SIMBOLOS_BAJISTAS,
)
TF_H4 = mt5.TIMEFRAME_H4  # no está en config.py, lo tomamos directo de MT5
from config_v413 import INDICES_CONFIG as _INDICES_CONFIG_MACRO
from utils import obtener_df, enviar_telegram
from estructura import detectar_swings, detectar_tendencia, detectar_bos_choch

# v5: stubs para módulos del v4 no disponibles
def detectar_reaccion_scalping(*a, **k): return False, "neutral", 0
def detectar_obs_m1(simbolo, es_bajista): return []
def analizar_liquidez(simbolo): return {'bsl': [], 'ssl': []}


from broker import nombre_real, detectar_y_configurar

# ── Configuración Telegram ────────────────────────────────
# Importa las mismas credenciales que usa el scanner
# Credenciales directas desde config.py
try:
    from config import TOKEN as TELEGRAM_TOKEN, CHAT_ID as TELEGRAM_CHAT_ID
except Exception:
    TELEGRAM_TOKEN   = ''
    TELEGRAM_CHAT_ID = ''

# Intervalo de polling para comandos Telegram (segundos)
POLLING_INTERVALO = 5
_ultimo_update_id = 0
_hilo_telegram    = None


# ============================================================
#  FUNCIÓN PRINCIPAL — ANÁLISIS COMPLETO
# ============================================================

def analizar_demanda(simbolo: str) -> str:
    """
    Ejecuta análisis completo del símbolo y retorna
    el reporte formateado como string (para consola o Telegram).
    """
    es_bajista = simbolo in SIMBOLOS_BAJISTAS

    # ── Precio actual ─────────────────────────────────────
    tick = mt5.symbol_info_tick(nombre_real(simbolo))
    if tick is None:
        return f"❌ No se pudo obtener precio de {simbolo}. ¿MT5 abierto?"
    precio = round((tick.bid + tick.ask) / 2, 2)

    # ── Datos por timeframe ───────────────────────────────
    df_m1  = obtener_df(simbolo, TF_M1,  VELAS_M1)
    df_m5  = obtener_df(simbolo, TF_M5,  VELAS_M5)
    df_m15 = obtener_df(simbolo, TF_M15, VELAS_M15)
    df_h1  = obtener_df(simbolo, TF_H1,  VELAS_H1)
    df_h4  = obtener_df(simbolo, TF_H4,  200)  # H4 para swing

    # ── Sesgo H1 ──────────────────────────────────────────
    sesgo_txt   = "sin datos"
    tendencia_h1 = "neutro"
    choch_txt   = ""
    if df_h1 is not None and len(df_h1) >= 20:
        swings_h1    = detectar_swings(df_h1, ventana=5)
        tendencia_h1 = detectar_tendencia(swings_h1)
        choch_h1     = detectar_bos_choch(df_h1, swings_h1, tendencia_h1)
        sesgo_config = _INDICES_CONFIG_MACRO.get(simbolo, {}).get('sesgo_diario', '')
        alineado = (
            (es_bajista and tendencia_h1 == "bajista") or
            (not es_bajista and tendencia_h1 == "alcista") or
            tendencia_h1 == "neutro"
        )
        sesgo_txt = (
            f"{sesgo_config} | H1={tendencia_h1} "
            f"{'✅' if alineado else '⚠️ EN CONTRA'}"
        )
        if choch_h1 and choch_h1["tipo"] == "CHoCH":
            choch_txt = f" | CHoCH H1 {choch_h1['direccion']}"

    # ── OBs y FVGs por TF ─────────────────────────────────
    obs_h1   = _detectar_obs(df_h1,  es_bajista, ventana=4, tol=300)
    fvgs_h1  = _detectar_fvgs(df_h1, es_bajista, tol=300)
    obs_m15  = _detectar_obs(df_m15, es_bajista, ventana=3, tol=150)
    fvgs_m15 = _detectar_fvgs(df_m15, es_bajista, tol=150)
    obs_m1   = detectar_obs_m1(simbolo, es_bajista)
    obs_m1_frescos = [ob for ob in obs_m1 if not ob.get('mitigado', False)]

    # ── H4 para swing ─────────────────────────────────────
    obs_h4  = _detectar_obs(df_h4, es_bajista, ventana=5, tol=600) if df_h4 is not None else []
    fvgs_h4 = _detectar_fvgs(df_h4, es_bajista, tol=600) if df_h4 is not None else []
    tendencia_h4 = "neutro"
    if df_h4 is not None and len(df_h4) >= 20:
        sw_h4 = detectar_swings(df_h4, ventana=5)
        tendencia_h4 = detectar_tendencia(sw_h4)

    # ── Liquidez ──────────────────────────────────────────
    liq = analizar_liquidez(simbolo)
    liq_bsl = liq.get('bsl', [])[:2]
    liq_ssl = liq.get('ssl', [])[:2]

    # ── Score POI v5 — conteo simple de confluencias ─────
    poi_score = 0
    if obs_h1:   poi_score += 2
    if fvgs_h1:  poi_score += 1
    if obs_m15:  poi_score += 2
    if fvgs_m15: poi_score += 1
    if obs_h4:   poi_score += 2
    if obs_m1:   poi_score += 2
    nivel_txt = "FUERTE" if poi_score >= 7 else "MEDIA" if poi_score >= 4 else "BAJA"
    poi_txt   = f"{poi_score}/10 — {nivel_txt}"
    poi_desglose = {}

    # ── Reacción M1 ───────────────────────────────────────
    m1_ok, m1_label, m1_score_val = detectar_reaccion_scalping(df_m1, es_bajista)
    m1_txt = f"⚡ {m1_label}" if m1_ok else "📵 neutral"

    # ── Construir entradas por tipo ───────────────────────
    scalp   = _entrada_scalp(precio, obs_m1_frescos, obs_m15, es_bajista, simbolo)
    intradia = _entrada_intradia(precio, obs_h1, fvgs_h1, obs_m15, es_bajista, simbolo)
    swing   = _entrada_swing(precio, obs_h4, fvgs_h4, tendencia_h4, es_bajista, simbolo)

    # ══════════════════════════════════════════════════════
    #  ARMAR REPORTE
    # ══════════════════════════════════════════════════════
    icono = "📉" if es_bajista else "📈"
    lineas = [
        f"{'─'*36}",
        f"📊 <b>ANÁLISIS DIEFERT — {simbolo}</b>",
        f"{'─'*36}",
        f"{icono} Precio actual: <b>{precio:,.0f}</b>",
        f"📐 Sesgo: {sesgo_txt}{choch_txt}",
        f"{'─'*36}",
        "<b>ZONAS DETECTADAS:</b>",
    ]

    # H4
    if obs_h4:
        z = obs_h4[0]
        lineas.append(f"  🟣 OB H4:  {z['low']:,.0f}–{z['high']:,.0f}  (dist {z['dist']:.0f}pts)")
    if fvgs_h4:
        z = fvgs_h4[0]
        lineas.append(f"  🟣 FVG H4: {z['low']:,.0f}–{z['high']:,.0f}")

    # H1
    for z in obs_h1[:2]:
        en = " ← precio aquí" if z['en_zona'] else f"  dist {z['dist']:.0f}pts"
        lineas.append(f"  🔵 OB H1:  {z['low']:,.0f}–{z['high']:,.0f}{en}")
    for z in fvgs_h1[:2]:
        en = " ← precio aquí" if z['en_zona'] else ""
        lineas.append(f"  🔵 FVG H1: {z['low']:,.0f}–{z['high']:,.0f}{en}")

    # M15
    for z in obs_m15[:2]:
        en = " ← precio aquí" if z['en_zona'] else f"  dist {z['dist']:.0f}pts"
        lineas.append(f"  🟡 OB M15: {z['low']:,.0f}–{z['high']:,.0f}{en}")
    for z in fvgs_m15[:2]:
        en = " ← precio aquí" if z['en_zona'] else ""
        lineas.append(f"  🟡 FVG M15:{z['low']:,.0f}–{z['high']:,.0f}{en}")

    # M1
    for ob in obs_m1_frescos[:2]:
        lineas.append(
            f"  🔴 OB M1:  {ob['ob_low']:,.0f}–{ob['ob_high']:,.0f}  ← trigger"
        )

    # Liquidez
    niveles_liq = liq_bsl if es_bajista else liq_ssl
    for b in niveles_liq[:2]:
        lineas.append(f"  💧 LIQ:    {b['nivel']:,.0f}  ({b['distancia']:.0f}pts)")

    # Score POI
    lineas += [
        f"{'─'*36}",
        f"📈 Score POI: {poi_txt}",
        f"   M1: {m1_txt}",
        f"{'─'*36}",
        "<b>ENTRADAS POSIBLES:</b>",
    ]

    # Scalping
    if scalp:
        lineas.append(f"\n⚡ <b>SCALP</b> (M1/M5 — entrada rápida):")
        lineas.append(f"   Entrada: {scalp['entrada']:,.0f} | SL: {scalp['sl']:,.0f} ({scalp['sl_dist']:.0f}pts)")
        lineas.append(f"   TP1: {scalp['tp1']:,.0f}  RR {scalp['rr1']} | TP2: {scalp['tp2']:,.0f}  RR {scalp['rr2']}")
        lineas.append(f"   📌 Base: {scalp['base']}")
    else:
        lineas.append(f"\n⚡ <b>SCALP:</b> sin OB M1 fresco en zona")

    # Intradía
    if intradia:
        lineas.append(f"\n🎯 <b>INTRADÍA</b> (M15/H1 — zona institucional):")
        lineas.append(f"   Entrada: {intradia['entrada']:,.0f} | SL: {intradia['sl']:,.0f} ({intradia['sl_dist']:.0f}pts)")
        lineas.append(f"   TP1: {intradia['tp1']:,.0f}  RR {intradia['rr1']} | TP2: {intradia['tp2']:,.0f}  RR {intradia['rr2']}")
        lineas.append(f"   📌 Base: {intradia['base']}")
    else:
        lineas.append(f"\n🎯 <b>INTRADÍA:</b> sin zona H1/M15 activa")

    # Swing
    if swing:
        lineas.append(f"\n📅 <b>SWING</b> (H4 — movimiento mayor):")
        lineas.append(f"   Entrada: {swing['entrada']:,.0f} | SL: {swing['sl']:,.0f} ({swing['sl_dist']:.0f}pts)")
        lineas.append(f"   TP1: {swing['tp1']:,.0f}  RR {swing['rr1']} | TP2: {swing['tp2']:,.0f}  RR {swing['rr2']}")
        lineas.append(f"   H4 tendencia: {tendencia_h4}")
        lineas.append(f"   📌 Base: {swing['base']}")
    else:
        lineas.append(f"\n📅 <b>SWING:</b> sin OB/FVG H4 detectado")

    lineas += [
        f"\n{'─'*36}",
        f"⏰ {datetime.now().strftime('%H:%M:%S')}",
    ]

    return "\n".join(lineas)


# ============================================================
#  CALCULADORES DE ENTRADA POR TIPO
# ============================================================

def _entrada_scalp(precio, obs_m1, obs_m15, es_bajista, simbolo):
    """Entrada scalp: usa OB M1 fresco o M15 cercano como base."""
    zona = None
    base = ""

    # Prioridad: OB M1 fresco en zona
    for ob in obs_m1:
        mid = ob.get('ob_mid', (ob['ob_high'] + ob['ob_low']) / 2)
        dist = abs(precio - mid)
        if dist <= 60:
            zona = {'high': ob['ob_high'], 'low': ob['ob_low'], 'mid': mid}
            base = f"OB M1 {ob['ob_low']:,.0f}–{ob['ob_high']:,.0f}"
            break

    # Fallback: OB M15 activo
    if zona is None and obs_m15:
        z = obs_m15[0]
        if z['dist'] <= 80:
            zona = z
            base = f"OB M15 {z['low']:,.0f}–{z['high']:,.0f}"

    if zona is None:
        return None

    sl_min = 40  # scalp mínimo
    if es_bajista:
        entrada = round(zona['high'], 0)
        sl      = round(zona['high'] + sl_min, 0)
        sl_dist = sl - entrada
        tp1     = round(entrada - sl_dist * 1.8, 0)
        tp2     = round(entrada - sl_dist * 3.0, 0)
    else:
        entrada = round(zona['low'], 0)
        sl      = round(zona['low'] - sl_min, 0)
        sl_dist = entrada - sl
        tp1     = round(entrada + sl_dist * 1.8, 0)
        tp2     = round(entrada + sl_dist * 3.0, 0)

    return {
        'entrada': entrada, 'sl': sl, 'sl_dist': sl_dist,
        'tp1': tp1, 'tp2': tp2,
        'rr1': round(abs(tp1 - entrada) / max(sl_dist, 1), 1),
        'rr2': round(abs(tp2 - entrada) / max(sl_dist, 1), 1),
        'base': base,
    }


def _entrada_intradia(precio, obs_h1, fvgs_h1, obs_m15, es_bajista, simbolo):
    """Entrada intradía: usa OB H1 o FVG H1 + M15 como refinamiento."""
    zona = None
    base = ""

    # OB H1 activo (precio en zona o cerca)
    for z in obs_h1:
        if z['dist'] <= 200:
            zona = z
            base = f"OB H1 {z['low']:,.0f}–{z['high']:,.0f}"
            break

    # FVG H1 si no hay OB
    if zona is None:
        for z in fvgs_h1:
            if z['dist'] <= 200:
                zona = z
                base = f"FVG H1 {z['low']:,.0f}–{z['high']:,.0f}"
                break

    # Refinar con M15 si hay zona
    if zona is None and obs_m15:
        z = obs_m15[0]
        if z['dist'] <= 150:
            zona = z
            base = f"OB M15 {z['low']:,.0f}–{z['high']:,.0f}"

    if zona is None:
        return None

    sl_min = 60
    tam    = max(zona['high'] - zona['low'], sl_min)

    if es_bajista:
        entrada = round(zona['high'] - tam * 0.2, 0)  # 20% dentro del OB
        sl      = round(zona['high'] + 20, 0)
        sl_dist = sl - entrada
        if sl_dist < sl_min:
            sl = round(entrada + sl_min, 0)
            sl_dist = sl_min
        tp1 = round(entrada - sl_dist * 1.8, 0)
        tp2 = round(entrada - sl_dist * 2.8, 0)
    else:
        entrada = round(zona['low'] + tam * 0.2, 0)
        sl      = round(zona['low'] - 20, 0)
        sl_dist = entrada - sl
        if sl_dist < sl_min:
            sl = round(entrada - sl_min, 0)
            sl_dist = sl_min
        tp1 = round(entrada + sl_dist * 1.8, 0)
        tp2 = round(entrada + sl_dist * 2.8, 0)

    return {
        'entrada': entrada, 'sl': sl, 'sl_dist': sl_dist,
        'tp1': tp1, 'tp2': tp2,
        'rr1': round(abs(tp1 - entrada) / max(sl_dist, 1), 1),
        'rr2': round(abs(tp2 - entrada) / max(sl_dist, 1), 1),
        'base': base,
    }


def _entrada_swing(precio, obs_h4, fvgs_h4, tendencia_h4, es_bajista, simbolo):
    """Entrada swing: usa OB H4 o FVG H4 con SL amplio."""
    zona = None
    base = ""

    for z in obs_h4:
        if z['dist'] <= 500:
            zona = z
            base = f"OB H4 {z['low']:,.0f}–{z['high']:,.0f}"
            break

    if zona is None:
        for z in fvgs_h4:
            if z['dist'] <= 500:
                zona = z
                base = f"FVG H4 {z['low']:,.0f}–{z['high']:,.0f}"
                break

    if zona is None:
        return None

    sl_min = 100
    tam    = max(zona['high'] - zona['low'], sl_min)

    if es_bajista:
        entrada = round(zona['mid'], 0)
        sl      = round(zona['high'] + 30, 0)
        sl_dist = sl - entrada
        if sl_dist < sl_min:
            sl = round(entrada + sl_min, 0)
            sl_dist = sl_min
        tp1 = round(entrada - sl_dist * 2.0, 0)
        tp2 = round(entrada - sl_dist * 4.0, 0)
    else:
        entrada = round(zona['mid'], 0)
        sl      = round(zona['low'] - 30, 0)
        sl_dist = entrada - sl
        if sl_dist < sl_min:
            sl = round(entrada - sl_min, 0)
            sl_dist = sl_min
        tp1 = round(entrada + sl_dist * 2.0, 0)
        tp2 = round(entrada + sl_dist * 4.0, 0)

    return {
        'entrada': entrada, 'sl': sl, 'sl_dist': sl_dist,
        'tp1': tp1, 'tp2': tp2,
        'rr1': round(abs(tp1 - entrada) / max(sl_dist, 1), 1),
        'rr2': round(abs(tp2 - entrada) / max(sl_dist, 1), 1),
        'base': base,
    }


# ============================================================
#  DETECTORES INTERNOS (OBs y FVGs)
# ============================================================

def _detectar_obs(df, es_bajista, ventana=4, max_obs=4, tol=150):
    if df is None or len(df) < ventana * 2 + 2:
        return []
    precio_actual = df['close'].iloc[-1]
    obs = []
    for i in range(ventana, len(df) - ventana):
        v = df.iloc[i]
        if es_bajista:
            if not all(df.iloc[j]['high'] <= v['high']
                       for j in range(i - ventana, i + ventana + 1) if j != i):
                continue
        else:
            if not all(df.iloc[j]['low'] >= v['low']
                       for j in range(i - ventana, i + ventana + 1) if j != i):
                continue
        zh, zl = v['high'], v['low']
        mitigado = (
            any(df.iloc[k]['high'] >= zh for k in range(i + 1, len(df)))
            if es_bajista else
            any(df.iloc[k]['low']  <= zl for k in range(i + 1, len(df)))
        )
        if not mitigado:
            mid = (zh + zl) / 2
            obs.append({
                'high': round(zh, 2), 'low': round(zl, 2), 'mid': round(mid, 2),
                'dist': round(abs(precio_actual - mid), 2),
                'tam':  round(zh - zl, 2),
                'en_zona': zl - tol <= precio_actual <= zh + tol,
            })
    obs.sort(key=lambda x: x['dist'])
    return obs[:max_obs]


def _detectar_fvgs(df, es_bajista, max_fvgs=4, tol=150):
    if df is None or len(df) < 3:
        return []
    precio_actual = df['close'].iloc[-1]
    fvgs = []
    for i in range(1, len(df) - 1):
        v1 = df.iloc[i - 1]
        v3 = df.iloc[i + 1]
        if es_bajista and v3['high'] < v1['low']:
            zh, zl = v1['low'], v3['high']
            mitigado = any(
                df.iloc[k]['low'] <= zh and df.iloc[k]['high'] >= zl
                for k in range(i + 2, len(df))
            )
            if not mitigado:
                mid = (zh + zl) / 2
                fvgs.append({
                    'high': round(zh, 2), 'low': round(zl, 2), 'mid': round(mid, 2),
                    'dist': round(abs(precio_actual - mid), 2),
                    'tam':  round(zh - zl, 2),
                    'en_zona': zl - tol <= precio_actual <= zh + tol,
                })
        elif not es_bajista and v3['low'] > v1['high']:
            zh, zl = v3['low'], v1['high']
            mitigado = any(
                df.iloc[k]['low'] <= zh and df.iloc[k]['high'] >= zl
                for k in range(i + 2, len(df))
            )
            if not mitigado:
                mid = (zh + zl) / 2
                fvgs.append({
                    'high': round(zh, 2), 'low': round(zl, 2), 'mid': round(mid, 2),
                    'dist': round(abs(precio_actual - mid), 2),
                    'tam':  round(zh - zl, 2),
                    'en_zona': zl - tol <= precio_actual <= zh + tol,
                })
    fvgs.sort(key=lambda x: x['dist'])
    return fvgs[:max_fvgs]


# ============================================================
#  TELEGRAM — RECIBIR COMANDOS /analisis
# ============================================================

def _obtener_updates(offset=0):
    """Lee mensajes nuevos del bot de Telegram."""
    if not TELEGRAM_TOKEN:
        return []
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        r   = requests.get(url, params={"offset": offset, "timeout": 3}, timeout=5)
        if r.ok:
            return r.json().get("result", [])
    except Exception:
        pass
    return []


def verificar_comando_telegram():
    """
    Llamar al inicio de cada ciclo del scanner en main_v4.py.
    Detecta mensajes /analisis <simbolo> y responde con el análisis.

    Agregar en main_v4.py dentro del loop principal:
        from analisis_demanda import verificar_comando_telegram
        verificar_comando_telegram()
    """
    global _ultimo_update_id

    updates = _obtener_updates(_ultimo_update_id + 1)

    if updates:
        print(f"  [analisis] {len(updates)} update(s) recibidos")

    for upd in updates:
        _ultimo_update_id = max(_ultimo_update_id, upd.get("update_id", 0))

        msg  = upd.get("message", {})
        text = msg.get("text", "").strip()

        print(f"  [analisis] mensaje recibido: '{text}'")

        if not (text.lower().startswith("/analisis") or text.lower().startswith("/analizar")):
            continue

        # Extraer símbolo: /analisis GainX 600
        partes  = text.split(" ", 1)
        simbolo = partes[1].strip() if len(partes) > 1 else ""

        if not simbolo:
            enviar_telegram(
                "❓ Uso: <b>/analisis GainX 600</b>\n"
                "Símbolos válidos: GainX 400/600/800/999/1200 | PainX 400/600/800/999/1200"
            )
            continue

        # Validar símbolo
        from config import SIMBOLOS
        simbolos_validos = list(SIMBOLOS)
        if simbolo not in simbolos_validos:
            enviar_telegram(
                f"❌ Símbolo <b>{simbolo}</b> no reconocido.\n"
                f"Válidos: {', '.join(simbolos_validos)}"
            )
            continue

        # Enviar respuesta "analizando..."
        enviar_telegram(f"🔍 Analizando <b>{simbolo}</b>...")

        try:
            reporte = analizar_demanda(simbolo)
            enviar_telegram(reporte)
        except Exception as e:
            enviar_telegram(f"❌ Error analizando {simbolo}: {e}")


# ============================================================
#  USO DESDE CONSOLA
#  python analisis_demanda.py GainX 600
#  python analisis_demanda.py PainX 400
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUso: python analisis_demanda.py <simbolo>")
        print("Ejemplo: python analisis_demanda.py GainX 600")
        print("         python analisis_demanda.py PainX 400")
        sys.exit(1)

    simbolo = " ".join(sys.argv[1:])

    print(f"\nConectando a MetaTrader 5...")
    if not mt5.initialize():
        print("Error: Abre MetaTrader 5 primero.")
        sys.exit(1)

    detectar_y_configurar(mt5)

    print(f"Analizando {simbolo}...\n")
    reporte = analizar_demanda(simbolo)

    # Imprimir en consola (sin tags HTML)
    import re
    reporte_consola = re.sub(r'<[^>]+>', '', reporte)
    print(reporte_consola)

    # Enviar a Telegram si está configurado
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        ok = enviar_telegram(reporte)
        print(f"\n{'✅ Enviado a Telegram' if ok else '❌ Error enviando a Telegram'}")
    else:
        print("\n⚠️  Telegram no configurado — solo consola")

    mt5.shutdown()
