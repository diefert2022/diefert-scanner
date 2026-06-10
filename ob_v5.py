# ============================================================
#  DIEFERT SCANNER v5 — ob_v5.py
#
#  Detecta Order Blocks frescos cercanos a una zona histórica.
#  Solo se usa para la alerta visual — NUNCA bloquea ni modifica
#  la señal de entrada.
#
#  REGLA: Un OB es válido si:
#    - Es de M5, M15, M30, H1, H4 o D1
#    - No ha sido mitigado (precio no volvió al origen)
#    - Está dentro de TOL_OB_ZONA pts de la zona histórica
#
#  RETORNA:
#    ob_en_zona(simbolo, precio_zona, es_bajista, df, tf_nombre)
#    → dict con:
#        encontrado: True/False
#        ob_high:    precio máximo del OB
#        ob_low:     precio mínimo del OB
#        tf:         timeframe donde se detectó
#        distancia:  pts entre el OB y la zona
# ============================================================

import MetaTrader5 as mt5
from utils import obtener_df
from config import (
    TF_M5, TF_M15, TF_M30, TF_H1,
    VELAS_M5, VELAS_M15, VELAS_M30, VELAS_H1,
)

# Tolerancia: el OB debe estar a menos de estos pts de la zona
TOL_OB_ZONA = 80   # pts — ajustable según índice

# Timeframes donde buscamos OBs para la alerta visual
# Orden: del más fino al más grueso
TFS_OB = [
    (TF_M5,  VELAS_M5,  "M5"),
    (TF_M15, VELAS_M15, "M15"),
    (TF_M30, VELAS_M30, "M30"),
    (TF_H1,  VELAS_H1,  "H1"),
]


def _detectar_ob_en_df(df, es_bajista):
    """
    Detecta OBs no mitigados en un DataFrame.
    Retorna lista de dicts con ob_high, ob_low, ob_mid.

    OB bajista: última vela alcista antes de impulso bajista fuerte
    OB alcista: última vela bajista antes de impulso alcista fuerte
    """
    obs = []
    if df is None or len(df) < 5:
        return obs

    avg_body = abs(df['close'] - df['open']).mean()
    umbral   = avg_body * 1.3

    for i in range(1, len(df) - 2):
        c  = df.iloc[i]
        cn = df.iloc[i + 1]

        if es_bajista:
            # Vela alcista seguida de impulso bajista fuerte
            if c['close'] > c['open'] and cn['close'] < cn['open']:
                if (cn['open'] - cn['close']) > umbral:
                    mitigado = any(
                        df.iloc[k]['high'] >= c['high']
                        for k in range(i + 2, min(i + 30, len(df)))
                    )
                    if not mitigado:
                        obs.append({
                            'ob_high': round(c['high'], 2),
                            'ob_low':  round(c['low'],  2),
                            'ob_mid':  round((c['high'] + c['low']) / 2, 2),
                        })
        else:
            # Vela bajista seguida de impulso alcista fuerte
            if c['close'] < c['open'] and cn['close'] > cn['open']:
                if (cn['close'] - cn['open']) > umbral:
                    mitigado = any(
                        df.iloc[k]['low'] <= c['low']
                        for k in range(i + 2, min(i + 30, len(df)))
                    )
                    if not mitigado:
                        obs.append({
                            'ob_high': round(c['high'], 2),
                            'ob_low':  round(c['low'],  2),
                            'ob_mid':  round((c['high'] + c['low']) / 2, 2),
                        })
    return obs


def ob_en_zona(simbolo, precio_zona, es_bajista, tol=TOL_OB_ZONA):
    """
    Busca si hay un OB no mitigado cercano a precio_zona.
    Recorre TFs de M5 a H1. Retorna el primero que encuentre.

    Parámetros:
      simbolo     → nombre del índice
      precio_zona → precio de la zona histórica detectada
      es_bajista  → True para PainX, False para GainX
      tol         → tolerancia en pts para considerar OB "en zona"

    Retorna dict:
      encontrado: True/False
      ob_high, ob_low, ob_mid, tf, distancia
    """
    for tf, velas, tf_nombre in TFS_OB:
        try:
            df = obtener_df(simbolo, tf, velas)
            if df is None or len(df) < 10:
                continue

            obs = _detectar_ob_en_df(df, es_bajista)

            for ob in obs:
                dist = abs(ob['ob_mid'] - precio_zona)
                if dist <= tol:
                    return {
                        'encontrado': True,
                        'ob_high':    ob['ob_high'],
                        'ob_low':     ob['ob_low'],
                        'ob_mid':     ob['ob_mid'],
                        'tf':         tf_nombre,
                        'distancia':  round(dist, 0),
                    }
        except Exception as e:
            print(f"  [ob_v5] Error en {simbolo} {tf_nombre}: {e}")
            continue

    return {
        'encontrado': False,
        'ob_high':    None,
        'ob_low':     None,
        'ob_mid':     None,
        'tf':         None,
        'distancia':  None,
    }
