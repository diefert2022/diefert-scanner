# ============================================================
#  DIEFERT SCANNER v4.7 — resistencias.py
#
#  Módulo de detección de soporte/resistencia histórica.
#  Corre en ciclo lento (cada 15 min) para no atrasar el
#  ciclo principal de 3 segundos.
#
#  FUENTES DE ANÁLISIS (máximo historial por TF):
#  ─────────────────────────────────────────────────────────
#  H4  → 4138 velas  (~2 años) — niveles institucionales
#  H1  → 16541 velas (~689 días) — zonas operativas
#  D1  → 689 velas   (~689 días) — sesgo macro
#
#  TIPOS DE ZONA DETECTADA:
#  ─────────────────────────────────────────────────────────
#  SH  = Swing High (resistencia por precio máximo)
#  SL  = Swing Low  (soporte por precio mínimo)
#  FVG = Fair Value Gap (imán institucional)
#  OB  = Order Block (zona de rechazo institucional)
#
#  SCORE POR ZONA (1–10):
#  ─────────────────────────────────────────────────────────
#  +1 por cada toque/confirmación en la zona
#  +2 si hay FVG en esa zona
#  +2 si hay OB en esa zona
#  +1 si coincide en H4 y H1 simultáneamente (confluencia)
#  +1 si es nivel psicológico redondo (múltiplo de 500)
#
#  PARÁMETROS CALIBRADOS (datos reales PainX/GainX mayo 2026):
#  ─────────────────────────────────────────────────────────
#  TOL_AGRUPACION  = 50 pts  (rango M15 avg=50 → <50pts = misma zona)
#  DIST_MAX_ACTIVA = 1000 pts (~1.7x rango diario 592pts → cubre hoy+mañana)
#
#  ARQUITECTURA:
#  ─────────────────────────────────────────────────────────
#  _cache_niveles  → dict con niveles calculados por símbolo
#  _ultimo_calculo → timestamp del último cálculo
#  INTERVALO_SEG   → cada cuántos segundos recalcular (900 = 15 min)
#
#  USO DESDE main_v4.py:
#  ─────────────────────────────────────────────────────────
#  from resistencias import obtener_niveles, resumen_niveles, actualizar_si_necesario
#
#  En el ciclo lento (cada 15 min):
#    actualizar_si_necesario(simbolo)
#
#  En gestionar_alertas o poi_score:
#    niveles = obtener_niveles(simbolo)
#    # niveles es una lista de dicts con keys:
#    # precio, dist, score, fuerza, tipos, tf, direccion
# ============================================================

import time
import MetaTrader5 as mt5
from collections import defaultdict

# ── Config extendido v412 para thresholds calibrados ─────
from config_v413 import INDICES_CONFIG as _INDICES_config_v413


def _ob_threshold(simbolo, timeframe="H4"):
    """
    Threshold mínimo de body para OBs según el índice.
    Usa ob_h4_min / ob_h1_min de config_v413.
    Si no existe → None (usa avg_body * mult como antes).
    """
    cfg = _INDICES_config_v413.get(simbolo, {})
    if timeframe == "H4":
        return cfg.get("ob_h4_min", None)
    return cfg.get("ob_h1_min", None)

# ── Parámetros globales ───────────────────────────────────
INTERVALO_SEG   = 900    # recalcular cada 15 minutos
LOOKBACK_SH     = 5      # velas a cada lado para confirmar swing high/low
TOL_AGRUPACION  = 50     # pts — zonas dentro de este rango se fusionan
                         # (calibrado: rango M15 avg=50pts → <50pts = misma zona)
DIST_MAX_ACTIVA = 1000   # pts — zona "activa" si precio está a menos de esto
                         # (calibrado: ~1.7x rango diario PainX/GainX 400 ~592pts)
FVG_MIN_TAM     = 15     # pts — tamaño mínimo de FVG válido
OB_MULT_BODY    = 1.3    # multiplicador body promedio para OB válido

# ── Velas por timeframe (máximo historial) ────────────────
VELAS_D1  = 689
VELAS_H4  = 4138
VELAS_H1  = 16541

# ── Cache en memoria ─────────────────────────────────────
_cache_niveles  = {}   # {simbolo: [lista de niveles]}
_ultimo_calculo = {}   # {simbolo: timestamp}

# ── Niveles semilla GainX 600 ─────────────────────────────
# Calculados desde datos reales (9 TFs: Monthly→M1, mayo 2026)
# Fuentes: Swings Daily, FVGs Daily+H4, OBs Daily+H4
# Score = confluencia por zona (FVG+OB+Swing, máx 20pts)
# Se cargan al inicio — el ciclo de 15min los enriquece con MT5
#
# Zonas activas al 21/05/2026 (precio ~110,859):
#   Z1 RESIST  110,930–111,050  score 20  (FVG+OB+Swing Daily)
#   Z2 SUPPORT 110,660–110,800  score 20  (FVG cluster H4+Daily)
#   Z3 RESIST  110,440–110,550  score 20  (FVG+OB+Swing Daily)
#   Z4 RESIST  111,300–111,450  score 15  (FVG BEAR+OB+Swing)
#   Z5 SUPPORT 109,870–110,050  score 17  (FVG+OB cluster)
#   Z6 SUPPORT 109,600–109,750  score 14  (FVG+Swing Low+OBs H4)
#   Z7 SUPPORT 109,300–109,450  score 14  (OBs Daily+H4)
_SEMILLA_GAINX600 = [
    # ── ZONA 1 — Resistencia inmediata (score 20) ─────────
    {'precio': 110_990.0, 'dist': 0, 'score': 20, 'fuerza': 3,
     'fuerza_txt': '🔴🔴🔴 ALTA', 'tipos': ['FVG_ALC', 'OB_BAJ', 'SH'],
     'tfs': ['D1', 'H4'], 'n_toques': 3, 'activa': True,
     'direccion': '↑ RESISTENCIA'},

    # ── ZONA 2 — Soporte inmediato (score 20) ─────────────
    {'precio': 110_730.0, 'dist': 0, 'score': 20, 'fuerza': 3,
     'fuerza_txt': '🔴🔴🔴 ALTA', 'tipos': ['FVG_ALC', 'FVG_BAJ', 'SL'],
     'tfs': ['D1', 'H4'], 'n_toques': 3, 'activa': True,
     'direccion': '↓ SOPORTE'},

    # ── ZONA 3 — Resistencia/Soporte secundaria (score 20) ─
    {'precio': 110_495.0, 'dist': 0, 'score': 20, 'fuerza': 3,
     'fuerza_txt': '🔴🔴🔴 ALTA', 'tipos': ['FVG_ALC', 'OB_BAJ', 'SH'],
     'tfs': ['D1', 'H4'], 'n_toques': 3, 'activa': True,
     'direccion': '↑ RESISTENCIA'},

    # ── ZONA 4 — Resistencia alta (score 15) ──────────────
    {'precio': 111_375.0, 'dist': 0, 'score': 15, 'fuerza': 3,
     'fuerza_txt': '🔴🔴🔴 ALTA', 'tipos': ['FVG_BAJ', 'OB_ALC', 'SH'],
     'tfs': ['D1', 'H4'], 'n_toques': 3, 'activa': True,
     'direccion': '↑ RESISTENCIA'},

    # ── ZONA 5 — Soporte medio (score 17) ─────────────────
    {'precio': 109_960.0, 'dist': 0, 'score': 17, 'fuerza': 3,
     'fuerza_txt': '🔴🔴🔴 ALTA', 'tipos': ['FVG_BAJ', 'OB_ALC'],
     'tfs': ['D1', 'H4'], 'n_toques': 2, 'activa': True,
     'direccion': '↓ SOPORTE'},

    # ── ZONA 6 — Zona demanda 1 (score 14) ────────────────
    {'precio': 109_675.0, 'dist': 0, 'score': 14, 'fuerza': 2,
     'fuerza_txt': '🟡🟡   MEDIA', 'tipos': ['FVG_BAJ', 'SL', 'OB_ALC'],
     'tfs': ['D1', 'H4'], 'n_toques': 2, 'activa': True,
     'direccion': '↓ SOPORTE'},

    # ── ZONA 7 — Zona demanda 2 (score 14) ────────────────
    {'precio': 109_375.0, 'dist': 0, 'score': 14, 'fuerza': 2,
     'fuerza_txt': '🟡🟡   MEDIA', 'tipos': ['OB_ALC', 'OB_BAJ'],
     'tfs': ['D1', 'H4'], 'n_toques': 2, 'activa': True,
     'direccion': '↓ SOPORTE'},

    # ── MACRO SOPORTES (Swing Lows Daily) ─────────────────
    {'precio': 108_984.0, 'dist': 0, 'score': 9, 'fuerza': 2,
     'fuerza_txt': '🟡🟡   MEDIA', 'tipos': ['SL', 'OB_ALC'],
     'tfs': ['D1'], 'n_toques': 1, 'activa': True,
     'direccion': '↓ SOPORTE'},

    {'precio': 107_609.0, 'dist': 0, 'score': 3, 'fuerza': 1,
     'fuerza_txt': '⚪     BAJA', 'tipos': ['SL'],
     'tfs': ['D1'], 'n_toques': 1, 'activa': True,
     'direccion': '↓ SOPORTE'},

    {'precio': 107_141.0, 'dist': 0, 'score': 3, 'fuerza': 1,
     'fuerza_txt': '⚪     BAJA', 'tipos': ['SL'],
     'tfs': ['D1'], 'n_toques': 1, 'activa': True,
     'direccion': '↓ SOPORTE'},

    # ── MACRO RESISTENCIAS (Swing Highs Daily) ────────────
    {'precio': 111_893.0, 'dist': 0, 'score': 3, 'fuerza': 1,
     'fuerza_txt': '⚪     BAJA', 'tipos': ['SH'],
     'tfs': ['D1'], 'n_toques': 1, 'activa': True,
     'direccion': '↑ RESISTENCIA'},

    {'precio': 112_496.0, 'dist': 0, 'score': 3, 'fuerza': 1,
     'fuerza_txt': '⚪     BAJA', 'tipos': ['SH'],
     'tfs': ['D1'], 'n_toques': 1, 'activa': True,
     'direccion': '↑ RESISTENCIA'},
]


def _cargar_semillas_gainx600(precio_actual):
    """
    Actualiza los campos 'dist' y 'activa' de las semillas
    según el precio actual y las retorna listas para usar
    como punto de partida del cache.
    """
    semillas = []
    for s in _SEMILLA_GAINX600:
        n = dict(s)
        n['dist']   = round(abs(n['precio'] - precio_actual), 0)
        n['activa'] = n['dist'] <= DIST_MAX_ACTIVA
        semillas.append(n)
    return sorted(semillas, key=lambda x: -x['score'])



# ============================================================
#  HELPER — obtener DataFrame desde MT5
# ============================================================

def _nombre_mt5(simbolo):
    """Traduce nombre interno al nombre real del broker activo."""
    try:
        from broker import nombre_real
        return nombre_real(simbolo)
    except Exception:
        return simbolo

def _get_df(simbolo, timeframe, n_velas):
    """Descarga velas desde MT5 y retorna DataFrame limpio."""
    try:
        rates = mt5.copy_rates_from_pos(_nombre_mt5(simbolo), timeframe, 0, n_velas)
        if rates is None or len(rates) == 0:
            return None
        import pandas as pd
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.rename(columns={'time':'date','tick_volume':'volume'})
        df = df[['date','open','high','low','close','volume']].reset_index(drop=True)
        return df
    except Exception as e:
        print(f"  [Resistencias] Error descargando {simbolo}: {e}")
        return None


# ============================================================
#  DETECCIÓN DE SWING HIGHS / LOWS
# ============================================================

def _detectar_swings(df, lookback=LOOKBACK_SH):
    """
    Retorna lista de swings con precio e índice.
    Un swing high es el máximo de una ventana de lookback velas a cada lado.
    Un swing low  es el mínimo de la misma ventana.
    """
    swings = []
    for i in range(lookback, len(df) - lookback):
        ventana = df.iloc[i - lookback: i + lookback + 1]
        if df.iloc[i]['high'] == ventana['high'].max():
            swings.append({'tipo': 'SH', 'precio': df.iloc[i]['high'], 'idx': i})
        if df.iloc[i]['low'] == ventana['low'].min():
            swings.append({'tipo': 'SL', 'precio': df.iloc[i]['low'],  'idx': i})
    return swings


# ============================================================
#  DETECCIÓN DE FVGs
# ============================================================

def _detectar_fvgs(df, es_bajista, min_tam=FVG_MIN_TAM):
    """
    FVG bajista: high[i+1] < low[i-1] — hueco donde precio cayó.
    FVG alcista: low[i+1]  > high[i-1] — hueco donde precio subió.
    Solo FVGs no mitigados.
    """
    fvgs = []
    for i in range(1, len(df) - 1):
        if es_bajista:
            gap = df.iloc[i - 1]['low'] - df.iloc[i + 1]['high']
            if gap >= min_tam:
                zh = df.iloc[i - 1]['low']
                zl = df.iloc[i + 1]['high']
                mid = (zh + zl) / 2
                # Verificar no mitigado
                mitigado = any(
                    df.iloc[k]['low'] <= zh and df.iloc[k]['high'] >= zl
                    for k in range(i + 2, min(i + 50, len(df)))
                )
                if not mitigado:
                    fvgs.append({
                        'tipo':  'FVG_BAJ',
                        'precio': round(mid, 2),
                        'tam':   round(gap, 2),
                        'idx':   i
                    })
        else:
            gap = df.iloc[i + 1]['low'] - df.iloc[i - 1]['high']
            if gap >= min_tam:
                zh = df.iloc[i + 1]['low']
                zl = df.iloc[i - 1]['high']
                mid = (zh + zl) / 2
                mitigado = any(
                    df.iloc[k]['low'] <= zh and df.iloc[k]['high'] >= zl
                    for k in range(i + 2, min(i + 50, len(df)))
                )
                if not mitigado:
                    fvgs.append({
                        'tipo':  'FVG_ALC',
                        'precio': round(mid, 2),
                        'tam':   round(gap, 2),
                        'idx':   i
                    })
    return fvgs


# ============================================================
#  DETECCIÓN DE ORDER BLOCKS
# ============================================================

def _detectar_obs(df, es_bajista, mult=OB_MULT_BODY, simbolo=None, timeframe="H4"):
    """
    OB bajista: última vela alcista antes de un impulso bajista fuerte.
    OB alcista: última vela bajista antes de un impulso alcista fuerte.

    v4.8: acepta simbolo + timeframe para usar ob_h4_min/ob_h1_min
    calibrados del config_v413. Si no existe → avg_body * mult (anterior).
    """
    obs = []
    avg_body = abs(df['close'] - df['open']).mean()
    threshold_config = _ob_threshold(simbolo, timeframe) if simbolo else None

    for i in range(1, len(df) - 2):
        c  = df.iloc[i]
        cn = df.iloc[i + 1]
        umbral = threshold_config if threshold_config else avg_body * mult

        if es_bajista:
            # Vela actual alcista, siguiente bajista con body grande
            if c['close'] > c['open'] and cn['close'] < cn['open']:
                body_next = cn['open'] - cn['close']
                if body_next > umbral:
                    # No mitigado: precio no volvió a subir al high del OB
                    mitigado = any(
                        df.iloc[k]['high'] >= c['high']
                        for k in range(i + 2, min(i + 30, len(df)))
                    )
                    if not mitigado:
                        obs.append({
                            'tipo':   'OB_BAJ',
                            'precio':  round(c['high'], 2),
                            'ob_high': round(c['high'], 2),
                            'ob_low':  round(c['low'],  2),
                            'idx':     i
                        })
        else:
            # Vela actual bajista, siguiente alcista con body grande
            if c['close'] < c['open'] and cn['close'] > cn['open']:
                body_next = cn['close'] - cn['open']
                if body_next > umbral:
                    mitigado = any(
                        df.iloc[k]['low'] <= c['low']
                        for k in range(i + 2, min(i + 30, len(df)))
                    )
                    if not mitigado:
                        obs.append({
                            'tipo':   'OB_ALC',
                            'precio':  round(c['low'], 2),
                            'ob_high': round(c['high'], 2),
                            'ob_low':  round(c['low'],  2),
                            'idx':     i
                        })
    return obs


# ============================================================
#  NIVELES PSICOLÓGICOS
# ============================================================

def _niveles_psicologicos(precio_actual, rango=3000, paso=500):
    """
    Genera niveles redondos cercanos al precio actual.
    Ej: 106,000 / 106,500 / 107,000 / 107,500
    """
    base = round(precio_actual / paso) * paso
    niveles = []
    for mult in range(-int(rango/paso), int(rango/paso) + 1):
        nivel = base + mult * paso
        if abs(nivel - precio_actual) <= rango:
            niveles.append({
                'tipo':   'PSICO',
                'precio':  float(nivel),
                'idx':     -1
            })
    return niveles


# ============================================================
#  AGRUPAR Y PUNTUAR NIVELES
# ============================================================

def _agrupar_y_puntuar(todos_los_niveles, precio_actual,
                        tol=TOL_AGRUPACION):
    """
    Fusiona niveles cercanos (dentro de tol pts) y les asigna
    un score según la cantidad y calidad de confirmaciones.

    Score:
      +1 por cada swing en la zona
      +2 si hay FVG
      +2 si hay OB
      +1 si hay nivel psicológico
      +1 bonus por confluencia HTF+LTF (si aparece en H4 y H1)
    """
    if not todos_los_niveles:
        return []

    # Ordenar por precio para agrupar secuencialmente
    ordenados = sorted(todos_los_niveles, key=lambda x: x['precio'])

    grupos = []
    grupo_actual = [ordenados[0]]

    for item in ordenados[1:]:
        if item['precio'] - grupo_actual[-1]['precio'] <= tol:
            grupo_actual.append(item)
        else:
            grupos.append(grupo_actual)
            grupo_actual = [item]
    grupos.append(grupo_actual)

    resultado = []
    for grupo in grupos:
        precio_zona = sum(i['precio'] for i in grupo) / len(grupo)
        tipos       = list(set(i['tipo'] for i in grupo))
        tfs         = list(set(i.get('tf', 'H4') for i in grupo))

        # Calcular score
        score = 0
        n_swings = sum(1 for i in grupo if i['tipo'] in ('SH', 'SL'))
        score += n_swings                                          # +1 por swing
        if any(t in ('FVG_BAJ', 'FVG_ALC') for t in tipos): score += 2  # +2 FVG
        if any(t in ('OB_BAJ',  'OB_ALC')  for t in tipos): score += 2  # +2 OB
        if 'PSICO' in tipos:                                  score += 1  # +1 psico
        if len(tfs) >= 2:                                     score += 1  # +1 confluencia

        # Fuerza 1-3 según score
        if score >= 8:
            fuerza = 3
            fuerza_txt = "🔴🔴🔴 ALTA"
        elif score >= 5:
            fuerza = 2
            fuerza_txt = "🟡🟡   MEDIA"
        else:
            fuerza = 1
            fuerza_txt = "⚪     BAJA"

        dist = abs(precio_actual - precio_zona)
        direccion = '↑ RESISTENCIA' if precio_zona > precio_actual else '↓ SOPORTE'

        resultado.append({
            'precio':      round(precio_zona, 0),
            'dist':        round(dist, 0),
            'score':       score,
            'fuerza':      fuerza,
            'fuerza_txt':  fuerza_txt,
            'tipos':       tipos,
            'tfs':         tfs,
            'n_toques':    n_swings,
            'direccion':   direccion,
            'activa':      dist <= DIST_MAX_ACTIVA,
        })

    # Ordenar por score descendente
    return sorted(resultado, key=lambda x: -x['score'])


# ============================================================
#  FUNCIÓN PRINCIPAL DE CÁLCULO
# ============================================================

def _calcular_niveles(simbolo, es_bajista):
    """
    Descarga el máximo historial disponible por TF,
    detecta todos los tipos de zonas y retorna lista unificada
    punteada y ordenada por score.
    """
    print(f"  🔍 [Resistencias] Calculando niveles históricos: {simbolo}...")
    t0 = time.time()

    todos = []

    # ── Daily ─────────────────────────────────────────────
    df_d1 = _get_df(simbolo, mt5.TIMEFRAME_D1, VELAS_D1)
    if df_d1 is not None and len(df_d1) > 10:
        precio_actual = df_d1['close'].iloc[-1]
        for s in _detectar_swings(df_d1, lookback=3):
            s['tf'] = 'D1'; todos.append(s)
        for f in _detectar_fvgs(df_d1, es_bajista, min_tam=50):
            f['tf'] = 'D1'; todos.append(f)
        for o in _detectar_obs(df_d1, es_bajista, mult=1.5, simbolo=simbolo, timeframe="D1"):
            o['tf'] = 'D1'; todos.append(o)
    else:
        precio_actual = None

    # ── H4 (máximo historial ~2 años) ─────────────────────
    df_h4 = _get_df(simbolo, mt5.TIMEFRAME_H4, VELAS_H4)
    if df_h4 is not None and len(df_h4) > 10:
        if precio_actual is None:
            precio_actual = df_h4['close'].iloc[-1]
        for s in _detectar_swings(df_h4, lookback=5):
            s['tf'] = 'H4'; todos.append(s)
        for f in _detectar_fvgs(df_h4, es_bajista, min_tam=20):
            f['tf'] = 'H4'; todos.append(f)
        for o in _detectar_obs(df_h4, es_bajista, mult=1.3, simbolo=simbolo, timeframe="H4"):
            o['tf'] = 'H4'; todos.append(o)

    # ── H1 (máximo historial ~689 días) ───────────────────
    df_h1 = _get_df(simbolo, mt5.TIMEFRAME_H1, VELAS_H1)
    if df_h1 is not None and len(df_h1) > 10:
        if precio_actual is None:
            precio_actual = df_h1['close'].iloc[-1]
        for s in _detectar_swings(df_h1, lookback=5):
            s['tf'] = 'H1'; todos.append(s)
        for f in _detectar_fvgs(df_h1, es_bajista, min_tam=15):
            f['tf'] = 'H1'; todos.append(f)
        for o in _detectar_obs(df_h1, es_bajista, mult=1.3, simbolo=simbolo, timeframe="H1"):
            o['tf'] = 'H1'; todos.append(o)

    if precio_actual is None:
        print(f"  ❌ [Resistencias] Sin datos para {simbolo}")
        return []

    # Niveles psicológicos
    for p in _niveles_psicologicos(precio_actual):
        p['tf'] = 'PSICO'; todos.append(p)

    # Agrupar, puntuar y filtrar
    niveles = _agrupar_y_puntuar(todos, precio_actual)

    # ── Para GainX 600: fusionar con niveles semilla ──────
    # Las semillas tienen score de confluencia de datos reales
    # (9 TFs analizados). Se combinan con lo que detecta MT5.
    if simbolo == "GainX 600":
        semillas = _cargar_semillas_gainx600(precio_actual)
        niveles_precios = {round(n['precio'] / TOL_AGRUPACION): n for n in niveles}
        for sem in semillas:
            clave = round(sem['precio'] / TOL_AGRUPACION)
            if clave in niveles_precios:
                # Zona ya detectada por MT5 — sumar score de semilla
                existente = niveles_precios[clave]
                existente['score'] = max(existente['score'], sem['score'])
                for t in sem['tipos']:
                    if t not in existente['tipos']:
                        existente['tipos'].append(t)
                for tf in sem['tfs']:
                    if tf not in existente['tfs']:
                        existente['tfs'].append(tf)
                # Actualizar fuerza_txt
                if existente['score'] >= 8:
                    existente['fuerza'] = 3
                    existente['fuerza_txt'] = '🔴🔴🔴 ALTA'
                elif existente['score'] >= 5:
                    existente['fuerza'] = 2
                    existente['fuerza_txt'] = '🟡🟡   MEDIA'
            else:
                # Zona nueva — agregar directamente
                niveles.append(sem)
        # Re-ordenar por score
        niveles = sorted(niveles, key=lambda x: -x['score'])

    elapsed = time.time() - t0
    print(
        f"  ✅ [Resistencias] {simbolo}: {len(niveles)} zonas detectadas "
        f"({len([n for n in niveles if n['activa']])} activas) — {elapsed:.1f}s"
    )
    return niveles


# ============================================================
#  API PÚBLICA
# ============================================================

def actualizar_si_necesario(simbolo, es_bajista, forzar=False):
    """
    Recalcula los niveles del símbolo si han pasado más de
    INTERVALO_SEG segundos desde el último cálculo.
    Llamar desde el ciclo lento de main_v4.py.

    Para GainX 600: pre-carga semillas institucionales en el
    primer ciclo para que el POI score funcione de inmediato
    sin esperar el primer cálculo completo de 15 min.
    """
    ahora = time.time()
    ultimo = _ultimo_calculo.get(simbolo, 0)

    # Pre-cargar semillas GainX 600 si es la primera vez
    if simbolo == "GainX 600" and simbolo not in _cache_niveles:
        try:
            import MetaTrader5 as mt5_inner
            rates = mt5_inner.copy_rates_from_pos(_nombre_mt5(simbolo), mt5_inner.TIMEFRAME_M1, 0, 5)
            if rates is not None and len(rates) > 0:
                precio_actual = rates[-1][4]  # close
                semillas = _cargar_semillas_gainx600(precio_actual)
                _cache_niveles[simbolo] = semillas
                print(f"  📌 [Resistencias] GainX 600: {len(semillas)} niveles semilla cargados")
        except Exception:
            pass

    if forzar or (ahora - ultimo) >= INTERVALO_SEG:
        try:
            niveles = _calcular_niveles(simbolo, es_bajista)
            _cache_niveles[simbolo]  = niveles
            _ultimo_calculo[simbolo] = ahora
        except Exception as e:
            print(f"  ❌ [Resistencias] Error en {simbolo}: {e}")


def obtener_niveles(simbolo, solo_activas=False, min_fuerza=1):
    """
    Retorna la lista de niveles calculados para el símbolo.
    Si aún no se calcularon, retorna lista vacía.

    Parámetros:
      solo_activas → solo zonas dentro de DIST_MAX_ACTIVA pts
      min_fuerza   → 1=todas, 2=media+alta, 3=solo alta
    """
    niveles = _cache_niveles.get(simbolo, [])
    if solo_activas:
        niveles = [n for n in niveles if n['activa']]
    if min_fuerza > 1:
        niveles = [n for n in niveles if n['fuerza'] >= min_fuerza]
    return niveles


def nivel_cercano(simbolo, precio_referencia, tolerancia=100):
    """
    Retorna el nivel más cercano al precio_referencia dentro
    de tolerancia pts, o None si no hay ninguno.
    Útil para que poi_score verifique si una zona M15 coincide
    con un nivel histórico importante.
    """
    niveles = _cache_niveles.get(simbolo, [])
    for n in sorted(niveles, key=lambda x: x['dist']):
        if abs(n['precio'] - precio_referencia) <= tolerancia:
            return n
    return None


def resumen_niveles(simbolo, max_mostrar=8):
    """
    Retorna string formateado para mostrar en consola.
    Solo muestra las zonas activas de mayor score.
    """
    niveles = obtener_niveles(simbolo, solo_activas=True, min_fuerza=1)
    if not niveles:
        ultimo = _ultimo_calculo.get(simbolo, 0)
        if ultimo == 0:
            return f"  {simbolo}: sin calcular aún"
        return f"  {simbolo}: sin zonas activas en rango ±{DIST_MAX_ACTIVA}pts"

    lineas = [f"\n  {'─'*60}"]
    lineas.append(f"  📊 NIVELES HISTÓRICOS — {simbolo}")
    lineas.append(f"  {'─'*60}")
    lineas.append(
        f"  {'Precio':<10} {'Dirección':<16} {'Dist':>6} {'Toques':>7} "
        f"{'Score':>6} {'Fuerza'}"
    )
    lineas.append(f"  {'─'*60}")

    for n in niveles[:max_mostrar]:
        lineas.append(
            f"  {n['precio']:<10.0f} {n['direccion']:<16} "
            f"{n['dist']:>5.0f}p  {n['n_toques']:>5}x  "
            f"{n['score']:>5}  {n['fuerza_txt']}"
        )

    lineas.append(f"  {'─'*60}")
    return "\n".join(lineas)


def enviar_niveles_telegram(simbolo, enviar_fn, max_niveles=6):
    """
    Envía resumen de niveles importantes por Telegram.
    Llamar manualmente o tras actualización.

    enviar_fn = función enviar_telegram de utils.py
    """
    niveles = obtener_niveles(simbolo, solo_activas=True, min_fuerza=2)
    if not niveles:
        return

    resistencias = [n for n in niveles if '↑' in n['direccion']][:3]
    soportes     = [n for n in niveles if '↓' in n['direccion']][:3]

    lineas = [
        f"📊 <b>Niveles históricos — {simbolo}</b>",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if resistencias:
        lineas.append("🔴 <b>RESISTENCIAS</b>")
        for n in resistencias:
            tipos_txt = "+".join(n['tipos'])
            lineas.append(
                f"  {n['precio']:.0f} | {n['dist']:.0f}pts | "
                f"{n['n_toques']}x | {tipos_txt} | score={n['score']}"
            )

    if soportes:
        lineas.append("🟢 <b>SOPORTES</b>")
        for n in soportes:
            tipos_txt = "+".join(n['tipos'])
            lineas.append(
                f"  {n['precio']:.0f} | {n['dist']:.0f}pts | "
                f"{n['n_toques']}x | {tipos_txt} | score={n['score']}"
            )

    lineas.append("━━━━━━━━━━━━━━━━━━")
    enviar_fn("\n".join(lineas))
