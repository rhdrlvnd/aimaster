import React from "react";
import ChecklistItem from "../checklist/ChecklistItem";

export default function RecipientView({ state, tab, setSelected }) {
  if (!state.permissions.can_view_content) {
    return (
      <section className="empty">
        <h2>인계자가 내용을 준비하고 있어요</h2>
        <p>
          체크리스트가 확정되면 업무 문서와 인수인계 내용을 확인할 수 있습니다.
        </p>
      </section>
    );
  }
  if (tab === "documents") {
    return (
      <section className="document-panel">
        <h2>업무 문서 · {state.documents.length}개</h2>
        <p className="subtext">
          인계자가 등록한 문서를 조회할 수 있습니다. 등록·수정·삭제는 인계자가
          담당합니다.
        </p>
        <div className="doc-list">
          {state.documents.map((doc) => (
            <button
              className="doc-open"
              key={doc.id}
              onClick={() => setSelected({ document_id: doc.id })}
            >
              {doc.name} · 내용 보기
            </button>
          ))}
        </div>
      </section>
    );
  }
  return (
    <section className="review-panel">
      <div className="review-heading">
        <div>
          <h2>확정된 인수인계 체크리스트</h2>
          <p>
            인계자의 검토가 완료된 내용입니다. 항목별 원문 근거를 확인할 수
            있습니다.
          </p>
        </div>
      </div>
      <div className="items">
        {state.items.map((item, index) => (
          <ChecklistItem
            key={item.id}
            item={item}
            items={state.items}
            number={index + 1}
            locked
            readOnly
            setSelected={setSelected}
          />
        ))}
      </div>
    </section>
  );
}
