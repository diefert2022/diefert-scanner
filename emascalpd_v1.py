# ============================================================
#  DIEFERT SCANNER v5 — emascalpd_v1.py
#
#  Estrategia EmaScalpD — LÓGICA COMPLETA
#  ─────────────────────────────────────────────────────────
#
#  FASE 1 — DIRECCIÓN:
#    EMA30, EMA50, EMA100 cruzan EMA200 y están armónicas.
#    Se busca el cruce más reciente de EMA100 sobre EMA200
#    en TODO el historial disponible.
#    Filtro armónico: precio > EMA30 > EMA50 > EMA100 > EMA200 (alcista)
#                     precio < EMA30 < EMA50 < EMA100 < EMA200 (bajista)
#
#  FASE 2 — SWING MAYOR:
#    Desde el momento del cruce, detectar el último High (alcista)
#    o Low (bajista) estructural (pivote real con vecinos menores).
#    Esperar que el precio rompa ese nivel CON CUERPO de vela.
#
#  FASE 3 — ENTRADA:
#    Después del BOS con cuerpo → precio retrocede y toca EMA30 → señal.
#    UNA SOLA entrada por BOS.
#    Si precio toca EMA30 sin nuevo BOS → NO hay entrada.
#    Nueva entrada solo cuando se rompe un nuevo High/Low con cuerpo.
#
#  RESET:
#    Si el precio cruza EMA200 → reset completo del estado.
#    Si las EMAs pierden armonía → reset completo.
#
#  SEÑALES VAN SOLO A: Telegram tópico EmaScalpD
#  NO tocan el flujo existente del scanner
# ============================================================

import urllib.request
import urllib.parse
import time
import pandas as pd
import numpy as np

# ── PRUEBA VISUAL — escribe swing en archivo para MT5 ────────────
try:
    from escribir_swing_debug import escribir_swing_debug
    _DEBUG_SWING = True
except ImportError:
    _DEBUG_SWING = False

# ── TELEGRAM — CANAL EMASCALPD ────────────────────────────
from config import TOKEN
EMASCALPD_CHAT_ID   = "-1002337310038"
EMASCALPD_THREAD_ID = 767

# ── PARÁMETROS GLOBALES ───────────────────────────────────
EMA_ENTRADA  = 30    # EMA de retroceso para entrada
SL_EXTRA     = 60    # pts extra más allá de EMA200 para el SL
COOLDOWN_SEG = 300   # segundos mínimos entre señales del mismo símbolo
TOLERANCIA   = 5     # pts de margen para considerar "toque" de EMA30
MIN_CUERPO   = 5     # pts mínimos de cuerpo para confirmar BOS

# ── ESTADO INTERNO POR SÍMBOLO ────────────────────────────
_estado = {}
_ciclos = {}   # contador de ciclos por símbolo para prints periódicos

def _get_estado(simbolo):
    if simbolo not in _estado:
        _estado[simbolo] = {
            'tendencia_activa': None,
            'idx_cruce':        None,
            'swing_mayor':      None,
            'bos_confirmado':   False,
            'swing_usado':      False,
            'ultimo_envio':     0,
        }
    return _estado[simbolo]

def _reset_estado(simbolo, motivo=''):
    e = _estado.get(simbolo)
    if e:
        e['tendencia_activa'] = None
        e['idx_cruce']        = None
        e['swing_mayor']      = None
        e['bos_confirmado']   = False
        e['swing_usado']      = False
    if motivo:
        print(f"  [EmaScalpD] {simbolo} — RESET: {motivo}")


# ── TELEGRAM ──────────────────────────────────────────────

def _enviar_emascalpd(mensaje):
    try:
        url  = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id":           EMASCALPD_CHAT_ID,
            "message_thread_id": EMASCALPD_THREAD_ID,
            "text":              mensaje,
            "parse_mode":        "HTML"
        }).encode()
        urllib.request.urlopen(url, data, timeout=5)
        print(f"  [EmaScalpD] ✅ Señal enviada a Telegram")
    except Exception as e:
        print(f"  [EmaScalpD] ❌ Error Telegram: {e}")


# ── CÁLCULO DE EMAs ───────────────────────────────────────

def _calcular_series_emas(df):
    """Retorna dict con la serie completa de cada EMA."""
    close = df['close']
    return {p: close.ewm(span=p, adjust=False).mean() for p in [30, 50, 100, 200]}

def _emas_actuales(series):
    """Retorna dict con el valor actual (última vela) de cada EMA."""
    return {p: series[p].iloc[-1] for p in [30, 50, 100, 200]}


# ── FASE 1: DETECTAR CRUCE MÁS RECIENTE EMA100/EMA200 ─────

def _detectar_cruce_reciente(series):
    """
    Busca el cruce más reciente de EMA100 sobre EMA200
    recorriendo el historial completo de atrás hacia adelante.

    Retorna: (direccion, idx_cruce) o (None, None)
    """
    ema100 = series[100]
    ema200 = series[200]
    n = len(ema100)

    for i in range(n - 1, 0, -1):
        curr100 = ema100.iloc[i]
        curr200 = ema200.iloc[i]
        prev100 = ema100.iloc[i - 1]
        prev200 = ema200.iloc[i - 1]

        # Cruce alcista: antes abajo, ahora arriba
        if prev100 <= prev200 and curr100 > curr200:
            return 'ALCISTA', i

        # Cruce bajista: antes arriba, ahora abajo
        if prev100 >= prev200 and curr100 < curr200:
            return 'BAJISTA', i

    return None, None


# ── FASE 1: FILTRO ARMÓNICO ───────────────────────────────

def _es_armonico(precio, emas, direccion):
    """
    ALCISTA: precio > EMA30 > EMA50 > EMA100 > EMA200
    BAJISTA: precio < EMA30 < EMA50 < EMA100 < EMA200
    """
    e30, e50, e100, e200 = emas[30], emas[50], emas[100], emas[200]
    if direccion == 'ALCISTA':
        return precio > e30 > e50 > e100 > e200
    elif direccion == 'BAJISTA':
        return precio < e30 < e50 < e100 < e200
    return False


# ── FASE 2: DETECTAR SWING MAYOR DESDE EL CRUCE ───────────

def _detectar_swing_mayor(df, idx_cruce, direccion):
    """
    Busca el High más alto (alcista) o Low más bajo (bajista)
    desde el cruce hasta la vela actual.
    
    Sin filtro de vecinos — simplemente el extremo absoluto
    desde el cruce. Esto coincide con lo que el trader ve visualmente
    como el "último bajo/alto de la tendencia".
    """
    highs = df['high'].values
    lows  = df['low'].values
    n     = len(df)

    # Rango: desde el cruce hasta la penúltima vela (excluyendo la vela en formación)
    rango_highs = highs[idx_cruce:n-1]
    rango_lows  = lows[idx_cruce:n-1]

    if len(rango_lows) == 0:
        return None

    if direccion == 'ALCISTA':
        return float(rango_highs.max())
    elif direccion == 'BAJISTA':
        return float(rango_lows.min())

    return None


# ── FASE 2: VERIFICAR BOS CON CUERPO ─────────────────────

def _verificar_bos_con_cuerpo(df, swing_mayor, direccion):
    """
    Verifica si alguna vela reciente (últimas 3) rompió el swing mayor
    CON CUERPO — no solo con mecha.
    """
    for i in range(-3, 0):
        vela       = df.iloc[i]
        cuerpo_max = max(vela['open'], vela['close'])
        cuerpo_min = min(vela['open'], vela['close'])
        tam_cuerpo = abs(vela['close'] - vela['open'])

        if tam_cuerpo < MIN_CUERPO:
            continue

        if direccion == 'ALCISTA' and cuerpo_max > swing_mayor:
            return True
        if direccion == 'BAJISTA' and cuerpo_min < swing_mayor:
            return True

    return False


# ── FASE 3: VERIFICAR TOQUE DE EMA30 ─────────────────────

def _precio_toca_ema30(precio_actual, emas):
    """
    Verifica si el precio está tocando la EMA30 con tolerancia.
    """
    return abs(precio_actual - emas[EMA_ENTRADA]) <= TOLERANCIA


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────

def analizar_emascalpd(simbolo, df_m5):
    """
    Analiza un símbolo aplicando la estrategia EmaScalpD.
    Envía señal a Telegram si se cumplen las 3 fases.
    """
    if df_m5 is None or len(df_m5) < 210:
        return

    estado        = _get_estado(simbolo)
    precio_actual = df_m5['close'].iloc[-1]

    # Calcular todas las series EMA
    series = _calcular_series_emas(df_m5)
    emas   = _emas_actuales(series)
    e200   = emas[200]

    # ── RESET si precio cruza EMA200 ─────────────────────
    if estado['tendencia_activa'] == 'ALCISTA' and precio_actual < e200:
        _reset_estado(simbolo, 'precio cruzó EMA200 hacia abajo')
        return
    if estado['tendencia_activa'] == 'BAJISTA' and precio_actual > e200:
        _reset_estado(simbolo, 'precio cruzó EMA200 hacia arriba')
        return

    # ── FASE 1: Detectar cruce EMA100/EMA200 ─────────────
    if estado['tendencia_activa'] is None:
        direccion, idx_cruce = _detectar_cruce_reciente(series)

        if direccion is None:
            return  # no hay cruce en el historial disponible

        if not _es_armonico(precio_actual, emas, direccion):
            # ── DIAGNÓSTICO FlipX 2 — cada 10 ciclos ─────────
            if simbolo == 'FlipX 2':
                _ciclos[simbolo] = _ciclos.get(simbolo, 0) + 1
                if _ciclos[simbolo] % 10 == 1:
                    e30, e50, e100, e200 = emas[30], emas[50], emas[100], emas[200]
                    ok30  = '✅' if (direccion == 'ALCISTA' and precio_actual > e30)  or (direccion == 'BAJISTA' and precio_actual < e30)  else '❌'
                    ok50  = '✅' if (direccion == 'ALCISTA' and e30 > e50)            or (direccion == 'BAJISTA' and e30 < e50)            else '❌'
                    ok100 = '✅' if (direccion == 'ALCISTA' and e50 > e100)           or (direccion == 'BAJISTA' and e50 < e100)           else '❌'
                    ok200 = '✅' if (direccion == 'ALCISTA' and e100 > e200)          or (direccion == 'BAJISTA' and e100 < e200)          else '❌'
                    print(f"  [EmaScalpD] FlipX 2 — esperando armonía {direccion}")
                    print(f"    precio={precio_actual:.1f}  {ok30}EMA30={e30:.1f}  {ok50}EMA50={e50:.1f}  {ok100}EMA100={e100:.1f}  {ok200}EMA200={e200:.1f}")
            return  # cruce existe pero EMAs aún no están en orden

        # Tendencia confirmada
        estado['tendencia_activa'] = direccion
        estado['idx_cruce']        = idx_cruce
        estado['bos_confirmado']   = False
        estado['swing_usado']      = False
        estado['swing_mayor']      = _detectar_swing_mayor(df_m5, idx_cruce, direccion)

        print(f"  [EmaScalpD] {simbolo} — {direccion} confirmada | "
              f"cruce en vela {idx_cruce} | swing={estado['swing_mayor']}")

        # ── PRUEBA VISUAL: escribir swing para MT5 ────────────
        if _DEBUG_SWING and estado['swing_mayor'] and simbolo == 'FlipX 2':
            tipo = 'HIGH' if direccion == 'ALCISTA' else 'LOW'
            escribir_swing_debug(simbolo, direccion, tipo, estado['swing_mayor'])

    if estado['tendencia_activa'] is None:
        return

    direccion = estado['tendencia_activa']

    # ── FASE 1: Verificar armonía en cada ciclo ───────────
    if not _es_armonico(precio_actual, emas, direccion):
        _reset_estado(simbolo, 'EMAs perdieron armonía')
        return

    # ── FASE 2: Verificar BOS sobre swing mayor ───────────
    swing_actual = estado['swing_mayor']

    if swing_actual is None:
        estado['swing_mayor'] = _detectar_swing_mayor(df_m5, estado['idx_cruce'], direccion)
        return

    # ── PRUEBA VISUAL: actualizar swing en MT5 cada ciclo ─
    if _DEBUG_SWING and estado['swing_mayor'] and simbolo == 'FlipX 2':
        tipo = 'HIGH' if direccion == 'ALCISTA' else 'LOW'
        escribir_swing_debug(simbolo, direccion, tipo, estado['swing_mayor'])

    if not estado['bos_confirmado']:
        if _verificar_bos_con_cuerpo(df_m5, swing_actual, direccion):
            estado['bos_confirmado'] = True
            estado['swing_usado']    = False
            # Actualizar swing al nuevo nivel
            nuevo = _detectar_swing_mayor(df_m5, estado['idx_cruce'], direccion)
            if nuevo and nuevo != swing_actual:
                estado['swing_mayor'] = nuevo
            print(f"  [EmaScalpD] {simbolo} — BOS ✅ | swing={estado['swing_mayor']:.1f} | esperando retroceso a EMA30")

            # ── PRUEBA VISUAL: actualizar swing en MT5 ────────
            if _DEBUG_SWING and estado['swing_mayor'] and simbolo == 'FlipX 2':
                tipo = 'HIGH' if direccion == 'ALCISTA' else 'LOW'
                escribir_swing_debug(simbolo, direccion, tipo, estado['swing_mayor'])
        else:
            return  # sin BOS todavía

    # ── FASE 3: Toque de EMA30 post-BOS ──────────────────
    if estado['swing_usado']:
        # Entrada ya usada — solo se reactiva con nuevo BOS
        nuevo = _detectar_swing_mayor(df_m5, estado['idx_cruce'], direccion)
        if nuevo and nuevo != estado['swing_mayor']:
            if _verificar_bos_con_cuerpo(df_m5, nuevo, direccion):
                estado['swing_mayor']    = nuevo
                estado['swing_usado']    = False
                estado['bos_confirmado'] = True
                print(f"  [EmaScalpD] {simbolo} — nuevo BOS ✅ | swing={nuevo:.1f} | entrada habilitada")
        return

    if not _precio_toca_ema30(precio_actual, emas):
        return  # precio aún no retrocedió a EMA30

    # ── Cooldown ──────────────────────────────────────────
    ahora = time.time()
    if ahora - estado['ultimo_envio'] < COOLDOWN_SEG:
        return

    # ── Construir y enviar señal ──────────────────────────
    ema30_val    = emas[EMA_ENTRADA]
    espacio_grid = round(abs(emas[30] - e200) / 10, 1)

    if direccion == 'ALCISTA':
        entrada = round(ema30_val, 2)
        sl      = round(e200 - SL_EXTRA, 2)
        icono   = '📈'
        dir_txt = 'COMPRA'
    else:
        entrada = round(ema30_val, 2)
        sl      = round(e200 + SL_EXTRA, 2)
        icono   = '📉'
        dir_txt = 'VENTA'

    mensaje = (
        f"{icono} <b>EmaScalpD — {simbolo}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Dirección: <b>{dir_txt}</b>\n"
        f"🎯 Entrada: <b>{entrada}</b> (EMA {EMA_ENTRADA})\n"
        f"🛑 SL: <b>{sl}</b> (EMA200 ± {SL_EXTRA}pts)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📐 EMA200: {round(e200, 1)} | EMA{EMA_ENTRADA}: {round(ema30_val, 1)}\n"
        f"📏 Espacio grid aprox: {espacio_grid}pts por entrada\n"
        f"🔧 A gestionar con grid\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ EMAs armónicas ✅ | BOS confirmado ✅ | Retroceso EMA30 ✅"
    )

    _enviar_emascalpd(mensaje)
    estado['swing_usado']  = True
    estado['ultimo_envio'] = ahora
    print(f"  [EmaScalpD] {simbolo} — señal {dir_txt} enviada | entrada={entrada} | sl={sl}")
