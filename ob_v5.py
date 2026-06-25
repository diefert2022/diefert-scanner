# ============================================================
#  DIEFERT SCANNER v6 — ob_v5.py
#
#  MÓDULO INDEPENDIENTE — NO modifica ningún archivo existente.
#  Principio de adición: solo suma información, nunca bloquea.
#
#  QUÉ HACE:
#  ─────────────────────────────────────────────────────────
#  Detecta Order Blocks H1 y M1 usando los umbrales
#  calibrados por índice desde config_v413.py.
#
#  POR QUÉ FALTABA EN v5:
#  ─────────────────────────────────────────────────────────
#  Al reescribir el scanner desde v4 a v5, los módulos
#  ob_m1.py y la lógica de OB H1 quedaron fuera.
#  config_v413.py tiene ob_h1_min y ob_m1_min perfectamente
#  calibrados por CSV real pero nadie los consumía.
#
#  RESULTADO: PainX 400 (el que más reacciona) tenía umbrales
#  de OB de config.py viejo (ob_h1_min=110, P85) en lugar
#  del calibrado real (ob_h1_min=79, P70) → 30% menos OBs
#  detectados → menos señales.
#
#  QUÉ DETECTA:
#  ─────────────────────────────────────────────────────────
#  OB H1:
#    Última vela contraria antes de un impulso fuerte H1.
#    Cuerpo >= ob_h1_min del índice (config_v413).
#    El precio retrocede al OB → entrada de alta probabilidad.
#
#  OB M1:
#    Última vela contraria antes de un impulso fuerte M1.
#    Cuerpo >= ob_m1_min del índice (config_v413).
#    Útil para entradas precisas dentro de una zona H1.
#
#  DEFINICIÓN SMC DE OB:
#    OB Bajista: última vela ALCISTA antes de impulso bajista
#      → cuerpo >= umbral → precio retrocede al OB → SHORT
#    OB Alcista: última vela BAJISTA antes de impulso alcista
#      → cuerpo >= umbral → precio retrocede al OB → LONG
#
#  USO:
#    from ob_v5 import verificar_ob_h1, verificar_ob_m1, verificar_obs
#
#    # Verificar ambos de una vez:
#    obs = verificar_obs(simbolo, precio_actual, es_bajista)
#    obs['ob_h1']['detectado']   → True/False
#    obs['ob_m1']['detectado']   → True/False
#    obs['hay_confluencia']      → True si H1 + M1 coinciden
#
#  RETORNA cada OB:
#    {
#      'detectado':   True/False,
#      'ob_high':     precio máximo del OB,
#      'ob_low':      precio mínimo del OB,
#      'ob_mid':      precio medio (50% del OB),
#      'ob_body':     tamaño del cuerpo en pts,
#      'precio_en_ob': True si precio actual está dentro,
#      'velas_atras': cuántas velas atrás está el OB,
#      'es_fuerte':   True si cuerpo >= umbral "fuerte" del índice,
#      'descripcion': texto para Telegram/consola,
#    }
# ============================================================

from utils import obtener_df
from config import TF_H1, TF_M1, VELAS_H1, VELAS_M1
from config_v413 import get_config

# Cuántas velas buscar hacia atrás para el OB
VENTANA_OB_H1 = 30   # últimas 30 velas H1 (~30 horas)
VENTANA_OB_M1 = 50   # últimas 50 velas M1 (~50 minutos)

# Tolerancia: el precio puede estar a N pts del OB y se considera "en zona"
TOL_OB_H1 = 15   # pts — tolerancia para OB H1
TOL_OB_M1 = 5    # pts — tolerancia para OB M1


def _detectar_ob(df, es_bajista, ob_min, ob_fuerte, ventana, tol):
    """
    Función interna. Detecta el OB más reciente en un dataframe.

    Lógica:
    1. Busca el impulso más fuerte reciente (la vela de mayor rango)
    2. Busca la última vela contraria ANTES de ese impulso
    3. Verifica que su cuerpo >= ob_min
    4. Verifica si el precio actual está dentro del OB

    Parámetros:
      df         → dataframe con OHLC
      es_bajista → True para PainX (busca OB bajista = última alcista)
      ob_min     → tamaño mínimo del cuerpo para ser OB válido
      ob_fuerte  → tamaño para ser OB "fuerte" (P85)
      ventana    → cuántas velas hacia atrás buscar
      tol        → tolerancia en pts para "precio en OB"
    """
    resultado_vacio = {
        'detectado':    False,
        'ob_high':      None,
        'ob_low':       None,
        'ob_mid':       None,
        'ob_body':      None,
        'precio_en_ob': False,
        'velas_atras':  None,
        'es_fuerte':    False,
        'descripcion':  'Sin OB detectado',
    }

    if df is None or len(df) < ventana + 5:
        return resultado_vacio

    precio_actual = round(float(df['close'].iloc[-1]), 2)
    n = len(df)
    inicio = max(0, n - ventana)

    # ── Paso 1: encontrar el impulso más fuerte ────────────
    # El impulso es la vela de mayor rango en la ventana
    # En dirección bajista: buscamos vela bajista fuerte
    # En dirección alcista: buscamos vela alcista fuerte
    mejor_impulso_idx  = None
    mejor_impulso_rng  = 0

    for i in range(inicio, n):
        v = df.iloc[i]
        rango = v['high'] - v['low']
        cuerpo = abs(v['close'] - v['open'])

        if es_bajista:
            # Impulso bajista: cierre < apertura Y rango grande
            if v['close'] < v['open'] and rango > mejor_impulso_rng:
                mejor_impulso_rng = rango
                mejor_impulso_idx = i
        else:
            # Impulso alcista: cierre > apertura Y rango grande
            if v['close'] > v['open'] and rango > mejor_impulso_rng:
                mejor_impulso_rng = rango
                mejor_impulso_idx = i

    if mejor_impulso_idx is None or mejor_impulso_idx == 0:
        return resultado_vacio

    # ── Paso 2: buscar la última vela CONTRARIA antes del impulso ──
    ob_idx = None
    for i in range(mejor_impulso_idx - 1, max(inicio - 1, -1), -1):
        v = df.iloc[i]
        cuerpo = abs(v['close'] - v['open'])

        if cuerpo < ob_min:
            continue   # cuerpo muy pequeño → no es OB válido

        if es_bajista:
            # OB bajista = última vela ALCISTA antes del impulso bajista
            if v['close'] > v['open']:
                ob_idx = i
                break
        else:
            # OB alcista = última vela BAJISTA antes del impulso alcista
            if v['close'] < v['open']:
                ob_idx = i
                break

    if ob_idx is None:
        return resultado_vacio

    # ── Paso 3: extraer datos del OB ──────────────────────
    vela_ob  = df.iloc[ob_idx]
    ob_high  = round(float(vela_ob['high']),  2)
    ob_low   = round(float(vela_ob['low']),   2)
    ob_mid   = round((ob_high + ob_low) / 2,  2)
    ob_body  = round(abs(float(vela_ob['close']) - float(vela_ob['open'])), 2)
    velas_atras = (n - 1) - ob_idx
    es_fuerte   = ob_body >= ob_fuerte

    # ── Paso 4: verificar si precio está en el OB ─────────
    precio_en_ob = (
        (ob_low - tol) <= precio_actual <= (ob_high + tol)
    )

    if not precio_en_ob:
        return resultado_vacio

    # ── Construir descripción ──────────────────────────────
    tipo_ob  = 'Bajista' if es_bajista else 'Alcista'
    fuerza   = '🔥 FUERTE' if es_fuerte else '📦 Normal'
    desc = (
        f"📦 OB {tipo_ob} {fuerza} | "
        f"Zona [{ob_low:.0f}–{ob_high:.0f}] | "
        f"Cuerpo={ob_body:.0f}pts | "
        f"Hace {velas_atras} velas"
    )

    return {
        'detectado':    True,
        'ob_high':      ob_high,
        'ob_low':       ob_low,
        'ob_mid':       ob_mid,
        'ob_body':      ob_body,
        'precio_en_ob': precio_en_ob,
        'velas_atras':  velas_atras,
        'es_fuerte':    es_fuerte,
        'descripcion':  desc,
    }


def verificar_ob_h1(simbolo, precio_actual, es_bajista):
    """
    Detecta OB H1 usando umbrales calibrados de config_v413.

    Para PainX (es_bajista=True):
      Busca última vela alcista H1 antes de impulso bajista.
      El precio debe estar retrocediendo hacia esa zona.

    Para GainX (es_bajista=False):
      Busca última vela bajista H1 antes de impulso alcista.
      El precio debe estar retrocediendo hacia esa zona.
    """
    try:
        cfg      = get_config(simbolo)
        ob_min   = cfg.get('ob_h1_min',    79)    # P70 por defecto
        ob_fuerte = cfg.get('ob_h1_fuerte', 110)  # P85 por defecto

        df = obtener_df(simbolo, TF_H1, VELAS_H1)
        if df is None:
            return {'detectado': False, 'descripcion': 'Sin datos H1'}

        return _detectar_ob(df, es_bajista, ob_min, ob_fuerte, VENTANA_OB_H1, TOL_OB_H1)

    except Exception as e:
        print(f"  [ob_v5] Error OB H1 {simbolo}: {e}")
        return {'detectado': False, 'descripcion': f'Error: {e}'}


def verificar_ob_m1(simbolo, precio_actual, es_bajista):
    """
    Detecta OB M1 usando umbrales calibrados de config_v413.
    Útil para entrada precisa dentro de una zona H1 ya confirmada.

    ob_m1_min es el umbral de cuerpo mínimo en M1.
    Para todos los índices está calibrado en ~6 pts (cuerpo mín M1).
    """
    try:
        cfg      = get_config(simbolo)
        ob_min   = cfg.get('ob_m1_min', 6)    # cuerpo mínimo M1
        ob_fuerte = ob_min * 2                 # "fuerte" = doble del mínimo

        df = obtener_df(simbolo, TF_M1, VELAS_M1)
        if df is None:
            return {'detectado': False, 'descripcion': 'Sin datos M1'}

        return _detectar_ob(df, es_bajista, ob_min, ob_fuerte, VENTANA_OB_M1, TOL_OB_M1)

    except Exception as e:
        print(f"  [ob_v5] Error OB M1 {simbolo}: {e}")
        return {'detectado': False, 'descripcion': f'Error: {e}'}


def verificar_obs(simbolo, precio_actual, es_bajista):
    """
    Función principal. Verifica OB H1 y OB M1 juntos.

    Retorna dict con:
      ob_h1:          resultado de verificar_ob_h1
      ob_m1:          resultado de verificar_ob_m1
      hay_confluencia: True si ambos detectados (H1 + M1)
      score_ob:        0, 1 o 2 (cuántos OBs activos)
      descripcion:     resumen para consola
    """
    ob_h1 = verificar_ob_h1(simbolo, precio_actual, es_bajista)
    ob_m1 = verificar_ob_m1(simbolo, precio_actual, es_bajista)

    confluencia = ob_h1['detectado'] and ob_m1['detectado']
    score = sum([ob_h1['detectado'], ob_m1['detectado']])

    if confluencia:
        desc = f"🏛 OB H1+M1 CONFLUENCIA | {ob_h1['descripcion']}"
    elif ob_h1['detectado']:
        desc = f"🏛 {ob_h1['descripcion']}"
    elif ob_m1['detectado']:
        desc = f"📍 {ob_m1['descripcion']}"
    else:
        desc = 'Sin OB activo'

    return {
        'ob_h1':          ob_h1,
        'ob_m1':          ob_m1,
        'hay_confluencia': confluencia,
        'score_ob':        score,
        'descripcion':     desc,
    }


# ============================================================
#  COMPATIBILIDAD — ob_en_zona()
#  alertas_v5.py importa esta función del ob_v5 anterior.
#  Se mantiene para no romper alertas_v5.py.
#  Internamente usa la nueva lógica calibrada.
# ============================================================

def ob_en_zona(simbolo, precio_zona, es_bajista, tolerancia=50):
    """
    Verifica si hay un OB H1 cerca de una zona histórica.
    Compatibilidad con alertas_v5.py.

    Retorna dict:
      encontrado: True/False
      tf:         'H1'
      ob_high:    precio máximo del OB
      ob_low:     precio mínimo del OB
    """
    try:
        cfg      = get_config(simbolo)
        ob_min   = cfg.get('ob_h1_min',    79)
        ob_fuerte = cfg.get('ob_h1_fuerte', 110)

        df = obtener_df(simbolo, TF_H1, VELAS_H1)
        if df is None:
            return {'encontrado': False}

        resultado = _detectar_ob(df, es_bajista, ob_min, ob_fuerte, VENTANA_OB_H1, tolerancia)

        if not resultado['detectado']:
            return {'encontrado': False}

        # Verificar que el OB está cerca de la zona histórica
        ob_mid = resultado['ob_mid']
        if abs(ob_mid - precio_zona) > tolerancia:
            return {'encontrado': False}

        return {
            'encontrado': True,
            'tf':         'H1',
            'ob_high':    resultado['ob_high'],
            'ob_low':     resultado['ob_low'],
            'ob_mid':     resultado['ob_mid'],
            'ob_body':    resultado['ob_body'],
            'es_fuerte':  resultado['es_fuerte'],
        }

    except Exception as e:
        print(f"  [ob_v5] Error ob_en_zona {simbolo}: {e}")
        return {'encontrado': False}
