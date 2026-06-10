# ============================================================
#  DIEFERT SCANNER v4.1 — utils.py
#
#  CAMBIOS v4.1:
#  ─────────────────────────────────────────────────────────
#  [+] Cooldown persistente en disco externo F:\
#      Archivo: F:\diefert_cooldown.json
#
#      ANTES: _ultimo_envio vivía en RAM → se perdía al
#             reiniciar el scanner → señales duplicadas.
#
#      AHORA: cada vez que se registra un envío, el tiempo
#             se guarda en el JSON del disco F:\.
#             Al iniciar el scanner, carga el JSON y respeta
#             los cooldowns activos aunque haya habido un
#             reinicio.
#
#  [+] _obs_usados también se persiste en el mismo JSON.
#      Un OB M1 que ya disparó señal no dispara de nuevo
#      aunque el scanner se reinicie.
#
#  ── ARCHIVO EN DISCO ──────────────────────────────────────
#  F:\diefert_cooldown.json
#  Formato:
#  {
#    "cooldowns": {
#      "señal_diefert_GainX 1200": 1716123456.78,
#      ...
#    },
#    "obs_usados": {
#      "GainX 1200": [90814, 90821],
#      ...
#    }
#  }
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
import urllib.request
import urllib.parse
import time
import json
import os
from config import TOKEN, CHAT_ID

# ── RUTA DEL ARCHIVO DE ESTADO ────────────────────────────
COOLDOWN_FILE = r"F:\diefert_cooldown.json"

# ── ESTADO EN MEMORIA (sincronizado con disco) ────────────
_ultimo_envio = {}
_obs_usados   = {}   # {simbolo: set(ob_mid)}


# ── CARGAR ESTADO DESDE DISCO ─────────────────────────────

def _cargar_estado():
    """
    Carga el estado de cooldowns y OBs usados desde disco.
    Se llama automáticamente al importar el módulo.
    Si el archivo no existe, empieza vacío.
    """
    global _ultimo_envio, _obs_usados
    try:
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            _ultimo_envio = datos.get('cooldowns', {})
            # Convertir listas a sets
            obs_raw = datos.get('obs_usados', {})
            _obs_usados = {k: set(v) for k, v in obs_raw.items()}
            print(f"  [Estado] Cooldowns cargados: {len(_ultimo_envio)} | OBs usados: {sum(len(v) for v in _obs_usados.values())}")
        else:
            print(f"  [Estado] Archivo nuevo: {COOLDOWN_FILE}")
    except Exception as e:
        print(f"  [Estado] Error cargando cooldown: {e} — iniciando vacío")
        _ultimo_envio = {}
        _obs_usados   = {}


def _guardar_estado():
    """
    Guarda el estado actual en disco.
    Se llama cada vez que hay un cambio.
    """
    try:
        # Convertir sets a listas para JSON
        obs_serial = {k: list(v) for k, v in _obs_usados.items()}
        datos = {
            'cooldowns':  _ultimo_envio,
            'obs_usados': obs_serial,
        }
        with open(COOLDOWN_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2)
    except Exception as e:
        print(f"  [Estado] Error guardando cooldown: {e}")


# ── COOLDOWN ──────────────────────────────────────────────

def puede_enviar(clave, segundos=1200):
    """
    Verifica si puede enviar una señal.
    Respeta el cooldown aunque el scanner se haya reiniciado.
    """
    ahora = time.time()
    ultimo = _ultimo_envio.get(clave, 0)

    if ahora - ultimo >= segundos:
        return True
    return False


def registrar_envio(clave):
    """
    Registra que se envió una señal ahora.
    Guarda en disco inmediatamente.
    """
    _ultimo_envio[clave] = time.time()
    _guardar_estado()


def resetear_cooldown(clave):
    """Resetea el cooldown de una clave específica."""
    if clave in _ultimo_envio:
        del _ultimo_envio[clave]
        _guardar_estado()


def tiempo_restante_cooldown(clave, segundos=1200):
    """
    Retorna cuántos segundos faltan para poder enviar de nuevo.
    0 si ya puede enviar.
    """
    ahora = time.time()
    ultimo = _ultimo_envio.get(clave, 0)
    restante = segundos - (ahora - ultimo)
    return max(0, int(restante))


# ── OBs USADOS ────────────────────────────────────────────

def ob_ya_usado(simbolo, ob_mid):
    """Retorna True si este OB ya fue usado como trigger."""
    return round(ob_mid) in _obs_usados.get(simbolo, set())


def registrar_ob_usado(simbolo, ob_mid):
    """Marca este OB como usado. Guarda en disco."""
    if simbolo not in _obs_usados:
        _obs_usados[simbolo] = set()
    _obs_usados[simbolo].add(round(ob_mid))
    _guardar_estado()


def limpiar_obs_usados(simbolo, obs_frescos_actuales):
    """
    Limpia OBs que ya no existen como frescos.
    Evita que el set crezca indefinidamente.
    """
    if simbolo not in _obs_usados:
        return
    mids_actuales = {round(ob['ob_mid']) for ob in obs_frescos_actuales}
    antes = len(_obs_usados[simbolo])
    _obs_usados[simbolo] = _obs_usados[simbolo] & mids_actuales
    if len(_obs_usados[simbolo]) != antes:
        _guardar_estado()


# ── TELEGRAM ──────────────────────────────────────────────

# ── CANALES DE DESTINO ────────────────────────────────────
# Señales llegan a AMBOS canales simultáneamente
CHAT_IDS = [
  #  CHAT_ID,              # canal principal (config.py)
   # "-1003933298024",    # Señales unidos
    "-1003918647141",    # Señales Weltrade Diefert
]

def enviar_telegram(mensaje):
    """Envía el mensaje a todos los canales configurados."""
    canales = list(dict.fromkeys(CHAT_IDS))  # elimina duplicados
    for chat_id in canales:
        try:
            url  = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id":    chat_id,
                "text":       mensaje,
                "parse_mode": "HTML"
            }).encode()
            urllib.request.urlopen(url, data, timeout=5)
        except Exception as e:
            print(f"  [Telegram error canal {chat_id}: {e}]")


# ── MT5 DATA ──────────────────────────────────────────────

def _nombre_mt5(simbolo):
    """
    Traduce el nombre interno (GainX 600) al nombre real del broker activo.
    Importa desde broker.py — sin imports circulares.
    """
    try:
        from broker import nombre_real
        return nombre_real(simbolo)
    except Exception:
        return simbolo


def obtener_df(simbolo, timeframe, velas):
    simbolo_real = _nombre_mt5(simbolo)
    rates = mt5.copy_rates_from_pos(simbolo_real, timeframe, 0, velas)
    if rates is None or len(rates) < 20:
        return None
    df         = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def precio_actual_mt5(simbolo):
    simbolo_real = _nombre_mt5(simbolo)
    rates = mt5.copy_rates_from_pos(simbolo_real, mt5.TIMEFRAME_M1, 0, 2)
    if rates is None or len(rates) == 0:
        return None
    return round(rates[-1]['close'], 2)


# ── INICIALIZAR AL IMPORTAR ───────────────────────────────
# Carga el estado guardado automáticamente cuando el scanner inicia.
_cargar_estado()
