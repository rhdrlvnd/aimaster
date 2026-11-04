import React, { useEffect, useState } from "react";
import {
  Activity,
  CircleCheck,
  Info,
  LoaderCircle,
  RefreshCw,
  Zap,
} from "lucide-react";
import { api } from "../../services/api";

const number = (value) => Number(value || 0).toLocaleString("ko-KR");
const periods = [
  ["today", "오늘"],
  ["month", "이번 달"],
  ["30d", "최근 30일"],
];
function UsageMetric({
  icon: Icon,
  title,
  value,
  unit,
  children,
  className = "",
}) {
  return (
    <article className={`ai-usage-metric ${className}`}>
      <div className="ai-usage-metric-title">
        <Icon size={17} />
        <span>{title}</span>
      </div>
      <div className="ai-usage-metric-value">
        {value}
        {unit && <span>{unit}</span>}
      </div>
      <div className="ai-usage-metric-detail">{children}</div>
    </article>
  );
}

function DailyChart({ rows }) {
  const maximum = Math.max(0, ...rows.map((row) => row.total_tokens));
  const scaleMaximum = Math.max(1, maximum);
  const populated = rows.some((row) => row.requests > 0);
  const unknown = rows.some((row) => row.unknown_usage_requests > 0);
  const step = rows.length > 15 ? 5 : rows.length > 7 ? 3 : 1;
  return (
    <section className="ai-usage-panel">
      <div className="ai-usage-panel-heading">
        <div>
          <h2>일별 토큰 사용량</h2>
          <p>AI 서버가 반환한 입력·출력 토큰의 합계입니다.</p>
        </div>
        <span className="ai-usage-chart-unit">
          {populated && maximum === 0 && unknown
            ? "확인된 토큰 없음"
            : `최대 ${number(maximum)} 토큰`}
        </span>
      </div>
      {!populated ? (
        <div className="ai-usage-chart-empty">
          선택한 기간에 기록된 요청이 없습니다.
        </div>
      ) : (
        <div
          className="ai-usage-chart"
          role="img"
          aria-label={`일별 토큰 사용량. ${rows
            .filter((row) => row.requests)
            .map(
              (row) =>
                `${row.date} ${number(row.total_tokens)} 토큰, ${number(row.requests)}회`,
            )
            .join(". ")}`}
        >
          {rows.map((row, index) => (
            <div
              className="ai-usage-chart-column"
              key={row.date}
              title={`${row.date}\n확인된 ${number(row.total_tokens)} 토큰 · ${number(row.requests)}회 요청${row.unknown_usage_requests ? `\n사용량 미확인 ${number(row.unknown_usage_requests)}회` : ""}`}
            >
              <div className="ai-usage-chart-track">
                <div
                  className={`ai-usage-chart-bar${row.requests && !row.total_tokens ? " is-unknown" : ""}`}
                  style={{
                    height: `${row.total_tokens ? Math.max(2, (row.total_tokens / scaleMaximum) * 100) : row.requests ? 3 : 0}%`,
                  }}
                />
              </div>
              <span>
                {index === 0 || index === rows.length - 1 || index % step === 0
                  ? row.date.slice(5).replace("-", "/")
                  : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function UsageBreakdown({ data }) {
  const [view, setView] = useState("models");
  const configs = {
    models: ["모델별", "모델", "model"],
    features: ["기능별", "기능", "operation"],
    handovers: ["인수인계별", "인수인계", "handover_id"],
    users: ["사용자별", "사용자 / 부서", "user_id"],
  };
  const rows = [...(data[view] || [])].sort(
    (a, b) => b.total_tokens - a.total_tokens || b.requests - a.requests,
  );
  return (
    <section className="ai-usage-panel">
      <div className="ai-usage-panel-heading">
        <div>
          <h2>사용량 상세</h2>
          <p>
            {view === "users"
              ? "AI 작업을 실행한 사용자 기준입니다. 같은 인수인계에서도 각 사용자의 요청을 나누어 집계합니다."
              : "문서 분석·체크리스트·일정·질문 답변 등 각 기능에서 발생한 AI 및 임베딩 요청을 합산합니다."}
          </p>
        </div>
        <div className="ai-usage-switches" aria-label="사용량 집계 기준">
          {Object.entries(configs).map(([key, [label]]) => (
            <button
              type="button"
              key={key}
              aria-pressed={view === key}
              onClick={() => setView(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="ai-usage-table-scroll">
        <table className="ai-usage-table">
          <thead>
            <tr>
              <th>{configs[view][1]}</th>
              <th>API 호출</th>
              <th>입력 토큰</th>
              <th>출력 토큰</th>
              <th>확인된 합계</th>
              <th>사용량 확인</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row[configs[view][2]] || "unassigned"}>
                <td>
                  <strong>
                    {view === "models"
                      ? row.model
                      : view === "features"
                        ? row.label
                        : row.name}
                  </strong>
                  {view === "users" && (
                    <small>
                      {[row.department, row.user_id]
                        .filter(Boolean)
                        .join(" · ") || "요청 사용자 정보 없음"}
                    </small>
                  )}
                </td>
                <td>
                  {number(row.requests)}회
                  {row.failed_requests > 0 && (
                    <small>실패 {number(row.failed_requests)}회</small>
                  )}
                </td>
                <td>
                  {number(row.input_tokens)}
                  {row.cached_input_tokens > 0 && (
                    <small>캐시 포함 {number(row.cached_input_tokens)}</small>
                  )}
                </td>
                <td>
                  {number(row.output_tokens)}
                  {row.reasoning_tokens > 0 && (
                    <small>추론 포함 {number(row.reasoning_tokens)}</small>
                  )}
                </td>
                <td>
                  <strong>{number(row.total_tokens)}</strong>
                  {row.unknown_usage_requests > 0 && (
                    <small className="ai-usage-caution">
                      미확인 {number(row.unknown_usage_requests)}회 제외
                    </small>
                  )}
                </td>
                <td>
                  {number(row.known_usage_requests)}/{number(row.requests)}회
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && (
        <div className="ai-usage-empty">집계할 사용 내역이 없습니다.</div>
      )}
    </section>
  );
}

export default function AdminAiUsage() {
  const [period, setPeriod] = useState("month");
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setData(null);
    api(`/admin/ai-usage?period=${period}`)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [period, revision]);
  const summary = data?.summary;
  const coverage = summary?.requests
    ? Math.floor((summary.known_usage_requests / summary.requests) * 1000) / 10
    : null;
  return (
    <div className="ai-usage-dashboard">
      <div className="ai-usage-toolbar">
        <div className="ai-usage-switches" aria-label="사용량 조회 기간">
          {periods.map(([key, label]) => (
            <button
              type="button"
              key={key}
              aria-pressed={period === key}
              onClick={() => setPeriod(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="ai-usage-period">
          {data && (
            <span>
              {data.start_date} ~ {data.end_date} · 한국 시간
            </span>
          )}
          <button
            type="button"
            disabled={loading}
            onClick={() => setRevision((v) => v + 1)}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            새로고침
          </button>
        </div>
      </div>
      {error && (
        <div className="alert error" role="alert">
          {error}
          <button type="button" onClick={() => setRevision((v) => v + 1)}>
            다시 불러오기
          </button>
        </div>
      )}
      {loading && (
        <div className="ai-usage-loading" role="status">
          <LoaderCircle size={20} className="spin" />
          AI 사용 내역을 불러오고 있어요.
        </div>
      )}
      {data && (
        <>
          <div className="ai-usage-metrics">
            <UsageMetric
              icon={Zap}
              title={
                summary.unknown_usage_requests
                  ? "확인된 토큰 사용량"
                  : "총 토큰 사용량"
              }
              value={number(summary.total_tokens)}
              unit="토큰"
            >
              <div>
                입력 {number(summary.input_tokens)} · 출력{" "}
                {number(summary.output_tokens)}
              </div>
              <div>
                입력 중 캐시 {number(summary.cached_input_tokens)} · 출력 중
                추론 {number(summary.reasoning_tokens)}
                {summary.unknown_usage_requests > 0 && (
                  <span className="ai-usage-caution">
                    {" "}
                    · 미확인 {number(summary.unknown_usage_requests)}회 제외
                  </span>
                )}
              </div>
            </UsageMetric>
            <UsageMetric
              icon={Activity}
              title="API 호출 수"
              value={number(summary.requests)}
              unit="회"
            >
              <div>
                성공 {number(summary.successful_requests)} · 실패{" "}
                {number(summary.failed_requests)}
              </div>
              <div>한 작업의 여러 AI·임베딩 호출과 재시도 포함</div>
            </UsageMetric>
            <UsageMetric
              icon={CircleCheck}
              title="사용량 확인률"
              value={
                coverage === null
                  ? data.first_request_at
                    ? "요청 없음"
                    : "기록 대기"
                  : coverage
              }
              unit={coverage === null ? undefined : "%"}
            >
              <div>
                사용량 확인 {number(summary.known_usage_requests)}/
                {number(summary.requests)}회
              </div>
              <div>
                {summary.unknown_usage_requests
                  ? `미확인 ${number(summary.unknown_usage_requests)}회 · 토큰 수 미반환`
                  : "AI 서버가 반환한 사용량 기준"}
              </div>
            </UsageMetric>
          </div>
          {summary.unknown_usage_requests > 0 && (
            <div className="ai-usage-information">
              <Info size={17} />
              <p>
                AI 서버가 토큰 수를 반환하지 않은{" "}
                {number(summary.unknown_usage_requests)}회는 합계에서
                제외합니다. 실제 사용량을 0으로 간주하지 않습니다.
              </p>
            </div>
          )}
          {!data.first_request_at && (
            <div className="ai-usage-information">
              <Info size={17} />
              <div>
                <p>
                  아직 기록된 AI 사용 내역이 없습니다. 문서 분석이나 체크리스트
                  생성 등 AI 기능을 사용하면 실제 응답의 토큰 수가 누적됩니다.
                </p>
                <p>
                  사용량 기록 기능을 적용하기 전의 요청은 소급 집계하지
                  않습니다.
                </p>
              </div>
            </div>
          )}
          <DailyChart rows={data.daily} />
          <UsageBreakdown data={data} />
          {data.first_request_at && (
            <p className="ai-usage-footnote">
              기록 기능 적용 후 수집한 요청만 표시합니다. 이전 요청의 사용량은
              복원하지 않습니다. 캐시 입력은 입력 토큰에, 추론 토큰은 출력
              토큰에 포함됩니다.
            </p>
          )}
        </>
      )}
    </div>
  );
}
