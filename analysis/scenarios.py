"""테스트 시나리오 (데모 모드의 "테스트 시나리오" 선택). 태그 규칙 하나씩과 그 경계를 확인한다.

기대 태그는 **규칙을 보고 손으로 적은 값**이다. export.py가 계산 결과와 비교해 다르면 실패한다
(계산값을 기대값으로 저장하면 테스트가 자기 자신을 확인하는 셈이 되므로).
  synthetic_trend : 합성 추세 모델(레포의 data/model_params.json). export와 레포 테스트가 확인한다.
  rnn             : 실데이터 RNN(private/models, 레포 밖). 그 파일이 있을 때만 테스트가 확인한다.
                    실모델은 σ가 합성보다 넓어 향상·감소 시나리오의 폭을 크게 잡았다.

시나리오는 페르소나 E(남자, 96kg급, 국내 대회, 특이 변화 없음)를 기준으로 행 몇 개만 바꿔 만든다.
체중 변화 시나리오는 체급 변경과 섞이지 않도록 최상위 체급(+109, 계체 109kg 초과)에서 만든다.
"""

import copy

PERSONA_EXPECT = {
    # 페르소나(논문 Figure용, 바꾸지 않음). A는 합성 기준 급상승이지만 실모델 σ에서는 +2σ 미만.
    "A": dict(label="선수 A", description="19세 남자 73kg · 최근 기록이 크게 오른 선수",
              expect={"synthetic_trend": ["rapid_improvement"], "rnn": ["baseline"]}),
    "B": dict(label="선수 B", description="27세 여자 59kg · 최근 기록이 내려간 선수",
              expect={"synthetic_trend": ["decline"], "rnn": ["baseline"]}),  # 여자 실모델 없음 → none
    "C": dict(label="선수 C", description="22세 남자 81→89kg · 체급을 올린 선수",
              expect={"synthetic_trend": ["weight_change"], "rnn": ["weight_change"]}),
    "D": dict(label="선수 D", description="25세 여자 64kg · 세계대회에 나간 선수",
              expect={"synthetic_trend": ["high_level"], "rnn": ["high_level"]}),  # 입력 기반 태그라 none이어도 붙음
    "E": dict(label="선수 E", description="23세 남자 96kg · 특이 변화 없는 선수",
              expect={"synthetic_trend": ["baseline"], "rnn": ["baseline"]}),
}


def _rows(e: dict) -> list[dict]:
    return copy.deepcopy(e["records"])


def _set(rows: list[dict], i: int, **fields) -> list[dict]:
    rows[i].update(fields)
    return rows


def _all_bw(rows: list[dict], bw: float, last: float | None = None) -> list[dict]:
    for r in rows:
        r["body_weight"] = bw
    if last is not None:
        rows[-1]["body_weight"] = last
    return rows


def _find(rows: list[dict], date: str) -> int:
    return next(i for i, r in enumerate(rows) if r["date"] == date)


# (id, 이름, 설명, 행 변환, 기대 태그(합성, 실모델), 기대 경고 코드)
SCENARIOS = [
    ("T01", "체중 증가 5kg 초과", "최상위 체급에서 직전 대회보다 계체 +6.5kg — 기록 변화 판단 대신 체중 변화",
     lambda e: _all_bw(_rows(e), 118.0, 124.5), ["weight_change"], ["weight_change"], []),
    ("T02", "체중 감소 5kg 초과", "최상위 체급에서 직전 대회보다 계체 −6.5kg",
     lambda e: _all_bw(_rows(e), 124.5, 118.0), ["weight_change"], ["weight_change"], []),
    ("T03", "경계: 체중 +5.0kg", "기준(±5kg 초과)에 딱 못 미침 — 체중 변화 태그 없음",
     lambda e: _all_bw(_rows(e), 112.0, 117.0), ["baseline"], ["baseline"], []),
    ("T04", "경계: 대륙대회 12개월 전", "마지막 대회 기준 정확히 12개월 전 대륙대회 — 높은 경기 수준",
     lambda e: (r := _rows(e)) and _set(r, _find(r, "2025-09"), competition_category="continent"),
     ["high_level"], ["high_level"], []),
    ("T05", "경계: 세계대회 15개월 전", "12개월 창 밖의 세계대회 — 높은 경기 수준 아님",
     lambda e: (r := _rows(e)) and _set(r, _find(r, "2025-06"), competition_category="world"),
     ["baseline"], ["baseline"], []),
    ("T06", "급격한 향상", "마지막 대회 합계 +45kg(용상) — 두 모델 모두 +2σ 넘음",
     lambda e: (r := _rows(e)) and _set(r, -1, clean_jerk=r[-1]["clean_jerk"] + 45),
     ["rapid_improvement"], ["rapid_improvement"], []),
    ("T07", "감소", "마지막 대회 합계 −45kg(용상) — 두 모델 모두 −2σ 아래",
     lambda e: (r := _rows(e)) and _set(r, -1, clean_jerk=r[-1]["clean_jerk"] - 45),
     ["decline"], ["decline"], []),
    ("T08", "오타 경고", "용상을 100kg 더 입력한 경우 — 비율·급변 경고 후, 확인하면 향상으로 계산",
     lambda e: (r := _rows(e)) and _set(r, -1, clean_jerk=r[-1]["clean_jerk"] + 100),
     ["rapid_improvement"], ["rapid_improvement"], ["ratio", "jump"]),
    ("T09", "비율 경고만", "합계는 같고 인상·용상 비율만 비정상 — 비율 경고, 태그는 그대로",
     lambda e: (r := _rows(e)) and _set(r, 2, snatch=170, clean_jerk=130), ["baseline"], ["baseline"], ["ratio"]),
]


def build(examples: dict) -> dict:
    """페르소나 예시(A~E)에 이름·설명·기대값을 붙이고 시나리오를 더한다."""
    out = {aid: {**PERSONA_EXPECT[aid], **ex, "warnings": []} for aid, ex in examples.items()}
    base = examples["E"]
    for sid, label, description, transform, synth, rnn, warnings in SCENARIOS:
        out[sid] = dict(label=label, description=description, sex=base["sex"], birth_year=base["birth_year"],
                        records=transform(base), expect={"synthetic_trend": synth, "rnn": rnn}, warnings=warnings)
    return out
