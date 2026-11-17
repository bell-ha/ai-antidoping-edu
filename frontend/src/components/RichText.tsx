import { Fragment, type ReactNode } from "react";

// 교육 본문 표기(선수 레슨 화면과 관리자 교육 자료가 같이 씀): 빈 줄 = 문단, "- " = 목록, "| … |" = 표, "출처:" 줄 = 출처 캡션,
// **굵게**, URL = 링크. 화면마다 따로 그리다 관리자 쪽에 별표·표 기호가 그대로 보이던 문제(테스터 3·5·13)로 하나로 합침.

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s)]+)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={i}>{part.slice(2, -2)}</b>;
    if (/^https?:\/\//.test(part))
      return (
        <a key={i} href={part} target="_blank" rel="noreferrer">
          {part}
        </a>
      );
    return <Fragment key={i}>{part}</Fragment>;
  });
}

const cells = (line: string) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

function Table({ lines }: { lines: string[] }) {
  const rows = lines.filter((l) => !/^\|?\s*:?-{2,}/.test(l.trim())); // 구분 줄(|---|) 빼기
  const [head, ...body] = rows.map(cells);
  return (
    <div className="table-scroll">
      <table className="data-table rich-table">
        <thead>
          <tr>{head.map((c, i) => <th key={i}>{inline(c)}</th>)}</tr>
        </thead>
        <tbody>
          {body.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RichText({ text, sourceClass = "caption lesson-source" }: { text: string; sourceClass?: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let table: string[] = [];
  const flush = () => {
    if (list.length) blocks.push(<ul key={`l${blocks.length}`} className="lesson-ul">{list.map((x, i) => <li key={i}>{inline(x)}</li>)}</ul>);
    if (table.length) blocks.push(<Table key={`t${blocks.length}`} lines={table} />);
    list = [];
    table = [];
  };
  text.split("\n").forEach((raw) => {
    const line = raw.trim();
    if (!line) return flush();
    if (line.startsWith("|")) {
      if (list.length) flush();
      return void table.push(line);
    }
    if (line.startsWith("- ")) {
      if (table.length) flush();
      return void list.push(line.slice(2));
    }
    flush();
    blocks.push(line.startsWith("출처:") ? <p key={blocks.length} className={sourceClass}>{inline(line)}</p> : <p key={blocks.length}>{inline(line)}</p>);
  });
  flush();
  return <>{blocks}</>;
}
