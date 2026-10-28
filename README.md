# AI Master — 업무 인수인계 Agent

기존 업무 문서로 체크리스트 초안을 만들고 인계자가 검토·확정합니다. 확정 체크리스트의 선행 관계와 중요도를 반영해 일정을 구성하고, 인수자는 달력·진행 현황·문서 근거 채팅을 활용합니다. 인계자 추가 답변, Google Calendar 등록, 성명·동의 기록과 Word 출력도 연결합니다.

## 로컬 실행

1. Python·Node.js를 준비하고 `python -m pip install -r requirements.txt`, `npm install`을 실행합니다.
2. `.env.example`을 `.env.local`로 복사하고 사용할 API 설정을 입력합니다. 실제 키는 Git에 넣지 않습니다.
3. `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`으로 API를 실행합니다.
4. 별도 터미널에서 `npm run dev -- --port 5185 --strictPort`를 실행합니다.
5. [로컬 화면](http://127.0.0.1:5185)을 열고 테스트 사용자를 선택합니다.

기본 생성 모델은 `gpt-6.1-sol`, 임베딩은 `text-embedding-3-large`입니다. 업무 데이터·문서·벡터는 `data/` 아래 저장합니다. PPT 이미지 변환은 PowerPoint가 설치된 Windows에서 지원합니다. 다른 운영체제나 PowerPoint가 없는 환경에서는 해당 변환을 사용할 수 없습니다.

새 인수인계는 생성한 사용자가 인계자가 되며 제목·담당 업무·기간·인수자를 지정합니다. 전체 목록의 기본 정보를 볼 수 있지만 지정된 참여자만 상세 자료에 접근합니다. 작업 공간 진입 시 인수인계 현황을 먼저 보여줍니다. 사용자 선택 방식은 개발용이며 운영 인증을 대체하지 않습니다.

## 기본 사용 순서

1. 인계자로 업무 문서에서 파일을 등록하고 문서별 분석 결과를 확인합니다. 개별 또는 전체 재분석을 지원합니다.
2. 체크리스트를 생성하고 내용·근거·선행 업무를 검토해 저장·확정합니다.
3. 인수인계 기간·주말·휴일을 설정하고 AI 일정 초안을 생성합니다. 월간 달력에서 드래그하거나 날짜를 선택해 조정한 뒤 확정합니다.
4. 인수자로 확정 일정과 자료를 확인하고 수행 상태를 기록합니다. 질문은 AI 채팅에서 하며 필요한 경우 인계자에게 추가 확인을 요청합니다.
5. 인계자는 질문 목록에서 답변하고 확정 내용에 성명·동의를 기록해 DOCX로 출력합니다.

체크리스트에는 모든 문서의 저장된 텍스트·표·PPT 전체 정리 내용을 사용하며 PPT 이미지를 다시 보내지 않습니다. 생성 실패 시 기존 결과를 유지합니다. 체크리스트 재생성 성공 시 이전 일정·수행 상태·서명이 초기화됩니다. 일정 재조정은 완료 업무를 유지한 새 초안을 만들고 다시 확정합니다.

## Google Calendar

`.env.example`의 OAuth 설정을 `.env.local`에 입력하고 서버를 재시작합니다. Google Cloud에서 Calendar API를 활성화하고 웹 OAuth 클라이언트의 리디렉션 URI를 `GOOGLE_REDIRECT_URI`와 맞춥니다. 기본 개발 주소는 `http://127.0.0.1:5185/api/calendar/callback`입니다. 테스트 모드에서는 연결 계정을 테스트 사용자에 등록해야 합니다.

OAuth 클라이언트 설정은 서비스 공통이고 인수자는 자신의 Google 계정으로 동의합니다. 일정 화면의 연결 기능을 이용한 뒤 확정 일정 전체 또는 일부를 등록합니다. 같은 항목을 다시 등록하면 이벤트를 갱신합니다. 토큰은 서버 메모리에 있으므로 재시작 후 다시 연결해야 합니다. 실제 계정 등록·갱신 검증 상태와 이전 이벤트 정리 제한은 [구현 기록](docs/IMPLEMENTATION.md)을 확인하세요.

## 문서

- [프로젝트 기획](docs/PROJECT_PLAN.md)
- [Task 1 — 역량·기술 스택](docs/TASK_01_SUBMISSION.md)
- [Task 2 — 문제 정의·서비스 기획](docs/TASK_02_SUBMISSION.md)
- [Task 3 — 사용자 시나리오](docs/TASK_03_SUBMISSION.md)
- [Task 4 — 멀티 에이전트 상세 설계](docs/TASK_04_SUBMISSION.md)
- [구현 상태·검증·남은 확인 사항](docs/IMPLEMENTATION.md)
- [KPI 후보·선택 이력](docs/KPI_CANDIDATES.md)

Task 문서는 사전 설계의 문체로 작성합니다. KPI 목표·예상 기준선과 실제 테스트 결과를 구분합니다.

## 코드 구조와 점검

- `backend/app.py`: API·권한·문서·체크리스트 처리
- `backend/checklist_generation.py`, `backend/dependencies.py`: 생성·검토 및 선행 관계 검증
- `backend/agents.py`: 역할별 AI 실행 지원
- `backend/rag.py`, `backend/knowledge.py`: 문서 분석·검색·답변
- `backend/scheduling.py`, `backend/features.py`, `backend/calendar_api.py`: 일정·진행·질문·출력·외부 연동
- `src/App.jsx`, `src/hooks/useWorkspace.js`: 메뉴·작업 공간 상태·진행 유지
- `src/components/documents/`, `checklist/`, `features/`, `common/`: 화면과 재사용 컴포넌트

문서 분석·체크리스트 작성·내용 검토·선행 업무 검토·일정 계획·업무 Q&A의 6개 역할을 LangGraph와 서버 처리 흐름으로 연결합니다.

프런트엔드는 `npm run format:check`, `npm test`, `npm run build`로 점검합니다. 생성·관계 관련 테스트는 `python -m unittest backend.test_checklist_generation backend.test_dependencies backend.test_workflow backend.test_ai_transport`로 실행합니다. `tools/check_*` 중에는 과거 화면이나 로컬 데이터에 의존하는 도구가 있으므로 새 설치에서 전부 그대로 실행하지 말고 각 도구의 대상·포트·데이터 조건을 확인하세요.

## Git 제외 자료와 다른 PC로 전달

`.env.local`, `data/`, `outputs/`, `ppt/`, 로그·임시 산출물은 Git에 포함하지 않습니다. `.env.example`에는 실제 비밀값을 넣지 않습니다.

새 데이터로 시작하려면 저장소와 실행 환경·별도 API 설정이 필요합니다. 기존 작업 상태까지 전달하려면 서버를 종료해 쓰기를 멈춘 뒤 `data/` 전체를 복사합니다. DB만 보내면 문서·벡터·이미지 자료가 빠질 수 있습니다. 설정 파일은 필요한 상대에게 별도 안전한 경로로 전달하며 Google 개인 연결은 새 서버에서 다시 진행합니다. `node_modules`와 Python 가상환경은 대상 PC에서 설치합니다.
