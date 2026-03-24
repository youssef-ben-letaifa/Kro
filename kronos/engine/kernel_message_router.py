"""# Kronos IDE — Kernel message router and dispatcher."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable

from PyQt6.QtCore import QObject, QEventLoop, QTimer, pyqtSignal


class KernelMessageRouter(QObject):
    """Centralized router for kernel iopub messages."""

    message_received = pyqtSignal(dict)
    stream_received = pyqtSignal(str, str)
    status_received = pyqtSignal(str, str)
    error_received = pyqtSignal(str, str)

    def __init__(self, kernel_client=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._kernel_client = None
        self._callbacks: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
        if kernel_client is not None:
            self.attach(kernel_client)

    def attach(self, kernel_client) -> None:
        """Attach to a kernel client and route all incoming iopub messages."""
        if kernel_client is self._kernel_client:
            return
        self._detach()
        self._kernel_client = kernel_client
        if (
            self._kernel_client is not None
            and hasattr(self._kernel_client, "iopub_channel")
            and hasattr(self._kernel_client.iopub_channel, "message_received")
        ):
            self._kernel_client.iopub_channel.message_received.connect(
                self._on_iopub_message
            )

    def _detach(self) -> None:
        if (
            self._kernel_client is not None
            and hasattr(self._kernel_client, "iopub_channel")
            and hasattr(self._kernel_client.iopub_channel, "message_received")
        ):
            try:
                self._kernel_client.iopub_channel.message_received.disconnect(
                    self._on_iopub_message
                )
            except Exception:
                pass
        self._kernel_client = None

    def register_callback(self, msg_id: str, callback: Callable[[dict], None]) -> None:
        """Register a callback for all iopub messages matching *msg_id*."""
        if not msg_id:
            return
        self._callbacks[msg_id].append(callback)

    def unregister_callback(self, msg_id: str, callback: Callable[[dict], None]) -> None:
        """Remove a callback registration for *msg_id*."""
        callbacks = self._callbacks.get(msg_id)
        if not callbacks:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            return
        if not callbacks:
            self._callbacks.pop(msg_id, None)

    def _on_iopub_message(self, msg: dict) -> None:
        self.message_received.emit(msg)
        parent_id = str(msg.get("parent_header", {}).get("msg_id") or "")
        msg_type = str(msg.get("header", {}).get("msg_type") or "")

        if msg_type == "stream":
            text = str(msg.get("content", {}).get("text", ""))
            if text:
                self.stream_received.emit(parent_id, text)
        elif msg_type == "status":
            state = str(msg.get("content", {}).get("execution_state", ""))
            self.status_received.emit(parent_id, state)
        elif msg_type == "error":
            traceback_text = "\n".join(msg.get("content", {}).get("traceback", []))
            self.error_received.emit(parent_id, traceback_text)

        if parent_id and parent_id in self._callbacks:
            for callback in list(self._callbacks[parent_id]):
                try:
                    callback(msg)
                except Exception:
                    pass

    def request_json(
        self,
        kernel_client,
        code: str,
        timeout_ms: int = 2000,
    ) -> dict:
        """Execute code and collect JSON emitted through stream output."""
        if kernel_client is None:
            return {}
        self.attach(kernel_client)

        stream_parts: list[str] = []
        error_parts: list[str] = []
        done = {"value": False}
        loop = QEventLoop()
        timer = QTimer(self)
        timer.setSingleShot(True)

        def finish() -> None:
            if done["value"]:
                return
            done["value"] = True
            if timer.isActive():
                timer.stop()
            try:
                loop.quit()
            except Exception:
                pass

        def on_timeout() -> None:
            finish()

        timer.timeout.connect(on_timeout)
        msg_id = kernel_client.execute(code, silent=False, store_history=False)

        def on_message(msg: dict) -> None:
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                return
            msg_type = msg.get("header", {}).get("msg_type")
            if msg_type == "stream":
                stream_parts.append(msg.get("content", {}).get("text", ""))
            elif msg_type == "error":
                error_parts.extend(msg.get("content", {}).get("traceback", []))
            elif msg_type == "status" and msg.get("content", {}).get(
                "execution_state"
            ) == "idle":
                finish()

        self.register_callback(msg_id, on_message)
        timer.start(max(200, timeout_ms))
        loop.exec()
        self.unregister_callback(msg_id, on_message)

        if error_parts:
            return {"error": "\n".join(error_parts)}

        raw = "".join(stream_parts).strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some kernels print extra lines around JSON; use last non-empty line.
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            if not lines:
                return {}
            try:
                return json.loads(lines[-1])
            except json.JSONDecodeError:
                return {}

