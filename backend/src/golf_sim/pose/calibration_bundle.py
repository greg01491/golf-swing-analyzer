"""Immutable camera evidence and atomic activation of accepted calibration bundles."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from golf_sim.config import Config

_ACTIVATION_LOCK = threading.RLock()


@contextmanager
def activation_guard() -> Iterator[None]:
    with _ACTIVATION_LOCK:
        yield


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def camera_signatures(config: Config, metadata: dict | None = None) -> dict:
    if metadata is not None:
        return capture_signatures_from_metadata(metadata)
    captures = (metadata or {}).get("cameras", {})
    signatures = {}
    for camera in config.cameras.devices:
        capture = captures.get(camera.role, {})
        rotated = camera.rotation_deg in (90, 270)
        recorded = metadata is not None
        controls = capture.get("geometry_controls", {})
        signatures[camera.role] = {
            "identity": capture.get("device_name") if recorded else camera.name,
            "width": (
                capture.get("width") if recorded else camera.height if rotated else camera.width
            ),
            "height": (
                capture.get("height") if recorded else camera.width if rotated else camera.height
            ),
            "rotation_deg": capture.get("rotation_deg") if recorded else camera.rotation_deg,
            "requested_fps": (
                capture.get("requested_fps", capture.get("fps")) if recorded else camera.fps
            ),
            "autofocus": (
                controls.get("autofocus", {}).get("readback") if recorded else camera.autofocus
            ),
            "focus": controls.get("focus", {}).get("readback") if recorded else camera.focus,
        }
    return signatures


def capture_signatures_from_metadata(metadata: dict) -> dict:
    return {
        role: {
            "identity": capture.get("device_name"),
            "width": capture.get("width"),
            "height": capture.get("height"),
            "rotation_deg": capture.get("rotation_deg"),
            "requested_fps": capture.get("requested_fps", capture.get("fps")),
            "autofocus": capture.get("geometry_controls", {}).get("autofocus", {}).get("readback"),
            "focus": capture.get("geometry_controls", {}).get("focus", {}).get("readback"),
        }
        for role, capture in metadata.get("cameras", {}).items()
    }


def compare_signatures(accepted: dict, current: dict) -> dict:
    differences = []
    unknown = []
    for role in sorted(set(accepted) | set(current)):
        before, after = accepted.get(role, {}), current.get(role, {})
        for field in (
            "identity",
            "width",
            "height",
            "rotation_deg",
            "requested_fps",
            "autofocus",
            "focus",
        ):
            first, second = before.get(field), after.get(field)
            if field in ("autofocus", "focus") and first is None and second is None:
                unknown.append(f"{role} {field} readback is unknown")
            elif first is None or second is None:
                unknown.append(f"{role} {field} evidence is missing")
            elif first != second:
                differences.append(f"{role} {field}: {first} -> {second}")
    return {
        "status": "incompatible" if differences else "unverified" if unknown else "compatible",
        "reasons": differences + unknown,
    }


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def publish_bundle(root: Path, calibration: Path, validation: dict, signatures: dict) -> dict:
    if validation.get("status") != "accepted":
        raise ValueError("only independently accepted camera geometry can be activated")
    identity_payload = {
        "version": 1,
        "calibration_sha256": fingerprint(calibration),
        "validation": validation,
        "signatures": signatures,
    }
    encoded = json.dumps(identity_payload, sort_keys=True, allow_nan=False).encode()
    bundle_id = hashlib.sha256(encoded).hexdigest()
    directory = root / "bundles" / bundle_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "Calib_rig.toml"
    if target.exists():
        if fingerprint(target) != identity_payload["calibration_sha256"]:
            raise ValueError("existing immutable calibration bundle was modified")
    else:
        with target.open("xb") as output:
            output.write(calibration.read_bytes())
    manifest = directory / "manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text()) != identity_payload:
            raise ValueError("existing immutable bundle manifest was modified")
    else:
        atomic_json(manifest, identity_payload)
    pointer = {"version": 1, "bundle_id": bundle_id, "ground_id": None}
    with activation_guard():
        atomic_json(root / "active.json", pointer)
    return {**pointer, "calib_file": str(target), "validation": validation}


def load_active_bundle(root: Path) -> dict | None:
    pointer_path = root / "active.json"
    if not pointer_path.exists():
        return None
    pointer = json.loads(pointer_path.read_text())
    bundle_id = pointer.get("bundle_id", "")
    if len(bundle_id) != 64 or any(character not in "0123456789abcdef" for character in bundle_id):
        raise ValueError("invalid calibration bundle identity")
    directory = root / "bundles" / bundle_id
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    encoded = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    if hashlib.sha256(encoded).hexdigest() != bundle_id:
        raise ValueError("calibration bundle manifest fingerprint mismatch")
    calibration = directory / "Calib_rig.toml"
    if fingerprint(calibration) != manifest["calibration_sha256"]:
        raise ValueError("calibration file fingerprint mismatch")
    return {**pointer, **manifest, "calib_file": str(calibration)}
