import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Plus,
  ArrowRight,
  Pencil,
  LoaderCircle,
  X,
  LockKeyhole,
} from "lucide-react";
import { api } from "../../services/api";
const blank = {
  name: "",
  scope: "",
  owner: "",
  successor: "",
  start_date: "",
  end_date: "",
};
const statuses = {
  empty: "문서 등록 전",
  ready: "문서 등록됨",
  review: "체크리스트 검토 중",
  approved: "체크리스트 확정",
  stale: "문서 변경됨",
};
export default function HandoverHome({ onOpen }) {
  const [users, setUsers] = useState([]);
  const [user, setUser] = useState(null);
  const [switching, setSwitching] = useState(false);
  const [list, setList] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [form, setForm] = useState(null),
    [editing, setEditing] = useState(null),
    [saving, setSaving] = useState(false);
  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api("/handovers");
      setList(data.handovers);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    async function init() {
      try {
        const data = await api("/demo/users");
        setUsers(data.users);
        try {
          const session = await api("/session");
          setUser(session.user);
          await load();
        } catch {
          setLoading(false);
        }
      } catch (e) {
        setError(e.message);
        setLoading(false);
      }
    }
    init();
  }, []);
  async function switchUser(id) {
    if (!id) return;
    setSwitching(true);
    setList([]);
    try {
      const data = await api("/demo/session", "POST", { user_id: id });
      setUser(data.user);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSwitching(false);
    }
  }
  function start(item) {
    setError("");
    setEditing(item || null);
    setForm(
      item
        ? Object.fromEntries(Object.keys(blank).map((k) => [k, item[k] || ""]))
        : { ...blank, owner: user.name },
    );
  }
  function close() {
    if (saving) return;
    const original = editing || blank;
    if (
      Object.keys(blank).some((k) => form[k] !== (original[k] || "")) &&
      !window.confirm("입력한 내용을 버리고 닫을까요?")
    )
      return;
    setForm(null);
  }
  async function submit(e) {
    e.preventDefault();
    setError("");
    if (form.end_date < form.start_date) {
      setError("종료일은 시작일보다 빠를 수 없습니다.");
      return;
    }
    setSaving(true);
    try {
      const result = await api(
        editing ? "/handovers/" + editing.id : "/handovers",
        editing ? "PUT" : "POST",
        editing ? { ...form, revision: editing.revision } : form,
      );
      setForm(null);
      if (editing) await load();
      else onOpen(result.id, user);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="handover-home">
      <div className="handover-brand">
        <BookOpen size={25} />
        업무 인수인계
      </div>
      <div className="demo-user-bar">
        <label>
          테스트 사용자
          <select
            aria-label="테스트 사용자"
            value={user?.id || ""}
            disabled={switching}
            onChange={(e) => switchUser(e.target.value)}
          >
            <option value="" disabled>
              사용자를 선택하세요
            </option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} · {u.department}
              </option>
            ))}
          </select>
        </label>
        <span>
          전체 목록은 공개되며, 내용은 인계자·인수자만 열 수 있습니다.
        </span>
      </div>
      <header className="handover-home-heading">
        <div>
          <h1>인수인계 목록</h1>
          <p>
            담당 업무별로 인수인계를 시작하고, 문서와 체크리스트를 관리하세요.
          </p>
        </div>
        <button
          className="primary"
          disabled={!user || switching}
          onClick={() => start()}
        >
          <Plus size={18} />
          인수인계 시작
        </button>
      </header>
      {error && !form && (
        <div className="alert error" role="alert">
          {error}
          <button onClick={load}>다시 불러오기</button>
        </div>
      )}
      {!user ? (
        <section className="empty">
          <h2>테스트 사용자를 선택해 주세요</h2>
          <p>
            사용자를 바꾸면 참여 여부에 따라 접근 가능한 인수인계가 달라집니다.
          </p>
        </section>
      ) : loading ? (
        <div className="empty">
          <LoaderCircle className="spin" />
          목록을 불러오는 중입니다.
        </div>
      ) : !error && !list.length ? (
        <section className="empty handover-empty">
          <BookOpen size={38} />
          <h2>첫 인수인계를 시작해 보세요</h2>
          <p>
            담당 업무와 전임자·후임자, 기간을 입력한 뒤 업무 문서를 등록할 수
            있어요.
          </p>
          <button
            className="primary"
            disabled={!user || switching}
            onClick={() => start()}
          >
            인수인계 시작
          </button>
        </section>
      ) : (
        <div className="handover-grid">
          {list.map((item) => (
            <article key={item.id} className="handover-entry">
              <div className="handover-entry-top">
                <span className="status">
                  {statuses[item.status] || item.status}
                </span>
                {item.can_manage && (
                  <button
                    className="text-button"
                    onClick={() => start(item)}
                    aria-label={item.name + " 기본 정보 수정"}
                  >
                    <Pencil size={14} />
                    기본 정보 수정
                  </button>
                )}
              </div>
              <h2>{item.name}</h2>
              <p>
                {!item.can_access
                  ? "참여자만 상세 내용을 확인할 수 있습니다."
                  : item.scope ||
                    "기존 자료를 보존한 인수인계입니다. 기본 정보를 입력해 주세요."}
              </p>
              <dl>
                <div>
                  <dt>전임자 → 후임자</dt>
                  <dd>
                    {item.owner || "미입력"} → {item.successor || "미입력"}
                  </dd>
                </div>
                <div>
                  <dt>기간</dt>
                  <dd>
                    {item.start_date || "미입력"} ~ {item.end_date || "미입력"}
                  </dd>
                </div>
              </dl>
              <div className="handover-entry-bottom">
                <span>
                  {item.can_access
                    ? `문서 ${item.document_count}개 · 체크리스트 ${item.item_count}개`
                    : "접근 제한"}
                </span>
                <button
                  disabled={!item.can_access}
                  onClick={() => onOpen(item.id, user)}
                  aria-label={item.name + " 열기"}
                >
                  {item.can_access ? (
                    <>
                      열기
                      <ArrowRight size={16} />
                    </>
                  ) : (
                    <>
                      참여자 전용
                      <LockKeyhole size={16} />
                    </>
                  )}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {form && (
        <div className="drawer-backdrop">
          <section
            className="handover-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="handover-form-title"
          >
            <div className="drawer-title">
              <h2 id="handover-form-title">
                {editing ? "인수인계 기본 정보 수정" : "인수인계 시작"}
              </h2>
              <button
                aria-label="생성 창 닫기"
                disabled={saving}
                onClick={close}
              >
                <X size={18} />
              </button>
            </div>
            <p>
              모든 항목을 입력해 주세요. 생성 후에도 기본 정보를 수정할 수
              있어요.
            </p>
            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}
            <form onSubmit={submit}>
              <label>
                인수인계 제목
                <input
                  autoFocus
                  required
                  maxLength={100}
                  value={form.name}
                  disabled={saving}
                  placeholder="예: 인사운영 업무 인수인계"
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>
              <label>
                담당 업무
                <textarea
                  required
                  maxLength={1000}
                  value={form.scope}
                  disabled={saving}
                  placeholder="예: 입퇴사 처리, 근태 마감, 급여 자료 작성"
                  onChange={(e) => setForm({ ...form, scope: e.target.value })}
                />
              </label>
              <div className="handover-form-row">
                {[
                  ["owner", "전임자"],
                  ["successor", "후임자"],
                ].map(([key, title]) => (
                  <label key={key}>
                    {title}
                    <select
                      required
                      value={form[key]}
                      disabled={saving || key === "owner"}
                      onChange={(e) =>
                        setForm({ ...form, [key]: e.target.value })
                      }
                    >
                      <option value="">사용자 선택</option>
                      {users.map((u) => (
                        <option key={u.id} value={u.name}>
                          {u.name} · {u.department}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <div className="handover-form-row">
                {[
                  ["start_date", "시작일"],
                  ["end_date", "종료일"],
                ].map(([key, title]) => (
                  <label key={key}>
                    {title}
                    <input
                      required
                      type="date"
                      min={key === "end_date" ? form.start_date : undefined}
                      value={form[key]}
                      disabled={saving}
                      onChange={(e) =>
                        setForm({ ...form, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
              </div>
              <div className="handover-form-actions">
                <button type="button" onClick={close} disabled={saving}>
                  취소
                </button>
                <button className="primary" type="submit" disabled={saving}>
                  {saving ? <LoaderCircle className="spin" size={16} /> : null}
                  {editing ? "기본 정보 저장" : "생성하고 문서 등록"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
