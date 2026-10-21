"""
Every pair of Setup options designed together, plus seeded random buildings, all checked against the design
invariants (tests/invariants.py).

Run size: the pairwise matrix always runs; random buildings: STRUCTOPTIMA_FUZZ_N (default 12; the nightly CI job
uses 300). A failing random case prints its seed, which reproduces it exactly:
    STRUCTOPTIMA_FUZZ_SEED=<seed> pytest tests/test_design_matrix.py -k random
"""
import logging
import os

import pytest

from src.design_pipeline import run_design
from tests.design_matrix import build, case_id, pairwise_cases, random_case
from tests.invariants import design_violations

logging.disable(logging.CRITICAL)

PAIRWISE = pairwise_cases()
N_RANDOM = int(os.environ.get("STRUCTOPTIMA_FUZZ_N", "12"))
SEEDS = [int(os.environ["STRUCTOPTIMA_FUZZ_SEED"])] if "STRUCTOPTIMA_FUZZ_SEED" in os.environ else \
    list(range(1000, 1000 + N_RANDOM))


def _check(case):
    gm, beams, inp = build(case)
    res = run_design(gm, beams, inp)
    bad = design_violations(res, inp)
    assert not bad, f"{case_id(case)} {case}\n" + "\n".join(bad[:25])
    return res


@pytest.mark.parametrize("case", PAIRWISE, ids=[f"{i:02d}-{case_id(c)}" for i, c in enumerate(PAIRWISE)])
def test_pairwise_matrix(case):
    _check(case)


@pytest.mark.parametrize("seed", SEEDS)
def test_random_building(seed):
    _check(random_case(seed))
