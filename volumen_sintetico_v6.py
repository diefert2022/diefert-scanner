# ============================================================
#  volumen_sintetico_v6.py
#  Diefert Scanner — Módulo INDEPENDIENTE
#
#  QUÉ HACE:
#  ─────────────────────────────────────────────────────────
#  Los índices sintéticos no tienen volumen real en MT5.
#  Este módulo crea un "Volumen Sintético Diefert" (VSD)
#  basado en 4 factores de precio puro:
#
#  1. VELOCIDAD    — rango de la vela M1 vs promedio histórico
#  2. DECISIÓN     — ratio cuerpo/mecha (vela limpia = fuerza)
#  3. CONTINUIDAD  — velas consecutivas en la misma dirección
#  4. ACELERACIÓN  — si el movimiento se frena = absorción
#
#  SCORE VSD: 0–100
#    0–30   → movimiento débil / sin fuerza
#    31–60  → fuerza moderada
#    61–80  → fuerza alta → posible zona de absorción
#    81–100 → fuerza extrema → alerta de absorción
#
#  ABSORCIÓN SINTÉTICA:
#    Se detecta cuando hay fuerza extrema (VSD > 70)
#    pero el precio NO avanza (se frena o revierte).
#    = alguien está absorbiendo el movimiento.
#
#  USO:
#    from volumen_sintetico_v6 import analizar_volumen_sintetico
#    resultado = analizar_volumen_sintetico(simbolo, es_bajista)
#
#  INTEGRACIÓN main_v5.py:
#    Agregar DESPUÉS del bloque de módulos v6 (línea ~495):
#
#    from volumen_sintetico_v6 import analizar_volumen_sintetico
#    vsd = analizar_volumen_sintetico(simbolo, es_bajista)
#    if vsd['alerta']:
#        print(f"  {vsd['descripcion']}")
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from utils import obtener_df
from config import TF_M1, VELAS_M1

# ── Parámetros ────────────────────────────────────────────
VELAS_ANALISIS   = 20   # velas M1 para calcular VSD
VELAS_HISTORICO  = 100  # velas M1 para calcular promedio base
CONSECUTIVAS_MIN = 3    # mínimo de velas seguidas para contar continuidad
VSD_ALERTA       = 70   # score mínimo para disparar alerta
VSD_ABSORCION    = 80   # score mínimo para detectar absorción


def _velocidad_score(df, idx_actual):
    """
    Factor 1: VELOCIDAD
    Compara el rango de la vela actual vs el promedio histórico.
    Vela 3x el promedio = score 100. Vela = promedio = score 50.
    """
    rango_actual = df['high'].iloc[idx_actual] - df['low'].iloc[idx_actual]
    rango_prom   = (df['high'] - df['low']).iloc[:idx_actual].mean()

    if rango_prom == 0:
        return 0

    ratio = rango_actual / rango_prom
    # ratio 0 → score 0, ratio 1 → score 50, ratio 3+ → score 100
    score = min(100, ratio * 50)
    return round(score, 1)


def _decision_score(df, idx_actual):
    """
    Factor 2: DECISIÓN (ratio cuerpo/rango)
    Vela con cuerpo 90%+ = dirección clara = score alto.
    Vela con mecha larga = indecisión = score bajo.
    """
    vela  = df.iloc[idx_actual]
    rango = vela['high'] - vela['low']
    if rango == 0:
        return 0

    cuerpo = abs(vela['close'] - vela['open'])
    ratio  = cuerpo / rango  # 0.0 a 1.0
    return round(ratio * 100, 1)


def _continuidad_score(df, idx_actual, es_bajista):
    """
    Factor 3: CONTINUIDAD
    Cuenta velas consecutivas en la dirección esperada.
    3 velas = score 50, 5+ velas = score 100.
    """
    count = 0
    for i in range(idx_actual, max(0, idx_actual - 10), -1):
        vela = df.iloc[i]
        es_direccional = (
            vela['close'] < vela['open'] if es_bajista
            else vela['close'] > vela['open']
        )
        if es_direccional:
            count += 1
        else:
            break

    # 1 vela = 20pts, máximo en 5 velas = 100
    score = min(100, count * 20)
    return round(score, 1)


def _aceleracion_score(df, idx_actual):
    """
    Factor 4: ACELERACIÓN
    Compara rango de últimas 3 velas vs 3 anteriores.
    Si el movimiento ACELERÓ → score alto (fuerza real).
    Si DESACELERÓ → score bajo (posible absorción).
    """
    if idx_actual < 6:
        return 50  # sin datos suficientes → neutral

    rango_reciente  = (df['high'] - df['low']).iloc[idx_actual-2:idx_actual+1].mean()
    rango_anterior  = (df['high'] - df['low']).iloc[idx_actual-5:idx_actual-2].mean()

    if rango_anterior == 0:
        return 50

    ratio = rango_reciente / rango_anterior
    # ratio > 1 = aceleración, ratio < 1 = desaceleración
    score = min(100, ratio * 50)
    return round(score, 1)


def _detectar_absorcion(df, idx_actual, es_bajista, vsd_score):
    """
    Detecta absorción sintética:
    Condición: VSD alto (fuerza) pero precio NO avanza.

    Señal de absorción:
    - Movimiento fuerte (VSD > 70)
    - Pero la última vela cierra CONTRA la dirección esperada
    - O la mecha supera el cuerpo en 2x (rechazo)

    Retorna: dict con detectado, tipo, descripcion
    """
    if vsd_score < VSD_ABSORCION:
        return {'detectado': False}

    vela  = df.iloc[idx_actual]
    rango = vela['high'] - vela['low']
    if rango == 0:
        return {'detectado': False}

    cuerpo    = abs(vela['close'] - vela['open'])
    mecha_inf = min(vela['open'], vela['close']) - vela['low']
    mecha_sup = vela['high'] - max(vela['open'], vela['close'])

    # Tipo A: vela cierra contra la dirección (rechazo fuerte)
    if es_bajista:
        cierre_contra = vela['close'] > vela['open']  # vela alcista en caída
        mecha_contra  = mecha_inf > cuerpo * 2         # mecha inferior larga
    else:
        cierre_contra = vela['close'] < vela['open']  # vela bajista en subida
        mecha_contra  = mecha_sup > cuerpo * 2         # mecha superior larga

    if cierre_contra:
        return {
            'detectado': True,
            'tipo':      'ABSORCION_CIERRE',
            'nivel':     round(vela['close'], 2),
        }

    if mecha_contra:
        return {
            'detectado': True,
            'tipo':      'ABSORCION_MECHA',
            'nivel':     round(vela['close'], 2),
        }

    return {'detectado': False}


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────
def analizar_volumen_sintetico(simbolo, es_bajista):
    """
    Calcula el Volumen Sintético Diefert (VSD) para el símbolo.

    Retorna dict con:
      vsd_score    → 0-100, fuerza del movimiento actual
      alerta       → True si VSD supera umbral
      absorcion    → True si hay señal de absorción
      descripcion  → texto para consola/Telegram
      factores     → desglose de los 4 factores
    """
    resultado_neutro = {
        'vsd_score':   0,
        'alerta':      False,
        'absorcion':   False,
        'descripcion': '',
        'factores':    {},
    }

    try:
        df = obtener_df(simbolo, TF_M1, VELAS_HISTORICO)
        if df is None or len(df) < 10:
            return resultado_neutro

        idx = len(df) - 1  # última vela

        # ── Calcular los 4 factores ───────────────────────
        f_velocidad   = _velocidad_score(df, idx)
        f_decision    = _decision_score(df, idx)
        f_continuidad = _continuidad_score(df, idx, es_bajista)
        f_aceleracion = _aceleracion_score(df, idx)

        # ── VSD = promedio ponderado ──────────────────────
        # Velocidad y decisión pesan más (son los más confiables)
        vsd = (
            f_velocidad   * 0.35 +
            f_decision    * 0.30 +
            f_continuidad * 0.20 +
            f_aceleracion * 0.15
        )
        vsd_score = round(vsd, 1)

        # ── Clasificación ─────────────────────────────────
        if vsd_score >= 81:
            nivel_txt = '🔥 EXTREMO'
            icono     = '🔥'
        elif vsd_score >= 61:
            nivel_txt = '⚡ ALTO'
            icono     = '⚡'
        elif vsd_score >= 31:
            nivel_txt = '📊 MODERADO'
            icono     = '📊'
        else:
            nivel_txt = '💤 DÉBIL'
            icono     = '💤'

        # ── Detección de absorción ────────────────────────
        absorcion = _detectar_absorcion(df, idx, es_bajista, vsd_score)

        # ── Descripción ───────────────────────────────────
        dir_txt = 'SHORT' if es_bajista else 'LONG'

        if absorcion['detectado']:
            tipo_abs = absorcion['tipo'].replace('_', ' ')
            desc = (
                f"🎯 VSD ABSORCIÓN {tipo_abs} | {simbolo} | "
                f"VSD={vsd_score} {nivel_txt} | "
                f"Nivel: {absorcion['nivel']:.0f} | {dir_txt}"
            )
            alerta = True
        elif vsd_score >= VSD_ALERTA:
            desc = (
                f"{icono} VSD {nivel_txt} | {simbolo} | "
                f"Score={vsd_score} | "
                f"Vel={f_velocidad:.0f} Dec={f_decision:.0f} "
                f"Con={f_continuidad:.0f} Acel={f_aceleracion:.0f}"
            )
            alerta = True
        else:
            desc  = ''
            alerta = False

        return {
            'vsd_score':  vsd_score,
            'alerta':     alerta,
            'absorcion':  absorcion['detectado'],
            'descripcion': desc,
            'factores': {
                'velocidad':   f_velocidad,
                'decision':    f_decision,
                'continuidad': f_continuidad,
                'aceleracion': f_aceleracion,
            },
        }

    except Exception as e:
        print(f"  [volumen_sintetico] Error en {simbolo}: {e}")
        return resultado_neutro


# ============================================================
#  INTEGRACIÓN EN main_v5.py — 2 cambios:
#
#  1) Al inicio, junto con los otros imports v6:
#     from volumen_sintetico_v6 import analizar_volumen_sintetico
#
#  2) En analizar_simbolo(), después del bloque de módulos v6
#     (después de la línea: obs = verificar_obs(...)):
#
#     vsd = analizar_volumen_sintetico(simbolo, es_bajista)
#     if vsd['alerta']:
#         print(f"  {vsd['descripcion']}")
#
#  NOTA: El VSD es solo informativo — no bloquea ni genera
#  señales por sí solo. Se muestra en consola como contexto.
#  Si quieres enviarlo a Telegram cuando hay absorción:
#
#     if vsd['absorcion']:
#         enviar_telegram(vsd['descripcion'])
# ============================================================
