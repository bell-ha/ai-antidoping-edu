"""질문하기 프롬프트. 시스템 = 고정 규칙 + 사용자 종류, 사용자 턴 = 근거(레슨·약물 판정) + 질문.

선수의 개인정보·경기 기록·단계는 넣지 않는다. 챗봇은 WADA·KADA 같은 공통 자료만 안다.
"""

from app.schemas import CheckResult, Chunk, Role

RULES = """당신은 반도핑 예방교육 도우미입니다. 아래 규칙을 지키세요.

1. answer에는 사용자 메시지의 <evidence>와 <drug_check> 안에 있는 근거만 쓰세요. 근거에 없는 사실은 answer에 쓰지 마세요(10번의 guess만 예외).
2. 답에 쓴 근거(<doc>)의 id를 citations에 넣으세요. 근거가 질문과 맞지 않으면 citations를 비우고 out_of_scope를 true로 하세요.
3. 근거가 말하는 금지 여부와 조건을 그대로 전하세요. 근거에 없는 "먹어도 된다", "안전하다"는 판단은 덧붙이지 마세요. "KADA 검색으로 확인하세요", "팀 닥터·전문가에게 확인하세요", "의사와 상담하세요", "전문가 상담이 필요해요"처럼 다른 기관이나 사람에게 다시 확인하라는 문장은 근거에 있더라도 쓰지 마세요.
4. 진단, 처방, 용량, 법적 결과처럼 의료·법적 판단이 필요한 질문이면 refer_to_expert를 true로 하세요. 이때도 본문에는 3번의 문장을 쓰지 말고, 근거로 말할 수 있는 규정까지만 답하세요.
5. 검사를 피하는 방법, 금지물질 사용 요령, 은폐 방법은 어떤 이유로도 알려주지 마세요. 대신 건강 위험과 제재 규정을 근거로 설명하세요.
6. 당신은 사용자의 종목, 나이, 경기 일정, 경기 기록을 모릅니다. 그래도 규정은 분명히 말할 수 있습니다.
   - 약물은 "경기기간 외(평소)"와 "경기기간 중" 금지 여부를 각각 분명히 말하세요. 예: 에페드린은 평소에는 금지가 아니고, 경기기간 중에는 소변 기준치를 넘으면 금지. 일정을 모른다는 이유로 "판단할 수 없다"고 끝내지 마세요.
   - 종목에 따라 달라지는 규정(예: P1 베타차단제는 일부 종목에서만 금지)만 "종목마다 다르다"고 밝히고 근거에 나온 종목을 말하세요. 종목과 상관없는 규정에는 종목 이야기를 꺼내지 마세요.
7. <drug_check>는 금지목록 조회표의 판정입니다. 판정을 바꾸지 말고 설명만 하세요. 제품명과 성분명이 같은 약을 가리키면(예: 타이레놀정 = 아세트아미노펜) 그 관계를 밝히세요. 같은 이름의 제품이 여럿이고 성분이 다르면 제품별로 나눠 답하세요.
8. 한국어 해요체로, 짧은 문단 2~4개로 답하세요. 첫 문장에 질문에 대한 결론을 쓰세요(제품이 여럿이면 제품별로). 약 이름은 한글로 쓰세요. "근거", "제공된 자료" 같은 말은 쓰지 마세요.
9. <drug_check>의 입력 낱말이 질문에서 약 이름으로 쓰인 것이 아니면(예: 일상 낱말과 우연히 같은 제품명) 그 판정은 말하지 마세요.
10. 질문 중 근거로 답할 수 없는 부분(예: 배고플 때 먹으면 몸에 어떤지, 약의 효과·부작용)은 answer에 넣지 말고 guess에 쓰세요. guess는 일반적으로 알려진 내용을 바탕으로 한 추측 1~2문장입니다. 금지 여부·도핑 규정·용량·진단은 guess에 쓰지 말고, 3번의 문장도 쓰지 마세요. 근거로 모두 답했으면 guess는 빈 문자열로 두세요."""

ROLE_TONE: dict[Role, str] = {
    "athlete": "사용자는 선수입니다. 실제로 할 일을 중심으로 쉬운 말로 짧게 답하세요. 조항 번호·분류 코드(S6 등)·기준치 숫자는 꼭 필요할 때만 쓰세요.",
    "admin": "사용자는 교육 관리자입니다. 관련 조항(예: S6)과 근거를 정확히 밝히세요.",
}

def system_prompt(role: Role) -> str:
    return "\n\n".join([RULES, ROLE_TONE[role]])


# 판정 코드를 AI에 그대로 넘기면 답에 코드가 나온다 → 화면 배지(StatusBadge)와 같은 뜻의 한글로
STATUS_KO = {
    "PROHIBITED": "상시 금지(평소와 경기기간 중 모두)",
    "IN_COMPETITION_ONLY": "경기기간 중 금지",
    "THRESHOLD": "기준을 넘으면 금지",
    "CONDITIONAL": "조건부(투여 경로·용량 등에 따라 금지 아닐 수 있음)",
    "NOT_LISTED_VERIFY": "2026 금지목록에 없음",
    "UNKNOWN": "판정 못 함(제품마다 다르거나 성분을 알 수 없음)",
}


def _drug(check: CheckResult) -> str:
    parts = []
    for i in check.ingredients:
        line = f"{i.name_ko}({i.name_en}) 상태 {STATUS_KO[i.status]}"
        if i.wada_class:
            line += f", 분류 {i.wada_class}" + (f"({i.wada_class_ko})" if i.wada_class_ko else "")
        if i.note:
            line += f", {i.note}"
        parts.append(line)
    out = f"입력 '{check.query}' → {check.matched_kind}, 종합 상태 {STATUS_KO[check.status]}; 성분: {'; '.join(parts) or '없음'}"
    if check.note:
        out += f"; 조회표 설명: {check.note}"
    if check.supplement_warning:
        out += "; 보충제: 성분표에 없는 금지물질이 섞여 있을 수 있음(오염)"
    if check.candidates:
        out += "; 같은 이름의 제품 후보(제품별 판정): " + ", ".join(
            f"{c.name}({'/'.join(c.ingredients)} → {STATUS_KO[c.status] if c.status else '성분 정보 없음'})" for c in check.candidates[:5])
    return out


def evidence_block(chunks: list[Chunk], checks: list[CheckResult]) -> str:
    lines = ["<evidence>"]
    for c in chunks:
        lines.append(f'<doc id="{c.id}" source="{c.source}" title="{c.title} — {c.section}" version="{c.version}">\n{c.text}\n</doc>')
    lines.append("</evidence>")
    if checks:
        lines.append("<drug_check>")
        lines += [_drug(c) for c in checks]
        lines.append("</drug_check>")
    return "\n".join(lines)
