"""Similitud coseno en Python sobre embeddings JSON (fallback portable a pgvector)."""
from __future__ import annotations

import math


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def mean_vector(vectors):
    vectors = [v for v in vectors if v]
    if not vectors:
        return None
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            acc[i] += v[i]
    n = len(vectors)
    return [x / n for x in acc]
