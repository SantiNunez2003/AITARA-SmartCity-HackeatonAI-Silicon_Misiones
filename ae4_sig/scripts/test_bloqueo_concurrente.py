"""Prueba automatizada de concurrencia y bloqueo MVCC a nivel de fila (Fase III).

Simula el escenario de edición simultánea entre psql (Sesión A) y QGIS Edit Buffer
(Sesión B) sobre un mismo registro de `sig_ae4.semaforos`:
  1. Sesión A ejecuta `BEGIN; UPDATE sig_ae4.semaforos ...` sin confirmar.
  2. Sesión B intenta actualizar la misma fila en un hilo paralelo y queda
     bloqueada esperando el lock de transacción/tupla.
  3. Una conexión observadora consulta `pg_stat_activity` y `pg_locks` para
     verificar `wait_event_type = 'Lock'` y `pg_blocking_pids`.
  4. Sesión A ejecuta `ROLLBACK`, liberando inmediatamente a Sesión B.
  5. Sesión B también ejecuta `ROLLBACK` para dejar la tabla y la auditoría
     sin modificaciones residuales.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

import psycopg2

AE4_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = AE4_ROOT / ".env"

LOCK_HOLD_SECONDS = 2.0
OBSERVER_DELAY_SECONDS = 0.8


def load_dotenv(env_path: Path) -> None:
    """Carga variables KEY=VALUE desde ae4_sig/.env sin sobrescribir entorno."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def open_connection(app_name: str, autocommit: bool) -> psycopg2.extensions.connection:
    """Abre una conexión PostgreSQL etiquetada con application_name."""
    load_dotenv(ENV_PATH)
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5433")),
        dbname=os.environ.get("POSTGRES_DB", "aitara_ae4_sig"),
        user=os.environ.get("POSTGRES_USER", "ae4_user"),
        password=os.environ.get("POSTGRES_PASSWORD", "ae4_sig_2026_local"),
        application_name=app_name,
    )
    conn.autocommit = autocommit
    return conn


def main() -> int:
    conn_a = open_connection("ae4_test_sesion_a_psql", autocommit=False)
    conn_b = open_connection("ae4_test_sesion_b_qgis", autocommit=False)
    conn_obs = open_connection("ae4_test_observador", autocommit=True)

    b_state: Dict[str, Any] = {
        "started": threading.Event(),
        "elapsed_s": 0.0,
        "error": None,
        "rowcount": 0,
    }

    try:
        with conn_obs.cursor() as cur_obs:
            cur_obs.execute(
                """
                SELECT id, id_ide, nombre, estado
                  FROM sig_ae4.semaforos
                 ORDER BY id
                 LIMIT 1;
                """
            )
            target = cur_obs.fetchone()
            if not target:
                print("[ERROR] sig_ae4.semaforos no tiene registros para probar el bloqueo.")
                return 1
            semaforo_id, id_ide, nombre, estado_original = target

        pid_a = conn_a.get_backend_pid()
        pid_b = conn_b.get_backend_pid()
        print(
            f"[Init] Semáforo objetivo id={semaforo_id} (id_ide={id_ide}, nombre='{nombre}') | "
            f"pid_A={pid_a}, pid_B={pid_b}"
        )

        # 1. Sesión A adquiere lock de fila sin hacer COMMIT
        with conn_a.cursor() as cur_a:
            cur_a.execute(
                """
                UPDATE sig_ae4.semaforos
                   SET estado = COALESCE(estado, 'Activo') || ' [LOCK_A]'
                 WHERE id = %s;
                """,
                (semaforo_id,),
            )
        print(f"[Sesión A] UPDATE ejecutado sin COMMIT (lock retenido por pid={pid_a}).")

        # 2. Sesión B intenta actualizar el mismo registro en un hilo paralelo
        def worker_sesion_b() -> None:
            t0 = time.monotonic()
            try:
                with conn_b.cursor() as cur_b:
                    cur_b.execute("SET LOCAL lock_timeout = '15s';")
                    b_state["started"].set()
                    cur_b.execute(
                        """
                        UPDATE sig_ae4.semaforos
                           SET estado = COALESCE(estado, 'Activo') || ' [LOCK_B]'
                         WHERE id = %s;
                        """,
                        (semaforo_id,),
                    )
                    b_state["rowcount"] = cur_b.rowcount
            except Exception as exc:  # pragma: no cover - reporte de diagnóstico
                b_state["error"] = exc
            finally:
                b_state["elapsed_s"] = time.monotonic() - t0

        thread_b = threading.Thread(target=worker_sesion_b, daemon=True)
        thread_b.start()
        b_state["started"].wait(timeout=5.0)

        # 3. Esperar brevemente y observar el bloqueo real en pg_stat_activity / pg_locks
        time.sleep(OBSERVER_DELAY_SECONDS)
        lock_observed = False
        with conn_obs.cursor() as cur_obs:
            cur_obs.execute(
                """
                SELECT a.pid,
                       a.application_name,
                       a.state,
                       a.wait_event_type,
                       a.wait_event,
                       pg_blocking_pids(a.pid) AS blocking_pids
                  FROM pg_stat_activity AS a
                 WHERE a.pid = %s;
                """,
                (pid_b,),
            )
            act = cur_obs.fetchone()
            if act:
                _, app_name, state, wait_type, wait_ev, blocking_pids = act
                blocking_list = list(blocking_pids or [])
                lock_observed = (wait_type == "Lock") and (pid_a in blocking_list)
                print(
                    f"[Observador] pg_stat_activity pid={pid_b} ({app_name}): "
                    f"state={state}, wait_event_type={wait_type}, wait_event={wait_ev}, "
                    f"blocking_pids={blocking_list}"
                )

            cur_obs.execute(
                """
                SELECT l.pid,
                       l.locktype,
                       l.mode,
                       l.granted
                  FROM pg_locks AS l
                 WHERE l.pid IN (%s, %s)
                   AND l.locktype IN ('relation', 'tuple', 'transactionid')
                 ORDER BY l.pid, l.locktype, l.granted DESC;
                """,
                (pid_a, pid_b),
            )
            print("[Observador] Locks relevantes en pg_locks:")
            for l_pid, l_type, l_mode, l_granted in cur_obs.fetchall():
                print(f"  - pid={l_pid} | locktype={l_type} | mode={l_mode} | granted={l_granted}")

        # 4. Completar ventana de retención y liberar Sesión A con ROLLBACK
        remaining_hold = max(0.0, LOCK_HOLD_SECONDS - OBSERVER_DELAY_SECONDS)
        time.sleep(remaining_hold)
        conn_a.rollback()
        print(f"[Sesión A] ROLLBACK ejecutado tras ~{LOCK_HOLD_SECONDS:.1f}s (lock liberado).")

        thread_b.join(timeout=10.0)
        if thread_b.is_alive():
            print("[ERROR] Sesión B no finalizó tras liberar Sesión A.")
            return 1

        if b_state["error"] is not None:
            print(f"[ERROR] Sesión B falló con excepción: {b_state['error']}")
            return 1

        print(
            f"[Sesión B] Desbloqueada tras {b_state['elapsed_s']:.2f}s; "
            f"filas afectadas={b_state['rowcount']}."
        )

        # Revertir Sesión B para mantener limpia la base de datos
        conn_b.rollback()
        print("[Sesión B] ROLLBACK ejecutado para preservar el estado original.")

        # 5. Verificar integridad final de la fila
        with conn_obs.cursor() as cur_obs:
            cur_obs.execute(
                "SELECT estado FROM sig_ae4.semaforos WHERE id = %s;",
                (semaforo_id,),
            )
            estado_final = cur_obs.fetchone()[0]

        unblocked_after_wait = b_state["elapsed_s"] >= (LOCK_HOLD_SECONDS * 0.75)
        state_preserved = estado_final == estado_original

        if not lock_observed or not unblocked_after_wait or not state_preserved:
            print(
                f"[FALLO] Verificación incompleta: lock_observed={lock_observed}, "
                f"unblocked_after_wait={unblocked_after_wait}, state_preserved={state_preserved}"
            )
            return 1

        print("[OK] Bloqueo MVCC verificado end-to-end y estado original preservado.")
        return 0
    finally:
        for conn in (conn_a, conn_b, conn_obs):
            try:
                if not conn.autocommit:
                    conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
