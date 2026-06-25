# ============================================================
#  test_emascalpd.py — Prueba rápida del módulo EmaScalpD
#  Corre desde CMD: python test_emascalpd.py
# ============================================================

import MetaTrader5 as mt5
from broker import detectar_y_configurar
from utils import obtener_df
from config import TF_M5
from emascalpd_v1 import analizar_emascalpd, _calcular_emas, _es_armonico, EMASCALPD_CHAT_ID, EMASCALPD_THREAD_ID, _enviar_emascalpd

SIMBOLO = "FlipX 1"

print("\n  🧪 TEST EmaScalpD")
print("  ─────────────────────────────────────────")

# ── Conectar MT5 ──────────────────────────────────────────
if not mt5.initialize():
    print(f"  ❌ No se pudo conectar MT5: {mt5.last_error()}")
    exit()

broker = detectar_y_configurar(mt5)
info   = mt5.account_info()
print(f"  ✅ MT5 conectado | Cuenta: {info.login} | Broker: {broker.upper()}")

# ── Obtener velas M5 ──────────────────────────────────────
df = obtener_df(SIMBOLO, TF_M5, 300)
if df is None or len(df) < 210:
    print(f"  ❌ No se obtuvieron velas de {SIMBOLO}")
    mt5.shutdown()
    exit()

print(f"  ✅ Velas M5 obtenidas: {len(df)} velas")

precio = df['close'].iloc[-1]
print(f"  💰 Precio actual: {precio:.2f}")

# ── Calcular EMAs ─────────────────────────────────────────
emas = _calcular_emas(df)
print(f"\n  📊 EMAs actuales:")
print(f"     EMA 30:  {emas[30]:.2f}")
print(f"     EMA 50:  {emas[50]:.2f}")
print(f"     EMA 100: {emas[100]:.2f}")
print(f"     EMA 200: {emas[200]:.2f}")

# ── Verificar filtro armónico ─────────────────────────────
armonico_alcista = _es_armonico(precio, emas, 'ALCISTA')
armonico_bajista = _es_armonico(precio, emas, 'BAJISTA')
print(f"\n  🔍 Filtro armónico:")
print(f"     ALCISTA: {'✅' if armonico_alcista else '❌'}")
print(f"     BAJISTA: {'✅' if armonico_bajista else '❌'}")

# ── Verificar canal Telegram ──────────────────────────────
print(f"\n  📡 Probando canal Telegram EmaScalpD...")
print(f"     chat_id: {EMASCALPD_CHAT_ID}")
print(f"     thread_id: {EMASCALPD_THREAD_ID}")

_enviar_emascalpd(
    "🧪 <b>TEST EmaScalpD</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    f"✅ Conexión exitosa\n"
    f"📊 FlipX 1 — precio: {precio:.2f}\n"
    f"📈 EMA30: {emas[30]:.1f} | EMA200: {emas[200]:.1f}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Módulo EmaScalpD funcionando correctamente"
)

# ── Correr análisis real ──────────────────────────────────
print(f"\n  🔄 Corriendo analizar_emascalpd()...")
analizar_emascalpd(SIMBOLO, df)

print(f"\n  ✅ Test completado. Revisa el tópico EmaScalpD en Telegram.")
print(f"  ─────────────────────────────────────────\n")

mt5.shutdown()
