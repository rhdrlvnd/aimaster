import React from "react";
import {
  CheckCheck,
  FileText,
  Upload,
  Plus,
  Trash2,
  LoaderCircle,
  CircleHelp,
} from "lucide-react";

export default function DocumentPanel({
  deleteDocument,
  addSample,
  deleteAllDocuments,
  docs,
  busy,
  locked,
  dirty,
  state,
  setFocusedDocument,
  input,
  upload,
  uploadProgress,
  elapsed,
  focusedDoc,
  focusedDocument,
  documentProgress,
}) {
  return (
    <section className="document-panel">
      <div className="section-top">
        <h2>
          업무 문서 <span>{docs.length}</span>
        </h2>
        <button
          className="delete-documents"
          disabled={!!busy || locked || dirty || !docs.length}
          onClick={deleteAllDocuments}
        >
          <Trash2 size={14} />
          문서 전체 삭제
        </button>
      </div>
      <p className="subtext">AI가 체크리스트를 만들 때 참고할 문서</p>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        accept=".docx,.xlsx,.pptx,.txt,.md"
        onChange={(e) => upload(e.target.files)}
      />
      <button
        className="upload-zone"
        disabled={!!busy || locked || dirty}
        onClick={() => input.current.click()}
      >
        <span className="upload-icon">
          {busy === "upload" ? (
            <LoaderCircle className="spin" size={24} />
          ) : (
            <Upload size={22} />
          )}
        </span>
        <strong>
          {busy === "upload" ? "문서 처리 중…" : "업무 문서 등록"}
        </strong>
        <span>여러 파일 선택 가능 · 총 10개까지</span>
        <span>Word · Excel · PPT / 파일당 최대 10MB</span>
        {uploadProgress && (
          <span className="upload-progress" role="status">
            {uploadProgress} · {elapsed}초 경과
          </span>
        )}
      </button>
      <button
        className="sample-button"
        disabled={!!busy || locked || dirty}
        onClick={addSample}
      >
        <Plus size={15} /> 예시 문서로 시작하기
      </button>
      <div className="doc-list" hidden={busy === "upload"}>
        {docs.map((doc) => (
          <div
            className={
              "doc-row " +
              (doc.rag?.status === "ready"
                ? "doc-complete "
                : doc.rag?.status === "failed"
                  ? "doc-failed "
                  : "") +
              (focusedDoc?.id === doc.id ? "doc-focused" : "")
            }
            key={doc.id}
          >
            <button
              className="doc-open"
              onClick={() => {
                setFocusedDocument(doc.id);
              }}
            >
              <span className="doc-icon">
                {busy === "index" && focusedDocument === doc.id ? (
                  <LoaderCircle className="spin" size={18} />
                ) : doc.rag?.status === "ready" ? (
                  <CheckCheck size={18} />
                ) : doc.rag?.status === "failed" ? (
                  <CircleHelp size={18} />
                ) : (
                  <FileText size={18} />
                )}
              </span>
              <div>
                <strong>{doc.name}</strong>
                <small>
                  {doc.text.length.toLocaleString()}자 ·{" "}
                  {doc.rag?.status === "ready"
                    ? `분석 완료 · ${doc.rag.chunk_count}개 청크`
                    : doc.rag?.status === "failed"
                      ? "분석 실패 · 재시도 필요"
                      : "AI 분석 필요"}
                </small>
              </div>
            </button>
            <button
              className="icon-button"
              aria-label={`${doc.name} 삭제`}
              disabled={!!busy || locked || dirty}
              onClick={() => deleteDocument(doc)}
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
      {busy === "upload" && (
        <div className="upload-queue" aria-label="문서 처리 목록">
          {documentProgress.map((file, i) => (
            <div
              key={i}
              className={
                "queue-row " +
                (file.stage === "done"
                  ? "complete"
                  : file.stage === "error"
                    ? "failed"
                    : file.stage === "queued"
                      ? "waiting"
                      : "active")
              }
            >
              {file.stage === "done" ? (
                <CheckCheck size={17} />
              ) : file.stage === "error" ? (
                <CircleHelp size={17} />
              ) : file.stage === "queued" ? (
                <FileText size={17} />
              ) : (
                <LoaderCircle className="spin" size={17} />
              )}
              <span title={file.name}>{file.name}</span>
              <small>
                {file.stage === "done"
                  ? "완료"
                  : file.stage === "error"
                    ? "실패"
                    : file.stage === "queued"
                      ? "대기"
                      : "분석 중"}
              </small>
            </div>
          ))}
        </div>
      )}
      {!docs.length && busy !== "upload" && (
        <p className="no-docs">
          등록된 문서가 없습니다.
          <br />
          예시 문서로 흐름을 먼저 확인해 보세요.
        </p>
      )}
      <details className="document-help">
        <summary>지원 파일 및 분석 안내</summary>
        <p>
          PPT는 슬라이드 이미지와 텍스트를 함께 분석합니다(합계 20장).
          Word·Excel은 텍스트와 표를 읽습니다. TXT·MD도 지원합니다(500KB).
        </p>
      </details>
      <div className="ai-status">
        <span className={state.llm_configured ? "dot green" : "dot"} />
        {state.llm_configured
          ? "AI 연결 설정 있음 · 실행 시 확인"
          : "AI 연결 설정 필요"}
      </div>
    </section>
  );
}
