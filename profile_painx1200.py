"""
profile_painx1200.py
---------------------
Script de perfilado para PainX 1200, mismo patron que usamos para
GainX 600 / GainX 800 / GainX 999 / PainX 400.

QUE HACE ESTE SCRIPT (explicado paso a paso porque estas aprendiendo):

1. Lee un archivo CSV exportado desde MT5 (o desde tu Diefert Scanner)
   con columnas de tiempo y precios OHLC (Open, High, Low, Close).
2. Calcula el "bias" del indice: que tan seguido cierra en verde (alcista)
   vs en rojo (bajista). Esto nos dice si el indice tiene sesgo comprador
   o vendedor, sin importar el nombre que tenga.
3. Calcula el rango total (maximo - minimo) del periodo analizado.
4. Detecta Order Blocks en H4 (la ultima vela opuesta antes de un
   movimiento fuerte) y mide su tamano promedio en puntos.
5. Detecta Fair Value Gaps (FVG) alcistas y bajistas, y mide su
   tamano promedio en puntos.
6. Calcula el "noise candle size": el tamano promedio del cuerpo de
   una vela M1, para saber cuanto "ruido" normal tiene el indice
   (util para calibrar SL y evitar barridos falsos).
7. Encuentra las horas del dia (UTC) donde el indice se mueve mas,
   para saber cuando activar tus scanners.

COMO USARLO:
    python3 profile_painx1200.py /ruta/a/PainX1200_H4.csv
    python3 profile_painx1200.py /ruta/a/PainX1200_M1.csv --m1

El CSV debe tener columnas (en cualquier orden, con estos nombres o
similares, el script los detecta automaticamente):
    time/date, open, high, low, close
"""

import sys
import argparse
import pandas as pd
import numpy as np


def cargar_csv(path):
    """Lee el CSV y normaliza los nombres de columnas a minusculas."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Intentamos mapear nombres comunes de exportacion MT5
    rename_map = {}
    for col in df.columns:
        if col in ("time", "date", "datetime", "<date>", "<time>"):
            rename_map[col] = "time"
        elif col in ("open", "<open>"):
            rename_map[col] = "open"
        elif col in ("high", "<high>"):
            rename_map[col] = "high"
        elif col in ("low", "<low>"):
            rename_map[col] = "low"
        elif col in ("close", "<close>"):
            rename_map[col] = "close"
    df = df.rename(columns=rename_map)

    columnas_necesarias = {"open", "high", "low", "close"}
    faltantes = columnas_necesarias - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el CSV: {faltantes}")

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")

    return df


def calcular_bias(df):
    """
    % de velas alcistas (close > open) vs bajistas (close < open).
    Esto es lo que en tu memoria aparece como 'BULL 59%' o 'BEAR 53.6%'.
    """
    alcistas = (df["close"] > df["open"]).sum()
    bajistas = (df["close"] < df["open"]).sum()
    total = alcistas + bajistas
    pct_alcista = round(100 * alcistas / total, 1) if total else 0
    pct_bajista = round(100 * bajistas / total, 1) if total else 0

    if pct_alcista > pct_bajista:
        sesgo = f"BULL {pct_alcista}%"
    else:
        sesgo = f"BEAR {pct_bajista}%"
    return sesgo, pct_alcista, pct_bajista


def calcular_rango(df):
    """Rango total del periodo, en puntos (no en pips)."""
    maximo = df["high"].max()
    minimo = df["low"].min()
    return round(maximo - minimo, 2), round(maximo, 2), round(minimo, 2)


def detectar_order_blocks_h4(df, lookahead=5, impulso_minimo_pct=0.3):
    """
    Deteccion simplificada de Order Blocks:
    - Buscamos la ultima vela ROJA antes de un impulso alcista fuerte
      (OB alcista), y la ultima vela VERDE antes de un impulso
      bajista fuerte (OB bajista).
    - 'Impulso fuerte' = movimiento de precio mayor a impulso_minimo_pct%
      dentro de las siguientes 'lookahead' velas.
    Devuelve el tamano promedio (high-low) de los OB detectados, en puntos.
    """
    tamanos_ob = []
    precios = df[["open", "high", "low", "close"]].to_numpy()

    for i in range(len(precios) - lookahead - 1):
        vela = precios[i]
        es_roja = vela[3] < vela[0]  # close < open
        es_verde = vela[3] > vela[0]

        precio_referencia = vela[3]
        max_futuro = precios[i + 1: i + 1 + lookahead, 1].max()
        min_futuro = precios[i + 1: i + 1 + lookahead, 2].min()

        movimiento_alcista_pct = (max_futuro - precio_referencia) / precio_referencia * 100
        movimiento_bajista_pct = (precio_referencia - min_futuro) / precio_referencia * 100

        if es_roja and movimiento_alcista_pct >= impulso_minimo_pct:
            tamanos_ob.append(vela[1] - vela[2])  # high - low de esa vela
        elif es_verde and movimiento_bajista_pct >= impulso_minimo_pct:
            tamanos_ob.append(vela[1] - vela[2])

    if not tamanos_ob:
        return 0
    return round(float(np.mean(tamanos_ob)), 2)


def detectar_fvg(df):
    """
    FVG de 3 velas (patron estandar SMC):
    - FVG alcista: low de vela3 > high de vela1 (hueco entre ellas)
    - FVG bajista: high de vela3 < low de vela1
    Devuelve tamano promedio en puntos de cada tipo.
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()

    fvg_bull = []
    fvg_bear = []

    for i in range(len(df) - 2):
        v1_high, v1_low = highs[i], lows[i]
        v3_high, v3_low = highs[i + 2], lows[i + 2]

        if v3_low > v1_high:
            fvg_bull.append(v3_low - v1_high)
        elif v3_high < v1_low:
            fvg_bear.append(v1_low - v3_high)

    prom_bull = round(float(np.mean(fvg_bull)), 2) if fvg_bull else 0
    prom_bear = round(float(np.mean(fvg_bear)), 2) if fvg_bear else 0
    return prom_bull, prom_bear


def calcular_noise_candle(df):
    """
    Tamano promedio del cuerpo de vela (|close - open|), pensado para
    datos M1. Esto te dice cuanto 'ruido' normal tiene el indice y
    sirve para calibrar SL_EXTRA y evitar barridos por ruido.
    """
    cuerpos = (df["close"] - df["open"]).abs()
    return round(float(cuerpos.mean()), 2)


def horas_mas_activas(df, top_n=3):
    """
    Requiere columna 'time'. Agrupa por hora UTC y mide el rango
    promedio (high-low) por hora, para encontrar las horas de mayor
    movimiento (utilies para activar tus scanners).
    """
    if "time" not in df.columns or df["time"].isna().all():
        return None

    df = df.copy()
    df["hora"] = df["time"].dt.hour
    df["rango"] = df["high"] - df["low"]
    promedio_por_hora = df.groupby("hora")["rango"].mean().sort_values(ascending=False)
    return promedio_por_hora.head(top_n).round(2)


def main():
    parser = argparse.ArgumentParser(description="Perfilado de indice PainX 1200")
    parser.add_argument("csv_path", help="Ruta al archivo CSV con datos OHLC")
    parser.add_argument("--m1", action="store_true",
                         help="Indica que el CSV es de temporalidad M1 (para noise candle)")
    args = parser.parse_args()

    print(f"Cargando {args.csv_path} ...")
    df = cargar_csv(args.csv_path)
    print(f"{len(df)} velas cargadas.\n")

    sesgo, pct_alcista, pct_bajista = calcular_bias(df)
    rango_pts, maximo, minimo = calcular_rango(df)
    ob_h4 = detectar_order_blocks_h4(df)
    fvg_bull, fvg_bear = detectar_fvg(df)

    print("=" * 50)
    print("PERFIL: PainX 1200")
    print("=" * 50)
    print(f"Sesgo direccional : {sesgo}  (alcista {pct_alcista}% / bajista {pct_bajista}%)")
    print(f"Rango del periodo : {rango_pts} pts  (max {maximo} / min {minimo})")
    print(f"OB_H4 promedio    : {ob_h4} pts")
    print(f"FVG alcista prom. : {fvg_bull} pts")
    print(f"FVG bajista prom. : {fvg_bear} pts")

    if args.m1:
        noise = calcular_noise_candle(df)
        print(f"Noise candle (M1) : {noise} pts")

    horas = horas_mas_activas(df)
    if horas is not None:
        print("\nHoras UTC mas activas (mayor rango promedio):")
        for hora, valor in horas.items():
            print(f"  {hora:02d}:00 UTC -> {valor} pts")
    else:
        print("\n(No se pudo calcular horas activas: falta columna 'time' valida)")

    print("\nListo. Copia estos valores a config_v412.py / config_v413.py")
    print("igual que hiciste con GainX 600/800/999 y PainX 400.")


if __name__ == "__main__":
    main()
