import React, { useState } from "react";
import { ArrowUpRight, FileText, Trash2, Pencil, Check } from "lucide-react";
import DependencyPicker from "../features/DependencyPicker";

export default function ChecklistItem({
  item,
  items = [],
  number,
  busy,
  locked,
  readOnly = false,
  changed,
  edit,
  onDelete,
  setSelected,
}) {
  const [editing, setEditing] = useState(!item.title);
  const [showDependencies, setShowDependencies] = useState(false);
  const editable = editing && !locked;
  return (
    <article
      id={`checklist-${item.id}`}
      tabIndex={-1}
      className={"item checklist-card " + (item.reviewed ? "reviewed" : "")}
    >
      <div className="item-number">{String(number).padStart(2, "0")}</div>
      <div className="item-content">
        <div className="item-meta">
          <span className="category-label">{item.category || "미분류"}</span>
          <span
            className={
              "importance-badge " + (item.priority === "높음" ? "high" : "")
            }
          >
            중요도 {item.priority}
          </span>
          <span className={"review-status " + (item.reviewed ? "done" : "")}>
            {item.reviewed ? "검토 완료" : "미검토"}
          </span>
          <small>{item.origin === "ai" ? "AI 제안" : "직접 추가"}</small>
          <div className="item-header-actions">
            <button
              type="button"
              className="text-button item-dependencies-toggle"
              aria-expanded={showDependencies}
              aria-controls={`dependencies-${item.id}`}
              onClick={() => setShowDependencies(!showDependencies)}
            >
              선행 업무{" "}
              {(item.dependencies || []).length
                ? `${item.dependencies.length}개`
                : "없음"}
            </button>
            {!locked && (
              <button
                className="text-button item-edit"
                disabled={!!busy}
                onClick={() => setEditing(!editing)}
                aria-expanded={editable}
              >
                {editable ? <Check size={14} /> : <Pencil size={14} />}
                {editable ? "수정 접기" : "수정"}
              </button>
            )}
          </div>
        </div>
        {editable ? (
          <div className="checklist-editor">
            <div className="editor-meta">
              <label>
                분류
                <input
                  aria-label="분류"
                  disabled={!!busy}
                  value={item.category}
                  maxLength={40}
                  onChange={(e) => edit(item.id, "category", e.target.value)}
                />
              </label>
              <label>
                중요도
                <select
                  aria-label="중요도"
                  disabled={!!busy}
                  value={item.priority}
                  onChange={(e) => edit(item.id, "priority", e.target.value)}
                >
                  {["높음", "보통", "낮음"].map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              업무명
              <input
                aria-label="업무명"
                placeholder="전달할 업무 이름"
                disabled={!!busy}
                maxLength={160}
                value={item.title}
                onChange={(e) => edit(item.id, "title", e.target.value)}
              />
            </label>
            <label>
              업무 설명
              <textarea
                aria-label="업무 설명"
                placeholder="인수인계할 내용을 입력하세요"
                disabled={!!busy}
                maxLength={3000}
                value={item.description}
                onChange={(e) => edit(item.id, "description", e.target.value)}
              />
            </label>
            <div className="editor-help">
              <span>수정한 내용은 하단의 ‘변경 저장’으로 저장하세요.</span>
              <button
                className="text-button"
                aria-label="항목 삭제"
                disabled={!!busy}
                onClick={() => onDelete(item.id)}
              >
                <Trash2 size={14} />
                항목 삭제
              </button>
            </div>
          </div>
        ) : (
          <div className="checklist-reading">
            <h3>{item.title || "업무명을 입력해 주세요"}</h3>
            <p>{item.description || "등록된 설명이 없습니다."}</p>
          </div>
        )}
        {showDependencies && (
          <div
            className="checklist-dependencies"
            id={`dependencies-${item.id}`}
          >
            <strong>먼저 완료할 업무</strong>
            {!locked && !readOnly ? (
              <fieldset disabled={!!busy}>
                <DependencyPicker
                  item={item}
                  items={items}
                  selected={item.dependencies || []}
                  defaultOpen
                  onChange={(value) => edit(item.id, "dependencies", value)}
                />
              </fieldset>
            ) : (
              <p>
                {(item.dependencies || [])
                  .map(
                    (id) =>
                      items.find((i) => i.id === id)?.title || "연결된 업무",
                  )
                  .join(", ") || "선행 업무 없음"}
              </p>
            )}
            {(item.dependencies || []).map(
              (id) =>
                item.dependency_notes?.[id] && (
                  <details key={id}>
                    <summary>
                      {items.find((i) => i.id === id)?.title || "선행 업무"} ·
                      AI 제안 이유와 근거
                    </summary>
                    <p>{item.dependency_notes[id].reason}</p>
                    <blockquote>{item.dependency_notes[id].quote}</blockquote>
                  </details>
                ),
            )}
          </div>
        )}
        <div className="item-bottom">
          <div className="evidence-links">
            {item.evidence.length ? (
              item.evidence.map((e, j) => (
                <button
                  key={j}
                  onClick={() => setSelected({ ...e, itemTitle: item.title })}
                >
                  <FileText size={14} />
                  {e.kind === "visual"
                    ? `슬라이드 ${e.slide} · 이미지 근거`
                    : "원문 근거"}{" "}
                  {item.evidence.length > 1 ? j + 1 : ""}
                  <ArrowUpRight size={13} />
                </button>
              ))
            ) : (
              <span className="no-evidence">
                {item.origin === "ai"
                  ? changed
                    ? "근거 문서 연결이 끊겼습니다 · 현재 문서로 초안을 다시 생성해 주세요"
                    : "AI 항목의 원문 근거가 누락됐습니다 · 초안을 다시 생성해 주세요"
                  : "직접 추가한 항목 · 연결한 원문 없음"}
              </span>
            )}
          </div>
          {readOnly ? (
            <span className="review-check">인계자 검토 완료</span>
          ) : (
            <label className="review-check">
              <input
                type="checkbox"
                checked={item.reviewed}
                disabled={!!busy || locked}
                onChange={(e) => edit(item.id, "reviewed", e.target.checked)}
              />
              검토 완료
            </label>
          )}
        </div>
      </div>
    </article>
  );
}
