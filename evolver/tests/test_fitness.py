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
