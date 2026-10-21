export function updateDocumentProgress(file, event) {
  const results = { ...file.results };
  const detail = event.detail || "";
  const number = (pattern) => detail.match(pattern)?.[1];
  const chars = number(/([\d,]+)자 추출 완료/);
  const slides = number(/슬라이드 ([\d,]+)장 변환 완료/);
  if (chars) results.extract = `텍스트 추출 완료 (${chars}자)`;
  if (slides) results.render = `${slides}장 이미지 변환 완료`;
  if (event.stage === "extract") results.receive = "파일 수신 완료";
  if (event.stage === "summarize") results.save = "문서 보관 완료";
  if (event.stage === "chunk") results.summarize = "전체 내용 정리 완료";
  const chunks = number(/([\d,]+)개 청크/);
  if (chunks) results.chunk = `${chunks}개 청크 생성`;
  const vectors = number(/([\d,]+)개 벡터 생성 완료/);
  if (vectors) results.embed = `${vectors}개 벡터 생성 완료`;
  if (event.stage === "done") results.store = "검색 자료 저장 완료";
  return { ...file, ...event, results };
}

export function savedDocumentProgress(doc) {
  const ready = doc.rag?.status === "ready";
  return {
    document_id: doc.id,
    name: doc.name,
    stage: ready ? "done" : "saved",
    detail: ready
      ? "문서 분석 완료"
      : doc.rag?.error || "AI 분석이 필요합니다.",
    results: {
      receive: "파일 수신 완료",
      extract: `텍스트 추출 완료 (${doc.text.length.toLocaleString()}자)`,
      ...(doc.slide_count
        ? { render: `${doc.slide_count}장 이미지 변환 완료` }
        : {}),
      save: "문서 보관 완료",
      ...(ready
        ? {
            summarize: "전체 내용 정리 완료",
            chunk: `${doc.rag.chunk_count}개 청크 생성`,
            embed: `${doc.rag.vector_count ?? doc.rag.chunk_count}개 벡터 생성 완료`,
            store: `${doc.rag.chunk_count}개 검색 자료 저장 완료`,
          }
        : {}),
    },
  };
}
