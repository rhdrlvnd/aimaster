import React from "react";
import { Check, LoaderCircle, X } from "lucide-react";
const statusLabels = {
  complete: "완료",
  active: "진행 중",
  failed: "실패",
  skipped: "미진행",
  waiting: "대기",
};
export default function ProgressStep({
  label,
  status = "waiting",
  detail,
  iconSize = 16,
}) {
  return (
    <li className={status}>
      <>
        {status === "failed" ? (
          <X size={iconSize} />
        ) : status === "complete" ? (
          <Check size={iconSize} />
        ) : status === "active" ? (
          <LoaderCircle className="spin" size={iconSize} />
        ) : (
          <span className="waiting-dot" />
        )}
      </>
      <span>{label}</span>
      <small>{statusLabels[status]}</small>
      {detail && <div className="stage-outcome">{detail}</div>}
    </li>
  );
}
