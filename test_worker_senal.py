"""
╔══════════════════════════════════════════════════════════╗
║   DIEFERT — TEST DE SEÑAL AL WORKER                     ║
║   Envía una señal de prueba al Cloudflare Worker        ║
║   para verificar que el EA la recibe y dibuja           ║
╚══════════════════════════════════════════════════════════╝

USO:
  1. Abre esta carpeta en terminal/cmd
  2. Ejecuta: python test_worker_senal.py
  3. Observa el gráfico del EA — debe dibujar las líneas y sonar

REQUISITO EN MT5:
  Herramientas → Opciones → Expert Advisors
  ✅ Permitir WebRequest para:
     https://diefert-senales.diefert2022.workers.dev
"""

import urllib.request
import urllib.error
import json
import time

# ── CONFIGURACIÓN ─────────────────────────────────────────────────
WORKER_URL = "https://diefert-senales.diefert2022.workers.dev"

# ── SEÑAL DE PRUEBA ───────────────────────────────────────────────
# Cambia "entrada" y "sl" al precio actual de tu GainX en MT5
SENAL = {
    "id":      int(time.time()),
    "simbolo": "GainX 400",
    "dir":     "LONG",
    "entrada": 110350.0,    # ← cambia al precio actual del GainX 400
    "sl":      110150.0,    # ← 200 pts abajo de la entrada
    "tp1":     110550.0,
    "tp2":     110750.0,
    "score":   78,
}

# ─────────────────────────────────────────────────────────────────

def enviar_senal(senal):
    print("=" * 55)
    print("  DIEFERT — TEST DE SEÑAL AL WORKER")
    print("=" * 55)
    print(f"\n  Simbolo  : {senal['simbolo']}")
    print(f"  Direccion: {senal['dir']}")
    print(f"  Entrada  : {senal['entrada']}")
    print(f"  SL       : {senal['sl']}")
    print(f"  TP1      : {senal['tp1']}")
    print(f"  ID       : {senal['id']}")
    print(f"\n  Enviando al Worker...")

    try:
        payload = json.dumps(senal).encode("utf-8")
        req = urllib.request.Request(
            WORKER_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent":   "DiefertTest/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp   = r.read().decode("utf-8").strip()
            status = r.status

        print(f"\n  OK Worker respondio ({status}): {resp}")
        print(f"\n  Espera hasta 5 segundos...")
        print(f"  El EA debe dibujar las lineas y sonar en MT5.")

    except urllib.error.URLError as e:
        print(f"\n  ERROR de conexion: {e.reason}")
        print(f"  Verifica tu conexion a internet.")
    except Exception as e:
        print(f"\n  ERROR inesperado: {e}")

    print("\n" + "=" * 55)


def verificar_worker():
    print("\n  Verificando senal almacenada en el Worker...")
    try:
        req = urllib.request.Request(
            WORKER_URL,
            headers={"User-Agent": "DiefertTest/1.0"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = r.read().decode("utf-8").strip()
        data = json.loads(resp)
        print(f"\n  Senal en el Worker:")
        for k, v in data.items():
            print(f"     {k}: {v}")
    except Exception as e:
        print(f"  ERROR al verificar: {e}")


if __name__ == "__main__":
    enviar_senal(SENAL)
    time.sleep(1)
    verificar_worker()
    print("\n  Presiona Enter para salir...")
    input()
