import React from "react";
import { ChevronRight, Sparkles, BookOpen, PanelLeftClose } from "lucide-react";

export default function Sidebar({
  handover,
  currentUser,
  onBack,
  busy,
  nav,
  tab,
  setTab,
  setError,
  setNotice,
  items,
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <BookOpen size={22} />
        </span>
        <div>
          업무 인수인계<span>AI WORKSPACE</span>
        </div>
      </div>
      <div className="workspace-label">WORKSPACE</div>
      <button
        className="workspace-picker"
        onClick={onBack}
        disabled={!!busy}
        aria-label="인수인계 목록으로"
      >
        <span className="project-icon">H</span>
        <div>
          {handover?.name || "불러오는 중"}
          <small>인수인계 목록으로</small>
        </div>
        <ChevronRight size={15} />
      </button>
      <nav>
        {nav.map(([key, Icon, label]) => (
          <button
            key={key}
            className={tab === key ? "nav active" : "nav"}
            disabled={!!busy}
            onClick={() => {
              setTab(key);
              setError("");
              setNotice("");
            }}
          >
            <Icon size={19} />
            {label}
            {key === "checklist" && items.length > 0 && (
              <span className="count">{items.length}</span>
            )}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="scope-note">
          <Sparkles size={17} />
          <strong>문서에서 시작하는 인수인계</strong>
          <p>
            업무 지식은 남기고,
            <br />
            다음 담당자의 시작은 가볍게.
          </p>
        </div>
        <div className="profile">
          <span>{currentUser?.name?.slice(0, 1) || "·"}</span>
          <div>
            {currentUser?.name || "사용자 확인 중"}
            <small>
              {currentUser?.department}
              {handover &&
                currentUser &&
                (currentUser.id === handover.owner_id
                  ? " · 인계자"
                  : currentUser.id === handover.successor_id
                    ? " · 인수자"
                    : "")}
            </small>
          </div>
          <PanelLeftClose size={17} />
        </div>
      </div>
    </aside>
  );
}
