import React, { useState, useEffect } from "react";
import { api } from "../../services/api";
export default function SchedulePanel({
  state,
  data,
  owner,
  busy,
  run,
  refresh,
  setError,
}) {
  const items = state.items;
  const [settings, setSettings] = useState(
    () =>
      data.schedule.settings || {
        start: state.handover.start_date || "",
        end: state.handover.end_date || "",
        weekends: false,
        holidays: [],
        durations: Object.fromEntries(items.map((i) => [i.id, 1])),
        dependencies: Object.fromEntries(
          items.map((i) => [i.id, i.dependencies || []]),
        ),
        unit: "hour",
        daily_hours: 4,
        day_start: 9,
      },
  );
  const [holidayText, setHolidayText] = useState(
    (settings.holidays || []).join(", "),
  );
  const proposalSettings = () => ({
    ...settings,
    dependencies: Object.fromEntries(
      items.map((i) => [i.id, i.dependencies || []]),
    ),
    holidays: holidayText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  });
  const [draft, setDraft] = useState(data.schedule.draft?.rows || []),
    [selected, setSelected] = useState([]);
  useEffect(() => {
    setDraft(data.schedule.draft?.rows || []);
    if (data.schedule.draft?.settings) {
      setSettings(data.schedule.draft.settings);
      setHolidayText(data.schedule.draft.settings.holidays.join(", "));
    }
  }, [data.schedule.draft]);
  const confirmed = data.schedule.confirmed || [];
  const title = (id) => items.find((i) => i.id === id)?.title || id;
  const ready = state.status === "approved";
  async function connect() {
    try {
      const d = await api("/calendar/connect", "POST", {});
      window.location.assign(d.url);
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <>
      {!ready && (
        <div className="inline-warning">
          체크리스트를 확정하면 일정을 작성할 수 있습니다.
        </div>
      )}
      {owner && (
        <div className="feature-card">
          <h2>AI 일정 계획</h2>
          <p>
            업무별 소요 시간을 확인해 주세요. 선행 업무는 체크리스트에서 확정한
            관계를 사용합니다. 같은 날 여러 업무를 배치하며 AI가 순서를 제안하고
            시스템이 날짜 조건을 검사합니다.
          </p>
          <fieldset disabled={busy || !ready}>
            <div className="feature-form-row">
              {settings.unit === "hour" && (
                <>
                  <label>
                    하루 가능 시간
                    <input
                      type="number"
                      min="1"
                      max="12"
                      value={settings.daily_hours}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          daily_hours: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label>
                    시작 시각 (시)
                    <input
                      type="number"
                      min="0"
                      max="11"
                      value={settings.day_start}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          day_start: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                </>
              )}

              <label>
                시작일
                <input
                  type="date"
                  value={settings.start}
                  onChange={(e) =>
                    setSettings({ ...settings, start: e.target.value })
                  }
                />
              </label>
              <label>
                종료일
                <input
                  type="date"
                  value={settings.end}
                  onChange={(e) =>
                    setSettings({ ...settings, end: e.target.value })
                  }
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.weekends}
                  onChange={(e) =>
                    setSettings({ ...settings, weekends: e.target.checked })
                  }
                />
                주말 포함
              </label>
            </div>
            <label>
              휴일 (YYYY-MM-DD, 쉼표로 구분)
              <input
                placeholder="2026-10-09, 2026-12-25"
                value={holidayText}
                onChange={(e) => setHolidayText(e.target.value)}
              />
            </label>
            <div className="feature-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>업무</th>
                    <th>
                      {settings.unit === "hour"
                        ? "소요 시간"
                        : "소요 업무일 (기존 일정)"}
                    </th>
                    <th>확정된 선행 업무</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.id}>
                      <td>
                        {i.title}
                        <small>{i.priority}</small>
                      </td>
                      <td>
                        <input
                          aria-label={
                            i.title +
                            (settings.unit === "hour"
                              ? " 소요 시간"
                              : " 소요 업무일")
                          }
                          type="number"
                          min="1"
                          max="365"
                          value={settings.durations[i.id] || 1}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              durations: {
                                ...settings.durations,
                                [i.id]: Number(e.target.value),
                              },
                            })
                          }
                        />
                      </td>
                      <td>
                        {(i.dependencies || []).length ? (
                          <ul>
                            {i.dependencies.map((id) => (
                              <li key={id}>{title(id)}</li>
                            ))}
                          </ul>
                        ) : (
                          <span>선행 업무 없음</span>
                        )}
                        <small>체크리스트 검토에서 설정</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="feature-actions">
              <button
                className="primary"
                onClick={() =>
                  run(
                    "/schedule/generate/stream",
                    { settings: proposalSettings(), reschedule: false },
                    "POST",
                    true,
                  )
                }
              >
                AI 일정 초안 작성
              </button>
              <button
                disabled={!confirmed.length}
                onClick={() =>
                  run(
                    "/schedule/generate/stream",
                    { settings: proposalSettings(), reschedule: true },
                    "POST",
                    true,
                  )
                }
              >
                진행 상황으로 일정 재조정
              </button>
            </div>
          </fieldset>
        </div>
      )}
      {owner && draft.length > 0 && (
        <div className="feature-card">
          <h2>일정 초안 검토</h2>
          <p>
            완료된 업무를 유지하면서 날짜와 조건을 검토하세요. 확정 전에는 기존
            일정이 유지됩니다.
          </p>
          <div className="feature-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>업무</th>
                  <th>시작</th>
                  <th>종료</th>
                  <th>배치 이유</th>
                </tr>
              </thead>
              <tbody>
                {draft.map((r, n) => (
                  <tr key={r.item_id}>
                    <td>{title(r.item_id)}</td>
                    {["start", "end"].map((k) => (
                      <td key={k}>
                        <input
                          type="date"
                          aria-label={title(r.item_id) + " " + k}
                          disabled={
                            busy || data.progress[r.item_id]?.status === "done"
                          }
                          value={r[k]}
                          onChange={(e) =>
                            setDraft(
                              draft.map((x, j) =>
                                j === n ? { ...x, [k]: e.target.value } : x,
                              ),
                            )
                          }
                        />
                        {settings.unit === "hour" && (
                          <input
                            type="time"
                            step="3600"
                            aria-label={title(r.item_id) + " " + k + " 시각"}
                            value={(r[k + "_time"] || "").slice(0, 5)}
                            disabled={
                              busy ||
                              data.progress[r.item_id]?.status === "done"
                            }
                            onChange={(e) =>
                              setDraft(
                                draft.map((x, j) =>
                                  j === n
                                    ? { ...x, [k + "_time"]: e.target.value }
                                    : x,
                                ),
                              )
                            }
                          />
                        )}
                      </td>
                    ))}
                    <td>{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            className="primary"
            disabled={busy}
            onClick={() => run("/schedule/confirm", { rows: draft })}
          >
            일정 확정
          </button>
        </div>
      )}
      <div className="feature-card">
        <h2>확정 일정과 인수 진행</h2>
        {!confirmed.length ? (
          <p>인계자가 일정을 확정하면 표시됩니다.</p>
        ) : (
          <>
            {!data.schedule_current && (
              <div className="inline-warning">
                자료가 변경되어 일정 재확정이 필요합니다.
              </div>
            )}
            <div className="feature-table-wrap">
              <table>
                <thead>
                  <tr>
                    {!owner && <th>선택</th>}
                    <th>업무</th>
                    <th>기간</th>
                    <th>인수 상태</th>
                  </tr>
                </thead>
                <tbody>
                  {confirmed.map((r) => (
                    <tr key={r.item_id}>
                      {!owner && (
                        <td>
                          <input
                            type="checkbox"
                            aria-label={title(r.item_id) + " 캘린더 선택"}
                            checked={selected.includes(r.item_id)}
                            onChange={(e) =>
                              setSelected(
                                e.target.checked
                                  ? [...selected, r.item_id]
                                  : selected.filter((x) => x !== r.item_id),
                              )
                            }
                          />
                        </td>
                      )}
                      <td>{title(r.item_id)}</td>
                      <td>
                        {r.start} {r.start_time?.slice(0, 5)} ~ {r.end}{" "}
                        {r.end_time?.slice(0, 5)}
                      </td>
                      <td>
                        {owner ? (
                          { todo: "미시작", doing: "진행 중", done: "완료" }[
                            data.progress[r.item_id]?.status || "todo"
                          ]
                        ) : (
                          <select
                            aria-label={title(r.item_id) + " 인수 상태"}
                            disabled={busy || !data.schedule_current}
                            value={data.progress[r.item_id]?.status || "todo"}
                            onChange={(e) =>
                              run("/progress", {
                                item_ids: [r.item_id],
                                status: e.target.value,
                              })
                            }
                          >
                            <option value="todo">미시작</option>
                            <option value="doing">진행 중</option>
                            <option value="done">완료</option>
                          </select>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!owner && (
              <div className="feature-actions">
                <button
                  onClick={() => setSelected(confirmed.map((r) => r.item_id))}
                >
                  전체 선택
                </button>
                {data.calendar.connected ? (
                  <>
                    <button
                      disabled={
                        busy || !selected.length || !data.schedule_current
                      }
                      onClick={() =>
                        window.confirm(
                          "선택한 확정 일정을 Google Calendar에 등록 또는 갱신할까요?",
                        ) && run("/calendar/events", { item_ids: selected })
                      }
                    >
                      선택 일정 캘린더 등록
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          await api("/calendar/connection", "DELETE");
                          await refresh();
                        } catch (e) {
                          setError(e.message);
                        }
                      }}
                    >
                      Google 연결 해제
                    </button>
                  </>
                ) : (
                  <button
                    disabled={!data.calendar.configured}
                    onClick={connect}
                  >
                    Google Calendar 연결
                  </button>
                )}
              </div>
            )}
          </>
        )}
        {!owner && !data.calendar.configured && (
          <p className="subtext">
            Google OAuth 설정을 등록하면 캘린더를 연결할 수 있습니다.
          </p>
        )}
        {data.calendar_results.map((r, i) => (
          <p key={i}>
            {title(r.item_id)} ·{" "}
            {r.status === "success" ? "캘린더 등록 완료" : r.detail}
          </p>
        ))}
      </div>
    </>
  );
}
