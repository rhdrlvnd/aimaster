export const PRIORITIES = [
  {
    label: "긴급",
    tone: "high",
    description: "인수인계 기간 초반에 반드시 파악해야 할 항목",
    example: "장애 대응·서비스 가용성 직결",
  },
  {
    label: "보통",
    tone: "medium",
    description: "기간 절반 이내 파악하면 되는 항목",
    example: "정기 운영·배포 등 주기적 업무",
  },
  {
    label: "여유",
    tone: "low",
    description: "기간 내 여유롭게 파악해도 되는 항목",
    example: "참고·히스토리·문서화",
  },
];

export function priorityInfo(value) {
  const label = { 높음: "긴급", 낮음: "여유" }[value] || value;
  return (
    PRIORITIES.find((priority) => priority.label === label) || PRIORITIES[1]
  );
}
