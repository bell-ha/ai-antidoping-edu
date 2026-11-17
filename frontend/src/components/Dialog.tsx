import { useEffect, useRef, type ReactNode } from "react";

/**
 * 팝업. 사이트 규칙(DESIGN.md "뒤로가기"): 휴대폰·브라우저 뒤로가기는 사이트를 떠나지 않고 이 팝업만 닫는다.
 * 열릴 때 브라우저 기록에 한 칸을 더하고, 뒤로가기가 그 칸을 빼면 닫는다. 버튼으로 닫으면 더한 칸을 되돌린다.
 * onBack이 true를 돌려주면(예: 첫 안내의 앞 카드로) 닫지 않고 칸을 다시 더한다.
 */
export function Dialog({
  children,
  onClose,
  onBack,
  className,
  label,
  persistent,
}: {
  children: ReactNode;
  onClose: () => void;
  onBack?: () => boolean;
  persistent?: boolean; // 바깥 누르기·Esc·뒤로가기로 닫히지 않음(코드처럼 지금만 볼 수 있는 내용, 테스터 3·4)
  className?: string;
  label?: string;
}) {
  const close = useRef(onClose);
  const back = useRef(onBack);
  close.current = persistent ? () => {} : onClose;
  back.current = persistent ? () => true : onBack;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    // 라우터의 state(idx·key)를 그대로 두고 표시만 더한다 → 같은 주소에서 칸만 하나 늘어난다
    const push = () => window.history.pushState({ ...window.history.state, overlay: true }, "");
    push();
    const onPop = (e: PopStateEvent) => {
      if (e.state?.overlay) return; // 아직 팝업 칸 위(다른 팝업이 막 닫히며 남긴 칸 등)
      if (back.current?.()) push();
      else close.current();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      if (window.history.state?.overlay) window.history.back(); // 버튼·Esc로 닫음: 더한 칸을 뺀다(주소를 바꿔 이동했으면 칸이 이미 없음)
    };
  }, []);

  return (
    <div className="dialog-backdrop" onClick={() => close.current()}>
      <div className={`dialog${className ? ` ${className}` : ""}`} role="dialog" aria-modal="true" aria-label={label} onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
