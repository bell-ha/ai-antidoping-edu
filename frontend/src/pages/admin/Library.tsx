import { ArrowLeft, BookOpen, ExternalLink, MessageCircle } from "lucide-react";
import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { api, type LibraryDoc, type LibraryDocSummary } from "../../api";

// 교육 자료 열람(관리자). 질문하기가 근거로 쓰는 레슨 파일을 그대로 보여 준다(같은 파일, 같은 섹션 번호).

const SOURCE_LABEL: Record<string, string> = { WADA: "WADA", KADA: "KADA", ADEL: "ADEL" };

// 본문 표기: 빈 줄 = 문단, "- " = 목록, "출처:" 줄 = 출처 캡션, URL = 링크
function linkify(text: string): ReactNode[] {
  return text.split(/(https?:\/\/[^\s)]+)/g).map((part, i) =>
    /^https?:\/\//.test(part) ? (
      <a key={i} href={part} target="_blank" rel="noreferrer">
        {part}
      </a>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
}

function Body({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) blocks.push(<ul key={`l${blocks.length}`}>{list.map((x, i) => <li key={i}>{linkify(x)}</li>)}</ul>);
    list = [];
  };
  text.split("\n").forEach((raw) => {
    const line = raw.trim();
    if (!line) return flush();
    if (line.startsWith("- ")) return void list.push(line.slice(2));
    flush();
    if (line.startsWith("출처:")) blocks.push(<p key={blocks.length} className="caption lib-source">{linkify(line)}</p>);
    else blocks.push(<p key={blocks.length}>{linkify(line)}</p>);
  });
  flush();
  return <div className="lib-body">{blocks}</div>;
}

export function Library() {
  const { docId } = useParams();
  return docId ? <DocView docId={docId} /> : <DocList />;
}

function DocList() {
  const [docs, setDocs] = useState<LibraryDocSummary[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.library().then(setDocs, (e) => setError(e.message));
  }, []);

  // 선수 화면과 같은 대분류(A~M)로, 서버가 준 배정 순서 그대로 묶는다
  const groups = new Map<string, LibraryDocSummary[]>();
  for (const d of docs ?? []) groups.set(d.category, [...(groups.get(d.category) ?? []), d]);

  return (
    <>
      <div className="page-head">
        <h1 className="title">교육 자료</h1>
        <p className="muted">선수가 듣는 교육 300개이자, 질문하기가 답할 때 근거로 쓰는 자료예요. WADA·KADA 자료를 바탕으로 썼고, 교육마다 원문 링크가 있어요.</p>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="stack-lg">
        {[...groups].map(([group, items]) => (
          <section key={group} className="stack">
            <h2 className="heading">
              {group} <span className="caption">{items.length}개</span>
            </h2>
            <div className="lib-grid">
              {items.map((d) => (
                <Link key={d.doc_id} to={`/library/${d.doc_id}`} className="card lib-card">
                  <span className="row" style={{ gap: 8 }}>
                    <span className="chip-source">
                      <b>{SOURCE_LABEL[d.source] ?? d.source}</b>
                    </span>
                    <span className="caption num">섹션 {d.section_headings.length}개</span>
                  </span>
                  <strong>{d.title}</strong>
                  <span className="caption">{d.summary ?? d.section_headings.slice(0, 4).join(" · ")}</span>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

function DocView({ docId }: { docId: string }) {
  const [doc, setDoc] = useState<LibraryDoc | null>(null);
  const [error, setError] = useState("");
  const { hash } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    setDoc(null);
    api.libraryDoc(docId).then(setDoc, (e) => setError(e.message));
  }, [docId]);

  // AI 출처 칩에서 "#s3"처럼 섹션을 지정해 들어오면 그 섹션으로
  useEffect(() => {
    if (doc && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [doc, hash]);

  if (error) return <p className="error">{error}</p>;
  if (!doc) return null;
  const target = hash.slice(1);

  return (
    <>
      <div className="page-head">
        <Link to="/library" className="btn-sub small" style={{ alignSelf: "flex-start" }}>
          <ArrowLeft size={14} /> 교육 자료 목록
        </Link>
        <h1 className="title">{doc.title}</h1>
        <p className="muted">
          {SOURCE_LABEL[doc.source] ?? doc.source} 안내를 바탕으로 정리 · {doc.version}
          {!doc.reviewed && " · 연구진 검토 전"}
        </p>
      </div>

      <div className="grid">
        <aside className="span-4 stack sticky">
          <nav className="card stack" aria-label="이 문서의 섹션">
            <p className="label">
              <BookOpen size={14} style={{ verticalAlign: -2 }} /> 목차
            </p>
            <ol className="lib-toc">
              {doc.sections.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} aria-current={s.id === target ? "location" : undefined}>
                    {s.heading}
                  </a>
                </li>
              ))}
            </ol>
            <a className="btn-sub" href={doc.url} target="_blank" rel="noreferrer">
              원문 보기 <ExternalLink size={14} />
            </a>
          </nav>
        </aside>

        <article className="span-8 stack-lg">
          {doc.sections.map((s) => (
            <section key={s.id} id={s.id} className={`card stack lib-section${s.id === target ? " is-target" : ""}`}>
              <h2 className="heading">{s.heading}</h2>
              <Body text={s.text} />
              <button
                type="button"
                className="btn-sub small"
                style={{ alignSelf: "flex-start" }}
                onClick={() => navigate("/ask", { state: { question: `${s.heading}에 대해 더 알려줘` } })}
              >
                <MessageCircle size={14} /> 이 내용 AI에게 묻기
              </button>
            </section>
          ))}
        </article>
      </div>
    </>
  );
}
