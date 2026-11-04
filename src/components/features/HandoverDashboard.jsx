import React from "react";
import { ChevronDown, ArrowUpRight, Layers } from "lucide-react";
export default function HandoverDashboard({ state, data, onOpenChecklist }) {
  const ids = new Set(state.items.map((i) => i.id));
  const done = Object.entries(data.progress).filter(
    ([id, v]) => ids.has(id) && v.status === "done",
  ).length;
  const doing = Object.entries(data.progress).filter(
    ([id, v]) => ids.has(id) && v.status === "doing",
  ).length;
  const total = state.items.length;
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const overdue = (data.schedule.confirmed || []).filter(
    (r) => r.end < today && data.progress[r.item_id]?.status !== "done",
  );
  const categories = [...new Set(state.items.map((i) => i.category))];
  return (
    <div className="feature-card handover-dashboard">
      <h2>{state.handover.name}</h2>
      <p>{state.handover.scope}</p>
      <p>
        인계자 {state.handover.owner} → 인수자 {state.handover.successor} ·{" "}
        {state.handover.start_date} ~ {state.handover.end_date}
      </p>
      <div className="feature-metrics">
        <div>
          <span>인수 완료</span>
          <strong>
            {done} / {total}
          </strong>
        </div>
        <div>
          <span>진행 중</span>
          <strong>{doing}개</strong>
        </div>
        <div>
          <span>인수 진행률</span>
          <strong>{total ? Math.round((done / total) * 100) : 0}%</strong>
        </div>
        <div>
          <span>기한 지난 미완료 업무</span>
          <strong>{overdue.length}개</strong>
        </div>
      </div>
      <p>인계자의 내용 검토와 별도로, 인수자가 기록한 업무 수행 상태입니다.</p>
      {state.handover.end_date && (
        <p>
          인수인계 종료일까지{" "}
          {Math.max(
            0,
            Math.ceil(
              (Date.parse(state.handover.end_date) - Date.parse(today)) /
                86400000,
            ),
          )}
          일 남았습니다.
        </p>
      )}
      {data.schedule.confirmed && !data.schedule_current && (
        <div className="inline-warning">
          체크리스트 또는 기간이 변경되었습니다. 일정을 다시 생성·확정해 주세요.
        </div>
      )}
      <div className="category-section-heading">
        <div>
          <h3>분류별 인수 진행</h3>
          <p>분류를 펼치면 해당 업무와 진행 상태를 확인할 수 있어요.</p>
        </div>
        <span className="category-count">
          <Layers size={15} /> {categories.length}개 분류
        </span>
      </div>
      <div className="category-grid">
        {categories.map((c) => {
          const rows = state.items.filter((i) => i.category === c);
          const n = rows.filter(
            (i) => data.progress[i.id]?.status === "done",
          ).length;
          const active = rows.filter(
            (i) => data.progress[i.id]?.status === "doing",
          ).length;
          const percent = Math.round((n / rows.length) * 100);
          const complete = n === rows.length;
          return (
            <details className="category-checklists" key={c}>
              <summary>
                <span className="category-card-heading">
                  <span className="category-name">{c || "미분류"}</span>
                  <span className="category-completion">
                    {n}/{rows.length} 완료
                  </span>
                </span>
                <span
                  className="category-track"
                  role="progressbar"
                  aria-label={`${c || "미분류"} 완료율`}
                  aria-valuenow={percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span
                    className="category-track-done"
                    style={{ width: `${percent}%` }}
                  />
                </span>
                <span className="category-card-footer">
                  <span>
                    {complete
                      ? "모든 업무 인수 완료"
                      : `남은 업무 ${rows.length - n}개`}
                    {active > 0 && ` · 진행 중 ${active}개`}
                  </span>
                  <span className="category-expand-label">
                    업무 보기{" "}
                    <ChevronDown size={15} className="category-expand" />
                  </span>
                </span>
              </summary>
              <ul>
                {rows.map((item) => (
                  <li key={item.id}>
                    <button onClick={() => onOpenChecklist(item.id)}>
                      <span className="category-item-title">{item.title}</span>
                      <span className="category-item-status">
                        {
                          { todo: "미시작", doing: "진행 중", done: "완료" }[
                            data.progress[item.id]?.status || "todo"
                          ]
                        }
                      </span>
                      <span
                        className="category-item-link"
                        aria-label="체크리스트 보기"
                      >
                        <ArrowUpRight size={16} aria-hidden="true" />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          );
        })}
      </div>
      {categories.length === 0 && (
        <p className="category-empty">
          체크리스트를 만들면 분류별 진행 현황이 표시됩니다.
        </p>
      )}
      {!state.permissions.admin_read_only && (
        <>
          <h3>답변 대기 질문</h3>
          <p>{data.questions.filter((q) => !q.answer).length}건</p>
        </>
      )}
    </div>
  );
}
