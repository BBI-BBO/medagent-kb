#!/usr/bin/env python3
"""Patch the public gh-pages viewer to understand the CPX overlay.

The viewer lives on the gh-pages branch, while this reproducible patch belongs
on main.  It fails loudly if the expected upstream viewer has changed.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch(text: str) -> str:
    text = replace_once(
        text,
        "  ['source', 'presentation', 'finding', 'mechanism', 'skku_exposure', 'disease', 'kg_edge'],",
        "  ['source', 'presentation', 'presentation_component', 'normalization_rule', 'finding', 'mechanism', 'skku_exposure', 'disease', 'kg_edge', 'cpx_evidence', 'exam_action', 'exam_action_finding'],",
        "ERD overlay tables",
    )
    text = replace_once(
        text,
        "const SRC_LABEL = {skku_lrc_pbl: '성균관의대', claude_draft: 'AI (Claude)', hira_kcd_master: 'KCD 검표·별표', loinc2hpo: 'LOINC2HPO',",
        "const SRC_LABEL = {skku_lrc_pbl: '성균관의대', cpx_core_2026: 'CPX 교과서 보강', claude_draft: 'AI (Claude)', hira_kcd_master: 'KCD 검표·별표', loinc2hpo: 'LOINC2HPO',",
        "CPX source label",
    )
    text = replace_once(
        text,
        "const SKREF = new Map();  /* 노드 → 이 노드가 나온 성균관의대 주호소 스키마들 */",
        """const SCHEMA_SRCS = new Set(['skku_lrc_pbl', 'cpx_core_2026']);
const isSchemaSource = src => SCHEMA_SRCS.has(src);
const schemaRefs = e => !isSchemaSource(e.src) || !e.ref ? null : new Set(e.ref.split(' · ').map(z => z.trim()).filter(Boolean));
const schemaContext = (context, e) => {
  const refs = schemaRefs(e);
  if (!refs) return context;
  if (!context) return refs;
  const shared = new Set([...context].filter(z => refs.has(z)));
  return shared.size ? shared : false;
};
const schemaContextKey = context => context ? [...context].sort().join('\\u001f') : '*';
const SKREF = new Map();  /* 노드 → 이 노드가 나온 성대·CPX 보강 주호소 스키마들 */""",
        "schema context helpers",
    )
    text = replace_once(
        text,
        "  if (src === 'skku_lrc_pbl' && ref) ref.split(' · ').forEach(z => [a, b].forEach(id => id && (SKREF.get(id) || SKREF.set(id, new Set()).get(id)).add(z)));",
        "  if (isSchemaSource(src) && ref) ref.split(' · ').forEach(z => [a, b].forEach(id => id && (SKREF.get(id) || SKREF.set(id, new Set()).get(id)).add(z)));",
        "schema reference collection",
    )
    text = replace_once(
        text,
        "const weight = e => e.fill ? 1 + (e.conf || 0) * 1.5 : e.src === 'skku_lrc_pbl' ? 12 : e.f != null ? 2 + e.f * 8 : e.src === 'hira_kcd_master' ? 6 : e.src === 'claude_draft' ? 4 : e.src === 'dismech' ? 3 : e.src === 'loinc2hpo' ? (e.pol === 'present' ? 3 : 1) : 2;",
        "const weight = e => e.fill ? 1 + (e.conf || 0) * 1.5 : isSchemaSource(e.src) ? 12 : e.f != null ? 2 + e.f * 8 : e.src === 'hira_kcd_master' ? 6 : e.src === 'claude_draft' ? 4 : e.src === 'dismech' ? 3 : e.src === 'loinc2hpo' ? (e.pol === 'present' ? 3 : 1) : 2;",
        "schema edge graph weight",
    )
    old_reach = """function reachTree(root, dir) {
  const nodes = new Set([root]), edges = new Set(), st = [root];
  while (st.length) {
    const a = st.pop();
    if (a !== root && (dir > 0 ? 'FHTD'.includes(a[0]) : 'DE'.includes(a[0]))) continue;
    ((dir > 0 ? GO : GI).get(a) || []).forEach(e => {
      if (!CAUSAL.has(e.p) || !edgeOk(e) || e.pol === 'absent' || (e.tgt && root[0] === 'D' && e.tgt !== root.slice(2))) return;  /* '보통 없음' 소견은 그래프에 잇지 않는다. GO 과정은 여러 병이 함께 써서, 질병 화면에서는 그 병명을 채운 연결만 따른다 */
      const b = dir > 0 ? e.o : e.s;
      if (b === root) return;
      edges.add(e);
      if (!nodes.has(b)) { nodes.add(b); st.push(b); }
    });
  }
  return {root, dir, nodes: [...nodes], edges: [...edges]};
}"""
    new_reach = """function reachTree(root, dir) {
  const nodes = new Set([root]), edges = new Set(), st = [[root, null]], seen = new Set([root + '|*']);
  while (st.length) {
    const [a, context] = st.pop();
    if (a !== root && (dir > 0 ? 'FHTD'.includes(a[0]) : 'DE'.includes(a[0]))) continue;
    ((dir > 0 ? GO : GI).get(a) || []).forEach(e => {
      if (!CAUSAL.has(e.p) || !edgeOk(e) || e.pol === 'absent' || (e.tgt && root[0] === 'D' && e.tgt !== root.slice(2))) return;  /* 공유 기전은 처음 들어간 주호소 문맥 안에서만 따른다 */
      const nextContext = schemaContext(context, e);
      if (nextContext === false) return;
      const b = dir > 0 ? e.o : e.s;
      if (b === root) return;
      edges.add(e); nodes.add(b);
      const state = b + '|' + schemaContextKey(nextContext);
      if (!seen.has(state)) { seen.add(state); st.push([b, nextContext]); }
    });
  }
  return {root, dir, nodes: [...nodes], edges: [...edges]};
}"""
    text = replace_once(text, old_reach, new_reach, "schema-scoped reachTree")

    text = text.replace("e.src === 'skku_lrc_pbl' ? ' s-skku' : ''", "isSchemaSource(e.src) ? ' s-skku' : ''")
    text = text.replace("e.src === 'skku_lrc_pbl' ? 1.8", "isSchemaSource(e.src) ? 1.8")

    old_edge_p = """  if (e.p === 'has_phenotype') p = (e.f != null ? e.f : e.src === 'skku_lrc_pbl' ? 0.35 : 0.4) * (e.cov != null ? e.cov : 1);  /* 스키마 연결은 '원인이 될 수 있다'라 빈도보다 약하게 */  /* 묶음 코드는 '그 소견이 있는 질병 비율 × 빈도' */
  else if (e.p === 'manifests_as') p = e.src === 'skku_lrc_pbl' ? 0.6 : e.src === 'dismech' ? 0.6 : 0.5;
  else p = e.src === 'skku_lrc_pbl' ? 0.85 : e.src === 'dismech' ? 0.8 : e.src === 'claude_draft' ? 0.7 : 0.6;"""
    new_edge_p = """  if (e.p === 'has_phenotype') p = (e.f != null ? e.f : isSchemaSource(e.src) ? 0.35 : 0.4) * (e.cov != null ? e.cov : 1);  /* 스키마 연결은 '원인이 될 수 있다'라 빈도보다 약하게 */  /* 묶음 코드는 '그 소견이 있는 질병 비율 × 빈도' */
  else if (e.p === 'manifests_as') p = isSchemaSource(e.src) ? 0.6 : e.src === 'dismech' ? 0.6 : 0.5;
  else p = isSchemaSource(e.src) ? 0.85 : e.src === 'dismech' ? 0.8 : e.src === 'claude_draft' ? 0.7 : 0.6;"""
    text = replace_once(text, old_edge_p, new_edge_p, "CPX profile weights")

    old_profile = """function profile(d) {
  if (PROF.has(d)) return PROF.get(d);
  const par = isEnt(d.slice(2)) && soleEnt(entCode(d.slice(2))) ? 'D|' + entCode(d.slice(2)) : null;  /* 병명이 하나뿐인 코드면 코드에 남은 연결도 물려받는다 (여럿이면 기전이 다를 수 있어 물려받지 않는다: 윌슨병 ≠ 멘케스병) */
  const best = new Map([[d, 1]]), from = new Map(), q = [d];
  if (par) { best.set(par, 1); q.push(par); }
  for (let it = 0; q.length && it < 20000; it++) {
    const a = q.shift(), sa = best.get(a);
    if (a !== d && a !== par && ('FHD'.includes(a[0]))) continue;
    (GO.get(a) || []).forEach(e => {
      if (!CAUSAL.has(e.p) || !edgeOk(e) || e.pol === 'absent' || e.o === d || e.o === par) return;
      const s = sa * edgeP(e);
      if (s > (best.get(e.o) || 0) + 1e-9) { best.set(e.o, s); from.set(e.o, a); q.push(e.o); }
    });
  }
  const out = new Map();
  best.forEach((s, n) => { if ('FH'.includes(n[0])) { const path = []; let c = from.get(n); while (c && c !== d && c !== par) { path.unshift(c); c = from.get(c); } out.set(n, [Math.min(0.95, Math.max(0.03, s)), path]); } });
  PROF.set(d, out);
  return out;
}"""
    new_profile = """function profile(d) {
  if (PROF.has(d)) return PROF.get(d);
  const par = isEnt(d.slice(2)) && soleEnt(entCode(d.slice(2))) ? 'D|' + entCode(d.slice(2)) : null;  /* 병명이 하나뿐인 코드면 코드에 남은 연결도 물려받는다 */
  const best = new Map(), from = new Map(), states = new Map(), q = [];
  const addRoot = n => { const key = n + '|*'; best.set(key, 1); states.set(key, {n, context: null}); q.push(key); };
  addRoot(d); if (par) addRoot(par);
  for (let it = 0; q.length && it < 20000; it++) {
    const key = q.shift(), {n: a, context} = states.get(key), sa = best.get(key);
    if (a !== d && a !== par && ('FHD'.includes(a[0]))) continue;
    (GO.get(a) || []).forEach(e => {
      if (!CAUSAL.has(e.p) || !edgeOk(e) || e.pol === 'absent' || e.o === d || e.o === par || (e.tgt && e.tgt !== d.slice(2) && (!par || e.tgt !== par.slice(2)))) return;
      const nextContext = schemaContext(context, e);
      if (nextContext === false) return;
      const nextKey = e.o + '|' + schemaContextKey(nextContext), score = sa * edgeP(e);
      if (score > (best.get(nextKey) || 0) + 1e-9) {
        best.set(nextKey, score); from.set(nextKey, key); states.set(nextKey, {n: e.o, context: nextContext}); q.push(nextKey);
      }
    });
  }
  const out = new Map();
  best.forEach((score, key) => {
    const n = states.get(key).n, previous = out.get(n);
    if (!'FH'.includes(n[0]) || (previous && previous[0] >= score)) return;
    const path = []; let cursor = from.get(key);
    while (cursor) { const step = states.get(cursor).n; if (step === d || step === par) break; path.unshift(step); cursor = from.get(cursor); }
    out.set(n, [Math.min(0.95, Math.max(0.03, score)), path]);
  });
  PROF.set(d, out);
  return out;
}"""
    return replace_once(text, old_profile, new_profile, "schema-scoped profile")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=Path)
    args = parser.parse_args()
    original = args.index.read_text(encoding="utf-8")
    if "const SCHEMA_SRCS = new Set(['skku_lrc_pbl', 'cpx_core_2026']);" in original:
        print(f"already patched {args.index}")
        return 0
    updated = patch(original)
    args.index.write_text(updated, encoding="utf-8")
    print(f"patched {args.index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
