# ============================================================
#  DIEFERT SCANNER v4.0 — trade_tracker.py
#
#  Seguimiento automático de trades con historial persistente.
#
#  NOVEDAD v4.0 — GUARDADO EN DISCO:
#  ─────────────────────────────────────────────────────────
#  Antes: todo en memoria RAM → se perdía al reiniciar.
#  Ahora: cada trade se guarda en "trades_log.csv" al instante.
#         Al reiniciar el scanner, los trades pendientes se
#         recuperan automáticamente y siguen siendo monitoreados.
#
#  FLUJO:
#  ─────────────────────────────────────────────────────────
#  1. main_v4 genera señal ALTA → llama registrar_trade()
#  2. El trade se guarda en CSV con estado "ACTIVO"
#  3. En cada ciclo → verificar_trades() monitorea precio
#  4. Al tocar TP o SL → actualiza CSV + alerta Telegram
#
#  ALERTAS TELEGRAM:
#  ─────────────────────────────────────────────────────────
#  ✅      TP1 alcanzado → parcial profit
#  ✅✅    TP2 alcanzado → profit extendido
#  🛑      SL tocado     → stop loss
#
#  ARCHIVO CSV: trades_log.csv (misma carpeta que el scanner)
#  ─────────────────────────────────────────────────────────
#  Columnas: id, fecha, hora, simbolo, direccion, entrada,
#            sl, tp1, tp2, score_poi, estado,
#            precio_cierre, pips_resultado, hora_cierre
# ============================================================

import csv
import os
import urllib.request
import urllib.parse
from datetime import datetime, date
from utils import enviar_telegram, obtener_df
from config import TF_M1, VELAS_M1, SIMBOLOS_BAJISTAS

# ── CONFIGURACIÓN ─────────────────────────────────────────
LOG_FILE  = "trades_log.csv"
TOL_TOQUE = 5

# ── SHEETS — distribución de señales a usuarios ───────────
SHEETS_URL   = "https://script.google.com/macros/s/AKfycbxu_g06ewkVL0oBysnabHFeufkXbK1jzOd74UydhMaXO2P1WmUWaJAP_AeBX7o0B7yMNg/exec"
SALT_SENALES = "MicroGrid2025DiegoSALSECRETA"

def _hash_senal(simbolo, entrada):
    """Hash para verificar que la señal viene del scanner oficial."""
    base = str(simbolo) + "-" + str(entrada) + "-" + SALT_SENALES
    h = 0
    for c in base:
        h = ((h * 31) + ord(c)) % 999999937
    h = abs(h)
    hs = str(h).zfill(12)
    return hs[0:4] + "-" + hs[4:8] + "-" + hs[8:12]

def _enviar_senal_sheets(trade):
    """Sube la señal al Google Sheets para que los EAs la descarguen."""
    try:
        simbolo = trade["simbolo"]
        entrada = round(trade["entrada"], 2)
        params  = urllib.parse.urlencode({
            "accion":  "nueva_senal",
            "simbolo": simbolo,
            "dir":     "SHORT" if trade["es_bajista"] else "LONG",
            "entrada": entrada,
            "sl":      round(trade["sl"],  2),
            "tp1":     round(trade["tp1"], 2),
            "tp2":     round(trade["tp2"], 2),
            "score":   trade["score_poi"],
            "hash":    _hash_senal(simbolo, entrada),
        })
        url = SHEETS_URL + "?" + params
        req = urllib.request.Request(url, headers={"User-Agent": "DiefertScanner/4.8"})
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = r.read().decode("utf-8").strip()
        print(f"  [Sheets] Señal enviada: {resp}")
    except Exception as e:
        print(f"  [Sheets] Error enviando señal: {e}")

COLUMNAS = [
    "id", "fecha", "hora", "simbolo", "direccion",
    "entrada", "sl", "tp1", "tp2", "pips_resultado",
    "estado", "precio_cierre", "hora_cierre", "notas", "extra", "score_poi",
]

# ── ESTADO EN MEMORIA (sincronizado con CSV) ───────────────
_trades_activos = {}   # {id: dict} — solo trades ACTIVO/TP1
_contador_id    = 0

# ── MÉTRICAS DEL DÍA (se recalculan al iniciar) ───────────
_metricas_dia = {
    "fecha":      None,
    "ganados":    0,
    "perdidos":   0,
    "pips_total": 0.0,
}


# ============================================================
#  INICIALIZACIÓN DEL CSV
#  Se llama automáticamente al importar el módulo.
#  Si el archivo no existe → lo crea con cabeceras.
#  Si existe → carga trades pendientes a memoria y recalcula
#  métricas del día para que el panel sea correcto.
# ============================================================

def _actualizar_metricas_directa(estado, pips):
    """Actualiza métricas sin verificar fecha (para recarga inicial)."""
    hoy = date.today()
    if _metricas_dia["fecha"] != hoy:
        _metricas_dia["fecha"]      = hoy
        _metricas_dia["ganados"]    = 0
        _metricas_dia["perdidos"]   = 0
        _metricas_dia["pips_total"] = 0.0
    if estado in ("CERRADO",):
        _metricas_dia["ganados"]    += 1
        _metricas_dia["pips_total"] += abs(pips)
    elif estado == "SL":
        _metricas_dia["perdidos"]   += 1
        _metricas_dia["pips_total"] -= abs(pips)


# ============================================================
#  HELPERS
# ============================================================

def _nuevo_id():
    global _contador_id
    _contador_id += 1
    return _contador_id

def _win_rate():
    total = _metricas_dia["ganados"] + _metricas_dia["perdidos"]
    if total == 0:
        return 0
    return round(_metricas_dia["ganados"] / total * 100)

def _actualizar_metricas(resultado, pips):
    hoy = date.today()
    if _metricas_dia["fecha"] != hoy:
        _metricas_dia["fecha"]      = hoy
        _metricas_dia["ganados"]    = 0
        _metricas_dia["perdidos"]   = 0
        _metricas_dia["pips_total"] = 0.0
    if resultado == "profit":
        _metricas_dia["ganados"]    += 1
        _metricas_dia["pips_total"] += abs(pips)
    else:
        _metricas_dia["perdidos"]   += 1
        _metricas_dia["pips_total"] -= abs(pips)

def _calcular_duracion(hora_entrada_str):
    try:
        ahora  = datetime.now()
        hora_e = datetime.strptime(hora_entrada_str, "%H:%M:%S").replace(
            year=ahora.year, month=ahora.month, day=ahora.day
        )
        diff    = ahora - hora_e
        minutos = int(diff.total_seconds() / 60)
        if minutos < 60:
            return f"{minutos}min"
        horas    = minutos // 60
        mins_rem = minutos % 60
        return f"{horas}h {mins_rem}min"
    except Exception:
        return "N/A"


# ============================================================
#  GUARDAR / ACTUALIZAR EN CSV
# ============================================================

def _guardar_trade_nuevo(trade):
    """Agrega una fila nueva al CSV cuando se registra un trade."""
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writerow({
            "id":             trade["id"],
            "fecha":          trade["fecha_entrada"],
            "hora":           trade["hora_entrada"],
            "simbolo":        trade["simbolo"],
            "direccion":      "SHORT" if trade["es_bajista"] else "LONG",
            "entrada":        round(trade["entrada"], 2),
            "sl":             round(trade["sl"], 2),
            "tp1":            round(trade["tp1"], 2),
            "tp2":            round(trade["tp2"], 2),
            "score_poi":      trade["score_poi"],
            "estado":         "ACTIVO",
            "precio_cierre":  "",
            "pips_resultado": "",
            "hora_cierre":    "",
        })
    # Copiar CSV a carpeta MT5 para que el EA lo lea
    _copiar_csv_a_mt5()
    # Enviar señal al Sheets para usuarios con EA Licensed
    _enviar_senal_sheets(trade)


MT5_FILES = r"C:\Users\Pc-Trabajo\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\trades_log.csv"

def _copiar_csv_a_mt5():
    """Copia trades_log.csv a la carpeta MQL5/Files para que el EA lo lea."""
    import shutil
    try:
        shutil.copy2(LOG_FILE, MT5_FILES)
    except Exception as e:
        print(f"  [Tracker] Warning: no se pudo copiar a MT5 Files: {e}")


def _actualizar_trade_csv(trade_id, estado, precio_cierre=None, pips=None):
    """
    Actualiza el estado de un trade existente en el CSV.
    Lee todas las filas, modifica la que corresponde, reescribe.
    """
    if not os.path.exists(LOG_FILE):
        return

    filas = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            if int(fila["id"]) == trade_id:
                fila["estado"] = estado
                if precio_cierre is not None:
                    fila["precio_cierre"]  = round(precio_cierre, 2)
                    fila["hora_cierre"]    = datetime.now().strftime("%H:%M:%S")
                if pips is not None:
                    fila["pips_resultado"] = round(pips, 1)
            filas.append(fila)

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writeheader()
        writer.writerows(filas)


# ============================================================
#  REGISTRAR TRADE
#  Llamar desde gestionar_alertas_v4() cuando se envía
#  una señal ALTA a Telegram.
# ============================================================

def registrar_trade(simbolo, es_bajista, precio_entrada,
                    sl, tp1, tp2, score_poi, trigger="ALTA"):
    """
    Registra un trade nuevo en memoria y en disco (CSV).
    Retorna el ID del trade para seguimiento.
    """
    ahora    = datetime.now()
    trade_id = _nuevo_id()

    trade = {
        "id":            trade_id,
        "simbolo":       simbolo,
        "es_bajista":    es_bajista,
        "entrada":       precio_entrada,
        "sl":            sl,
        "tp1":           tp1,
        "tp2":           tp2,
        "score_poi":     score_poi,
        "trigger":       trigger,
        "hora_entrada":  ahora.strftime("%H:%M:%S"),
        "fecha_entrada": ahora.strftime("%Y-%m-%d"),
        "estado":        "ACTIVO",
        "tp1_alcanzado": False,
        "sl_alcanzado":  False,
    }

    # Guardar en memoria
    _trades_activos[trade_id] = trade

    # Guardar en disco inmediatamente
    _guardar_trade_nuevo(trade)

    print(
        f"  📋 TRADE #{trade_id} REGISTRADO | {simbolo} | "
        f"entrada={precio_entrada:.0f} | SL={sl:.0f} | "
        f"TP1={tp1:.0f} TP2={tp2:.0f} | guardado en {LOG_FILE}"
    )
    return trade_id


# ============================================================
#  VERIFICAR TRADES ACTIVOS
#  Llamar en cada ciclo del scanner desde main_v4.py
# ============================================================

def verificar_trades():
    """
    Revisa todos los trades activos contra el precio actual.
    Actualiza CSV y envía alertas Telegram cuando corresponde.
    """
    if not _trades_activos:
        return

    trades_a_cerrar = []

    for trade_id, t in _trades_activos.items():
        if t["estado"] == "CERRADO":
            trades_a_cerrar.append(trade_id)
            continue

        df = obtener_df(t["simbolo"], TF_M1, 5)
        if df is None:
            continue

        precio     = round(df['close'].iloc[-1], 2)
        es_bajista = t["es_bajista"]

        # ── Verificar SL ──────────────────────────────────
        sl_tocado = (
            (es_bajista     and precio >= t["sl"] - TOL_TOQUE) or
            (not es_bajista and precio <= t["sl"] + TOL_TOQUE)
        )

        if sl_tocado and not t["sl_alcanzado"]:
            pips = abs(precio - t["entrada"])
            t["sl_alcanzado"] = True
            t["estado"]       = "SL"

            _actualizar_metricas("stop", pips)
            _actualizar_trade_csv(trade_id, "SL", precio, -pips)
            _enviar_alerta(t, "sl", precio, pips)
            trades_a_cerrar.append(trade_id)
            continue

        # ── Verificar TP1 ─────────────────────────────────
        tp1_tocado = (
            (es_bajista     and precio <= t["tp1"] + TOL_TOQUE) or
            (not es_bajista and precio >= t["tp1"] - TOL_TOQUE)
        )

        if tp1_tocado and not t["tp1_alcanzado"]:
            pips = abs(t["tp1"] - t["entrada"])
            t["tp1_alcanzado"] = True
            t["estado"]        = "TP1"

            _actualizar_trade_csv(trade_id, "TP1")
            _enviar_alerta(t, "tp1", precio, pips)

        # ── Verificar TP2 ─────────────────────────────────
        tp2_tocado = (
            (es_bajista     and precio <= t["tp2"] + TOL_TOQUE) or
            (not es_bajista and precio >= t["tp2"] - TOL_TOQUE)
        )

        if tp2_tocado and not t.get("tp2_alcanzado") and t["tp1_alcanzado"]:
            pips = abs(t["tp2"] - t["entrada"])
            t["tp2_alcanzado"] = True
            t["estado"]        = "CERRADO"

            _actualizar_metricas("profit", pips)
            _actualizar_trade_csv(trade_id, "CERRADO", precio, pips)
            _enviar_alerta(t, "tp2", precio, pips)
            trades_a_cerrar.append(trade_id)

    # Limpiar trades cerrados de memoria
    for trade_id in trades_a_cerrar:
        if trade_id in _trades_activos:
            del _trades_activos[trade_id]


# ============================================================
#  ALERTAS TELEGRAM
# ============================================================

def _enviar_alerta(trade, nivel, precio_actual, pips):
    t          = trade
    simbolo    = t["simbolo"]
    es_bajista = t["es_bajista"]
    icono_dir  = "📉" if es_bajista else "📈"
    entrada    = t["entrada"]
    score      = t["score_poi"]
    hora_e     = t["hora_entrada"]
    hora_a     = datetime.now().strftime("%H:%M:%S")
    duracion   = _calcular_duracion(hora_e)

    ganados  = _metricas_dia["ganados"]
    perdidos = _metricas_dia["perdidos"]
    wr       = _win_rate()
    pips_tot = round(_metricas_dia["pips_total"], 0)
    pips_txt = f"+{pips_tot:.0f}" if pips_tot >= 0 else f"{pips_tot:.0f}"

    if nivel == "sl":
        msg = (
            f"🛑 <b>STOP LOSS — {simbolo}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{icono_dir} Entrada:  {entrada:.0f}\n"
            f"🛑 SL:       {t['sl']:.0f}  ({pips:.0f} pts)\n"
            f"⏱ Duración: {duracion}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Score POI: {score}/10\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📅 Hoy: {ganados}✅ {perdidos}🛑 | WR:{wr}% | {pips_txt}pts\n"
            f"⏰ {hora_e} → {hora_a}"
        )
        print(f"  🛑 STOP | {simbolo} | -{pips:.0f}pts | {duracion}")

    elif nivel == "tp1":
        msg = (
            f"✅ <b>TP1 ALCANZADO — {simbolo}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{icono_dir} Entrada: {entrada:.0f}\n"
            f"✅ TP1:     {t['tp1']:.0f}  (+{pips:.0f} pts)\n"
            f"⏱ Duración: {duracion}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👀 Monitoreando TP2: {t['tp2']:.0f}\n"
            f"⏰ {hora_e} → {hora_a}"
        )
        print(f"  ✅ TP1 | {simbolo} | +{pips:.0f}pts | {duracion}")

    elif nivel == "tp2":
        msg = (
            f"✅✅ <b>TP2 — PROFIT | {simbolo}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{icono_dir} Entrada: {entrada:.0f}\n"
            f"✅ TP1: {t['tp1']:.0f}\n"
            f"✅ TP2: {t['tp2']:.0f}  (+{pips:.0f} pts)\n"
            f"⏱ Duración: {duracion}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Score POI: {score}/10\n"
            f"📅 Hoy: {ganados}✅ {perdidos}🛑 | WR:{wr}% | {pips_txt}pts\n"
            f"⏰ {hora_e} → {hora_a}"
        )
        print(f"  ✅✅ TP2 | {simbolo} | +{pips:.0f}pts | {duracion}")

    enviar_telegram(msg)


# ============================================================
#  RESUMEN Y PANEL
# ============================================================

def resumen_dia():
    """Línea de métricas para el panel de consola."""
    g   = _metricas_dia["ganados"]
    p   = _metricas_dia["perdidos"]
    wr  = _win_rate()
    pts = round(_metricas_dia["pips_total"], 0)
    pts_txt = f"+{pts:.0f}" if pts >= 0 else f"{pts:.0f}"
    return f"HOY: {g}✅ {p}🛑 WR:{wr}% {pts_txt}pts"


def trades_activos_resumen():
    """Lista de trades activos para mostrar en consola."""
    activos = [t for t in _trades_activos.values()
               if t["estado"] not in ("CERRADO", "SL")]
    if not activos:
        return []
    resumenes = []
    for t in activos:
        estado_txt = "TP1✅ → esperando TP2" if t["tp1_alcanzado"] else "activo"
        resumenes.append(
            f"  #{t['id']} {t['simbolo']} "
            f"{'↓' if t['es_bajista'] else '↑'} "
            f"entrada={t['entrada']:.0f} | "
            f"SL={t['sl']:.0f} | TP1={t['tp1']:.0f} | "
            f"{estado_txt} | desde {t['hora_entrada']}"
        )
    return resumenes


def resumen_efectividad():
    """
    Lee el CSV completo y muestra estadísticas históricas.
    Puedes llamar esto manualmente cuando quieras ver el historial.
    Ejemplo: python -c "from trade_tracker import resumen_efectividad; print(resumen_efectividad())"
    """
    if not os.path.exists(LOG_FILE):
        return "Sin historial todavía."

    total = ganadoras = perdedoras = pendientes = 0
    pips_total = 0.0
    por_simbolo = {}

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            total += 1
            sim = fila["simbolo"]
            if sim not in por_simbolo:
                por_simbolo[sim] = {"g": 0, "p": 0, "pend": 0, "pips": 0.0}

            if fila["estado"] == "CERRADO":
                ganadoras += 1
                p = float(fila["pips_resultado"] or 0)
                pips_total += p
                por_simbolo[sim]["g"]    += 1
                por_simbolo[sim]["pips"] += p
            elif fila["estado"] == "SL":
                perdedoras += 1
                p = float(fila["pips_resultado"] or 0)
                pips_total += p
                por_simbolo[sim]["p"]    += 1
                por_simbolo[sim]["pips"] += p
            else:
                pendientes += 1
                por_simbolo[sim]["pend"] += 1

    cerradas = ganadoras + perdedoras
    tasa = round(ganadoras / cerradas * 100, 1) if cerradas > 0 else 0

    lineas = [
        "=" * 50,
        f"  HISTORIAL DIEFERT SCANNER v4.0",
        f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "=" * 50,
        f"  Total señales:   {total}",
        f"  Ganadoras:       {ganadoras}",
        f"  Perdedoras:      {perdedoras}",
        f"  Pendientes:      {pendientes}",
        f"  Win rate:        {tasa}%",
        f"  Pips netos:      {round(pips_total, 1)}",
        "-" * 50,
    ]
    for sim, d in sorted(por_simbolo.items()):
        c = d["g"] + d["p"]
        t = round(d["g"] / c * 100, 1) if c > 0 else 0
        lineas.append(
            f"  {sim:<14} G={d['g']} P={d['p']} "
            f"Pend={d['pend']} WR={t}% Pips={round(d['pips'],1)}"
        )
    lineas.append("=" * 50)
    return "\n".join(lineas)


# ── INICIALIZAR AL IMPORTAR ───────────────────────────────

def _inicializar():
    global _contador_id

    # Crear CSV si no existe
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNAS)
            writer.writeheader()
        print(f"  [Tracker] CSV creado: {LOG_FILE}")
        return

    # Si existe → recuperar trades activos y métricas del día
    hoy = date.today().strftime("%Y-%m-%d")
    recuperados  = 0
    expirados    = []   # trades ACTIVOS con más de 24 horas sin scanner
    ahora        = datetime.now()
    LIMITE_HORAS = 24   # trades activos más viejos que esto se cierran al arrancar

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            trade_id = int(fila.get("id") or fila.get("trade_id") or 0)
            if trade_id > _contador_id:
                _contador_id = trade_id

            # Recalcular métricas del día con trades cerrados hoy
            if fila["fecha"] == hoy and fila["estado"] in ("SL", "CERRADO"):
                _actualizar_metricas_directa(
                    fila["estado"],
                    float(fila["pips_resultado"] or 0)
                )

            # Recuperar trades que siguen activos (ACTIVO o TP1)
            if fila["estado"] in ("ACTIVO", "TP1"):
                # Calcular antigüedad del trade
                try:
                    fecha_hora_str = f"{fila['fecha']} {fila['hora']}"
                    hora_entrada   = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M:%S")
                    horas_activo   = (ahora - hora_entrada).total_seconds() / 3600
                except Exception:
                    horas_activo   = 0

                if horas_activo > LIMITE_HORAS:
                    # Trade viejo — marcar para expirar
                    expirados.append({
                        "id":      trade_id,
                        "simbolo": fila["simbolo"],
                        "horas":   round(horas_activo, 1),
                        "entrada": fila["entrada"],
                        "dir":     fila["direccion"],
                    })
                else:
                    # Trade reciente — recuperar normalmente
                    _trades_activos[trade_id] = {
                        "id":            trade_id,
                        "simbolo":       fila["simbolo"],
                        "es_bajista":    fila["direccion"] == "SHORT",
                        "entrada":       float(fila["entrada"]),
                        "sl":            float(fila["sl"]),
                        "tp1":           float(fila["tp1"]),
                        "tp2":           float(fila["tp2"]),
                        "score_poi":     int(fila.get("score_poi") or 0),
                        "hora_entrada":  fila["hora"],
                        "fecha_entrada": fila["fecha"],
                        "estado":        fila["estado"],
                        "tp1_alcanzado": fila["estado"] == "TP1",
                        "sl_alcanzado":  False,
                    }
                    recuperados += 1

    # Cerrar trades expirados en el CSV
    for t in expirados:
        _actualizar_trade_csv(t["id"], "EXPIRADO", precio_cierre=None, pips=0)
        print(f"  [Tracker] Trade #{t['id']} {t['simbolo']} expirado ({t['horas']}h) → EXPIRADO")

    if recuperados > 0:
        print(f"  [Tracker] {recuperados} trade(s) activo(s) recuperado(s) del CSV")

    # ── RESUMEN DE ARRANQUE A TELEGRAM ────────────────────
    _enviar_resumen_arranque(recuperados, expirados)


def _enviar_resumen_arranque(recuperados, expirados):
    """Envía resumen del estado al arrancar el scanner."""
    ahora = datetime.now().strftime("%H:%M:%S")
    lineas = [
        f"🟢 <b>Diefert Scanner iniciado</b>",
        f"⏰ {ahora}",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    # Trades expirados limpiados
    if expirados:
        lineas.append(f"🗑 <b>{len(expirados)} señal(es) expirada(s) eliminadas:</b>")
        for t in expirados:
            icono = "📉" if t["dir"] == "SHORT" else "📈"
            lineas.append(f"   {icono} #{t['id']} {t['simbolo']} — {t['horas']}h activo")
    else:
        lineas.append(f"✅ Sin señales expiradas")

    lineas.append(f"━━━━━━━━━━━━━━━━━━")

    # Trades activos recuperados
    if recuperados > 0:
        lineas.append(f"📋 <b>{recuperados} trade(s) activo(s) retomados:</b>")
        for trade in _trades_activos.values():
            icono = "📉" if trade["es_bajista"] else "📈"
            lineas.append(
                f"   {icono} #{trade['id']} {trade['simbolo']} "
                f"entrada={trade['entrada']:.0f} | desde {trade['hora_entrada']}"
            )
    else:
        lineas.append(f"📋 Sin trades activos pendientes")

    lineas.append(f"━━━━━━━━━━━━━━━━━━")
    lineas.append(f"🔍 Escaneando {len(_trades_activos)} símbolo(s) activos...")

    try:
        enviar_telegram("\n".join(lineas))
    except Exception as e:
        print(f"  [Tracker] Error enviando resumen arranque: {e}")


# Esto corre automáticamente cuando main_v4.py importa este módulo.
# No necesitas llamarlo manualmente.
_inicializar()
