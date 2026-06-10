# ============================================================
#  DIEFERT SCANNER v5 — alertas_v5.py
#
#  Calcula el nivel de alerta visual cuando el precio se
#  acerca a una zona histórica.
#
#  NIVELES:
#  ─────────────────────────────────────────────────────────
#  ⚠️  NIVEL 1 — Zona sola
#      Precio a menos de DIST_ALERTA pts de zona histórica
#
#  🔥  NIVEL 2 — Zona + OB coinciden
#      Zona histórica Y hay un OB en esa área (M5 a H1)
#
#  🎯  NIVEL 3 — Zona + OB + liquidez
#      Todo lo anterior Y la zona tiene mechas sin barrer
#      (toques históricos con mecha = liquidez acumulada)
#
#  REGLA FUNDAMENTAL:
#  Ningún nivel bloquea ni modifica la señal de entrada.
#  Solo informan al trader para que esté listo.
#
#  USO:
#    from alertas_v5 import evaluar_alerta
#    alerta = evaluar_alerta(simbolo, precio, zona, es_bajista)
# ============================================================

from ob_v5 import ob_en_zona

# Distancia en pts para activar alerta temprana
DIST_ALERTA = 10   # pts antes de llegar a la zona


def evaluar_alerta(simbolo, precio_actual, zona, es_bajista):
    """
    Evalúa el nivel de alerta para una zona histórica.

    Parámetros:
      simbolo       → nombre del índice
      precio_actual → precio actual del mercado
      zona          → dict de resistencias.py con keys:
                        precio, dist, score, fuerza,
                        n_toques, tipos, tfs, direccion
      es_bajista    → True para PainX, False para GainX

    Retorna dict:
      nivel:       1, 2 o 3 (o 0 si no hay alerta)
      icono:       ⚠️ 🔥 🎯
      descripcion: texto para consola/Telegram
      zona:        la zona evaluada
      ob:          dict del OB encontrado (o None)
      activa:      True si precio está dentro de DIST_ALERTA
    """
    precio_zona = zona['precio']
    dist        = abs(precio_actual - precio_zona)

    # Solo activar alerta si precio está cerca de la zona
    if dist > DIST_ALERTA:
        return {
            'nivel':       0,
            'icono':       '',
            'descripcion': '',
            'zona':        zona,
            'ob':          None,
            'activa':      False,
        }

    # ── Nivel 1: zona sola ────────────────────────────────
    nivel       = 1
    icono       = '⚠️'
    tiene_ob    = False
    tiene_liq   = False
    ob_info     = None

    # ── Nivel 2: verificar si hay OB en la zona ──────────
    ob_resultado = ob_en_zona(simbolo, precio_zona, es_bajista)
    if ob_resultado['encontrado']:
        nivel    = 2
        icono    = '🔥'
        tiene_ob = True
        ob_info  = ob_resultado

    # ── Nivel 3: verificar liquidez (mechas históricas) ──
    # Una zona tiene liquidez si tiene 2+ toques Y score >= 3
    # (los toques con mecha quedan registrados en n_toques)
    if tiene_ob and zona.get('n_toques', 0) >= 2 and zona.get('score', 0) >= 3:
        nivel      = 3
        icono      = '🎯'
        tiene_liq  = True

    # ── Construir descripción ─────────────────────────────
    tf_zona    = '+'.join(zona.get('tfs', ['?']))
    direccion  = zona.get('direccion', '')
    fuerza_txt = zona.get('fuerza_txt', '')

    desc_partes = [
        f"{icono} ZONA {tf_zona} | {precio_zona:.0f} | {direccion}",
        f"dist={dist:.0f}pts | fuerza={fuerza_txt} | toques={zona.get('n_toques',0)}x",
    ]

    if tiene_ob:
        desc_partes.append(
            f"OB {ob_info['tf']}: [{ob_info['ob_low']:.0f}–{ob_info['ob_high']:.0f}]"
        )

    if tiene_liq:
        desc_partes.append("liquidez acumulada (mechas sin barrer)")

    return {
        'nivel':       nivel,
        'icono':       icono,
        'descripcion': ' | '.join(desc_partes),
        'zona':        zona,
        'ob':          ob_info,
        'activa':      True,
    }


def resumen_alerta_consola(alerta):
    """
    Formatea la alerta para mostrar en consola.
    """
    if not alerta['activa']:
        return None

    nivel_txt = {1: "ZONA CERCANA", 2: "ZONA+OB", 3: "ZONA+OB+LIQ"}
    return (
        f"  {alerta['icono']} [{nivel_txt.get(alerta['nivel'], '?')}] "
        f"{alerta['descripcion']}"
    )


def resumen_alerta_telegram(simbolo, alerta, es_bajista):
    """
    Formatea la alerta para enviar por Telegram como aviso previo.
    Solo se envía si nivel >= 2 para no saturar el canal.
    """
    if not alerta['activa'] or alerta['nivel'] < 2:
        return None

    icono_dir = '📉' if es_bajista else '📈'
    zona      = alerta['zona']
    ob        = alerta['ob']

    lineas = [
        f"{icono_dir} {alerta['icono']} <b>ZONA ACTIVA — {simbolo}</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"📍 Zona: <b>{zona['precio']:.0f}</b> | {zona['direccion']}",
        f"📊 Fuerza: {zona['fuerza_txt']} | Toques: {zona.get('n_toques',0)}x",
        f"📐 TFs: {'+'.join(zona.get('tfs', ['?']))}",
    ]

    if ob:
        lineas.append(
            f"🟦 OB {ob['tf']}: [{ob['ob_low']:.0f}–{ob['ob_high']:.0f}]"
        )

    if alerta['nivel'] == 3:
        lineas.append("💧 Liquidez acumulada (mechas sin barrer)")

    lineas += [
        f"━━━━━━━━━━━━━━━━━━",
        f"⏳ Esperando CHoCH M5 para entrada...",
    ]

    return '\n'.join(lineas)
