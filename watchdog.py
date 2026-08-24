# ============================================================
#  WATCHDOG — Diefert Scanner
# ------------------------------------------------------------
#  Lanza main_v5.py como proceso hijo y lo vigila. Si el scanner
#  deja de actualizar su archivo de heartbeat (heartbeat.txt)
#  por más de HEARTBEAT_TIMEOUT segundos, asume que se colgó,
#  lo mata y lo vuelve a lanzar automáticamente.
#
#  USO: en vez de correr "python main_v5.py", corre:
#       python watchdog.py
#
#  El watchdog muestra en la misma consola todo lo que imprime
#  el scanner (no oculta nada), y además imprime sus propios
#  mensajes con el prefijo [WATCHDOG].
#
#  No modifica nada de main_v5.py más allá del heartbeat que
#  ya se agregó ahí. Este archivo es 100% independiente.
# ============================================================

import os
import subprocess
import sys
import time
from datetime import datetime

CARPETA = os.path.dirname(os.path.abspath(__file__))
SCRIPT_SCANNER = os.path.join(CARPETA, "main_v5.py")
HEARTBEAT_PATH = os.path.join(CARPETA, "heartbeat.txt")
WATCHDOG_LOG = os.path.join(CARPETA, "watchdog_log.txt")

# Cuanto tiempo sin actualizar el heartbeat antes de considerar
# que el scanner esta colgado y reiniciarlo (en segundos).
# El heartbeat se actualiza despues de CADA simbolo analizado,
# asi que 5 minutos da bastante margen incluso en el ciclo mas
# lento (recalculo de resistencias, ~40s por simbolo).
HEARTBEAT_TIMEOUT = 300

# Cuanto tiempo esperar tras cada arranque antes de empezar a
# vigilar el heartbeat (le da tiempo a MT5 a conectar y al
# analisis macro inicial a correr sin que el watchdog lo mate
# de entrada pensando que esta colgado).
GRACIA_ARRANQUE = 180

# Cuanto esperar entre chequeos del heartbeat.
INTERVALO_CHEQUEO = 15


def _log(msg):
    linea = f"[WATCHDOG] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — {msg}"
    print(linea)
    try:
        with open(WATCHDOG_LOG, 'a', encoding='utf-8') as f:
            f.write(linea + "\n")
    except Exception:
        pass


def _segundos_desde_ultimo_latido():
    if not os.path.exists(HEARTBEAT_PATH):
        return None
    try:
        with open(HEARTBEAT_PATH, 'r', encoding='utf-8') as f:
            texto = f.read().strip()
        ultimo = datetime.fromisoformat(texto)
        return (datetime.now() - ultimo).total_seconds()
    except Exception:
        return None


def _matar_proceso(proc):
    """Mata el proceso del scanner de forma robusta en Windows."""
    if proc.poll() is not None:
        return  # ya esta muerto
    try:
        # taskkill con /T mata tambien cualquier proceso hijo que
        # MT5 o alguna libreria haya podido lanzar.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True
        )
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _lanzar_scanner():
    _log(f"Iniciando main_v5.py ...")
    # Borrar heartbeat viejo para no confundirlo con uno nuevo
    try:
        if os.path.exists(HEARTBEAT_PATH):
            os.remove(HEARTBEAT_PATH)
    except Exception:
        pass

    proc = subprocess.Popen(
        [sys.executable, SCRIPT_SCANNER],
        cwd=CARPETA,
        # stdout/stderr = None -> hereda la consola del watchdog,
        # asi ves exactamente lo mismo que verias corriendolo directo.
        stdout=None,
        stderr=None,
    )
    return proc


def iniciar_watchdog():
    _log("Watchdog iniciado. Vigilando main_v5.py ...")
    reinicios = 0

    while True:
        proc = _lanzar_scanner()
        inicio = time.time()

        while True:
            time.sleep(INTERVALO_CHEQUEO)

            # ¿El proceso se cerro solo (crash, error fatal, etc.)?
            if proc.poll() is not None:
                _log(f"⚠️  main_v5.py se cerró solo (código {proc.returncode}). Reiniciando...")
                break

            # Durante el periodo de gracia no se vigila el heartbeat
            if time.time() - inicio < GRACIA_ARRANQUE:
                continue

            segundos = _segundos_desde_ultimo_latido()
            if segundos is None:
                # Aun no ha escrito ningun heartbeat y ya paso la gracia
                if time.time() - inicio > GRACIA_ARRANQUE + HEARTBEAT_TIMEOUT:
                    _log("⚠️  El scanner nunca escribió su primer heartbeat. Reiniciando...")
                    _matar_proceso(proc)
                    break
                continue

            if segundos > HEARTBEAT_TIMEOUT:
                reinicios += 1
                _log(f"🧊 Sin heartbeat hace {int(segundos)}s (límite {HEARTBEAT_TIMEOUT}s). "
                     f"El scanner parece congelado. Reiniciando (reinicio #{reinicios})...")
                _matar_proceso(proc)
                break

        # Pequeña pausa antes de relanzar, para no entrar en un
        # ciclo de reinicios demasiado agresivo si algo esta mal
        # de fondo (ej. MT5 cerrado, sin internet, etc.)
        time.sleep(5)


if __name__ == "__main__":
    try:
        iniciar_watchdog()
    except KeyboardInterrupt:
        print("\n  🛑 Watchdog detenido por usuario.")
