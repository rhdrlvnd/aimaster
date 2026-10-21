import React from "react";
import { ArrowUpRight, Check, CircleHelp } from "lucide-react";
export default function DocumentResult({ doc, onOpen }) {
  const rag = doc.rag || {},
    ready = rag.status === "ready";
  const rows = [
    ["텍스트·표 추출", `${doc.text.length.toLocaleString()}자 추출`, true],
    ...(doc.slide_count
      ? [["슬라이드 이미지 변환", `${doc.slide_count}장 변환`, true]]
      : []),
    [
      "전체 내용 정리",
      ready ? "내용 정리 완료" : "재분석 필요",
      ready,
    ],
    [
      "문서 청킹",
      ready ? `${rag.chunk_count}개 청크 생성` : "완료된 결과 없음",
      ready,
    ],
    [
      "벡터 임베딩",
      ready
        ? `${rag.vector_count ?? rag.chunk_count}개 벡터 생성`
        : "완료된 결과 없음",
      ready,
    ],
    [
      "ChromaDB 저장",
      ready ? `${rag.chunk_count}개 검색 자료 저장 완료` : "완료된 결과 없음",
      ready,
    ],
  ];
  return (
    <div className="document-result-detail">
      <div className="result-heading">
        <strong>{doc.name}</strong>
        <button className="text-button" onClick={onOpen}>
          원문 보기 <ArrowUpRight size={14} />
        </button>
      </div>
      <dl className="stage-results">
        {rows.map(([label, value, done]) => (
          <div key={label}>
            <dt>
              {done ? <Check size={16} /> : <CircleHelp size={16} />} {label}
            </dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {rag.embedding_model && (
        <p className="result-model">임베딩 모델: {rag.embedding_model}</p>
      )}
      {rag.organized_text && (
        <details className="result-summary">
          <summary>정리된 전체 내용 보기</summary>
          <p style={{whiteSpace:'pre-wrap',maxHeight:420,overflowY:'auto'}}>{rag.organized_text}</p>
        </details>
      )}
      {doc.warnings?.length > 0 && (
        <p className="analysis-error">{doc.warnings.join(" / ")}</p>
      )}
      {rag.limitations?.length>0 && <p className="analysis-error">{rag.limitations.join(' / ')}</p>}
      {rag.error && <p className="analysis-error">{rag.error}</p>}
    </div>
  );
}
