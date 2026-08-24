# ============================================================
#  DIEFERT SCANNER v5 — main_v5.py
#  ACTUALIZADO v6.1: sweep, premium/discount, CHoCH M1,
#                    OB H1 + M1 (ob_v5), contexto macro inicial
#
#  NÚCLEO LIMPIO — construido desde cero sobre la base definida
#  en papel antes de codear.
#
#  LÓGICA DE ANÁLISIS:
#  ─────────────────────────────────────────────────────────
#  Entrada Tipo 1 — Zona histórica:
#    Zona fuerte (2+ toques + liquidez) en M30/H1/H4/D1
#    → alerta 10pts antes
#    → CHoCH en M5 con cierre de vela dentro/en zona
#    → señal
#
#  Entrada Tipo 1_M1 — CHoCH M1 en zona (v6):
#    Igual que Tipo 1 pero detectado en M1 cuando precio
#    ya está dentro de la zona. Entrada más precisa y temprana.
#    Requiere además sweep previo confirmado.
#
#  Entrada Tipo 1_OB — OB H1 activo (v6.1 NUEVO):
#    OB H1 calibrado por índice (config_v413).
#    Precio retrocede al OB → señal si hay CHoCH M5 o sweep.
#    Prioridad: entre Tipo1 y Tipo2.
#
#  Entrada Tipo 2 — Continuación BOS:
#    BOS en M15 o M5 confirma tendencia activa
#    → precio retrocede al OB que generó el BOS
#    → precio llega al OB
#    → señal
#
#  DIRECCIÓN (fija, sin excepciones):
#    GainX 400/600/800/999/1200 → solo COMPRAS
#    PainX 400/600/800/999/1200 → solo VENTAS
#
#  GESTIÓN:
#    SL = máximo anterior M5 (venta) / mínimo anterior M5 (compra)
#    TP = RR mínimo 1:2 calculado desde el SL
#    Resistencias en el camino = advertencia, no bloqueo
#
#  PRINCIPIO DE ADICIÓN:
#    Todo lo nuevo va en módulo separado.
#    Nunca se modifica este archivo para agregar features.
#    Lo nuevo suma información o score, nunca bloquea.
#
#  NO SE TOCA:
#    broker.py, utils.py, trade_tracker.py
#    Sistema Telegram (dos canales), marcas en MT5
#
#  CAMBIOS v6.1:
#  ─────────────────────────────────────────────────────────
#  [+] ob_v5.py integrado — OB H1 + M1 con umbrales calibrados
#      por índice desde config_v413 (ob_h1_min, ob_m1_min reales)
#  [+] contexto_inicial.py — análisis macro D1→H4→H1→M15→M5
#      corre al arrancar, se refresca cada 60 min
#  [+] SL usa config_v413 sl_minimo calibrado (antes usaba config.py viejo)
#  [+] Señal TIPO1_OB cuando precio en OB H1 activo + sweep confirmado
# ============================================================

import MetaTrader5 as mt5
import os
import time
from datetime import datetime

# ── Intocables ────────────────────────────────────────────
from broker import detectar_y_configurar, nombre_real
from utils import (
    obtener_df,
    enviar_telegram,
    puede_enviar,
    registrar_envio,
    tiempo_restante_cooldown,
)
from trade_tracker import registrar_trade, verificar_trades, trades_activos_resumen, resumen_dia

# ── Módulos copiados sin tocar ─────────────────────────────
from config import (
    SIMBOLOS, SIMBOLOS_BAJISTAS,
    TF_M5, TF_M15,
    VELAS_M5, VELAS_M15,
    CICLO_SEG,
    SL_MINIMO, SL_MINIMO_DEFAULT,
)
from config_v413 import get_config   # ← umbrales calibrados por CSV real
from resistencias import (
    actualizar_si_necesario as actualizar_zonas,
    obtener_niveles,
)
from estructura import (
    detectar_swings,
    detectar_bos_choch,
    detectar_bos_estructural,
)

# ── Módulos v5 ────────────────────────────────────────────
from alertas_v5 import evaluar_alerta, resumen_alerta_consola, resumen_alerta_telegram

# ── Módulos v6 ────────────────────────────────────────────
from sweep_v6 import verificar_sweep
from pd_filter_v6 import verificar_premium_discount
from choch_m1_v6 import verificar_choch_m1
from institutional_setup_v6 import evaluar_setup_institucional

# ── Módulos v6.1 (NUEVOS) ─────────────────────────────────
from ob_v5 import verificar_obs

# ── EmaScalpD (canal exclusivo Telegram) ──────────────────
from emascalpd_v1 import analizar_emascalpd

# ── Patrones Armónicos PCI (v1 — señal independiente, solo seguimiento) ──
from harmonicos_v1 import analizar_patron_armonico

# ── Motor bidireccional para FlipX (v1 — zonas+FVG+OB+CHoCH/BOS) ──
from motor_bidireccional_v1 import analizar_indices_bidireccionales

# ═══ INICIO BLOQUE COMPETENCIA (BORRAR AL TERMINAR) ═══
from spike_hunter_v1 import cazar_spikes
# ═══ FIN BLOQUE COMPETENCIA ═══
from volumen_sintetico_v6 import analizar_volumen_sintetico
from contexto_inicial import (
    inicializar_contexto,
    obtener_contexto,
    refrescar_si_necesario,
    imprimir_resumen_contexto,
)

# ── Configuración ─────────────────────────────────────────
COOLDOWN_SEÑAL  = 1200   # 20 minutos entre señales del mismo símbolo
RR_MINIMO       = 2.0    # ratio mínimo riesgo:beneficio
DIST_ZONA       = 10     # pts antes de zona para alerta temprana
TOQUES_MINIMOS  = 2      # toques históricos mínimos para zona válida
SCORE_ZONA_MIN  = 3      # score mínimo de zona para considerar válida

# ── Validación de metodología (24-ago-2026) ─────────────────
# Mientras se valida la calidad de TIPO1 (zona real D1+H4+H1 +
# CHoCH confirmado en M5 — la metodología "correcta": resistencia
# fuerte + rechazo + giro confirmado), los otros 4 tipos quedan
# apagados. Es reversible: poner en False reactiva todo tal cual
# estaba (INSTITUCIONAL, TIPO1_M1, TIPO1_OB, TIPO2).
SOLO_TIPO1_ACTIVO = True
CICLO_ZONAS_SEG = 900    # recalcular zonas cada 15 minutos


def _clave_señal(simbolo):
    return f"señal_v5_{simbolo}"


# ============================================================
#  HEARTBEAT — para que watchdog.py detecte si el scanner
#  se quedó colgado (nunca debe poder tumbar el scanner: por
#  eso está protegido con su propio try/except).
# ============================================================

def _latido():
    try:
        heartbeat_path = os.path.join(os.path.dirname(__file__), "heartbeat.txt")
        with open(heartbeat_path, 'w', encoding='utf-8') as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass


# ============================================================
#  HELPER — SL desde máximo/mínimo anterior M5
#  v6.1: usa sl_minimo de config_v413 (calibrado por CSV real)
#        en lugar del valor genérico de config.py
# ============================================================

def _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo):
    """
    SL = máximo anterior en ventas / mínimo anterior en compras.
    Usa las últimas 10 velas M5 para encontrar el swing relevante.
    Respeta el SL mínimo calibrado por índice.

    v6.1: prioriza sl_minimo de config_v413 (valor real por CSV)
          sobre el genérico de SL_MINIMO en config.py.
    """
    # Priorizar config_v413 (calibrado real) sobre config.py (genérico)
    cfg    = get_config(simbolo)
    sl_min = cfg.get('sl_minimo') or SL_MINIMO.get(simbolo, SL_MINIMO_DEFAULT)

    if df_m5 is None or len(df_m5) < 5:
        if es_bajista:
            return precio_entrada + sl_min
        return precio_entrada - sl_min

    ultimas = df_m5.tail(10)

    if es_bajista:
        sl_calculado = ultimas['high'].max()
        sl = max(sl_calculado, precio_entrada + sl_min)
    else:
        sl_calculado = ultimas['low'].min()
        sl = min(sl_calculado, precio_entrada - sl_min)

    return round(sl, 2)


# ============================================================
#  HELPER — TP con RR mínimo 1:2
# ============================================================

def _calcular_tp(precio_entrada, sl, es_bajista, rr=RR_MINIMO):
    dist_sl = abs(precio_entrada - sl)
    if es_bajista:
        tp1 = precio_entrada - (dist_sl * rr)
        tp2 = precio_entrada - (dist_sl * rr * 1.5)
    else:
        tp1 = precio_entrada + (dist_sl * rr)
        tp2 = precio_entrada + (dist_sl * rr * 1.5)

    rr_real = round(dist_sl * rr / dist_sl, 1) if dist_sl > 0 else 0

    return {
        'tp1':     round(tp1, 2),
        'tp2':     round(tp2, 2),
        'sl':      sl,
        'dist_sl': round(dist_sl, 0),
        'rr':      rr_real,
    }


# ============================================================
#  HELPER — Verificar resistencias en el camino al TP
# ============================================================

def _resistencias_en_camino(simbolo, precio_entrada, tp1, es_bajista):
    zonas = obtener_niveles(simbolo, solo_activas=True, min_fuerza=2)
    en_camino = []

    for z in zonas:
        p = z['precio']
        if es_bajista:
            if tp1 < p < precio_entrada:
                en_camino.append(z)
        else:
            if precio_entrada < p < tp1:
                en_camino.append(z)

    return sorted(en_camino, key=lambda x: abs(x['precio'] - precio_entrada))


# ============================================================
#  DETECCIÓN TIPO 1 — CHoCH M5 en zona histórica
# ============================================================

def _detectar_choch_en_zona(simbolo, es_bajista, zonas_validas):
    """
    TIPO1 — la metodología principal: zona fuerte (D1+H4+H1) +
    CHoCH confirmado en M5. Los sintéticos reaccionan rápido en
    las zonas fuertes — M5 captura el giro a tiempo, sin esperar
    a que el precio ya se haya movido (M15 confirma tarde). Lo
    que filtra el ruido es la exigencia de la ZONA (score≥3,
    ≥2 toques, combinando D1+H4+H1), no la temporalidad del CHoCH.
    """
    df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
    if df_m5 is None or len(df_m5) < 20:
        return {'detectado': False}

    precio_actual = df_m5['close'].iloc[-1]
    swings_m5     = detectar_swings(df_m5, ventana=3)

    if not swings_m5:
        return {'detectado': False}

    choch = detectar_bos_choch(
        df_m5,
        swings_m5,
        tendencia='bajista' if not es_bajista else 'alcista'
    )

    if choch is None:
        return {'detectado': False}

    dir_esperada = 'bajista' if es_bajista else 'alcista'
    if choch['direccion'] != dir_esperada:
        return {'detectado': False}

    idx_choch  = choch['idx']
    idx_ultima = len(df_m5) - 1
    if (idx_ultima - idx_choch) > 3:
        return {'detectado': False}

    for zona in zonas_validas:
        precio_zona = zona['precio']
        tol_zona    = 50

        if abs(precio_actual - precio_zona) <= tol_zona:
            return {
                'detectado':   True,
                'tipo':        'TIPO1',
                'zona':        zona,
                'precio':      precio_actual,
                'choch_nivel': choch['nivel'],
                'df_m5':       df_m5,
            }

    return {'detectado': False}


# ============================================================
#  DETECCIÓN TIPO 1_OB — OB H1 activo + sweep (NUEVO v6.1)
# ============================================================

def _detectar_ob_h1_activo(simbolo, es_bajista, obs, sweep):
    """
    Señal TIPO1_OB: precio está en OB H1 calibrado por índice
    Y hay un sweep previo confirmado.

    Esto resuelve el problema de PainX 400: el scanner tenía
    ob_h1_min=110 (P85) cuando el valor real calibrado es 79 (P70).
    Con ob_v5 se usan los umbrales correctos de config_v413.

    Prioridad: mayor que Tipo2, menor que Tipo1_M1 y Tipo1.
    """
    if not obs['ob_h1']['detectado']:
        return {'detectado': False}

    if not sweep['hubo_sweep']:
        return {'detectado': False}

    ob = obs['ob_h1']
    return {
        'detectado': True,
        'tipo':      'TIPO1_OB',
        'precio':    ob['ob_mid'],
        'ob_high':   ob['ob_high'],
        'ob_low':    ob['ob_low'],
        'ob_body':   ob['ob_body'],
        'es_fuerte': ob['es_fuerte'],
    }


# ============================================================
#  DETECCIÓN TIPO 2 — BOS en M15/M5 + retroceso a OB
# ============================================================

def _detectar_bos_retroceso(simbolo, es_bajista):
    for tf, velas, tf_nombre in [(TF_M15, VELAS_M15, 'M15'), (TF_M5, VELAS_M5, 'M5')]:
        try:
            df = obtener_df(simbolo, tf, velas)
            if df is None or len(df) < 20:
                continue

            precio_actual = df['close'].iloc[-1]
            swings        = detectar_swings(df, ventana=4 if tf == TF_M15 else 3)

            if not swings:
                continue

            bos = detectar_bos_estructural(df, swings, es_bajista)

            if not bos['detectado']:
                continue

            idx_bos    = bos['idx']
            idx_ultima = len(df) - 1
            if (idx_ultima - idx_bos) > 5:
                continue

            ob_high = None
            ob_low  = None

            for i in range(bos['idx'] - 1, max(0, bos['idx'] - 10), -1):
                c = df.iloc[i]
                if es_bajista:
                    if c['close'] > c['open']:
                        ob_high = round(c['high'], 2)
                        ob_low  = round(c['low'],  2)
                        break
                else:
                    if c['close'] < c['open']:
                        ob_high = round(c['high'], 2)
                        ob_low  = round(c['low'],  2)
                        break

            if ob_high is None:
                continue

            precio_en_ob = precio_actual >= ob_low and precio_actual <= ob_high

            if precio_en_ob:
                return {
                    'detectado': True,
                    'tipo':      'TIPO2',
                    'tf_bos':    tf_nombre,
                    'ob_high':   ob_high,
                    'ob_low':    ob_low,
                    'ob_mid':    round((ob_high + ob_low) / 2, 2),
                    'precio':    precio_actual,
                    'bos_nivel': bos['nivel'],
                    'df_ref':    df,
                }

        except Exception as e:
            print(f"  [v5] Error BOS {simbolo} {tf_nombre}: {e}")
            continue

    return {'detectado': False}


# ============================================================
#  CONSTRUIR MENSAJE TELEGRAM
# ============================================================

def _construir_mensaje(simbolo, es_bajista, precio, sl, tps,
                        tipo_entrada, zona=None, tf_bos=None,
                        resistencias_camino=None,
                        sweep=None, pd_ctx=None, obs=None,
                        ctx=None):
    icono  = '📉' if es_bajista else '📈'
    accion = 'VENTA' if es_bajista else 'COMPRA'

    if tipo_entrada == 'TIPO1_M1':
        tipo_txt = 'CHoCH M1 EN ZONA 🎯'
    elif tipo_entrada == 'TIPO1':
        tipo_txt = 'ZONA HISTÓRICA'
    elif tipo_entrada == 'TIPO1_OB':
        tipo_txt = 'OB H1 INSTITUCIONAL 🏛'
    else:
        tipo_txt = f'CONTINUACIÓN BOS {tf_bos}'

    lineas = [
        f"{icono} <b>SEÑAL — {accion} | {simbolo}</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"📌 Tipo: {tipo_txt}",
        f"💰 Entrada: <b>{precio:.0f}</b>",
        f"🛑 SL: {sl:.0f}  ({tps['dist_sl']:.0f} pts)",
        f"━━━━━━━━━━━━━━━━━━",
        f"🎯 TP1: {tps['tp1']:.0f}  RR {tps['rr']}:1",
        f"🎯 TP2: {tps['tp2']:.0f}  RR {tps['rr'] * 1.5:.1f}:1",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    # Contexto macro (v6.1)
    if ctx and ctx.get('bias_general'):
        alineado_txt = '✅' if ctx.get('alineado') else '⚠️'
        pdh = f"PDH={ctx['pdh']:.0f}" if ctx.get('pdh') else ''
        pdl = f"PDL={ctx['pdl']:.0f}" if ctx.get('pdl') else ''
        lineas.append(
            f"📊 Bias: {ctx['bias_general']} {alineado_txt} | {pdh} {pdl}"
        )

    # Info de zona (Tipo 1 / Tipo 1_M1)
    if zona:
        tf_zona = '+'.join(zona.get('tfs', ['?']))
        lineas.append(
            f"🏛 Zona {tf_zona}: {zona['precio']:.0f} | "
            f"{zona['fuerza_txt']} | {zona.get('n_toques',0)} toques"
        )

    # Info OB H1 (Tipo1_OB)
    if obs and obs['ob_h1']['detectado']:
        ob = obs['ob_h1']
        fuerza = '🔥 FUERTE' if ob['es_fuerte'] else 'Normal'
        lineas.append(
            f"🏛 OB H1 {fuerza}: [{ob['ob_low']:.0f}–{ob['ob_high']:.0f}] "
            f"cuerpo={ob['ob_body']:.0f}pts"
        )

    # Contexto sweep v6
    if sweep and sweep.get('hubo_sweep'):
        lineas.append(f"🧹 {sweep['descripcion']}")

    # Contexto Premium/Discount v6
    if pd_ctx:
        lineas.append(f"{pd_ctx['descripcion']}")

    # Resistencias en el camino (informativo)
    if resistencias_camino:
        for r in resistencias_camino[:2]:
            lineas.append(
                f"⚠️ Nivel en camino: {r['precio']:.0f} "
                f"({r['direccion']})"
            )

    lineas.append(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

    return '\n'.join(lineas)


# ============================================================
#  CICLO PRINCIPAL — analizar un símbolo
# ============================================================

def analizar_simbolo(simbolo):
    """
    Analiza un símbolo completo.
    Jerarquía de señales (mayor a menor prioridad):
      1. TIPO1_M1  — CHoCH M1 en zona + sweep
      2. TIPO1     — CHoCH M5 en zona histórica
      3. TIPO1_OB  — OB H1 calibrado + sweep (NUEVO v6.1)
      4. TIPO2     — BOS + retroceso al OB generador

    v6.1: integra ob_v5 y contexto_inicial.
    FlipX: ignorados por scanner principal (solo EmaScalpD los analiza)
    """
    # FlipX solo los analiza EmaScalpD
    if simbolo.startswith("FlipX"):
        return {'simbolo': simbolo, 'resultado': 'EMASCALPD_ONLY', 'precio': 0}

    es_bajista = simbolo in SIMBOLOS_BAJISTAS

    # ── 1. Actualizar zonas históricas ──────────────────────
    actualizar_zonas(simbolo, es_bajista)

    # ── 2. Obtener zonas válidas ─────────────────────────────
    todas_zonas   = obtener_niveles(simbolo, solo_activas=True, min_fuerza=1)
    zonas_validas = [
        z for z in todas_zonas
        if z.get('n_toques', 0) >= TOQUES_MINIMOS
        and z.get('score', 0) >= SCORE_ZONA_MIN
    ]

    # ── 3. Obtener precio actual ─────────────────────────────
    df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
    if df_m5 is None or len(df_m5) < 5:
        return {'simbolo': simbolo, 'resultado': 'SIN_DATOS'}

    precio_actual = df_m5['close'].iloc[-1]

    # ── 4. Contexto macro (v6.1) ─────────────────────────────
    ctx = obtener_contexto(simbolo)

    # ── 5. Evaluar alertas visuales ──────────────────────────
    for zona in zonas_validas:
        alerta      = evaluar_alerta(simbolo, precio_actual, zona, es_bajista)
        msg_consola = resumen_alerta_consola(alerta)
        if msg_consola:
            print(msg_consola)

        if alerta['activa'] and alerta['nivel'] >= 2:
            clave_alerta = f"alerta_v5_{simbolo}_{int(zona['precio'])}"
            if puede_enviar(clave_alerta, 3600):
                msg_tg = resumen_alerta_telegram(simbolo, alerta, es_bajista)
                if msg_tg:
                    enviar_telegram(msg_tg)
                    registrar_envio(clave_alerta)

    # ── 6. Módulos de contexto institucional (v6) ────────────
    sweep    = verificar_sweep(simbolo, es_bajista)
    pd_ctx   = verificar_premium_discount(simbolo, precio_actual, es_bajista)
    choch_m1 = verificar_choch_m1(simbolo, precio_actual, es_bajista, zonas_validas)

    # ── 6.1 OB H1 + M1 (NUEVO v6.1) ─────────────────────────
    obs = verificar_obs(simbolo, precio_actual, es_bajista)

    # ── 6.2 Volumen Sintético Diefert (VSD) ──────────────────
    vsd = analizar_volumen_sintetico(simbolo, es_bajista)
    if vsd['alerta']:
        print(f"  {vsd['descripcion']}")

    # Mostrar en consola
    if sweep['hubo_sweep']:
        print(f"  {sweep['descripcion']}")
    print(f"  {pd_ctx['descripcion']}")
    if choch_m1['en_zona']:
        print(f"  {choch_m1['descripcion']}")
    if obs['ob_h1']['detectado'] or obs['ob_m1']['detectado']:
        print(f"  {obs['descripcion']}")

    # ── 7. Verificar cooldown de señal ───────────────────────
    clave_señal = _clave_señal(simbolo)
    if not puede_enviar(clave_señal, COOLDOWN_SEÑAL):
        mins = tiempo_restante_cooldown(clave_señal, COOLDOWN_SEÑAL) // 60
        print(f"  ⏳ COOLDOWN | {simbolo} | faltan {mins}m")
        return {'simbolo': simbolo, 'resultado': 'COOLDOWN', 'precio': precio_actual}

    # ── 7.5 Setup INSTITUCIONAL (sweep + FVG + CHoCH M1) ─────
    if not SOLO_TIPO1_ACTIVO:
        setup_inst = evaluar_setup_institucional(simbolo, precio_actual)
        if setup_inst['detectado']:
            precio_entrada = setup_inst['entrada']
            sl  = _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo)
            tps = _calcular_tp(precio_entrada, sl, es_bajista)
            if tps['rr'] >= RR_MINIMO:
                enviar_telegram(setup_inst['descripcion'])
                registrar_envio(clave_señal)
                registrar_trade(
                    simbolo=simbolo, es_bajista=es_bajista,
                    precio_entrada=precio_entrada, sl=sl,
                    tp1=tps['tp1'], tp2=tps['tp2'],
                    score_poi=0, trigger='INSTITUCIONAL',
                )
                return {
                    'simbolo': simbolo, 'resultado': 'SEÑAL',
                    'tipo': 'INSTITUCIONAL', 'precio': precio_entrada,
                    'sl': sl, 'tps': tps,
                }

    # ── 8. Señal TIPO1_M1 — CHoCH M1 en zona + sweep ────────
    if not SOLO_TIPO1_ACTIVO and choch_m1['detectado'] and sweep['hubo_sweep'] and pd_ctx.get('valid', True):
        precio_entrada = choch_m1['precio']
        sl  = _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo)
        tps = _calcular_tp(precio_entrada, sl, es_bajista)

        if tps['rr'] >= RR_MINIMO:
            res_camino = _resistencias_en_camino(simbolo, precio_entrada, tps['tp1'], es_bajista)
            msg = _construir_mensaje(
                simbolo=simbolo, es_bajista=es_bajista,
                precio=precio_entrada, sl=sl, tps=tps,
                tipo_entrada='TIPO1_M1',
                zona=choch_m1['zona'],
                sweep=sweep, pd_ctx=pd_ctx,
                obs=obs, ctx=ctx,
                resistencias_camino=res_camino or None,
            )
            print(f"  ✅ SEÑAL TIPO1_M1 | {simbolo} | {'VENTA' if es_bajista else 'COMPRA'} | entrada={precio_entrada:.0f} SL={sl:.0f} TP1={tps['tp1']:.0f}")
            enviar_telegram(msg)
            registrar_envio(clave_señal)
            registrar_trade(
                simbolo=simbolo, es_bajista=es_bajista,
                precio_entrada=precio_entrada, sl=sl,
                tp1=tps['tp1'], tp2=tps['tp2'],
                score_poi=0, trigger='TIPO1_M1',
            )
            return {
                'simbolo': simbolo, 'resultado': 'SEÑAL',
                'tipo': 'TIPO1_M1', 'precio': precio_entrada,
                'sl': sl, 'tps': tps,
            }

    # ── 9. Señal TIPO1 — CHoCH M5 en zona ───────────────────
    señal = _detectar_choch_en_zona(simbolo, es_bajista, zonas_validas)

    if señal['detectado']:
        precio_entrada = señal['precio']
        sl  = _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo)
        tps = _calcular_tp(precio_entrada, sl, es_bajista)

        if tps['rr'] >= RR_MINIMO:
            res_camino = _resistencias_en_camino(simbolo, precio_entrada, tps['tp1'], es_bajista)
            msg = _construir_mensaje(
                simbolo=simbolo, es_bajista=es_bajista,
                precio=precio_entrada, sl=sl, tps=tps,
                tipo_entrada='TIPO1',
                zona=señal.get('zona'),
                sweep=sweep, pd_ctx=pd_ctx,
                obs=obs, ctx=ctx,
                resistencias_camino=res_camino or None,
            )
            print(f"  ✅ SEÑAL TIPO1 | {simbolo} | {'VENTA' if es_bajista else 'COMPRA'} | entrada={precio_entrada:.0f} SL={sl:.0f} TP1={tps['tp1']:.0f}")
            enviar_telegram(msg)
            registrar_envio(clave_señal)
            registrar_trade(
                simbolo=simbolo, es_bajista=es_bajista,
                precio_entrada=precio_entrada, sl=sl,
                tp1=tps['tp1'], tp2=tps['tp2'],
                score_poi=0, trigger='TIPO1',
            )
            return {
                'simbolo': simbolo, 'resultado': 'SEÑAL',
                'tipo': 'TIPO1', 'precio': precio_entrada,
                'sl': sl, 'tps': tps,
            }

    # ── 10. Señal TIPO1_OB — OB H1 + sweep (NUEVO v6.1) ─────
    señal_ob = _detectar_ob_h1_activo(simbolo, es_bajista, obs, sweep)

    if not SOLO_TIPO1_ACTIVO and señal_ob['detectado'] and pd_ctx.get('valid', True):
        precio_entrada = señal_ob['precio']
        sl  = _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo)
        tps = _calcular_tp(precio_entrada, sl, es_bajista)

        if tps['rr'] >= RR_MINIMO:
            res_camino = _resistencias_en_camino(simbolo, precio_entrada, tps['tp1'], es_bajista)
            msg = _construir_mensaje(
                simbolo=simbolo, es_bajista=es_bajista,
                precio=precio_entrada, sl=sl, tps=tps,
                tipo_entrada='TIPO1_OB',
                sweep=sweep, pd_ctx=pd_ctx,
                obs=obs, ctx=ctx,
                resistencias_camino=res_camino or None,
            )
            print(f"  ✅ SEÑAL TIPO1_OB | {simbolo} | {'VENTA' if es_bajista else 'COMPRA'} | entrada={precio_entrada:.0f} SL={sl:.0f} TP1={tps['tp1']:.0f}")
            enviar_telegram(msg)
            registrar_envio(clave_señal)
            registrar_trade(
                simbolo=simbolo, es_bajista=es_bajista,
                precio_entrada=precio_entrada, sl=sl,
                tp1=tps['tp1'], tp2=tps['tp2'],
                score_poi=0, trigger='TIPO1_OB',
            )
            return {
                'simbolo': simbolo, 'resultado': 'SEÑAL',
                'tipo': 'TIPO1_OB', 'precio': precio_entrada,
                'sl': sl, 'tps': tps,
            }

    # ── 11. Señal TIPO2 — BOS + retroceso ───────────────────
    if SOLO_TIPO1_ACTIVO:
        return {'simbolo': simbolo, 'resultado': 'SIN_SEÑAL', 'precio': precio_actual}

    señal = _detectar_bos_retroceso(simbolo, es_bajista)

    if not señal['detectado']:
        return {'simbolo': simbolo, 'resultado': 'SIN_SEÑAL', 'precio': precio_actual}

    precio_entrada = señal['precio']
    sl  = _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo)
    tps = _calcular_tp(precio_entrada, sl, es_bajista)

    if tps['rr'] < RR_MINIMO:
        print(f"  ⛔ RR insuficiente | {simbolo} | RR={tps['rr']} < {RR_MINIMO}")
        return {'simbolo': simbolo, 'resultado': 'RR_INSUFICIENTE', 'precio': precio_actual}

    res_camino = _resistencias_en_camino(simbolo, precio_entrada, tps['tp1'], es_bajista)
    msg = _construir_mensaje(
        simbolo=simbolo, es_bajista=es_bajista,
        precio=precio_entrada, sl=sl, tps=tps,
        tipo_entrada='TIPO2',
        tf_bos=señal.get('tf_bos'),
        sweep=sweep, pd_ctx=pd_ctx,
        obs=obs, ctx=ctx,
        resistencias_camino=res_camino or None,
    )

    print(f"  ✅ SEÑAL TIPO2 | {simbolo} | {'VENTA' if es_bajista else 'COMPRA'} | entrada={precio_entrada:.0f} SL={sl:.0f} TP1={tps['tp1']:.0f}")
    enviar_telegram(msg)
    registrar_envio(clave_señal)
    registrar_trade(
        simbolo=simbolo, es_bajista=es_bajista,
        precio_entrada=precio_entrada, sl=sl,
        tp1=tps['tp1'], tp2=tps['tp2'],
        score_poi=0, trigger='TIPO2',
    )

    return {
        'simbolo':   simbolo,
        'resultado': 'SEÑAL',
        'tipo':      'TIPO2',
        'precio':    precio_entrada,
        'sl':        sl,
        'tps':       tps,
    }


# ============================================================
#  PANEL CONSOLA
# ============================================================

def _imprimir_panel(resultados, hora):
    ancho = 98
    print(f"\n  {'═' * ancho}")
    print(f"  ║  DIEFERT SCANNER v5+v6.1   {hora}  ")
    print(f"  {'═' * ancho}")
    print(f"  {'SÍMBOLO':<16} {'PRECIO':>8}  {'RESULTADO':<20} {'TIPO':<10}")
    print(f"  {'─' * ancho}")
    for r in resultados:
        if r is None:
            continue
        simbolo   = r.get('simbolo', '?')
        precio    = r.get('precio', 0)
        resultado = r.get('resultado', '?')
        tipo      = r.get('tipo', '')
        icono     = '📉' if simbolo in SIMBOLOS_BAJISTAS else '📈'
        print(f"  {icono}{simbolo:<15} {precio:>8.0f}  {resultado:<20} {tipo}")
    print(f"  {'═' * ancho}\n")


# ============================================================
#  INICIALIZACIÓN Y LOOP PRINCIPAL
# ============================================================

def iniciar_v5():
    print("\n  🚀 Iniciando Diefert Scanner v5+v6.1...")

    # Limpiar trades del día anterior conservando encabezados
    import os
    import csv as _csv
    from trade_tracker import COLUMNAS
    csv_path = os.path.join(os.path.dirname(__file__), "trades_log.csv")
    if os.path.exists(csv_path):
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            _csv.DictWriter(f, fieldnames=COLUMNAS).writeheader()
        print("  🗑️  Trades anteriores limpiados — comenzando de cero")

    # Conectar MT5
    if not mt5.initialize():
        print(f"  ❌ Error MT5: {mt5.last_error()}")
        return

    broker = detectar_y_configurar(mt5)
    info   = mt5.account_info()
    if info:
        print(f"  ✅ MT5 conectado | Cuenta: {info.login} | Broker: {broker.upper()} | Balance: ${info.balance:.2f}")
    else:
        print(f"  ✅ MT5 conectado | Broker: {broker.upper()}")

    print(f"  📡 Ciclo: {CICLO_SEG}s | Cooldown señal: {COOLDOWN_SEÑAL//60}min | RR mínimo: {RR_MINIMO}")
    print(f"  📊 Símbolos: {len(SIMBOLOS)} activos")
    print(f"  🆕 Módulos v6.1: sweep + P/D filter + CHoCH M1 + OB H1/M1 + Contexto Macro")
    print(f"  ─────────────────────────────────────────────")

    _latido()  # heartbeat inicial, antes del analisis macro (que puede tardar)

    # ── ANÁLISIS MACRO INICIAL (v6.1) ─────────────────────────
    # Corre UNA VEZ al arrancar. Analiza D1→H4→H1→M15→M5.
    # Resuelve el problema de rangos incorrectos al reiniciar:
    # los sintéticos no descansan y el contexto macro se pierde
    # si no se calcula antes de entrar al loop.
    inicializar_contexto()

    ciclo = 0

    try:
        while True:
            ciclo += 1
            hora  = datetime.now().strftime('%H:%M:%S')

            # Refrescar contexto macro cada 60 min (no bloquea el ciclo)
            try:
                refrescar_si_necesario()
            except Exception as e_ctx:
                print(f"  [contexto] ERROR: {e_ctx}")

            resultados = []

            for simbolo in SIMBOLOS:
                try:
                    r = analizar_simbolo(simbolo)
                    resultados.append(r)
                except Exception as e:
                    print(f"  ❌ Error en {simbolo}: {e}")
                    resultados.append({'simbolo': simbolo, 'resultado': 'ERROR'})

                # ── EmaScalpD — DESACTIVADO (ya no envía señales a Telegram) ──
                # Para reactivar, descomenta las 4 líneas de abajo.
                # try:
                #     df_m5_ema = obtener_df(simbolo, TF_M5, 300)
                #     analizar_emascalpd(simbolo, df_m5_ema)
                # except Exception as e_ema:
                #     print(f"  [EmaScalpD] Error en {simbolo}: {e_ema}")

                # ═══ BLOQUE COMPETENCIA — DESACTIVADO 09-ago-2026 ═══
                # (seguimiento de spikes, mandaba al mismo tópico EmaScalpD)
                # Para reactivar, descomenta las 4 líneas de abajo.
                # try:
                #     cazar_spikes(simbolo)
                # except Exception as e_spk:
                #     print(f"  [spike_hunter] Error en {simbolo}: {e_spk}")
                # ═══ FIN BLOQUE COMPETENCIA ═══

                # ── Patrones Armónicos PCI — SOLO SEGUIMIENTO ──────
                # Módulo 100% independiente (ver harmonicos_v1.py).
                # No bloquea ni afecta ninguna señal TIPO1/TIPO1_OB/TIPO2.
                # Si falla, se registra el error y el ciclo sigue normal.
                try:
                    analizar_patron_armonico(simbolo)
                except Exception as e_harm:
                    print(f"  [Harmónicos] Error en {simbolo}: {e_harm}")

                # Heartbeat despues de cada simbolo (no solo al final del
                # ciclo) para que el watchdog detecte un cuelgue rapido,
                # incluso si se congela a mitad de un ciclo largo.
                _latido()

            # ── Motor completo bidireccional (FlipX) ─────────────────────
            # Módulo 100% independiente — no toca el motor TIPO1/TIPO1_OB/TIPO2.
            # Ver motor_bidireccional_v1.py para el detalle completo.
            try:
                analizar_indices_bidireccionales()
            except Exception as e_motor_bidir:
                print(f"  [Motor bidireccional] ERROR general: {e_motor_bidir}")

            # Panel cada 10 ciclos
            if ciclo % 10 == 0:
                _imprimir_panel(resultados, hora)
                print(resumen_dia())

            # Verificar trades activos
            try:
                verificar_trades()
            except Exception as e_vt:
                print(f"  [verificar_trades] ERROR: {e_vt}")

            # Escuchar comandos Telegram
            try:
                from analisis_demanda import verificar_comando_telegram
                verificar_comando_telegram()
            except Exception as _e:
                import traceback
                print(f"  [analisis] ERROR: {_e}")
                traceback.print_exc()

            time.sleep(CICLO_SEG)

    except KeyboardInterrupt:
        print("\n  🛑 Scanner detenido por usuario")
        mt5.shutdown()


if __name__ == "__main__":
    iniciar_v5()
