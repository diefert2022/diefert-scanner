# ============================================================
#  test_harmonico_visual.py
#  Diefert Scanner — PRUEBA MANUAL de harmonicos_v1.py
#
#  Qué hace:
#  ─────────────────────────────────────────────────────────
#  Toma los últimos 5 swings REALES del símbolo elegido
#  (mismos datos que usaría el scanner en vivo), los etiqueta
#  como X-A-B-C-D y FUERZA el envío de una señal de prueba:
#    1. Manda el mensaje a Telegram (canal Señales Weltrade Diefert)
#    2. Escribe el archivo harmonico_<SIMBOLO>.txt para que
#       HarmonicVisualizer.mq5 lo lea y dibuje en el gráfico
#
#  No pasa por el filtro de ratios Fibonacci/PCI — es solo
#  para confirmar que la TUBERÍA completa funciona (Telegram
#  + archivo + dibujo), no que el patrón sea válido.
#
#  Ejecutar UNA VEZ con MT5 abierto (puede estar el scanner
#  corriendo también, no hay conflicto — solo lee datos).
#
#  Uso:
#    python test_harmonico_visual.py
#  (edita SIMBOLO_PRUEBA abajo si quieres probar otro índice)
# ============================================================

import time
import MetaTrader5 as mt5

from config import TF_M15, VELAS_M15
from utils import obtener_df, enviar_telegram
from estructura import detectar_swings
from harmonicos_v1 import (
    _limpiar_swings_alternados,
    _escribir_visual_mt5,
    _epoch,
    VENTANA_SWING,
)

# ── EDITA ESTO PARA PROBAR OTRO SÍMBOLO ───────────────────
SIMBOLO_PRUEBA = "PainX 1200"


def enviar_prueba(simbolo):
    print(f"\n🧪 Probando patrón armónico en {simbolo}...")

    df = obtener_df(simbolo, TF_M15, VELAS_M15)
    if df is None or len(df) < 30:
        print("❌ No se pudieron obtener velas — ¿MT5 conectado y símbolo correcto?")
        return

    precio_actual = df['close'].iloc[-1]

    swings = detectar_swings(df, ventana=VENTANA_SWING)
    swings = _limpiar_swings_alternados(swings)

    if len(swings) < 5:
        print(f"❌ Solo hay {len(swings)} swings limpios — necesita al menos 5. Prueba otro símbolo.")
        return

    ultimos5 = swings[-5:]
    d_tipo = ultimos5[-1]['tipo']
    direccion = 'alcista' if d_tipo == 'SL' else 'bajista'

    # ── Mensaje de Telegram (formato igual al real, marcado como PRUEBA) ──
    icono = '📉' if direccion == 'bajista' else '📈'
    d_precio = ultimos5[-1]['precio']
    mensaje = (
        f"🧪 <b>PRUEBA — PATRÓN ARMÓNICO | {simbolo}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{icono} Esto es solo un test de la tubería completa\n"
        f"📍 Punto D (real, de tus últimos swings): <b>{d_precio:.0f}</b>\n"
        f"💹 Precio actual: {precio_actual:.0f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Si ves este mensaje → Telegram funciona\n"
        f"✅ Revisa el gráfico → deberías ver líneas X-A-B-C-D + zona dorada\n"
        f"⏰ {time.strftime('%H:%M:%S')}"
    )

    print("📤 Enviando a Telegram...")
    enviar_telegram(mensaje)

    # ── Archivo para MT5 (mismo formato que usa harmonicos_v1.py) ──
    puntos = {
        etiqueta: {'precio': s['precio'], 'time': _epoch(df, s['idx'])}
        for etiqueta, s in zip(['X', 'A', 'B', 'C', 'D'], ultimos5)
    }

    print("🖊️  Escribiendo archivo para MT5...")
    _escribir_visual_mt5(simbolo, "Gartley (PRUEBA)", direccion, puntos, int(time.time()))

    print("\n✅ Listo. Revisa:")
    print("   1. Tu Telegram — debería llegar el mensaje de prueba en unos segundos")
    print("   2. El gráfico en MT5 — el indicador lee el archivo cada 20s (según POLL_SEGUNDOS)")
    print("      así que puede tardar hasta 20s en aparecer el dibujo")


if __name__ == "__main__":
    if not mt5.initialize():
        print(f"❌ MT5 no conectado: {mt5.last_error()}")
    else:
        enviar_prueba(SIMBOLO_PRUEBA)
        mt5.shutdown()
