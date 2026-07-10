import MetaTrader5 as mt5
import sys
sys.path.insert(0, r'F:\clude\diefert_scanner_v5')

mt5.initialize()

from utils import obtener_df
from config import TF_M5

df = obtener_df('FlipX 2', TF_M5, 300)
close = df['close']

ema100s = close.ewm(span=100, adjust=False).mean()
ema200s = close.ewm(span=200, adjust=False).mean()

# Buscar cruce
idx_cruce = None
direccion = None
for i in range(len(df)-1, 0, -1):
    if ema100s.iloc[i-1] >= ema200s.iloc[i-1] and ema100s.iloc[i] < ema200s.iloc[i]:
        idx_cruce = i
        direccion = 'BAJISTA'
        break
    if ema100s.iloc[i-1] <= ema200s.iloc[i-1] and ema100s.iloc[i] > ema200s.iloc[i]:
        idx_cruce = i
        direccion = 'ALCISTA'
        break

print(f"Cruce: {direccion} en índice {idx_cruce}")

# Calcular swing con la nueva lógica
lows  = df['low'].values
highs = df['high'].values
n     = len(df)

rango_lows  = lows[idx_cruce:n-1]
rango_highs = highs[idx_cruce:n-1]

if direccion == 'BAJISTA':
    swing = float(rango_lows.min())
else:
    swing = float(rango_highs.max())

print(f"Swing calculado: {swing:.2f}")
print(f"Tu Low correcto: 107571.00")
print(f"Coincide: {abs(swing - 107571) < 5}")

# También escribir el archivo para ver en MT5
import os
MT5_FILES = (
    r"C:\Users\Pc-Trabajo\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
)
ruta = os.path.join(MT5_FILES, "swing_debug.txt")
tipo = 'HIGH' if direccion == 'ALCISTA' else 'LOW'
linea = f"FlipX 2,{direccion},{tipo},{swing:.2f}"
with open(ruta, "w") as f:
    f.write(linea)
print(f"\nEscrito en MT5: {linea}")
print("Espera 30s y revisa el gráfico")

mt5.shutdown()
input("\nPresiona Enter para cerrar...")
