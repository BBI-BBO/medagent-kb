# 의료 agent 지식 DB 뷰어

N.O.V.A. 2026 의료 agent 팀의 진단 지식 DB를 살펴보는 화면입니다.

**https://bbi-bbo.github.io/medagent-kb/**

- **관계 그래프**: KCD 병명·소견·기전·검사를 가운데 두고 원인 → 결과 방향으로 잇습니다.
- **진료**: 넣은 소견을 함께 가진 질병을 보여 줍니다 (확률이 아니라 공통점).
- **구조 · 테이블**: DB 표 구조(ERD)와 행을 봅니다.

## 자료와 이용 조건

KCD(HIRA 상병마스터), 성균관의대 LRC PBL 주호소 스키마(팀 자체 수집), HPO, MONDO, Orphadata, DisMech, LOINC·LOINC2HPO, Gene Ontology를 묶었습니다.
각 출처와 이용 조건은 화면 오른쪽 위 **DB 정보**에 있습니다.

- 이 공개판에는 **HPOA(phenotype.hpoa)에서만 온 연결을 넣지 않았습니다** (이용 조건).
- **AI(Claude)** 표시가 붙은 기전·연결은 AI가 쓰고 다른 AI가 따로 검토한 것으로, **의학과 검수 전**입니다.
- 글꼴: Pretendard, IBM Plex Mono (SIL Open Font License 1.1).

## 올리는 법

화면과 자료는 연구 폴더(`viz/db_viewer`)에서 만들고, `tools/build_public_viewer.py`가 HPOA를 걸러 공개판을 만든 뒤
`gh-pages` 가지에 올립니다 (자료가 커서 가지에는 마지막 판 하나만 둡니다).
