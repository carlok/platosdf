"""
Flask API serving:
  GET  /api/grammar                        → list available grammars
  POST /api/evaluate                       → accept grammar JSON, return raymarcher params
  POST /api/mesh                           → accept grammar JSON, return GLB binary
  GET  /api/mesh/<name>                    → export a named grammar as GLB
  GET  /api/gallery                        → list evolution epochs (manifest.json)
  GET  /api/gallery/<epoch>/<filename>     → serve a file from gallery/epoch_NNNN/
"""

import io
import os
import json
import re
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.exceptions import BadRequest

from grammar_store import list_grammar_names, load_grammar
from sdf import SierpSphereEvaluator, extract_mesh

app = Flask(__name__)
CORS(app)

GRAMMAR_DIR = Path(os.environ.get("GRAMMAR_DIR", "/app/grammar"))
GALLERY_DIR = Path(os.environ.get("GALLERY_DIR", "/app/gallery"))

_GALLERY_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.(glb|json)$", re.IGNORECASE)


def _epoch_dir_for_gallery(epoch: int) -> Path | None:
    """Return the gallery epoch directory when it exists on disk."""
    if epoch < 0 or epoch > 9999:
        return None
    target_name = f"epoch_{epoch:04d}"
    if not GALLERY_DIR.is_dir():
        return None
    for child in GALLERY_DIR.iterdir():
        if child.is_dir() and child.name == target_name:
            return child
    return None


def _gallery_files(epoch_dir: Path) -> dict[str, Path]:
    """Map basenames to files in an epoch directory."""
    return {path.name: path for path in epoch_dir.iterdir() if path.is_file()}


def _lookup_gallery_file(epoch_dir: Path, filename: str) -> Path | None:
    """Return a gallery file path when filename is allowed and present."""
    if not _GALLERY_FILENAME_RE.fullmatch(filename):
        return None
    return _gallery_files(epoch_dir).get(filename)


@app.route("/api/grammar", methods=["GET"])
def list_grammars():
    return jsonify(list_grammar_names(GRAMMAR_DIR))


@app.route("/api/grammar/<name>", methods=["GET"])
def get_grammar(name: str):
    """Return the raw grammar JSON for a named preset."""
    try:
        grammar = load_grammar(GRAMMAR_DIR, name)
    except FileNotFoundError:
        return jsonify({"error": "Grammar not found"}), 404
    return jsonify(grammar)


@app.route("/api/evaluate", methods=["POST"])
def evaluate_grammar():
    """Accept grammar JSON, return the flat SDF description for the raymarcher."""
    try:
        grammar = request.get_json(force=True)
        ev = SierpSphereEvaluator(grammar)
        return jsonify(ev.to_raymarcher_json())
    except (BadRequest, KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid grammar payload"}), 400


@app.route("/api/mesh", methods=["POST"])
def mesh_from_grammar():
    """Accept grammar JSON, return a GLB mesh."""
    try:
        grammar = request.get_json(force=True)
        ev = SierpSphereEvaluator(grammar)
        res = grammar.get("render", {}).get("resolution", 128)
        bnd = grammar.get("render", {}).get("bounds", 1.8)
        mesh = extract_mesh(ev, resolution=res, bounds=bnd)
    except (BadRequest, KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid grammar payload"}), 400

    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    buf.seek(0)
    return send_file(buf, mimetype="model/gltf-binary", download_name="sierpsphere.glb")


@app.route("/api/mesh/<name>", methods=["GET"])
def mesh_named(name: str):
    """Export a named grammar file as GLB."""
    try:
        grammar = load_grammar(GRAMMAR_DIR, name)
        ev = SierpSphereEvaluator(grammar)
        res = grammar.get("render", {}).get("resolution", 128)
        bnd = grammar.get("render", {}).get("bounds", 1.8)
        mesh = extract_mesh(ev, resolution=res, bounds=bnd)
    except FileNotFoundError:
        return jsonify({"error": "Grammar not found"}), 404

    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    buf.seek(0)
    return send_file(buf, mimetype="model/gltf-binary", download_name=f"{name}.glb")


@app.route("/api/gallery", methods=["GET"])
def gallery_manifest():
    """Return the evolution manifest (list of epochs with fitness summaries)."""
    manifest_path = GALLERY_DIR / "manifest.json"
    if not manifest_path.exists():
        return jsonify([])
    return jsonify(json.loads(manifest_path.read_text()))


@app.route("/api/gallery/<int:epoch>/<filename>", methods=["GET"])
def gallery_file(epoch: int, filename: str):
    """Serve a file from gallery/epoch_NNNN/ (GLB, JSON, etc.)."""
    if not _GALLERY_FILENAME_RE.fullmatch(filename):
        return jsonify({"error": "Invalid filename"}), 400
    epoch_dir = _epoch_dir_for_gallery(epoch)
    if epoch_dir is None:
        return jsonify({"error": "Not found"}), 404
    file_path = _lookup_gallery_file(epoch_dir, filename)
    if file_path is None:
        return jsonify({"error": "Not found"}), 404
    if filename.endswith(".glb"):
        return send_file(str(file_path), mimetype="model/gltf-binary", download_name=filename)
    if filename.endswith(".json"):
        return jsonify(json.loads(file_path.read_text()))
    return send_file(str(file_path), download_name=filename)


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=debug)
