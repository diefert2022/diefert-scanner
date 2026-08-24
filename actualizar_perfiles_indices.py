# ============================================================
#  actualizar_perfiles_indices.py
#  Diefert Scanner v5 — Actualización automática de perfiles
# ------------------------------------------------------------
#  QUÉ HACE (explicado paso a paso, porque estás aprendiendo):
#
#  1. Se conecta a tu MT5 (debe estar ABIERTO y conectado a
#     Weltrade antes de correr este script).
#  2. Para cada uno de los 10 índices (PainX/GainX 400-1200),
#     descarga velas D1, H4, H1 y M15 de los últimos N meses.
#  3. Calcula automáticamente, con datos REALES y actuales:
#       - sesgo direccional (% alcista vs % bajista)
#       - rango_diario   (P90 del rango D1 — como hacíamos a mano)
#       - rango_m15      (promedio del rango M15)
#       - ob_h4_min      (P85 del tamaño de cuerpo en H4)
#       - ob_h1_min      (P85 del tamaño de cuerpo en H1)
#       - fvg_bull_fuerte / fvg_bear_fuerte (promedio FVG M15)
#       - horas_activas_utc (top horas por rango promedio M15)
#       - rango_saturado (90% del rango_diario)
#       - sl_minimo      (promedio cuerpo H1 + buffer 10pts)
#  4. NO toca tu config.py directamente (para que puedas revisar
#     los valores antes de aplicarlos — así trabajábamos antes).
#     En vez de eso, genera un archivo nuevo:
#         perfiles_actualizados_<fecha>.py
#     con los bloques ya listos en el mismo formato que usa
#     INDICE_CONFIG en config.py, para copiar y pegar.
#  5. También imprime en pantalla una tabla comparativa rápida.
#
#  CÓMO USARLO:
#     1. Abre MT5 y asegúrate que esté conectado (ves precios
#        moviéndose en Market Watch).
#     2. Copia este archivo a la carpeta del scanner:
#        F:\DIEFERT EXTERNO\clude\diefert_scanner_v5\
#     3. Corre:
#        python actualizar_perfiles_indices.py
#     4. Revisa el archivo perfiles_actualizados_<fecha>.py que
#        se genera en la misma carpeta.
#     5. Cuando confirmes que los valores tienen sentido, me
#        pasas ese archivo (o los valores) y te reescribo el
#        config.py completo con los datos nuevos.
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── CONFIGURACIÓN ───────────────────────────────────────────
MESES_HISTORIAL = 3   # cuántos meses hacia atrás analizar

SIMBOLOS = [
    "PainX 400", "PainX 600", "PainX 800", "PainX 999", "PainX 1200",
    "GainX 400", "GainX 600", "GainX 800", "GainX 999", "GainX 1200",
]

# Símbolos que ya sabemos que son bajistas de fondo (para el reporte)
SIMBOLOS_BAJISTAS_CONOCIDOS = {"PainX 400", "PainX 600", "PainX 800", "PainX 999", "PainX 1200"}


# ── CONEXIÓN MT5 ─────────────────────────────────────────────
def conectar_mt5():
    if not mt5.initialize():
        print(f"❌ No se pudo conectar a MT5: {mt5.last_error()}")
        print("   Verifica que MT5 esté ABIERTO y con sesión iniciada.")
        exit()
    print("✅ Conectado a MT5\n")


def descargar_velas(simbolo, timeframe, dias):
    fecha_fin = datetime.utcnow()
    fecha_inicio = fecha_fin - timedelta(days=dias)
    rates = mt5.copy_rates_range(simbolo, timeframe, fecha_inicio, fecha_fin)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


# ── CÁLCULOS (misma lógica ya validada que usamos antes) ────
def calcular_bias(df):
    alcistas = (df["close"] > df["open"]).sum()
    bajistas = (df["close"] < df["open"]).sum()
    total = alcistas + bajistas
    pct_alcista = round(100 * alcistas / total, 1) if total else 0
    pct_bajista = round(100 * bajistas / total, 1) if total else 0
    if pct_alcista >= pct_bajista:
        return f"BULL {pct_alcista}%", pct_alcista, pct_bajista
    return f"BEAR {pct_bajista}%", pct_alcista, pct_bajista


def rango_diario_p90(df_d1):
    """P90 del rango (high-low) por vela diaria — como se calibró a mano antes."""
    rangos = (df_d1["high"] - df_d1["low"]).to_numpy()
    if len(rangos) == 0:
        return 0
    return int(round(np.percentile(rangos, 90)))


def rango_m15_promedio(df_m15):
    rangos = (df_m15["high"] - df_m15["low"]).to_numpy()
    if len(rangos) == 0:
        return 0
    return int(round(np.mean(rangos)))


def cuerpo_p85(df):
    """P85 del tamaño de cuerpo (|close-open|) — usado para OB_H4/OB_H1."""
    cuerpos = (df["close"] - df["open"]).abs().to_numpy()
    if len(cuerpos) == 0:
        return 0
    return int(round(np.percentile(cuerpos, 85)))


def cuerpo_promedio(df):
    cuerpos = (df["close"] - df["open"]).abs().to_numpy()
    if len(cuerpos) == 0:
        return 0
    return round(float(np.mean(cuerpos)), 2)


def detectar_fvg(df):
    """FVG de 3 velas estándar SMC (igual que profile_painx1200.py)."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    fvg_bull, fvg_bear = [], []
    for i in range(len(df) - 2):
        v1_high, v1_low = highs[i], lows[i]
        v3_high, v3_low = highs[i + 2], lows[i + 2]
        if v3_low > v1_high:
            fvg_bull.append(v3_low - v1_high)
        elif v3_high < v1_low:
            fvg_bear.append(v1_low - v3_high)
    prom_bull = int(round(np.mean(fvg_bull))) if fvg_bull else 0
    prom_bear = int(round(np.mean(fvg_bear))) if fvg_bear else 0
    return prom_bull, prom_bear


def horas_activas(df_m15, top_n=8):
    """Top N horas UTC con mayor rango promedio en M15."""
    df = df_m15.copy()
    df["hora"] = df["time"].dt.hour
    df["rango"] = df["high"] - df["low"]
    promedio = df.groupby("hora")["rango"].mean().sort_values(ascending=False)
    return sorted(promedio.head(top_n).index.tolist())


# ── PROCESAR UN SÍMBOLO COMPLETO ─────────────────────────────
def perfilar_simbolo(simbolo, dias):
    print(f"📊 Analizando {simbolo} ...")

    df_d1  = descargar_velas(simbolo, mt5.TIMEFRAME_D1,  dias)
    df_h4  = descargar_velas(simbolo, mt5.TIMEFRAME_H4,  dias)
    df_h1  = descargar_velas(simbolo, mt5.TIMEFRAME_H1,  dias)
    df_m15 = descargar_velas(simbolo, mt5.TIMEFRAME_M15, dias)

    if any(d is None for d in [df_d1, df_h4, df_h1, df_m15]):
        print(f"  ❌ {simbolo}: no se pudieron descargar todas las temporalidades (revisa el nombre en Market Watch)")
        return None

    sesgo, pct_alcista, pct_bajista = calcular_bias(df_d1)
    rango_diario   = rango_diario_p90(df_d1)
    rango_m15      = rango_m15_promedio(df_m15)
    ob_h4_min      = cuerpo_p85(df_h4)
    ob_h1_min      = cuerpo_p85(df_h1)
    fvg_bull, fvg_bear = detectar_fvg(df_m15)
    horas          = horas_activas(df_m15)
    rango_saturado = int(round(rango_diario * 0.9))
    sl_minimo      = int(round(cuerpo_promedio(df_h1) + 10))
    es_bajista     = pct_bajista > pct_alcista

    print(f"  ✅ {simbolo}: {sesgo} | Daily(P90)={rango_diario} | M15={rango_m15} | "
          f"OB_H4={ob_h4_min} | OB_H1={ob_h1_min} | SL={sl_minimo}")

    return {
        "simbolo": simbolo,
        "sesgo": sesgo,
        "pct_alcista": pct_alcista,
        "pct_bajista": pct_bajista,
        "es_bajista": es_bajista,
        "rango_diario": rango_diario,
        "rango_m15": rango_m15,
        "ob_h4_min": ob_h4_min,
        "ob_h1_min": ob_h1_min,
        "fvg_bull_fuerte": fvg_bull,
        "fvg_bear_fuerte": fvg_bear,
        "horas_activas_utc": horas,
        "rango_saturado": rango_saturado,
        "sl_minimo": sl_minimo,
        "velas_d1": len(df_d1),
    }


# ── GENERAR ARCHIVO DE SALIDA (formato copiar/pegar) ─────────
def generar_archivo_salida(perfiles):
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = f"perfiles_actualizados_{fecha}.py"

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write(f"#  PERFILES ACTUALIZADOS — generado automáticamente\n")
        f.write(f"#  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC\n")
        f.write(f"#  Basado en {MESES_HISTORIAL} meses de historial real (MT5)\n")
        f.write("#\n")
        f.write("#  INSTRUCCIONES:\n")
        f.write("#  Estos bloques NO reemplazan tu config.py automáticamente.\n")
        f.write("#  Revísalos, y si tienen sentido, pásaselos a Claude para\n")
        f.write("#  que te reescriba el config.py completo con estos valores.\n")
        f.write("# ============================================================\n\n")

        for p in perfiles:
            if p is None:
                continue
            f.write(f"    # ── {p['simbolo']} — actualizado {datetime.now().strftime('%Y-%m-%d')} ──\n")
            f.write(f"    # {p['sesgo']} (alcista {p['pct_alcista']}% / bajista {p['pct_bajista']}%) "
                    f"| {p['velas_d1']} velas D1 analizadas\n")
            f.write(f'    "{p["simbolo"]}": {{\n')
            f.write(f'        "es_bajista":        {p["es_bajista"]},\n')
            f.write(f'        "usar_fvg":          True,\n')
            f.write(f'        "usar_ob":           True,\n')
            f.write(f'        "usar_swinglow":     False,\n')
            f.write(f'        "sl_minimo":         {p["sl_minimo"]},\n')
            f.write(f'        "rango_diario":      {p["rango_diario"]},\n')
            f.write(f'        "rango_m15":         {p["rango_m15"]},\n')
            f.write(f'        "ob_h4_min":         {p["ob_h4_min"]},\n')
            f.write(f'        "ob_h1_min":         {p["ob_h1_min"]},\n')
            f.write(f'        "fvg_bull_fuerte":   {p["fvg_bull_fuerte"]},\n')
            f.write(f'        "fvg_bear_fuerte":   {p["fvg_bear_fuerte"]},\n')
            f.write(f'        "horas_activas_utc": {p["horas_activas_utc"]},\n')
            f.write(f'        "rango_saturado":    {p["rango_saturado"]},\n')
            f.write(f'    }},\n\n')

    print(f"\n✅ Archivo generado: {nombre_archivo}")
    return nombre_archivo


# ── MAIN ───────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  DIEFERT SCANNER — Actualización automática de perfiles")
    print(f"  Analizando {MESES_HISTORIAL} meses de historial real")
    print("=" * 60 + "\n")

    conectar_mt5()

    dias = MESES_HISTORIAL * 30
    perfiles = []

    for simbolo in SIMBOLOS:
        resultado = perfilar_simbolo(simbolo, dias)
        perfiles.append(resultado)

    mt5.shutdown()

    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    for p in perfiles:
        if p is None:
            continue
        print(f"  {p['simbolo']:<12} {p['sesgo']:<10} Daily={p['rango_diario']:<5} "
              f"M15={p['rango_m15']:<4} OB_H4={p['ob_h4_min']:<5} SL={p['sl_minimo']}")

    generar_archivo_salida(perfiles)
    print("\nListo. Revisa el archivo generado y me lo compartes para actualizar config.py.")


if __name__ == "__main__":
    main()
