"""Export helpers for signals, figures, and sessions."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from scipy.io import savemat, wavfile

from .signal_model import SignalRecord


class ExportManager:
    """Handles signal, figure, and session export formats."""

    def export_signal(self, record: SignalRecord, path: str | Path) -> None:
        """Export one signal record based on output extension."""
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        data = np.asarray(record.data, dtype=np.float64)

        if suffix == ".csv":
            time = record.start_time + np.arange(data.size, dtype=np.float64) / max(record.fs, 1e-9)
            stacked = np.column_stack([time, data])
            np.savetxt(file_path, stacked, delimiter=",", header="time,value", comments="")
            return

        if suffix == ".txt":
            np.savetxt(file_path, data)
            return

        if suffix == ".npy":
            np.save(file_path, data)
            return

        if suffix == ".wav":
            clipped = np.clip(data, -1.0, 1.0)
            wavfile.write(file_path, int(round(record.fs)), (clipped * 32767.0).astype(np.int16))
            return

        if suffix == ".mat":
            savemat(file_path, {record.name: data})
            return

        raise ValueError(f"Unsupported signal export format: {suffix}")

    def export_figure(self, figure: Figure, path: str | Path, *, dpi: int = 300) -> None:
        """Export matplotlib figure into PNG/SVG/PDF."""
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix not in {".png", ".svg", ".pdf"}:
            raise ValueError(f"Unsupported figure export format: {suffix}")
        figure.savefig(file_path, dpi=dpi, bbox_inches="tight")

    def save_session(self, records: list[SignalRecord], path: str | Path) -> None:
        """Save full analyzer session into .ksa JSON file."""
        payload = {
            "version": 1,
            "signals": [
                {
                    "id": record.id,
                    "name": record.name,
                    "data": np.asarray(record.data, dtype=np.float64).tolist(),
                    "fs": float(record.fs),
                    "unit": record.unit,
                    "start_time": float(record.start_time),
                    "source": record.source,
                    "parent_id": record.parent_id,
                    "color": record.color.name(),
                    "visible": bool(record.visible),
                    "preprocessing_log": list(record.preprocessing_log),
                }
                for record in records
            ],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
