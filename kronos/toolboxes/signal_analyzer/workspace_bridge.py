"""Bridge between Signal Analyzer and embedded IPython workspace."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, QEventLoop, QTimer

from .signal_model import SignalRecord


class WorkspaceBridge(QObject):
    """Reads array-like variables from a Jupyter kernel client."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._kernel_client: Any = None

    def set_kernel_client(self, kernel_client: Any) -> None:
        """Attach current QtConsole kernel client."""
        self._kernel_client = kernel_client

    def list_array_variables(self, timeout_ms: int = 1200) -> list[dict[str, str]]:
        """Return array-like workspace variables as dict rows."""
        code = (
            "import json as __json\n"
            "import numpy as __np\n"
            "try:\n"
            "    __ip = get_ipython()\n"
            "    __ns = __ip.user_ns if __ip else globals()\n"
            "except Exception:\n"
            "    __ns = globals()\n"
            "__rows = []\n"
            "for __name, __val in __ns.items():\n"
            "    try:\n"
            "        if isinstance(__val, __np.ndarray):\n"
            "            __rows.append({'name': __name, 'size': str(list(__val.shape)), 'class': 'ndarray'})\n"
            "        elif isinstance(__val, list):\n"
            "            __rows.append({'name': __name, 'size': str(len(__val)), 'class': 'list'})\n"
            "    except Exception:\n"
            "        pass\n"
            "print(__json.dumps(__rows))\n"
        )
        payload = self._request_json(code, timeout_ms=timeout_ms)
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        return []

    def fetch_signal(self, name: str, timeout_ms: int = 1200) -> SignalRecord | None:
        """Pull one variable from workspace as SignalRecord if possible."""
        code = (
            "import json as __json\n"
            "import numpy as __np\n"
            "try:\n"
            "    __ip = get_ipython()\n"
            "    __ns = __ip.user_ns if __ip else globals()\n"
            "except Exception:\n"
            "    __ns = globals()\n"
            f"__val = __ns.get({name!r})\n"
            "__out = {'ok': False}\n"
            "if isinstance(__val, __np.ndarray):\n"
            "    __arr = __val.reshape(-1).astype(float)\n"
            "    __out = {'ok': True, 'data': __arr.tolist(), 'fs': 1000.0}\n"
            "elif isinstance(__val, list):\n"
            "    __arr = __np.asarray(__val, dtype=float).reshape(-1)\n"
            "    __out = {'ok': True, 'data': __arr.tolist(), 'fs': 1000.0}\n"
            "print(__json.dumps(__out))\n"
        )
        payload = self._request_json(code, timeout_ms=timeout_ms)
        if not isinstance(payload, dict) or not payload.get("ok"):
            return None

        data = np.asarray(payload.get("data", []), dtype=np.float64)
        if data.size == 0:
            return None
        return SignalRecord.create(
            name=name,
            data=data,
            fs=float(payload.get("fs", 1000.0)),
            source="workspace",
        )

    def _request_json(self, code: str, timeout_ms: int = 1200) -> Any:
        if self._kernel_client is None:
            return None

        stream_parts: list[str] = []
        done = {"value": False}

        loop = QEventLoop()
        timer = QTimer(self)
        timer.setSingleShot(True)

        msg_id = self._kernel_client.execute(code, silent=False, store_history=False)

        def finish() -> None:
            if done["value"]:
                return
            done["value"] = True
            if timer.isActive():
                timer.stop()
            loop.quit()

        def on_timeout() -> None:
            finish()

        def on_message(msg: dict) -> None:
            parent = msg.get("parent_header", {}).get("msg_id")
            if parent != msg_id:
                return
            msg_type = msg.get("header", {}).get("msg_type")
            if msg_type == "stream":
                stream_parts.append(str(msg.get("content", {}).get("text", "")))
            elif msg_type == "status" and msg.get("content", {}).get("execution_state") == "idle":
                finish()

        channel = getattr(self._kernel_client, "iopub_channel", None)
        if channel is None or not hasattr(channel, "message_received"):
            return None

        timer.timeout.connect(on_timeout)
        channel.message_received.connect(on_message)
        timer.start(max(200, int(timeout_ms)))
        loop.exec()

        try:
            channel.message_received.disconnect(on_message)
        except Exception:
            pass

        raw = "".join(stream_parts).strip()
        if not raw:
            return None

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None
