# 성균관의대 주호소 표현 정규화

## 목적

성대 LRC PBL 주호소 표현은 사람이 읽는 원문으로 보존하면서, 검색·추론에는 더 작은 임상 의미 단위를 사용한다. 정규화는 특정 증례 정답을 맞히기 위한 변환이 아니라 모든 주호소에 같은 규칙을 적용하는 호환 층이다.

원본 `presentation.id`, `name_ko`, `name_en`, 대표 `finding_id`는 바꾸지 않는다. 세분화 결과는 `presentation_component`에만 추가한다.

## 저장 단위

`presentation_component` 한 행은 다음을 분리해 저장한다.

| 열 | 의미 |
|---|---|
| `expression_ko` | 성대 원문에서 잘라 낸 표면 표현 |
| `normalized_ko` | 표준 소견 사전의 정규 라벨 |
| `node_id` | `F|` 또는 `H|` 표준 소견 노드. 진료 맥락이면 비울 수 있음 |
| `concept_kind` | symptom, sign, lab, developmental_state, care_context 등 |
| `semantic_role` | 단일 핵심(`core`), 병렬 핵심(`coequal`), 진료 맥락(`care_context`) |
| `onset` | acute, chronic 같은 발병·경과 수식어 |
| `body_site` | chest, pelvis, hands_and_feet 같은 부위 수식어 |
| `laterality` | left, right, bilateral 같은 좌우 수식어 |
| `severity` | mild, moderate, severe 같은 중증도 수식어 |
| `context` | menstruation, urination, prenatal care 같은 상황 맥락 |

## 규칙

1. 독립적으로 문진하거나 확인할 수 있는 병렬 표현은 분리한다.
   - `구역·구토` → `nausea` + `vomiting`
   - `관절통·관절부기` → `arthralgia` + `joint_swelling`
   - `무뇨·핍뇨` → `anuria` + `oliguria`
   - `저혈압·쇼크` → `hypotension` + `shock`
   - `월경통·골반통` → `dysmenorrhea` + `pelvic_pain`
   - `성장지연·사춘기발달` → `short_stature` + `delayed_puberty`

2. 시간·부위·좌우·중증도·맥락은 새 질환이나 소견으로 만들지 않는다.
   - `호흡곤란(급성)` → `dyspnea`, `onset=acute`
   - `손발저림` → `paresthesia`, `body_site=hands_and_feet`
   - `배뇨통` → `dysuria`, `context=urination`

3. 원문과 정규 표준 라벨을 모두 보존한다. 띄어쓰기·번역 차이 때문에 중복 개념을 만들지 않는다.

4. 고정 임상 표현이나 비율은 의미가 달라질 수 있으므로 문자만 보고 쪼개지 않는다. 예: BUN/Cr, PT/INR, CT/MRI.

5. 진료 맥락은 증상으로 위장하지 않는다. `산전관리`는 `care_context`이고 양성·음성 소견이 아니다.

6. 정규화만으로 진찰 결과를 생성하지 않는다. `exam_action`은 수행할 행동, `exam_action_finding`은 확인 가능한 결과이며 실제 결과는 별도로 관찰해야 한다.

## 호환성과 조회

```python
from kb import KB

kb = KB(version="kb-2026.10.13.1")
kb.presentation("vomiting")
kb.presentation("dyspnea_acute")
```

옛 소비자는 기존 `presentation` 표만 계속 읽을 수 있다. 새 소비자는 `components`를 사용해 병렬 증상과 수식어를 분리한다.

## 품질 확인

- 모든 `node_id`가 실제 `finding` 또는 HPO 노드인지 빌드 시 검사한다.
- 모든 성대 주호소는 최소 한 개 구성요소를 가져야 한다.
- 원본 주호소 행 수와 ID는 기초판과 동일해야 한다.
- 복합 표현은 정해진 순서(`ordinal`)로 재구성할 수 있어야 한다.
- 특정 NOVA 공개 샘플의 진단·모범 기록은 정규화 입력으로 사용하지 않는다.
