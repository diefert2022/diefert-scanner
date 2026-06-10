# ============================================================
#  DIEFERT SCANNER v6 — choch_m1_v6.py
#
#  MÓDULO INDEPENDIENTE — NO modifica ningún archivo existente.
#  Principio de adición: activa vigilancia M1 en paralelo
#  cuando el precio ya está dentro de una zona.
#
#  QUÉ HACE:
#  ─────────────────────────────────────────────────────────
#  El scanner v5 detecta CHoCH en M5 como trigger de entrada.
#
#  Este módulo agrega vigilancia M1 para cuando el precio
#  YA ESTÁ DENTRO de una zona válida. Razón:
#
#    En M5: cada vela = 5 minutos → el CHoCH puede darte
#    una entrada tarde, con poco RR restante.
#
#    En M1: cada vela = 1 minuto → detectas el CHoCH más
#    temprano, dentro de la zona, con mejor precio de entrada
#    y mayor RR disponible hacia el TP.
#
#  REGLA DE ACTIVACIÓN:
#    Solo vigilamos M1 si el precio está DENTRO de la zona
#    (tolerancia = TOL_ZONA_M1 pts).
#    Fuera de zona → este módulo no aplica.
#
#  DEFINICIÓN DE CHoCH M1:
#    Igual que en estructura.py pero en M1:
#    → Detectar swings M1 (ventana=2 — más sensible)
#    → Buscar rotura del último swing en dirección correcta
#    → La vela que rompe DEBE CERRAR más allá del swing
#      (no solo mecha — regla de cierre obligatoria)
#    → Rango mínimo de la vela de rotura > MIN_RANGO_CHOCH
#
#  USO:
#    from choch_m1_v6 import verificar_choch_m1
#    resultado = verificar_choch_m1(simbolo, precio_actual, es_bajista, zonas_validas)
#
#  RETORNA:
#    {
#      'detectado':    True/False,
#      'en_zona':      True/False,  ← precio está en alguna zona
#      'zona':         dict de la zona donde está,
#      'choch_nivel':  precio del swing roto,
#      'precio':       precio actual al momento del CHoCH,
#      'rango_vela':   tamaño de la vela de rotura,
#      'descripcion':  texto para Telegram/consola,
#    }
# ============================================================

from utils import obtener_df
from config import TF_M1, VELAS_M1
from estructura import detectar_swings

# Tolerancia para considerar que el precio "está en la zona"
TOL_ZONA_M1 = 50   # pts — mismo valor que usa main_v5.py para tol_zona

# Rango mínimo de la vela que confirma el CHoCH M1
# Más pequeño que M5 porque M1 tiene velas naturalmente menores
MIN_RANGO_CHOCH = 4   # pts — filtra microroturas falsas en M1

# Cuántas velas atrás puede estar el CHoCH y aún ser válido
MAX_VELAS_ATRÁS = 3   # últimas 3 velas M1 = últimos 3 minutos


def _precio_en_zona(precio_actual, zonas_validas):
    """
    Verifica si el precio actual está dentro de alguna zona válida.
    Retorna la zona si está dentro, None si no.
    """
    for zona in zonas_validas:
        precio_zona = zona['precio']
        if abs(precio_actual - precio_zona) <= TOL_ZONA_M1:
            return zona
    return None


def _detectar_choch_en_m1(df_m1, es_bajista):
    """
    Detecta CHoCH en M1.

    Para GainX (LONG):
      Busca el último Swing Low M1.
      Si una vela CIERRA por ENCIMA del último Swing High → CHoCH alcista.

    Para PainX (SHORT):
      Busca el último Swing High M1.
      Si una vela CIERRA por DEBAJO del último Swing Low → CHoCH bajista.

    IMPORTANTE: siempre esperar CIERRE de vela (close), no solo wick.

    Retorna dict con detectado, nivel, idx, rango_vela.
    """
    vacio = {'detectado': False, 'nivel': None, 'idx': -1, 'rango_vela': 0}

    if df_m1 is None or len(df_m1) < 10:
        return vacio

    swings_m1 = detectar_swings(df_m1, ventana=2)   # ventana pequeña para M1
    if not swings_m1:
        return vacio

    if es_bajista:
        # PainX SHORT: buscar CHoCH bajista
        # Necesitamos que el precio rompa el último Swing Low M1
        ultimo_sl = next((s for s in reversed(swings_m1) if s['tipo'] == 'SL'), None)
        if ultimo_sl is None:
            return vacio

        nivel = ultimo_sl['precio']

        # Buscar vela que cierra por debajo del SL
        for i in range(ultimo_sl['idx'] + 1, len(df_m1)):
            v          = df_m1.iloc[i]
            rango_vela = v['high'] - v['low']

            if rango_vela < MIN_RANGO_CHOCH:
                continue   # microrotura — ignorar

            if v['close'] < nivel:
                return {
                    'detectado':  True,
                    'nivel':      nivel,
                    'idx':        i,
                    'rango_vela': round(rango_vela, 2),
                }

    else:
        # GainX LONG: buscar CHoCH alcista
        # Necesitamos que el precio rompa el último Swing High M1
        ultimo_sh = next((s for s in reversed(swings_m1) if s['tipo'] == 'SH'), None)
        if ultimo_sh is None:
            return vacio

        nivel = ultimo_sh['precio']

        # Buscar vela que cierra por encima del SH
        for i in range(ultimo_sh['idx'] + 1, len(df_m1)):
            v          = df_m1.iloc[i]
            rango_vela = v['high'] - v['low']

            if rango_vela < MIN_RANGO_CHOCH:
                continue

            if v['close'] > nivel:
                return {
                    'detectado':  True,
                    'nivel':      nivel,
                    'idx':        i,
                    'rango_vela': round(rango_vela, 2),
                }

    return vacio


def verificar_choch_m1(simbolo, precio_actual, es_bajista, zonas_validas):
    """
    Función principal. Solo actúa si precio está en zona válida.

    Flujo:
    1. ¿Precio está dentro de alguna zona válida?
       → No: retorna en_zona=False, detectado=False
    2. ¿Hay CHoCH M1 reciente (últimas MAX_VELAS_ATRÁS velas)?
       → No: retorna en_zona=True, detectado=False
    3. Sí: retorna en_zona=True, detectado=True con detalles

    Parámetros:
      simbolo       → nombre del índice
      precio_actual → precio actual del mercado
      es_bajista    → True para PainX, False para GainX
      zonas_validas → lista de zonas de main_v5.py

    Retorna dict completo.
    """
    resultado_base = {
        'detectado':   False,
        'en_zona':     False,
        'zona':        None,
        'choch_nivel': None,
        'precio':      precio_actual,
        'rango_vela':  0,
        'descripcion': '',
    }

    try:
        # ── 1. Verificar si precio está en zona ───────────
        zona_activa = _precio_en_zona(precio_actual, zonas_validas)
        if zona_activa is None:
            return resultado_base   # no en zona → no vigilar M1

        resultado_base['en_zona'] = True
        resultado_base['zona']    = zona_activa

        # ── 2. Obtener datos M1 ───────────────────────────
        df_m1 = obtener_df(simbolo, TF_M1, VELAS_M1)
        if df_m1 is None or len(df_m1) < 10:
            return resultado_base

        # ── 3. Detectar CHoCH M1 ──────────────────────────
        choch = _detectar_choch_en_m1(df_m1, es_bajista)

        if not choch['detectado']:
            resultado_base['descripcion'] = (
                f"⏳ En zona {zona_activa['precio']:.0f} — "
                f"esperando CHoCH M1..."
            )
            return resultado_base

        # ── 4. Verificar que el CHoCH es reciente ─────────
        idx_choch  = choch['idx']
        idx_ultima = len(df_m1) - 1
        velas_diff = idx_ultima - idx_choch

        if velas_diff > MAX_VELAS_ATRÁS:
            resultado_base['descripcion'] = (
                f"⏳ En zona {zona_activa['precio']:.0f} — "
                f"CHoCH M1 detectado pero viejo ({velas_diff} velas atrás)"
            )
            return resultado_base

        # ── 5. CHoCH M1 válido y reciente ─────────────────
        dir_txt = 'bajista 📉' if es_bajista else 'alcista 📈'
        desc = (
            f"🎯 CHoCH M1 {dir_txt} | "
            f"Zona: {zona_activa['precio']:.0f} | "
            f"Nivel roto: {choch['nivel']:.0f} | "
            f"Vela: {choch['rango_vela']:.1f}pts | "
            f"Hace {velas_diff} velas M1"
        )

        return {
            'detectado':   True,
            'en_zona':     True,
            'zona':        zona_activa,
            'choch_nivel': choch['nivel'],
            'precio':      precio_actual,
            'rango_vela':  choch['rango_vela'],
            'descripcion': desc,
        }

    except Exception as e:
        print(f"  [choch_m1_v6] Error en {simbolo}: {e}")
        return resultado_base
