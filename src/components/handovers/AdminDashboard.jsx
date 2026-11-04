import React, { useEffect, useState } from "react";
import {
  BarChart3,
  LayoutDashboard,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api } from "../../services/api";
import AdminAiUsage from "./AdminAiUsage";
import "./admin-ai-usage.css";

const labels = {
  delayed: "지연",
  review: "일정 재수립 필요",
  soon: "종료 임박",
  unscheduled: "일정 미확정",
  on_track: "일정 준수",
  complete: "완료",
};
export default function AdminDashboard({ onOpen }) {
  const [tab, setTab] = useState("handovers");
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("all"),
    [query, setQuery] = useState("");
  async function load() {
    setLoading(true);
    setError("");
    try {
      setData(await api("/admin/dashboard"));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  const rows = (data?.handovers || []).filter(
    (row) =>
      (filter === "all" || row.status === filter) &&
      [row.name, row.owner, ...row.successors]
        .join(" ")
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const metrics = [
    ["all", "전체 인수인계", data?.handovers.length || 0],
    ["delayed", "일정 지연", data?.counts.delayed || 0],
    ["soon", "3일 이내 종료", data?.counts.soon || 0],
    ["complete", "인수 완료", data?.counts.complete || 0],
  ];
  return (
    <section className="admin-dashboard">
      <header className="admin-heading">
        <div>
          <div className="admin-eyebrow">
            <ShieldCheck size={16} /> 관리자
          </div>
          <h1>{tab === "usage" ? "AI 사용량" : "인수인계 운영 현황"}</h1>
          <p>
            {tab === "usage"
              ? "각 기능의 API 호출에서 실제로 사용한 토큰을 확인하세요."
              : "일정이 늦어지는 인수인계와 확인이 필요한 현황을 살펴보세요."}
          </p>
        </div>
        {tab === "handovers" && (
          <button onClick={load} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> 새로고침
          </button>
        )}
      </header>
      <div className="admin-section-tabs" aria-label="관리자 화면 선택">
        <button
          type="button"
          aria-pressed={tab === "handovers"}
          onClick={() => setTab("handovers")}
        >
          <LayoutDashboard size={17} /> 인수인계 현황
        </button>
        <button
          type="button"
          aria-pressed={tab === "usage"}
          onClick={() => setTab("usage")}
        >
          <BarChart3 size={17} /> AI 사용량
        </button>
      </div>
      <div hidden={tab !== "handovers"}>
        {error && (
          <div className="alert error" role="alert">
            {error}
          </div>
        )}
        {loading && !data ? (
          <p role="status">전체 현황을 불러오고 있어요.</p>
        ) : (
          data && (
            <>
              <div className="admin-metrics">
                {metrics.map(([key, title, count]) => (
                  <button
                    key={key}
                    className={`admin-metric ${key}`}
                    aria-pressed={filter === key}
                    onClick={() => setFilter(key)}
                  >
                    <span>{title}</span>
                    <strong>
                      {count}
                      <small>건</small>
                    </strong>
                    <span className="admin-metric-link">목록 보기 →</span>
                  </button>
                ))}
              </div>
              <div className="admin-table-panel">
                <div className="admin-toolbar">
                  <h2>
                    전체 진행 현황 <span>{rows.length}건</span>
                  </h2>
                  <div className="admin-filters">
                    <label className="admin-search">
                      <Search size={16} />
                      <input
                        aria-label="인수인계 또는 담당자 검색"
                        placeholder="인수인계·담당자 검색"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </label>
                    <select
                      aria-label="진행 상태 필터"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="all">모든 상태</option>
                      {Object.entries(labels).map(([key, label]) => (
                        <option value={key} key={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="admin-table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>인수인계 / 담당자</th>
                        <th>기간</th>
                        <th>인수 진행률</th>
                        <th>기한 경과 미완료</th>
                        <th>일정 상태</th>
                        <th>
                          <span className="sr-only">인수인계 열기</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.id}>
                          <td>
                            <strong>{row.name}</strong>
                            <small>
                              {row.owner || "미지정"} →{" "}
                              {row.successors.filter(Boolean).join(", ") ||
                                "미지정"}
                            </small>
                          </td>
                          <td className="admin-period">
                            {row.start_date || "미입력"}
                            <br />~ {row.end_date || "미입력"}
                            <small>
                              {row.status === "complete"
                                ? "인수 완료"
                                : row.days_remaining === null
                                  ? "기간 미설정"
                                  : row.days_remaining < 0
                                    ? `종료일 ${-row.days_remaining}일 경과`
                                    : row.days_remaining === 0
                                      ? "오늘 종료"
                                      : `${row.days_remaining}일 남음`}
                            </small>
                          </td>
                          <td>
                            <div className="admin-progress-label">
                              <span>{row.percent}%</span>
                              <small>
                                {row.done}/{row.total}개
                              </small>
                            </div>
                            <progress
                              value={row.done}
                              max={row.total || 1}
                              aria-label={`${row.name} 인수 진행률`}
                            />
                          </td>
                          <td>
                            <span
                              className={row.overdue ? "admin-overdue" : ""}
                            >
                              {row.overdue === null
                                ? `판단 보류 (${row.status === "review" ? "일정 재수립 필요" : "세부 일정 미확정"})`
                                : `${row.overdue}개`}
                            </span>
                            {row.due_count > 0 && (
                              <small>
                                기한 지난 {row.due_count}개 중 {row.due_done}개
                                완료
                              </small>
                            )}
                          </td>
                          <td>
                            <span className={`admin-status ${row.status}`}>
                              {labels[row.status]}
                            </span>
                            <small>{row.reason}</small>
                          </td>
                          <td>
                            <button
                              onClick={() => onOpen(row.id)}
                              aria-label={`${row.name} 인수인계 보기`}
                            >
                              인수인계 보기
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!rows.length && (
                  <p className="admin-empty">
                    {data.handovers.length
                      ? "조건에 맞는 인수인계가 없습니다."
                      : "등록된 인수인계가 없습니다."}
                  </p>
                )}
                <div className="admin-footnote">
                  {data.as_of} 한국 시간 기준 · 지연은 확정 일정의 종료일이 지난
                  미완료 업무를 기준으로 판단합니다. 일정 미확정·재수립 대상은
                  업무별 지연 판단을 보류합니다. 진행률은 인수자들이 공유하는
                  완료 상태입니다.
                </div>
              </div>
            </>
          )
        )}
      </div>
      {tab === "usage" && <AdminAiUsage />}
    </section>
  );
}
