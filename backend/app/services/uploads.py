"""Photos waiting to be saved: stored under data/uploads, deleted after 24 h (SPEC §9)."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

import cv2

from app import config
from app.analysis.engine import analyze, decode_image
from app.analysis.models import AnalysisResult


class NotAPhoto(ValueError):
    pass


def sample_files() -> dict[str, Path]:
    """The synthetic photos a user may pick. fixtures/real is never included."""
    samples: dict[str, Path] = {}
    for folder in config.SAMPLE_DIRS:
        for path in sorted(folder.glob("*.jpg")):
            samples[path.stem] = path
    return samples


_sample_hashes: dict[str, str] | None = None


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sample_hashes() -> dict[str, str]:
    """SHA-256 → sample name, so a dropped copy of a sample is still labelled synthetic."""
    global _sample_hashes
    if _sample_hashes is None:
        _sample_hashes = {_hash_bytes(path.read_bytes()): name for name, path in sample_files().items()}
    return _sample_hashes


def _meta_path(token: str) -> Path:
    return config.uploads_dir() / f"{token}.json"


def image_path(token: str) -> Path:
    return config.uploads_dir() / f"{token}.jpg"


def valid_token(token: str) -> bool:
    return len(token) == 32 and all(c in "0123456789abcdef" for c in token)


def read_meta(token: str) -> dict | None:
    if not valid_token(token):
        return None
    path = _meta_path(token)
    if not path.exists() or not image_path(token).exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_meta(token: str, meta: dict) -> None:
    _meta_path(token).write_text(json.dumps(meta), encoding="utf-8")


def clean_old_uploads(now: float | None = None) -> int:
    """Delete uploads older than the limit. Returns how many files went."""
    folder = config.uploads_dir()
    if not folder.exists():
        return 0
    cutoff = (now if now is not None else time.time()) - config.UPLOAD_MAX_AGE_H * 3600
    removed = 0
    for path in folder.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _preset_scale(settings: dict | None) -> float | None:
    presets = (settings or {}).get("microscope_presets") or {}
    if len(presets) == 1:
        return float(next(iter(presets.values())))
    return None


def _scale_meta(result: AnalysisResult) -> dict:
    """What the save flow must know about a photo. Kept here so it never has to trust the browser."""
    return {
        "width": result.width,
        "height": result.height,
        "um_per_px": result.um_per_px,
        "calibration": result.calibration,
        "grid_spacing_px": result.grid_spacing_px,
        "photo_volume_ml": result.photo_volume_ml,
    }


def store_and_analyze(data: bytes, filename: str | None, settings: dict | None = None) -> tuple[str, dict, AnalysisResult]:
    """Save an upload and analyze it. Runs in a worker thread: this is CPU work."""
    image = decode_image(data)
    if image is None:
        raise NotAPhoto("That file isn't a photo Thetis can read. Use a JPG or PNG.")
    clean_old_uploads()
    config.uploads_dir().mkdir(parents=True, exist_ok=True)

    token = uuid.uuid4().hex
    sample_name = sample_hashes().get(_hash_bytes(data))
    if data[:3] == b"\xff\xd8\xff":
        image_path(token).write_bytes(data)
    else:
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise NotAPhoto("That photo couldn't be converted to JPEG.")
        image_path(token).write_bytes(encoded.tobytes())

    preset = _preset_scale(settings)
    result = analyze(image, um_per_px=preset, calibration="preset")
    meta = {
        "token": token,
        "filename": filename,
        "synthetic": sample_name is not None,
        "source_name": sample_name or filename,
        **_scale_meta(result),
    }
    _write_meta(token, meta)
    return token, meta, result


def reanalyze_with_scale(token: str, um_per_px: float) -> tuple[dict, AnalysisResult]:
    """Run the analysis again with a scale the user drew by hand."""
    meta = read_meta(token)
    if meta is None:
        raise FileNotFoundError(token)
    image = cv2.imread(str(image_path(token)), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(token)
    result = analyze(image, um_per_px=um_per_px, calibration="manual")
    meta = meta | _scale_meta(result)
    _write_meta(token, meta)
    return meta, result


def analysis_payload(token: str, meta: dict, result: AnalysisResult) -> dict:
    return {
        "token": token,
        "url": f"/api/files/uploads/{token}.jpg",
        "filename": meta.get("filename"),
        "synthetic": meta.get("synthetic", False),
        "source_name": meta.get("source_name"),
        "width": result.width,
        "height": result.height,
        "um_per_px": result.um_per_px,
        "calibration": result.calibration,
        "grid_spacing_px": result.grid_spacing_px,
        "photo_volume_ml": result.photo_volume_ml,
        "detections": [d.model_dump() for d in result.detections],
        "engine_version": result.engine_version,
        "ms": result.ms,
    }


# Plain names for the sample menu
SAMPLE_LABELS = {
    "t03-today": ("T-03 today", "Bacterial pattern"),
    "slide-healthy-umbo": ("Healthy umbo", "Few dead, full guts"),
    "slide-vibrio-suspect": ("Dead shells, thin guts", "A bacterial pattern"),
    "slide-low-omega": ("Malformed D-stage", "No grid in view"),
    "slide-d-stage": ("Young D-stage", "Small larvae, two clumps"),
    "slide-eyed": ("Eyed larvae", "Large, no grid in view"),
}


def sample_list() -> list[dict]:
    rows = []
    for name in sample_files():
        label, note = SAMPLE_LABELS.get(name, (name, ""))
        rows.append({"name": name, "label": label, "note": note, "url": f"/api/samples/{name}/image"})
    return rows
