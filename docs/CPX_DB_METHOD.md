# CPX 의료 지식 DB 보강 방법

## 범위와 분리 원칙

이번 보강은 `kb-2026.10.08.2` 공개판을 고정 기초판으로 삼는다. 대상은 성대 주호소 스키마에 이미 연결된 질환 전체이며, NOVA 공개 샘플의 정답·모범 SOAP·채점 결과를 질환 선택이나 간선 작성에 사용하지 않는다.

선정 순서는 다음과 같다.

1. 모든 CPX 연결 질환을 기계적으로 감사한다.
2. 기전 경로가 없거나 직접 소견만 있는 질환을 우선순위로 만든다.
3. 여러 주호소에 반복해 등장하는 임상 핵심 질환을 먼저 보강한다.
4. 외부 교과서에서 질환 → 기전 → 증상/징후 연결을 확인한다.
5. 사실 단위로 짧게 요약하고 URL, 확인일, 검토 상태를 함께 저장한다.
6. 공통 기전 노드를 지나 다른 주호소 소견이 섞이지 않도록 스키마 문맥을 유지한다.

따라서 이 자료는 샘플 세 건을 미리 맞춘 정답표가 아니라, 같은 규칙으로 전체 DB의 결손을 줄인 오버레이다.

## 그래프 규칙

- 인과 방향은 질환/원인 → 기전 → 증상·징후이다.
- 같은 의미의 기전은 가능한 한 기존 정규 노드를 재사용한다.
- 지나치게 일반적인 `감염`, `염증`, `허혈` 노드는 주호소 스키마 문맥과 함께 순회한다.
- 연속된 `skku_lrc_pbl` 또는 `cpx_core_2026` 간선은 `ref`에 공통 스키마가 하나 이상 있어야 한다.
- 코드 수준 연결이 아형 전체에 성립하지 않을 수 있으면 qualifier에 범위를 기록한다.
- 진찰 행동은 질환-소견 간선이 아니다. 행동 사전과 확인 가능한 소견의 매핑으로 분리한다.
- `exams_for_disease` 결과는 진찰 후보이지 예상 양성 결과가 아니다.

## 이번 보강 질환군

기초판에서 기전 결손이 크고 CPX에서 반복되는 다음 16개 질환군을 먼저 보강했다.

| KCD | 질환군 | 핵심 기전 |
|---|---|---|
| I21 | 급성 심근경색 | 죽상경화판 파열 → 혈전성 관상동맥 폐색 → 허혈/괴사 |
| G373 | 횡단척수염 | 척수 염증 → 탈수초/축삭 손상 |
| E512 | 베르니케뇌병증 | 티아민 결핍 → 뇌 에너지 대사 장애 |
| J848 | 특정 간질성 폐질환 | 폐포·간질 손상 → 섬유화 → 확산 장애 |
| I455 | 심장차단 | 방실 전도 장애 → 서맥/심박출량 저하 |
| K658 | 기타 복막염 | 복막 염증 → 복부 방어/경직 |
| G618 | 염증성 다발신경병증 | 면역성 염증 → 분절성 탈수초 |
| G474 | 발작수면 | 오렉신 결핍 → 수면-각성 불안정 |
| N12 | 세뇨관간질신염 | 세뇨관·간질 염증 → 사구체여과 저하 |
| I40 | 급성 심근염 | 심근 염증 → 심근세포 손상/심박출량 저하 |
| E051/E052 | 독성 갑상선 결절성 질환 | 자율적 호르몬 생성 → 대사율 증가 |
| E065 | 만성 갑상선염 | 자가면역성 여포세포 파괴 → 호르몬 결핍(해당 아형) |
| K44 | 횡격막탈장 | 복강 장기의 흉강 내 탈출 → 폐 압박 |
| U071 | COVID-19 | SARS-CoV-2 조직 손상 → 전신 염증 |
| B181 | 만성 B형간염 | 바이러스 연관 면역성 간손상 |

## 근거 자료

질환 기전은 NCBI Bookshelf의 다음 자료를 사용했다.

- [Myocardial Infarction](https://www.ncbi.nlm.nih.gov/books/NBK537076/)
- [Transverse Myelitis](https://www.ncbi.nlm.nih.gov/books/NBK559302/)
- [Wernicke Encephalopathy](https://www.ncbi.nlm.nih.gov/books/NBK470344/)
- [Interstitial Lung Disease](https://www.ncbi.nlm.nih.gov/books/NBK541084/)
- [Atrioventricular Block](https://www.ncbi.nlm.nih.gov/books/NBK459147/)
- [Peritoneum](https://www.ncbi.nlm.nih.gov/books/NBK534788/)
- [Chronic Inflammatory Demyelinating Polyradiculoneuropathy](https://www.ncbi.nlm.nih.gov/books/NBK563249/)
- [Narcolepsy](https://www.ncbi.nlm.nih.gov/books/NBK459236/)
- [Tubulointerstitial Nephritis](https://www.ncbi.nlm.nih.gov/books/NBK557537/)
- [Myocarditis](https://www.ncbi.nlm.nih.gov/books/NBK441847/)
- [Hyperthyroidism](https://www.ncbi.nlm.nih.gov/books/NBK537053/)
- [Thyroiditis](https://www.ncbi.nlm.nih.gov/books/NBK555975/)
- [Diaphragmatic Hernia](https://www.ncbi.nlm.nih.gov/books/NBK536952/)
- [COVID-19](https://www.ncbi.nlm.nih.gov/books/NBK554776/)
- [Hepatitis B](https://www.ncbi.nlm.nih.gov/books/NBK555945/)

진찰 행동은 [Physical Examination](https://www.ncbi.nlm.nih.gov/books/NBK361/), [Chest](https://www.ncbi.nlm.nih.gov/books/NBK368/), [Abdomen](https://www.ncbi.nlm.nih.gov/books/NBK420/), [Musculoskeletal System](https://www.ncbi.nlm.nih.gov/books/NBK272/), [Neurologic Examination](https://www.ncbi.nlm.nih.gov/books/NBK373/), [Thyroid](https://www.ncbi.nlm.nih.gov/books/NBK244/), [Edema](https://www.ncbi.nlm.nih.gov/books/NBK348/), [Lymph Nodes](https://www.ncbi.nlm.nih.gov/books/NBK256/), [Jugular Venous Pressure](https://www.ncbi.nlm.nih.gov/books/NBK300/), [Anthropometry](https://www.ncbi.nlm.nih.gov/books/NBK335/)를 기준으로 정규화했다.

`cpx_evidence.review_status`의 `independent_model_checked;clinician_pending`은 URL과 요약을 독립적으로 재확인했지만 의료인 최종 검수는 남아 있다는 뜻이다.

## 진찰 모델

`exam_action` 28개는 활력징후, 전신 시진, 흉부, 심혈관, 복부, 근골격, 신경, 갑상선, 림프절, 신체계측으로 나뉜다. `exam_action_finding`은 62개 연결로 각 행동이 확인할 수 있는 표준 소견을 지정한다.

예를 들어 복부 촉진은 압통·방어·경직·종괴·장기비대를 확인할 수 있지만, 복막염 질환 노드와 연결됐다는 사실만으로 방어가 있다고 기록해서는 안 된다.

## 감사 결과

같은 감사기로 기초판과 보강판을 비교했다.

| 지표 | kb-2026.10.08.2 | kb-2026.10.13.1 |
|---|---:|---:|
| CPX 연결 질환 | 1,876 | 1,876 |
| 기전 경로 없음 | 147 | 131 |
| 직접 소견만 있음 | 229 | 212 |
| 물리 진찰 징후 없음 | 357 | 355 |

전역 순회와 스키마 제한 순회의 결과 차이는 오류 건수가 아니라 공유 기전 허브의 영향 범위를 보여 주는 진단 지표다. 기본 API와 공개 화면은 스키마 제한 순회를 사용한다.

## 재현

```bash
python3 tools/build_cpx_release.py \
  --base /tmp/medagent-kb-cache/kb-2026.10.08.2 \
  --output /tmp/medagent-kb-build/kb-2026.10.13.1

MEDAGENT_KB_BASE=/tmp/medagent-kb-cache/kb-2026.10.08.2 \
MEDAGENT_KB_CACHE=/tmp/medagent-kb-cache \
PYTHONPATH=. python3 -m unittest discover -s tests -v

python3 tools/audit_cpx_coverage.py \
  --base /tmp/medagent-kb-build/kb-2026.10.13.1
```
