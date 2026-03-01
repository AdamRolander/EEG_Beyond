"""
Parse XDF file and return streams, channels, markers, notes for UI.
"""

import os

try:
    import pyxdf
    import numpy as np
    PYXDF_AVAILABLE = True
except ImportError:
    PYXDF_AVAILABLE = False


def _stream_info(s: dict) -> dict:
    """Extract name, type, channel_count, srate from a stream dict."""
    name = "unknown"
    stype = ""
    n_ch = 0
    sr = 0.0
    info = s.get("info")
    if info is not None:
        if callable(getattr(info, "name", None)):
            name = info.name() or name
        elif isinstance(info, dict):
            n = info.get("name")
            if isinstance(n, (list, tuple)) and n and isinstance(n[0], (list, tuple)) and n[0]:
                name = str(n[0][0])
            elif isinstance(n, str):
                name = n
        if callable(getattr(info, "type", None)):
            stype = info.type() or stype
        elif isinstance(info, dict):
            t = info.get("type")
            if isinstance(t, (list, tuple)) and t and isinstance(t[0], (list, tuple)) and t[0]:
                stype = str(t[0][0])
            elif isinstance(t, str):
                stype = t
        if callable(getattr(info, "channel_count", None)):
            n_ch = int(info.channel_count()) if info.channel_count() else 0
        elif isinstance(info, dict):
            c = info.get("channel_count")
            if isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple)) and c[0]:
                try:
                    n_ch = int(c[0][0])
                except (TypeError, ValueError):
                    pass
        if callable(getattr(info, "nominal_srate", None)):
            try:
                sr = float(info.nominal_srate())
            except (TypeError, ValueError):
                pass
        elif isinstance(info, dict):
            r = info.get("nominal_srate")
            if isinstance(r, (list, tuple)) and r and isinstance(r[0], (list, tuple)) and r[0]:
                try:
                    sr = float(r[0][0])
                except (TypeError, ValueError):
                    pass
    if n_ch == 0 and "time_series" in s:
        ts = s["time_series"]
        if hasattr(ts, "shape") and len(ts.shape) >= 1:
            n_ch = ts.shape[0]
    return {"name": str(name), "type": str(stype), "channel_count": n_ch, "nominal_srate": sr}


def _channel_labels(s: dict) -> list:
    """Extract channel labels from stream (EEG)."""
    labels = []
    info = s.get("info")
    if info is not None:
        desc = info.get("desc") if isinstance(info, dict) else None
        if desc is None and hasattr(info, "desc"):
            desc = info.desc()
        if desc is not None:
            try:
                if hasattr(desc, "child"):
                    chs_node = desc.child("channels")
                    if chs_node is not None and hasattr(chs_node, "iter"):
                        for ch in chs_node.iter():
                            if hasattr(ch, "child_value"):
                                labels.append(ch.child_value("label") or "")
                elif isinstance(desc, dict):
                    chs = desc.get("channels", [])
                    for ch in (chs if isinstance(chs, list) else []):
                        labels.append(str(ch.get("label", ch.get("name", ""))))
            except Exception:
                pass
    if not labels and "time_series" in s:
        ts = s["time_series"]
        if hasattr(ts, "shape") and len(ts.shape) >= 1:
            labels = [f"Ch{i+1}" for i in range(ts.shape[0])]
    return labels


def parse_xdf(path: str) -> dict:
    """
    Parse XDF file. Returns:
      ok: bool
      error: str if ok is False
      streams: list of {name, type, channel_count, nominal_srate}
      channels: list of channel labels (from first EEG-like stream)
      markers: list of {time, code} or summary (from ImageryMarkers)
      notes: list of {trial_number, rating} (from ImageryTrialRatings)
    """
    if not PYXDF_AVAILABLE:
        return {"ok": False, "error": "pyxdf not installed"}
    if not os.path.isfile(path):
        return {"ok": False, "error": "File not found"}
    try:
        streams_data, _ = pyxdf.load_xdf(path)
    except Exception as e:
        return {"ok": False, "error": f"XDF read error: {e}"}
    if not streams_data:
        return {"ok": False, "error": "No streams in file"}
    streams = []
    channels = []
    markers = []
    notes = []
    eeg_stream = None
    markers_stream = None
    ratings_stream = None
    for s in streams_data:
        si = _stream_info(s)
        streams.append(si)
        name = (si.get("name") or "").lower()
        stype = (si.get("type") or "").lower()
        if "eeg" in name or "eeg" in stype:
            if eeg_stream is None:
                eeg_stream = s
        if "imagerymarkers" in name or "markers" in name:
            markers_stream = s
        if "imagerytrialratings" in name or "trialratings" in name or "ratings" in name:
            ratings_stream = s
    if eeg_stream is not None:
        channels = _channel_labels(eeg_stream)
        if not channels and "time_series" in eeg_stream:
            ts = eeg_stream["time_series"]
            if hasattr(ts, "shape"):
                channels = [f"Ch{i+1}" for i in range(ts.shape[0])]
    if markers_stream is not None:
        ts = markers_stream.get("time_series")
        t = markers_stream.get("time_stamps")
        if ts is not None and t is not None:
            try:
                ts = np.asarray(ts)
                t = np.asarray(t)
                if ts.size > 0:
                    if ts.ndim == 1:
                        markers = [{"time": float(t[0]), "code": int(ts[0])}]
                    else:
                        for i in range(min(ts.shape[1], 100)):
                            code = int(ts[0, i]) if ts.shape[0] > 0 else 0
                            markers.append({"time": float(t[i]), "code": code})
                    if len(markers) > 50:
                        markers = markers[:50] + [{"time": None, "code": f"... and {ts.shape[1] - 50} more"}]
            except Exception:
                markers = [{"time": None, "code": "Extraction error"}]
    if ratings_stream is not None:
        ts = ratings_stream.get("time_series")
        if ts is not None:
            try:
                ts = np.asarray(ts)
                if ts.size > 0 and ts.ndim >= 1:
                    n = ts.shape[1] if ts.ndim > 1 else 1
                    for i in range(min(n, 200)):
                        if ts.ndim == 1:
                            trial, rating = i + 1, int(ts[i])
                        else:
                            trial = int(ts[0, i]) if ts.shape[0] > 0 else i + 1
                            rating = int(ts[1, i]) if ts.shape[0] > 1 else 0
                        notes.append({"trial_number": trial, "rating": rating})
                    if n > 200:
                        notes = notes[:200] + [{"trial_number": "...", "rating": f"+{n - 200} more"}]
            except Exception:
                notes = [{"trial_number": "-", "rating": "Error"}]
    return {
        "ok": True,
        "streams": streams,
        "channels": channels,
        "markers": markers,
        "notes": notes,
    }
