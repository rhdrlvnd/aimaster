import PageNavigation from "./components/layout/PageNavigation";
import useWorkspace from "./hooks/useWorkspace";
import { navigation as nav } from "./navigation";
import Sidebar from "./components/layout/Sidebar";
import Overview from "./components/layout/Overview";
import DocumentPanel from "./components/documents/DocumentPanel";
import DocumentAnalysis from "./components/documents/DocumentAnalysis";
import EvidenceDrawer from "./components/documents/EvidenceDrawer";
import ChecklistPanel from "./components/checklist/ChecklistPanel";
import React, { useState, useEffect } from "react";
import FeatureWorkspace from "./components/features/FeatureWorkspace";
import RecipientView from "./components/handovers/RecipientView";
import HandoverHome from "./components/handovers/HandoverHome";
import {
  ArrowUpRight,
  Check,
  CheckCheck,
  ChevronRight,
  CalendarDays,
  X,
  LoaderCircle,
} from "lucide-react";

const labels = {
  empty: "문서 등록 전",
  ready: "분석 준비",
  review: "검토 중",
  approved: "확정 완료",
  stale: "문서 변경됨",
};
export default function App() {
  const [activeId, setActiveId] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  return activeId ? (
    <Workspace
      key={activeId}
      handoverId={activeId}
      currentUser={currentUser}
      onExit={() => setActiveId(null)}
    />
  ) : (
    <HandoverHome
      onOpen={(id, user) => {
        setCurrentUser(user);
        setActiveId(id);
      }}
    />
  );
}
function Workspace({ handoverId, currentUser, onExit }) {
  const [featureBusy, setFeatureBusy] = useState(false);
  const [checklistTarget, setChecklistTarget] = useState(null);
  const {
    deleteAllDocuments,
    state,
    items,
    tab,
    setTab,
    busy,
    error,
    setError,
    notice,
    setNotice,
    uploadProgress,
    documentProgress,
    focusedDocument,
    setFocusedDocument,
    analysisView,
    setAnalysisView,
    progress,
    elapsed,
    dirty,
    filter,
    setFilter,
    selected,
    setSelected,
    input,
    refresh,
    locked,
    reviewed,
    changed,
    edit,
    upload,
    analyzeDocument,
    analyzeAllDocuments,
    generate,
    add,
    docs,
    focusedDoc,
    analyzing,
    progressFiles,
    readyDocs,
    visible,
    addSample,
    reopenChecklist,
    saveChecklist,
    suggestDependencies,
    markAllReviewed,
    approveChecklist,
    deleteDocument,
    deleteItem,
  } = useWorkspace(handoverId);
  useEffect(() => {
    if (tab !== "checklist" || !checklistTarget) return;
    const card = document.getElementById(`checklist-${checklistTarget}`);
    if (!card) return;
    card.scrollIntoView({ block: "center" });
    card.focus({ preventScroll: true });
    card.classList.add("checklist-linked-focus");
    setChecklistTarget(null);
    const clear = () => card.classList.remove("checklist-linked-focus");
    card.addEventListener("blur", clear, { once: true });
  }, [tab, checklistTarget]);
  function backToList() {
    if (busy || featureBusy) return;
    if (
      dirty &&
      !window.confirm(
        "저장하지 않은 변경 사항이 있습니다. 변경 사항을 버리고 목록으로 이동할까요?",
      )
    )
      return;
    onExit();
  }
  const pageTitle = nav.find(([key]) => key === tab)?.[2];
  const generating = busy === "generate";
  const navigationBusy = featureBusy || (!!busy && !generating);
  return (
    <div className="shell">
      <Sidebar
        handover={state?.handover}
        currentUser={currentUser}
        onBack={backToList}
        busy={busy || featureBusy}
        navigationBusy={navigationBusy}
        generating={generating}
        nav={nav}
        tab={tab}
        setTab={setTab}
        setError={setError}
        setNotice={setNotice}
        items={items}
      />
      <div className="main">
        <header>
          <div>
            {state?.handover?.name || "인수인계"} <ChevronRight size={14} />
            <strong>{pageTitle}</strong>
          </div>
          <span className="local-badge">
            <span /> 로컬 개발 버전
          </span>
        </header>
        <main>
          {generating && tab !== "checklist" && (
            <div className="alert" role="status">
              <LoaderCircle className="spin" size={17} />
              <span>
                체크리스트 초안을 생성하고 있어요. 문서는 조회할 수 있지만
                생성이 끝날 때까지 변경할 수 없습니다.
              </span>
              <button onClick={() => setTab("checklist")}>
                생성 진행 보기
              </button>
            </div>
          )}
          {error && (
            <div className="alert error" role="alert">
              {error}
              <button aria-label="오류 닫기" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={17} />
              {notice}
              <button aria-label="알림 닫기" onClick={() => setNotice("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {!state ? (
            <div className="empty">
              <LoaderCircle className="spin" />
              <h2>작업 공간을 불러오고 있어요</h2>
              {error && (
                <button
                  onClick={() => refresh().catch((e) => setError(e.message))}
                >
                  다시 연결
                </button>
              )}
            </div>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    HANDOVER / {tab === "checklist" ? "REVIEW" : "WORKSPACE"}
                  </div>
                  <h1>{pageTitle}</h1>
                  <p>
                    {tab === "checklist"
                      ? state.permissions?.can_manage === false
                        ? "인계자가 확정한 업무와 원문 근거를 확인하세요."
                        : "업무 문서에서 만든 초안을 검토하고, 다음 담당자에게 전달할 내용을 확정하세요."
                      : "업무 지식과 인수인계 과정을 한곳에서 관리하세요."}
                  </p>
                </div>
                <div className="page-heading-actions">
                  <span className={"status " + (locked ? "approved" : "")}>
                    {locked ? (
                      <CheckCheck size={15} />
                    ) : (
                      <span className="dot" />
                    )}
                    {labels[state.status]}
                  </span>
                  {state.permissions?.can_view_content !== false && (
                    <PageNavigation
                      tab={tab}
                      busy={navigationBusy}
                      onNavigate={(next) => {
                        setTab(next);
                        setError("");
                        setNotice("");
                      }}
                    />
                  )}
                </div>
              </div>
              {state.permissions?.can_view_content === false ? (
                <RecipientView
                  state={state}
                  tab={tab}
                  setSelected={setSelected}
                />
              ) : ["overview", "schedule", "qa"].includes(tab) ? (
                <FeatureWorkspace
                  key={handoverId}
                  handoverId={handoverId}
                  currentUser={currentUser}
                  state={state}
                  tab={tab}
                  setSelected={setSelected}
                  onBusy={setFeatureBusy}
                  onRefresh={refresh}
                  externalBusy={generating}
                  onOpenChecklist={(id) => {
                    setFilter("전체");
                    setChecklistTarget(id);
                    setTab("checklist");
                  }}
                />
              ) : state.permissions?.can_manage === false ? (
                <RecipientView
                  state={state}
                  tab={tab}
                  setSelected={setSelected}
                />
              ) : (
                <div
                  className={
                    "work-area " +
                    (tab === "documents" ? "documents-only" : "checklist-only")
                  }
                >
                  {tab === "documents" && (
                    <DocumentPanel
                      deleteDocument={deleteDocument}
                      addSample={addSample}
                      deleteAllDocuments={deleteAllDocuments}
                      docs={docs}
                      busy={busy}
                      locked={locked}
                      dirty={dirty}
                      state={state}
                      setFocusedDocument={setFocusedDocument}
                      input={input}
                      upload={upload}
                      uploadProgress={uploadProgress}
                      elapsed={elapsed}
                      focusedDoc={focusedDoc}
                      focusedDocument={focusedDocument}
                      documentProgress={documentProgress}
                    />
                  )}
                  {tab === "documents" && (
                    <DocumentAnalysis
                      setSelected={setSelected}
                      busy={busy}
                      documentProgress={documentProgress}
                      readyDocs={readyDocs}
                      docs={docs}
                      analysisView={analysisView}
                      setAnalysisView={setAnalysisView}
                      analyzing={analyzing}
                      progressFiles={progressFiles}
                      elapsed={elapsed}
                      focusedDocument={focusedDocument}
                      setFocusedDocument={setFocusedDocument}
                      focusedDoc={focusedDoc}
                      locked={locked}
                      dirty={dirty}
                      analyzeDocument={analyzeDocument}
                      analyzeAllDocuments={analyzeAllDocuments}
                    />
                  )}
                  {tab === "checklist" && (
                    <ChecklistPanel
                      setSelected={setSelected}
                      approveChecklist={approveChecklist}
                      saveChecklist={saveChecklist}
                      suggestDependencies={suggestDependencies}
                      markAllReviewed={markAllReviewed}
                      reopenChecklist={reopenChecklist}
                      locked={locked}
                      state={state}
                      busy={busy}
                      dirty={dirty}
                      docs={docs}
                      readyDocs={readyDocs}
                      generate={generate}
                      items={items}
                      changed={changed}
                      filter={filter}
                      setFilter={setFilter}
                      reviewed={reviewed}
                      add={add}
                      progress={progress}
                      elapsed={elapsed}
                      visible={visible}
                      edit={edit}
                      deleteItem={deleteItem}
                    />
                  )}
                </div>
              )}
            </>
          )}
          <div className="page-footnote">
            업무 인수인계 Agent{" "}
            <span>문서 · 체크리스트 · 일정 · 업무 질문</span>
          </div>
        </main>
      </div>
      {selected && (
        <EvidenceDrawer
          setSelected={setSelected}
          selected={selected}
          docs={docs}
          handoverId={handoverId}
        />
      )}
    </div>
  );
}
