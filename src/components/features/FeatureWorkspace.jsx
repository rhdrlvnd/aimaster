import React, { useEffect, useState } from "react";
import { api, streamRequest } from "../../services/api";
import SchedulePanel from "./SchedulePanel";
import QuestionsPanel from "./QuestionsPanel";
import HandoverDashboard from "./HandoverDashboard";
import ExportPanel from "./ExportPanel";

export default function FeatureWorkspace({
  handoverId,
  state,
  currentUser,
  tab,
  setSelected,
  onBusy,
  onRefresh,
}) {
  const prefix = "/handovers/" + handoverId;
  const [data, setData] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [progress, setProgress] = useState(null);
  const owner = state.permissions.can_manage;
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
    if (busy) return false;
    setBusy(true);
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
    busy,
    run,
    currentUser,
    prefix,
    refresh: load,
    setError,
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
          <HandoverDashboard {...props} />
          {owner && <ExportPanel {...props} />}
        </>
      )}
      {tab === "schedule" && <SchedulePanel {...props} />}
      {tab === "qa" && <QuestionsPanel {...props} setSelected={setSelected} />}
    </section>
  );
}
