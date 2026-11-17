import { CircleHelp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/** 칸 이름 옆 ⓘ. 누르면 짧은 설명(휴대폰에서도 보이게 title이 아니라 누르는 방식). 바깥을 누르면 닫힌다. */
export function Help({ text, label }: { text: string; label: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [open]);
  return (
    <span className="help" ref={ref}>
      <button type="button" className="help-btn" aria-label={`${label} 설명`} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <CircleHelp size={14} />
      </button>
      {open && (
        <span className="help-pop" role="note">
          {text}
        </span>
      )}
    </span>
  );
}
