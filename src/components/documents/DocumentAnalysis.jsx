import React from "react";
import { ListChecks, Sparkles, LoaderCircle, RefreshCw } from "lucide-react";
import DocumentProgress from "./DocumentProgress";
import DocumentResult from "./DocumentResult";

export default function DocumentAnalysis({
  busy,
  documentProgress,
  readyDocs,
  docs,
  analysisView,
  setAnalysisView,
  analyzing,
  progressFiles,
  elapsed,
  focusedDocument,
  setFocusedDocument,
  focusedDoc,
  setSelected,
  locked,
  dirty,
  analyzeDocument,
  analyzeAllDocuments,
}) {
  return (
    <section className="document-results" aria-label="문서 분석 현황">
      <div className="section-top">
        <h2>
          문서 분석{" "}
          <span>
            {busy === "upload"
              ? `${documentProgress.filter((f) => f.stage === "done").length} / ${documentProgress.length}`
              : `${readyDocs} / ${docs.length}`}
          </span>
        </h2>
        <button
          type="button"
          className="primary reanalyze-button bulk-reanalyze-button"
          disabled={!!busy || locked || dirty || !docs.length}
          onClick={analyzeAllDocuments}
          title={
            locked
              ? "체크리스트 검토를 다시 열면 분석할 수 있습니다."
              : dirty
                ? "변경 사항을 먼저 저장해 주세요."
                : "등록한 모든 문서를 순서대로 다시 분석합니다."
          }
        >
          <RefreshCw size={17} aria-hidden="true" />
          전체 문서 다시 분석
        </button>
      </div>
      <div className="analysis-tabs" aria-label="분석 보기 전환">
        {[
          ["progress", "분석 진행"],
          ["results", "분석 결과"],
        ].map(([key, label]) => (
          <button
            key={key}
            aria-pressed={analysisView === key}
            className={analysisView === key ? "selected" : ""}
            onClick={() => setAnalysisView(key)}
          >
            {label}
            {key === "progress" && analyzing && (
              <LoaderCircle size={14} className="spin" />
            )}
          </button>
        ))}
      </div>
      {analysisView === "progress" &&
        (progressFiles.length > 0 ? (
          <DocumentProgress
            files={progressFiles}
            busy={analyzing}
            elapsed={elapsed}
            focusedDocument={analyzing ? null : focusedDocument}
            onSelect={setFocusedDocument}
          />
        ) : (
          <div className="analysis-overview">
            <ListChecks size={22} />
            <div>
              <strong>진행 중인 분석이 없습니다</strong>
              <p>
                문서를 등록하면 단계별 진행 상황이 표시됩니다. 완료한 문서는
                분석 결과에서 확인하세요.
              </p>
            </div>
          </div>
        ))}
      {analysisView === "results" &&
        (focusedDoc ? (
          <>
            <DocumentResult
              doc={focusedDoc}
              onOpen={() =>
                setSelected({ document_id: focusedDoc.id, quote: "" })
              }
            />
            <button
              className="primary reanalyze-button"
              type="button"
              disabled={!!busy || locked || dirty}
              onClick={() => analyzeDocument(focusedDoc)}
            >
              <RefreshCw size={17} aria-hidden="true" />
              {focusedDoc.rag?.status === "ready" ||
              focusedDoc.rag?.status === "outdated"
                ? "AI 문서 다시 분석"
                : "AI 문서 분석 시작"}
            </button>
          </>
        ) : (
          <div className="analysis-overview">
            <ListChecks size={22} />
            <div>
              <strong>아직 분석 결과가 없습니다</strong>
              <p>문서 분석이 완료되면 이곳에서 결과를 확인할 수 있습니다.</p>
            </div>
          </div>
        ))}
    </section>
  );
}
