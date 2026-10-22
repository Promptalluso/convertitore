"""Run one conversion with cancellation and a deadline."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

MAX_DIAGNOSTIC = 131_072


class Cancelled(Exception):
    """The user stopped the current conversion."""


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        subprocess.run([str(taskkill), "/PID", str(proc.pid), "/T", "/F"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10, check=False)
        if proc.poll() is None:
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=10)


def _invoke(payload: dict, cancelled: threading.Event, timeout: float,
            command: list[str] | None) -> dict:
    if cancelled.is_set():
        raise Cancelled("Conversione annullata.")
    request = json.dumps(payload).encode()
    if len(request) > 65_536:
        raise ValueError("Richiesta di conversione troppo grande.")
    cmd = command or ([sys.executable, "--worker"] if getattr(sys, "frozen", False)
                      else [sys.executable, "-m", "convertitore", "--worker"])
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                creationflags=flags, start_new_session=os.name != "nt")
        started = time.monotonic()
        try:
            assert proc.stdin is not None
            proc.stdin.write(request)
            proc.stdin.close()
            while proc.poll() is None:
                if cancelled.is_set():
                    raise Cancelled("Conversione annullata.")
                if time.monotonic() - started > timeout:
                    raise TimeoutError("Conversione oltre il limite di tempo.")
                if (os.fstat(out.fileno()).st_size > MAX_DIAGNOSTIC
                        or os.fstat(err.fileno()).st_size > MAX_DIAGNOSTIC):
                    raise ValueError("Il processo ha superato il limite dei messaggi diagnostici.")
                time.sleep(0.04)
            if os.fstat(out.fileno()).st_size > MAX_DIAGNOSTIC:
                raise ValueError("Risposta del processo troppo grande.")
            out.seek(0)
            try:
                result = json.loads(out.read(MAX_DIAGNOSTIC + 1))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError("Il processo di conversione non ha risposto correttamente.") from exc
            if not result.get("ok"):
                raise ValueError(result.get("error", "Conversione fallita."))
            if proc.returncode != 0:
                raise ValueError("Il processo di conversione si è chiuso con errore.")
            return result
        finally:
            _stop(proc)


def run_job(source: Path, target: str, output_dir: Path, cancelled: threading.Event,
            timeout: float = 180, command: list[str] | None = None) -> Path:
    result = _invoke({"source": str(source), "target": target,
                      "output_dir": str(output_dir)}, cancelled, timeout, command)
    return Path(result["output"])


def run_operation(action: str, sources: list[Path], options: dict,
                  output_dir: Path, cancelled: threading.Event,
                  timeout: float = 180, command: list[str] | None = None) -> list[Path]:
    result = _invoke({"action": action, "sources": [str(path) for path in sources],
                      "options": options, "output_dir": str(output_dir)},
                     cancelled, timeout, command)
    outputs = result.get("outputs")
    if not isinstance(outputs, list) or not outputs or not all(isinstance(item, str) for item in outputs):
        raise ValueError("Il processo non ha restituito file validi.")
    return [Path(item) for item in outputs]
