import { ChevronDown } from "lucide-react";

export function Select<T extends string>({
  id,
  value,
  options,
  onChange,
  label,
}: {
  id: string;
  label?: string; // 화면에 보이는 <label for>가 없을 때(표 안의 셀 등) 접근 가능한 이름
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="select-wrap">
      <select id={id} className="select" aria-label={label} value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown size={20} />
    </div>
  );
}
