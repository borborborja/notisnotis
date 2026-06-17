from django.test import TestCase

from stories.analysis import compute_bias_distribution, detect_blindspot
from stories.similarity import cosine, mean_vector


class _FakeSource:
    def __init__(self, bias):
        self.bias = bias


class _FakeArticle:
    def __init__(self, bias):
        self.source = _FakeSource(bias)


class SimilarityTests(TestCase):
    def test_cosine_identical(self):
        self.assertAlmostEqual(cosine([1, 0, 0], [1, 0, 0]), 1.0)

    def test_cosine_orthogonal(self):
        self.assertAlmostEqual(cosine([1, 0], [0, 1]), 0.0)

    def test_cosine_mismatched_or_empty(self):
        self.assertEqual(cosine([1, 2], [1]), 0.0)
        self.assertEqual(cosine([], [1]), 0.0)

    def test_mean_vector(self):
        self.assertEqual(mean_vector([[0, 0], [2, 4]]), [1.0, 2.0])
        self.assertIsNone(mean_vector([]))


class BlindspotTests(TestCase):
    def test_distribution_counts(self):
        arts = [_FakeArticle("left"), _FakeArticle("left"), _FakeArticle("center")]
        dist = compute_bias_distribution(arts)
        self.assertEqual(dist["left"], 2)
        self.assertEqual(dist["center"], 1)

    def test_blindspot_when_one_side_dominates(self):
        dist = {"left": 5, "lean_left": 3, "center": 0, "lean_right": 0, "right": 0}
        is_blind, side = detect_blindspot(dist)
        self.assertTrue(is_blind)
        self.assertEqual(side, "right")

    def test_no_blindspot_when_balanced(self):
        dist = {"left": 3, "lean_left": 0, "center": 1, "lean_right": 0, "right": 3}
        is_blind, _ = detect_blindspot(dist)
        self.assertFalse(is_blind)

    def test_no_blindspot_below_minimum_coverage(self):
        dist = {"left": 2, "lean_left": 0, "center": 0, "lean_right": 0, "right": 0}
        is_blind, _ = detect_blindspot(dist)
        self.assertFalse(is_blind)
