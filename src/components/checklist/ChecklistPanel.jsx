import React from "react";
import {
  CheckCheck,
  ChevronRight,
  FileText,
  ListChecks,
  Sparkles,
  Plus,
  LoaderCircle,
} from "lucide-react";
import GenerationProgress from "./GenerationProgress";
import ChecklistItem from "./ChecklistItem";

export default function ChecklistPanel({
  approveChecklist,
  saveChecklist,
  reopenChecklist,
  locked,
  state,
  busy,
  dirty,
  docs,
  readyDocs,
  generate,
  suggestDependencies,
  markAllReviewed,
  items,
  changed,
  filter,
  setFilter,
  reviewed,
  add,
  progress,
  elapsed,
  visible,
  edit,
  deleteItem,
  setSelected,
}) {
  const generating = busy === "generate";
  const remaining = items.length - reviewed;
  const nextAction = changed
    ? "문서가 변경됐어요. 새 초안을 생성한 뒤 검토해 주세요."
    : remaining > 0
      ? `내용과 선행 업무를 확인하고 남은 ${remaining}개 항목을 검토 완료로 표시해 주세요.`
      : dirty
        ? "모든 항목을 확인했어요. 변경 저장 후 최종 확정해 주세요."
        : "검토 내용이 저장됐어요. 최종 확정하면 일정을 만들 수 있어요.";
  return (
    <section className="review-panel">
      <div className="review-heading">
        <div>
          <h2>인수인계 체크리스트</h2>
          <p>
            {generating
              ? "등록된 문서를 분석해 새 체크리스트 초안을 만들고 있습니다."
              : locked
                ? "검토한 내용이 확정되었습니다."
                : state.source === "ai"
                  ? "내용과 선행 업무를 함께 검토한 뒤, 저장하고 최종 확정하세요."
                  : "문서를 등록하면 AI가 업무별 초안을 제안합니다."}
          </p>
        </div>
        <div className="checklist-ai-actions">
          {!generating && !locked && items.length > 0 && (
            <details className="review-ai-options">
              <summary>선행 업무 다시 제안 · 선택</summary>
              <div>
                <p>
                  초안 생성 시 선행 업무도 함께 제안됩니다. 다시 분석이 필요할
                  때만 사용하세요.
                </p>
                <p>
                  실행하면 기존 선행 관계가 바뀌고 검토 완료 표시가
                  초기화됩니다.
                </p>
                {dirty && <p>수정한 내용을 먼저 변경 저장해 주세요.</p>}
                <button
                  disabled={!!busy || locked || dirty || !items.length}
                  onClick={suggestDependencies}
                >
                  {busy === "dependencies"
                    ? "선행 업무 분석 중…"
                    : "AI로 선행 업무 다시 제안"}
                </button>
              </div>
            </details>
          )}
          <button
            className={items.length && !generating ? "" : "primary"}
            disabled={
              !!busy ||
              locked ||
              !docs.length ||
              readyDocs !== docs.length ||
              !state.llm_configured
            }
            onClick={generate}
          >
            {busy === "generate" ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}{" "}
            {busy === "generate"
              ? "초안 생성 중…"
              : items.length
                ? "AI 초안 다시 생성"
                : "AI 초안 생성"}
          </button>
        </div>
      </div>
      <div className="document-summary">
        <span>
          <FileText size={17} />
          {docs.length
            ? `분석 대상 문서 ${docs.length}개 · AI 분석 완료 ${readyDocs}개`
            : "등록된 업무 문서가 없습니다"}
          {busy === "upload" && " · 문서 처리 중"}
        </span>
      </div>
      {docs.length > 0 && readyDocs !== docs.length && (
        <div className="inline-warning">
          새 초안을 만들려면 업무 문서 탭에서 모든 문서의 AI 분석을 먼저 완료해
          주세요. 기존 체크리스트는 그대로 확인할 수 있습니다.
        </div>
      )}
      {!generating && changed && (
        <div className="inline-warning">
          현재 초안은 변경 전 문서로 만든 내용입니다. 삭제한 문서의 근거는
          확인할 수 없습니다. 현재 등록된 문서로 AI 초안을 다시 생성해 주세요.
        </div>
      )}
      {!generating && locked && (
        <div className="approved-banner">
          <CheckCheck size={20} />
          <div>
            <strong>체크리스트 검토를 마쳤어요</strong>
            <span>
              인수인계 일정 메뉴에서 AI 일정 초안을 작성하고 검토할 수 있습니다.
            </span>
          </div>
          <button disabled={!!busy} onClick={reopenChecklist}>
            검토 다시 열기
          </button>
        </div>
      )}
      {!generating && items.length > 0 && (
        <div className="review-toolbar">
          <div className="filters" role="group" aria-label="검토 상태 필터">
            {["전체", "미검토", "검토 완료"].map((f) => (
              <button
                key={f}
                aria-pressed={filter === f}
                className={filter === f ? "selected" : ""}
                onClick={() => setFilter(f)}
              >
                {f}
                <span>
                  {f === "전체"
                    ? items.length
                    : f === "미검토"
                      ? items.length - reviewed
                      : reviewed}
                </span>
              </button>
            ))}
          </div>
          <div className="checklist-review-actions">
            <button
              type="button"
              disabled={
                !!busy ||
                locked ||
                changed ||
                !items.length ||
                reviewed === items.length
              }
              onClick={markAllReviewed}
              title="전체 내용을 확인한 뒤 사용하세요. 필터와 관계없이 모든 항목을 검토 완료로 표시합니다."
            >
              <CheckCheck size={16} />
              모두 검토 완료로 표시
              {items.length > reviewed && ` (${items.length - reviewed}개)`}
            </button>
            <button
              className="text-button"
              disabled={!!busy || locked}
              onClick={add}
            >
              <Plus size={16} />
              항목 추가
            </button>
          </div>
        </div>
      )}
      {progress && busy !== "generate" && (
        <GenerationProgress
          progress={progress}
          busy={false}
          elapsed={elapsed}
        />
      )}
      {busy === "generate" ? (
        <GenerationProgress progress={progress} busy elapsed={elapsed} />
      ) : !items.length ? (
        <div className="empty checklist-empty">
          <ListChecks size={38} />
          <h3>전달할 업무를 함께 정리해요</h3>
          <p>
            ‘업무 문서’ 탭에서 문서를 등록한 뒤 ‘AI 초안 생성’을 눌러 주세요.
            <br />
            생성한 항목은 직접 수정하고 확정할 수 있습니다.
          </p>
          <div className="empty-pills">
            <span>업무 추출</span>
            <ChevronRight size={14} />
            <span>근거 확인</span>
            <ChevronRight size={14} />
            <span>전임자 검토</span>
          </div>
        </div>
      ) : !visible.length ? (
        <div className="empty">
          <CheckCheck size={34} />
          <h3>이 상태의 항목이 없습니다</h3>
        </div>
      ) : (
        <div className="items">
          {visible.map((item) => (
            <ChecklistItem
              key={item.id}
              item={item}
              items={items}
              number={items.findIndex((i) => i.id === item.id) + 1}
              busy={busy}
              locked={locked}
              changed={changed}
              edit={edit}
              onDelete={deleteItem}
              setSelected={setSelected}
            />
          ))}
        </div>
      )}
      {!generating && !locked && items.length > 0 && (
        <footer className="review-footer">
          <div>
            <strong>
              {reviewed}
              <span> / {items.length}개 검토 완료</span>
            </strong>
            <small aria-live="polite">{nextAction}</small>
            {dirty && remaining > 0 && (
              <small>검토 중에도 변경 내용을 저장할 수 있어요.</small>
            )}
          </div>
          <div>
            {dirty && (
              <button
                className="primary"
                disabled={!!busy || locked || !dirty}
                onClick={saveChecklist}
              >
                변경 저장
              </button>
            )}
            {!dirty && (
              <button
                className="primary"
                disabled={
                  !!busy ||
                  locked ||
                  dirty ||
                  !items.length ||
                  reviewed !== items.length ||
                  changed
                }
                onClick={approveChecklist}
              >
                <CheckCheck size={16} /> 검토 최종 확정
              </button>
            )}
          </div>
        </footer>
      )}
    </section>
  );
}
