import React from "react";
import { FileText, X } from "lucide-react";

export default function EvidenceDrawer({
  selected,
  setSelected,
  docs,
  handoverId,
}) {
  const document = docs.find((doc) => doc.id === selected.document_id);
  return (
    <div className="drawer-backdrop" onClick={() => setSelected(null)}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={selected.quote ? "연결된 근거" : "업무 문서"}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-title">
          <h2>{selected.quote ? "연결된 근거" : "업무 문서"}</h2>
          <button
            className="icon-button"
            aria-label="원문 닫기"
            onClick={() => setSelected(null)}
          >
            <X />
          </button>
        </div>
        {selected.itemTitle && (
          <div className="evidence-item-context">
            <span className="eyebrow">선택한 체크리스트</span>
            <p>{selected.itemTitle}</p>
          </div>
        )}
        <p className="source-name">
          <FileText size={17} />
          {document?.name || "문서를 찾을 수 없음"}
        </p>
        {document && (
          <button
            onClick={async () => {
              const response = await fetch(
                `/api/handovers/${handoverId}/documents/${document.id}/download`,
              );
              if (!response.ok) {
                const error = await response.json();
                window.alert(error.detail);
                return;
              }
              const url = URL.createObjectURL(await response.blob());
              const link = window.document.createElement("a");
              link.href = url;
              link.download = document.name;
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}
          >
            원본 파일 다운로드
          </button>
        )}
        {selected.quote && (
          <section className="evidence-excerpt">
            <h3>
              {selected.itemTitle
                ? "이 항목에 연결된 인용문"
                : "답변에 연결된 인용문"}
            </h3>
            <p className="evidence-help">
              {selected.itemTitle
                ? "체크리스트의 내용과 아래 인용문을 비교해 확인하세요. 전체 맥락은 원본 파일을 다운로드해 확인할 수 있습니다."
                : "답변에서 근거로 연결한 부분입니다. 아래 인용 내용을 확인하세요."}
            </p>
            <span className="eyebrow">
              {selected.kind === "visual"
                ? "AI가 이미지에서 해석한 근거 · 직접 확인 필요"
                : "문서에서 인용한 내용"}
            </span>
            <blockquote>{selected.quote}</blockquote>
          </section>
        )}
        {document?.slide_count > 0 && (
          <section className="slide-preview">
            <label>
              슬라이드{" "}
              <select
                aria-label="슬라이드 선택"
                value={selected.slide || 1}
                onChange={(e) =>
                  setSelected({ ...selected, slide: Number(e.target.value) })
                }
              >
                {Array.from(
                  {
                    length: document.slide_count,
                  },
                  (_, i) => (
                    <option key={i + 1} value={i + 1}>
                      {i + 1}
                    </option>
                  ),
                )}
              </select>
            </label>
            <a
              href={`/api/handovers/${handoverId}/documents/${selected.document_id}/slides/${selected.slide || 1}`}
              target="_blank"
              rel="noreferrer"
            >
              크게 보기
            </a>
            <img
              key={`${selected.document_id}-${selected.slide || 1}`}
              src={`/api/handovers/${handoverId}/documents/${selected.document_id}/slides/${selected.slide || 1}`}
              alt={`슬라이드 ${selected.slide || 1}`}
            />
          </section>
        )}
        {document && !selected.quote && (
          <details
            className="evidence-document-context"
            key={`${selected.document_id}-${selected.quote || "document"}-${selected.itemTitle || ""}`}
            open
          >
            <summary>문서 전체 내용 보기</summary>
            <p className="evidence-help">
              파일에서 추출한 텍스트와 표입니다. 원래 파일의 배치는 원본
              다운로드로 확인하세요.
            </p>
            {document.text ? (
              <pre>{document.text}</pre>
            ) : (
              <p>추출된 본문이 없습니다.</p>
            )}
            {document.warnings?.length > 0 && (
              <div className="evidence-extraction-notes">
                <h3>문서 추출 범위 안내</h3>
                {[...new Set(document.warnings)].map((warning) => (
                  <p className="evidence-help" key={warning}>
                    {warning}
                  </p>
                ))}
              </div>
            )}
          </details>
        )}
        <button onClick={() => setSelected(null)}>닫기</button>
      </aside>
    </div>
  );
}
