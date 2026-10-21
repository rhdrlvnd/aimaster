import React from "react";
import { ArrowUpRight } from "lucide-react";

export default function Overview({ docs, items, reviewed, setTab, handover }) {
  return (
    <section className="overview">
      {handover && (
        <div className="handover-info">
          <h2>{handover.name}</h2>
          <p>
            {handover.scope ||
              "목록에서 담당 업무와 기본 정보를 입력해 주세요."}
          </p>
          <span>
            전임자 {handover.owner || "미입력"} · 후임자{" "}
            {handover.successor || "미입력"} ·{" "}
            {handover.start_date || "시작일 미입력"} ~{" "}
            {handover.end_date || "종료일 미입력"}
          </span>
        </div>
      )}
      <div className="metric">
        <span>등록한 업무 문서</span>
        <strong>
          {docs.length}
          <small>개</small>
        </strong>
      </div>
      <div className="metric">
        <span>인수인계 항목</span>
        <strong>
          {items.length}
          <small>개</small>
        </strong>
      </div>
      <div className="metric">
        <span>전임자 검토</span>
        <strong>
          {reviewed}
          <small> / {items.length}</small>
        </strong>
      </div>
      <section className="overview-callout">
        <h2>문서와 초안을 함께 보며 검토하세요.</h2>
        <p>
          이 수치는 전임자의 검토 상태입니다. 후임자의 업무 완료율은 다음
          단계에서 연결합니다.
        </p>
        <button className="primary" onClick={() => setTab("checklist")}>
          체크리스트 검토 <ArrowUpRight size={16} />
        </button>
      </section>
    </section>
  );
}
