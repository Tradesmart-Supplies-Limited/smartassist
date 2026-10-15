"""BMS output must stay exactly as it was before the multi-client change.

bms_reference.json was made with the old code (main 7e24cb2): every word and its position for 4 invented
trucks. The same trucks are built now and compared word by word, position by position.
"""
import glob
import json
import os

import pytest

from bms_snapshot import digest, snapshot
from conftest import make_pretend_sample
from core.clients import bms
from core.pdf_builder import load_template

HERE = os.path.dirname(__file__)
REFERENCE = json.load(open(os.path.join(HERE, "bms_reference.json"), encoding="utf-8"))
SAMPLES = sorted(glob.glob(os.path.join(HERE, "..", "samples", "*.pdf")))


def test_bms_output_from_the_pretend_sample_is_unchanged():
    now = snapshot(load_template(make_pretend_sample(), bms))
    assert now == REFERENCE["pretend_words"]


@pytest.mark.skipif(not SAMPLES, reason="sample PDF not present")
def test_bms_output_from_the_real_sample_is_unchanged():
    now = snapshot(load_template(open(SAMPLES[0], "rb").read(), bms))
    assert [len(w) for w in now] == REFERENCE["sample_word_counts"]
    assert [digest(w) for w in now] == REFERENCE["sample_digests"]
