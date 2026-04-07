"""
Flask API serving:
  GET  /api/grammar          → list available grammars
  POST /api/evaluate          → accept grammar JSON, return raymarcher params
  POST /api/mesh              → accept grammar JSON, return GLB binary
  GET  /api/mesh/<name>       → export a named grammar as GLB
"""

import json
import io
import os
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from sdf import SierpSphereEvaluator, extract_mesh

app = Flask(__name__)
CORS(app)

GRAMMAR_DIR = Path(os.environ.get("GRAMMAR_DIR", "/app/grammar"))


def _load_grammar(name: str) -> dict:
    p = GRAMMAR_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"Grammar '{name}' not found")
    return json.loads(p.read_text())


@app.route("/api/grammar", methods=["GET"])
def list_grammars():
    files = sorted(p.stem for p in GRAMMAR_DIR.glob("*.json") if p.stem != "schema")
    return jsonify(files)


@app.route("/api/grammar/<name>", methods=["GET"])
def get_grammar(name: str):
    """Return the raw grammar JSON for a named preset."""
    grammar = _load_grammar(name)
    return jsonify(grammar)


@app.route("/api/evaluate", methods=["POST"])
def evaluate_grammar():
    """Accept grammar JSON, return the flat SDF description for the raymarcher."""
    grammar = request.get_json(force=True)
    ev = SierpSphereEvaluator(grammar)
    return jsonify(ev.to_raymarcher_json())


@app.route("/api/mesh", methods=["POST"])
def mesh_from_grammar():
    """Accept grammar JSON, return a GLB mesh."""
    grammar = request.get_json(force=True)
    ev = SierpSphereEvaluator(grammar)
    res = grammar.get("render", {}).get("resolution", 128)
    bnd = grammar.get("render", {}).get("bounds", 1.8)
    mesh = extract_mesh(ev, resolution=res, bounds=bnd)

    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    buf.seek(0)
    return send_file(buf, mimetype="model/gltf-binary", download_name="sierpsphere.glb")


@app.route("/api/mesh/<name>", methods=["GET"])
def mesh_named(name: str):
    """Export a named grammar file as GLB."""
    grammar = _load_grammar(name)
    ev = SierpSphereEvaluator(grammar)
    res = grammar.get("render", {}).get("resolution", 128)
    bnd = grammar.get("render", {}).get("bounds", 1.8)
    mesh = extract_mesh(ev, resolution=res, bounds=bnd)

    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    buf.seek(0)
    return send_file(buf, mimetype="model/gltf-binary", download_name=f"{name}.glb")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
