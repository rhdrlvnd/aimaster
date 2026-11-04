import React, { useState, useRef } from "react";
import { Check, CircleDot } from "lucide-react";
import ScheduleDetailDrawer from "./ScheduleDetailDrawer";
import { PRIORITIES, priorityInfo } from "../../services/priorities";
const statusLabels = { todo: "미시작", doing: "진행 중", done: "완료" };
const iso = (d) => d.toISOString().slice(0, 10);
const add = (day, n) => {
  const d = new Date(day + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return iso(d);
};
const shiftMonth = (month, n) => {
  const d = new Date(month + "-01T00:00:00Z");
  d.setUTCMonth(d.getUTCMonth() + n);
  return iso(d).slice(0, 7);
};
const hour = (value) => Number((value || "00:00").slice(0, 2));

export default function ScheduleCalendar({
  rows,
  settings,
  items,
  progress,
  disabled,
  readOnly = false,
  lockReason = "",
  onMove,
}) {
  const drag = useRef(null);
  const suppressClick = useRef(false);
  const [dragView, setDragView] = useState(null);
  function beginDrag(e, row) {
    suppressClick.current = false;
    if (disabled || progress[row.item_id]?.status === "done" || e.button !== 0)
      return;
    drag.current = {
      id: row.item_id,
      hour: hour(row.start_time),
      x: e.clientX,
      y: e.clientY,
      active: false,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function updateDrag(e) {
    const current = drag.current;
    if (!current) return;
    if (
      !current.active &&
      Math.hypot(e.clientX - current.x, e.clientY - current.y) < 6
    )
      return;
    current.active = true;
    setDragView({ id: current.id, x: e.clientX, y: e.clientY });
    const day = document
      .elementFromPoint(e.clientX, e.clientY)
      ?.closest("[data-calendar-date]")?.dataset.calendarDate;
    setHoverDay(day && available(day) ? day : null);
  }
  function finishDrag(e) {
    const current = drag.current;
    drag.current = null;
    setDragView(null);
    setHoverDay(null);
    if (!current?.active) return;
    suppressClick.current = true;
    const day = document
      .elementFromPoint(e.clientX, e.clientY)
      ?.closest("[data-calendar-date]")?.dataset.calendarDate;
    if (day) move(current.id, day, current.hour);
  }
  function cancelDrag() {
    drag.current = null;
    setDragView(null);
    setHoverDay(null);
  }
  const [month, setMonth] = useState(() =>
    (rows[0]?.start || settings.start).slice(0, 7),
  );
  const [selected, setSelected] = useState(null);
  const [dateError, setDateError] = useState("");
  const [hoverDay, setHoverDay] = useState(null);
  const first = month + "-01";
  const offset = new Date(first + "T00:00:00Z").getUTCDay();
  const last = add(shiftMonth(month, 1) + "-01", -1);
  const count = Math.ceil((offset + Number(last.slice(8))) / 7) * 7;
  const days = Array.from({ length: count }, (_, n) => add(first, n - offset));
  const title = (id) => items.find((i) => i.id === id)?.title || id;
  const number = (id) => items.findIndex((item) => item.id === id) + 1;
  const selectedItem = items.find((item) => item.id === selected);
  const selectedRow = rows.find((row) => row.item_id === selected);
  const canMoveSelected = !disabled && progress[selected]?.status !== "done";
  const available = (day) =>
    day >= settings.start &&
    day <= settings.end &&
    !(settings.holidays || []).includes(day) &&
    (settings.weekends ||
      ![0, 6].includes(new Date(day + "T00:00:00Z").getUTCDay()));
  const select = (row) => {
    setSelected(selected === row.item_id ? null : row.item_id);
    setDateError("");
  };
  async function move(id, day, time) {
    setHoverDay(null);
    if (!id || disabled || progress[id]?.status === "done" || !available(day))
      return;
    if (await onMove(id, day, time)) setSelected(null);
  }
  return (
    <div className="schedule-calendar">
      {dragView && (
        <div
          className="calendar-drag-preview"
          style={{ left: dragView.x + 12, top: dragView.y + 12 }}
        >
          {title(dragView.id)}
        </div>
      )}
      <div className="calendar-toolbar">
        <div>
          <button
            type="button"
            disabled={month <= settings.start.slice(0, 7)}
            onClick={() => setMonth(shiftMonth(month, -1))}
          >
            이전 달
          </button>
          <strong>
            {Number(month.slice(0, 4))}년 {Number(month.slice(5))}월
          </strong>
          <button
            type="button"
            disabled={month >= settings.end.slice(0, 7)}
            onClick={() => setMonth(shiftMonth(month, 1))}
          >
            다음 달
          </button>
        </div>
        <div className="calendar-summary">
          <span>월간 일정 · {rows.length}개 업무</span>
          <div
            className="calendar-priority-legend"
            aria-label="업무 중요도: 긴급 빨강, 보통 노랑, 여유 초록"
          >
            <span>중요도</span>
            {PRIORITIES.map(({ label, tone, description }) => (
              <span key={tone} title={description}>
                <i
                  className={`priority-dot priority-${tone}`}
                  aria-hidden="true"
                />
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>
      <p className="calendar-help">
        {lockReason ||
          "카드를 클릭하면 업무 상세를 확인하고, 드래그하면 날짜를 변경할 수 있습니다."}
      </p>
      {selectedItem && (
        <ScheduleDetailDrawer
          item={selectedItem}
          row={selectedRow}
          items={items}
          onClose={() => setSelected(null)}
          onSelect={(id) => {
            setSelected(id);
            const row = rows.find((entry) => entry.item_id === id);
            if (row) {
              setDateError("");
              setMonth(row.start.slice(0, 7));
            }
          }}
        >
          {readOnly ? (
            <p>
              인수 상태:{" "}
              {
                { todo: "미시작", doing: "진행 중", done: "완료" }[
                  progress[selected]?.status || "todo"
                ]
              }
            </p>
          ) : (
            <div className="schedule-date-editor">
              <label htmlFor="handover-task-date">인수인계 날짜</label>
              <input
                id="handover-task-date"
                type="date"
                value={selectedRow?.start || ""}
                min={settings.start}
                max={settings.end}
                disabled={!canMoveSelected}
                onChange={async (event) => {
                  const day = event.target.value;
                  if (!day) return;
                  if (!available(day)) {
                    setDateError(
                      "인수인계 기간 안의 업무일을 선택해 주세요. 주말·휴일 설정도 확인해 주세요.",
                    );
                    return;
                  }
                  setDateError("");
                  if (
                    await onMove(selected, day, hour(selectedRow?.start_time))
                  )
                    setMonth(day.slice(0, 7));
                  else
                    setDateError(
                      "날짜를 변경하지 못했습니다. 선행·후속 업무의 일정과 화면의 오류 안내를 확인해 주세요.",
                    );
                }}
              />
              {dateError && <p role="alert">{dateError}</p>}
              <small>
                {progress[selected]?.status === "done"
                  ? "완료된 업무의 날짜는 변경할 수 없습니다."
                  : "변경 후 ‘일정 확정’을 눌러 저장하세요."}
              </small>
            </div>
          )}
        </ScheduleDetailDrawer>
      )}
      <div
        className="month-calendar-scroll"
        onKeyDown={(e) => {
          if (e.key === "Escape") setSelected(null);
        }}
      >
        <div className="month-calendar-grid">
          {["일", "월", "화", "수", "목", "금", "토"].map((name, n) => (
            <div
              key={name}
              className={
                "month-weekday " +
                (n === 0 ? "sunday" : n === 6 ? "weekend" : "")
              }
            >
              {name}
            </div>
          ))}
          {days.map((day) => {
            const dayRows = available(day)
              ? rows
                  .filter((row) => row.start <= day && row.end >= day)
                  .sort(
                    (a, b) =>
                      a.start.localeCompare(b.start) ||
                      (a.start_time || "").localeCompare(b.start_time || ""),
                  )
              : [];
            const completedCount = dayRows.filter(
              (row) => progress[row.item_id]?.status === "done",
            ).length;
            return (
              <div
                key={day}
                data-calendar-date={day}
                className={
                  "month-day " +
                  (day.slice(0, 7) !== month ? "outside-month " : "") +
                  (!available(day) ? "unavailable " : "") +
                  (hoverDay === day ? "drop-target" : "")
                }
                onDragOver={(e) => {
                  if (!disabled && available(day)) {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    setHoverDay(day);
                  }
                }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget))
                    setHoverDay(null);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const id = e.dataTransfer.getData("text/plain");
                  const row = rows.find((r) => r.item_id === id);
                  if (row) move(id, day, hour(row.start_time));
                }}
              >
                <div className="month-date-heading">
                  <div className="month-date-label">
                    <span
                      className={
                        "month-date" +
                        (new Date(day + "T00:00:00Z").getUTCDay() === 0 ||
                        (settings.holidays || []).includes(day)
                          ? " holiday-date"
                          : "")
                      }
                    >
                      {Number(day.slice(8))}
                    </span>
                    {dayRows.length > 0 && (
                      <span
                        className="month-day-progress"
                        aria-label={`${day} 업무 ${dayRows.length}개 중 ${completedCount}개 완료`}
                        title={`총 ${dayRows.length}개 업무 중 ${completedCount}개 완료`}
                      >
                        완료 {completedCount}/{dayRows.length}
                      </span>
                    )}
                  </div>
                  {!available(day) && (
                    <small>
                      {day < settings.start || day > settings.end
                        ? "기간 외"
                        : "휴무"}
                    </small>
                  )}
                </div>
                <div className="month-events">
                  {dayRows.map((r) => {
                    const priority = priorityInfo(
                      items.find((item) => item.id === r.item_id)?.priority,
                    );
                    const done = progress[r.item_id]?.status === "done";
                    const doing = progress[r.item_id]?.status === "doing";
                    const label = `${number(r.item_id)}. ${title(r.item_id)} · 중요도 ${priority.label} · ${statusLabels[progress[r.item_id]?.status || "todo"]}${r.start !== day ? " · 계속" : ""}`;
                    return (
                      <div className="calendar-event-card" key={r.item_id}>
                        <button
                          type="button"
                          className={
                            `month-event priority-${priority.tone} ` +
                            (selected === r.item_id ? "selected " : "") +
                            (done ? "completed" : "")
                          }
                          draggable={false}
                          aria-label={label}
                          aria-pressed={selected === r.item_id}
                          title={`${label}${!disabled && !done ? " · 드래그하여 날짜 이동" : ""}${lockReason ? " · " + lockReason : ""}`}
                          onClick={() => {
                            if (suppressClick.current) {
                              suppressClick.current = false;
                              return;
                            }
                            select(r);
                          }}
                          onPointerDown={(e) => beginDrag(e, r)}
                          onPointerMove={updateDrag}
                          onPointerUp={finishDrag}
                          onPointerCancel={cancelDrag}
                          onLostPointerCapture={cancelDrag}
                        >
                          <span className="month-event-title">
                            {number(r.item_id)}. {title(r.item_id)}
                          </span>
                          {done ? (
                            <Check
                              className="month-event-status"
                              size={14}
                              aria-hidden="true"
                            />
                          ) : doing ? (
                            <CircleDot
                              className="month-event-status"
                              size={14}
                              aria-hidden="true"
                            />
                          ) : null}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
