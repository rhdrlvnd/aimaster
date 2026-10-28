import ProgressStep from "../common/ProgressStep";
import React from "react";
import { CheckCheck, LoaderCircle, CircleHelp } from "lucide-react";
const generationSteps = [
  ["prepare", "자료 준비"],
  ["retrieve", "문서 근거 검색"],
  ["analyze", "AI 업무 분석"],
  ["validate", "결과 검증"],
  ["save", "초안 저장"],
];
export default function GenerationProgress({ progress, busy, elapsed }) {
  const index = generationSteps.findIndex(
    ([key]) => key === (progress.failedStage || progress.stage),
  );
  return (
    <section
      className="generation-progress"
      aria-label="체크리스트 생성 진행 상태"
      aria-busy={busy}
    >
      <div className="generation-title">
        <strong>
          {busy ? (
            <LoaderCircle className="spin" size={22} />
          ) : progress.stage === "done" ? (
            <CheckCheck size={22} />
          ) : (
            <CircleHelp size={22} />
          )}{" "}
          {busy
            ? "체크리스트를 만들고 있어요"
            : progress.stage === "done"
              ? "초안 생성 완료"
              : "처리를 완료하지 못했어요"}
        </strong>
        <span>
          {Math.floor(elapsed / 60)}분 {elapsed % 60}초 경과
        </span>
      </div>
      <ol>
        {generationSteps.map(([key, label], i) => {
          const done = progress.stage === "done" || index > i;
          const active =
            key === progress.stage ||
            (key === "prepare" && progress.stage === "connecting");
          const showDetail =
            active ||
            (progress.stage === "error" && i === Math.max(index, 0)) ||
            (progress.stage === "done" && key === "save");
          return (
            <ProgressStep
              key={key}
              label={label}
              status={
                done
                  ? "complete"
                  : progress.stage === "error"
                    ? i === Math.max(index, 0)
                      ? "failed"
                      : "skipped"
                    : active
                      ? "active"
                      : "waiting"
              }
              detail={
                showDetail ? (
                  <span role="status">
                    {progress.detail}
                    {busy && elapsed >= 30 && key === "analyze" && (
                      <span className="inline-wait-note">
                        AI 응답은 요청당 최대 10분까지 기다립니다.
                      </span>
                    )}
                  </span>
                ) : undefined
              }
              iconSize={18}
            />
          );
        })}
      </ol>
    </section>
  );
}
