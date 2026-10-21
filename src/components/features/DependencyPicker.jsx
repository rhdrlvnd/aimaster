import React from "react";

export default function DependencyPicker({
  item,
  items,
  selected = [],
  onChange,
  defaultOpen = false,
}) {
  const candidates = items.filter((candidate) => candidate.id !== item.id);
  return (
    <div className="dependency-picker">
      <div className="dependency-selection" aria-live="polite">
        {selected.length ? (
          <>
            <strong>선행 업무 {selected.length}개 선택됨</strong>
            <ul>
              {candidates
                .filter((candidate) => selected.includes(candidate.id))
                .map((candidate) => (
                  <li key={candidate.id}>{candidate.title}</li>
                ))}
            </ul>
          </>
        ) : (
          <span>선행 업무 없음</span>
        )}
      </div>
      <details open={defaultOpen}>
        <summary aria-label={`${item.title} 선행 업무 선택`}>
          선행 업무 선택·변경
        </summary>
        <p>이 업무를 시작하기 전에 끝나야 하는 업무만 체크하세요.</p>
        <div className="dependency-options">
          {candidates.map((candidate) => (
            <label key={candidate.id}>
              <input
                type="checkbox"
                checked={selected.includes(candidate.id)}
                aria-label={`${item.title}의 선행 업무: ${candidate.title}`}
                onChange={(event) =>
                  onChange(
                    event.target.checked
                      ? [...selected, candidate.id]
                      : selected.filter((id) => id !== candidate.id),
                  )
                }
              />
              <span>{candidate.title}</span>
            </label>
          ))}
          {!candidates.length && <p>선택할 다른 업무가 없습니다.</p>}
        </div>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])}>
            선택 모두 해제
          </button>
        )}
      </details>
    </div>
  );
}
