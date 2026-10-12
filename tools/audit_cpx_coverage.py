#!/usr/bin/env python3
"""Audit CPX disease coverage without reading case answers.

The public graph intentionally normalizes identical mechanisms into one node.
That is useful for search, but a traversal can accidentally leave the chief-
complaint schema in which a SKKU edge was asserted.  This audit reports both
the legacy traversal and a schema-scoped traversal so data work can distinguish
real coverage from hub-mediated over-connection.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kb import CAUSAL, KB  # noqa: E402


MECHANISM_KINDS = frozenset("MXCGP")
TERMINAL_KINDS = frozenset("FHTD")


def schema_refs(edge: dict[str, Any]) -> frozenset[str]:
    if edge.get("src") not in {"skku_lrc_pbl", "cpx_core_2026"} or not edge.get("ref"):
        return frozenset()
    return frozenset(x.strip() for x in edge["ref"].split(" · ") if x.strip())


def walk(kb: KB, root: str, *, schema_scoped: bool) -> dict[str, Any]:
    """Walk causal edges and retain SKKU schema context when requested."""
    queue = deque([(root, None, False)])
    seen: set[tuple[str, frozenset[str] | None, bool]] = {(root, None, False)}
    findings: set[str] = set()
    mechanism_findings: set[str] = set()
    mechanisms: set[str] = set()
    traversed_edges = 0

    while queue:
        node, context, used_mechanism = queue.popleft()
        if node != root and node[0] in TERMINAL_KINDS:
            continue
        for edge in kb.GO.get(node, []):
            if edge.get("p") not in CAUSAL or not kb._ok(edge):
                continue
            if edge.get("pol") == "absent":
                continue
            if edge.get("tgt") and root[0] == "D" and edge["tgt"] != root[2:]:
                continue

            next_context = context
            refs = schema_refs(edge)
            if schema_scoped and refs:
                if context is None:
                    next_context = refs
                else:
                    next_context = context & refs
                    if not next_context:
                        continue

            target = edge["o"]
            if target == root:
                continue
            traversed_edges += 1
            next_used_mechanism = used_mechanism or target[0] in MECHANISM_KINDS
            if target[0] in "FH":
                findings.add(target)
                if used_mechanism:
                    mechanism_findings.add(target)
                continue
            if target[0] in MECHANISM_KINDS:
                mechanisms.add(target)

            state = (target, next_context, next_used_mechanism)
            if state not in seen:
                seen.add(state)
                queue.append(state)

    return {
        "findings": findings,
        "mechanism_findings": mechanism_findings,
        "mechanisms": mechanisms,
        "edges": traversed_edges,
    }


def disease_name(kb: KB, node: str) -> str:
    return kb.node(node).get("name") or node


def audit(kb: KB) -> dict[str, Any]:
    presentations = {
        "F|" + row["finding_id"]: row
        for row in kb.table("presentation")
        if row.get("finding_id")
    }
    finding_kind = {"F|" + key: row.get("kind") for key, row in kb.FND.items()}

    roots = sorted(
        node
        for node, refs in kb.SKREF.items()
        if node.startswith("D|") and refs and node in kb.GO
    )
    rows: list[dict[str, Any]] = []
    for root in roots:
        legacy = walk(kb, root, schema_scoped=False)
        scoped = walk(kb, root, schema_scoped=True)
        scoped_findings = scoped["findings"]
        direct = {
            edge["o"]
            for edge in kb.GO.get(root, [])
            if edge.get("p") == "has_phenotype"
            and edge.get("o", "")[:1] in "FH"
            and edge.get("pol") != "absent"
            and kb._ok(edge)
        }
        complaint_ids = sorted(
            presentations[item]["id"]
            for item in scoped_findings & presentations.keys()
        )
        schemas = sorted(kb.SKREF.get(root, set()))
        rows.append(
            {
                "id": root,
                "name": disease_name(kb, root),
                "schemas": schemas,
                "schema_count": len(schemas),
                "chief_complaints": complaint_ids,
                "chief_complaint_count": len(complaint_ids),
                "findings": len(scoped_findings),
                "direct_findings": len(direct),
                "mechanism_findings": len(scoped["mechanism_findings"]),
                "mechanisms": len(scoped["mechanisms"]),
                "physical_signs": sum(finding_kind.get(x) == "sign" for x in scoped_findings),
                "legacy_findings": len(legacy["findings"]),
                "cross_schema_findings": len(legacy["findings"] - scoped_findings),
                "edges": scoped["edges"],
            }
        )

    gaps = {
        "no_finding": [r for r in rows if not r["findings"]],
        "no_mechanism": [r for r in rows if not r["mechanisms"]],
        "direct_only": [
            r for r in rows if r["findings"] and not r["mechanism_findings"]
        ],
        "no_physical_sign": [r for r in rows if not r["physical_signs"]],
        "cross_schema": [r for r in rows if r["cross_schema_findings"]],
    }
    priority = sorted(
        rows,
        key=lambda r: (
            not bool(r["cross_schema_findings"]),
            bool(r["mechanism_findings"]),
            bool(r["physical_signs"]),
            -r["schema_count"],
            r["name"],
        ),
    )
    complaint_coverage: dict[str, dict[str, int]] = {}
    for node, presentation in sorted(presentations.items(), key=lambda x: x[1]["id"]):
        matched = [r for r in rows if presentation["id"] in r["chief_complaints"]]
        complaint_coverage[presentation["id"]] = {
            "diseases": len(matched),
            "with_mechanism": sum(bool(r["mechanism_findings"]) for r in matched),
            "with_physical_sign": sum(bool(r["physical_signs"]) for r in matched),
        }

    return {
        "meta": {
            "version": kb.version,
            "generated_at": kb.generated_at,
            "selection": "all diseases linked to a SKKU chief-complaint schema; case-answer-blind",
            "schema_scoping": "successive SKKU edges must share at least one schema reference",
        },
        "counts": {
            "diseases": len(rows),
            "chief_complaints": len(presentations),
            "no_finding": len(gaps["no_finding"]),
            "no_mechanism": len(gaps["no_mechanism"]),
            "direct_only": len(gaps["direct_only"]),
            "no_physical_sign": len(gaps["no_physical_sign"]),
            "cross_schema": len(gaps["cross_schema"]),
        },
        "complaints": complaint_coverage,
        "gap_samples": {
            key: sorted(value, key=lambda r: (-r["schema_count"], r["name"]))[:100]
            for key, value in gaps.items()
        },
        "priority": priority[:250],
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="kb-2026.10.08.2")
    parser.add_argument("--base", help="로컬 빌드 폴더. 지정하면 --version 대신 이 자료를 읽음")
    parser.add_argument("--cache", default="~/.cache/medagent-kb")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    kb = KB(
        version=None if args.base else args.version,
        base=args.base,
        cache=str(Path(args.cache).expanduser()),
    )
    report = audit(kb)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    counts = report["counts"]
    print(
        " · ".join(
            [
                f"판 {report['meta']['version']}",
                f"CPX 연결 질환 {counts['diseases']}",
                f"기전 없음 {counts['no_mechanism']}",
                f"직접 소견만 {counts['direct_only']}",
                f"진찰징후 없음 {counts['no_physical_sign']}",
                f"전역/스키마 차이 {counts['cross_schema']}",
            ]
        )
    )
    for row in report["priority"][: args.top]:
        print(
            f"{row['id']}\t{row['name']}\t스키마 {row['schema_count']}\t"
            f"기전 {row['mechanisms']}\t소견 {row['findings']}\t"
            f"진찰 {row['physical_signs']}\t전역차이 {row['cross_schema_findings']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
