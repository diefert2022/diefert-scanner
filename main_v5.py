# ============================================================
#  DIEFERT SCANNER v5 — main_v5.py
#  ACTUALIZADO v6: sweep, premium/discount, CHoCH M1
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
#  Entrada Tipo 1_M1 — CHoCH M1 en zona (NUEVO v6):
#    Igual que Tipo 1 pero detectado en M1 cuando precio
#    ya está dentro de la zona. Entrada más precisa y temprana.
#    Requiere además sweep previo confirmado.
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
# ============================================================

import MetaTrader5 as mt5
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

# ── Módulos nuevos v6 ─────────────────────────────────────
from sweep_v6 import verificar_sweep
from pd_filter_v6 import verificar_premium_discount
from choch_m1_v6 import verificar_choch_m1

# ── Configuración ─────────────────────────────────────────
COOLDOWN_SEÑAL  = 1200   # 20 minutos entre señales del mismo símbolo
RR_MINIMO       = 2.0    # ratio mínimo riesgo:beneficio
DIST_ZONA       = 10     # pts antes de zona para alerta temprana
TOQUES_MINIMOS  = 2      # toques históricos mínimos para zona válida
SCORE_ZONA_MIN  = 3      # score mínimo de zona para considerar válida
CICLO_ZONAS_SEG = 900    # recalcular zonas cada 15 minutos


def _clave_señal(simbolo):
    return f"señal_v5_{simbolo}"


# ============================================================
#  HELPER — SL desde máximo/mínimo anterior M5
# ============================================================

def _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo):
    """
    SL = máximo anterior en ventas / mínimo anterior en compras.
    Usa las últimas 10 velas M5 para encontrar el swing relevante.
    Respeta el SL mínimo calibrado por índice.
    """
    sl_min = SL_MINIMO.get(simbolo, SL_MINIMO_DEFAULT)

    if df_m5 is None or len(df_m5) < 5:
        if es_bajista:
            return precio_entrada + sl_min
        return precio_entrada - sl_min

    ultimas = df_m5.tail(10)

    if es_bajista:
        # SL en el máximo anterior
        sl_calculado = ultimas['high'].max()
        sl = max(sl_calculado, precio_entrada + sl_min)
    else:
        # SL en el mínimo anterior
        sl_calculado = ultimas['low'].min()
        sl = min(sl_calculado, precio_entrada - sl_min)

    return round(sl, 2)


# ============================================================
#  HELPER — TP con RR mínimo 1:2
# ============================================================

def _calcular_tp(precio_entrada, sl, es_bajista, rr=RR_MINIMO):
    """
    TP = entrada ± (distancia_sl × rr)
    RR mínimo 1:2 por defecto.
    """
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
    """
    Retorna lista de zonas históricas que están entre la entrada y el TP.
    Solo informativo — no bloquea la señal.
    """
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
    Verifica si el precio está en una zona histórica válida
    Y hay un CHoCH M5 confirmado (cierre de vela).

    Retorna dict con:
      detectado:     True/False
      tipo:          'TIPO1'
      zona:          zona histórica donde ocurrió
      precio:        precio actual
      choch_nivel:   nivel del CHoCH
    """
    df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
    if df_m5 is None or len(df_m5) < 20:
        return {'detectado': False}

    precio_actual = df_m5['close'].iloc[-1]
    swings_m5     = detectar_swings(df_m5, ventana=3)

    if not swings_m5:
        return {'detectado': False}

    # Detectar CHoCH M5
    # Para GainX (compra): CHoCH alcista = rompe último SH con cierre
    # Para PainX (venta):  CHoCH bajista = rompe último SL con cierre
    choch = detectar_bos_choch(
        df_m5,
        swings_m5,
        tendencia='bajista' if not es_bajista else 'alcista'
        # Inversion intencional: buscamos el CHoCH contra la tendencia previa
        # que confirma el inicio del movimiento en nuestra dirección
    )

    if choch is None:
        return {'detectado': False}

    # El CHoCH debe ser en la dirección correcta
    dir_esperada = 'bajista' if es_bajista else 'alcista'
    if choch['direccion'] != dir_esperada:
        return {'detectado': False}

    # Verificar que el CHoCH es reciente (últimas 3 velas M5)
    idx_choch    = choch['idx']
    idx_ultima   = len(df_m5) - 1
    if (idx_ultima - idx_choch) > 3:
        return {'detectado': False}

    # Verificar que el precio está en una zona válida
    for zona in zonas_validas:
        precio_zona = zona['precio']
        tol_zona    = 50   # tolerancia para estar "en zona"

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
#  DETECCIÓN TIPO 2 — BOS en M15/M5 + retroceso a OB
# ============================================================

def _detectar_bos_retroceso(simbolo, es_bajista):
    """
    Verifica si:
    1. Hubo un BOS en M15 o M5
    2. El precio retrocedió al OB que generó ese BOS
    3. El precio llegó al OB

    Retorna dict con:
      detectado:  True/False
      tipo:       'TIPO2'
      tf_bos:     'M15' o 'M5'
      ob_high:    precio máximo del OB
      ob_low:     precio mínimo del OB
      precio:     precio actual
      bos_nivel:  nivel del BOS detectado
    """
    # Revisar primero M15 (más peso) luego M5
    for tf, velas, tf_nombre in [(TF_M15, VELAS_M15, 'M15'), (TF_M5, VELAS_M5, 'M5')]:
        try:
            df = obtener_df(simbolo, tf, velas)
            if df is None or len(df) < 20:
                continue

            precio_actual = df['close'].iloc[-1]
            swings        = detectar_swings(df, ventana=4 if tf == TF_M15 else 3)

            if not swings:
                continue

            # Detectar BOS estructural en la dirección correcta
            bos = detectar_bos_estructural(df, swings, es_bajista)

            if not bos['detectado']:
                continue

            # El BOS debe ser reciente (últimas 5 velas del TF)
            idx_bos    = bos['idx']
            idx_ultima = len(df) - 1
            if (idx_ultima - idx_bos) > 5:
                continue

            # Encontrar el OB que generó el BOS
            # Es la última vela contraria antes del impulso del BOS
            ob_high = None
            ob_low  = None

            for i in range(bos['idx'] - 1, max(0, bos['idx'] - 10), -1):
                c = df.iloc[i]
                if es_bajista:
                    # OB bajista: última vela alcista antes del impulso bajista
                    if c['close'] > c['open']:
                        ob_high = round(c['high'], 2)
                        ob_low  = round(c['low'],  2)
                        break
                else:
                    # OB alcista: última vela bajista antes del impulso alcista
                    if c['close'] < c['open']:
                        ob_high = round(c['high'], 2)
                        ob_low  = round(c['low'],  2)
                        break

            if ob_high is None:
                continue

            # Verificar que el precio retrocedió al OB
            if es_bajista:
                # Para venta: precio debe subir de vuelta al OB
                precio_en_ob = precio_actual >= ob_low and precio_actual <= ob_high
            else:
                # Para compra: precio debe bajar de vuelta al OB
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
                        sweep=None, pd_ctx=None):
    """
    Construye el mensaje de señal para Telegram.
    Formato limpio y consistente.
    v6: agrega contexto de sweep y premium/discount.
    """
    icono  = '📉' if es_bajista else '📈'
    accion = 'VENTA' if es_bajista else 'COMPRA'

    if tipo_entrada == 'TIPO1_M1':
        tipo_txt = 'CHoCH M1 EN ZONA 🎯'
    elif tipo_entrada == 'TIPO1':
        tipo_txt = 'ZONA HISTÓRICA'
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

    # Info de zona (Tipo 1 / Tipo 1_M1)
    if zona:
        tf_zona   = '+'.join(zona.get('tfs', ['?']))
        lineas.append(
            f"🏛 Zona {tf_zona}: {zona['precio']:.0f} | "
            f"{zona['fuerza_txt']} | {zona.get('n_toques',0)} toques"
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
    Analiza un símbolo completo:
    1. Actualiza zonas históricas si hace falta
    2. Evalúa alertas visuales (⚠️ 🔥 🎯)
    3. v6: evalúa sweep, premium/discount, CHoCH M1
    4. Detecta entrada Tipo 1_M1 (CHoCH M1 en zona + sweep)
    5. Detecta entrada Tipo 1 (CHoCH M5 en zona)
    6. Detecta entrada Tipo 2 (BOS + retroceso OB)
    7. Si hay señal: calcula SL/TP y envía a Telegram

    Retorna dict con resultado del análisis.
    """
    es_bajista = simbolo in SIMBOLOS_BAJISTAS

    # ── 1. Actualizar zonas históricas ──────────────────
    actualizar_zonas(simbolo, es_bajista)

    # ── 2. Obtener zonas válidas ─────────────────────────
    # Zona válida: 2+ toques, score >= 3, activa (dentro de rango)
    todas_zonas = obtener_niveles(simbolo, solo_activas=True, min_fuerza=1)
    zonas_validas = [
        z for z in todas_zonas
        if z.get('n_toques', 0) >= TOQUES_MINIMOS
        and z.get('score', 0) >= SCORE_ZONA_MIN
    ]

    # ── 3. Obtener precio actual ─────────────────────────
    df_m5 = obtener_df(simbolo, TF_M5, VELAS_M5)
    if df_m5 is None or len(df_m5) < 5:
        return {'simbolo': simbolo, 'resultado': 'SIN_DATOS'}

    precio_actual = df_m5['close'].iloc[-1]

    # ── 4. Evaluar alertas visuales ──────────────────────
    for zona in zonas_validas:
        alerta = evaluar_alerta(simbolo, precio_actual, zona, es_bajista)
        msg_consola = resumen_alerta_consola(alerta)
        if msg_consola:
            print(msg_consola)

        # Enviar alerta nivel 2-3 a Telegram (sin cooldown de señal)
        if alerta['activa'] and alerta['nivel'] >= 2:
            clave_alerta = f"alerta_v5_{simbolo}_{int(zona['precio'])}"
            if puede_enviar(clave_alerta, 3600):  # cooldown 60 min
                msg_tg = resumen_alerta_telegram(simbolo, alerta, es_bajista)
                if msg_tg:
                    enviar_telegram(msg_tg)
                    registrar_envio(clave_alerta)

    # ── 5. v6: Módulos de contexto institucional ─────────
    sweep    = verificar_sweep(simbolo, es_bajista)
    pd_ctx   = verificar_premium_discount(simbolo, precio_actual, es_bajista)
    choch_m1 = verificar_choch_m1(simbolo, precio_actual, es_bajista, zonas_validas)

    # Mostrar en consola (informativo — siempre)
    if sweep['hubo_sweep']:
        print(f"  {sweep['descripcion']}")
    print(f"  {pd_ctx['descripcion']}")
    if choch_m1['en_zona']:
        print(f"  {choch_m1['descripcion']}")

    # ── 6. Verificar cooldown de señal ───────────────────
    clave_señal = _clave_señal(simbolo)
    if not puede_enviar(clave_señal, COOLDOWN_SEÑAL):
        mins = tiempo_restante_cooldown(clave_señal, COOLDOWN_SEÑAL) // 60
        print(f"  ⏳ COOLDOWN | {simbolo} | faltan {mins}m")
        return {'simbolo': simbolo, 'resultado': 'COOLDOWN', 'precio': precio_actual}

    # ── 7. Señal TIPO1_M1 — CHoCH M1 en zona + sweep ─────
    #        Prioridad máxima: entrada más precisa que M5
    if choch_m1['detectado'] and sweep['hubo_sweep'] and pd_ctx.get('valid', True):
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
                tf_bos=None,
                resistencias_camino=res_camino if res_camino else None,
                sweep=sweep,
                pd_ctx=pd_ctx,
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

    # ── 8. Detectar señal Tipo 1 (CHoCH M5) ─────────────
    señal = _detectar_choch_en_zona(simbolo, es_bajista, zonas_validas)

    # ── 9. Si no hay Tipo 1, intentar Tipo 2 ─────────────
    if not señal['detectado']:
        señal = _detectar_bos_retroceso(simbolo, es_bajista)

    # ── 10. Sin señal → salir ────────────────────────────
    if not señal['detectado']:
        return {'simbolo': simbolo, 'resultado': 'SIN_SEÑAL', 'precio': precio_actual}

    # ── 11. Calcular SL y TP ─────────────────────────────
    precio_entrada = señal['precio']
    sl = _calcular_sl(df_m5, precio_entrada, es_bajista, simbolo)
    tps = _calcular_tp(precio_entrada, sl, es_bajista)

    # Verificar RR mínimo
    if tps['rr'] < RR_MINIMO:
        print(
            f"  ⛔ RR insuficiente | {simbolo} | "
            f"RR={tps['rr']} < {RR_MINIMO}"
        )
        return {'simbolo': simbolo, 'resultado': 'RR_INSUFICIENTE', 'precio': precio_actual}

    # ── 12. Resistencias en el camino (informativo) ──────
    res_camino = _resistencias_en_camino(
        simbolo, precio_entrada, tps['tp1'], es_bajista
    )

    # ── 13. Construir y enviar señal ─────────────────────
    zona_señal = señal.get('zona', None)
    tf_bos     = señal.get('tf_bos', None)

    msg = _construir_mensaje(
        simbolo      = simbolo,
        es_bajista   = es_bajista,
        precio       = precio_entrada,
        sl           = sl,
        tps          = tps,
        tipo_entrada = señal['tipo'],
        zona         = zona_señal,
        tf_bos       = tf_bos,
        resistencias_camino = res_camino if res_camino else None,
        sweep        = sweep,
        pd_ctx       = pd_ctx,
    )

    print(f"  ✅ SEÑAL {señal['tipo']} | {simbolo} | {'VENTA' if es_bajista else 'COMPRA'} | entrada={precio_entrada:.0f} SL={sl:.0f} TP1={tps['tp1']:.0f}")
    enviar_telegram(msg)
    registrar_envio(clave_señal)

    registrar_trade(
        simbolo        = simbolo,
        es_bajista     = es_bajista,
        precio_entrada = precio_entrada,
        sl             = sl,
        tp1            = tps['tp1'],
        tp2            = tps['tp2'],
        score_poi      = 0,
        trigger        = señal['tipo'],
    )

    return {
        'simbolo':   simbolo,
        'resultado': 'SEÑAL',
        'tipo':      señal['tipo'],
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
    print(f"  ║  DIEFERT SCANNER v5+v6   {hora}  ")
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
    print("\n  🚀 Iniciando Diefert Scanner v5+v6...")

    # Limpiar trades del día anterior (CONSERVANDO encabezados)
    # FIX v5.1: antes se vaciaba el archivo completo, borrando también
    # la fila de encabezados → causaba KeyError: 'fecha' al reiniciar.
    # Ahora se reescribe dejando solo la fila de encabezados.
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

    # Detectar broker y mostrar info de cuenta
    broker = detectar_y_configurar(mt5)
    info   = mt5.account_info()
    if info:
        print(f"  ✅ MT5 conectado | Cuenta: {info.login} | Broker: {broker.upper()} | Balance: ${info.balance:.2f}")
    else:
        print(f"  ✅ MT5 conectado | Broker: {broker.upper()}")

    print(f"  📡 Ciclo: {CICLO_SEG}s | Cooldown señal: {COOLDOWN_SEÑAL//60}min | RR mínimo: {RR_MINIMO}")
    print(f"  📊 Símbolos: {len(SIMBOLOS)} activos")
    print(f"  🆕 Módulos v6: sweep + P/D filter + CHoCH M1")
    print(f"  ─────────────────────────────────────────────")
    print(f"  ✅ Iniciando escaneo — zonas se calculan en el primer ciclo\n")

    ciclo = 0

    try:
        while True:
            ciclo += 1
            hora  = datetime.now().strftime('%H:%M:%S')
            resultados = []

            for simbolo in SIMBOLOS:
                try:
                    r = analizar_simbolo(simbolo)
                    resultados.append(r)
                except Exception as e:
                    print(f"  ❌ Error en {simbolo}: {e}")
                    resultados.append({'simbolo': simbolo, 'resultado': 'ERROR'})

            # Panel cada 10 ciclos
            if ciclo % 10 == 0:
                _imprimir_panel(resultados, hora)
                print(resumen_dia())

            # Verificar trades activos
            verificar_trades()

            # Escuchar comandos Telegram (/analisis GainX 600)
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
