import { CalendarCheck, CircleHelp, MessageCircle, PlayCircle, RotateCcw, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const STEPS: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: CalendarCheck, title: "1. 일주일에 한 번 들어와요", body: "한 주(월~일)에 처음 들어올 때 이번 주 교육이 정해져요. 지난주에 못 들은 교육은 이번 주 목록에 남아 있어요." },
  { icon: PlayCircle, title: "2. 교육 시작하기", body: "교육은 짧은 글이에요. 다 읽으면 아래 퀴즈 1문제를 풀어요. 답하면(맞든 틀리든) 그 교육은 이수돼요. 해설을 꼭 읽어 보세요." },
  { icon: Zap, title: "3. 갑자기 퀴즈", body: "들어올 때 갑자기 퀴즈가 나올 수 있어요. 지금까지 배운 교육에서 나오고, 전에 틀린 문제가 먼저 나와요." },
  { icon: MessageCircle, title: "4. 질문하기", body: "약 이름(예: 타이레놀, 아세트아미노펜)이나 규정을 물어보세요. 제품명으로 물어도 성분으로 찾아서 답해요. 평소와 경기기간 중 규정이 다르면 둘 다 알려 줘요." },
  { icon: RotateCcw, title: "5. 내 학습 기록", body: "들은 교육과 퀴즈 정답률을 볼 수 있어요. 틀린 문제는 '오답 다시 풀기'에서 다시 풀고, 맞히면 목록에서 빠져요." },
  { icon: CircleHelp, title: "6. 이런 건 이렇게", body: "AI는 내 종목이나 경기 일정을 몰라요. 종목에 따라 다른 규정은 '종목마다 다르다'고 답해요. 답 아래의 출처(WADA·KADA)를 눌러 근거를 볼 수 있어요." },
];

export function Guide() {
  return (
    <>
      <div className="page-head">
        <h1 className="title">사용 설명서</h1>
        <p className="muted">처음이라면 이것만 읽고 시작하세요.</p>
      </div>
      <div className="cards-2">
        {STEPS.map(({ icon: Icon, title, body }) => (
          <section key={title} className="card stack">
            <Icon size={24} />
            <h2 className="heading">{title}</h2>
            <p className="muted">{body}</p>
          </section>
        ))}
      </div>
    </>
  );
}
