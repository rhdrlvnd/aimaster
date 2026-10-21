import React, { useState, useEffect } from "react";
import { api } from "../../services/api";
import ScheduleCalendar from "./ScheduleCalendar";
export default function SchedulePanel({
  state,
  data,
  owner,
  busy,
  run,
  refresh,
  setError,
  prefix,
  onCalendarBusy,
}) {
  const items = state.items;
  const staleDraft =
    !!data.schedule.draft &&
    (data.draft_current === false ||
      data.schedule.draft.rows.some(
        (row) => !items.some((item) => item.id === row.item_id),
      ));
  const [settingsOpen, setSettingsOpen] = useState(false);
  async function generateSchedule() {
    const success = await run(
      "/schedule/generate/stream",
      {
        settings: proposalSettings(),
        reschedule:
          !!data.schedule.confirmed?.length ||
          Object.keys(data.schedule.preserved_completed || {}).length > 0,
      },
      "POST",
      true,
    );
    if (success) setSettingsOpen(false);
  }
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
        unit: "balanced",
        daily_hours: 4,
        day_start: 9,
      },
  );
  const [holidayText, setHolidayText] = useState(
    (settings.holidays || []).join(", "),
  );
  const [holidayDate, setHolidayDate] = useState("");
  const holidays = [
    ...new Set(
      holidayText
        .split(",")
        .map((day) => day.trim())
        .filter(Boolean),
    ),
  ].sort();
  const proposalSettings = () => ({
    ...settings,
    unit: "balanced",
    durations: {},
    dependencies: Object.fromEntries(
      items.map((i) => [i.id, i.dependencies || []]),
    ),
    holidays: holidayText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  });
  const [draft, setDraft] = useState(
      staleDraft ? [] : data.schedule.draft?.rows || [],
    ),
    [selected, setSelected] = useState([]);
  useEffect(() => {
    setDraft(staleDraft ? [] : data.schedule.draft?.rows || []);
    if (data.schedule.draft?.settings) {
      setSettings(data.schedule.draft.settings);
      setHolidayText(data.schedule.draft.settings.holidays.join(", "));
    }
  }, [data.schedule.draft, staleDraft]);
  const confirmed = data.schedule.confirmed || [];
  const title = (id) => items.find((i) => i.id === id)?.title || id;
  const ready = state.status === "approved";
  const calendarLockReason = !ready
    ? "체크리스트가 검토 중이라 일정 이동이 잠겨 있습니다. 체크리스트에서 변경 저장 후 검토 확정을 진행해 주세요."
    : data.draft_current === false
      ? "체크리스트가 변경되어 이전 일정 초안은 이동할 수 없습니다. 위의 AI 일정 생성/재조정으로 새 초안을 만들어 주세요."
      : "";
  const [moveNotice, setMoveNotice] = useState("");
  async function moveCalendarItem(item_id, start, hour) {
    if (busy || calendarLockReason) return false;
    onCalendarBusy(true);
    setError("");
    setMoveNotice("");
    try {
      const result = await api(prefix + "/schedule/move", "POST", {
        revision: data.revision,
        rows: draft,
        item_id,
        start,
        hour,
      });
      setDraft(result.rows);
      setMoveNotice("일정 초안을 이동했습니다. ‘일정 확정’을 눌러 저장하세요.");
      return true;
    } catch (error) {
      setError(error.message);
      return false;
    } finally {
      onCalendarBusy(false);
    }
  }
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
      {owner && staleDraft && (
        <div className="inline-warning" role="status">
          체크리스트가 변경되어 이전 일정 초안을 표시하지 않습니다. 기간과
          휴일을 확인한 뒤 ‘AI 일정 생성’을 눌러 현재 항목과 선행 업무를 반영해
          주세요.
        </div>
      )}
      {!ready && (
        <div className="inline-warning">
          체크리스트를 확정하면 일정을 작성할 수 있습니다.
        </div>
      )}
      {owner && (
        <div className="feature-card schedule-settings-card">
          <div className="schedule-control-bar">
            <div>
              <strong>인수인계 기간</strong>
              <div className="schedule-period-inputs">
                <input
                  aria-label="인수인계 시작일"
                  type="date"
                  value={settings.start}
                  disabled={busy || !ready}
                  onChange={(e) =>
                    setSettings({ ...settings, start: e.target.value })
                  }
                />
                <span>~</span>
                <input
                  aria-label="인수인계 종료일"
                  type="date"
                  value={settings.end}
                  min={settings.start}
                  disabled={busy || !ready}
                  onChange={(e) =>
                    setSettings({ ...settings, end: e.target.value })
                  }
                />
                {(settings.start !== state.handover.start_date ||
                  settings.end !== state.handover.end_date) && (
                  <small>변경 미적용 · 일정 생성 시 저장</small>
                )}
              </div>
            </div>
            <div className="schedule-control-actions">
              <button
                type="button"
                aria-expanded={settingsOpen}
                aria-controls="schedule-settings"
                disabled={busy}
                onClick={() => setSettingsOpen(!settingsOpen)}
              >
                주말·휴일 설정 {settingsOpen ? "접기" : "열기"}
              </button>
              <button
                type="button"
                className="primary"
                disabled={busy || !ready}
                onClick={generateSchedule}
              >
                {confirmed.length
                  ? "AI 일정 재조정"
                  : draft.length
                    ? "AI 일정 다시 생성"
                    : "AI 일정 생성"}
              </button>
            </div>
          </div>
          {!draft.length && !confirmed.length && (
            <p className="schedule-first-help">
              남은 업무일에 항목 수를 고르게 나눕니다. 하루 개수 제한은
              없습니다. 생성된 일정은 달력에서 옮길 수 있습니다.
            </p>
          )}
          {settingsOpen && (
            <div id="schedule-settings" className="schedule-settings-body">
              <fieldset
                className="schedule-day-options"
                disabled={busy || !ready}
              >
                <div className="schedule-weekend-option">
                  <strong>주말 배치</strong>
                  <label className="schedule-weekend-toggle">
                    <input
                      type="checkbox"
                      checked={settings.weekends}
                      onChange={(e) =>
                        setSettings({ ...settings, weekends: e.target.checked })
                      }
                    />
                    토요일·일요일에도 배치
                  </label>
                  <small>선택하지 않으면 평일에만 배치합니다.</small>
                </div>
                <div className="schedule-holiday-option">
                  <label htmlFor="schedule-holiday-date">
                    배치에서 제외할 날짜
                  </label>
                  <div className="schedule-holiday-add">
                    <input
                      id="schedule-holiday-date"
                      type="date"
                      value={holidayDate}
                      onChange={(e) => setHolidayDate(e.target.value)}
                    />
                    <button
                      type="button"
                      disabled={!holidayDate || holidays.includes(holidayDate)}
                      onClick={() => {
                        setHolidayText(
                          [...holidays, holidayDate].sort().join(", "),
                        );
                        setHolidayDate("");
                      }}
                    >
                      날짜 추가
                    </button>
                  </div>
                  <div className="schedule-holiday-list" aria-live="polite">
                    {holidays.length ? (
                      holidays.map((day) => (
                        <button
                          type="button"
                          key={day}
                          aria-label={`${day} 제외 날짜 삭제`}
                          onClick={() =>
                            setHolidayText(
                              holidays
                                .filter((value) => value !== day)
                                .join(", "),
                            )
                          }
                        >
                          {day} <span aria-hidden="true">×</span>
                        </button>
                      ))
                    ) : (
                      <small>추가한 제외 날짜가 없습니다.</small>
                    )}
                  </div>
                </div>
              </fieldset>
              <p className="schedule-options-note">
                변경한 설정은 AI 일정 생성·재조정 시 적용됩니다.
              </p>
            </div>
          )}
        </div>
      )}
      {owner && draft.length > 0 && (
        <div className="feature-card">
          <h2>일정 초안 검토</h2>
          {calendarLockReason && (
            <div className="calendar-lock-message" role="status">
              <strong>이전 일정 · 보기 전용</strong>
              <p>{calendarLockReason}</p>
            </div>
          )}
          <p>
            날짜와 선행 업무를 확인하고 일정을 확정하세요. 완료된 업무의 날짜는
            유지됩니다.
          </p>
          {["hour", "balanced"].includes(
            data.schedule.draft?.settings?.unit,
          ) && (
            <ScheduleCalendar
              rows={draft}
              settings={data.schedule.draft.settings}
              items={items}
              progress={data.progress}
              disabled={busy || !!calendarLockReason}
              lockReason={calendarLockReason}
              onMove={moveCalendarItem}
            />
          )}
          {moveNotice && <p role="status">{moveNotice}</p>}
          <details className="calendar-table-editor">
            <summary>목록으로 날짜·시간 자세히 수정</summary>
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
                              busy ||
                              !!calendarLockReason ||
                              data.progress[r.item_id]?.status === "done"
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
                                !!calendarLockReason ||
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
          </details>
          <button
            className="primary"
            disabled={busy || !!calendarLockReason}
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
