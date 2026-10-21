# AI Master — 업무 인수인계 Agent

## 로컬 실행

인수인계 생성·문서 분석·체크리스트 검토부터 AI 일정 작성, 인수 진행 관리, 문서 기반 질문, 인계자 답변, 캘린더 연동, 서명·Word 출력까지 연결합니다. [구현 상태와 실행 방법](docs/IMPLEMENTATION.md)을 확인하세요.

1. `python -m pip install -r requirements.txt`
2. `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`
3. 별도 터미널에서 `npm install` 후 `npm run dev`
4. 이 작업 환경에서는 `npm run dev -- --port 5185 --strictPort`로 실행하고 http://127.0.0.1:5185 열기

`.env.example`을 `.env.local`로 복사하고 발급받은 키를 입력합니다. `.env.local`의 사내 LLM 설정을 사용합니다. 먼저 직접 만든 예시 문서로 확인하세요. 생성 모델은 `gpt-6.1-sol`, 임베딩은 `text-embedding-3-large`가 기본값입니다. 벡터는 `data/chroma`에 로컬 저장합니다. 기존 문서는 업무 문서 탭의 ‘AI 문서 분석’으로 검색 자료를 생성하세요. 실패한 분석은 문서를 다시 올리지 않고 재시도할 수 있습니다.

Google Calendar는 `.env.example`의 OAuth 설정 3개를 `.env.local`에 입력한 뒤 서버를 재시작합니다. Google Cloud에서 Calendar API를 활성화하고 웹 OAuth 클라이언트의 승인된 리디렉션 URI를 `GOOGLE_REDIRECT_URI`와 일치시켜야 합니다. 인수자가 화면에서 Google 연결에 동의한 뒤 선택한 일정을 등록합니다. 연결 토큰은 서버 메모리에만 두므로 서버 재시작 후 다시 연결합니다. 실제 Google 등록 검증은 설정 제공 후 진행합니다.

문서 분석·체크리스트 작성·체크리스트 검토·일정 계획·업무 Q&A의 5개 역할을 LangGraph로 실행합니다. `backend/agents.py`, `backend/scheduling.py`, `backend/knowledge.py`, `backend/features.py`와 `src/components/features/`에 역할 및 화면을 분리했습니다. 로그인은 기존 테스트 사용자 전환 방식이며 운영용 계정 인증은 별도 연동이 필요합니다.

## 기획 문서

2026년 10월 7일 부문 과제 배정에 따라 새로 시작합니다. 기존 과제의 기획·설계·평가·예시 자료는 삭제했습니다.

전달받은 기본 기획의 슬라이드 이미지 13장을 확인했습니다. 원본은 로컬 ppt 폴더에서 관리하며 Git에는 포함하지 않습니다. 자료의 내용과 이번 구현에서 결정할 사항을 구분해 정리했습니다. 구현 범위·기술·평가 목표는 협의 후 확정합니다.

- [새 프로젝트 기획서](docs/PROJECT_PLAN.md)
- [Task 1 — 역량 및 기술 스택 확인](docs/TASK_01_SUBMISSION.md)
- [Task 2 — 문제 정의 및 서비스 기획](docs/TASK_02_SUBMISSION.md)
- [Task 3 — 시나리오 수립](docs/TASK_03_SUBMISSION.md)

Task 입력 항목과 확인된 개인 개발 경험은 유지합니다. 이전 과제의 기술 선택·기능·제외 범위·KPI는 새 과제에 자동 적용하지 않습니다.

## 프런트엔드 코드 구조

- `src/main.jsx`: React 실행 진입점
- `src/App.jsx`: 화면 구성과 메뉴 연결
- `src/components/documents/`: 문서 등록, 분석 진행·결과, 원문 보기
- `src/components/checklist/`: 체크리스트 화면과 재사용 가능한 업무 항목
- `src/components/layout/`: 사이드바와 인수인계 현황
- `src/components/common/`: 문서 분석·초안 생성이 공유하는 진행 단계 표시
- `src/hooks/useWorkspace.js`: 작업 공간 상태와 업로드·분석·저장·삭제 동작. 메뉴 이동 중에도 작업 상태를 유지합니다.
- `src/hooks/useElapsedTime.js`: 작업 경과 시간
- `src/services/api.js`: JSON API와 공통 스트리밍 응답 처리
- `src/documentProgress.js`: 분석 이벤트 누적 및 저장된 문서의 단계별 결과 변환

작업 화면 컴포넌트는 props로 데이터와 동작을 받습니다. 인수인계 목록·생성 화면은 목록 API를 호출하고, 선택된 작업 공간의 요청은 해당 인수인계 ID로 구분합니다. 새 화면은 기존 분석·원문 보기·업무 항목 컴포넌트를 가져와 구성할 수 있습니다.

`npm run format`으로 코드 형식을 정리하고, `npm run format:check`, `npm test`, `npm run build`로 점검합니다. 브라우저 회귀 검증은 `tools/check_refactored_workflow.cjs`, `tools/check_analysis_results.cjs`, `tools/check_progress_by_file.cjs`, `tools/check_bulk_delete.cjs`를 사용합니다. 해당 스크립트는 로컬 5185 포트와 테스트용 API 응답을 사용하며 실제 업무 데이터를 변경하지 않습니다.

## 인수인계별 관리

첫 화면에서 인수인계 제목, 담당 업무, 전임자, 후임자, 시작일·종료일을 입력해 생성합니다. 목록에서 기본 정보를 수정하거나 해당 인수인계를 열 수 있습니다. 문서·체크리스트·근거는 인수인계별로 분리되며, 기존 자료는 기존 업무 인수인계로 한 번만 이전됩니다. 이전 전 SQLite 백업과 원래 workspace 행을 보존합니다.

새 흐름 검증: python -m unittest tools.test_handovers backend.test_workflow backend.test_slides backend.test_rag -v 및 node tools/check_handovers.cjs. 기존 tools/check_* 스크립트 중 단일 작업 공간을 가정한 스크립트는 이전 UI 전용입니다.

## Git에 포함하지 않는 자료

API 키와 OAuth 비밀값은 `.env.local`에만 보관합니다. 업로드 문서·DB·벡터 저장소(`data/`), 생성 산출물(`outputs/`), 전달받은 기획 원본(`ppt/`), 로그·임시 파일은 `.gitignore`로 제외합니다. 실행 설정 예시인 `.env.example`에는 실제 키를 넣지 않습니다.
