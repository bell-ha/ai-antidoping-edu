import { CircleHelp } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/** 칸 이름 옆 ⓘ. 누르면 짧은 설명(휴대폰에서도 보이게 title이 아니라 누르는 방식). 바깥을 누르거나 화면을 움직이면 닫힌다.
 * 설명 상자는 화면 기준으로 띄워 표 스크롤 영역이나 화면 가장자리에서 잘리지 않게 한다(테스터 1·4·6: 왼쪽이 잘려 보임). */
export function Help({ text, label }: { text: string; label: string }) {
  return (
    <Pop text={text} label={`${label} 설명`} className="help-btn">
      <CircleHelp size={16} />
    </Pop>
  );
}

/** 본문 속 어려운 말. 점선 밑줄, 누르면 쉬운 풀이(content/glossary.ts). */
export function Term({ word, text }: { word: string; text: string }) {
  return (
    <Pop text={text} label={`${word} 뜻`} className="term-btn">
      {word}
    </Pop>
  );
}

function Pop({ text, label, className, children }: { text: string; label: string; className: string; children: ReactNode }) {
  const [pos, setPos] = useState<CSSProperties | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!pos) return;
    const close = (e: Event) => (e.type !== "click" || (ref.current && !ref.current.contains(e.target as Node))) && setPos(null);
    document.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [pos]);
  const toggle = () => {
    if (pos || !btn.current) return setPos(null);
    const r = btn.current.getBoundingClientRect();
    const width = Math.min(280, window.innerWidth - 16);
    const left = Math.min(Math.max(8, r.left + r.width / 2 - width / 2), window.innerWidth - width - 8);
    setPos({ position: "fixed", top: r.bottom + 6, left, width });
  };
  return (
    <span className="help" ref={ref}>
      <button ref={btn} type="button" className={className} aria-label={label} aria-expanded={!!pos} onClick={toggle}>
        {children}
      </button>
      {pos && (
        <span className="help-pop" role="note" style={pos}>
          {text}
        </span>
      )}
    </span>
  );
}
