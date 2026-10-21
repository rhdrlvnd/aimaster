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
        aria-label="원문 근거"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-title">
          <h2>원문 근거</h2>
          <button
            className="icon-button"
            aria-label="원문 닫기"
            onClick={() => setSelected(null)}
          >
            <X />
          </button>
        </div>
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
          <>
            <span className="eyebrow">
              {selected.kind === "visual"
                ? "AI가 이미지에서 해석한 근거 · 직접 확인 필요"
                : "인용한 내용"}
            </span>
            <blockquote>{selected.quote}</blockquote>
          </>
        )}
        {(document?.warnings || []).map((w, i) => (
          <p className="inline-warning" key={i}>
            {w}
          </p>
        ))}
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
        <span className="eyebrow">추출한 문서 내용</span>
        <pre>{document?.text}</pre>
        <button onClick={() => setSelected(null)}>닫기</button>
      </aside>
    </div>
  );
}
