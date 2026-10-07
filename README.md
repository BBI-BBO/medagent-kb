# 의료 agent 지식 DB

N.O.V.A. 2026 의료 agent 팀의 진단 지식 DB 공개판입니다. 사람은 화면으로, 코드와 AI 에이전트는 `kb.py`나 원본 파일로 씁니다.

- 화면: **https://bbi-bbo.github.io/medagent-kb/**
- 지금 판: [`version.json`](https://bbi-bbo.github.io/medagent-kb/version.json) · 지난 판: [Releases](https://github.com/BBI-BBO/medagent-kb/releases)

| 절 | 누구에게 |
|---|---|
| [1. 빠른 시작 (파이썬)](#1-빠른-시작-파이썬) | 코드에서 쓰는 사람 |
| [2. AI 에이전트에 붙이기](#2-ai-에이전트에-붙이기) | Claude·GPT 도구 호출 |
| [3. 버전 관리](#3-버전-관리) | 실험·평가에 쓰는 사람 (꼭 읽기) |
| [4. 자료 구조](#4-자료-구조-다른-언어에서-직접-읽기) | 다른 언어에서 원본 파일을 직접 읽는 사람 |
| [5. 자료와 이용 조건](#5-자료와-이용-조건) | 모두 |

## 1. 빠른 시작 (파이썬)

`kb.py` 하나만 받으면 됩니다. 표준 라이브러리만 쓰고, 처음 한 번 자료(압축 전 약 40MB)를 받아 `~/.cache/medagent-kb/<판>/`에 둡니다.

```bash
curl -O https://raw.githubusercontent.com/BBI-BBO/medagent-kb/main/kb.py
python kb.py search 당뇨                          # 질병 찾기
python kb.py disease E14                          # 코드 정보·병명
python kb.py pheno E14@MONDO:0005015              # 병명의 표현형
python kb.py ddx HP:0002027 HP:0002013 -HP:0001945   # 있음 소견 / -없음 소견으로 후보
python kb.py versions                             # 올라온 판 목록
python kb.py disease E14 --version=kb-2026.10.07.1   # 판 고정
```

```python
from kb import KB
kb = KB(version="kb-2026.10.07.1")   # 판 고정 (권장). KB() 는 최신판
kb.search("윌슨", kind="disease")
kb.disease("E83.0")["names"]                      # [{'id': 'D|E830@MONDO:0010200', 'ko': '윌슨병', …}, …]
kb.phenotypes("E830@MONDO:0010200")[:5]           # 빈도 높은 순
kb.reach("E830@MONDO:0010200", direction=1)       # 질병 → 기전 사슬 → 소견
kb.rank_diseases(["HP:0000952", "HP:0001744"])    # 황달 + 비장비대를 함께 가진 병명
```

| 함수 | 하는 일 | 돌려주는 것 |
|---|---|---|
| `search(text, kind="disease", limit=20)` | 이름·코드로 찾기. kind: `disease` `finding` `mechanism` `test` | `[{id, name, en, …}]` — `id`를 다른 함수에 넘김 |
| `disease(code)` | KCD 코드(`E14`·`E83.0`)나 병명 키(`E830@MONDO:…`) | 이름·장·상위·하위 코드·포함 용어·**병명 목록**·주호소 스키마 |
| `phenotypes(name_key)` | 병명의 HPO 표현형 | `[{id, name, en, freq, freq_by_source, sources, diagnostic, from_subtype}]` |
| `edges(node, direction="out"/"in")` | 한 노드의 나가는(원인으로서)·들어오는(결과로서) 연결 | `[{from, relation, to, source, qualifier, …}]` |
| `reach(node, direction=1/-1)` | 화면 그래프와 같은 인과 트리 (1 = 결과 쪽, -1 = 원인 쪽) | `{root, nodes, edges}` |
| `findings_of(disease)` | 질병에서 기전을 거쳐 닿는 소견 (화면 목록의 '소견 N') | 노드 ID 집합 |
| `causes_of(finding)` | 소견을 일으킬 수 있는 질병·노출 (감별 후보) | `[{id, name, …}]` |
| `tests_for(finding)` | 소견을 판정하는 검사 (LOINC2HPO) | `[{from(검사), qualifier(결과 H·L·POS…), …}]` |
| `rank_diseases(present, absent=())` | '있음' 소견을 많이 함께 가진 병명 순, '없음'과 어긋나는 수 | `[{id, name, matched, conflicts, …}]` — **확률이 아니라 공통점** |
| `table(name)` · `tables()` | DB 표를 dict 로 | 큰 표는 미리보기 300행만 (`total`이 실제 행 수) |
| `node(id)` | 노드 이름·영어·종류 | `{id, name, en, kind}` |

## 2. AI 에이전트에 붙이기

`KB.TOOLS`는 함수 6개(search·disease·phenotypes·reach·rank_diseases·tests_for)의 JSON 스키마이고, `kb.call(name, args)`가 실행합니다.

```python
import anthropic, json
from kb import KB
kb, client = KB(version="kb-2026.10.07.1"), anthropic.Anthropic()
msgs = [{"role": "user", "content": "황달과 복수가 있는 33세 여성. 감별할 병명과 확인할 검사를 지식 DB로 찾아 줘."}]
while True:
    r = client.messages.create(model="claude-sonnet-5-5", max_tokens=2000, tools=KB.TOOLS, messages=msgs)
    msgs.append({"role": "assistant", "content": r.content})
    calls = [b for b in r.content if b.type == "tool_use"]
    if not calls:
        break
    msgs.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c.id,
                 "content": json.dumps(kb.call(c.name, c.input), ensure_ascii=False)[:20000]} for c in calls]})
print(r.content[-1].text)
```

OpenAI 호환 API 는 `{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}`로 바꿔 넘기면 됩니다.

에이전트에게 함께 알려 줄 것:
- 노드 ID는 `종류|값`입니다 (4절). `search`로 찾은 `id`를 그대로 넘기게 하세요.
- `rank_diseases`는 겹치는 소견 수일 뿐 진단 확률이 아닙니다.
- `ai_or_auto`가 붙은 연결(AI 기전 초안·유전자 자동 연결)과 `name_src: "AI 번역"` · `method: "ai_place"`인 병명은 **의학과 검수 전**입니다.

## 3. 버전 관리

그래프는 계속 고쳐집니다 (병명 자리·번역·기전 채우기·출처 갱신). 그래서 판마다 이름을 붙이고, 지난 판도 그대로 보관합니다.

- **판 이름**: `kb-YYYY.MM.DD.N` (그날 N번째 판). 화면 'DB 정보'와 `version.json`에 나옵니다. 자료가 바뀔 때만 새 판을 만들고, 화면만 고친 배포는 판 이름이 그대로입니다 (`version.json`의 `data_sha256`이 자료 지문).
- **최신판**: `https://bbi-bbo.github.io/medagent-kb/` — 배포하면 바로 바뀝니다. `KB()`.
- **고정 판**: `https://github.com/BBI-BBO/medagent-kb/releases/download/<판>/data.js` 처럼 Release 자산으로 보관하고 **바꾸지 않습니다**. `KB(version="<판>")`.
- **실험·평가·대회 제출에는 판을 고정하세요.** 같은 질문에 같은 답이 나와야 결과를 비교할 수 있습니다. 결과를 기록할 때 `kb.version`을 함께 남기세요.
- **자료 구조 판 `format`**: 파일·키·열 구조가 바뀌어 기존 코드가 깨질 수 있으면 올립니다 (지금 1). `kb.py`는 자기가 모르는 `format`을 만나면 새로 받으라고 알립니다. 내용만 바뀌는 판(행 추가·수정)은 `format`을 올리지 않습니다.
- **무엇이 바뀌었나**: [Releases](https://github.com/BBI-BBO/medagent-kb/releases)에 판마다 바뀐 내용과 스냅숏 시각이 있습니다. `python kb.py versions`로도 봅니다.

`version.json` 예:
```json
{"version": "kb-2026.10.07.1", "format": 1, "snapshot": "2026-10-07 20:40", "public": true, "excluded": ["hpoa"],
 "counts": {"kcd_codes": 9626, "disease_names": 2950, "name_phenotype_links": 67709, "kg_edges": 18467, "findings": 292, "mechanisms": 406}}
```

## 4. 자료 구조 (다른 언어에서 직접 읽기)

파일 네 개는 모두 `앞머리 + JSON + ;` 입니다. 앞머리를 떼면 JSON 입니다.

| 파일 | 앞머리 | 내용 |
|---|---|---|
| `data.js` (12MB) | `window.DB = ` | 표 · 관계 그래프 · 이름 사전 (아래) |
| `pheno.js` (6MB) | `window.DB.tables.entity_phenotype.rows = ` | 병명 → HPO 표현형 행 |
| `fill.js` (14MB) | `window.DB.fill = ` | 기전 채우기: AI 기전 초안(B) · 유전자→GO 자동 연결(A) |
| `search.js` (4.5MB) | `window.DB_ALIAS = ` | 질병 검색 별칭 `{KCD코드: [[별칭, 대상, 종류], …]}` |
| `version.json` | (그냥 JSON) | 판·형식·행 수 |

**`window.DB` 주요 키**
- `tables`: `{표이름: {columns: [{name, type, comment}], rows: [[…]], total, pk, fks, comment, kind}}` — 행은 `columns` 순서의 배열. 큰 표는 미리보기만 (`total`이 실제 수).
  자주 쓰는 표: `disease`(KCD 코드 15,768 · 3·4자리 9,626), `kcd_entity`(병명 2,950: kcd, mondo_id, name_ko, name_en, name_src, method), `finding`(소견 292), `mechanism`(기전 406), `kcd_ext`(KCD↔MONDO), `entity_phenotype`(열: kcd, mondo_id, hpo_id, finding_id, sources, f_dismech, f_orphadata, f_hpoa, n_ext, min_depth, diagnostic, deny_only).
- `kg`: 관계 `[출발, 관계, 도착, 출처, qualifier, polarity, 근거(주호소 스키마), 원문 표기]` — 출발·도착은 원본 ID (`KCD:E14`, `SKKU:F:dysuria`, `HP:…`, `LOINC:…`).
- `dismech`: `{mechs: [[id, MONDO, 영어, 한국어, 단계, 차수, GO, GO방향]], edges: [[기전, 다음기전, HPO]], pheno, mondo2kcd: {MONDO: [[KCD4, MONDO, 깊이]]}, go, labels}`.
- `loinc`: `{코드: [이름, 한국어, component, property, 검체, 방법, 부하 조건, 분석물]}` · `analyte_ko` · `hpo_labels: {HP: [영어, 한국어]}` · `mondo_labels` · `node_labels` · `sources` · `version` · `format`.
- `fill`(fill.js): `{nodes: {ID: […]}, edges: [[출발, 관계, 도착, 출처, qualifier, 신뢰도 0~3, 근거, 깊이, 대상 병명, 작성, 검토, 판정]]}` — 신뢰도 3 높음 · 2 중간 · 1 낮음 · 0 가설.

**노드 ID** (`kb.py`·화면이 쓰는 그래프 ID, `kb.nid()`가 원본 ID를 바꿈)

| 접두 | 종류 | 예 |
|---|---|---|
| `D|` | 질병: KCD 코드(`D|E14`) 또는 병명(`D|E830@MONDO:0010200` = 코드@MONDO) | 진단 답의 단위는 병명 |
| `F|` | 소견 (성균관의대 사전) | `F|hypoglycemia` |
| `H|` | 소견 (HPO) | `H|HP:0001744` |
| `M|` · `X|` · `C|` | 기전: 성균관의대 · DisMech · AI 초안(검수 전) | |
| `G|` · `P|` | 유전자 (Orphanet) · GO 생물학적 과정 | `G|HGNC:…` · `P|GO:…` |
| `E|` | 원인·노출 (스키마 표기) | |
| `A|` · `T|` | 검사 묶음(분석물) · LOINC 검사 | `A|Glucose` · `T|2345-7` |

**관계** (모두 원인 → 결과 방향): `causes` 일으킴 · `constitutes` 이룸(기전 → 질병) · `manifests_as` 나타남(기전 → 소견) · `has_phenotype` 표현형(질병 → 소견) · `indicates` 검사 판정(검사 → 소견) · `subclass_of` 종류(병명 → KCD 코드) · `involved_in` 관여(유전자 → 과정).

## 5. 자료와 이용 조건

KCD(HIRA 상병마스터), 성균관의대 LRC PBL 주호소 스키마(팀 자체 수집), HPO, MONDO, Orphadata, DisMech, LOINC·LOINC2HPO, Gene Ontology를 묶었습니다. 출처별 판과 이용 조건은 화면 오른쪽 위 **DB 정보**에 있습니다.

- 공개판에는 **HPOA(phenotype.hpoa)에서만 온 연결을 넣지 않았습니다** (이용 조건). 그래서 팀 내부판보다 표현형 수가 적습니다.
- **AI(Claude)** 표시가 붙은 기전·연결·병명 자리·한국어 이름은 AI가 쓰고 다른 AI가 따로 검토한 것으로, **의학과 검수 전**입니다.
- 화면 글꼴: Pretendard, IBM Plex Mono (SIL Open Font License 1.1).

### 올리는 법 (팀)

연구 폴더에서 `bash tools/deploy_public_viewer.sh "바뀐 내용"` — HPOA를 걸러 공개판을 만들고, `gh-pages` 가지에 마지막 판 하나를 올리고, 그 판의 자료를 Release(`kb-YYYY.MM.DD.N`)로 보관합니다.
