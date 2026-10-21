export async function api(path, method = "GET", body) {
  const response = await fetch(`/api${path}`, {
    method,
    ...(body instanceof FormData
      ? { body }
      : body
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }
        : {}),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "서버 응답을 읽지 못했습니다. 서버 실행 상태를 확인해 주세요.",
    );
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "입력 내용을 확인해 주세요.",
    );
  return data;
}

export async function streamRequest(
  form,
  onProgress,
  path = "/api/documents/stream",
) {
  const response = await fetch(path, {
    method: "POST",
    ...(form instanceof FormData
      ? { body: form }
      : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        }),
  });
  if (!response.ok) {
    let message = "문서 등록 요청에 실패했습니다.";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {}
    throw new Error(message);
  }
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "",
    completed = false;
  function consume(line) {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.stage === "heartbeat") return;
    if (event.stage === "error") throw new Error(event.detail);
    onProgress(event);
    if (event.stage === "done") completed = true;
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.forEach(consume);
      if (done) {
        consume(buffer);
        break;
      }
    }
    if (!completed)
      throw new Error(
        "연결이 끊어졌습니다. 문서 목록에서 등록 여부를 확인해 주세요.",
      );
  } finally {
    try {
      await reader.cancel();
    } catch {}
    reader.releaseLock();
  }
}
