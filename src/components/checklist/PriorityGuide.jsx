import React from "react";
import { PRIORITIES } from "../../services/priorities";

export default function PriorityGuide() {
  return (
    <aside className="priority-guide" aria-label="중요도 판단 기준">
      <strong>중요도 판단 기준</strong>
      <ul>
        {PRIORITIES.map(({ label, tone, description, example }) => (
          <li key={label}>
            <span className={`importance-badge ${tone}`}>{label}</span>
            <span>
              {description}{" "}
              <span className="priority-guide-example">({example})</span>
            </span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
