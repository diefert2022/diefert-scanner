# ============================================================
#  diagnostico_volumen.py
#  Diefert Scanner — diagnóstico de datos de volumen en MT5
#  Ejecutar UNA VEZ con MT5 conectado y scanner detenido.
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

SIMBOLOS = ["GainX 600", "PainX 400", "GainX 999"]

def diagnosticar(simbolo):
    print(f"\n{'='*60}")
    print(f"  SÍMBOLO: {simbolo}")
    print(f"{'='*60}")

    # 1. Velas M1 — tick_volume y real_volume
    rates = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M1, 0, 5)
    if rates is not None:
        df = pd.DataFrame(rates)
        print("\n✅ VELAS M1:")
        print(df[['time','open','high','low','close','tick_volume','real_volume']].to_string(index=False))
        tv = df['tick_volume'].sum()
        rv = df['real_volume'].sum()
        print(f"\n   tick_volume total: {tv} | real_volume total: {rv}")
        if rv == 0:
            print("   ⚠️  real_volume = 0 → MT5 no entrega volumen real (normal en sintéticos)")
        else:
            print("   ✅ real_volume disponible")
    else:
        print("❌ No se pudieron obtener velas M1")

    # 2. Ticks individuales — bid/ask separados
    ahora    = datetime.utcnow()
    hace_2min = ahora - timedelta(minutes=2)
    ticks = mt5.copy_ticks_range(simbolo, hace_2min, ahora, mt5.COPY_TICKS_ALL)
    if ticks is not None and len(ticks) > 0:
        df_t = pd.DataFrame(ticks)
        print(f"\n✅ TICKS (últimos 2 min): {len(ticks)} ticks")
        print(df_t[['time','bid','ask','last','volume','flags']].head(10).to_string(index=False))
        vol_total = df_t['volume'].sum()
        print(f"\n   volume total en ticks: {vol_total}")
        if vol_total == 0:
            print("   ⚠️  volume en ticks = 0")
        else:
            print("   ✅ volume en ticks disponible")
    else:
        print("\n⚠️  Ticks no disponibles (mercado cerrado o no soportado)")

    # 3. DOM (Depth of Market)
    dom = mt5.market_book_get(simbolo)
    if dom and len(dom) > 0:
        print(f"\n✅ DOM disponible: {len(dom)} niveles")
    else:
        print("\n⚠️  DOM no disponible (normal en sintéticos)")

    print()

if __name__ == "__main__":
    if not mt5.initialize():
        print(f"❌ MT5 no conectado: {mt5.last_error()}")
    else:
        print("🔍 DIAGNÓSTICO DE VOLUMEN EN MT5")
        print("Verifica qué datos están disponibles para absorción\n")
        for s in SIMBOLOS:
            diagnosticar(s)
        mt5.shutdown()
        print("✅ Diagnóstico completo.")
