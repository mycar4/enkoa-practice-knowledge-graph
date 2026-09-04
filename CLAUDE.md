# 🏛️ DART-Trace 지배구조 지식그래프 시스템 가이드 (CLAUDE.md)
> 본 문서는 **Claude Code(CLI)**가 DART-Trace 저장소에서 코드 검수, 기능 보강, 리팩토링 및 릴리즈 승인을 수행할 때 반드시 준수해야 하는 **시스템 헌법(Strict Invariants)과 운영 표준**을 정의합니다.

---

## 1. 프로젝트 개요 및 핵심 아키텍처
* **목적**: 금융감독원 전자공시(DART) 원문(XML) 기반의 기업 자본이벤트(CB, BW, 증자) 및 5% 대량보유 지분 관계를 정직하고 무결하게 추출·검증·시각화하는 지식그래프(GraphRAG) 플랫폼.
* **주요 스택**: Python 3.11+, Streamlit, Neo4j Graph Database (Cloud Aura), `uv` 패키지 관리자.
* **작업 디렉토리**: 모든 프로덕션 코드, UI, 테스트는 `내작업폴더/` 하위에 위치하며, 기존 `day27~day35` 교육 실습 폴더는 절대 임의 이동하거나 삭제하지 않습니다 (점진적 계층 분리 원칙).

---

## 2. 🛡️ 시스템 6대 불변 계약 (Strict Invariants)

Claude Code는 검수 및 작업 시 아래 6대 불변 계약을 단 1건이라도 위반하는 코드에 대해 **즉시 거부(Reject)** 판정을 내려야 합니다.

### ① 지배력 단정 관계(`:OWNS_STAKE`) 절대 생성 금지
* DART 5% 대량보유 공시 원문에서 추출된 지분은 **'단순 경제적 지분 보유 사실'**일 뿐, 기업 간 지배력·경영권 통제를 의미하지 않습니다.
* 지배력을 단정하는 `:OWNS_STAKE` 관계는 DB 내에 **0건으로 완전 격리**되어야 하며, 오직 원문 해시가 결속된 `:HOLDS_ECONOMIC_STAKE` 관계만 허용됩니다.

### ② 메뉴 2 및 대시보드 UI/서비스 100% 읽기 전용 (Read-Only)
* `decision_report_service.py` 및 UI 컴포넌트는 반드시 `driver.session(default_access_mode=READ_ACCESS)`를 강제합니다.
* 서비스 및 UI 코드 내에 `WRITE_ACCESS`, `CREATE`, `MERGE`, `SET`, `DELETE` 실행 코드가 단 1줄이라도 포함되어서는 안 됩니다.

### ③ 단일 원자적 트랜잭션(Atomic Single Tx) & 롤백(Zero Pollution)
* 데이터 적재 시 `session.execute_write` 단일 트랜잭션 내에서 일괄 실행되어야 합니다.
* 필수 노드 결손이나 트랜잭션 내부 감사 실패 시 커밋 전 즉시 예외를 발생시켜 **단 1건의 쓰레기 데이터도 남기지 않고 100% 원자적으로 롤백**되어야 합니다.

### ④ 최초 적재 혈통(Lineage) 영구 불변 & 재실행 분리 기록
* 최초 승격 시의 실행 ID(`r.promotion_run_id`)와 승격 시각(`r.promoted_at`)은 `ON CREATE`에서만 기록하며, 이후 재실행 시 **절대 덮어쓰거나 변경할 수 없습니다.**
* 멱등 재실행(MERGE ON MATCH) 시에는 마지막 재검증 정보(`r.last_verified_run_id`, `r.last_verified_at`)만 별도로 1건 갱신합니다.

### ⑤ 화면(메뉴 2) 상의 사실과 후보 완전 분리 (Zero Mixing)
* **[검증·승격된 경제적 보유 사실]**: 봉인 매니페스트 SHA-256 결속 + 원문 행 해시 전수 감사 통과본 (초록색 전용 카드 및 독립 표 표출).
* **[5% 공시 원문 추출 후보]**: 엔티티 해소 전 1차 파싱 후보 (슬레이트색 독립 카드 및 `⚪ 미검증 후보` 표 표출).
* 두 데이터는 화면과 데이터 모델에서 **절대 혼합(Merge)하여 표출할 수 없습니다.**

### ⑥ 시간적 의미(Temporal Semantics) 왜곡 금지
* 추출된 지분과 자본이벤트는 **'2023년 공시 보고의무발생일 당시의 과거 공시 사실'**입니다.
* 이를 현재(2026년) 지분이나 최신 지배구조로 과도 해석·단정하는 텍스트나 로직을 작성해서는 안 됩니다.

---

## 3. 🧪 필수 테스트 및 검증 명령어

Claude Code는 검수 시 아래 명령어들을 실행하여 결함 유무를 확인합니다.

```powershell
# 1. 메뉴 2 4단 의사결정 리포트 계약 회귀 테스트 (HLB 0건 유지, 알루코 1건 승격 분리 확인)
uv run python 내작업폴더/tests/test_menu2_decision_report.py

# 2. 자동 하네스 계약 테스트 (운영 DB 무변경 안전 기본 모드: 5/5 전수 통과 확인)
uv run python 내작업폴더/tests/test_promotion_harness_contracts.py

# 3. 대상 노드 결손 시 100% 자동 롤백 실측 검증
uv run python 내작업폴더/tests/test_promotion_rollback_on_missing_node.py

# 4. [선택/명시적 필요 시] 운영 Aura 실시간 재실행 멱등성 및 혈통 불변 실측 통합 테스트
uv run python 내작업폴더/tests/test_promotion_harness_contracts.py --live-rerun

# 5. 로컬 Streamlit 대시보드 상태 확인
curl -I http://localhost:8501
```

---

## 4. 📂 Git 커밋 및 릴리즈 가이드
* **선별 커밋 원칙**: 작업과 직접 관련이 없는 임시 파일(scratch scripts), 캐시, 다른 실습 폴더(`day34`, `day35`)는 절대 `git add .`로 일괄 커밋하지 않고 대상 파일만 명시적으로 스테이징합니다.
* **원격 푸시 동기화**: 검수 승인 후 `main` 브랜치를 `origin/main`과 항상 일치시킵니다.
