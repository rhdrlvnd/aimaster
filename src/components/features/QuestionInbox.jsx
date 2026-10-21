import React, { useState } from "react";

export default function QuestionInbox({ questions, busy, run, setSelected }) {
  const [filter, setFilter] = useState("pending");
  const [selectedId, setSelectedId] = useState(null);
  const [drafts, setDrafts] = useState({});
  const visible = questions.filter(
    (q) => filter === "all" || (filter === "pending" ? !q.answer : !!q.answer),
  );
  const selected = visible.find((q) => q.id === selectedId) || visible[0];
  const pending = questions.filter((q) => !q.answer).length;
  return (
    <section className="feature-card question-inbox">
      <header>
        <h2>전달받은 질문</h2>
        <p className="subtext">
          인수자가 추가 확인을 요청한 내용을 확인하고 답변해 주세요.
        </p>
      </header>
      <div className="question-channels" aria-label="질문 상태">
        {[
          ["pending", `답변 대기 ${pending}`],
          ["answered", `답변 완료 ${questions.length - pending}`],
          ["all", `전체 ${questions.length}`],
        ].map(([value, label]) => (
          <button
            key={value}
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="question-inbox-layout">
        <nav className="question-inbox-list" aria-label="전달받은 질문 목록">
          {visible.map((q) => (
            <button
              key={q.id}
              aria-pressed={selected?.id === q.id}
              onClick={() => setSelectedId(q.id)}
            >
              <span>
                {q.answer ? "답변 완료" : "답변 대기"} · {q.author}
              </span>
              <strong>{q.question}</strong>
            </button>
          ))}
          {!visible.length && (
            <p className="subtext">
              {filter === "pending"
                ? "답변을 기다리는 질문이 없습니다."
                : "해당 질문이 없습니다."}
            </p>
          )}
        </nav>
        {selected && (
          <article className="question-inbox-detail">
            <span className="subtext">{selected.author}의 질문</span>
            <h3>{selected.question}</h3>
            {selected.ai_answer && (
              <details className="question-ai-context">
                <summary>AI가 안내한 내용과 문서 근거</summary>
                <p>{selected.ai_answer}</p>
                <div className="feature-actions">
                  {(selected.evidence || []).map((e, i) => (
                    <button key={i} onClick={() => setSelected(e)}>
                      근거 {i + 1}
                    </button>
                  ))}
                </div>
              </details>
            )}
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                await run(`/questions/${selected.id}/answer`, {
                  content: drafts[selected.id] ?? selected.answer ?? "",
                });
              }}
            >
              <label>
                인수자에게 전달할 답변
                <textarea
                  required
                  maxLength={8000}
                  disabled={busy}
                  value={drafts[selected.id] ?? selected.answer ?? ""}
                  onChange={(e) =>
                    setDrafts({ ...drafts, [selected.id]: e.target.value })
                  }
                  placeholder="업무 처리 방법이나 추가로 확인한 내용을 작성해 주세요."
                />
              </label>
              <button
                className="primary"
                disabled={
                  busy || !(drafts[selected.id] ?? selected.answer ?? "").trim()
                }
              >
                {selected.answer ? "답변 수정 저장" : "답변 전달"}
              </button>
            </form>
          </article>
        )}
      </div>
    </section>
  );
}
