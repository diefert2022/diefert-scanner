# ============================================================
#  DIEFERT SCANNER v5 — estructura_nuevos_v1.py
#
#  Señales de ESTRUCTURA PURA (soportes/resistencias + CHoCH)
#  para los índices NUEVOS de Weltrade que el broker nuevo
#  también replica con el mismo nombre: FX Vol y SFX Vol.
#
#  POR QUÉ MÓDULO APARTE (no se tocó main_v5.py, resistencias.py,
#  alertas_v5.py, ob_v5.py, config_v413.py ni broker.py):
#  ─────────────────────────────────────────────────────────
#  - FX Vol y SFX Vol son BIDIRECCIONALES (no tienen lado fijo
#    como PainX=venta / GainX=compra), así que no encajan en
#    el motor TIPO1/TIPO1_OB/TIPO2 de main_v5.py, que asume
#    una dirección fija (es_bajista) por símbolo desde
#    SIMBOLOS_BAJISTAS/SIMBOLOS_ALCISTAS.
#  - Tampoco tienen perfil calibrado en config_v413.py
#    (ob_h4_min, fvg_bull_fuerte, sl_minimo, etc.) porque no
#    hay CSV real todavía — por eso este módulo NO usa OB/FVG,
#    solo estructura pura: swings (SH/SL) + CHoCH, que
#    funciona igual de bien sin calibración por índice.
#  - Nombres iguales a Weltrade en el broker nuevo → no hace
#    falta tocar broker.py (nombre_real() ya devuelve el mismo
#    nombre cuando el símbolo no está en EQUIVALENCIAS).
#
#  ⚠️ 100% independiente — mismo principio que harmonicos_v1.py:
#  - Reusa detectar_swings / detectar_tendencia / detectar_bos_choch
#    de estructura.py (sin modificar ese archivo).
#  - Reusa obtener_df / enviar_telegram / puede_enviar /
#    registrar_envio de utils.py (sin modificar ese archivo).
#  - Si algo falla acá, main_v5.py lo atrapa con su propio
#    try/except y el resto del scanner sigue sin enterarse.
#
#  MARCADO EN MICROGRID (v1.1):
#  ─────────────────────────────────────────────────────────
#  Cada señal también llama a registrar_trade() de
#  trade_tracker.py (sin modificar ese archivo), exactamente
#  igual que main_v5.py con TIPO1/TIPO1_OB/TIPO2. Eso hace que:
#    - Se guarde en trades_log.csv y se copie a MQL5/Files
#      → MicroGrid dibuja línea de ENTRADA + SL en el gráfico.
#    - Se distribuya vía Sheets/Worker a todos los usuarios
#      con licencia (Licencia/Vitalicia), igual que cualquier
#      otra señal del scanner — decisión confirmada por Diego.
#
#  DIRECCIÓN: se decide en vivo con cada señal, según hacia
#  dónde rompió el CHoCH (rotura alcista = compra, rotura
#  bajista = venta). No hay sesgo fijo por símbolo, a
#  diferencia de PainX/GainX.
#
#  CÓMO SE LLAMA DESDE main_v5.py:
#    from estructura_nuevos_v1 import analizar_estructura_nuevos
#    ...dentro del ciclo, UNA VEZ por vuelta (no por símbolo,
#    esta función ya recorre su propia lista adentro):
#    analizar_estructura_nuevos()
# ============================================================

from datetime import datetime

from config import TF_M5, VELAS_M5
from utils import obtener_df, enviar_telegram, puede_enviar, registrar_envio
from estructura import detectar_swings, detectar_tendencia, detectar_bos_choch
from trade_tracker import registrar_trade

# ── Símbolos nuevos (mismo nombre en Weltrade y en el broker nuevo) ──
SIMBOLOS_ESTRUCTURA_NUEVOS = [
    "FX Vol 20", "FX Vol 40", "FX Vol 60", "FX Vol 80", "FX Vol 99",
    "SFX Vol 20", "SFX Vol 40", "SFX Vol 60", "SFX Vol 80", "SFX Vol 99",
]

# ── Parámetros (ajustables sin afectar nada más del scanner) ──
VENTANA_SWING  = 3      # misma ventana que usa TIPO1 en M5 (main_v5.py)
VELAS_RECIENTE = 3      # el CHoCH debe haber ocurrido en las últimas N velas M5
SL_BUFFER      = 15     # pts extra más allá del swing roto (buffer de seguridad)
RR_MINIMO      = 2.0    # mismo mínimo que exige el motor principal
COOLDOWN_SEG   = 1200   # 20 min entre señales del mismo símbolo (igual que COOLDOWN_SEÑAL)


def _clave(simbolo):
    return f"estructura_nueva_{simbolo}"


def _calcular_sl_tp(precio_entrada, nivel_swing, es_venta, rr=RR_MINIMO):
    """
    SL = swing roto + buffer (venta) / swing roto - buffer (compra).
    TP con RR mínimo, mismo esquema que _calcular_tp de main_v5.py.
    """
    if es_venta:
        sl = max(nivel_swing, precio_entrada) + SL_BUFFER
    else:
        sl = min(nivel_swing, precio_entrada) - SL_BUFFER

    dist_sl = abs(precio_entrada - sl)
    if dist_sl <= 0:
        return None

    if es_venta:
        tp1 = precio_entrada - dist_sl * rr
        tp2 = precio_entrada - dist_sl * rr * 1.5
    else:
        tp1 = precio_entrada + dist_sl * rr
        tp2 = precio_entrada + dist_sl * rr * 1.5

    return {
        'sl':      round(sl, 2),
        'tp1':     round(tp1, 2),
        'tp2':     round(tp2, 2),
        'dist_sl': round(dist_sl, 0),
        'rr':      rr,
    }


def _mensaje(simbolo, es_venta, precio, tps, nivel_swing):
    icono  = '📉' if es_venta else '📈'
    accion = 'VENTA' if es_venta else 'COMPRA'
    return '\n'.join([
        f"{icono} <b>SEÑAL ESTRUCTURA — {accion} | {simbolo}</b>",
        "━━━━━━━━━━━━━━━━━━",
        "📌 Tipo: CHoCH estructural (solo S/R, sin OB/FVG)",
        f"💰 Entrada: <b>{precio:.0f}</b>",
        f"🛑 SL: {tps['sl']:.0f}  ({tps['dist_sl']:.0f} pts)",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 TP1: {tps['tp1']:.0f}  RR {tps['rr']}:1",
        f"🎯 TP2: {tps['tp2']:.0f}  RR {tps['rr'] * 1.5:.1f}:1",
        "━━━━━━━━━━━━━━━━━━",
        f"🔀 Swing roto: {nivel_swing:.0f}",
        "⚠️ Índice sin calibración CSV — solo estructura pura.",
        f"⏰ {datetime.now().strftime('%H:%M:%S')}",
    ])


def analizar_estructura_nuevos():
    """
    Recorre SIMBOLOS_ESTRUCTURA_NUEVOS y busca un CHoCH reciente
    en M5 en cualquier dirección. Llamar UNA VEZ por ciclo desde
    main_v5.py (esta función ya recorre su propia lista adentro,
    no hace falta ponerla dentro del for de SIMBOLOS principal).
    """
    for simbolo in SIMBOLOS_ESTRUCTURA_NUEVOS:
        try:
            df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
            if df_m5 is None or len(df_m5) < 20:
                continue

            swings    = detectar_swings(df_m5, ventana=VENTANA_SWING)
            tendencia = detectar_tendencia(swings)
            choch     = detectar_bos_choch(df_m5, swings, tendencia)

            if not choch or choch['tipo'] != 'CHoCH':
                continue

            # Solo señales recientes — que el CHoCH acaba de ocurrir,
            # no uno viejo que ya se movió hace rato
            velas_desde_choch = (len(df_m5) - 1) - choch['idx']
            if velas_desde_choch > VELAS_RECIENTE:
                continue

            clave = _clave(simbolo)
            if not puede_enviar(clave, COOLDOWN_SEG):
                continue

            precio_entrada = float(df_m5['close'].iloc[-1])
            es_venta       = choch['direccion'] == 'bajista'

            tps = _calcular_sl_tp(precio_entrada, choch['nivel'], es_venta)
            if not tps or tps['rr'] < RR_MINIMO:
                continue

            msg = _mensaje(simbolo, es_venta, precio_entrada, tps, choch['nivel'])
            enviar_telegram(msg)
            registrar_envio(clave)

            # Marca el gráfico vía MicroGrid (línea entrada + SL) y
            # distribuye a usuarios con licencia — mismo mecanismo
            # que usan las señales TIPO1/TIPO1_OB/TIPO2 normales.
            registrar_trade(
                simbolo=simbolo,
                es_bajista=es_venta,
                precio_entrada=precio_entrada,
                sl=tps['sl'],
                tp1=tps['tp1'],
                tp2=tps['tp2'],
                score_poi=0,
                trigger='ESTRUCTURA_NUEVA',
            )

            accion_txt = 'VENTA' if es_venta else 'COMPRA'
            print(
                f"  ✅ [Estructura nueva] SEÑAL | {simbolo} | {accion_txt} | "
                f"entrada={precio_entrada:.0f} SL={tps['sl']:.0f} TP1={tps['tp1']:.0f}"
            )

        except Exception as e:
            print(f"  [Estructura nueva] Error en {simbolo}: {e}")
