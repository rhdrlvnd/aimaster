import React, { useState } from "react";
import { api } from "../../services/api";
export default function QuestionsPanel({
  state,
  data,
  owner,
  busy,
  run,
  setSelected,
  refresh,
  prefix,
  setError,
}) {
  const [conversationId, setConversationId] = useState(""),
    [question, setQuestion] = useState(""),
    [board, setBoard] = useState(""),
    [replies, setReplies] = useState({});
  const selected = data.conversations.find((c) => c.id === conversationId);
  async function ask(e) {
    e.preventDefault();
    if (
      await run(
        "/qa/stream",
        { question, conversation_id: conversationId || null },
        "POST",
        true,
      )
    ) {
      const latest = await refresh();
      setConversationId(
        conversationId || latest.conversations.at(-1)?.id || "",
      );
      setQuestion("");
    }
  }
  async function remove() {
    if (!window.confirm("이 대화를 삭제할까요?")) return;
    try {
      await api(
        prefix + "/qa/" + conversationId + "?revision=" + data.revision,
        "DELETE",
      );
      setConversationId("");
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <div className="questions-grid">
      <section className="feature-card">
        <h2>문서 근거 AI 질문</h2>
        <div className="feature-actions">
          <select
            aria-label="대화 선택"
            disabled={busy}
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value)}
          >
            <option value="">새 대화</option>
            {data.conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
          {conversationId && (
            <button disabled={busy} onClick={remove}>
              대화 삭제
            </button>
          )}
        </div>
        <div className="chat-history">
          {!selected && (
            <p className="subtext">
              업무 절차를 질문하거나 “오늘 일정 완료 처리”처럼 요청할 수
              있습니다. 변경 작업은 대상을 확인한 뒤 실행합니다.
            </p>
          )}
          {selected?.messages.map((msg) => (
            <article className="chat-turn" key={msg.id}>
              <div className="chat-user">
                <strong>질문</strong>
                <p>{msg.question}</p>
              </div>
              <div className="chat-answer">
                <strong>
                  AI 답변{msg.insufficient ? " · 추가 확인 필요" : ""}
                </strong>
                <p>{msg.answer}</p>
                <div className="feature-actions">
                  {msg.evidence.map((e, i) => (
                    <button key={i} onClick={() => setSelected(e)}>
                      근거 {i + 1}
                      {e.kind === "visual" ? " · 이미지 해석" : ""}
                    </button>
                  ))}
                </div>
                {msg.action && !owner && (
                  <div className="action-proposal">
                    <strong>실행 전 대상 확인</strong>
                    <p>
                      {msg.action.kind === "progress"
                        ? "인수 상태 변경"
                        : "캘린더 등록"}
                      :{" "}
                      {msg.action.item_ids
                        .map(
                          (id) =>
                            state.items.find((i) => i.id === id)?.title || id,
                        )
                        .join(", ")}
                      {msg.action.kind === "progress"
                        ? " → " +
                          { todo: "미시작", doing: "진행 중", done: "완료" }[
                            msg.action.status
                          ]
                        : ""}
                    </p>
                    <button
                      disabled={
                        busy ||
                        msg.action_executed ||
                        msg.action_revision !== data.revision
                      }
                      onClick={() =>
                        run("/qa/action", {
                          conversation_id: selected.id,
                          message_id: msg.id,
                        })
                      }
                    >
                      {msg.action_executed ? "처리 완료" : "확인하고 실행"}
                    </button>
                    {!msg.action_executed &&
                      msg.action_revision !== data.revision && (
                        <small>자료가 변경되어 다시 요청해야 합니다.</small>
                      )}
                  </div>
                )}
                {!owner && msg.insufficient && (
                  <button onClick={() => setBoard(msg.question)}>
                    인계자 질문으로 옮기기
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
        <form onSubmit={ask}>
          <label>
            업무 질문
            <textarea
              required
              maxLength={4000}
              disabled={busy || state.status !== "approved"}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="업무 처리 절차나 궁금한 내용을 입력하세요."
            />
          </label>
          <button
            className="primary"
            disabled={busy || state.status !== "approved" || !question.trim()}
          >
            AI에게 질문
          </button>
        </form>
      </section>
      <section className="feature-card">
        <h2>인계자에게 질문</h2>
        <p>AI 답변과 별도로 인계자가 직접 작성한 답변을 확인합니다.</p>
        {!owner && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (await run("/questions", { content: board })) setBoard("");
            }}
          >
            <label>
              추가 확인할 내용
              <textarea
                required
                maxLength={8000}
                disabled={busy}
                value={board}
                onChange={(e) => setBoard(e.target.value)}
              />
            </label>
            <button disabled={busy || !board.trim()}>질문 등록</button>
          </form>
        )}
        {data.questions.length === 0 && (
          <p className="subtext">등록된 질문이 없습니다.</p>
        )}
        {[...data.questions].reverse().map((q) => (
          <article className="board-question" key={q.id}>
            <strong>
              {q.answer ? "답변 완료" : "답변 대기"} · {q.author}
            </strong>
            <p>{q.question}</p>
            {q.answer && (
              <div className="human-answer">
                <strong>{q.answered_by}의 답변</strong>
                <p>{q.answer}</p>
              </div>
            )}
            {owner && (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  await run("/questions/" + q.id + "/answer", {
                    content: replies[q.id] ?? q.answer ?? "",
                  });
                }}
              >
                <label>
                  직접 답변
                  <textarea
                    required
                    disabled={busy}
                    value={replies[q.id] ?? q.answer ?? ""}
                    onChange={(e) =>
                      setReplies({ ...replies, [q.id]: e.target.value })
                    }
                  />
                </label>
                <button disabled={busy}>답변 저장</button>
              </form>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
