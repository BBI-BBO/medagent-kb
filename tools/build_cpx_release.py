#!/usr/bin/env python3
"""Build a reproducible public KB release by applying the CPX overlay.

The script never mutates the pinned base release.  It copies the immutable
assets to a new directory, adds auditable tables and graph edges to data.js,
and emits version.json.  Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OVERLAY = ROOT / "overlays" / "cpx_core_2026.10.13.1.json"
RELEASE = "https://github.com/BBI-BBO/medagent-kb/releases/download/{version}/{name}"
HEAD = "window.DB = "
ASSETS = ("data.js", "pheno.js", "fill.js", "search.js")


def column(name: str, type_: str = "text", *, required: bool = False, comment: str | None = None) -> dict[str, Any]:
    return {"name": name, "type": type_, "notnull": required, "comment": comment}


def table(
    columns: list[dict[str, Any]],
    rows: list[list[Any]],
    comment: str,
    *,
    pk: tuple[str, ...] = (),
    fks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "layer": "출처",
        "kind": "table",
        "comment": comment,
        "columns": columns,
        "pk": list(pk),
        "fks": fks or [],
        "hidden": [],
        "rows": rows,
        "total": len(rows),
    }


def read_data(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith(HEAD):
        raise ValueError(f"{path}: data.js 앞머리가 다릅니다")
    return json.loads(raw[len(HEAD):].rstrip().rstrip(";"))


def write_data(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        HEAD + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


def ensure_base(base: Path, version: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        path = base / name
        if path.exists():
            continue
        req = urllib.request.Request(
            RELEASE.format(version=version, name=name),
            headers={"User-Agent": "medagent-kb-cpx-builder/1"},
        )
        with urllib.request.urlopen(req, timeout=300) as response:
            path.write_bytes(response.read())


def rows_as_dicts(tab: dict[str, Any]) -> list[dict[str, Any]]:
    names = [item["name"] for item in tab["columns"]]
    return [dict(zip(names, row)) for row in tab["rows"]]


def presentation_components(data: dict[str, Any], overlay: dict[str, Any]) -> list[list[Any]]:
    overrides = overlay.get("presentation_overrides", {})
    finding_rows = {
        row["id"]: row for row in rows_as_dicts(data["tables"]["finding"])
    }
    out: list[list[Any]] = []
    for presentation in rows_as_dicts(data["tables"]["presentation"]):
        components = overrides.get(presentation["id"])
        if components is None:
            components = [{
                "expression_ko": presentation["name_ko"],
                "node_id": "F|" + presentation["finding_id"] if presentation["finding_id"] else None,
                "semantic_role": "core" if presentation["finding_id"] else "care_context",
            }]
        for ordinal, component in enumerate(components, 1):
            node_id = component.get("node_id")
            finding = finding_rows.get(node_id[2:]) if node_id and node_id.startswith("F|") else None
            out.append([
                presentation["id"],
                ordinal,
                component["expression_ko"],
                component.get("normalized_ko") or (finding or {}).get("name_ko") or component["expression_ko"],
                node_id,
                component.get("concept_kind") or (finding or {}).get("kind") or "context",
                component.get("semantic_role", "core"),
                component.get("onset"),
                component.get("body_site"),
                component.get("laterality"),
                component.get("severity"),
                component.get("context"),
                "skku_lrc_pbl+cpx_core_2026",
            ])
    return out


def validate(data: dict[str, Any], overlay: dict[str, Any]) -> None:
    tables = data["tables"]
    diseases = {row[0] for row in tables["disease"]["rows"]}
    findings = {row[0] for row in tables["finding"]["rows"]}
    mechanisms = {row[0] for row in tables["mechanism"]["rows"]} | {row[0] for row in overlay["mechanisms"]}
    hpo = set(data.get("hpo_labels", {}))
    presentations = {row[0] for row in tables["presentation"]["rows"]}

    def unique(label: str, values: list[Any]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"{label}: 중복 키가 있습니다")

    unique("추가 기전", [row[0] for row in overlay["mechanisms"]])
    unique("근거", [row[0] for row in overlay["evidence"]])
    unique("진찰 행동", [row[0] for row in overlay["exam_actions"]])
    unique("진찰-소견 연결", [(row[0], row[1]) for row in overlay["exam_action_findings"]])

    unknown_presentations = set(overlay.get("presentation_overrides", {})) - presentations
    if unknown_presentations:
        raise ValueError(f"없는 주호소 override: {sorted(unknown_presentations)}")

    def valid(raw: str | None) -> bool:
        if not raw:
            return True
        if raw.startswith("KCD:"):
            return raw[4:].replace(".", "")[:4] in diseases
        if raw.startswith("SKKU:F:"):
            return raw[7:] in findings
        if raw.startswith("SKKU:M:"):
            return raw[7:] in mechanisms
        if raw.startswith("HP:"):
            return raw in hpo
        return True

    bad = [(edge[0], edge[2]) for edge in overlay["kg"] if not valid(edge[0]) or not valid(edge[2])]
    if bad:
        raise ValueError(f"오버레이 간선에 없는 노드가 있습니다: {bad[:10]}")

    graph_nodes = {"F|" + item for item in findings} | {"H|" + item for item in hpo}
    for presentation_id, components in overlay.get("presentation_overrides", {}).items():
        if not components:
            raise ValueError(f"{presentation_id}: 구성요소가 비었습니다")
        for component in components:
            node_id = component.get("node_id")
            if node_id is not None and node_id not in graph_nodes:
                raise ValueError(f"{presentation_id}: 없는 정규화 소견 {node_id}")

    action_ids = {row[0] for row in overlay["exam_actions"]}
    for action_id, node_id, _ in overlay["exam_action_findings"]:
        if action_id not in action_ids:
            raise ValueError(f"없는 진찰 행동 {action_id}")
        if node_id not in graph_nodes:
            raise ValueError(f"{action_id}: 없는 진찰 소견 {node_id}")


def build(base: Path, output: Path, overlay_path: Path) -> dict[str, Any]:
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    ensure_base(base, overlay["base_version"])
    data = read_data(base / "data.js")
    if data.get("version") != overlay["base_version"]:
        raise ValueError(f"기초판 불일치: {data.get('version')} != {overlay['base_version']}")
    validate(data, overlay)

    output.mkdir(parents=True, exist_ok=True)
    for name in ASSETS[1:]:
        shutil.copy2(base / name, output / name)

    source_table = data["tables"]["source"]
    source_columns = [item["name"] for item in source_table["columns"]]
    source_id = max(row[source_columns.index("id")] for row in source_table["rows"]) + 1
    source = overlay["source"]
    source_table["rows"].append([source_id] + [source.get(name) for name in source_columns[1:]])
    source_table["total"] = len(source_table["rows"])
    data.setdefault("sources", {})[source["code"]] = {
        "title": source["title"],
        "rights": source["rights"],
        "version": source["version_date"],
    }

    mechanism_table = data["tables"]["mechanism"]
    known_mechanisms = {row[0] for row in mechanism_table["rows"]}
    mechanism_table["rows"].extend(row for row in overlay["mechanisms"] if row[0] not in known_mechanisms)
    mechanism_table["total"] = len(mechanism_table["rows"])

    existing_edges = {tuple(json.dumps(item, ensure_ascii=False) for item in edge) for edge in data["kg"]}
    additions = []
    for edge in overlay["kg"]:
        key = tuple(json.dumps(item, ensure_ascii=False) for item in edge)
        if key not in existing_edges:
            additions.append(edge)
            existing_edges.add(key)
    data["kg"].extend(additions)
    if "kg_edge" in data["tables"]:
        data["tables"]["kg_edge"]["total"] = len(data["kg"])

    components = presentation_components(data, overlay)
    data["tables"]["presentation_component"] = table(
        [
            column("presentation_id", required=True),
            column("ordinal", "integer", required=True),
            column("expression_ko", required=True, comment="성대 원문에서 분리한 표면 표현"),
            column("normalized_ko", required=True, comment="표준 소견 사전의 정규 라벨"),
            column("node_id", comment="F| 또는 H| 표준 소견 노드"),
            column("concept_kind", required=True, comment="symptom · sign · lab · developmental_state · care_context 등"),
            column("semantic_role", required=True, comment="core · coequal · care_context"),
            column("onset", comment="acute · chronic 등 시간 수식어"),
            column("body_site", comment="부위 수식어"),
            column("laterality", comment="left · right · bilateral 등 좌우 수식어"),
            column("severity", comment="mild · moderate · severe 등 중증도 수식어"),
            column("context", comment="월경·배뇨·산전관리 등 발생·진료 맥락"),
            column("source", required=True),
        ],
        components,
        "성대 주호소 원문을 보존한 채 독립 증상과 시점·부위 수식어로 분해한 정규화 층",
        pk=("presentation_id", "ordinal"),
        fks=[{"cols": ["presentation_id"], "table": "presentation", "refcols": ["id"], "virtual": False}],
    )
    data["tables"]["normalization_rule"] = table(
        [column("id", required=True), column("rule_ko", required=True), column("example")],
        overlay["normalization_rules"],
        "표현 정규화 원칙. 특정 증례 답이 아니라 전체 주호소에 동일하게 적용",
        pk=("id",),
    )
    data["tables"]["cpx_evidence"] = table(
        [
            column("id", required=True), column("subjects", required=True), column("claim_ko", required=True),
            column("source_title", required=True), column("source_url", required=True),
            column("checked_on", "date", required=True), column("review_status", required=True),
        ],
        overlay["evidence"],
        "CPX 기전 연결의 교과서 근거 요약과 검토 상태. 원문을 복제하지 않음",
        pk=("id",),
    )
    data["tables"]["exam_action"] = table(
        [
            column("id", required=True), column("system", required=True), column("name_ko", required=True),
            column("name_en"), column("method_ko", required=True), column("source_url", required=True),
            column("priority", "integer", required=True),
        ],
        overlay["exam_actions"],
        "질환 정답과 독립된 표준 진찰 행동 사전. 행동 자체와 확인 가능한 소견을 분리",
        pk=("id",),
    )
    data["tables"]["exam_action_finding"] = table(
        [column("action_id", required=True), column("node_id", required=True), column("interpretation", required=True)],
        overlay["exam_action_findings"],
        "진찰 행동으로 확인할 수 있는 표준 소견. 양성 결과를 미리 단정하지 않음",
        pk=("action_id", "node_id"),
        fks=[{"cols": ["action_id"], "table": "exam_action", "refcols": ["id"], "virtual": False}],
    )

    layer = data.setdefault("layers", {}).setdefault("출처", [])
    for name in ("presentation_component", "normalization_rule", "cpx_evidence", "exam_action", "exam_action_finding"):
        if name not in layer:
            layer.append(name)

    data["version"] = overlay["version"]
    data["generated_at"] = source["version_date"] + " 00:00"
    data.setdefault("stats", {})["cpx_core_2026"] = {
        "base_version": overlay["base_version"],
        "mechanisms_added": len(overlay["mechanisms"]),
        "kg_edges_added": len(additions),
        "presentation_components": len(components),
        "exam_actions": len(overlay["exam_actions"]),
        "exam_action_finding_links": len(overlay["exam_action_findings"]),
        "evidence_records": len(overlay["evidence"]),
        "selection": "case-answer-blind CPX common-disease and examination coverage",
        "review": "independent model checked; clinician review pending",
    }
    write_data(output / "data.js", data)

    digest = hashlib.sha256()
    for name in ASSETS:
        digest.update((output / name).read_bytes())
    version = {
        "version": overlay["version"],
        "format": data.get("format", 1),
        "snapshot": data["generated_at"],
        "public": bool(data.get("public")),
        "excluded": ["hpoa"],
        "base_version": overlay["base_version"],
        "data_sha256": digest.hexdigest()[:16],
        "counts": {
            "kcd_codes": sum(1 for row in data["tables"]["disease"]["rows"] if len(row[0]) <= 4),
            "disease_names": data["tables"]["kcd_entity"]["total"],
            "name_phenotype_links": data["tables"]["entity_phenotype"]["total"],
            "kg_edges": len(data["kg"]),
            "findings": data["tables"]["finding"]["total"],
            "mechanisms": data["tables"]["mechanism"]["total"],
            "presentation_components": len(components),
            "exam_actions": len(overlay["exam_actions"]),
        },
    }
    (output / "version.json").write_text(
        json.dumps(version, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--base", type=Path, default=Path("~/.cache/medagent-kb/kb-2026.10.08.2").expanduser())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.base.expanduser(), args.output, args.overlay)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
