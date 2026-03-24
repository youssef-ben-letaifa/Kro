"""Bridge for executing code in the embedded kernel."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

log = logging.getLogger(__name__)

# Pending messages older than this (seconds) are considered stale and discarded.
_STALE_TIMEOUT = 60.0
# How often to run the stale-message sweep (milliseconds).
_SWEEP_INTERVAL_MS = 30_000


class KernelBridge(QObject):
    """Execute code in the IPython kernel and emit signals."""

    execution_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    output_ready = pyqtSignal(str)

    def __init__(self, kernel_client=None) -> None:
        super().__init__()
        self.kernel_client = None
        self._pending: dict[str, float] = {}  # msg_id -> timestamp
        self._failed: set[str] = set()
        self._completion_callbacks: dict[str, Callable[[str], None]] = {}

        # Periodic sweep of stale pending messages.
        self._sweep_timer = QTimer(self)
        self._sweep_timer.setInterval(_SWEEP_INTERVAL_MS)
        self._sweep_timer.timeout.connect(self._sweep_stale)
        self._sweep_timer.start()

        if kernel_client is not None:
            self.reconnect(kernel_client)

    # ── Public API ──────────────────────────────────────────────────

    def reconnect(self, kernel_client) -> None:
        """Attach (or re-attach) to a kernel client.

        Safe to call repeatedly — disconnects the previous client first.
        """
        if kernel_client is self.kernel_client:
            return
        self._disconnect_iopub()
        self.kernel_client = kernel_client
        self._connect_iopub()

    def execute_code(
        self,
        code: str,
        on_finished: Callable[[str], None] | None = None,
        silent: bool = False,
        store_history: bool = True,
    ) -> str | None:
        """Execute raw Python code in the kernel."""
        if self.kernel_client is None:
            self._emit_error("Kernel client is not available.", on_finished)
            return None
        try:
            msg_id = self.kernel_client.execute(
                code,
                silent=silent,
                store_history=store_history,
            )
        except Exception as exc:
            log.warning("kernel_bridge: execute() failed: %s", exc)
            self._emit_error(f"Kernel execution failed: {exc}", on_finished)
            return None
        self._pending[msg_id] = time.monotonic()
        if on_finished is not None:
            self._completion_callbacks[msg_id] = on_finished
        return msg_id

    def execute_file(self, path: str) -> None:
        """Execute a Python file in the kernel."""
        try:
            code = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            self.error_occurred.emit(f"Cannot read file: {exc}")
            return
        self.execute_code(code)

    def execute_file_or_code(self, value: str) -> None:
        """Execute a path if it exists, otherwise treat as code."""
        if "\n" not in value:
            candidate = Path(value)
            if candidate.is_file():
                self.execute_file(str(candidate))
                return
        self.execute_code(value)

    # ── Internal ────────────────────────────────────────────────────

    def _emit_error(self, message: str, callback: Callable[[str], None] | None) -> None:
        self.error_occurred.emit(message)
        self.execution_finished.emit("error")
        if callback is not None:
            try:
                callback("error")
            except Exception:
                pass

    def _connect_iopub(self) -> None:
        kc = self.kernel_client
        if kc is not None and hasattr(kc, "iopub_channel"):
            ch = kc.iopub_channel
            if hasattr(ch, "message_received"):
                ch.message_received.connect(self._on_iopub_msg)

    def _disconnect_iopub(self) -> None:
        kc = self.kernel_client
        if kc is not None and hasattr(kc, "iopub_channel"):
            ch = kc.iopub_channel
            if hasattr(ch, "message_received"):
                try:
                    ch.message_received.disconnect(self._on_iopub_msg)
                except (TypeError, RuntimeError):
                    pass

    def _on_iopub_msg(self, msg: dict) -> None:
        try:
            parent_id = msg.get("parent_header", {}).get("msg_id")
            if not parent_id or parent_id not in self._pending:
                return

            msg_type = msg.get("header", {}).get("msg_type")
            if msg_type == "stream":
                text = msg.get("content", {}).get("text", "")
                if text:
                    self.output_ready.emit(text)
            elif msg_type == "execute_result":
                text = msg.get("content", {}).get("data", {}).get("text/plain", "")
                if text:
                    self.output_ready.emit(text)
            elif msg_type == "error":
                traceback_text = "\n".join(msg.get("content", {}).get("traceback", []))
                self._failed.add(parent_id)
                self.error_occurred.emit(traceback_text)
            elif msg_type == "status" and msg.get("content", {}).get("execution_state") == "idle":
                self._complete(parent_id)
        except Exception:
            log.exception("kernel_bridge: error processing iopub message")

    def _complete(self, msg_id: str) -> None:
        """Mark a pending execution as complete and fire callbacks."""
        status = "error" if msg_id in self._failed else "ok"
        self._failed.discard(msg_id)
        self._pending.pop(msg_id, None)
        callback = self._completion_callbacks.pop(msg_id, None)
        if callback is not None:
            try:
                callback(status)
            except Exception:
                pass
        self.execution_finished.emit(status)

    def _sweep_stale(self) -> None:
        """Discard pending messages that have been waiting too long."""
        now = time.monotonic()
        stale = [mid for mid, ts in self._pending.items() if now - ts > _STALE_TIMEOUT]
        for msg_id in stale:
            log.warning("kernel_bridge: discarding stale pending msg %s", msg_id)
            self._pending.pop(msg_id, None)
            self._failed.discard(msg_id)
            callback = self._completion_callbacks.pop(msg_id, None)
            if callback is not None:
                try:
                    callback("error")
                except Exception:
                    pass
