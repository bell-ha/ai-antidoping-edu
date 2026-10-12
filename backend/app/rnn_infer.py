"""RNN(LSTM) 경기력 예측의 numpy 추론 (D2: 서버에 torch 없음).

연구진 모델(원고의 RNNRegressor)과 같은 연산을 numpy로 다시 쓴 것이다. 학습은 analysis/train_rnn.py가
torch로 하고, 가중치는 .npz로 내보낸다. 두 구현의 출력이 같은지는 train_rnn.py가 내보낼 때 검증한다
(최대 오차 1e-4 kg 미만이 아니면 내보내지 않음).

이 모듈은 numpy만 import한다 — 학습용 가상환경(torch)에서도 경로로 불러 검증에 쓸 수 있게.

연산:
  x_t = [(total_t − center)/scale, E_ec[ec_t], E_age[age_t], E_year[year_t]]   (모르는 토큰은 0 → 영벡터)
  LSTM 1층, 게이트 순서 i, f, g, o (PyTorch), h0 = c0 = 0, 실제 길이만큼만 진행
  예측 = Linear(H→H/2) → ReLU → Linear(H/2→1), 출력 × scale + center
"""

import numpy as np

WEIGHTS = ("emb_ec.weight", "emb_age.weight", "emb_year.weight", "rnn.weight_ih_l0", "rnn.weight_hh_l0",
           "rnn.bias_ih_l0", "rnn.bias_hh_l0", "head.0.weight", "head.0.bias", "head.3.weight", "head.3.bias")


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def encode(vocab: dict[str, int], tokens: list[str]) -> list[int]:
    """0은 학습에 없던 토큰(영벡터). 학습 중에는 실제 시점에 0이 들어간 적이 없으므로 호출 쪽이 경고해야 한다."""
    return [vocab.get(t, 0) for t in tokens]


def predict(w: dict[str, np.ndarray], center: float, scale: float, totals: list[float],
            ec: list[int], age: list[int], year: list[int]) -> float:
    """한 선수의 이력(시간순, 길이 ≥ 1)으로 다음 대회 합계(kg)를 예측한다."""
    n = len(totals)
    if not n or not (len(ec) == len(age) == len(year) == n):
        raise ValueError("이력 길이가 맞지 않습니다")
    x = np.concatenate([
        ((np.asarray(totals, np.float64) - center) / scale)[:, None],
        w["emb_ec.weight"][ec], w["emb_age.weight"][age], w["emb_year.weight"][year],
    ], axis=1)
    w_ih, w_hh = w["rnn.weight_ih_l0"], w["rnn.weight_hh_l0"]
    b = w["rnn.bias_ih_l0"] + w["rnn.bias_hh_l0"]
    hidden = w_hh.shape[1]
    h = np.zeros(hidden)
    c = np.zeros(hidden)
    for t in range(n):
        gates = w_ih @ x[t] + w_hh @ h + b
        i, f, g, o = np.split(gates, 4)
        c = _sigmoid(f) * c + _sigmoid(i) * np.tanh(g)
        h = _sigmoid(o) * np.tanh(c)
    z = np.maximum(w["head.0.weight"] @ h + w["head.0.bias"], 0.0)
    out = float((w["head.3.weight"] @ z + w["head.3.bias"])[0])
    return out * scale + center


def load(path) -> dict[str, np.ndarray]:
    with np.load(path) as f:
        missing = set(WEIGHTS) - set(f.files)
        if missing:
            raise ValueError(f"가중치 누락: {sorted(missing)}")
        return {k: f[k].astype(np.float64) for k in WEIGHTS}
