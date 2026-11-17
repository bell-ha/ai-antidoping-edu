import { Check, Copy } from "lucide-react";
import { useState } from "react";

/** 새 로그인 코드 전달: 코드 복사 + 선수에게 그대로 보낼 안내문. 코드 원문은 서버에 남지 않아 지금만 볼 수 있다. */
export function CodeHandoff({ name, code }: { name: string; code: string }) {
  const [copied, setCopied] = useState<"" | "code" | "message">("");
  const message = `${name} 선수님, 도핑방지 교육 사이트 안내예요.\n주소: ${window.location.origin}\n로그인 코드: ${code}\n처음 들어가면 사용 안내가 나와요. 일주일에 한 번 들어와서 이번 주 교육을 들어 주세요.`;
  const copy = (text: string, what: "code" | "message") =>
    navigator.clipboard?.writeText(text).then(
      () => setCopied(what),
      () => setCopied(""),
    );

  return (
    <div className="stack" style={{ gap: 12 }}>
      <div className="row" style={{ gap: 8 }}>
        <code className="issued-code" style={{ flex: 1 }}>
          {code}
        </code>
        <button className="btn-sub" onClick={() => copy(code, "code")} aria-label="코드 복사">
          {copied === "code" ? <Check size={16} /> : <Copy size={16} />} {copied === "code" ? "복사함" : "복사"}
        </button>
      </div>
      <div className="field">
        <span className="label">선수에게 보낼 안내문</span>
        <textarea className="input handoff-message" readOnly value={message} rows={4} onFocus={(e) => e.currentTarget.select()} />
      </div>
      <button className="btn-sub" onClick={() => copy(message, "message")}>
        {copied === "message" ? <Check size={16} /> : <Copy size={16} />} {copied === "message" ? "안내문을 복사했어요" : "안내문 복사"}
      </button>
    </div>
  );
}
