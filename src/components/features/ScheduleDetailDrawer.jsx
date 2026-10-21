import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

export default function ScheduleDetailDrawer({
  item,
  row,
  items,
  onSelect,
  onClose,
  children,
}) {
  const closeButton = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    closeButton.current?.focus();
    const escape = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("keydown", escape);
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  const before = items.filter((entry) =>
    (item.dependencies || []).includes(entry.id),
  );
  const after = items.filter((entry) =>
    (entry.dependencies || []).includes(item.id),
  );
  return createPortal(
    <aside className="schedule-detail-drawer" aria-label="일정 업무 상세">
      <header className="schedule-detail-header">
        <strong>업무 상세</strong>
        <button ref={closeButton} type="button" onClick={onClose}>
          닫기 ×
        </button>
      </header>
      <div className="schedule-detail-body">
        <h2>
          {items.findIndex((entry) => entry.id === item.id) + 1}. {item.title}
        </h2>
        <p>
          중요도 {item.priority || "보통"} · {row?.start}
          {row?.end !== row?.start ? ` ~ ${row?.end}` : ""}
        </p>
        {item.description && (
          <p className="schedule-detail-description">{item.description}</p>
        )}
        {[
          ["먼저 끝낼 업무", before],
          ["이후 진행할 업무", after],
        ].map(([label, entries]) => (
          <section key={label}>
            <h3>{label}</h3>
            {entries.length ? (
              entries.map((entry) => (
                <button
                  className="schedule-related-task"
                  type="button"
                  key={entry.id}
                  onClick={() => onSelect(entry.id)}
                >
                  {items.findIndex((i) => i.id === entry.id) + 1}. {entry.title}
                </button>
              ))
            ) : (
              <p>없음</p>
            )}
          </section>
        ))}
        {row?.reason && (
          <section>
            <h3>배치 이유</h3>
            <p>{row.reason}</p>
          </section>
        )}
        {children}
      </div>
    </aside>,
    document.body,
  );
}
