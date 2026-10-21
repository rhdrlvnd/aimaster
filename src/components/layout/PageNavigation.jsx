import React from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { navigation } from "../../navigation";

const destinations = {
  overview: [null, "documents"],
  documents: [null, "checklist"],
  checklist: ["documents", "schedule"],
  schedule: ["checklist", "qa"],
  qa: ["schedule", null],
};

export default function PageNavigation({ tab, busy, onNavigate }) {
  const targets = destinations[tab] || [];
  return (
    <div
      className="page-navigation"
      role="group"
      aria-label="관련 화면으로 이동"
    >
      {targets.map((key, index) => {
        if (!key) return null;
        const label = navigation.find(([id]) => id === key)?.[2];
        return (
          <button
            key={key}
            type="button"
            disabled={!!busy}
            onClick={() => onNavigate(key)}
          >
            {index === 0 && <ArrowLeft size={15} />}
            {label}
            {["schedule", "qa"].includes(key) ? "으로" : "로"} 이동
            {index === 1 && <ArrowRight size={15} />}
          </button>
        );
      })}
    </div>
  );
}
