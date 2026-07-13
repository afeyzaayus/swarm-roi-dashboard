import math

import numpy as np
import pytest

from src.math_utils import (
    distance,
    heading_of,
    horizontal_distance,
    limit,
    norm,
    normalize,
    vec,
    wrap_angle,
)


def test_vec_creates_3d_float_array():
    v = vec(1, 2)
    assert v.shape == (3,)
    assert v.dtype == float
    assert v[2] == 0.0


def test_distance_basic():
    assert distance(vec(0, 0, 0), vec(3, 4, 0)) == pytest.approx(5.0)


def test_horizontal_distance_ignores_z():
    assert horizontal_distance(vec(0, 0, 100), vec(3, 4, 0)) == pytest.approx(5.0)


def test_normalize_unit_length():
    n = normalize(vec(10, 0, 0))
    assert norm(n) == pytest.approx(1.0)
    assert n[0] == pytest.approx(1.0)


def test_normalize_zero_vector_stays_zero():
    assert norm(normalize(vec(0, 0, 0))) == 0.0


def test_limit_caps_magnitude():
    v = limit(vec(10, 0, 0), 3.0)
    assert norm(v) == pytest.approx(3.0)


def test_limit_keeps_small_vectors():
    v = vec(1, 1, 0)
    assert np.allclose(limit(v, 5.0), v)


def test_wrap_angle():
    assert wrap_angle(3 * math.pi) == pytest.approx(math.pi)
    assert abs(wrap_angle(-3 * math.pi)) == pytest.approx(math.pi)
    assert wrap_angle(0.5) == pytest.approx(0.5)


def test_heading_of():
    assert heading_of(vec(0, 1, 0)) == pytest.approx(math.pi / 2)
