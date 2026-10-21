import ProgressStep from "../common/ProgressStep";
import React, { useEffect, useState } from "react";
export default function DocumentProgress({
  files,
  busy,
  elapsed,
  focusedDocument,
  onSelect,
}) {
  const [picked, setPicked] = useState(null);
  useEffect(() => {
    setPicked(null);
  }, [busy]);
  useEffect(() => {
    if (focusedDocument) setPicked(focusedDocument);
  }, [focusedDocument]);
  const current = files.findIndex(
    (file) => !["queued", "done", "error", "saved"].includes(file.stage),
  );
  const selected = files.findIndex((f) => (f.document_id || f.name) === picked);
  const shown = selected >= 0 ? selected : current >= 0 ? current : 0;
  return (
    <section
      className="document-progress"
      aria-label="AI 분석 진행 상황"
      aria-busy={busy}
    >
      <div className="generation-title">
        <strong>AI 분석 진행 상황</strong>
        {busy && <span>{elapsed}초 경과</span>}
      </div>
      <div className="progress-document-picker">
        <label htmlFor="progress-document">확인할 문서</label>
        <select
          id="progress-document"
          value={files[shown]?.document_id || files[shown]?.name || ""}
          onChange={(e) => {
            setPicked(e.target.value);
            const file = files.find(
              (f) => (f.document_id || f.name) === e.target.value,
            );
            if (file?.document_id) onSelect(file.document_id);
          }}
        >
          {files.map((file) => (
            <option
              key={file.document_id || file.name}
              value={file.document_id || file.name}
            >
              {file.name} ·{" "}
              {file.stage === "done"
                ? "완료"
                : file.stage === "error"
                  ? "실패"
                  : file.stage === "queued"
                    ? "대기"
                    : file.stage === "saved"
                      ? "분석 필요"
                      : "분석 중"}
            </option>
          ))}
        </select>
        {busy && picked && (
          <button className="text-button" onClick={() => setPicked(null)}>
            현재 분석 문서 보기
          </button>
        )}
      </div>
      {files.slice(shown, shown + 1).map((file) => {
        const steps = [
          ["receive", "파일 업로드"],
          ["extract", "텍스트·표 추출"],
          ...(file.name.toLowerCase().endsWith(".pptx")
            ? [["render", "슬라이드 이미지 변환"]]
            : []),
          ["save", "문서 보관"],
          ["summarize", "전체 내용 정리"],
          ["chunk", "문서 청킹"],
          ["embed", "벡터 임베딩"],
          ["store", "ChromaDB 저장"],
        ];
        const index = steps.findIndex(
          ([key]) => key === (file.failedStage || file.stage),
        );
        return (
          <article className="file-progress" key={shown}>
            <strong className="processing-filename">
              {shown + 1} / {files.length} · {file.name}
            </strong>
            <ol>
              {steps.map(([key, label], n) => {
                const done =
                  !!file.results?.[key] || file.stage === "done" || n < index;
                const failed = file.stage === "error" && n === index;
                const active = file.stage === key;
                return (
                  <ProgressStep
                    key={key}
                    label={label}
                    status={
                      failed
                        ? "failed"
                        : done
                          ? "complete"
                          : active
                            ? "active"
                            : file.stage === "error"
                              ? "skipped"
                              : "waiting"
                    }
                    detail={
                      file.results?.[key] ||
                      (failed || active
                        ? file.detail
                        : done
                          ? "완료"
                          : file.stage === "error"
                            ? "미진행"
                            : "대기")
                    }
                  />
                );
              })}
            </ol>
            <p className={file.stage === "error" ? "failed" : ""} role="status">
              {file.detail}
            </p>
          </article>
        );
      })}
      <p className="processing-note">
        AI 분석이 완료된 문서로 체크리스트 초안을 생성할 수 있습니다.
      </p>
    </section>
  );
}
