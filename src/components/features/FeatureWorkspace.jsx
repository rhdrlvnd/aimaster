import React, { useEffect, useRef, useState } from "react";
import { api, streamRequest } from "../../services/api";
import SchedulePanel from "./SchedulePanel";
import QuestionsPanel from "./QuestionsPanel";
import HandoverDashboard from "./HandoverDashboard";
import ExportPanel from "./ExportPanel";
import ScheduleCalendar from "./ScheduleCalendar";

export default function FeatureWorkspace({
  handoverId,
  state,
  currentUser,
  tab,
  setSelected,
  onBusy,
  onRefresh,
  externalBusy = false,
  onOpenChecklist,
}) {
  const prefix = "/handovers/" + handoverId;
  const [data, setData] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [progress, setProgress] = useState(null);
  const [scheduleGenerating, setScheduleGenerating] = useState(false);
  const owner = state.permissions.can_manage;
  const poll = useRef(null);
  poll.current = async () => {
    if (owner || busy || externalBusy || document.hidden) return;
    const latest = await api(prefix + "/features");
    setData(latest);
    if (latest.revision !== state.revision) await onRefresh();
  };
  useEffect(() => {
    // Read our DB only; Google status changes are processed by the 06:00 batch.
    let running = false;
    const check = async () => {
      if (running) return;
      running = true;
      try {
        await poll.current?.();
      } catch {
        /* Existing view remains available. */
      } finally {
        running = false;
      }
    };
    const timer = window.setInterval(check, 60000);
    window.addEventListener("focus", check);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", check);
    };
  }, [handoverId]);
  async function load() {
    const result = await api(prefix + "/features");
    setData(result);
    return result;
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [handoverId, state.revision]);
  useEffect(() => {
    onBusy?.(busy);
    const guard = (e) => {
      if (busy) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => {
      onBusy?.(false);
      window.removeEventListener("beforeunload", guard);
    };
  }, [busy]);
  async function run(path, body, method = "POST", stream = false) {
    if (busy || externalBusy) return false;
    setBusy(true);
    setScheduleGenerating(path === "/schedule/generate/stream");
    setError("");
    setNotice("");
    setProgress(null);
    try {
      if (stream)
        await streamRequest(
          { ...body, revision: data.revision },
          setProgress,
          "/api" + prefix + path,
        );
      else
        await api(prefix + path, method, { ...body, revision: data.revision });
      await load();
      await onRefresh();
      setNotice("처리 결과를 저장했습니다.");
      return true;
    } catch (e) {
      setError(e.message);
      await load().catch(() => {});
      return false;
    } finally {
      setBusy(false);
      setScheduleGenerating(false);
    }
  }
  if (!data)
    return (
      <section className="empty">
        {error || "업무 정보를 불러오고 있어요."}
      </section>
    );
  const props = {
    state,
    data,
    owner,
    busy: busy || externalBusy,
    run,
    currentUser,
    prefix,
    refresh: load,
    setError,
    onCalendarBusy: setBusy,
  };
  return (
    <section className="feature-workspace">
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="alert success" role="status">
          {notice}
        </div>
      )}
      {busy && (
        <div className="feature-progress" role="status">
          <span className="activity-dot" />
          {progress?.detail || "요청을 처리하고 있습니다…"}
        </div>
      )}
      {tab === "overview" && (
        <>
          <HandoverDashboard {...props} onOpenChecklist={onOpenChecklist} />
          {owner && <ExportPanel {...props} />}
        </>
      )}
      {tab === "schedule" && (
        <div className="schedule-panel-stack" hidden={scheduleGenerating}>
          {state.permissions.admin_read_only ? (
            <section className="feature-card">
              <h2>인수인계 일정 · 읽기 전용</h2>
              {data.schedule.draft ? (
                <p>일정 초안입니다. 아직 확정되지 않았습니다.</p>
              ) : (
                !data.schedule_current && (
                  <p>현재 내용과 일치하는 확정 일정이 없습니다.</p>
                )
              )}
              {(data.schedule.draft?.rows || data.schedule.confirmed)
                ?.length ? (
                <ScheduleCalendar
                  rows={data.schedule.draft?.rows || data.schedule.confirmed}
                  settings={
                    data.schedule.draft?.settings || data.schedule.settings
                  }
                  items={state.items}
                  progress={data.progress}
                  disabled
                  readOnly
                  lockReason="관리자는 일정을 조회할 수 있습니다. 일정 변경은 인계자가 담당합니다."
                />
              ) : (
                <p>아직 작성된 일정이 없습니다.</p>
              )}
            </section>
          ) : (
            <SchedulePanel {...props} />
          )}
        </div>
      )}
      {tab === "qa" && !state.permissions.admin_read_only && (
        <QuestionsPanel {...props} setSelected={setSelected} />
      )}
    </section>
  );
}
