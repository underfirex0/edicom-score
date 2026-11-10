import pandas as pd
from edicom_score import scoring as S
from edicom_score.pipeline import classify, CLASS_LABEL

def test_classify_thresholds():
    assert classify(80) == "A" and classify(75) == "A" and classify(74.9) == "B"
    assert classify(60) == "B" and classify(45) == "C" and classify(30) == "D" and classify(29.9) == "E"
    assert classify(float("nan")) == "NR"

def test_anchors_monotone_where_expected():
    # more equity per DH of capital must never lower the solvency sub-score
    xs = pd.Series([-2, -1, 0, 0.25, 0.5, 1, 2, 5])
    ys = S.interp("headroom", xs)
    assert ys.is_monotonic_increasing

def test_weights_sum_to_one():
    w = S.CONFIG["pillar_w"]
    assert abs(sum(w.values()) - 1) < 1e-9

def test_caps_present():
    assert S.CONFIG["caps"] == {"neg_equity": 30, "legal_alert": 45}

def test_panel_invariants(svc):
    R = svc.store.R
    sc = R[R.classe != "NR"]
    assert sc.score.between(0, 100).all()
    # class is consistent with the score
    assert (sc.score.map(classify) == sc.classe).all()
    # negative-equity firms are capped at 30
    neg = sc[sc.CP_cur < 0]
    assert (neg.score <= 30).all()
    assert set(R.classe.unique()) <= set(CLASS_LABEL)
