"""Workspace tracking utilities for Kronos."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)


class WorkspaceManager(QObject):
    """Track variables available in the kernel."""

    workspace_changed = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._vars: dict[str, dict[str, str]] = {}
        self._connected_kc = None
        self._pending_msg: str | None = None
        self._buffer: list[str] = []

    def update_from_kernel(self, kernel_client) -> None:
        """Query the kernel for variables using %whos and update state."""
        if kernel_client is None:
            self.clear()
            return
        if self._connected_kc is not kernel_client:
            # Disconnect from the previous client to avoid leaked connections.
            self._disconnect_iopub()
            self._connected_kc = kernel_client
            self._connect_iopub()

        self._buffer = []
        try:
            self._pending_msg = kernel_client.execute(
                "%whos", silent=False, store_history=False
            )
        except Exception as exc:
            log.warning("workspace_manager: failed to query kernel: %s", exc)

    # ── Signal management ──────────────────────────────────────────

    def _connect_iopub(self) -> None:
        kc = self._connected_kc
        if kc is None:
            return
        if hasattr(kc, "iopub_channel") and hasattr(
            kc.iopub_channel, "message_received"
        ):
            kc.iopub_channel.message_received.connect(self._on_iopub_msg)

    def _disconnect_iopub(self) -> None:
        kc = self._connected_kc
        if kc is None:
            return
        if hasattr(kc, "iopub_channel") and hasattr(
            kc.iopub_channel, "message_received"
        ):
            try:
                kc.iopub_channel.message_received.disconnect(self._on_iopub_msg)
            except (TypeError, RuntimeError):
                pass

    # ── Message handling ───────────────────────────────────────────

    def _on_iopub_msg(self, msg: dict) -> None:
        try:
            if (
                not self._pending_msg
                or msg.get("parent_header", {}).get("msg_id") != self._pending_msg
            ):
                return

            msg_type = msg.get("header", {}).get("msg_type")
            if msg_type == "stream":
                self._buffer.append(msg.get("content", {}).get("text", ""))
            elif msg_type == "execute_result":
                self._buffer.append(
                    msg.get("content", {}).get("data", {}).get("text/plain", "")
                )
            elif (
                msg_type == "status"
                and msg.get("content", {}).get("execution_state") == "idle"
            ):
                self._pending_msg = None
                self._vars = self._parse_whos_output("\n".join(self._buffer))
                self.workspace_changed.emit(self._vars)
                self._buffer = []
        except Exception:
            log.exception("workspace_manager: error processing iopub message")

    @staticmethod
    def _parse_whos_output(output: str) -> dict[str, dict[str, str]]:
        variables: dict[str, dict[str, str]] = {}
        lines = [line for line in output.splitlines() if line.strip()]
        parsing = False
        for line in lines:
            if line.strip().startswith("Variable"):
                parsing = True
                continue
            if parsing and set(line.strip()) == {"-"}:
                continue
            if not parsing:
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                var_type = parts[1]
                value = " ".join(parts[2:]) if len(parts) > 2 else ""
                variables[name] = {"type": var_type, "value": value}
        return variables

    def get_variables(self) -> dict:
        """Return the current variable mapping."""
        return dict(self._vars)

    def clear(self) -> None:
        """Clear workspace variables."""
        self._vars = {}
        self.workspace_changed.emit(self._vars)
