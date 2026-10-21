import React, { useState } from "react";
export default function ExportPanel({
  state,
  data,
  busy,
  run,
  prefix,
  currentUser,
  setError,
}) {
  const [name, setName] = useState(""),
    [consent, setConsent] = useState(false),
    [downloading, setDownloading] = useState(false);
  async function download() {
    setDownloading(true);
    try {
      const response = await fetch("/api" + prefix + "/export");
      if (!response.ok) {
        let e = await response.json();
        throw Error(e.detail || "출력 실패");
      }
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = state.handover.name + ".docx";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  }
  return (
    <section className="feature-card">
      <h2>인수인계 문서 출력·서명</h2>
      <p>
        확정한 체크리스트와 일정을 Word 문서로 출력합니다. 성명 입력과 동의
        기록을 서명으로 남깁니다.
      </p>
      <div className="feature-form-row">
        <label>
          인계자 성명
          <input
            aria-label="서명 성명"
            disabled={busy}
            placeholder={currentUser.name}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
          />
          내용과 일정을 확인했으며 서명에 동의합니다.
        </label>
      </div>
      <div className="feature-actions">
        <button
          disabled={
            busy ||
            !data.schedule_current ||
            !data.schedule.confirmed ||
            !consent ||
            name !== currentUser.name
          }
          onClick={() => run("/signature", { name, consent })}
        >
          서명 저장
        </button>
        <button
          className="primary"
          disabled={
            busy || downloading || !data.signature || !data.schedule_current
          }
          onClick={download}
        >
          {downloading ? "문서 생성 중…" : "Word 문서 다운로드"}
        </button>
      </div>
      {data.signature && (
        <p>
          서명자 {data.signature.name} · {data.signature.signed_at}
        </p>
      )}
    </section>
  );
}
