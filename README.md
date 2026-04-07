# SierpSphere

Generate 3D fractal-like structures inspired by the Sierpinski Gasket using spheres as the base seed. Boolean operations (add, subtract, intersect) are applied iteratively along polyhedral symmetry axes (tetrahedral, octahedral, icosahedral) to carve and grow complex "lace" geometry from a single sphere.

Two rendering paths: a **real-time GLSL raymarcher** in the browser for instant feedback, and a **Python SDF engine** that extracts meshes via marching cubes and exports GLB files for 3D printing or external tools.

```
sierpsphere/
├── docker-compose.yml
├── grammar/
│   ├── schema.json                 # JSON Schema for the DSL
│   └── sierpinski_classic.json     # example preset
├── engine/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── sdf.py                      # SDF evaluator, marching cubes, GLTF export
│   └── server.py                   # Flask REST API
└── viewer/
    ├── Dockerfile
    ├── nginx.conf
    └── index.html                  # Three.js + GLSL raymarcher
```

---

## Prerequisites

- **Podman** (and `podman-compose`, or Podman 4.7+ which ships `podman compose` natively)
- Alternatively, Docker + Docker Compose work identically — just replace `podman` with `docker` everywhere below

Verify your install:

```bash
podman --version
podman compose version   # or: podman-compose --version
```

If you only have `podman-compose` (the Python shim) installed via pip:

```bash
pip install podman-compose   # if needed
```

---

## First-time setup

### 1. Clone or enter the project

```bash
cd /path/to/sierpsphere
```

### 2. Build the containers

```bash
podman compose build
```

This builds two images:

| Image | Base | Purpose |
|-------|------|---------|
| `sierpsphere-engine` | `python:3.12-slim` | Flask API + SDF engine + marching cubes |
| `sierpsphere-viewer` | `nginx:alpine` | Static file server for the Three.js viewer |

### 3. Start the stack

```bash
podman compose up -d
```

| Service | URL | Description |
|---------|-----|-------------|
| engine | http://localhost:5000 | REST API (grammar evaluation, GLB export) |
| viewer | http://localhost:8001 | Interactive 3D viewer |

### 4. Open the viewer

Navigate to **http://localhost:8001** in your browser.

You should see the default Sierpinski-sphere rendered via the GLSL raymarcher. Use the right-hand panel to tweak parameters and hit **Apply (Raymarcher)** to re-render.

### 5. Verify the API

```bash
# List available grammar presets
curl http://localhost:5000/api/grammar

# Download a GLB mesh of the classic preset
curl -o sierpinski.glb http://localhost:5000/api/mesh/sierpinski_classic
```

---

## Daily workflow

### Starting work

```bash
podman compose up -d
```

### Checking status

```bash
podman compose ps
podman compose logs -f          # tail all logs
podman compose logs -f engine   # tail engine only
```

### Stopping

```bash
podman compose down
```

### Rebuilding after code changes

If you edit Python files (`engine/sdf.py`, `engine/server.py`):

```bash
podman compose up -d --build engine
```

If you edit the viewer (`viewer/index.html`):

```bash
podman compose up -d --build viewer
```

Rebuild everything:

```bash
podman compose up -d --build
```

### Watching engine logs while developing

```bash
podman compose logs -f engine
```

The Flask server runs in debug mode, but since the code is baked into the image you need to rebuild after edits. For a faster loop, mount the source:

```bash
# Development override: mount source for hot reload
podman compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Create a `docker-compose.dev.yml` if you want live-reloading:

```yaml
services:
  engine:
    volumes:
      - ./engine/sdf.py:/app/sdf.py:ro
      - ./engine/server.py:/app/server.py:ro
    environment:
      - FLASK_DEBUG=1
```

---

## Creating custom grammars

Drop a new JSON file into `grammar/`. The engine picks it up automatically (the directory is mounted into the container).

### Minimal example

```json
{
  "seed": {
    "type": "sphere",
    "radius": 1.0
  },
  "symmetry_group": "octahedral",
  "iterations": [
    {
      "operation": "subtract",
      "scale_factor": 0.4,
      "smooth_radius": 0.03
    }
  ]
}
```

### Full grammar reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `seed.type` | `sphere` \| `cube` \| `octahedron` | yes | Starting primitive |
| `seed.radius` | number > 0 | yes | Seed size |
| `seed.center` | [x,y,z] | no | Default `[0,0,0]` |
| `symmetry_group` | `tetrahedral` \| `octahedral` \| `icosahedral` | no | Default `tetrahedral` |
| **Per iteration:** | | | |
| `operation` | `subtract` \| `add` \| `intersect` | yes | Boolean op applied to parent SDF |
| `primitive` | `sphere` \| `cube` \| `octahedron` | no | Default `sphere` |
| `scale_factor` | 0 < n < 1 | yes | Child size relative to parent |
| `distance_factor` | number | no | Offset along axis. Default `1.0` |
| `smooth_radius` | number >= 0 | no | Blend softness. `0` = hard Boolean |
| `apply_to` | `all` \| `surface` \| `new` | no | Which parent nodes to expand |
| **Render hints:** | | | |
| `render.resolution` | 32–512 | no | Marching cubes grid density |
| `render.bounds` | number | no | Sampling volume half-extent |
| `render.color_mode` | `depth` \| `iteration` \| `normal` \| `solid` | no | Surface coloring strategy |

### Symmetry groups at a glance

| Group | Axes | Aesthetic |
|-------|------|-----------|
| Tetrahedral | 4 | Organic, crystalline, minimal |
| Octahedral | 6 | Denser, cubic feel |
| Icosahedral | 12 | Very dense, sphere-like lace |

### Tips for interesting results

- **Alternating subtract/add** iterations create the characteristic Sierpinski lace
- **`smooth_radius` > 0** prevents sharp edges and gives an organic look
- **`scale_factor` near 0.5** yields self-similar recursion; smaller values make sparser patterns
- **`distance_factor` < 1.0** pulls children inward, creating tighter nesting
- **`apply_to: "new"`** limits exponential growth — only the most recent children expand
- Be careful with **icosahedral + more than 3 iterations** — the operation count explodes (12^n children)

---

## API reference

All endpoints are served by the `engine` container on port 5000.

### `GET /api/grammar`

Returns a JSON array of available grammar preset names.

```bash
curl http://localhost:5000/api/grammar
# ["sierpinski_classic"]
```

### `POST /api/evaluate`

Accepts a grammar JSON body. Returns a flat SDF description (seed + operations array) that the raymarcher consumes directly.

```bash
curl -X POST http://localhost:5000/api/evaluate \
  -H "Content-Type: application/json" \
  -d @grammar/sierpinski_classic.json
```

Response shape:

```json
{
  "seed": { "type": "sphere", "center": [0,0,0], "radius": 1.0 },
  "operations": [
    { "bool_op": "subtract", "primitive": "sphere", "center": [...], "radius": 0.5, "smooth_k": 0.02 },
    ...
  ]
}
```

### `POST /api/mesh`

Accepts a grammar JSON body. Returns a binary GLB file.

```bash
curl -X POST http://localhost:5000/api/mesh \
  -H "Content-Type: application/json" \
  -d @grammar/sierpinski_classic.json \
  -o output.glb
```

### `GET /api/mesh/<name>`

Exports a named preset from `grammar/` as GLB.

```bash
curl -o classic.glb http://localhost:5000/api/mesh/sierpinski_classic
```

---

## Viewer controls

| Control | Action |
|---------|--------|
| **Drag** | Orbit camera around the fractal |
| **Scroll** | Zoom in/out (range: 1.5–10 units) |
| **Symmetry dropdown** | Switch polyhedral axis set |
| **Iterations slider** | 1–5 recursive steps |
| **Scale Factor slider** | 0.20–0.60 child/parent ratio |
| **Smooth K slider** | 0–0.100 blend radius |
| **Apply (Raymarcher)** | Regenerate the GLSL shader from current params |
| **Download GLB Mesh** | Send current grammar to the API, download the extracted mesh |

The viewer works **entirely client-side** for raymarching — the API is only needed for GLB mesh export and loading presets.

---

## Exporting for external use

### GLB for 3D printing or Blender

```bash
# From a preset
curl -o fractal.glb http://localhost:5000/api/mesh/sierpinski_classic

# From a custom grammar
curl -X POST http://localhost:5000/api/mesh \
  -H "Content-Type: application/json" \
  -d @grammar/my_custom.json \
  -o fractal.glb
```

The GLB can be opened directly in Blender, imported into slicer software, or viewed in any GLTF viewer.

### Higher resolution meshes

Set `render.resolution` in your grammar JSON (up to 512). Higher values produce smoother surfaces but take longer:

| Resolution | Grid points | Approx. time |
|------------|-------------|---------------|
| 64 | 262k | < 1s |
| 128 | 2M | ~2–5s |
| 256 | 16.7M | ~30–60s |
| 512 | 134M | several minutes, ~8GB RAM |

---

## Cleanup

### Stop and remove containers

```bash
podman compose down
```

### Remove built images

```bash
podman compose down --rmi all
```

### Remove everything including volumes

```bash
podman compose down --rmi all --volumes
```

### Prune dangling images after rebuilds

```bash
podman image prune -f
```

---

## Troubleshooting

### "Address already in use" on port 5000 or 8080

```bash
# Find what's using the port
lsof -i :5000
# Kill it or change the port mapping in docker-compose.yml
```

### Viewer shows "Loading..." but no fractal

The raymarcher runs entirely in the browser — no API needed for the default view. Check the browser console for WebGL errors. Ensure your browser supports WebGL 1.0+.

### GLB download fails

Verify the engine is running:

```bash
podman compose ps
podman compose logs engine
```

Common causes: missing Python dependencies (rebuild the image), grammar JSON syntax errors.

### Raymarcher is slow

Reduce iterations or switch from icosahedral to tetrahedral. Each iteration multiplies the SDF operation count by the number of symmetry axes (4, 6, or 12). Three iterations with icosahedral = 12 + 144 + 1728 = 1884 SDF evaluations per pixel per frame.

### Podman on macOS

Podman on macOS runs containers inside a Linux VM. Make sure it's initialized:

```bash
podman machine init    # first time only
podman machine start
```
