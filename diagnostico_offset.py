import MetaTrader5 as mt5
import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, r'F:\clude\diefert_scanner_v5')
mt5.initialize()

simbolo  = "PainX 400"
fecha    = "2026-06-26"
hora     = "17:32:53"
entrada  = 86844.26

# Probar diferentes offsets
for offset in [0, 5, 6, 7, 8]:
    dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S")
    dt_utc = dt.replace(tzinfo=timezone.utc) + timedelta(hours=offset)
    rates = mt5.copy_rates_from(simbolo, mt5.TIMEFRAME_M5, dt_utc, 5)
    if rates is None:
        print(f"Offset +{offset}h → sin datos")
        continue
    print(f"\nOffset +{offset}h → primera vela: {datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc).strftime('%d %H:%M')} UTC")
    for r in rates[:3]:
        t = datetime.fromtimestamp(r['time'], tz=timezone.utc).strftime('%H:%M')
        toco = "← ENTRADA" if r['low'] <= entrada <= r['high'] else ""
        print(f"  {t} | H={r['high']} L={r['low']} C={r['close']} {toco}")

mt5.shutdown()
input("\nPresiona Enter...")
