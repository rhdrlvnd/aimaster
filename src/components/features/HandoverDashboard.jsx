import React from "react";
export default function HandoverDashboard({ state, data }) {
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
    <div className="feature-card">
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
      <h3>분류별 인수 진행</h3>
      {categories.map((c) => {
        const rows = state.items.filter((i) => i.category === c);
        const n = rows.filter(
          (i) => data.progress[i.id]?.status === "done",
        ).length;
        return (
          <div className="category-progress" key={c}>
            <span>{c}</span>
            <progress value={n} max={rows.length} />
            <span>
              {n}/{rows.length}
            </span>
          </div>
        );
      })}
      <h3>답변 대기 질문</h3>
      <p>{data.questions.filter((q) => !q.answer).length}건</p>
    </div>
  );
}
