"""
evaluar_senales.py — v3
========================
Dos análisis por señal:
1. Estado actual (precio en vivo vs entrada)
2. Reacción histórica (¿el precio reaccionó antes de tocar SL?)

Offset horario: CSV usa hora Colombia (UTC-5 aprox),
MT5 usa UTC → diferencia = +8 horas al timestamp del CSV.
"""
import MetaTrader5 as mt5
import sys, json
import pandas as pd
from datetime import datetime, timezone, timedelta

sys.path.insert(0, r'F:\clude\diefert_scanner_v5')
from broker import nombre_real, detectar_y_configurar

CSV_PATH   = r'F:\clude\diefert_scanner_v5\trades_log.csv'
OUTPUT     = r'F:\clude\diefert_scanner_v5\resultado_evaluacion.json'
UTC_OFFSET = 8   # horas a sumar para convertir hora CSV → UTC


def velas_desde_senal(simbolo_mt5, fecha, hora):
    """Obtiene velas M5 desde la hora de la señal hasta ahora."""
    try:
        dt       = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S")
        # Colombia = UTC-5, servidor MT5 = UTC+3 aprox → diferencia = +8
        dt_utc   = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
                           tzinfo=timezone.utc) + timedelta(hours=UTC_OFFSET)
        dt_hasta = datetime.now(tz=timezone.utc) + timedelta(hours=12)
        rates    = mt5.copy_rates_range(simbolo_mt5, mt5.TIMEFRAME_M5, dt_utc, dt_hasta)
        if rates is None or len(rates) == 0:
            return None
        return pd.DataFrame(rates)
    except Exception as e:
        print(f"    Error velas: {e}")
        return None


def analizar_reaccion(df, entrada, sl, tp1, direccion):
    """
    Busca primero cuándo el precio tocó la entrada.
    Desde ESA vela mide si hubo reacción a favor antes del SL.
    Si nunca tocó la entrada → señal no activada.
    """
    highs  = df['high'].values
    lows   = df['low'].values
    closes = df['close'].values

    sl_dist  = abs(sl - entrada)
    tp1_dist = abs(tp1 - entrada)

    # ── Paso 1: encontrar cuándo tocó la entrada ──────────
    vela_entrada = None
    for i in range(len(df)):
        if direccion == 'LONG' and lows[i] <= entrada:
            vela_entrada = i
            break
        elif direccion == 'SHORT' and highs[i] >= entrada:
            vela_entrada = i
            break

    if vela_entrada is None:
        return {
            'resultado'    : 'NO ACTIVADA',
            'reacciono'    : False,
            'primer_favor' : 0,
            'max_favor'    : 0,
            'max_contra'   : 0,
            'toco_sl'      : False,
            'toco_tp1'     : False,
            'salio'        : False,
            'vela_entrada' : None,
        }

    # ── Paso 2: desde la vela de entrada medir reacción ──
    primer_favor = 0
    max_favor    = 0
    max_contra   = 0
    toco_sl      = False
    toco_tp1     = False
    salio        = False
    fase         = 'INICIO'

    for i in range(vela_entrada, len(df)):
        h, l, c = highs[i], lows[i], closes[i]

        if direccion == 'LONG':
            favor  = max(0, h - entrada)
            contra = max(0, entrada - l)
            if c > entrada: salio = True
            if h >= tp1:
                toco_tp1 = True
                max_favor = max(max_favor, min(favor, tp1_dist))
                break
            if l <= sl:
                toco_sl = True
                max_contra = sl_dist
                break
        else:
            favor  = max(0, entrada - l)
            contra = max(0, h - entrada)
            if c < entrada: salio = True
            if l <= tp1:
                toco_tp1 = True
                max_favor = max(max_favor, min(favor, tp1_dist))
                break
            if h >= sl:
                toco_sl = True
                max_contra = sl_dist
                break

        max_favor  = max(max_favor,  favor)
        max_contra = max(max_contra, contra)

    reacciono = max_favor >= 1

    if toco_tp1:   resultado = 'WIN TP1'
    elif toco_sl:  resultado = 'LOSS SL'
    elif salio:    resultado = 'POSITIVO'
    else:          resultado = 'ACTIVO'

    return {
        'resultado'    : resultado,
        'reacciono'    : reacciono,
        'primer_favor' : round(primer_favor, 1),
        'max_favor'    : round(max_favor, 1),
        'max_contra'   : round(max_contra, 1),
        'toco_sl'      : toco_sl,
        'toco_tp1'     : toco_tp1,
        'salio'        : salio,
        'vela_entrada' : int(vela_entrada),
    }


def evaluar_senal(row):
    simbolo   = row['simbolo']
    direccion = row['direccion']
    entrada   = float(row['entrada'])
    sl        = float(row['sl'])
    tp1       = float(row['tp1'])
    simbolo_mt5 = nombre_real(simbolo)

    # Estado actual en vivo
    tick = mt5.symbol_info_tick(simbolo_mt5)
    precio_actual = tick.bid if tick else None
    if precio_actual:
        pts_ahora = (precio_actual - entrada) if direccion == 'LONG' else (entrada - precio_actual)
    else:
        pts_ahora = None

    # Análisis histórico desde la señal
    df_velas = velas_desde_senal(simbolo_mt5, row['fecha'], row['hora'])
    if df_velas is not None and len(df_velas) > 2:
        hist = analizar_reaccion(df_velas, entrada, sl, tp1, direccion)
    else:
        hist = None

    return {
        'simbolo'      : simbolo,
        'direccion'    : direccion,
        'hora'         : row['hora'],
        'entrada'      : entrada,
        'sl'           : sl,
        'sl_dist'      : round(abs(sl - entrada), 2),
        'tp1_dist'     : round(abs(tp1 - entrada), 2),
        'precio_actual': round(precio_actual, 2) if precio_actual else None,
        'pts_ahora'    : round(pts_ahora, 1) if pts_ahora is not None else None,
        'hist'         : hist,
    }


def main():
    print("=== EVALUADOR DE SEÑALES DIEFERT v3 ===\n")
    if not mt5.initialize():
        print("No se pudo conectar a MT5")
        return
    detectar_y_configurar(mt5)

    df = pd.read_csv(CSV_PATH)
    activas = df[df['estado'] == 'ACTIVO'].copy()
    print(f"Señales ACTIVAS: {len(activas)}\n")

    resultados = []
    for _, row in activas.iterrows():
        print(f"  {row['simbolo']} {row['direccion']} @ {row['entrada']} ({row['hora']})")
        r = evaluar_senal(row)
        resultados.append(r)

        # Estado actual
        if r['pts_ahora'] is not None:
            signo = '+' if r['pts_ahora'] >= 0 else ''
            print(f"    Ahora  : {r['precio_actual']} | {signo}{r['pts_ahora']} pts")

        # Reacción histórica
        h = r['hist']
        if h:
            if h['resultado'] == 'NO ACTIVADA':
                print(f"    Reacción: ⚪ NO ACTIVADA — precio nunca tocó la entrada")
            else:
                reac = '✅ SÍ reaccionó' if h['reacciono'] else '❌ NO reaccionó'
                print(f"    Reacción: {reac} | max favor={h['max_favor']}pts | max contra={h['max_contra']}pts | resultado={h['resultado']}")
        else:
            print(f"    Reacción: sin datos históricos")
        print()

    # Resumen
    print("="*50)
    reaccionaron = [r for r in resultados if r['hist'] and r['hist']['reacciono']]
    no_reaccionaron = [r for r in resultados if r['hist'] and not r['hist']['reacciono']]
    wins = [r for r in resultados if r['hist'] and r['hist']['resultado'] == 'WIN TP1']
    print(f"Total señales      : {len(resultados)}")
    print(f"Reaccionaron       : {len(reaccionaron)} ({round(len(reaccionaron)/len(resultados)*100 if resultados else 0, 1)}%)")
    print(f"No reaccionaron    : {len(no_reaccionaron)}")
    print(f"WIN TP1            : {len(wins)}")

    with open(OUTPUT, 'w') as f:
        json.dump([{**r, 'hist': r['hist']} for r in resultados], f, indent=2, default=str)

    print(f"\nGuardado: {OUTPUT}")
    mt5.shutdown()
    input("\nPresiona Enter para cerrar...")

if __name__ == '__main__':
    main()
