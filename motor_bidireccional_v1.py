# ============================================================
#  DIEFERT SCANNER v5 — motor_bidireccional_v1.py
#
#  Mismo NIVEL de análisis que PainX/GainX (zonas históricas
#  D1+H4+H1 con FVG+OB+swings, CHoCH en zona, BOS+retroceso),
#  pero evaluando AMBAS direcciones — porque FlipX no tiene
#  lado fijo como PainX=venta/GainX=compra.
#
#  ⚠️ ALCANCE ACTUAL (24-ago-2026): FlipX 1-5, ya calibrado con
#  datos reales (actualizar_perfiles_flipx_v1.py). Los índices
#  FX Vol/SFX Vol se sacaron de este motor por ahora (mucho
#  volumen de señales mientras se estabilizaba P/G) — quedan
#  en PERFIL_NUEVOS comentados más abajo por si se retoman.
#
#  REEMPLAZA a estructura_nuevos_v1.py (que ya no se usa desde
#  main_v5.py — puedes borrarlo o dejarlo, no hace nada si no
#  se importa). Este módulo hace todo lo que hacía el anterior
#  y además agrega FVG+OB como confluencia real de zona.
#
#  ⚠️ HALLAZGO IMPORTANTE que resolvimos acá:
#  ─────────────────────────────────────────────────────────
#  resistencias.py y ob_v5.py usan tolerancias FIJAS en puntos
#  (TOL_AGRUPACION=50, DIST_MAX_ACTIVA=1000, TOL_OB_H1=15...)
#  calibradas para la escala de PainX/GainX (~50-150pts).
#  FX Vol/SFX Vol se mueven en escalas MUY distintas entre sí
#  (SFX Vol 99 ~71pts de SL vs SFX Vol 60 ~2365pts de SL — 33x
#  de diferencia). Usar esas tolerancias fijas tal cual haría
#  que el motor pareciera funcionar pero casi nunca detectara
#  nada útil en los símbolos grandes (zonas que nunca se separan
#  bien, "activa" casi siempre falso, OB que nunca se considera
#  "cerca").
#
#  SOLUCIÓN: cada símbolo tiene su propio PERFIL_NUEVOS (datos
#  reales de actualizar_perfiles_nuevos_v1.py) y de ahí se
#  derivan tolerancias ESCALADAS proporcionalmente — mismo
#  principio que ya usa el motor original (P70/P85 por símbolo),
#  solo que aplicado también a las tolerancias de agrupación/
#  actividad/cercanía que el motor original tenía fijas.
#
#  QUÉ SE REUTILIZA SIN TOCAR NINGÚN ARCHIVO:
#  ─────────────────────────────────────────────────────────
#  - resistencias.py: _detectar_swings, _detectar_fvgs,
#    _detectar_obs, _niveles_psicologicos, _agrupar_y_puntuar,
#    _get_df, VELAS_D1/H4/H1 (import directo, funciones ya
#    parametrizadas — no dependen de tocar el archivo).
#  - ob_v5.py: _detectar_ob (función interna parametrizada,
#    VENTANA_OB_H1). Los wrappers verificar_ob_h1/m1 SÍ tienen
#    tolerancias fijas, por eso llamamos _detectar_ob directo
#    con nuestras propias tolerancias escaladas.
#  - estructura.py: detectar_swings, detectar_tendencia,
#    detectar_bos_choch, detectar_bos_estructural.
#  - trade_tracker.py: registrar_trade (marca MicroGrid +
#    distribuye a usuarios con licencia, igual que P/G).
#  - contexto_inicial.py: _calcular_contexto_simbolo (bias
#    D1+H4+M15, PDH/PDL) — mismo patrón que ya usábamos.
#
#  QUÉ SE DEJÓ FUERA DE ESTA VERSIÓN (a propósito):
#  ─────────────────────────────────────────────────────────
#  sweep_v6.py, pd_filter_v6.py y choch_m1_v6.py (TIPO1_M1,
#  sweep, premium/discount) también tienen constantes fijas en
#  puntos (ej. TOL_EQUAL=5) que necesitarían el mismo trabajo
#  de escalado — no alcanzó a auditarlas todas con cuidado en
#  esta pasada. El núcleo que SÍ quedó completo y verificado
#  (zonas con FVG+OB+swings, TIPO1, TIPO1_OB, TIPO2) es el
#  corazón real del motor de P/G. Si funciona bien, avísame y
#  metemos sweep/premium-discount como fase 2.
#
#  SEÑALES QUE GENERA (dirección decidida en vivo, no fija):
#  ─────────────────────────────────────────────────────────
#  TIPO1    → CHoCH M5 dentro de una zona histórica fuerte
#             (score≥3, ≥2 toques) — misma jerarquía que P/G.
#  TIPO1_OB → OB H1 calibrado por símbolo, precio adentro.
#  TIPO2    → BOS estructural M15/M5 + retroceso al OB que lo
#             generó.
#  Prioridad: TIPO1 > TIPO1_OB > TIPO2 (igual que main_v5.py).
#
#  CÓMO SE LLAMA DESDE main_v5.py:
#    from motor_bidireccional_v1 import analizar_indices_bidireccionales
#    ...dentro del ciclo, UNA VEZ por vuelta:
#    analizar_indices_bidireccionales()
# ============================================================

import os
import time
from datetime import datetime

import MetaTrader5 as mt5

from config import TF_M5, TF_M15, TF_H1, VELAS_M5, VELAS_M15, VELAS_H1
from utils import obtener_df, enviar_telegram, puede_enviar, registrar_envio
from estructura import (
    detectar_swings, detectar_tendencia,
    detectar_bos_choch, detectar_bos_estructural,
)
from trade_tracker import registrar_trade
from contexto_inicial import _calcular_contexto_simbolo

# ── Piezas reutilizadas de resistencias.py (sin tocar el archivo) ──
from resistencias import (
    _detectar_swings as _r_detectar_swings,
    _detectar_fvgs as _r_detectar_fvgs,
    _detectar_obs as _r_detectar_obs,
    _niveles_psicologicos as _r_niveles_psicologicos,
    _agrupar_y_puntuar as _r_agrupar_y_puntuar,
    _get_df as _r_get_df,
    VELAS_D1 as _VELAS_D1_ZONAS,
    VELAS_H4 as _VELAS_H4_ZONAS,
    VELAS_H1 as _VELAS_H1_ZONAS,
)

# ── Pieza reutilizada de ob_v5.py (función interna parametrizada) ──
from ob_v5 import _detectar_ob as _ob_detectar_ob, VENTANA_OB_H1

# ── Símbolos bidireccionales (ahora solo FlipX — los Vol se sacaron) ──
SIMBOLOS_ESTRUCTURA_NUEVOS = [
    "FlipX 1", "FlipX 2", "FlipX 3", "FlipX 4", "FlipX 5",
]

# ── Perfil calibrado real por símbolo — PENDIENTE ──
# Esperando el archivo perfiles_flipx_actualizados_<fecha>.py de
# actualizar_perfiles_flipx_v1.py. Mientras esté vacío, el símbolo
# se salta solo (ver el guard en analizar_indices_bidireccionales)
# — no crashea, simplemente no genera señales todavía.
PERFIL_NUEVOS = {
    # Los Vol se sacaron de este motor por ahora (24-ago-2026) —
    # quedan comentados, no borrados, por si se retoman más adelante:
    # "FX Vol 20":  {"sl_minimo": 206,  "rango_diario": 2819,  "rango_m15": 193,  "ob_h4_min": 733,  "ob_h1_min": 350,  "fvg_bull_fuerte": 73,  "fvg_bear_fuerte": 69,  "rango_saturado": 2537},
    # "FX Vol 40":  {"sl_minimo": 627,  "rango_diario": 8733,  "rango_m15": 593,  "ob_h4_min": 2219, "ob_h1_min": 1120, "fvg_bull_fuerte": 229, "fvg_bear_fuerte": 219, "rango_saturado": 7860},
    # "FX Vol 60":  {"sl_minimo": 174,  "rango_diario": 2230,  "rango_m15": 160,  "ob_h4_min": 612,  "ob_h1_min": 298,  "fvg_bull_fuerte": 61,  "fvg_bear_fuerte": 60,  "rango_saturado": 2007},
    # "FX Vol 80":  {"sl_minimo": 326,  "rango_diario": 4309,  "rango_m15": 304,  "ob_h4_min": 1193, "ob_h1_min": 565,  "fvg_bull_fuerte": 118, "fvg_bear_fuerte": 113, "rango_saturado": 3878},
    # "FX Vol 99":  {"sl_minimo": 353,  "rango_diario": 4628,  "rango_m15": 334,  "ob_h4_min": 1310, "ob_h1_min": 618,  "fvg_bull_fuerte": 125, "fvg_bear_fuerte": 128, "rango_saturado": 4165},
    # "SFX Vol 20": {"sl_minimo": 135,  "rango_diario": 1560,  "rango_m15": 102,  "ob_h4_min": 427,  "ob_h1_min": 224,  "fvg_bull_fuerte": 49,  "fvg_bear_fuerte": 53,  "rango_saturado": 1404},
    # "SFX Vol 40": {"sl_minimo": 446,  "rango_diario": 5651,  "rango_m15": 366,  "ob_h4_min": 1465, "ob_h1_min": 800,  "fvg_bull_fuerte": 178, "fvg_bear_fuerte": 177, "rango_saturado": 5086},
    # "SFX Vol 60": {"sl_minimo": 2365, "rango_diario": 33088, "rango_m15": 1975, "ob_h4_min": 8019, "ob_h1_min": 4257, "fvg_bull_fuerte": 983, "fvg_bear_fuerte": 975, "rango_saturado": 29779},
    # "SFX Vol 80": {"sl_minimo": 1429, "rango_diario": 20685, "rango_m15": 1152, "ob_h4_min": 5321, "ob_h1_min": 2598, "fvg_bull_fuerte": 597, "fvg_bear_fuerte": 579, "rango_saturado": 18616},
    # "SFX Vol 99": {"sl_minimo": 71,   "rango_diario": 889,   "rango_m15": 51,   "ob_h4_min": 210,  "ob_h1_min": 111,  "fvg_bull_fuerte": 26,  "fvg_bear_fuerte": 25,  "rango_saturado": 800},
    #
    # FlipX 1-5 — calibrado real (actualizar_perfiles_flipx_v1.py, 24-ago-2026):
    "FlipX 1": {"sl_minimo": 58,  "rango_diario": 630,  "rango_m15": 47,  "ob_h4_min": 161, "ob_h1_min": 87,  "fvg_bull_fuerte": 18, "fvg_bear_fuerte": 17, "rango_saturado": 567},
    "FlipX 2": {"sl_minimo": 85,  "rango_diario": 981,  "rango_m15": 74,  "ob_h4_min": 275, "ob_h1_min": 136, "fvg_bull_fuerte": 28, "fvg_bear_fuerte": 28, "rango_saturado": 883},
    "FlipX 3": {"sl_minimo": 113, "rango_diario": 1496, "rango_m15": 101, "ob_h4_min": 384, "ob_h1_min": 187, "fvg_bull_fuerte": 37, "fvg_bear_fuerte": 36, "rango_saturado": 1346},
    "FlipX 4": {"sl_minimo": 140, "rango_diario": 1637, "rango_m15": 127, "ob_h4_min": 462, "ob_h1_min": 230, "fvg_bull_fuerte": 47, "fvg_bear_fuerte": 45, "rango_saturado": 1473},
    "FlipX 5": {"sl_minimo": 171, "rango_diario": 2217, "rango_m15": 156, "ob_h4_min": 589, "ob_h1_min": 291, "fvg_bull_fuerte": 58, "fvg_bear_fuerte": 58, "rango_saturado": 1995},
}

# ── Parámetros generales (scale-invariant, mismos que main_v5.py) ──
RR_MINIMO       = 2.0
COOLDOWN_SEG    = 1200   # 20 min entre señales del mismo símbolo
TOQUES_MINIMOS  = 2      # zona válida necesita ≥2 toques (cuenta, no pts)
SCORE_ZONA_MIN  = 3      # zona válida necesita score ≥3 (cuenta, no pts)

# ── Validación de metodología (24-ago-2026) ─────────────────
# Mismo criterio que main_v5.py: mientras se valida la calidad
# de la zona real (D1+H4+H1) + CHoCH confirmado en M5, se apagan
# TIPO1_OB y TIPO2 acá también. Reversible: poner en False
# reactiva los 3 tipos tal cual estaban.
SOLO_TIPO1_ACTIVO = True
INTERVALO_ZONAS_SEG = 900   # recalcular zonas cada 15 min, igual que resistencias.py

# ── Contexto macro — caché propio, independiente de contexto_inicial.py ──
REFRESH_MINUTOS_CTX = 60
_contexto_nuevos    = {}
_ultimo_refresh_ctx = 0

# ── Caché de zonas propio — independiente del de resistencias.py ──
_cache_zonas          = {}
_ultimo_calculo_zonas = {}


def _clave(simbolo):
    return f"bidir_{simbolo}"


def _latido():
    """
    Heartbeat propio — mismo archivo que usa main_v5.py, para que
    el watchdog NO piense que el scanner se colgó mientras este
    módulo calcula las 10 zonas nuevas (puede tardar varios
    minutos la primera vez). No importa _latido() de main_v5.py
    para evitar import circular (main_v5.py importa este módulo);
    en vez de eso escribe el mismo archivo de forma independiente.
    """
    try:
        heartbeat_path = os.path.join(os.path.dirname(__file__), "heartbeat.txt")
        with open(heartbeat_path, 'w', encoding='utf-8') as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass


def _parametros_escalados(perfil):
    """
    Deriva tolerancias ESCALADAS a partir del perfil real del símbolo,
    en vez de usar los números fijos de resistencias.py/ob_v5.py
    (calibrados para la escala de PainX/GainX). Las proporciones
    vienen de comparar los valores fijos originales contra el
    rango_m15/rango_diario real de PainX 400 (rango_m15≈51,
    TOL_AGRUPACION=50 → casi 1:1; DIST_MAX_ACTIVA=1000 ≈ 1.7x
    rango_diario≈592).
    """
    rango_m15    = perfil["rango_m15"]
    rango_diario = perfil["rango_diario"]
    ob_h1_min    = perfil["ob_h1_min"]
    ob_m1_min    = max(3, round(ob_h1_min / 15))

    return {
        "tol_agrupacion":  max(10, round(rango_m15 * 1.0)),
        "dist_max_activa": round(rango_diario * 1.7),
        "ob_h1_fuerte":    round(ob_h1_min * 1.35),
        "ob_m1_min":       ob_m1_min,
        "ob_m1_fuerte":    ob_m1_min * 2,
        "tol_ob_h1":       max(5, round(rango_m15 * 0.3)),
        "fvg_min_h1":      max(5, round(rango_m15 * 0.3)),
        "fvg_min_h4":      max(8, round(rango_m15 * 0.4)),
        "fvg_min_d1":      max(10, round(rango_m15 * 1.0)),
    }


def _refrescar_contexto_si_necesario():
    global _ultimo_refresh_ctx
    ahora = time.time()
    if _contexto_nuevos and (ahora - _ultimo_refresh_ctx) < REFRESH_MINUTOS_CTX * 60:
        return
    print("  📊 [Motor bidireccional] Calculando contexto macro (FX Vol / SFX Vol)...")
    for simbolo in SIMBOLOS_ESTRUCTURA_NUEVOS:
        try:
            _contexto_nuevos[simbolo] = _calcular_contexto_simbolo(simbolo)
        except Exception as e:
            print(f"  [Motor bidireccional][contexto] Error en {simbolo}: {e}")
        finally:
            _latido()
    _ultimo_refresh_ctx = ahora
    print("  ✅ [Motor bidireccional] Contexto macro listo\n")


def _calcular_zonas_bidireccional(simbolo, esc):
    """
    Igual que resistencias.py._calcular_niveles, pero detecta FVG
    y OB en AMBAS direcciones (bull y bear) y fusiona todo junto,
    en vez de una sola dirección fija. Los swings (SH/SL) ya eran
    bidireccionales en el original — eso no cambia.
    """
    print(f"  🔍 [Motor bidireccional] Calculando zonas: {simbolo}...")
    t0 = time.time()
    todos = []
    precio_actual = None

    # ── Daily ──────────────────────────────────────────────
    df_d1 = _r_get_df(simbolo, mt5.TIMEFRAME_D1, _VELAS_D1_ZONAS)
    if df_d1 is not None and len(df_d1) > 10:
        precio_actual = float(df_d1['close'].iloc[-1])
        for s in _r_detectar_swings(df_d1, lookback=3):
            s['tf'] = 'D1'; todos.append(s)
        for es_baj in (True, False):
            for f in _r_detectar_fvgs(df_d1, es_baj, min_tam=esc["fvg_min_d1"]):
                f['tf'] = 'D1'; todos.append(f)
            for o in _r_detectar_obs(df_d1, es_baj, mult=1.5, simbolo=simbolo, timeframe="D1"):
                o['tf'] = 'D1'; todos.append(o)

    # ── H4 ─────────────────────────────────────────────────
    df_h4 = _r_get_df(simbolo, mt5.TIMEFRAME_H4, _VELAS_H4_ZONAS)
    if df_h4 is not None and len(df_h4) > 10:
        if precio_actual is None:
            precio_actual = float(df_h4['close'].iloc[-1])
        for s in _r_detectar_swings(df_h4, lookback=5):
            s['tf'] = 'H4'; todos.append(s)
        for es_baj in (True, False):
            for f in _r_detectar_fvgs(df_h4, es_baj, min_tam=esc["fvg_min_h4"]):
                f['tf'] = 'H4'; todos.append(f)
            for o in _r_detectar_obs(df_h4, es_baj, mult=1.3, simbolo=simbolo, timeframe="H4"):
                o['tf'] = 'H4'; todos.append(o)

    # ── H1 ─────────────────────────────────────────────────
    df_h1 = _r_get_df(simbolo, mt5.TIMEFRAME_H1, _VELAS_H1_ZONAS)
    if df_h1 is not None and len(df_h1) > 10:
        if precio_actual is None:
            precio_actual = float(df_h1['close'].iloc[-1])
        for s in _r_detectar_swings(df_h1, lookback=5):
            s['tf'] = 'H1'; todos.append(s)
        for es_baj in (True, False):
            for f in _r_detectar_fvgs(df_h1, es_baj, min_tam=esc["fvg_min_h1"]):
                f['tf'] = 'H1'; todos.append(f)
            for o in _r_detectar_obs(df_h1, es_baj, mult=1.3, simbolo=simbolo, timeframe="H1"):
                o['tf'] = 'H1'; todos.append(o)

    if precio_actual is None:
        print(f"  ❌ [Motor bidireccional] Sin datos para {simbolo}")
        return []

    for p in _r_niveles_psicologicos(precio_actual):
        p['tf'] = 'PSICO'; todos.append(p)

    niveles = _r_agrupar_y_puntuar(todos, precio_actual, tol=esc["tol_agrupacion"])

    # _agrupar_y_puntuar calcula 'activa' con DIST_MAX_ACTIVA fijo
    # (1000pts) — lo corregimos acá con el umbral escalado del símbolo.
    for z in niveles:
        z['activa'] = z['dist'] <= esc["dist_max_activa"]

    elapsed = time.time() - t0
    activas = len([n for n in niveles if n['activa']])
    print(f"  ✅ [Motor bidireccional] {simbolo}: {len(niveles)} zonas ({activas} activas) — {elapsed:.1f}s")
    return niveles


def _actualizar_zonas_si_necesario(simbolo, esc, forzar=False):
    ahora = time.time()
    ultimo = _ultimo_calculo_zonas.get(simbolo, 0)
    if forzar or simbolo not in _cache_zonas or (ahora - ultimo) >= INTERVALO_ZONAS_SEG:
        try:
            _cache_zonas[simbolo] = _calcular_zonas_bidireccional(simbolo, esc)
            _ultimo_calculo_zonas[simbolo] = ahora
        except Exception as e:
            print(f"  ❌ [Motor bidireccional] Error zonas {simbolo}: {e}")


def _detectar_choch_en_zona(zonas_validas, df_m5, esc):
    """
    TIPO1 — CHoCH M5 detectado, y coincide en dirección y cercanía
    con una zona histórica fuerte. La zona "manda" la dirección:
    RESISTENCIA arriba del precio → venta, SOPORTE abajo → compra
    (campo 'direccion' de resistencias.py, ya es dinámico por precio).
    """
    if df_m5 is None or len(df_m5) < 20 or not zonas_validas:
        return {'detectado': False}

    precio_actual = float(df_m5['close'].iloc[-1])
    swings_m5 = detectar_swings(df_m5, ventana=3)
    if not swings_m5:
        return {'detectado': False}

    tendencia_m5 = detectar_tendencia(swings_m5)
    choch = detectar_bos_choch(df_m5, swings_m5, tendencia_m5)
    if not choch or choch['tipo'] != 'CHoCH':
        return {'detectado': False}

    idx_ultima = len(df_m5) - 1
    if (idx_ultima - choch['idx']) > 3:
        return {'detectado': False}

    es_bajista_choch = choch['direccion'] == 'bajista'

    for zona in zonas_validas:
        es_bajista_zona = 'RESISTENCIA' in zona['direccion']
        if es_bajista_zona != es_bajista_choch:
            continue
        if abs(precio_actual - zona['precio']) <= esc["tol_agrupacion"]:
            return {
                'detectado':   True,
                'tipo':        'TIPO1',
                'es_bajista':  es_bajista_zona,
                'zona':        zona,
                'precio':      precio_actual,
                'choch_nivel': choch['nivel'],
            }

    return {'detectado': False}


def _detectar_ob_h1_activo(simbolo, perfil, esc):
    """TIPO1_OB — OB H1 calibrado por símbolo, precio adentro (cualquier dirección)."""
    df_h1 = obtener_df(simbolo, TF_H1, VELAS_H1)
    if df_h1 is None:
        return {'detectado': False}

    for es_bajista in (True, False):
        r = _ob_detectar_ob(
            df_h1, es_bajista,
            perfil["ob_h1_min"], esc["ob_h1_fuerte"],
            VENTANA_OB_H1, esc["tol_ob_h1"],
        )
        if r['detectado']:
            r['tipo']       = 'TIPO1_OB'
            r['es_bajista'] = es_bajista
            r['precio']     = r['ob_mid']
            return r

    return {'detectado': False}


def _detectar_bos_retroceso(simbolo):
    """TIPO2 — BOS estructural M15/M5 + retroceso al OB que lo generó (cualquier dirección)."""
    for tf, velas, tf_nombre in [(TF_M15, VELAS_M15, 'M15'), (TF_M5, VELAS_M5, 'M5')]:
        df = obtener_df(simbolo, tf, velas)
        if df is None or len(df) < 20:
            continue

        precio_actual = float(df['close'].iloc[-1])
        swings = detectar_swings(df, ventana=4 if tf == TF_M15 else 3)
        if not swings:
            continue

        for es_bajista in (True, False):
            bos = detectar_bos_estructural(df, swings, es_bajista)
            if not bos['detectado']:
                continue

            idx_ultima = len(df) - 1
            if (idx_ultima - bos['idx']) > 5:
                continue

            ob_high = ob_low = None
            for i in range(bos['idx'] - 1, max(0, bos['idx'] - 10), -1):
                c = df.iloc[i]
                if es_bajista:
                    if c['close'] > c['open']:
                        ob_high = round(float(c['high']), 2)
                        ob_low  = round(float(c['low']),  2)
                        break
                else:
                    if c['close'] < c['open']:
                        ob_high = round(float(c['high']), 2)
                        ob_low  = round(float(c['low']),  2)
                        break

            if ob_high is None:
                continue

            if ob_low <= precio_actual <= ob_high:
                return {
                    'detectado':  True,
                    'tipo':       'TIPO2',
                    'es_bajista': es_bajista,
                    'tf_bos':     tf_nombre,
                    'ob_high':    ob_high,
                    'ob_low':     ob_low,
                    'precio':     precio_actual,
                    'bos_nivel':  bos['nivel'],
                }

    return {'detectado': False}


def _calcular_sl(df_m5, precio_entrada, es_bajista, perfil):
    sl_min = perfil["sl_minimo"]
    ultimas = df_m5.tail(10)
    if es_bajista:
        sl_calculado = float(ultimas['high'].max())
        sl = max(sl_calculado, precio_entrada + sl_min)
    else:
        sl_calculado = float(ultimas['low'].min())
        sl = min(sl_calculado, precio_entrada - sl_min)
    return round(sl, 2)


def _calcular_tp(precio_entrada, sl, es_bajista, rr=RR_MINIMO):
    dist_sl = abs(precio_entrada - sl)
    if dist_sl <= 0:
        return None
    if es_bajista:
        tp1 = precio_entrada - dist_sl * rr
        tp2 = precio_entrada - dist_sl * rr * 1.5
    else:
        tp1 = precio_entrada + dist_sl * rr
        tp2 = precio_entrada + dist_sl * rr * 1.5
    return {
        'sl': round(sl, 2), 'tp1': round(tp1, 2), 'tp2': round(tp2, 2),
        'dist_sl': round(dist_sl, 0), 'rr': rr,
    }


def _construir_mensaje(simbolo, es_bajista, precio, tps, señal, ctx=None):
    icono  = '📉' if es_bajista else '📈'
    accion = 'VENTA' if es_bajista else 'COMPRA'
    tipo   = señal['tipo']
    tipo_txt = {
        'TIPO1':    'ZONA HISTÓRICA + CHoCH',
        'TIPO1_OB': 'OB H1 CALIBRADO 🏛',
        'TIPO2':    f"CONTINUACIÓN BOS {señal.get('tf_bos', '')}",
    }.get(tipo, tipo)

    lineas = [
        f"{icono} <b>SEÑAL COMPLETA — {accion} | {simbolo}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"📌 Tipo: {tipo_txt}",
        f"💰 Entrada: <b>{precio:.0f}</b>",
        f"🛑 SL: {tps['sl']:.0f}  ({tps['dist_sl']:.0f} pts)",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 TP1: {tps['tp1']:.0f}  RR {tps['rr']}:1",
        f"🎯 TP2: {tps['tp2']:.0f}  RR {tps['rr'] * 1.5:.1f}:1",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if tipo == 'TIPO1' and señal.get('zona'):
        zona = señal['zona']
        tf_zona = '+'.join(zona.get('tfs', ['?']))
        lineas.append(
            f"🏛 Zona {tf_zona}: {zona['precio']:.0f} | {zona.get('fuerza_txt','')} | "
            f"{zona.get('n_toques',0)} toques | score={zona.get('score',0)}"
        )

    if tipo == 'TIPO1_OB':
        fuerza = '🔥 FUERTE' if señal.get('es_fuerte') else 'Normal'
        lineas.append(
            f"🏛 OB H1 {fuerza}: [{señal['ob_low']:.0f}–{señal['ob_high']:.0f}] "
            f"cuerpo={señal.get('ob_body',0):.0f}pts"
        )

    if ctx and ctx.get('bias_general'):
        pdh = f"PDH={ctx['pdh']:.0f}" if ctx.get('pdh') else 'PDH=?'
        pdl = f"PDL={ctx['pdl']:.0f}" if ctx.get('pdl') else 'PDL=?'
        lineas.append(f"📊 Bias D1+H4+M15: {ctx['bias_general']} | {pdh} {pdl}")

    lineas.append("⚙️ Motor completo (zonas+FVG+OB+CHoCH/BOS) — sin sweep/premium-discount todavía.")
    lineas.append(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    return '\n'.join(lineas)


def analizar_indices_bidireccionales():
    """
    Recorre SIMBOLOS_ESTRUCTURA_NUEVOS con el motor completo
    bidireccional. Llamar UNA VEZ por ciclo desde main_v5.py
    (recorre su propia lista adentro).
    """
    _refrescar_contexto_si_necesario()

    for simbolo in SIMBOLOS_ESTRUCTURA_NUEVOS:
        try:
            if simbolo not in PERFIL_NUEVOS:
                continue   # todavía sin calibrar (esperando perfiles_flipx_actualizados_*.py)
            perfil = PERFIL_NUEVOS[simbolo]
            esc    = _parametros_escalados(perfil)

            _actualizar_zonas_si_necesario(simbolo, esc)
            _latido()   # ← clave: heartbeat después de lo más pesado (zonas)
            todas_zonas = _cache_zonas.get(simbolo, [])
            zonas_validas = [
                z for z in todas_zonas
                if z.get('activa') and z.get('n_toques', 0) >= TOQUES_MINIMOS
                and z.get('score', 0) >= SCORE_ZONA_MIN
            ]

            df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
            if df_m5 is None or len(df_m5) < 20:
                continue

            clave = _clave(simbolo)
            if not puede_enviar(clave, COOLDOWN_SEG):
                continue

            # Jerarquía: TIPO1 > TIPO1_OB > TIPO2 (igual que main_v5.py)
            señal = _detectar_choch_en_zona(zonas_validas, df_m5, esc)
            if not señal['detectado'] and not SOLO_TIPO1_ACTIVO:
                señal = _detectar_ob_h1_activo(simbolo, perfil, esc)
            if not señal['detectado'] and not SOLO_TIPO1_ACTIVO:
                señal = _detectar_bos_retroceso(simbolo)
            if not señal['detectado']:
                continue

            es_bajista     = señal['es_bajista']
            precio_entrada = float(señal['precio'])

            sl  = _calcular_sl(df_m5, precio_entrada, es_bajista, perfil)
            tps = _calcular_tp(precio_entrada, sl, es_bajista)
            if not tps or tps['rr'] < RR_MINIMO:
                continue

            msg = _construir_mensaje(
                simbolo, es_bajista, precio_entrada, tps, señal,
                ctx=_contexto_nuevos.get(simbolo),
            )
            enviar_telegram(msg)
            registrar_envio(clave)

            registrar_trade(
                simbolo=simbolo,
                es_bajista=es_bajista,
                precio_entrada=precio_entrada,
                sl=tps['sl'],
                tp1=tps['tp1'],
                tp2=tps['tp2'],
                score_poi=señal.get('zona', {}).get('score', 0),
                trigger=f"BIDIR_{señal['tipo']}",
            )

            accion_txt = 'VENTA' if es_bajista else 'COMPRA'
            print(
                f"  ✅ [Motor bidireccional] SEÑAL {señal['tipo']} | {simbolo} | {accion_txt} | "
                f"entrada={precio_entrada:.0f} SL={tps['sl']:.0f} TP1={tps['tp1']:.0f}"
            )

        except Exception as e:
            print(f"  [Motor bidireccional] Error en {simbolo}: {e}")
        finally:
            _latido()   # heartbeat siempre, incluso si el símbolo dio error
