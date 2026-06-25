# ============================================================
#  descargar_historico.py
#  Descarga CSV histórico de todos los índices desde MT5
#  Ejecutar con MT5 abierto y conectado
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import os

SIMBOLOS = [
    "GainX 400", "GainX 600", "GainX 800", "GainX 999", "GainX 1200",
    "PainX 400", "PainX 600", "PainX 800", "PainX 999", "PainX 1200",
]

CARPETA  = r"F:\clude\historico_csv"
MESES    = 3      # cuántos meses hacia atrás
TF       = mt5.TIMEFRAME_M5
TF_NOMBRE = "M5"

if not os.path.exists(CARPETA):
    os.makedirs(CARPETA)

if not mt5.initialize():
    print(f"❌ MT5 no conectado: {mt5.last_error()}")
    exit()

fecha_fin    = datetime.utcnow()
fecha_inicio = fecha_fin - timedelta(days=MESES * 30)

print(f"📥 Descargando {TF_NOMBRE} — {MESES} meses de historial")
print(f"   Desde: {fecha_inicio.strftime('%Y-%m-%d')}")
print(f"   Hasta: {fecha_fin.strftime('%Y-%m-%d')}\n")

for simbolo in SIMBOLOS:
    rates = mt5.copy_rates_range(simbolo, TF, fecha_inicio, fecha_fin)
    if rates is None or len(rates) == 0:
        print(f"  ❌ {simbolo}: sin datos")
        continue

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df[['time','open','high','low','close','tick_volume']]
    df.columns = ['fecha','open','high','low','close','volumen']

    nombre = simbolo.replace(" ", "_") + f"_{TF_NOMBRE}.csv"
    ruta   = os.path.join(CARPETA, nombre)
    df.to_csv(ruta, index=False)
    print(f"  ✅ {simbolo}: {len(df)} velas → {nombre}")

mt5.shutdown()
print(f"\n✅ Listo. Archivos guardados en: {CARPETA}")
