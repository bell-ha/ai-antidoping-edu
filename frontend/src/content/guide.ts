import { CalendarCheck, ChartColumn, CircleHelp, EyeOff, KeyRound, LayoutList, MessageCircle, PlayCircle, RotateCcw, Scale, Sparkles, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// 선수 안내 문구. 사용 설명서(Guide)와 첫 로그인 안내(Onboarding)가 같은 내용을 쓰므로 여기 한 곳에서 고친다.
// 넣지 않는 것: 단계·순위·위험 같은 말, 질문 내용을 관리자가 본다는 안내(사용자 결정).

export interface GuideStep {
  icon: LucideIcon;
  title: string;
  body: string;
}

export const GUIDE_STEPS: GuideStep[] = [
  { icon: CalendarCheck, title: "1. 일주일에 한 번 들어와요", body: "한 주(월~일)에 처음 들어올 때 이번 주 교육이 정해져요. 지난주에 못 들은 교육은 이번 주 목록에 남아 있어요. 교육 개수는 선수마다 달라요(실력을 평가한 게 아니에요)." },
  { icon: PlayCircle, title: "2. 교육 시작하기", body: "교육은 짧은 글이에요. 다 읽으면 아래 퀴즈 1문제를 풀어요. 답하면(맞든 틀리든) 그 교육은 완료예요. 해설을 꼭 읽어 보세요." },
  { icon: Zap, title: "3. 깜짝 퀴즈", body: "그날 처음 들어올 때 복습 문제가 나올 수 있어요. 지금까지 배운 교육에서 나오고, 전에 틀린 문제가 먼저 나와요." },
  { icon: MessageCircle, title: "4. 질문하기", body: "약 이름(예: 타이레놀, 아세트아미노펜)이나 규정을 물어보세요. 제품명으로 물어도 성분으로 찾아서 답해요. 평소와 경기기간 중(보통 경기 전날 밤 11시 59분부터 그 경기의 검사가 끝날 때까지) 규정이 다르면 둘 다 알려 줘요." },
  { icon: RotateCcw, title: "5. 내 학습 기록", body: "들은 교육과 퀴즈 정답률을 볼 수 있어요. 틀린 문제는 '오답 다시 풀기'에서 다시 풀고, 맞히면 목록에서 빠져요." },
  { icon: CircleHelp, title: "6. 이런 건 이렇게", body: "AI는 내 종목·성별·경기 일정을 몰라요. 필요하면 질문에 적어 주세요. 종목에 따라 다른 규정은 '종목마다 다르다'고 답해요. 답 아래의 출처(WADA·KADA)를 눌러 근거를 볼 수 있어요." },
];

/** 첫 로그인 안내 4장. 이름·이번 주 교육 수를 모르면(사용 설명서에서 다시 보기) 일반 문구로. */
export function introSlides(name?: string, lessonsThisWeek?: number): GuideStep[] {
  const count = lessonsThisWeek ? `이번 주 교육은 ${lessonsThisWeek}개예요` : "이번 주 교육을 들어요";
  return [
    {
      icon: Sparkles,
      title: name ? `반가워요, ${name}님` : "반가워요",
      body: "도핑방지 규정을 짧은 글과 퀴즈로 익히는 곳이에요. 일주일에 한 번 들어와서 이번 주 교육을 들으면 돼요.",
    },
    {
      icon: PlayCircle,
      title: count,
      body: "교육 하나는 짧은 글과 퀴즈 1문제예요. 답하면 맞든 틀리든 완료예요. 못 들은 교육은 다음 주에도 남아 있어요. 교육 개수는 선수마다 달라요(실력을 평가한 게 아니에요).",
    },
    {
      icon: Zap,
      title: "깜짝 퀴즈와 내 학습 기록",
      body: "그날 처음 들어올 때 배운 교육에서 복습 문제가 나올 수 있어요. 틀린 문제는 '내 학습 기록'에서 다시 풀 수 있어요.",
    },
    {
      icon: MessageCircle,
      title: "궁금하면 질문하기",
      body: "'타이레놀 먹어도 돼?'처럼 약 이름이나 규정을 물어보세요. AI는 내 종목·성별·경기 일정을 몰라서, 평소와 경기기간 중(보통 경기 전날 밤부터 그 경기 검사가 끝날 때까지)을 나눠 알려 줘요.",
    },
  ];
}

/** 관리자 첫 로그인 안내. 가장 먼저 알릴 것: 단계는 교육량이지 도핑 의심이 아니다(연구진 원고의 결론과 같음). */
export const ADMIN_SLIDES: GuideStep[] = [
  {
    icon: LayoutList,
    title: "관리자 화면이에요",
    body: "선수를 등록하고, 경기 기록을 넣고, 교육 진행을 보는 곳이에요. 이 안내를 닫으면 나오는 시작 체크리스트를 차례로 하면 돼요.",
  },
  {
    icon: Scale,
    title: "단계는 교육량이에요",
    body: "연구진 모델이 지난 기록으로 마지막 대회 합계를 예측해요. 실제 합계가 예측보다 많이 오른 선수일수록 높은 단계가 되고, 한 주 교육과 깜짝 퀴즈가 많아져요. 도핑 여부를 판단하는 점수가 아니에요.",
  },
  {
    icon: EyeOff,
    title: "선수에게는 단계 이름이 보이지 않아요",
    body: "선수는 이번 주 교육 개수만 봐요(개수로 짐작할 수는 있어요). 단계·순위·실제−예측은 관리자 화면에만 있어요. 선수가 단계를 물으면 질문하기가 '선수마다 다르고, 평가한 게 아니에요'라고 정해진 말로 답해요.",
  },
  {
    icon: KeyRound,
    title: "선수 등록과 코드 전달",
    body: "선수를 등록하면 로그인 코드가 한 번 나와요. 복사하거나 함께 나오는 안내문을 그대로 보내세요. 잃어버리면 선수 상세에서 다시 발급해요.",
  },
  {
    icon: ChartColumn,
    title: "진행 보기",
    body: "선수 표에서 이수·퀴즈·질문 수를 보고, 선수를 누르면 경기 기록·퀴즈 기록·질문 원문이 나와요. 표 위에서 CSV로 내보낼 수 있어요.",
  },
];
