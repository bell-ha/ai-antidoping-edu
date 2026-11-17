import { Check, Copy, Share2 } from "lucide-react";
import { useState } from "react";

/** 새 로그인 코드 전달: 코드 복사·공유 + 선수에게 그대로 보낼 안내문. 코드 원문은 서버에 남지 않아 지금만 볼 수 있다.
 * 이 화면은 바깥 누르기·Esc·뒤로가기로 닫히지 않고(Dialog persistent), 복사·공유하지 않고 닫으면 한 번 묻는다. */
export function CodeHandoff({ name, code, onClose }: { name: string; code: string; onClose: () => void }) {
  const [copied, setCopied] = useState<"" | "code" | "message" | "shared">("");
  const message = `${name} 선수님, 도핑방지 교육 사이트 안내예요.\n주소: ${window.location.origin}\n로그인 코드: ${code}\n코드는 본인만 쓰세요. 잃어버리면 관리자에게 새 코드를 받으면 돼요.\n처음 들어가면 사용 안내가 나와요. 일주일에 한 번 들어와서 이번 주 교육을 들어 주세요.`;
  const copy = (text: string, what: "code" | "message") =>
    navigator.clipboard?.writeText(text).then(
      () => setCopied(what),
      () => setCopied(""),
    );
  const share = () => navigator.share?.({ text: message }).then(() => setCopied("shared"), () => undefined);
  const close = () => {
    if (!copied && !window.confirm("코드를 복사하거나 보내지 않았어요. 닫으면 이 코드는 다시 볼 수 없어요(새로 발급은 가능). 닫을까요?")) return;
    onClose();
  };

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
        <textarea className="input handoff-message" readOnly value={message} rows={6} onFocus={(e) => e.currentTarget.select()} />
      </div>
      <div className="row wrap" style={{ gap: 8 }}>
        <button className="btn-sub" onClick={() => copy(message, "message")}>
          {copied === "message" ? <Check size={16} /> : <Copy size={16} />} {copied === "message" ? "안내문을 복사했어요" : "안내문 복사"}
        </button>
        {typeof navigator.share === "function" && (
          <button className="btn-sub" onClick={share}>
            <Share2 size={16} /> {copied === "shared" ? "보냈어요" : "카톡·문자로 보내기"}
          </button>
        )}
      </div>
      <button className="btn" onClick={close}>
        {copied ? "전달했어요 · 닫기" : "닫기"}
      </button>
    </div>
  );
}
