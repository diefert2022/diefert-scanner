# ============================================================
#  DIEFERT SCANNER v5 — emascalpd_v1.py
#
#  Estrategia EmaScalpD
#  ─────────────────────────────────────────────────────────
#  LÓGICA COMPLETA:
#
#  DETECCIÓN DE TENDENCIA:
#    - EMA 30, 50, 100 cruzan EMA 200 progresivamente
#    - Tendencia confirmada cuando EMA 100 cruza EMA 200
#    - Filtro armónico: precio > EMA30 > EMA50 > EMA100 > EMA200 (alcista)
#                       precio < EMA30 < EMA50 < EMA100 < EMA200 (bajista)
#
#  SWING HIGH/LOW MAYOR:
#    - Solo cuentan CHoCH/BOS que rompen el Swing High/Low Mayor
#    - Los CHoCH/BOS internos se ignoran (ruido)
#    - El Swing High/Low Mayor solo se invalida si EMA200 se pierde
#
#  ENTRADA:
#    - Inicio de tendencia: alto/bajo previo roto con cuerpo → retrocede a EMA_ENTRADA
#    - Continuidad: nuevo Swing High/Low roto con cuerpo → retrocede a EMA_ENTRADA
#    - UNA sola entrada por swing (aunque toque EMA_ENTRADA varias veces)
#    - Se resetea solo cuando se rompe un NUEVO swing
#
#  SEÑAL ENVIADA A TELEGRAM (tópico EmaScalpD):
#    - Tendencia confirmada
#    - CHoCH/BOS detectado
#    - Precio de entrada (EMA_ENTRADA)
#    - SL (EMA200 + SL_EXTRA pts)
#    - "A gestionar con grid"
#
#  PARÁMETROS CONFIGURABLES (por símbolo):
#    EMA_ENTRADA   = 30     # EMA de retroceso para entrada (21, 30, 50...)
#    SL_EXTRA      = 60     # pts extra después de EMA200 para SL
#    VELAS_M5      = 200    # velas a analizar en M5
#    COOLDOWN_SEG  = 300    # segundos entre señales del mismo símbolo
#
#  SEÑALES VAN SOLO A: Telegram tópico EmaScalpD
#  NO tocan el flujo existente del scanner
# ============================================================

import urllib.request
import urllib.parse
import time
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# ── TELEGRAM — CANAL EMASCALPD ────────────────────────────
from config import TOKEN
EMASCALPD_CHAT_ID  = "-1002337310038"
EMASCALPD_THREAD_ID = 767

# ── PARÁMETROS GLOBALES (modificables) ────────────────────
EMA_ENTRADA   = 30      # EMA de retroceso para entrada
SL_EXTRA      = 60      # pts extra debajo de EMA200 para SL (modificable)
VELAS_M5      = 300     # velas M5 a analizar
COOLDOWN_SEG  = 300     # segundos mínimos entre señales del mismo símbolo

# ── ESTADO INTERNO ────────────────────────────────────────
# Para cada símbolo guardamos:
#   tendencia_activa:   'ALCISTA' | 'BAJISTA' | None
#   swing_mayor:        float — el Swing High/Low mayor activo
#   swing_usado:        bool  — si ya se usó la entrada de este swing
#   ultimo_envio:       float — timestamp del último envío
_estado = {}

def _get_estado(simbolo):
    if simbolo not in _estado:
        _estado[simbolo] = {
            'tendencia_activa': None,
            'swing_mayor':      None,
            'swing_usado':      False,
            'ultimo_envio':     0,
        }
    return _estado[simbolo]


# ── TELEGRAM ──────────────────────────────────────────────

def _enviar_emascalpd(mensaje):
    """Envía mensaje al tópico EmaScalpD del grupo Diefert Trading."""
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

def _calcular_emas(df):
    """
    Calcula EMA 30, 50, 100, 200 sobre el dataframe.
    Retorna dict con los valores actuales de cada EMA.
    """
    close = df['close']
    emas = {}
    for periodo in [30, 50, 100, 200]:
        ema = close.ewm(span=periodo, adjust=False).mean()
        emas[periodo] = ema.iloc[-1]
    return emas


def _calcular_ema_serie(df, periodo):
    """Retorna la serie completa de una EMA."""
    return df['close'].ewm(span=periodo, adjust=False).mean()


# ── FILTRO ARMÓNICO ───────────────────────────────────────

def _es_armonico(precio, emas, direccion):
    """
    Verifica que las EMAs estén en orden armónico.
    ALCISTA: precio > EMA30 > EMA50 > EMA100 > EMA200
    BAJISTA: precio < EMA30 < EMA50 < EMA100 < EMA200
    """
    e30  = emas[30]
    e50  = emas[50]
    e100 = emas[100]
    e200 = emas[200]

    if direccion == 'ALCISTA':
        return precio > e30 > e50 > e100 > e200
    elif direccion == 'BAJISTA':
        return precio < e30 < e50 < e100 < e200
    return False


# ── DETECCIÓN DE CRUCE EMA100 / EMA200 ────────────────────

def _detectar_cruce_tendencia(df):
    """
    Detecta si la EMA100 cruzó la EMA200 recientemente.
    Busca en las últimas 5 velas para detectar el cruce fresco.

    Retorna: 'ALCISTA', 'BAJISTA' o None
    """
    ema100 = _calcular_ema_serie(df, 100)
    ema200 = _calcular_ema_serie(df, 200)

    # Revisar últimas 5 velas
    for i in range(-5, -1):
        antes_100 = ema100.iloc[i-1]
        antes_200 = ema200.iloc[i-1]
        ahora_100 = ema100.iloc[i]
        ahora_200 = ema200.iloc[i]

        # Cruce alcista: EMA100 cruza EMA200 hacia arriba
        if antes_100 <= antes_200 and ahora_100 > ahora_200:
            return 'ALCISTA'

        # Cruce bajista: EMA100 cruza EMA200 hacia abajo
        if antes_100 >= antes_200 and ahora_100 < ahora_200:
            return 'BAJISTA'

    return None


# ── DETECCIÓN DE SWING HIGH/LOW MAYOR ─────────────────────

def _detectar_swing_mayor(df, direccion, n=5):
    """
    Detecta el Swing High (alcista) o Swing Low (bajista) más reciente
    que sea un punto pivote real (rodeado de velas menores).
    n = velas a cada lado para confirmar el pivote.
    """
    highs = df['high'].values
    lows  = df['low'].values

    if direccion == 'ALCISTA':
        # Buscar el High más alto en las últimas 100 velas
        ventana = highs[-100:]
        idx_max = np.argmax(ventana)
        return ventana[idx_max]

    elif direccion == 'BAJISTA':
        # Buscar el Low más bajo en las últimas 100 velas
        ventana = lows[-100:]
        idx_min = np.argmin(ventana)
        return ventana[idx_min]

    return None


# ── VERIFICAR SI EL SWING FUE ROTO CON CUERPO ─────────────

def _swing_roto_con_cuerpo(df, swing_mayor, direccion, min_cuerpo=5):
    """
    Verifica si una vela reciente rompió el swing mayor CON CUERPO.
    El cuerpo debe superar el nivel, no solo la mecha.
    min_cuerpo = mínimo de pts del cuerpo para confirmar (evita ruido).
    """
    # Revisar las últimas 3 velas
    for i in range(-3, 0):
        vela = df.iloc[i]
        cuerpo_max = max(vela['open'], vela['close'])
        cuerpo_min = min(vela['open'], vela['close'])
        tamaño_cuerpo = abs(vela['close'] - vela['open'])

        if tamaño_cuerpo < min_cuerpo:
            continue  # vela sin cuerpo suficiente

        if direccion == 'ALCISTA' and cuerpo_max > swing_mayor:
            return True, cuerpo_max

        if direccion == 'BAJISTA' and cuerpo_min < swing_mayor:
            return True, cuerpo_min

    return False, None


# ── VERIFICAR TOQUE DE EMA ENTRADA ────────────────────────

def _precio_toca_ema_entrada(precio_actual, emas, direccion, tolerancia=3):
    """
    Verifica si el precio está tocando la EMA de entrada (EMA_ENTRADA).
    tolerancia = pts de margen para considerar "toque".

    En tendencia alcista: precio bajó y está cerca de EMA_ENTRADA desde arriba
    En tendencia bajista: precio subió y está cerca de EMA_ENTRADA desde abajo
    """
    ema_val = emas.get(EMA_ENTRADA)
    if ema_val is None:
        return False

    dist = abs(precio_actual - ema_val)
    return dist <= tolerancia


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────

def analizar_emascalpd(simbolo, df_m5):
    """
    Analiza un símbolo en M5 aplicando la estrategia EmaScalpD.
    Envía señal al tópico EmaScalpD si se cumplen las condiciones.

    Parámetros:
        simbolo  → nombre del índice (ej. "FlipX 1")
        df_m5    → DataFrame con velas M5 del símbolo

    No retorna nada — solo envía a Telegram si hay señal.
    """
    if df_m5 is None or len(df_m5) < 210:
        return

    estado = _get_estado(simbolo)
    precio_actual = df_m5['close'].iloc[-1]

    # ── 1. Calcular EMAs ──────────────────────────────────
    emas = _calcular_emas(df_m5)
    e200 = emas[200]

    # ── 2. Verificar si EMA200 sigue siendo guardián ──────
    #    Si el precio cruza EMA200 → resetear todo
    if estado['tendencia_activa'] == 'ALCISTA' and precio_actual < e200:
        print(f"  [EmaScalpD] {simbolo} — precio cruzó EMA200 hacia abajo → reset")
        estado['tendencia_activa'] = None
        estado['swing_mayor']      = None
        estado['swing_usado']      = False

    elif estado['tendencia_activa'] == 'BAJISTA' and precio_actual > e200:
        print(f"  [EmaScalpD] {simbolo} — precio cruzó EMA200 hacia arriba → reset")
        estado['tendencia_activa'] = None
        estado['swing_mayor']      = None
        estado['swing_usado']      = False

    # ── 3. Detectar inicio de tendencia (cruce EMA100/200) ─
    if estado['tendencia_activa'] is None:
        cruce = _detectar_cruce_tendencia(df_m5)
        if cruce:
            estado['tendencia_activa'] = cruce
            estado['swing_mayor']      = _detectar_swing_mayor(df_m5, cruce)
            estado['swing_usado']      = False
            print(f"  [EmaScalpD] {simbolo} — tendencia {cruce} confirmada | swing_mayor={estado['swing_mayor']:.1f}")

    # ── 4. Sin tendencia activa → nada que hacer ──────────
    if estado['tendencia_activa'] is None:
        return

    direccion = estado['tendencia_activa']

    # ── 5. Filtro armónico ────────────────────────────────
    if not _es_armonico(precio_actual, emas, direccion):
        return  # EMAs mezcladas → no operar

    # ── 6. Verificar si el swing mayor fue roto ───────────
    swing_actual = estado['swing_mayor']
    if swing_actual is None:
        estado['swing_mayor'] = _detectar_swing_mayor(df_m5, direccion)
        return

    roto, nivel_ruptura = _swing_roto_con_cuerpo(df_m5, swing_actual, direccion)

    if roto:
        # Nuevo swing roto → resetear flag de entrada usada
        # y actualizar el swing mayor al nuevo nivel
        nuevo_swing = _detectar_swing_mayor(df_m5, direccion)
        if nuevo_swing != swing_actual:
            print(f"  [EmaScalpD] {simbolo} — nuevo swing roto: {swing_actual:.1f} → {nuevo_swing:.1f}")
            estado['swing_mayor'] = nuevo_swing
            estado['swing_usado'] = False  # nueva oportunidad de entrada

    # ── 7. Verificar entrada: toque de EMA_ENTRADA ────────
    if estado['swing_usado']:
        return  # ya se usó la entrada de este swing

    if not _precio_toca_ema_entrada(precio_actual, emas, direccion):
        return  # precio no está en la EMA de entrada

    # ── 8. Cooldown ───────────────────────────────────────
    ahora = time.time()
    if ahora - estado['ultimo_envio'] < COOLDOWN_SEG:
        return

    # ── 9. Calcular niveles de la señal ───────────────────
    ema_entrada_val = emas.get(EMA_ENTRADA, precio_actual)

    if direccion == 'ALCISTA':
        entrada = round(ema_entrada_val, 2)
        sl      = round(e200 - SL_EXTRA, 2)
        icono   = '📈'
        dir_txt = 'COMPRA'
    else:
        entrada = round(ema_entrada_val, 2)
        sl      = round(e200 + SL_EXTRA, 2)
        icono   = '📉'
        dir_txt = 'VENTA'

    dist_ema30_200 = abs(emas[30] - e200)
    espacio_grid   = round(dist_ema30_200 / 10, 1)

    # ── 10. Construir mensaje ─────────────────────────────
    mensaje = (
        f"{icono} <b>EmaScalpD — {simbolo}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Dirección: <b>{dir_txt}</b>\n"
        f"🎯 Entrada: <b>{entrada}</b> (EMA {EMA_ENTRADA})\n"
        f"🛑 SL: <b>{sl}</b> (EMA200 ± {SL_EXTRA}pts)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📐 EMA200: {round(e200, 1)} | EMA{EMA_ENTRADA}: {round(ema_entrada_val, 1)}\n"
        f"📏 Espacio grid aprox: {espacio_grid}pts por entrada\n"
        f"🔧 A gestionar con grid\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ EMAs armónicas ✅ | Swing Mayor roto ✅"
    )

    # ── 11. Enviar y marcar como usado ────────────────────
    _enviar_emascalpd(mensaje)
    estado['swing_usado']  = True
    estado['ultimo_envio'] = ahora
    print(f"  [EmaScalpD] {simbolo} — señal {dir_txt} enviada | entrada={entrada} | sl={sl}")


# ── INTEGRACIÓN CON main_v5.py ────────────────────────────
# En main_v5.py, dentro del loop de analizar_simbolo(), agregar:
#
#   from emascalpd_v1 import analizar_emascalpd
#   from utils import obtener_df
#   from config import TF_M5, VELAS_M5
#
#   df_m5 = obtener_df(simbolo, TF_M5, 300)
#   analizar_emascalpd(simbolo, df_m5)
#
# Nota: Si el símbolo ya tiene df_m5 calculado en el loop,
# reutilizarlo en lugar de volver a pedirlo a MT5.
# ============================================================
