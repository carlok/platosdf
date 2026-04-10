"""
Tests for fitness.py: _primitive_diversity and WEIGHTS sum.
Hard-gate and mesh tests are skipped without trimesh/scipy (use Podman for those).
"""
import pytest


# ── WEIGHTS ───────────────────────────────────────────────────────────────────

def test_weights_sum_to_one():
    from fitness import WEIGHTS
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


def test_weights_all_positive():
    from fitness import WEIGHTS
    for k, v in WEIGHTS.items():
        assert v > 0, f"Weight {k} is not positive: {v}"


def test_primitive_diversity_replaces_self_similarity():
    from fitness import WEIGHTS
    assert "primitive_diversity" in WEIGHTS
    assert "self_similarity" not in WEIGHTS


# ── _primitive_diversity ──────────────────────────────────────────────────────

def _g(seed, step_prims):
    return {
        "seed": {"type": seed},
        "iterations": [{"primitive": p} for p in step_prims],
    }


def test_diversity_all_same_scores_zero():
    from fitness import _primitive_diversity
    assert _primitive_diversity(_g("sphere", ["sphere", "sphere"])) == 0.0


def test_diversity_two_types_half():
    from fitness import _primitive_diversity
    score = _primitive_diversity(_g("sphere", ["cube", "cube"]))
    assert 0.4 <= score <= 0.65


def test_diversity_all_three_types_max():
    from fitness import _primitive_diversity
    score = _primitive_diversity(_g("sphere", ["cube", "octahedron"]))
    assert score >= 0.9


def test_diversity_seed_counted():
    from fitness import _primitive_diversity
    # seed=cube, steps all sphere → two distinct types
    score = _primitive_diversity(_g("cube", ["sphere", "sphere"]))
    assert score > 0.0


def test_diversity_step_mix_bonus():
    from fitness import _primitive_diversity
    # same as two-type but step prims vary → small bonus
    no_bonus = _primitive_diversity(_g("sphere", ["cube", "cube"]))
    bonus    = _primitive_diversity(_g("sphere", ["cube", "octahedron"]))
    assert bonus > no_bonus


def test_diversity_score_in_range():
    from fitness import _primitive_diversity
    from mutate import diverse_population
    for g in diverse_population(24):
        score = _primitive_diversity(g)
        assert 0.0 <= score <= 1.0, f"Score out of range: {score}"


def test_diversity_empty_iterations():
    from fitness import _primitive_diversity
    # Only seed, no steps — single type, score 0
    g = {"seed": {"type": "sphere"}, "iterations": []}
    assert _primitive_diversity(g) == 0.0


def test_diversity_single_step_same_as_seed():
    from fitness import _primitive_diversity
    g = {"seed": {"type": "cube"}, "iterations": [{"primitive": "cube"}]}
    assert _primitive_diversity(g) == 0.0


def test_diversity_single_step_different_from_seed():
    from fitness import _primitive_diversity
    g = {"seed": {"type": "cube"}, "iterations": [{"primitive": "sphere"}]}
    score = _primitive_diversity(g)
    assert score == 0.5  # two distinct types, no step mix bonus


def test_weights_expected_keys():
    from fitness import WEIGHTS
    expected = {
        "fractal_dimension", "curvature_variance", "symmetry_preservation",
        "normalised_S_V", "genus", "aspect_ratio", "min_wall_thickness",
        "min_feature_size", "drain_openings", "enclosed_voids", "no_islands",
        "thermal_mass_variance", "support_volume_ratio", "silhouette_complexity",
        "primitive_diversity",
    }
    assert set(WEIGHTS.keys()) == expected


def test_fail_returns_zero_fitness():
    from fitness import _fail
    result = _fail("no_islands")
    assert result["fitness"] == 0.0
    assert result["hard_gate_failed"] == "no_islands"
    assert result["scores"] == {}


# ── mesh-based tests (trimesh available in Podman) ────────────────────────────

def _unit_sphere_mesh():
    import trimesh
    return trimesh.creation.icosphere(subdivisions=3, radius=1.0)


def test_aspect_ratio_sphere():
    from fitness import _aspect_ratio
    mesh = _unit_sphere_mesh()
    score = _aspect_ratio(mesh)
    assert score == 1.0  # sphere is ~isotropic


def test_thermal_mass_sphere_high():
    from fitness import _thermal_mass
    mesh = _unit_sphere_mesh()
    score = _thermal_mass(mesh)
    # Sphere is perfectly uniform across octants → high score
    assert score > 0.8


def test_thermal_mass_returns_float_in_range():
    from fitness import _thermal_mass
    mesh = _unit_sphere_mesh()
    score = _thermal_mass(mesh)
    assert 0.0 <= score <= 1.0


def test_genus_sphere_zero():
    from fitness import _genus
    mesh = _unit_sphere_mesh()
    score = _genus(mesh)
    # Genus 0 → score 0.0
    assert score == 0.0


def test_compute_fitness_sphere_structure():
    import trimesh
    from fitness import compute_fitness, WEIGHTS
    mesh = _unit_sphere_mesh()
    g = {"seed": {"type": "sphere"}, "symmetry_group": "tetrahedral", "iterations": []}
    result = compute_fitness(mesh, g)
    assert "fitness" in result
    assert "scores" in result
    # Plain sphere is watertight single component — should not hard-gate
    if result.get("hard_gate_failed") is None:
        assert result["fitness"] > 0.0
        for k in WEIGHTS:
            assert k in result["scores"]
