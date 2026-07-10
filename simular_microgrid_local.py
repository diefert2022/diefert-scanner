"""
simular_microgrid_local.py
===========================
Simula el MicroGrid usando los datos del resultado_evaluacion.json
Sin necesidad de consultar MT5 de nuevo.

Lógica:
- Grid abre entradas cada VELA_SIZE pts mientras precio va en contra
- TP = cuando hay spike a favor (max_favor) desde el punto más bajo
- SL = cuando max_contra >= distancia al SL
- PnL = suma de (punto_mas_bajo - nivel) * lote para cada entrada cerrada
"""
import json
import os

INPUT  = r'F:\clude\diefert_scanner_v5\resultado_evaluacion.json'
OUTPUT = r'F:\clude\diefert_scanner_v5\resultado_microgrid.json'

LOTE_INICIAL  = 0.01
MULTIPLICADOR_DEFAULT = 1.2

# Multiplicador por índice
MULTIPLICADOR = {
    'PainX 400' : 1.2,
    'PainX 600' : 1.2,
    'PainX 800' : 1.2,
    'PainX 999' : 1.2,
    'PainX 1200': 1.1,   # más conservador por volatilidad
    'GainX 400' : 1.2,
    'GainX 600' : 1.2,
    'GainX 800' : 1.2,
    'GainX 999' : 1.2,
    'GainX 1200': 1.2,
}

VELA_SIZE = {
    'PainX 400' : 3.5,
    'PainX 600' : 3.0,
    'PainX 800' : 2.0,
    'PainX 999' : 2.5,
    'PainX 1200': 1.5,
    'GainX 400' : 4.0,
    'GainX 600' : 3.0,
    'GainX 800' : 2.0,
    'GainX 999' : 2.5,
    'GainX 1200': 1.2,
}


def simular_grid(simbolo, direccion, entrada, sl_dist, max_contra, max_favor):
    distancia = VELA_SIZE.get(simbolo, 3.0)
    mult      = MULTIPLICADOR.get(simbolo, MULTIPLICADOR_DEFAULT)

    # Cuántas entradas se abrieron mientras el precio fue en contra
    n_entradas = max(1, int(max_contra / distancia) + 1)

    # Construir niveles del grid
    niveles = []
    for i in range(n_entradas):
        if direccion == 'LONG':
            nivel = entrada - (i * distancia)
            if nivel <= (entrada - sl_dist): break
        else:
            nivel = entrada + (i * distancia)
            if nivel >= (entrada + sl_dist): break
        lote = round(LOTE_INICIAL * (mult ** i), 6)
        niveles.append({'nivel': nivel, 'lote': lote})

    if not niveles:
        return {'resultado': 'SIN NIVELES', 'pnl': 0}

    # Punto más bajo del grid (donde empieza el spike)
    if direccion == 'LONG':
        punto_bajo = entrada - max_contra
        # TP = punto_bajo + max_favor
        tp_precio  = punto_bajo + max_favor
        toco_tp    = max_favor > 0
        toco_sl    = max_contra >= sl_dist
    else:
        punto_bajo = entrada + max_contra
        tp_precio  = punto_bajo - max_favor
        toco_tp    = max_favor > 0
        toco_sl    = max_contra >= sl_dist

    # Calcular PnL
    pnl = 0.0
    if toco_sl and not toco_tp:
        for n in niveles:
            if direccion == 'LONG':
                pnl -= (n['nivel'] - (entrada - sl_dist)) * n['lote']
            else:
                pnl -= ((entrada + sl_dist) - n['nivel']) * n['lote']
        resultado = 'LOSS'
    elif toco_tp:
        for n in niveles:
            if direccion == 'LONG':
                pnl += (tp_precio - n['nivel']) * n['lote']
            else:
                pnl += (n['nivel'] - tp_precio) * n['lote']
        resultado = 'WIN'
    else:
        resultado = 'ACTIVO'
        pnl = 0

    lote_total = round(sum(n['lote'] for n in niveles), 4)

    return {
        'resultado'   : resultado,
        'pnl'         : round(pnl, 4),
        'n_entradas'  : len(niveles),
        'lote_total'  : lote_total,
        'distancia'   : distancia,
        'punto_bajo'  : round(punto_bajo, 2),
        'tp_precio'   : round(tp_precio, 2),
        'max_favor'   : max_favor,
        'max_contra'  : max_contra,
    }


def main():
    print("=== SIMULADOR MICROGRID — DATOS LOCALES ===\n")

    with open(INPUT) as f:
        data = json.load(f)

    detalle = data if isinstance(data, list) else data.get('detalle', [])

    resultados = []
    pnl_total  = 0

    for r in detalle:
        simbolo   = r['simbolo']
        direccion = r['direccion']
        entrada   = r['entrada']
        hist      = r.get('hist')

        if not hist or hist.get('resultado') == 'NO ACTIVADA':
            print(f"  {simbolo} {direccion} → NO ACTIVADA — omitida")
            continue

        max_favor  = hist['max_favor']
        max_contra = hist['max_contra']

        # Usar sl_dist real del JSON
        sl_dist = float(r.get('sl_dist', 0))
        if sl_dist == 0:
            print(f"  {simbolo} → sin sl_dist, corre primero evaluar_senales.py")
            continue

        sim = simular_grid(simbolo, direccion, entrada, sl_dist, max_contra, max_favor)
        sim['simbolo']   = simbolo
        sim['direccion'] = direccion
        sim['entrada']   = entrada
        resultados.append(sim)
        pnl_total += sim['pnl']

        signo = '+' if sim['pnl'] >= 0 else ''
        print(f"  {simbolo} {direccion} @ {entrada}")
        print(f"    Entradas: {sim['n_entradas']} c/{sim['distancia']}pts | Lote total: {sim['lote_total']}")
        print(f"    Punto bajo: {sim['punto_bajo']} | TP spike: {sim['tp_precio']}")
        print(f"    → {sim['resultado']} | PnL={signo}{sim['pnl']}\n")

    print("="*50)
    wins   = [r for r in resultados if r['resultado'] == 'WIN']
    losses = [r for r in resultados if r['resultado'] == 'LOSS']
    print(f"Total simuladas : {len(resultados)}")
    print(f"WIN             : {len(wins)}")
    print(f"LOSS            : {len(losses)}")
    print(f"PnL TOTAL       : {'+' if pnl_total >= 0 else ''}{round(pnl_total, 4)}")
    if wins:
        mejor = max(wins, key=lambda r: r['pnl'])
        print(f"Mejor trade     : {mejor['simbolo']} +{mejor['pnl']}")
    if losses:
        peor = min(losses, key=lambda r: r['pnl'])
        print(f"Peor trade      : {peor['simbolo']} {peor['pnl']}")

    with open(OUTPUT, 'w') as f:
        json.dump({'pnl_total': round(pnl_total, 4),
                   'wins': len(wins), 'losses': len(losses),
                   'detalle': resultados}, f, indent=2)

    print(f"\nGuardado: {OUTPUT}")
    input("\nPresiona Enter para cerrar...")

if __name__ == '__main__':
    main()
