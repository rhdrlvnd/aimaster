import React, { useState, useEffect, useRef } from "react";
import QuestionInbox from "./QuestionInbox";
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
  const [channel, setChannel] = useState("ai");
  const [pending, setPending] = useState("");
  const history = useRef(null);
  useEffect(() => {
    if (history.current)
      history.current.scrollTop = history.current.scrollHeight;
  }, [data.conversations, data.questions, pending, channel, conversationId]);
  const selected = data.conversations.find((c) => c.id === conversationId);
  async function ask(e) {
    e.preventDefault();
    if (busy || !question.trim()) return;
    const sent = question;
    setPending(sent);
    setQuestion("");
    if (
      await run(
        "/qa/stream",
        { question: sent, conversation_id: conversationId || null },
        "POST",
        true,
      )
    ) {
      const latest = await refresh();
      setConversationId(
        conversationId || latest.conversations.at(-1)?.id || "",
      );
    } else {
      setQuestion(sent);
    }
    setPending("");
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
  if (owner)
    return (
      <QuestionInbox
        questions={data.questions}
        busy={busy}
        run={run}
        setSelected={setSelected}
      />
    );
  return (
    <div className="questions-chat">
      <div className="question-channels" role="group" aria-label="대화 대상">
        <button
          aria-pressed={channel === "ai"}
          onClick={() => setChannel("ai")}
        >
          AI와 대화
        </button>
        <button
          aria-pressed={channel === "human"}
          onClick={() => setChannel("human")}
        >
          인계자 답변 확인
        </button>
      </div>
      <section
        className="feature-card chat-panel conversation-workspace"
        hidden={channel !== "ai"}
      >
        <aside className="conversation-sidebar" aria-label="이전 대화">
          <div className="conversation-sidebar-heading">
            <strong>대화 목록</strong>
            <span>{data.conversations.length}</span>
          </div>
          <button
            className="conversation-new"
            disabled={busy}
            aria-pressed={!conversationId}
            onClick={() => {
              setConversationId("");
              setQuestion("");
            }}
          >
            + 새 대화
          </button>
          <div className="conversation-list">
            {[...data.conversations].reverse().map((c) => (
              <button
                key={c.id}
                className="conversation-list-item"
                disabled={busy}
                aria-pressed={conversationId === c.id}
                onClick={() => {
                  setConversationId(c.id);
                  setQuestion("");
                }}
              >
                <strong>{c.title}</strong>
                <span>
                  {c.messages.at(-1)?.question || "대화를 시작해 보세요."}
                </span>
                <small>질문 {c.messages.length}개</small>
              </button>
            ))}
            {!data.conversations.length && (
              <p className="subtext">
                아직 대화가 없습니다.
                <br />
                질문하면 여기에 저장됩니다.
              </p>
            )}
          </div>
        </aside>
        <div className="conversation-main">
          <header className="conversation-heading">
            <h2>{selected?.title || "새 대화"}</h2>
            {conversationId && (
              <button disabled={busy} onClick={remove}>
                대화 삭제
              </button>
            )}
          </header>
          <div
            className="chat-history"
            ref={channel === "ai" ? history : null}
            aria-label="AI 대화 내역"
          >
            {!selected && (
              <p className="subtext">
                업무 절차를 질문하거나 “오늘 일정 완료 처리”처럼 요청할 수
                있습니다. 변경 작업은 대상을 확인한 뒤 실행합니다.
              </p>
            )}
            {selected?.messages.map((msg) => (
              <article className="chat-turn" key={msg.id}>
                <div className="chat-user">
                  <strong>나</strong>
                  <p>{msg.question}</p>
                </div>
                <div className="chat-answer">
                  <strong>
                    AI 답변{msg.insufficient ? " · 추가 확인 필요" : ""}
                  </strong>
                  <p>{msg.answer}</p>
                  <div className="chat-answer-actions">
                    {msg.evidence.map((e, i) => (
                      <button key={i} onClick={() => setSelected(e)}>
                        근거 {i + 1}
                        {e.kind === "visual" ? " · 이미지 해석" : ""}
                      </button>
                    ))}
                    {!data.questions.some((q) => q.message_id === msg.id) && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          run("/questions", {
                            content: msg.question,
                            conversation_id: selected.id,
                            message_id: msg.id,
                          })
                        }
                      >
                        인계자에게 추가 확인 요청
                      </button>
                    )}
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
                  {(() => {
                    const forwarded = data.questions.find(
                      (q) => q.message_id === msg.id,
                    );
                    return forwarded ? (
                      <div className="forwarded-answer">
                        <strong>
                          {forwarded.answer
                            ? `${forwarded.answered_by}의 답변`
                            : "인계자 답변 대기 중"}
                        </strong>
                        <p>
                          {forwarded.answer ||
                            "질문과 AI 답변을 인계자에게 전달했습니다."}
                        </p>
                      </div>
                    ) : null;
                  })()}
                </div>
              </article>
            ))}
            {pending && (
              <article className="chat-turn">
                <div className="chat-user">
                  <strong>나</strong>
                  <p>{pending}</p>
                </div>
                <div className="chat-answer" role="status">
                  <strong>AI</strong>
                  <p>문서를 확인하며 답변을 작성하고 있어요…</p>
                </div>
              </article>
            )}
          </div>
          <form className="chat-composer" onSubmit={ask}>
            <label>
              <span className="chat-input-label">메시지</span>
              <textarea
                required
                maxLength={4000}
                disabled={busy || state.status !== "approved"}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    e.currentTarget.form.requestSubmit();
                  }
                }}
                placeholder="메시지를 입력하세요. Enter로 전송 · Shift+Enter로 줄바꿈"
              />
            </label>
            <button
              className="primary"
              disabled={busy || state.status !== "approved" || !question.trim()}
            >
              전송
            </button>
          </form>
        </div>
      </section>
      <section
        className="feature-card chat-panel human-chat-panel"
        hidden={channel !== "human"}
      >
        <h2>인계자 답변 확인</h2>
        <p className="subtext">인계자가 직접 확인하고 답변합니다.</p>
        <div
          className="chat-history"
          ref={channel === "human" ? history : null}
          aria-label="인계자 대화 내역"
        >
          {data.questions.length === 0 && (
            <p className="subtext">등록된 질문이 없습니다.</p>
          )}
          {data.questions.map((q) => (
            <article className="board-question" key={q.id}>
              <div className={owner ? "chat-answer" : "chat-user"}>
                <strong>
                  {q.answer ? "답변 완료" : "답변 대기"} · {q.author}
                </strong>
                <p>{q.question}</p>
              </div>
              {q.answer && (
                <div className={owner ? "chat-user" : "chat-answer"}>
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
        </div>
        {!owner && (
          <form
            className="chat-composer"
            onSubmit={async (e) => {
              e.preventDefault();
              if (await run("/questions", { content: board })) setBoard("");
            }}
          >
            <label>
              메시지
              <textarea
                required
                maxLength={8000}
                disabled={busy}
                value={board}
                onChange={(e) => setBoard(e.target.value)}
              />
            </label>
            <button disabled={busy || !board.trim()}>전송</button>
          </form>
        )}
      </section>
    </div>
  );
}
