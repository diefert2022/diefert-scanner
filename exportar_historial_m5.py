# ============================================================
#  exportar_historial_m5.py
#  Exporta velas M5 desde MT5 a un CSV para el backtester
#  de EmaScalpD.
#
#  Requisitos: MetaTrader5 abierto y logueado en tu broker.
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# ── CONFIGURA AQUÍ ──────────────────────────────────────────
SIMBOLO    = "FlipX 2"     # cambia por el símbolo que quieras probar
DIAS_ATRAS = 45            # ~45 días calendario = ~1 mes de trading + warm-up
ARCHIVO_SALIDA = f"historial_{SIMBOLO.replace(' ', '_')}_M5.csv"
# ─────────────────────────────────────────────────────────────

print("Conectando a MT5...")
if not mt5.initialize():
    print("ERROR: Abre MetaTrader 5 primero y vuelve a correr el script.")
    quit()

print(f"Conexión exitosa. Descargando {SIMBOLO} M5, últimos {DIAS_ATRAS} días...")

fecha_fin    = datetime.now()
fecha_inicio = fecha_fin - timedelta(days=DIAS_ATRAS)

velas = mt5.copy_rates_range(SIMBOLO, mt5.TIMEFRAME_M5, fecha_inicio, fecha_fin)

if velas is None or len(velas) == 0:
    print(f"ERROR: No se pudo descargar historial de {SIMBOLO}.")
    print("Verifica que el símbolo esté visible en Market Watch de MT5.")
    mt5.shutdown()
    quit()

df = pd.DataFrame(velas)
df["time"] = pd.to_datetime(df["time"], unit="s")
df = df[["time", "open", "high", "low", "close", "tick_volume"]]

df.to_csv(ARCHIVO_SALIDA, index=False)

print(f"✅ Listo. {len(df)} velas guardadas en: {ARCHIVO_SALIDA}")
print(f"   Rango: {df['time'].iloc[0]} → {df['time'].iloc[-1]}")
print()
print("Sube ese archivo CSV al chat para que armemos el backtest visual.")

mt5.shutdown()
