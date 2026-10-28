import { useEffect, useRef, useState } from "react";
import { api as request, streamRequest as stream } from "../services/api";
import {
  updateDocumentProgress,
  savedDocumentProgress,
} from "../documentProgress";
import useElapsedTime from "./useElapsedTime";
export default function useWorkspace(handoverId) {
  const prefix = "/handovers/" + encodeURIComponent(handoverId);
  const api = (path, method, body) => request(prefix + path, method, body);
  const streamRequest = (body, onProgress, path = "/api/documents/stream") =>
    stream(body, onProgress, "/api" + prefix + path.replace(/^\/api/, ""));
  const [state, setState] = useState(null),
    [items, setItems] = useState([]),
    [tab, setTab] = useState("overview");
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [uploadProgress, setUploadProgress] = useState("");
  const [documentProgress, setDocumentProgress] = useState([]);
  const [focusedDocument, setFocusedDocument] = useState(null);
  const [analysisView, setAnalysisView] = useState("results");
  const [progress, setProgress] = useState(null);
  const elapsed = useElapsedTime(busy);
  const [dirty, setDirty] = useState(false),
    [filter, setFilter] = useState("전체"),
    [selected, setSelected] = useState(null);
  const input = useRef(null);
  async function refresh() {
    const data = await api("/workspace");
    setState(data);
    setItems(data.items);
    setDirty(false);
    return data;
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    const guard = (event) => {
      if (dirty || busy) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty, busy]);
  async function action(name, fn, message) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
      if (message) setNotice(message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  const locked = state?.status === "approved",
    reviewed = items.filter((i) => i.reviewed).length;
  const changed = state?.status === "stale";
  function edit(id, key, value) {
    setItems((prev) =>
      prev.map((i) =>
        i.id === id
          ? {
              ...i,
              [key]: value,
              ...(key === "dependencies"
                ? {
                    dependency_notes: Object.fromEntries(
                      Object.entries(i.dependency_notes || {}).filter(([id]) =>
                        value.includes(id),
                      ),
                    ),
                  }
                : {}),
              ...(key !== "reviewed" ? { reviewed: false } : {}),
            }
          : i,
      ),
    );
    setDirty(true);
  }
  async function upload(fileList) {
    const files = Array.from(fileList || []);
    if (input.current) input.current.value = "";
    if (!files.length || busy || locked) return;
    if (dirty) {
      setError("수정한 항목을 먼저 저장해 주세요.");
      return;
    }
    const remaining = 10 - (state?.documents.length || 0);
    if (files.length > remaining) {
      setError(
        `문서는 총 10개까지 등록할 수 있습니다. 현재 추가 가능한 파일은 ${remaining}개입니다.`,
      );
      return;
    }
    setAnalysisView("progress");
    setBusy("upload");
    setError("");
    setNotice("");
    setProgress(null);
    setDocumentProgress(
      files.map((file) => ({
        name: file.name,
        stage: "queued",
        detail: "처리 대기 중",
      })),
    );
    const updateFile = (index, event) =>
      setDocumentProgress((previous) =>
        previous.map((file, i) =>
          i === index ? updateDocumentProgress(file, event) : file,
        ),
      );
    let succeeded = 0;
    const failures = [];
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setUploadProgress(`${i + 1} / ${files.length} · ${file.name}`);
        const form = new FormData();
        form.append("file", file);
        let lastStage = "receive";
        updateFile(i, {
          stage: "receive",
          detail: "파일을 서버로 보내고 있습니다.",
        });
        try {
          await streamRequest(form, (event) => {
            lastStage = event.stage;
            updateFile(i, event);
          });
          succeeded++;
        } catch (e) {
          updateFile(i, {
            stage: "error",
            failedStage: lastStage,
            detail: e.message,
          });
          failures.push(`${file.name}: ${e.message}`);
        }
      }
      try {
        const data = await refresh();
        const latest = [...data.documents]
          .reverse()
          .find((d) => files.some((f) => f.name === d.name));
        if (latest) setFocusedDocument(latest.id);
        setAnalysisView("results");
      } catch (e) {
        failures.push(
          `목록 갱신 실패: ${e.message} 새로고침하여 등록 상태를 확인해 주세요.`,
        );
      }
      if (succeeded)
        setNotice(
          `${files.length}개 중 ${succeeded}개 문서의 등록과 AI 분석을 완료했습니다. 체크리스트에서 AI 초안을 생성해 주세요.`,
        );
      if (failures.length) setError(failures.join("\n"));
    } finally {
      setBusy("");
      setUploadProgress("");
    }
  }
  const analyzeDocument = (doc) => analyzeDocuments([doc]);
  const analyzeAllDocuments = () => analyzeDocuments(state.documents);
  async function analyzeDocuments(documents) {
    if (busy || dirty || locked || !documents.length) return;
    setAnalysisView("progress");
    setBusy("index");
    setError("");
    setNotice("");
    setDocumentProgress(
      documents.map((doc) => ({
        ...savedDocumentProgress({ ...doc, rag: null }),
        stage: "queued",
        detail: "분석 대기 중입니다.",
      })),
    );
    const failures = [];
    let succeeded = 0;
    const update = (id, event) =>
      setDocumentProgress((previous) =>
        previous.map((file) =>
          file.document_id === id ? updateDocumentProgress(file, event) : file,
        ),
      );
    try {
      for (const doc of documents) {
        setFocusedDocument(doc.id);
        let lastStage = "summarize";
        update(doc.id, {
          stage: lastStage,
          detail: "등록한 문서의 분석을 시작합니다.",
        });
        try {
          // Every analysis changes the revision, including partial failures.
          const current = await api("/workspace");
          await streamRequest(
            { revision: current.revision },
            (event) => {
              lastStage = event.stage;
              update(doc.id, event);
            },
            `/api/documents/${doc.id}/analyze/stream`,
          );
          succeeded++;
        } catch (e) {
          failures.push(`${doc.name}: ${e.message}`);
          update(doc.id, {
            stage: "error",
            failedStage: lastStage,
            detail: e.message,
          });
        }
      }
      setNotice(
        `${documents.length}개 중 ${succeeded}개 문서의 분석을 완료했습니다.${failures.length ? ` 실패 ${failures.length}개는 개별 재분석할 수 있습니다.` : ""}`,
      );
      if (failures.length) setError(failures.join("\n"));
    } finally {
      try {
        await refresh();
      } catch (e) {
        setError((previous) =>
          [previous, e.message].filter(Boolean).join("\n"),
        );
      }
      setBusy("");
    }
  }
  async function generate() {
    if (busy || locked) return;
    if (
      (items.length || dirty) &&
      !window.confirm(
        dirty
          ? "저장하지 않은 검토·수정 내용이 있습니다. 새 초안 생성이 완료되면 체크리스트가 교체되고 기존 일정과 진행 상태가 초기화됩니다. 계속할까요?"
          : "새 초안 생성이 완료되면 체크리스트가 교체되고 기존 일정과 진행 상태가 초기화됩니다. 계속할까요?",
      )
    )
      return;
    setBusy("generate");
    setError("");
    setNotice("");
    setProgress({
      stage: "connecting",
      detail: "서버에 분석을 요청하고 있습니다.",
    });
    try {
      await streamRequest(
        { revision: state.revision },
        setProgress,
        "/api/generate/stream",
      );
      await refresh();
      setNotice("AI 초안을 생성했습니다. 원문과 비교해 검토해 주세요.");
    } catch (e) {
      setError(e.message);
      setProgress((previous) => ({
        stage: "error",
        failedStage: previous?.stage,
        detail: e.message,
      }));
    } finally {
      setBusy("");
    }
  }

  function add() {
    setItems((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        title: "",
        description: "",
        category: "업무",
        priority: "보통",
        evidence: [],
        reviewed: false,
        origin: "manual",
      },
    ]);
    setDirty(true);
    setFilter("전체");
  }
  const docs = state?.documents || [];
  const focusedDoc = docs.find((d) => d.id === focusedDocument) || docs[0];
  const analyzing = busy === "upload" || busy === "index";
  const progressFiles = [
    ...docs.map((doc) => {
      const live = documentProgress.find(
        (f) =>
          f.document_id === doc.id || (!f.document_id && f.name === doc.name),
      );
      return live
        ? { ...live, document_id: doc.id }
        : savedDocumentProgress(doc);
    }),
    ...documentProgress.filter(
      (f) =>
        !docs.some(
          (doc) =>
            f.document_id === doc.id || (!f.document_id && f.name === doc.name),
        ),
    ),
  ];
  const readyDocs = docs.filter((d) => d.rag?.status === "ready").length;
  const visible = items.filter(
    (i) =>
      filter === "전체" || (filter === "미검토" ? !i.reviewed : i.reviewed),
  );

  const deleteAllDocuments = () => {
    if (
      !window.confirm(
        `등록된 문서 ${docs.length}개와 전체 내용 정리·검색 데이터·PPT 이미지를 모두 삭제합니다. 되돌릴 수 없습니다.\n\n기존 체크리스트는 남지만 원문 근거가 제거되어 새 문서로 다시 생성해야 합니다.\n문서를 모두 삭제할까요?`,
      )
    )
      return;
    action(
      "delete-all",
      async () => {
        await api(`/documents?revision=${state.revision}`, "DELETE");
        setDocumentProgress([]);
        setProgress(null);
        setFocusedDocument(null);
        setSelected(null);
      },
      "모든 업무 문서를 삭제했습니다. 새 문서를 등록해 주세요.",
    );
  };
  const addSample = () =>
    action(
      "sample",
      () => api("/sample", "POST"),
      "가상의 운영 매뉴얼을 등록했습니다.",
    );
  const reopenChecklist = () =>
    action(
      "reopen",
      () => api("/reopen", "POST", { revision: state.revision }),
      "검토를 다시 열었습니다.",
    );
  const saveChecklist = () =>
    action(
      "save",
      () => api("/checklist", "PUT", { revision: state.revision, items }),
      "검토 내용을 저장했습니다.",
    );
  const suggestDependencies = () => {
    if (busy || locked || dirty) return;
    if (
      !window.confirm(
        "AI가 선행 업무를 다시 제안하고 검토 상태를 초기화합니다. 계속할까요?",
      )
    )
      return;
    return action(
      "dependencies",
      () =>
        streamRequest(
          { revision: state.revision },
          setProgress,
          "/api/checklist/dependencies/stream",
        ),
      "선행 업무 제안을 확인하고 검토해 주세요.",
    );
  };
  const approveChecklist = () =>
    action(
      "approve",
      () => api("/approve", "POST", { revision: state.revision }),
      "체크리스트를 확정했습니다.",
    );
  const deleteDocument = (doc) => {
    if (
      window.confirm(
        "문서를 삭제하면 이 문서에 연결된 원문 근거도 제거됩니다. 기존 초안은 현재 문서로 다시 생성해야 합니다. 삭제할까요?",
      )
    )
      action(
        "delete",
        () => api(`/documents/${doc.id}?revision=${state.revision}`, "DELETE"),
        "문서를 삭제했습니다.",
      );
  };
  function deleteItem(id) {
    if (
      window.confirm("이 항목을 삭제할까요? 저장 버튼을 눌러야 반영됩니다.")
    ) {
      setItems((prev) =>
        prev
          .filter((i) => i.id !== id)
          .map((i) =>
            (i.dependencies || []).includes(id)
              ? {
                  ...i,
                  reviewed: false,
                  dependencies: i.dependencies.filter((key) => key !== id),
                  dependency_notes: Object.fromEntries(
                    Object.entries(i.dependency_notes || {}).filter(
                      ([key]) => key !== id,
                    ),
                  ),
                }
              : i,
          ),
      );
      setDirty(true);
    }
  }
  function markAllReviewed() {
    if (busy || locked || changed || !items.length) return;
    const count = items.filter((item) => !item.reviewed).length;
    if (!count) return;
    setItems((previous) =>
      previous.map((item) => ({ ...item, reviewed: true })),
    );
    setDirty(true);
    setNotice(
      `${count}개 항목을 검토 완료로 표시했습니다. ‘변경 저장’ 후 ‘검토 확정’을 진행해 주세요.`,
    );
  }
  return {
    markAllReviewed,
    addSample,
    reopenChecklist,
    saveChecklist,
    suggestDependencies,
    approveChecklist,
    deleteItem,
    deleteDocument,
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
  };
}
