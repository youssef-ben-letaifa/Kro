"""Signal import utilities for Signal Analyzer."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
from scipy.io import loadmat, wavfile
from scipy.io.wavfile import WavFileWarning

from .signal_model import SignalRecord


class SignalLoader:
    """Load signal records from files and session bundles."""

    def __init__(self, default_fs: float = 1_000.0) -> None:
        self._default_fs = float(default_fs)

    def load_file(self, path: str | Path) -> list[SignalRecord]:
        """Load one or more signals from file path."""
        file_path = Path(path)
        suffix = file_path.suffix.lower()

        if suffix == ".wav":
            return self._load_wav(file_path)
        if suffix in {".csv", ".txt"}:
            return self._load_text(file_path)
        if suffix == ".npy":
            return self._load_npy(file_path)
        if suffix == ".mat":
            return self._load_mat(file_path)
        if suffix == ".ksa":
            return self._load_ksa(file_path)

        raise ValueError(f"Unsupported signal format: {suffix}")

    def _load_wav(self, path: Path) -> list[SignalRecord]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", WavFileWarning)
            fs, data = wavfile.read(path)

        array = np.asarray(data)
        if np.issubdtype(array.dtype, np.integer):
            dtype = np.iinfo(array.dtype)
            scale = float(max(abs(dtype.min), abs(dtype.max)))
            if scale > 0.0:
                array = array.astype(np.float64) / scale
        else:
            array = array.astype(np.float64, copy=False)
        if array.ndim == 1:
            signals = [array]
        else:
            signals = [array[:, ch] for ch in range(array.shape[1])]

        records: list[SignalRecord] = []
        for idx, values in enumerate(signals):
            name = path.stem if idx == 0 else f"{path.stem}_ch{idx + 1}"
            records.append(
                SignalRecord.create(
                    name=name,
                    data=np.asarray(values, dtype=np.float64),
                    fs=float(fs),
                    source="file",
                    unit="",
                )
            )
        return records

    def _load_text(self, path: Path) -> list[SignalRecord]:
        data = np.loadtxt(path, delimiter="," if path.suffix.lower() == ".csv" else None)
        data = np.asarray(data, dtype=np.float64)
        if data.ndim == 1:
            return [
                SignalRecord.create(
                    name=path.stem,
                    data=data,
                    fs=self._default_fs,
                    source="file",
                )
            ]

        # First column can be time values if monotonic.
        first = data[:, 0]
        if data.shape[1] >= 2 and np.all(np.diff(first) > 0):
            dt = float(np.median(np.diff(first)))
            fs = 1.0 / dt if dt > 0 else self._default_fs
            values = data[:, 1]
            start_time = float(first[0])
            return [
                SignalRecord.create(
                    name=path.stem,
                    data=values,
                    fs=fs,
                    start_time=start_time,
                    source="file",
                )
            ]

        records: list[SignalRecord] = []
        for col in range(data.shape[1]):
            records.append(
                SignalRecord.create(
                    name=f"{path.stem}_col{col + 1}",
                    data=data[:, col],
                    fs=self._default_fs,
                    source="file",
                )
            )
        return records

    def _load_npy(self, path: Path) -> list[SignalRecord]:
        arr = np.load(path, allow_pickle=True)
        if isinstance(arr, np.ndarray) and arr.ndim == 1:
            return [
                SignalRecord.create(
                    name=path.stem,
                    data=arr,
                    fs=self._default_fs,
                    source="file",
                )
            ]

        arr = np.asarray(arr)
        records: list[SignalRecord] = []
        if arr.ndim == 2:
            for idx in range(arr.shape[1]):
                records.append(
                    SignalRecord.create(
                        name=f"{path.stem}_col{idx + 1}",
                        data=arr[:, idx],
                        fs=self._default_fs,
                        source="file",
                    )
                )
        else:
            records.append(
                SignalRecord.create(
                    name=path.stem,
                    data=arr.reshape(-1),
                    fs=self._default_fs,
                    source="file",
                )
            )
        return records

    def _load_mat(self, path: Path) -> list[SignalRecord]:
        payload = loadmat(path)
        records: list[SignalRecord] = []
        for key, value in payload.items():
            if key.startswith("__"):
                continue
            array = np.asarray(value)
            if array.ndim == 2 and 1 in array.shape:
                array = array.reshape(-1)
            if array.ndim != 1:
                continue
            if array.size < 2:
                continue
            records.append(
                SignalRecord.create(
                    name=key,
                    data=array.astype(np.float64),
                    fs=self._default_fs,
                    source="file",
                )
            )
        if records:
            return records
        raise ValueError("No 1D signal vectors found in MAT file.")

    def _load_ksa(self, path: Path) -> list[SignalRecord]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records: list[SignalRecord] = []
        for item in payload.get("signals", []):
            records.append(
                SignalRecord.create(
                    name=str(item.get("name", "signal")),
                    data=np.asarray(item.get("data", []), dtype=np.float64),
                    fs=float(item.get("fs", self._default_fs)),
                    unit=str(item.get("unit", "")),
                    start_time=float(item.get("start_time", 0.0)),
                    source="file",
                    parent_id=item.get("parent_id"),
                )
            )
            records[-1].visible = bool(item.get("visible", True))
            records[-1].preprocessing_log = [str(v) for v in item.get("preprocessing_log", [])]
        if records:
            return records
        raise ValueError("Session does not contain any signals.")
