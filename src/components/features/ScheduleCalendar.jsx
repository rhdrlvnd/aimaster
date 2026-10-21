import React, { useState, useRef } from "react";
import ScheduleDetailDrawer from "./ScheduleDetailDrawer";
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
  lockReason = "",
  onMove,
}) {
  const drag = useRef(null);
  const suppressClick = useRef(false);
  const [dragView, setDragView] = useState(null);
  function beginDrag(e, row) {
    if (disabled || progress[row.item_id]?.status === "done" || e.button !== 0)
      return;
    suppressClick.current = false;
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
  const offset = (new Date(first + "T00:00:00Z").getUTCDay() + 6) % 7;
  const last = add(shiftMonth(month, 1) + "-01", -1);
  const count = Math.ceil((offset + Number(last.slice(8))) / 7) * 7;
  const days = Array.from({ length: count }, (_, n) => add(first, n - offset));
  const title = (id) => items.find((i) => i.id === id)?.title || id;
  const number = (id) => items.findIndex((item) => item.id === id) + 1;
  const predecessors = (id) =>
    items.find((item) => item.id === id)?.dependencies || [];
  const successors = (id) =>
    items
      .filter((item) => (item.dependencies || []).includes(id))
      .map((item) => item.id);
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
        <span>월간 일정 · {rows.length}개 업무</span>
      </div>
      <p className="calendar-help">
        {lockReason ||
          "카드에서 중요도와 선행·후속 업무 수를 확인하세요. 카드를 클릭하면 오른쪽에서 상세를 보고, 드래그하면 다른 날짜로 이동합니다."}
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
                if (await onMove(selected, day, hour(selectedRow?.start_time)))
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
        </ScheduleDetailDrawer>
      )}
      <div
        className="month-calendar-scroll"
        onKeyDown={(e) => {
          if (e.key === "Escape") setSelected(null);
        }}
      >
        <div className="month-calendar-grid">
          {["월", "화", "수", "목", "금", "토", "일"].map((name, n) => (
            <div
              key={name}
              className={"month-weekday " + (n >= 5 ? "weekend" : "")}
            >
              {name}
            </div>
          ))}
          {days.map((day) => (
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
                <span className="month-date">{Number(day.slice(8))}</span>
                {!available(day) && (
                  <small>
                    {day < settings.start || day > settings.end
                      ? "기간 외"
                      : "휴무"}
                  </small>
                )}
              </div>
              <div className="month-events">
                {available(day) &&
                  rows
                    .filter((r) => r.start <= day && r.end >= day)
                    .sort(
                      (a, b) =>
                        a.start.localeCompare(b.start) ||
                        (a.start_time || "").localeCompare(b.start_time || ""),
                    )
                    .map((r) => {
                      const priority =
                        items.find((item) => item.id === r.item_id)?.priority ||
                        "보통";
                      const done = progress[r.item_id]?.status === "done";
                      return (
                        <div className="calendar-event-card" key={r.item_id}>
                          <button
                            type="button"
                            className={
                              "month-event " +
                              (selected === r.item_id ? "selected " : "") +
                              (done ? "completed" : "")
                            }
                            draggable={false}
                            title={`${title(r.item_id)} · 중요도 ${priority} · 드래그하여 날짜 이동${lockReason ? " · " + lockReason : ""}`}
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
                            <small
                              className={
                                "calendar-priority " +
                                (priority === "높음" ? "high" : "")
                              }
                            >
                              중요도 {priority} {done ? "· 완료" : ""}
                              {r.start !== day ? " · 계속" : ""}
                            </small>
                            <span>
                              {number(r.item_id)}. {title(r.item_id)}
                            </span>
                            <small className="calendar-relation-count">
                              선행 {predecessors(r.item_id).length} · 후속{" "}
                              {successors(r.item_id).length}
                            </small>
                          </button>
                        </div>
                      );
                    })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
