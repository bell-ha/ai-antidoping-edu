"""개인화 프롬프트 (D15). 시스템 = 고정 규칙 + 역할 톤 + 프로파일, 사용자 턴 = 근거 청크 + 질문.

프로파일은 태그 표시명·연령대·경기 수준만 넣는다. 원 기록, 대회명, 체중 수치는 넣지 않는다.
"""

from app.schemas import CheckResult, Chunk, ProfileRecord, Role

RULES = """당신은 반도핑 예방교육 도우미입니다. 아래 규칙을 지키세요.

1. 사용자 메시지의 <evidence> 안에 있는 근거만 사용해 답하세요. 근거에 없는 사실은 말하지 마세요.
2. 답에 쓴 근거의 id를 citations에 넣으세요. 근거가 질문과 맞지 않으면 citations를 비우고 out_of_scope를 true로 하세요.
3. 특정 약이나 보충제를 "먹어도 된다", "안전하다"고 단정하지 마세요. 최종 확인은 KADA 의약품 검색이나 팀 닥터에게 하라고 안내하세요.
4. 진단, 처방, 용량, 법적 결과처럼 의료·법적 판단이 필요한 질문이면 refer_to_expert를 true로 하세요.
5. 검사를 피하는 방법, 금지물질 사용 요령, 은폐 방법은 어떤 이유로도 알려주지 마세요. 대신 건강 위험과 제재 규정을 근거로 설명하세요.
6. 선수 개인을 평가하거나 낙인찍는 표현을 쓰지 말고, 교육 주제로만 이야기하세요. 교육 프로파일 태그나 선수의 경기력 변화를 답에서 언급하거나 이유로 들지 말고, 다룰 주제를 고르는 데만 쓰세요.
7. 한국어로, 짧은 문단 2~4개로 답하세요."""

ROLE_TONE: dict[Role, str] = {
    "athlete": "사용자는 선수입니다. 실제로 할 일을 중심으로 쉬운 말로 짧게 답하세요. 조항 번호는 꼭 필요할 때만 쓰세요.",
    "coach": "사용자는 지도자입니다. 규정 준수와 선수 지원 관점에서, 지도자가 확인하고 안내할 일을 체크리스트처럼 정리하세요. 특정 선수 개인에 대해서는 말하지 마세요.",
    "support": "사용자는 선수지원인력(트레이너, 팀 닥터, 약사 등)입니다. 관련 조항(예: S6)과 절차를 정확히 밝히세요.",
}

LEVEL_KO = {"junior": "주니어", "national": "국내 대회", "international": "국제 대회"}


def system_prompt(role: Role, profile: ProfileRecord | None, tag_labels: list[str]) -> str:
    parts = [RULES, ROLE_TONE[role]]
    if profile is not None:
        parts.append(
            "선수의 교육 프로파일: "
            f"연령대 {profile.age_band}, 경기 수준 {LEVEL_KO[profile.competition_level]}, "
            f"교육 프로파일 태그 {', '.join(tag_labels)}. "
            "이 프로파일과 관련된 교육 내용이 근거에 있으면 먼저 다루세요."
        )
    return "\n\n".join(parts)


def evidence_block(chunks: list[Chunk], check: CheckResult | None) -> str:
    lines = ["<evidence>"]
    for c in chunks:
        lines.append(f'<doc id="{c.id}" source="{c.source}" title="{c.title} — {c.section}" version="{c.version}">\n{c.text}\n</doc>')
    lines.append("</evidence>")
    if check is not None:
        names = ", ".join(f"{i.name_ko}({i.status})" for i in check.ingredients) or "없음"
        lines.append(
            "<check_result>조회표 판정(이 판정을 바꾸지 말고 설명만 하세요): "
            f"입력 '{check.query}', 상태 {check.status}, 성분 {names}, 사용 시기 {check.timing}, 국가 {check.country}"
            "</check_result>"
        )
    return "\n".join(lines)
