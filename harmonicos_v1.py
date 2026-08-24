# ============================================================
#  DIEFERT SCANNER v5 — harmonicos_v1.py
#
#  Detector de PATRONES ARMÓNICOS (AB=CD, Gartley, Bat,
#  Butterfly, Crab) usando el concepto de PCI (Pattern
#  Completion Interval) del libro "Guide to Precision
#  Harmonic Pattern Trading" (Young Ho Seo).
#
#  IDEA CENTRAL DEL PCI:
#  ─────────────────────────────────────────────────────────
#  En vez de exigir que el ratio Fibonacci sea EXACTO
#  (ej. D debe estar EXACTAMENTE en 0.786 de XA), se define
#  una banda de tolerancia estadística alrededor del ratio
#  central (ej. 0.786 ± 5%). Si el precio cae dentro de esa
#  banda, el patrón se considera válido — igual que un
#  intervalo de confianza.
#
#  ⚠️ IMPORTANTE — módulo 100% independiente:
#  ─────────────────────────────────────────────────────────
#  - NO modifica ni depende de alertas_v5.py, trade_tracker.py
#    ni del sistema de señales TIPO1/TIPO1_OB/TIPO2.
#  - NO bloquea ni interfiere con nada del scanner principal.
#  - Solo LEE velas (obtener_df) y REUSA enviar_telegram()
#    de utils.py — no modifica utils.py.
#  - Su único propósito es dar SEGUIMIENTO: manda una alerta
#    con el patrón detectado y la razón, para que puedas
#    verificar tú mismo qué tan bien funciona antes de
#    integrarlo algún día como un punto más del Total
#    Confluence Framework.
#  - Si algo falla acá, main_v5.py lo atrapa con su propio
#    try/except y el resto del scanner sigue sin enterarse.
#
#  NO CONFUNDIR con el "harmonic order" de EMAs que usa
#  EmaScalpD (precio > EMA30 > EMA50 > EMA100 > EMA200).
#  Son dos conceptos completamente distintos que solo
#  comparten la palabra "armónico".
#
#  SEÑALES VAN A: mismo canal Telegram "Señales Weltrade
#  Diefert" (utils.enviar_telegram, chat_id -1003918647141),
#  pero con encabezado propio "PATRÓN ARMÓNICO" para no
#  confundirse con las señales TIPO1/TIPO1_OB/TIPO2.
# ============================================================

import time
from datetime import datetime
import os

from config import TF_M15, VELAS_M15
from utils import obtener_df, enviar_telegram
from estructura import detectar_swings
from broker import nombre_real

# ── PARÁMETROS GLOBALES (ajustables) ──────────────────────
TF_ANALISIS     = TF_M15   # timeframe de análisis — M15 da estructura más limpia que M5
VELAS_ANALISIS  = VELAS_M15
VENTANA_SWING   = 4         # misma ventana que usa el scanner en M15

PCI_TOLERANCIA  = 0.05      # banda de tolerancia estadística (±5%) alrededor del ratio central
                             # subir a 0.07-0.08 = más señales, menos precisas
                             # bajar a 0.03      = menos señales, más estrictas

TOLERANCIA_D_PRZ = 0.006    # 0.6% — qué tan cerca debe estar el precio actual del punto D
                             # (PRZ) para considerar el patrón "vigente ahora" y no histórico

COOLDOWN_SEG     = 1800     # 30 min entre alertas del mismo símbolo+patrón
                             # (estado en memoria, se reinicia si el scanner reinicia —
                             #  no crítico porque esto es solo seguimiento, no trading real)

# ── DIBUJO EN MT5 (mismo mecanismo que escribir_swing_debug.py) ──
# Escribe un archivo .txt por símbolo en la carpeta Files del terminal.
# El indicador HarmonicVisualizer.mq5 (companero de este archivo) lo
# lee y dibuja las líneas X-A-B-C-D + zona PRZ directo en el gráfico.
# Si esta carpeta no existe o falla la escritura, NO afecta nada más
# del scanner — está protegido con su propio try/except.
MT5_FILES = (
    r"C:\Users\Pc-Trabajo\AppData\Roaming\MetaQuotes\Terminal"
    r"\A8AD829AC7294D1F2A5550B091C0BF33\MQL5\Files"
)

# ── ESTADO INTERNO (independiente de todo lo demás) ───────
_ultimo_envio = {}   # {"simbolo|patron|direccion": timestamp}


def _puede_enviar(clave):
    ahora = time.time()
    ultimo = _ultimo_envio.get(clave, 0)
    return (ahora - ultimo) >= COOLDOWN_SEG


def _registrar_envio(clave):
    _ultimo_envio[clave] = time.time()


# ============================================================
#  DEFINICIÓN DE PATRONES (ratios centrales del libro/estándar)
#  Cada patrón define:
#    b_centro   → retroceso de B respecto a XA (ratio único, con PCI)
#    c_min/max  → retroceso de C respecto a AB (rango ya definido, sin PCI extra)
#    d_centro   → retroceso/extensión de D respecto a XA (EL MÁS IMPORTANTE — nivel PRZ)
#    cd_min/max → proyección de CD respecto a BC (validación secundaria)
# ============================================================

PATRONES = [
    {
        'nombre': 'Gartley',
        'emoji': '🦋',
        'b_centro': 0.618,
        'c_min': 0.382, 'c_max': 0.886,
        'd_centro': 0.786,
        'cd_min': 1.13, 'cd_max': 1.618,
    },
    {
        'nombre': 'Bat',
        'emoji': '🦇',
        'b_centro': 0.50,   # rango real 0.382-0.500, se usa el centro con banda más ancha
        'c_min': 0.382, 'c_max': 0.886,
        'd_centro': 0.886,
        'cd_min': 1.618, 'cd_max': 2.618,
    },
    {
        'nombre': 'Butterfly',
        'emoji': '🦋',
        'b_centro': 0.786,
        'c_min': 0.382, 'c_max': 0.886,
        'd_centro': 1.27,   # rango real 1.27-1.618, se usa el extremo más común
        'cd_min': 1.618, 'cd_max': 2.618,
    },
    {
        'nombre': 'Crab',
        'emoji': '🦀',
        'b_centro': 0.50,   # rango real 0.382-0.618, se usa el centro
        'c_min': 0.382, 'c_max': 0.886,
        'd_centro': 1.618,
        'cd_min': 2.24, 'cd_max': 3.618,
    },
]

# AB=CD se evalúa aparte porque solo usa 4 puntos (A-B-C-D), no 5 (X-A-B-C-D)
ABCD_C_MIN, ABCD_C_MAX = 0.618, 0.786   # retroceso de C respecto a AB
ABCD_CD_CENTRO         = 1.0            # CD debe ser ≈ igual de largo que AB


# ============================================================
#  LIMPIAR SWINGS — asegurar alternancia estricta SH/SL
# ============================================================

def _limpiar_swings_alternados(swings):
    """
    detectar_swings() puede devolver swings consecutivos del mismo
    tipo (dos SH seguidos, etc). Para armar X-A-B-C-D necesitamos
    una secuencia limpia que alterne SH/SL. Cuando hay dos seguidos
    del mismo tipo, se queda con el más extremo.
    """
    if not swings:
        return []

    limpios = [swings[0]]
    for s in swings[1:]:
        anterior = limpios[-1]
        if s['tipo'] == anterior['tipo']:
            # mismo tipo seguido → quedarse con el más extremo
            if s['tipo'] == 'SH' and s['precio'] > anterior['precio']:
                limpios[-1] = s
            elif s['tipo'] == 'SL' and s['precio'] < anterior['precio']:
                limpios[-1] = s
            # si no es más extremo, se ignora el nuevo
        else:
            limpios.append(s)

    return limpios


# ============================================================
#  PCI — banda de tolerancia estadística
# ============================================================

def _dentro_de_pci(ratio, centro, tolerancia=PCI_TOLERANCIA):
    """Retorna True si 'ratio' cae dentro de la banda centro±tolerancia."""
    return (centro - tolerancia) <= ratio <= (centro + tolerancia)


def _dentro_de_rango(ratio, minimo, maximo, tolerancia=PCI_TOLERANCIA):
    """Igual que _dentro_de_pci pero para rangos ya definidos (ej. C: 0.382-0.886),
    ensanchando un poco los bordes con la tolerancia PCI."""
    return (minimo - tolerancia) <= ratio <= (maximo + tolerancia)


# ============================================================
#  EVALUAR PATRONES DE 5 PUNTOS (X-A-B-C-D)
# ============================================================

def _evaluar_xabcd(x, a, b, c, d):
    """
    Recibe los 5 puntos (precios) y evalúa contra cada patrón
    de la lista PATRONES. Retorna el primer match encontrado
    (o None). direccion: 'alcista' si D es un mínimo (esperar
    rebote hacia arriba), 'bajista' si D es un máximo.
    """
    xa = a - x
    ab = b - a
    bc = c - b
    cd = d - c

    if xa == 0 or ab == 0 or bc == 0:
        return None

    ratio_b  = abs(ab) / abs(xa)
    ratio_c  = abs(bc) / abs(ab)
    ratio_d  = abs(d - x) / abs(xa)      # posición de D respecto a XA (el PRZ)
    ratio_cd = abs(cd) / abs(bc)

    for pat in PATRONES:
        if not _dentro_de_pci(ratio_b, pat['b_centro']):
            continue
        if not _dentro_de_rango(ratio_c, pat['c_min'], pat['c_max']):
            continue
        if not _dentro_de_pci(ratio_d, pat['d_centro']):
            continue
        if not _dentro_de_rango(ratio_cd, pat['cd_min'], pat['cd_max']):
            continue

        return {
            'nombre':   pat['nombre'],
            'emoji':    pat['emoji'],
            'ratio_b':  round(ratio_b, 3),
            'ratio_c':  round(ratio_c, 3),
            'ratio_d':  round(ratio_d, 3),
            'ratio_cd': round(ratio_cd, 3),
            'd_precio': d,
        }

    return None


def _evaluar_abcd(a, b, c, d):
    """Patrón AB=CD — solo 4 puntos, sin X."""
    ab = b - a
    bc = c - b
    cd = d - c

    if ab == 0 or bc == 0:
        return None

    ratio_c  = abs(bc) / abs(ab)
    ratio_cd = abs(cd) / abs(ab)   # CD debe ser ≈ igual de largo que AB

    if not _dentro_de_rango(ratio_c, ABCD_C_MIN, ABCD_C_MAX):
        return None
    if not _dentro_de_pci(ratio_cd, ABCD_CD_CENTRO, tolerancia=0.10):
        return None

    return {
        'nombre':   'AB=CD',
        'emoji':    '📐',
        'ratio_c':  round(ratio_c, 3),
        'ratio_cd': round(ratio_cd, 3),
        'd_precio': d,
    }


# ============================================================
#  CONSTRUIR MENSAJE
# ============================================================

def _construir_mensaje(simbolo, patron, direccion, precio_actual):
    icono  = '📉' if direccion == 'bajista' else '📈'
    accion = 'posible reversión BAJISTA' if direccion == 'bajista' else 'posible reversión ALCISTA'

    lineas = [
        f"{patron['emoji']} <b>PATRÓN ARMÓNICO — {patron['nombre']} | {simbolo}</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"{icono} Señal de seguimiento: {accion}",
        f"📍 Precio en zona PRZ (punto D): <b>{patron['d_precio']:.0f}</b>",
        f"💹 Precio actual: {precio_actual:.0f}",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    if 'ratio_b' in patron:
        lineas.append(f"📊 Ratios: B={patron['ratio_b']} | C={patron['ratio_c']} | D={patron['ratio_d']} | CD/BC={patron['ratio_cd']}")
    else:
        lineas.append(f"📊 Ratios: C={patron['ratio_c']} | CD/AB={patron['ratio_cd']}")

    lineas.append(f"🧪 Tolerancia PCI: ±{int(PCI_TOLERANCIA*100)}%")
    lineas.append(f"⚠️ SOLO SEGUIMIENTO — no reemplaza tu setup habitual (SMC/EmaScalpD)")
    lineas.append(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

    return '\n'.join(lineas)


# ============================================================
#  ESCRIBIR ARCHIVO PARA MT5 (dibujo del patrón en el gráfico)
# ============================================================

def _epoch(df, idx):
    """Convierte el timestamp de la vela en 'idx' a segundos unix,
    sin reinterpretar zona horaria (mismo valor que puso obtener_df)."""
    return int(df['time'].iloc[idx].value // 10**9)


def _escribir_visual_mt5(simbolo, patron, direccion, puntos, generado_epoch):
    """
    Escribe harmonico_<SIMBOLO_REAL>.txt en la carpeta Files de MT5.
    Formato CSV de una línea:
      patron,direccion,x_time,x_precio,a_time,a_precio,b_time,b_precio,
      c_time,c_precio,d_time,d_precio,zona_alto,zona_bajo,generado

    Si el patrón es AB=CD (sin punto X), x_time/x_precio se escriben
    como "NA".

    Protegido con try/except — si falla, no afecta el resto del scanner.
    """
    try:
        simbolo_real = nombre_real(simbolo)
        nombre_archivo = "harmonico_" + simbolo_real.replace(" ", "") + ".txt"
        ruta = os.path.join(MT5_FILES, nombre_archivo)

        d_precio = puntos['D']['precio']
        zona_alto = round(d_precio * (1 + TOLERANCIA_D_PRZ), 2)
        zona_bajo = round(d_precio * (1 - TOLERANCIA_D_PRZ), 2)

        if 'X' in puntos:
            x_time, x_precio = puntos['X']['time'], puntos['X']['precio']
        else:
            x_time, x_precio = "NA", "NA"

        campos = [
            patron, direccion,
            x_time, x_precio,
            puntos['A']['time'], puntos['A']['precio'],
            puntos['B']['time'], puntos['B']['precio'],
            puntos['C']['time'], puntos['C']['precio'],
            puntos['D']['time'], puntos['D']['precio'],
            zona_alto, zona_bajo,
            generado_epoch,
        ]
        linea = ",".join(str(c) for c in campos)

        with open(ruta, "w", encoding="utf-8") as f:
            f.write(linea)

        print(f"  [Harmónicos] 🖊️  Dibujo escrito → {nombre_archivo}")
    except Exception as e:
        print(f"  [Harmónicos] ⚠️ No se pudo escribir archivo visual: {e}")


# ============================================================
#  FUNCIÓN PRINCIPAL — llamada desde main_v5.py
# ============================================================

def analizar_patron_armonico(simbolo):
    """
    Analiza un símbolo buscando patrones armónicos vigentes
    (punto D cerca del precio actual). Si encuentra uno dentro
    de la tolerancia PCI y no está en cooldown, manda alerta
    de SEGUIMIENTO al canal de Telegram.

    No retorna nada crítico para el scanner — si falla, main_v5.py
    lo atrapa y sigue. No bloquea ninguna otra lógica.
    """
    df = obtener_df(simbolo, TF_ANALISIS, VELAS_ANALISIS)
    if df is None or len(df) < 30:
        return

    precio_actual = df['close'].iloc[-1]

    swings = detectar_swings(df, ventana=VENTANA_SWING)
    swings = _limpiar_swings_alternados(swings)

    if len(swings) < 4:
        return

    # ── Intentar patrones de 5 puntos (X-A-B-C-D) ───────────
    if len(swings) >= 5:
        ultimos5 = swings[-5:]
        x, a, b, c, d = [s['precio'] for s in ultimos5]
        d_tipo = swings[-1]['tipo']   # 'SL' → D es mínimo (alcista) | 'SH' → D es máximo (bajista)

        match = _evaluar_xabcd(x, a, b, c, d)
        if match:
            direccion = 'alcista' if d_tipo == 'SL' else 'bajista'
            dist_pct  = abs(precio_actual - match['d_precio']) / match['d_precio']

            if dist_pct <= TOLERANCIA_D_PRZ:
                clave = f"{simbolo}|{match['nombre']}|{direccion}"
                if _puede_enviar(clave):
                    msg = _construir_mensaje(simbolo, match, direccion, precio_actual)
                    print(f"  🔷 [Harmónicos] {match['nombre']} {direccion.upper()} detectado | {simbolo} | D={match['d_precio']:.0f}")
                    enviar_telegram(msg)
                    _registrar_envio(clave)

                    puntos = {
                        etiqueta: {'precio': s['precio'], 'time': _epoch(df, s['idx'])}
                        for etiqueta, s in zip(['X', 'A', 'B', 'C', 'D'], ultimos5)
                    }
                    _escribir_visual_mt5(simbolo, match['nombre'], direccion, puntos, int(time.time()))
                return  # un patrón por ciclo es suficiente

    # ── Intentar AB=CD (4 puntos) ────────────────────────────
    ultimos4 = swings[-4:]
    a, b, c, d = [s['precio'] for s in ultimos4]
    d_tipo = swings[-1]['tipo']

    match = _evaluar_abcd(a, b, c, d)
    if match:
        direccion = 'alcista' if d_tipo == 'SL' else 'bajista'
        dist_pct  = abs(precio_actual - match['d_precio']) / match['d_precio']

        if dist_pct <= TOLERANCIA_D_PRZ:
            clave = f"{simbolo}|{match['nombre']}|{direccion}"
            if _puede_enviar(clave):
                msg = _construir_mensaje(simbolo, match, direccion, precio_actual)
                print(f"  🔷 [Harmónicos] AB=CD {direccion.upper()} detectado | {simbolo} | D={match['d_precio']:.0f}")
                enviar_telegram(msg)
                _registrar_envio(clave)

                puntos = {
                    etiqueta: {'precio': s['precio'], 'time': _epoch(df, s['idx'])}
                    for etiqueta, s in zip(['A', 'B', 'C', 'D'], ultimos4)
                }
                _escribir_visual_mt5(simbolo, match['nombre'], direccion, puntos, int(time.time()))
