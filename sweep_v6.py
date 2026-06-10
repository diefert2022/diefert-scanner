# ============================================================
#  DIEFERT SCANNER v6 — sweep_v6.py
#
#  MÓDULO INDEPENDIENTE — NO modifica ningún archivo existente.
#  Principio de adición: solo suma información, nunca bloquea.
#
#  QUÉ HACE:
#  ─────────────────────────────────────────────────────────
#  Antes de que el scanner alerte una zona, verifica que el
#  precio ya hizo un SWEEP del nivel de liquidez previo.
#
#  DEFINICIÓN DE SWEEP (regla estricta SMC):
#    - El wick de la vela ROMPE el nivel (high/low anterior)
#    - El CUERPO de la vela CIERRA ADENTRO del rango previo
#    - Si el cuerpo cierra afuera → es una rotura real, no sweep
#
#  ¿POR QUÉ IMPORTA?
#  Los algoritmos necesitan tomar liquidez antes de revertir.
#  Si el precio llega a una zona sin haber hecho sweep previo,
#  la probabilidad de rebote baja considerablemente.
#  Un sweep confirmado = "ya cazaron los stops, ahora invierten."
#
#  NIVELES QUE BUSCA COMO OBJETIVO DEL SWEEP:
#    - Máximo/mínimo de las últimas N velas (swing reciente)
#    - Equal Highs / Equal Lows (dos toques al mismo nivel)
#    - Mínimo/máximo del día anterior (PDH/PDL)
#
#  USO:
#    from sweep_v6 import verificar_sweep
#    resultado = verificar_sweep(simbolo, es_bajista)
#
#  RETORNA:
#    {
#      'hubo_sweep':     True/False,
#      'nivel_barrido':  precio del nivel que se barrió,
#      'tipo_nivel':     'SWING' / 'EQH/EQL' / 'PDH/PDL',
#      'velas_atras':    cuántas velas atrás ocurrió el sweep,
#      'descripcion':    texto para consola/Telegram,
#    }
#
#  PARÁMETRO CLAVE:
#    VENTANA_SWEEP = cuántas velas M5 hacia atrás buscar el sweep.
#    Si el sweep es muy viejo, ya no es relevante.
# ============================================================

from utils import obtener_df
from config import TF_M5, VELAS_M5

# Cuántas velas M5 hacia atrás buscar el sweep (= ~1.5 horas)
VENTANA_SWEEP = 18

# Tolerancia para considerar dos niveles "iguales" (EQH/EQL)
TOL_EQUAL = 5   # pts — dos niveles a menos de 5pts = equal


def _detectar_equal_levels(df, es_bajista, ventana=30):
    """
    Detecta Equal Highs (para PainX) o Equal Lows (para GainX).
    Dos máx/mín al mismo nivel = trampa de liquidez clásica.

    Retorna lista de niveles equal detectados.
    """
    niveles = []
    n = len(df)
    if n < ventana:
        return niveles

    recientes = df.tail(ventana)

    if es_bajista:
        # Para SHORT: buscamos Equal Highs (liquidez arriba)
        maximos = recientes['high'].values
        for i in range(len(maximos) - 1):
            for j in range(i + 2, len(maximos)):
                if abs(maximos[i] - maximos[j]) <= TOL_EQUAL:
                    niveles.append(round((maximos[i] + maximos[j]) / 2, 2))
    else:
        # Para LONG: buscamos Equal Lows (liquidez abajo)
        minimos = recientes['low'].values
        for i in range(len(minimos) - 1):
            for j in range(i + 2, len(minimos)):
                if abs(minimos[i] - minimos[j]) <= TOL_EQUAL:
                    niveles.append(round((minimos[i] + minimos[j]) / 2, 2))

    return list(set(niveles))  # eliminar duplicados


def _detectar_pdh_pdl(df, es_bajista):
    """
    Previous Day High (PDH) para PainX — nivel de liquidez arriba.
    Previous Day Low  (PDL) para GainX — nivel de liquidez abajo.

    Usa las últimas 480 velas M5 = 40 horas aprox.
    Identifica el high/low del día anterior (velas del día D-1).
    """
    if df is None or len(df) < 200:
        return None

    # Agrupar por fecha
    df_copy = df.copy()
    df_copy['fecha'] = df_copy['time'].dt.date
    fechas = sorted(df_copy['fecha'].unique())

    if len(fechas) < 2:
        return None

    # Tomar el día anterior al último
    dia_anterior = fechas[-2]
    velas_dia = df_copy[df_copy['fecha'] == dia_anterior]

    if len(velas_dia) == 0:
        return None

    if es_bajista:
        return round(velas_dia['high'].max(), 2)   # PDH
    else:
        return round(velas_dia['low'].min(), 2)    # PDL


def verificar_sweep(simbolo, es_bajista):
    """
    Función principal. Verifica si hubo un sweep de liquidez
    en las últimas VENTANA_SWEEP velas M5.

    Para PainX (SHORT): busca sweep de máximos anteriores
      → el precio subió rompiendo un high con wick,
        pero cerró por debajo → cazaron los stops arriba

    Para GainX (LONG): busca sweep de mínimos anteriores
      → el precio bajó rompiendo un low con wick,
        pero cerró por encima → cazaron los stops abajo

    Retorna dict:
      hubo_sweep:    True/False
      nivel_barrido: precio del nivel barrido
      tipo_nivel:    'SWING' / 'EQH/EQL' / 'PDH/PDL'
      velas_atras:   índice desde el final (0 = última vela)
      descripcion:   texto para Telegram/consola
    """
    resultado_vacio = {
        'hubo_sweep':    False,
        'nivel_barrido': None,
        'tipo_nivel':    None,
        'velas_atras':   None,
        'descripcion':   'Sin sweep detectado',
    }

    try:
        df = obtener_df(simbolo, TF_M5, VELAS_M5)
        if df is None or len(df) < 30:
            return resultado_vacio

        # ── Construir lista de niveles candidatos ─────────
        niveles_candidatos = []   # [(precio, tipo_nivel)]

        # 1. Swing reciente (máx/mín de las últimas 40 velas)
        ventana_swing = 40
        recientes = df.tail(ventana_swing)
        if es_bajista:
            swing_nivel = round(recientes['high'].max(), 2)
        else:
            swing_nivel = round(recientes['low'].min(), 2)
        niveles_candidatos.append((swing_nivel, 'SWING'))

        # 2. Equal Highs / Equal Lows
        equals = _detectar_equal_levels(df, es_bajista)
        for eq in equals:
            niveles_candidatos.append((eq, 'EQH/EQL'))

        # 3. PDH / PDL
        pdh_pdl = _detectar_pdh_pdl(df, es_bajista)
        if pdh_pdl is not None:
            niveles_candidatos.append((pdh_pdl, 'PDH/PDL'))

        if not niveles_candidatos:
            return resultado_vacio

        # ── Buscar sweep en las últimas VENTANA_SWEEP velas ──
        # Revisamos desde la más reciente hacia atrás
        n = len(df)
        inicio_busqueda = max(0, n - VENTANA_SWEEP)

        for i in range(n - 1, inicio_busqueda - 1, -1):
            vela = df.iloc[i]
            cuerpo_open  = vela['open']
            cuerpo_close = vela['close']
            wick_high    = vela['high']
            wick_low     = vela['low']

            velas_atras = (n - 1) - i

            for nivel, tipo in niveles_candidatos:
                if es_bajista:
                    # SWEEP BAJISTA:
                    # Wick sube por encima del nivel (high > nivel)
                    # Cuerpo cierra por debajo del nivel (close < nivel)
                    wick_rompe   = wick_high > nivel
                    cuerpo_adentro = cuerpo_close < nivel

                    if wick_rompe and cuerpo_adentro:
                        desc = (
                            f"🧹 Sweep {tipo} detectado | "
                            f"Nivel: {nivel:.0f} | "
                            f"Wick hasta {wick_high:.0f}, cerró en {cuerpo_close:.0f} | "
                            f"Hace {velas_atras} velas M5"
                        )
                        return {
                            'hubo_sweep':    True,
                            'nivel_barrido': nivel,
                            'tipo_nivel':    tipo,
                            'velas_atras':   velas_atras,
                            'descripcion':   desc,
                        }
                else:
                    # SWEEP ALCISTA:
                    # Wick baja por debajo del nivel (low < nivel)
                    # Cuerpo cierra por encima del nivel (close > nivel)
                    wick_rompe     = wick_low < nivel
                    cuerpo_adentro = cuerpo_close > nivel

                    if wick_rompe and cuerpo_adentro:
                        desc = (
                            f"🧹 Sweep {tipo} detectado | "
                            f"Nivel: {nivel:.0f} | "
                            f"Wick hasta {wick_low:.0f}, cerró en {cuerpo_close:.0f} | "
                            f"Hace {velas_atras} velas M5"
                        )
                        return {
                            'hubo_sweep':    True,
                            'nivel_barrido': nivel,
                            'tipo_nivel':    tipo,
                            'velas_atras':   velas_atras,
                            'descripcion':   desc,
                        }

        return resultado_vacio

    except Exception as e:
        print(f"  [sweep_v6] Error en {simbolo}: {e}")
        return resultado_vacio
