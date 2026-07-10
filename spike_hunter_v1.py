# ============================================================
#  DIEFERT SCANNER — spike_hunter_v1.py  (v1.1 — MODO SEGUIMIENTO)
#
#  MÓDULO TEMPORAL — 100% INDEPENDIENTE
#  ─────────────────────────────────────────────────────────
#  NO modifica ningún archivo existente del scanner.
#
#  QUÉ HACE:
#  Detecta TODOS los spikes en M1 — verdes (alcistas) y
#  rojos (bajistas) — SIN IMPORTAR si el índice es GainX o
#  PainX. Ignora el filtro de dirección del scanner normal.
#
#  v1.1 — NOVEDAD (MODO SEGUIMIENTO):
#  Ahora tiene dos modos, controlados por MODO_DURACION:
#
#    MODO_DURACION = "HOY"    → activo hasta las 23:59:59 de hoy.
#                               Se apaga solo a medianoche.
#                               (modo actual — para seguimiento)
#
#    MODO_DURACION = "HORAS"  → activo HORAS_ACTIVO horas desde
#                               que arranca el scanner.
#                               (modo competencia original)
#
#  SE AUTO-DESACTIVA SOLO — no necesitas acordarte de nada.
#
#  CRITERIO DE SPIKE:
#    rango de la vela (high - low) >= promedio reciente * 1.5
#
#  CUANDO TERMINE EL SEGUIMIENTO:
#    1. Borra el bloque marcado en main_v5.py
#    2. Borra este archivo spike_hunter_v1.py
#    Listo, todo vuelve a quedar exactamente como estaba.
# ============================================================

from datetime import datetime, timedelta
from utils import obtener_df
from emascalpd_v1 import _enviar_emascalpd
from config import TF_M1, VELAS_M1

# ── CONFIGURACIÓN ─────────────────────────────────────────
MODO_DURACION       = "HOY"   # "HOY" = hasta medianoche | "HORAS" = modo competencia
HORAS_ACTIVO        = 2       # solo se usa si MODO_DURACION = "HORAS"
MULTIPLICADOR_SPK   = 1.5     # spike = rango > promedio reciente * este valor
VELAS_PROMEDIO      = 20      # velas usadas para calcular el rango promedio
MAX_MEMORIA_SPIKES  = 500     # limpieza de memoria para que no crezca infinito

_hora_inicio = datetime.now()

if MODO_DURACION == "HOY":
    # Activo hasta las 23:59:59 de HOY (medianoche)
    _hora_fin = _hora_inicio.replace(hour=23, minute=59, second=59, microsecond=0)
else:
    # Modo competencia clásico: N horas desde el arranque
    _hora_fin = _hora_inicio + timedelta(hours=HORAS_ACTIVO)

_spikes_enviados = {}   # {simbolo: set(idx_vela_ya_avisado)}

print(f"  🔍 [spike_hunter v1.1] SEGUIMIENTO ACTIVADO | "
      f"Modo: {MODO_DURACION} | "
      f"Termina automáticamente a las {_hora_fin.strftime('%H:%M:%S')}")


def _competencia_activa():
    """True mientras no se llegue a la hora de fin."""
    return datetime.now() < _hora_fin


def tiempo_restante_min():
    """Minutos restantes de seguimiento (para mensajes/consola)."""
    restante = _hora_fin - datetime.now()
    return max(0, int(restante.total_seconds() // 60))


def _detectar_spikes(df):
    """
    Revisa las últimas velas M1 y marca cuáles son spikes,
    verdes o rojas, SIN filtrar por dirección de tendencia.
    """
    spikes = []
    n = len(df)
    if n < VELAS_PROMEDIO + 3:
        return spikes

    rangos = (df['high'] - df['low']).to_numpy()

    # Solo revisamos las últimas 3 velas (evita reprocesar todo)
    for i in range(n - 3, n):
        promedio = rangos[max(0, i - VELAS_PROMEDIO):i].mean()
        if promedio <= 0:
            continue

        rango_i = rangos[i]
        if rango_i < promedio * MULTIPLICADOR_SPK:
            continue   # no es spike, es vela normal

        v = df.iloc[i]
        es_verde = v['close'] > v['open']

        spikes.append({
            'idx':   i,
            'tipo':  'VERDE' if es_verde else 'ROJO',
            'high':  round(float(v['high']), 2),
            'low':   round(float(v['low']), 2),
            'rango': round(float(rango_i), 2),
        })

    return spikes


def cazar_spikes(simbolo):
    """
    Punto de entrada. Se llama UNA VEZ por símbolo en cada
    ciclo del loop principal — solo mientras dure el seguimiento.
    """
    if not _competencia_activa():
        return   # ya terminó el seguimiento → no hace nada más

    # FlipX se mueve distinto (lo analiza solo EmaScalpD) — no aplica seguimiento de spikes
    if simbolo.startswith("FlipX"):
        return

    try:
        df = obtener_df(simbolo, TF_M1, VELAS_M1)
        if df is None:
            return

        spikes = _detectar_spikes(df)
        if not spikes:
            return

        ya_enviados = _spikes_enviados.setdefault(simbolo, set())

        for spk in spikes:
            if spk['idx'] in ya_enviados:
                continue   # ya avisado — evita duplicados

            ya_enviados.add(spk['idx'])

            emoji = '🟢' if spk['tipo'] == 'VERDE' else '🔴'
            msg = (
                f"🔍 <b>SEGUIMIENTO — SPIKE {spk['tipo']}</b> {emoji}\n"
                f"📊 {simbolo}\n"
                f"Zona: {spk['low']:.0f} – {spk['high']:.0f}\n"
                f"Rango: {spk['rango']:.0f} pts\n"
                f"⏱ Quedan {tiempo_restante_min()} min de seguimiento"
            )
            _enviar_emascalpd(msg)
            print(f"  🔍 SPIKE {spk['tipo']} | {simbolo} | "
                  f"[{spk['low']:.0f}-{spk['high']:.0f}] rango={spk['rango']:.0f}pts")

        if len(ya_enviados) > MAX_MEMORIA_SPIKES:
            ya_enviados.clear()

    except Exception as e:
        print(f"  [spike_hunter] Error en {simbolo}: {e}")
