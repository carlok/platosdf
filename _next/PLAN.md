# g-sdf-evolver — Implementation Plan

Built from: PROMPT.txt + foundation.tex + SALVAGE.txt  
Math reference: foundation.tex (authoritative for all formulas)  
Predecessor: carlok/sierpsphere

---

## Guiding invariants (from PROMPT.txt)

- Every individual is a **G-invariant SDF** — structural, not measured
- Seed ↔ Group is a **bijection**: tetrahedron→Td, cube→Oh, icosahedron→Ih
- Child placement uses **fd_point(G, u, v)** ∈ FD(G), not a raw axis vector
- Every child is **Symmetrize_G(P, φ)** — orbit-replicated before Boolean op
- Grammar dict has **no `symmetry_group` field** — derived from seed.type
- **WEIGHTS must sum to 1.0** (test-enforced); no `symmetry_preservation` key

---

## Step 1 — evolver/sdf_metal.py  ★ foundation, do this first

**Keep verbatim:** `DEVICE`, `_smin`, `_smax`, `_sd_sphere`, `_sd_box`,
`extract_mesh_metal`, `device_info`

**Add — new primitive SDFs (PyTorch tensors):**
```
_sd_tetrahedron(pts, center, radius)
    md = max(-x-y-z, x+y-z, -x+y+z, x-y+z);  return (md - r) / √3
    (foundation.tex eq. 3)

_sd_icosahedron(pts, center, radius)
    φ = (1+√5)/2
    n1=(φ,1,0)/‖·‖, n2=(0,φ,1)/‖·‖, n3=(1,0,φ)/‖·‖  + sign permutations
    return max_i(|nᵢ·x|) · √(φ²+1)/φ  − r
    (foundation.tex eq. 5)
```

**Add — group geometry:**
```
GROUP_MATRICES: dict[str, torch.Tensor]   # (|G|, 3, 3) on DEVICE
    "tetrahedral"  → 24 matrices  (Td)
    "octahedral"   → 48 matrices  (Oh)
    "icosahedral"  → 120 matrices (Ih)
    Generate programmatically from axis-angle or hardcode from known generators.

FD_CORNERS: dict[str, list[np.ndarray]]   # 3 unit vectors per group
    "tetrahedral":  [(1,1,1)/√3, (1,1,0)/√2, (1,0,0)]
    "octahedral":   [(1,1,1)/√3, (1,1,0)/√2, (1,0,0)]  (smaller triangle)
    "icosahedral":  [(1,1,1)/√3, (φ,1,0)/‖·‖, (1,0,0)]

fd_point(group: str, u: float, v: float) -> np.ndarray
    # Barycentric on spherical triangle (foundation.tex eq. 1)
    # clamp: if u+v > 1, set v = 1-u
    p = (1-u-v)*c0 + u*c1 + v*c2
    return p / ‖p‖
```

**Add — orbit symmetrisation:**
```
symmetrize_g(pts, prim_fn, center, radius, group) -> torch.Tensor
    # Stack |G| evaluations; take channel-wise min  (foundation.tex eq. 2)
    # pts: (N, 3) on DEVICE
    # For each g in GROUP_MATRICES[group]:
    #   transformed = pts @ g.T
    #   evals[g] = prim_fn(transformed, center, radius)
    # return torch.stack(evals).min(dim=0).values
```

**Rewrite — evaluate_grammar_metal:**
- Seed SDF uses `_sd_tetrahedron` / `_sd_box` / `_sd_icosahedron`
- For each iteration: compute `φ = fd_point(group, it["fd_u"], it["fd_v"])`  
  scale by `it["scale_factor"]`, call `symmetrize_g(pts, prim_fn, φ, radius, group)`
- Apply smooth Boolean as before
- Remove all references to `distance_factor`, `apply_to` center computation

---

## Step 2 — engine/sdf.py

**Keep verbatim:** `SierpSphereEvaluator`, gallery/grammar endpoints logic

**Add — numpy mirrors of Step 1:**
```
_sd_tetrahedron_np, _sd_icosahedron_np
GROUP_MATRICES_NP (same matrices, numpy float64)
fd_point(group, u, v)         — identical to sdf_metal version
symmetrize_g_np(pts, ...)     — same orbit min, no torch
```

**Update `SierpSphereEvaluator`:** use `fd_u`/`fd_v` + `symmetrize_g_np`  
Remove `distance_factor`, `symmetry_group` field handling.

---

## Step 3 — evolver/mutate.py

**Keep verbatim:** `tournament_select`

**Replace constants:**
```python
PRIMITIVES  = ["tetrahedron", "cube", "icosahedron"]   # child prims (sphere ok too)
SYMMETRIES  = ["tetrahedral", "octahedral", "icosahedral"]
OPERATIONS  = ["subtract", "add", "intersect"]
SEED_TO_GROUP = {"tetrahedron": "tetrahedral",
                 "cube": "octahedral",
                 "icosahedron": "icosahedral"}
```

**Rewrite `random_grammar_pure(n_steps, seed_type)`:**
- `fd_u, fd_v` sampled uniform [0,1]; if u+v>1 swap to 1-u, 1-v
- No `distance_factor`, no `symmetry_group` in dict

**Rewrite `mutate(grammar, rate)`:**
- `fd_u` += N(0, 0.15), clamp [0,1]; same for `fd_v`; if sum>1 renormalise
- Seed type mutated at rate×0.15 → resample all `fd_u`/`fd_v` in new FD
- Remove `distance_factor` mutation

**Rewrite `crossover(a, b)`:**
- Each child inherits seed from one parent → derives group
- Ops borrowed freely from either parent's iteration list
- If inherited group ≠ donor group: resample `fd_u`, `fd_v` uniformly

**Rewrite `diverse_population(n)`:** equal thirds of each seed type

---

## Step 4 — evolver/grammar_name.py

**Rewrite entirely.** New encoding:
```
Display:  C.Ns4u12v34  (seed-char . op+prim+smooth_radius + u×100 + v×100)
Slug:     C.Ns4u12v34  (already POSIX-safe)

Seed chars:  tetrahedron→T  cube→C  icosahedron→I
Op chars (display):  subtract→-  add→+  intersect→x
Op chars (slug):     subtract→N  add→P  intersect→X
Prim chars:  tetrahedron→t  cube→c  icosahedron→i  sphere→s
smooth_radius:  int units of 0.005 (same as before)
u, v: two-digit integer × 100 (00–100), prefix u/v
```
No group prefix — implied by seed char.

---

## Step 5 — evolver/fitness.py

**Remove:** `_symmetry`, `_sym_axes`, `symmetry_preservation` from WEIGHTS

**Rebalance WEIGHTS** (must sum to 1.0):
```python
"fractal_dimension":     0.16,   # +0.03
"curvature_variance":    0.12,   # +0.03
"fill_ratio":            0.05,   # +0.02
# all others unchanged
# drain_openings: 0.05 (already reduced)
```

**Update `compute_fitness`:** remove `_symmetry` call; `fill_ratio` already added.

**`_fill_ratio` already present** — no change needed.

---

## Step 6 — evolver/evolver_native.py

**Keep verbatim:** `_worker_init`, `_worker_eval`, `evaluate_population`,
CLI flags (`--workers`, `--epochs`, `--resume`), multiprocessing spawn logic

**Update `build_seed_population`:** call `diverse_population()` (new version)

**Update `evaluate_individual`:** pass grammar to `sdf_metal` — no other changes
needed (grammar schema change is transparent here)

**Update `run()`:** remove any `symmetry_group` references in logging/saving

---

## Step 7 — evolver/tests/

Rewrite all three test files to match new grammar schema:

**test_mutate.py:**
- `PRIMITIVES` = {tetrahedron, cube, icosahedron}
- Grammar dicts use `fd_u`/`fd_v` not `distance_factor`
- Crossover: verify inherited seed from one parent
- `fd_u + fd_v <= 1` invariant tested

**test_grammar_name.py:**
- New encoding: seed chars T/C/I, u/v fields
- POSIX-safe slug test

**test_fitness.py:**
- `WEIGHTS` expected keys: no `symmetry_preservation`
- Sum still 1.0

---

## Step 8 — Dockerfiles + docker-compose.yml

**evolver/Dockerfile:** add `tetrahedron`/`icosahedron` — no Dockerfile change
needed (deps unchanged: numpy, trimesh, scipy, scikit-image, pytest)

**docker-compose.yml:** unchanged — evolver profile already removed

**engine/Dockerfile:** unchanged

---

## Build order

```
1. sdf_metal.py   — GROUP_MATRICES + fd_point + symmetrize_g + new primitives
2. engine/sdf.py  — numpy mirror
3. mutate.py      — new grammar schema
4. grammar_name.py
5. fitness.py     — weight rebalance
6. evolver_native.py — wire up
7. tests/         — rewrite all three
8. smoke test:    python evolver_native.py --epochs 1 --workers 1
```

## Verification

After Step 1:
```python
# Quick sanity — Ih orbit produces 120 copies
from sdf_metal import symmetrize_g, _sd_sphere, fd_point, DEVICE
import torch
pts = torch.zeros(1, 3, device=DEVICE)
φ = torch.tensor(fd_point("icosahedral", 0.3, 0.2), device=DEVICE)
result = symmetrize_g(pts, _sd_sphere, φ, 0.1, "icosahedral")
# Should return min distance from origin to any of 120 orbit sphere copies
```

After Step 8:
```bash
bash evolver/run_native.sh --epochs 2 --workers 4
# Expect: 3 seed types in initial population log
# Expect: no symmetry_preservation in fitness output
# Expect: shapes with visible G-orbit replication in epoch_0001/
```

---

## Status: complete (2026-04-11)

All 8 steps implemented and smoke-tested. 105 pytest tests passing.

### Post-implementation fixes

**Td group generators wrong** — `[C3([1,1,1]), σ_d([1,-1,0])]` only generates S3
(order 6, unsigned axis permutations). Fixed by adding `C2([1,0,0])` as a third
generator; this introduces the sign changes required to reach Td (order 24).

**Crossover step-count explosion** — crossover concatenated parent step lists with
no upper bound. Over many epochs the count reached 15+, producing degenerate
geometry. Fixed: both children are sliced to `MAX=5` after crossover.

**Island / near-island GLBs** — marching cubes at coarse `eval_resolution` creates
phantom bridges between nearly-disconnected regions. At save resolution these
resolve into separate components. Fix: `extract_mesh_metal` always drops components
with < 15% of the largest component's face count, at both eval and save resolution.
Only zero-fitness individuals are excluded from GLB output.

**`grammar_dir` vestigial** — config key and `grammar_store` import removed;
population is loaded from `gallery/population.json` on `--resume`.

### Config (current)
```json
eval_resolution: 40   (was 28 — raised to reduce phantom bridges)
save_resolution: 64
pop_size:        24
mutation_rate:   0.55
crossover_rate:  0.45
n_epochs:        50
save_top_k:      5
```
