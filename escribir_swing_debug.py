"""
escribir_swing_debug.py
========================
Agrega esto al final de analizar_emascalpd() en emascalpd_v1.py,
dentro del bloque donde se detecta el swing (FASE 2).

O también puedes llamarlo directamente desde main_v5.py
después de analizar FlipX 2.

El archivo swing_debug.txt se escribe en la carpeta Files de MT5:
C:\\Users\\Pc-Trabajo\\AppData\\Roaming\\MetaQuotes\\Terminal\\
D0E8209F77C8CF37AD8BF550E51FF075\\MQL5\\Files\\swing_debug.txt
"""

import os

# ── RUTA CARPETA FILES DE MT5 ─────────────────────────────────────
MT5_FILES = (
    r"C:\Users\Pc-Trabajo\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
)

def escribir_swing_debug(simbolo: str, tendencia: str,
                          tipo: str, precio: float):
    """
    Escribe el swing activo en swing_debug.txt para que
    el MicroGrid EA lo lea y dibuje la línea en el gráfico.

    Parámetros:
        simbolo   : "FlipX 2"
        tendencia : "ALCISTA" o "BAJISTA"
        tipo      : "HIGH" o "LOW"
        precio    : valor del swing, ej. 12345.67
    """
    ruta = os.path.join(MT5_FILES, "swing_debug.txt")
    linea = f"{simbolo},{tendencia},{tipo},{precio:.2f}"

    try:
        with open(ruta, "w") as f:
            f.write(linea)
        print(f"  [SwingDebug] ✅ Escrito → {linea}")
    except Exception as e:
        print(f"  [SwingDebug] ❌ Error escribiendo archivo: {e}")


# ── CÓMO INTEGRARLO EN emascalpd_v1.py ───────────────────────────
#
# En la función analizar_emascalpd(), justo después de detectar
# el swing_mayor (cuando estado['swing_mayor'] se asigna),
# agrega esto:
#
#   from escribir_swing_debug import escribir_swing_debug
#
#   # Al detectar el swing por primera vez:
#   if estado['swing_mayor'] is not None:
#       tipo = 'HIGH' if direccion == 'ALCISTA' else 'LOW'
#       escribir_swing_debug(simbolo, direccion, tipo, estado['swing_mayor'])
#
#   # Al detectar BOS y actualizar swing:
#   if bos_nuevo:
#       tipo = 'HIGH' if direccion == 'ALCISTA' else 'LOW'
#       escribir_swing_debug(simbolo, direccion, tipo, estado['swing_mayor'])
#
# ─────────────────────────────────────────────────────────────────


# ── TEST MANUAL — ejecuta este archivo directamente para probar ──
if __name__ == "__main__":
    print("=== TEST escribir_swing_debug ===")
    print(f"Carpeta MT5 Files: {MT5_FILES}")
    print()

    # Simula que el scanner detectó este swing en FlipX 2
    escribir_swing_debug(
        simbolo   = "FlipX 2",
        tendencia = "ALCISTA",
        tipo      = "HIGH",
        precio    = 99999.50   # ← reemplaza con precio real de prueba
    )

    # Verificar que se escribió
    ruta = os.path.join(MT5_FILES, "swing_debug.txt")
    if os.path.exists(ruta):
        with open(ruta) as f:
            contenido = f.read()
        print(f"  Archivo creado: {ruta}")
        print(f"  Contenido: {contenido}")
        print()
        print("✅ Ahora abre MT5 → el MicroGrid EA leerá esto en el próximo OnTimer (30s)")
        print("   Verás una línea AZUL en el gráfico de FlipX 2 M5")
    else:
        print("❌ No se pudo crear el archivo — verifica la ruta MT5_FILES")
        print("   Puedes cambiarla manualmente arriba si tu ruta es diferente")
