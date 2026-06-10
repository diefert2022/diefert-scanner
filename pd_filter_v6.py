# ============================================================
#  DIEFERT SCANNER v6 — pd_filter_v6.py
#
#  MÓDULO INDEPENDIENTE — NO modifica ningún archivo existente.
#  Principio de adición: solo suma información, nunca bloquea.
#
#  QUÉ HACE:
#  ─────────────────────────────────────────────────────────
#  Calcula el rango reciente del precio y determina si el
#  precio actual está en zona PREMIUM o DISCOUNT.
#
#  CONCEPTO SMC:
#    Rango = entre el último Swing High y el último Swing Low.
#    Equilibrium (EQ) = 50% del rango = línea divisoria.
#
#    PREMIUM  = precio > 50% del rango → zona "cara"
#               → aquí los institucionales VENDEN
#               → válido solo señales SHORT (PainX)
#
#    DISCOUNT = precio < 50% del rango → zona "barata"
#               → aquí los institucionales COMPRAN
#               → válido solo señales LONG (GainX)
#
#  LÓGICA DE FILTRO:
#    GainX (LONG):  señal válida solo si precio en DISCOUNT
#    PainX (SHORT): señal válida solo si precio en PREMIUM
#
#    Si el precio está del lado "equivocado", el módulo
#    retorna valid=False — la señal pierde contexto institucional.
#
#  USO:
#    from pd_filter_v6 import verificar_premium_discount
#    resultado = verificar_premium_discount(simbolo, precio_actual, es_bajista)
#
#  RETORNA:
#    {
#      'valid':         True/False,  ← señal alineada con PD
#      'zona':          'PREMIUM' / 'DISCOUNT' / 'EQUILIBRIUM',
#      'equilibrium':   precio del 50%,
#      'swing_high':    precio del SH del rango,
#      'swing_low':     precio del SL del rango,
#      'pct_en_rango':  porcentaje de posición en el rango (0-100),
#      'descripcion':   texto para Telegram/consola,
#    }
# ============================================================

from utils import obtener_df
from estructura import detectar_swings
from config import TF_H1, VELAS_H1, TF_H4, VELAS_H4

# ?ndices con movimientos grandes ? usar H4 para rango P/D
INDICES_H4 = {"PainX 1200", "GainX 1200", "PainX 999", "GainX 999"}

# Velas extra para ?ndices en m?ximos hist?ricos
VELAS_H4_GRANDE = 200  # cubre ~33 d?as

# Buffer: si el precio está a este % del equilibrium, se considera
# zona neutra (EQUILIBRIUM) — ni premium ni discount.
BUFFER_EQ_PCT = 5   # 5% del rango = zona neutra alrededor del 50%


def verificar_premium_discount(simbolo, precio_actual, es_bajista):
    """
    Determina si el precio actual está en zona Premium o Discount.

    Usa H1 como timeframe de referencia para calcular el rango.
    Swings detectados con ventana=5 (estándar H1).

    Parámetros:
      simbolo       → nombre del índice
      precio_actual → precio actual del mercado
      es_bajista    → True para PainX, False para GainX

    Retorna dict con valid, zona, equilibrium, etc.
    """
    resultado_neutro = {
        'valid':        True,   # sin datos = no bloquear
        'zona':         'DESCONOCIDO',
        'equilibrium':  None,
        'swing_high':   None,
        'swing_low':    None,
        'pct_en_rango': None,
        'descripcion':  'Sin datos P/D',
    }

    try:
        if simbolo in INDICES_H4:
            tf    = TF_H4
            velas = VELAS_H4_GRANDE
        else:
            tf    = TF_H1
            velas = VELAS_H1
        df = obtener_df(simbolo, tf, velas)
        if df is None or len(df) < 20:
            return resultado_neutro

        # ── Detectar swings H1 ────────────────────────────
        swings = detectar_swings(df, ventana=5)
        if len(swings) < 2:
            return resultado_neutro

        # ── Extraer último SH y último SL del rango ───────
        ultimo_sh = next((s for s in reversed(swings) if s['tipo'] == 'SH'), None)
        ultimo_sl = next((s for s in reversed(swings) if s['tipo'] == 'SL'), None)

        if ultimo_sh is None or ultimo_sl is None:
            return resultado_neutro

        swing_high = ultimo_sh['precio']
        swing_low  = ultimo_sl['precio']

        # Para ?ndices H4: si el precio est? fuera del rango de swings
        # (precio en nuevo m?ximo/m?nimo) usar rango directo de velas
        if simbolo in INDICES_H4:
            sh_real = round(df['high'].max(), 2)
            sl_real = round(df['low'].min(), 2)
            if sh_real > swing_high or sl_real < swing_low:
                swing_high = sh_real
                swing_low  = sl_real

        # Verificar que el rango tiene sentido
        if swing_high <= swing_low:
            return resultado_neutro

        # Rango m?nimo por ?ndice ? si el swing detectado es muy peque?o
        # usar el rango real de las ?ltimas 50 velas H1
        RANGO_MINIMO = {
            'PainX 1200': 300, 'GainX 1200': 300,
            'PainX 999':  200, 'GainX 999':  200,
            'PainX 800':  150, 'GainX 800':  150,
            'PainX 600':  150, 'GainX 600':  150,
            'PainX 400':  150, 'GainX 400':  150,
        }
        rango_min = RANGO_MINIMO.get(simbolo, 100)
        rango_calculado = swing_high - swing_low
        if rango_calculado < rango_min:
            # Usar rango real de 50 velas H1
            swing_high = round(df.tail(50)['high'].max(), 2)
            swing_low  = round(df.tail(50)['low'].min(), 2)
            if swing_high <= swing_low:
                return resultado_neutro

        rango       = swing_high - swing_low
        equilibrium = round(swing_low + rango * 0.5, 2)
        buffer      = rango * (BUFFER_EQ_PCT / 100)

        # ── Posición en el rango (0% = low, 100% = high) ──
        pct = round((precio_actual - swing_low) / rango * 100, 1)

        # ── Determinar zona ───────────────────────────────
        if precio_actual > (equilibrium + buffer):
            zona = 'PREMIUM'
        elif precio_actual < (equilibrium - buffer):
            zona = 'DISCOUNT'
        else:
            zona = 'EQUILIBRIUM'

        # ── Validar alineación con la dirección del trade ──
        # GainX  (LONG)  → válido en DISCOUNT o EQUILIBRIUM
        # PainX  (SHORT) → válido en PREMIUM o EQUILIBRIUM
        if es_bajista:
            valid = zona in ('PREMIUM', 'EQUILIBRIUM')
        else:
            valid = zona in ('DISCOUNT', 'EQUILIBRIUM')

        # ── Icono visual ──────────────────────────────────
        if zona == 'PREMIUM':
            icono = '🔴'
        elif zona == 'DISCOUNT':
            icono = '🟢'
        else:
            icono = '🟡'

        dir_txt  = 'SHORT' if es_bajista else 'LONG'
        valid_txt = '✅ alineado' if valid else '⚠️ contratendencia P/D'

        desc = (
            f"{icono} P/D: {zona} ({pct:.0f}% del rango) | "
            f"EQ={equilibrium:.0f} | "
            f"Rango [{swing_low:.0f}–{swing_high:.0f}] | "
            f"{dir_txt} → {valid_txt}"
        )

        return {
            'valid':        valid,
            'zona':         zona,
            'equilibrium':  equilibrium,
            'swing_high':   swing_high,
            'swing_low':    swing_low,
            'pct_en_rango': pct,
            'descripcion':  desc,
        }

    except Exception as e:
        print(f"  [pd_filter_v6] Error en {simbolo}: {e}")
        return resultado_neutro
