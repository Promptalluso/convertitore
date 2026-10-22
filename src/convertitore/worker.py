"""Single-file conversion protocol for a disposable child process."""

import json
import sys
from pathlib import Path

from .publication import convert_and_publish
from .operation_publication import publish_operation

MAX_REQUEST = 65_536


def worker_main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise ValueError("Richiesta di conversione troppo grande.")
        request = json.loads(raw)
        if "action" in request:
            outputs = publish_operation(
                request["action"], [Path(source) for source in request["sources"]],
                request.get("options", {}), Path(request["output_dir"])
            )
            result = {"ok": True, "outputs": [str(path) for path in outputs]}
        else:
            output = convert_and_publish(
                Path(request["source"]), request["target"], Path(request["output_dir"])
            )
            result = {"ok": True, "output": str(output)}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)[:1000] or "Conversione fallita."}
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return 0 if result["ok"] else 1
