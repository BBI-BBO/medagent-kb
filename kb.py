"""의료 agent 지식 DB 공개판을 코드·AI 에이전트에서 쓰는 도구. 파이썬 표준 라이브러리만 쓴다.

    from kb import KB
    kb = KB()                                  # 최신판 (https://bbi-bbo.github.io/medagent-kb/) — ~/.cache/medagent-kb/<판> 에 저장
    kb = KB(version="kb-2026.10.07.1")         # 판 고정 (GitHub Release 자산, 바뀌지 않음) — 실험·평가는 판을 고정해서
    kb.version, KB.versions()                  # 지금 판 · 올라온 판 목록
    kb.search("당뇨")                           # 질병 찾기
    kb.disease("E14")                          # 코드 정보와 그 아래 병명
    kb.phenotypes("E14@MONDO:0005015")         # 병명의 표현형(소견)과 출처별 빈도
    kb.findings_of("D|E14@MONDO:0005015")      # 기전을 거쳐 닿는 소견까지
    kb.rank_diseases(["HP:0002027", "HP:0002013"])   # 소견을 함께 가진 질병 (확률이 아니라 공통점)

명령줄:  python kb.py search 당뇨 · python kb.py disease E14 · python kb.py ddx HP:0002027 HP:0002013 · python kb.py versions
        판 고정은 아무 명령에나 --version=kb-2026.10.07.1
AI 함수 호출:  kb.TOOLS (JSON 스키마) + kb.call(name, args) — README '외부 AI가 쓰는 법' 참고.

화면(viz/db_viewer)이 그래프를 만드는 규칙을 그대로 옮겼다: 모든 간선은 인과 방향(원인 → 결과),
노드 ID 는 '종류|값' (D 질병·병명, F 소견(성균관의대), H 소견(HPO), M 기전(성균관의대), X 기전(DisMech),
C 기전(AI 초안), G 유전자, P GO 과정, E 원인·노출, A 검사 묶음, T LOINC 검사).
공개판에는 HPOA(phenotype.hpoa)에서만 온 연결이 없다. 'AI' 연결은 의학과 검수 전이다.
"""
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

BASE = "https://bbi-bbo.github.io/medagent-kb/"
RELEASE = "https://github.com/BBI-BBO/medagent-kb/releases/download/{v}/"
API = "https://api.github.com/repos/BBI-BBO/medagent-kb/releases"
FORMAT = 1  # 이 도구가 아는 자료 구조 판. 공개판의 format 이 더 크면 kb.py 를 새로 받으라고 알린다
HEAD = {"data.js": "window.DB = ", "pheno.js": "window.DB.tables.entity_phenotype.rows = ",
        "fill.js": "window.DB.fill = ", "search.js": "window.DB_ALIAS = "}
CAUSAL = {"causes", "manifests_as", "constitutes", "has_phenotype", "involved_in"}
KIND = {"D": "질병", "F": "소견 (성균관의대)", "H": "소견 (HPO)", "M": "기전 (성균관의대)", "X": "기전 (DisMech)",
        "C": "기전 (AI 초안, 검수 전)", "G": "유전자 (Orphanet)", "P": "생물학적 과정 (GO)", "E": "원인·노출",
        "A": "검사 묶음 (LOINC 분석물)", "T": "검사 (LOINC)"}
PRED_KO = {"causes": "일으킴", "manifests_as": "나타남", "constitutes": "이룸", "has_phenotype": "표현형",
           "indicates": "검사 판정", "subclass_of": "종류", "involved_in": "관여"}
CONF_KO = ["가설", "낮음", "중간", "높음"]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "medagent-kb/1"})
    return urllib.request.urlopen(req, timeout=300).read().decode("utf-8")


def _load(name, base, cache):
    """공개판 파일 하나를 읽어 JSON 으로. base 가 폴더 경로면 그 폴더에서, 주소면 받아서 cache 에 둔다."""
    if not base.startswith("http"):
        s = open(os.path.join(base, name), encoding="utf-8").read()
    else:
        path = os.path.join(cache, name) if cache else None
        if path and os.path.exists(path):
            s = open(path, encoding="utf-8").read()
        else:
            s = _get(base + name)
            if path:
                os.makedirs(cache, exist_ok=True)
                open(path, "w", encoding="utf-8").write(s)
    head = HEAD[name]
    if not s.startswith(head):
        raise ValueError(f"{name}: 형식이 다릅니다 ({s[:40]!r})")
    return json.loads(s[len(head):].rstrip().rstrip(";"))


class KB:
    def __init__(self, version=None, base=None, cache=os.path.expanduser("~/.cache/medagent-kb"), refresh=False):
        """version: None = 최신판, 'kb-YYYY.MM.DD.N' = 그 판 고정 (GitHub Release). base: 내려받은 폴더나 다른 주소를 직접 줄 때.
        캐시는 판마다 따로 둔다 (cache/<판>/). refresh=True 면 그 판 캐시를 지우고 다시 받는다."""
        if base is None:
            if version is None:  # 최신판: 작은 version.json 으로 지금 판을 알아내고, 그 판의 캐시를 쓴다
                version = json.loads(_get(BASE + "version.json?nocache=1"))["version"]
                base = BASE
            else:
                base = RELEASE.format(v=version)
        cache = os.path.join(cache, version or "local") if cache and base.startswith("http") else None
        if refresh and cache and os.path.isdir(cache):
            for f in HEAD:
                p = os.path.join(cache, f)
                if os.path.exists(p):
                    os.remove(p)
        D = _load("data.js", base, cache)
        D["tables"]["entity_phenotype"]["rows"] = _load("pheno.js", base, cache)
        self.D, self.fill, self.alias = D, _load("fill.js", base, cache), _load("search.js", base, cache)
        self.generated_at, self.public = D.get("generated_at"), bool(D.get("public"))
        self.version, self.format = D.get("version") or version, D.get("format", 1)
        if self.format > FORMAT:
            print(f"[medagent-kb] 자료 구조 판 {self.format} 이 이 kb.py({FORMAT})보다 새 판입니다. kb.py 를 새로 받으세요.", file=sys.stderr)
        self._build()

    @staticmethod
    def versions():
        """올라온 판 목록 (새 판부터): [{version, date, notes}]"""
        return [{"version": r["tag_name"], "date": r["published_at"], "notes": r["body"]} for r in json.loads(_get(API + "?per_page=100"))]

    # ── 표 ──
    def table(self, name):
        """DB 표를 dict 목록으로. 큰 표(term·assertion 등)는 공개판에 미리보기 300행만 있다 — self.D['tables'][name]['total'] 이 실제 행 수."""
        t = self.D["tables"][name]
        cols = [c["name"] for c in t["columns"]]
        return [dict(zip(cols, r)) for r in t["rows"]]

    def tables(self):
        """표 이름 → {행 수(DB), 공개판에 든 행 수, 설명}"""
        return {n: {"total": t["total"], "rows": len(t["rows"]), "comment": t.get("comment")} for n, t in self.D["tables"].items()}

    # ── 그래프 만들기 (화면과 같은 규칙) ──
    def _build(self):
        D = self.D
        self.DIS = {r["kcd"]: r for r in self.table("disease")}
        # 병명: KCD 4자리 아래 MONDO 질병. 한국어 이름이 코드 이름과 똑같은 병명(담관염 = K83.0 담관염)은 코드와 같은 병이라
        # 그래프에서 코드 노드 하나로 합친다 (SAME). ENTS 에는 이름이 다른 병명만 둔다. 화면과 같은 규칙
        self.ENT, self.ENTS, self.SAME, self.ENT_SAME = {}, defaultdict(list), set(), defaultdict(list)
        norm = lambda z: re.sub(r"\s+", "", z or "")
        for r in self.table("kcd_entity"):
            k = r["kcd"] + "@" + r["mondo_id"]
            self.ENT[k] = {"kcd": r["kcd"], "mondo": r["mondo_id"], "ko": r["name_ko"], "en": r["name_en"],
                           "name_src": r["name_src"], "method": r["method"]}
            if norm(r["name_ko"]) == norm(self.DIS.get(r["kcd"], {}).get("name_ko")):
                self.SAME.add(k)
                self.ENT_SAME[r["kcd"]].append(k)
            else:
                self.ENTS[r["kcd"]].append(k)
        self.FND = {r["id"]: r for r in self.table("finding")}
        self.MEC = {r["id"]: r for r in self.table("mechanism")}
        self.HPO2F = {r["hpo_id"]: r["id"] for r in self.FND.values() if r.get("hpo_id")}
        self.MONDO2KCD = {}
        for r in self.table("kcd_ext"):
            m, k = r["ext_id"], r["kcd"][:4]
            if m not in self.MONDO2KCD or r["method"] == "icd10_xref":
                self.MONDO2KCD[m] = k
        self.HL, self.LOINC, self.ANKO = D.get("hpo_labels", {}), D.get("loinc", {}), D.get("analyte_ko", {})
        # HPO 동의어(EXACT)와 부모 목록: 찾기는 동의어로도, 후보 순위는 하위 용어까지 맞게 센다 (화면 진료 탭과 같은 규칙)
        self.HSYN, self.HPAR = D.get("hpo_syn", {}), D.get("hpo_tree", {})
        self.HCH = defaultdict(list)
        for c, ps in self.HPAR.items():
            for p_ in ps:
                self.HCH[p_].append(c)
        self._desc = {}
        dm = D.get("dismech", {})
        self.DMm = {str(r[0]): {"mondo": r[1], "en": r[2], "ko": r[3], "stage": r[4], "depth": r[5], "go": r[6] or [], "gm": r[7] or []} for r in dm.get("mechs", [])}
        self.GOL, self.FN, self.GOKO = dm.get("go", {}), self.fill.get("nodes", {}), self.fill.get("go_ko", {})
        self.GO, self.GI, self.SKREF, self.CO = defaultdict(list), defaultdict(list), defaultdict(set), defaultdict(list)

        def add(s, p, o, **a):
            if not s or not o or s == o:
                return
            e = {"s": s, "p": p, "o": o, **a}
            self.GO[s].append(e)
            self.GI[o].append(e)

        agg = {}
        for s, p, o, src, q, pol, ref, ev in D.get("kg", []):
            if p == "same_as":
                continue
            a, b = self.nid(s), self.nid(o)
            if p == "indicates" and a and a[0] == "T":  # LOINC 코드 여러 개를 검사 묶음(분석물)으로 모은다
                c = a[2:]
                an = "A|" + ((self.LOINC.get(c) or [None] * 8)[7] or c)
                g = agg.setdefault((an, b, pol), {"src": src, "qs": set(), "codes": set()})
                if q:
                    g["qs"].add(q)
                g["codes"].add(c)
                continue
            if src == "skku_lrc_pbl" and ref:
                for z in ref.split(" · "):
                    for i in (a, b):
                        if i:
                            self.SKREF[i].add(z)
            add(a, p, b, src=src, q=q, pol=pol, ref=ref, ev=ev)
        for (an, b, pol), g in agg.items():
            add(an, "indicates", b, src=g["src"], pol=pol, q="·".join(sorted(g["qs"])), codes=sorted(g["codes"]))
        ep = self.D["tables"]["entity_phenotype"]
        cols = [c["name"] for c in ep["columns"]]
        for row in ep["rows"]:
            r = dict(zip(cols, row))
            d, h = "D|" + self.canon(r["kcd"] + "@" + r["mondo_id"]), r["hpo_id"]
            fs = [r[c] for c in ("f_dismech", "f_orphadata", "f_hpoa") if r.get(c) is not None]
            a = dict(src=",".join(r["sources"] or []), f=max(fs) if fs else None, depth=r["min_depth"], deny=r.get("deny_only"),
                     diagnostic=r.get("diagnostic"), freq={k[2:]: r[k] for k in ("f_dismech", "f_orphadata", "f_hpoa") if r.get(k) is not None})
            if not str(h).startswith("HP:"):  # 표현형 자리에 질병이 적힌 것: 동반 보고 (방향을 알 수 없어 인과로 잇지 않음)
                self.CO[d].append({**a, "other": self.nid(h) or h, "term": h})
                continue
            add(d, "has_phenotype", self.nid(h), **a)
        DMP = dm.get("pheno", {})
        term = lambda i: bool(DMP.get(str(i)) and DMP[str(i)][1])
        for i, (hp, t) in DMP.items():
            if not t:
                add("X|" + i, "manifests_as", self.nid(hp), src="dismech", q="같은 이름의 표현형")
        for mid, m in self.DMm.items():
            for k0, e0, d in dm.get("mondo2kcd", {}).get(m["mondo"], []):
                k = self.canon(k0 + "@" + e0)
                if term(mid):
                    if m["depth"] == 1:
                        add("D|" + k, "has_phenotype", self.nid(DMP[mid][0]), src="dismech", depth=d)
                    continue
                if m["stage"] == "etiology":
                    add("X|" + mid, "constitutes", "D|" + k, src="dismech", q="병인", depth=d)
                elif m["depth"] == 1:
                    add("D|" + k, "causes", "X|" + mid, src="dismech", depth=d)
        for k, v in self.ENT.items():
            if k not in self.SAME:
                add("D|" + k, "subclass_of", "D|" + v["kcd"], src="mondo", q="KCD 분류")
        for a, bm, bh in dm.get("edges", []):
            a = str(a)
            if bm is not None:
                if term(bm):
                    add("X|" + a, "manifests_as", self.nid(DMP[str(bm)][0]), src="dismech")
                else:
                    add("X|" + a, "causes", "X|" + str(bm), src="dismech")
            if bh:
                add("X|" + a, "manifests_as", self.nid(bh), src="dismech")
        for s, p, o, src, q, conf, basis, depth, tgt, cd, cr, vd in self.fill.get("edges", []):
            add(self.nid(s), p, self.nid(o), src=src, q=q, conf=conf, basis=basis or (q if src == "orphanet_go" else ""),
                depth=depth or 0, fill="B" if src == "claude_mech" else "A", tgt=tgt and self.canon(tgt), review=vd)
        self._fc = {}

    def canon(self, k):
        """병명 키 → 그래프 노드 키 (코드 이름과 같은 병명은 그 코드)"""
        return self.ENT[k]["kcd"] if k in self.SAME else k

    def hpo_of(self, node):
        """노드 ID → HPO ID (F 노드는 소견 사전의 hpo_id)"""
        return node[2:] if node.startswith("H|") else (self.FND.get(node[2:], {}).get("hpo_id") if node.startswith("F|") else None)

    def descendants(self, node):
        """노드와 그 하위 HPO 용어 노드들 (그래프에 있는 것만). '빈맥' → 동성 빈맥·심실 빈맥 …"""
        if node in self._desc:
            return self._desc[node]
        out, h = {node}, self.hpo_of(node)
        if h:
            st, seen = [h], {h}
            while st:
                for c in self.HCH.get(st.pop(), []):
                    if c not in seen:
                        seen.add(c)
                        st.append(c)
                        n = "F|" + self.HPO2F[c] if c in self.HPO2F else "H|" + c
                        if n in self.GI:
                            out.add(n)
        self._desc[node] = out
        return out

    def nid(self, raw):
        """원본 ID(KCD:E14, MONDO:…, HP:…, SKKU:F:…, DM:…, HGNC:…, GO:…, CDM:…, LOINC:…) → 그래프 노드 ID"""
        if not raw:
            return None
        if raw.startswith("D|"):
            return "D|" + self.canon(raw[2:])
        ns, _, v = raw.partition(":")
        if ns == "KCD":
            return "D|" + v.replace(".", "")[:4]
        if ns == "MONDO":
            k = self.MONDO2KCD.get(raw)
            return ("D|" + (self.canon(k + "@" + raw) if k + "@" + raw in self.ENT else k)) if k else None
        if ns == "HP":
            return "F|" + self.HPO2F[raw] if raw in self.HPO2F else "H|" + raw
        if ns == "SKKU":
            k, _, w = v.partition(":")
            return {"F": "F|", "M": "M|", "X": "E|", "P": "F|"}.get(k, "F|") + w
        return {"FND": "F|" + v, "MEC": "M|" + v, "DM": "X|" + v, "HGNC": "G|" + raw, "GENE": "G|" + raw,
                "GO": "P|" + raw, "CDM": "C|" + v, "EXP": "E|" + v, "LOINC": "T|" + v}.get(ns)

    def node(self, i):
        """노드 ID → 이름(한국어)·영어·종류. 'E14' 처럼 접두사가 없으면 질병으로 본다."""
        i = self._id(i)
        k, v = i[0], i[2:]
        ko = en = ""
        if k == "D":
            e = self.ENT.get(v)
            if e:
                ko, en = e["ko"], e["en"]
            elif v in self.DIS:
                ko, en = self.DIS[v]["name_ko"], self.DIS[v]["name_en"]
        elif k == "F" and v in self.FND:
            ko, en = self.FND[v]["name_ko"], self.FND[v].get("name_en") or ""
        elif k == "H":
            lab = self.HL.get(v) or [v, None]
            ko, en = lab[1] or lab[0], lab[0]
        elif k == "M" and v in self.MEC:
            ko, en = self.MEC[v]["name_ko"], self.MEC[v].get("name_en") or ""
        elif k == "X" and v in self.DMm:
            ko, en = self.DMm[v]["ko"] or self.DMm[v]["en"], self.DMm[v]["en"]
        elif k == "T" and v in self.LOINC:
            ko, en = self.LOINC[v][1] or self.LOINC[v][0], self.LOINC[v][0]
        elif k == "A":
            ko, en = self.ANKO.get(v, v), v
        elif k == "E":
            ko = self.D.get("node_labels", {}).get("EXP:" + v, v)
        elif k == "G":
            n = self.FN.get(v) or []
            ko, en = (n[3] if len(n) > 3 else None) or v, (n[2] if len(n) > 2 else "") or ""
        elif k == "P":
            n = self.FN.get(v) or []
            ko = self.GOKO.get(v) or (self.GOL.get(v) or [None, None])[1] or (n[2] if len(n) > 2 else None) or v
            en = (self.GOL.get(v) or [""])[0] or ""
        elif k == "C":
            n = self.FN.get("CDM:" + v) or []
            ko, en = (n[1] if len(n) > 1 else None) or v, (n[2] if len(n) > 2 else "") or ""
        return {"id": i, "name": ko or v, "en": en if en != ko else "", "kind": KIND.get(k, k)}

    def _id(self, i):
        i = str(i).strip()
        if len(i) > 1 and i[1] == "|":
            return "D|" + self.canon(i[2:]) if i[0] == "D" else i
        if i.startswith("HP:"):
            return self.nid(i)
        if "@" in i or re.match(r"^[A-Z]\d\d", i):
            return "D|" + self.canon(i.replace(".", "") if "@" not in i else i.split("@")[0].replace(".", "") + "@" + i.split("@", 1)[1])
        return i

    def _ok(self, e, sub=True, fill=True, hypotheses=False):
        """화면 기본 필터와 같음: 하위 질병 포함, AI 기전·유전자 연결 포함, 신뢰도 '가설'은 뺌"""
        if e.get("fill") and (not fill or (not e.get("conf") and not hypotheses)):
            return False
        return sub or not e.get("depth")

    def _edge(self, e):
        out = {"from": self.node(e["s"])["name"], "from_id": e["s"], "relation": PRED_KO.get(e["p"], e["p"]), "predicate": e["p"],
               "to": self.node(e["o"])["name"], "to_id": e["o"], "source": e.get("src")}
        for k in ("q", "f", "depth", "pol", "codes", "ref"):
            if e.get(k) not in (None, "", []):
                out[{"q": "qualifier", "f": "freq", "pol": "polarity", "ref": "schema"}.get(k, k)] = e[k]
        if e.get("fill"):
            out["ai_or_auto"] = {"B": "AI 기전 초안 (검수 전)", "A": "유전자 자동 연결"}[e["fill"]]
            out["confidence"] = CONF_KO[e.get("conf") or 0]
        return out

    # ── 찾기·조회 ──
    def search(self, text, kind="disease", limit=20):
        """이름·코드로 찾기. kind: disease(KCD 코드·병명·별칭) · finding(소견·HPO) · mechanism · test"""
        q = text.strip().lower()
        has = lambda *xs: any(x and q in str(x).lower() for x in xs)
        out = []
        if kind == "disease":
            for k, r in self.DIS.items():
                if len(k) > 4:
                    continue
                hit = next((a for a in self.alias.get(k, []) if has(a[0])), None)
                if has(k, r["name_ko"], r["name_en"]) or hit or any(has(self.ENT[e]["ko"], self.ENT[e]["en"]) for e in self.ENTS.get(k, [])):
                    out.append({"id": "D|" + k, "code": k, "name": r["name_ko"], "en": r["name_en"],
                                "names": [{"id": "D|" + e, "name": self.ENT[e]["ko"], "en": self.ENT[e]["en"]} for e in self.ENTS.get(k, [])],
                                **({"matched_alias": hit[0]} if hit else {})})
            direct = lambda r: has(r["code"], r["name"], r["en"]) or any(has(n["name"], n["en"]) for n in r["names"])
            out.sort(key=lambda r: (r["code"].lower() != q.replace(".", "").lower(), not direct(r), -len(self.GO.get(r["id"], [])), r["code"]))  # 코드 일치 → 이름 일치 → 별칭
        elif kind == "finding":
            for f, r in self.FND.items():
                syn = self.HSYN.get(r.get("hpo_id") or "", [])
                if has(f, r["name_ko"], r.get("name_en"), r.get("hpo_id")) or has(*syn):
                    out.append({"id": "F|" + f, "name": r["name_ko"], "en": r.get("name_en"), "hpo": r.get("hpo_id"),
                                **({} if has(f, r["name_ko"], r.get("name_en"), r.get("hpo_id")) else {"matched_synonym": next(z for z in syn if has(z))})})
            for h, lab in self.HL.items():
                syn = self.HSYN.get(h, [])
                if h not in self.HPO2F and (has(h, *lab) or has(*syn)):
                    out.append({"id": "H|" + h, "name": lab[1] or lab[0], "en": lab[0], "hpo": h,
                                **({} if has(h, *lab) else {"matched_synonym": next(z for z in syn if has(z))})})
            out.sort(key=lambda r: ("matched_synonym" in r, -len(self.GI.get(r["id"], []))))  # 이름으로 맞은 것 먼저
        elif kind == "mechanism":
            for m, r in self.MEC.items():
                if has(m, r["name_ko"], r.get("name_en")):
                    out.append({"id": "M|" + m, "name": r["name_ko"], "en": r.get("name_en")})
            for m, r in self.DMm.items():
                if has(r["ko"], r["en"]):
                    out.append({"id": "X|" + m, "name": r["ko"] or r["en"], "en": r["en"], "disease": r["mondo"]})
        elif kind == "test":
            for a in {e["s"] for es in self.GO.values() for e in es if e["s"][0] == "A"}:
                if has(a[2:], self.ANKO.get(a[2:])):
                    out.append({"id": a, "name": self.ANKO.get(a[2:], a[2:]), "en": a[2:]})
        return out[:limit]

    def disease(self, code):
        """KCD 코드(E14, E83.0) 또는 병명 키(E830@MONDO:0010200) → 이름·상위·하위·병명·주호소 스키마"""
        i = self._id(code)
        k = i[2:].split("@")[0]
        r = self.DIS.get(k, {})
        kids = [d for d, x in self.DIS.items() if x.get("parent") == k and len(d) <= 4]
        return {"id": i, "code": k, "name": r.get("name_ko"), "en": r.get("name_en"), "chapter": r.get("chapter"),
                "parent": r.get("parent"), "children": kids, "inclusions": r.get("inclusions_ko") or [],
                "names": [{"id": "D|" + e, **{x: self.ENT[e][x] for x in ("ko", "en", "mondo", "name_src", "method")}} for e in self.ENTS.get(k, [])],
                "same_as_code": [{x: self.ENT[e][x] for x in ("ko", "en", "mondo", "name_src", "method")} for e in self.ENT_SAME.get(k, [])],  # 코드와 같은 병명 (그래프에서는 코드 노드)
                "schemas": sorted(self.SKREF.get(i, set()) | self.SKREF.get("D|" + k, set()))}

    def phenotypes(self, name_key, sub=True):
        """병명(코드@MONDO)의 HPO 표현형: 출처별 빈도(0~1), 진단적 여부, 하위 질병에서 왔는지(depth>0). 빈도 높은 순"""
        d = self._id(name_key)
        rows = [e for e in self.GO.get(d, []) if e["p"] == "has_phenotype" and (sub or not e.get("depth"))]
        out = [{"id": e["o"], **{k: v for k, v in self.node(e["o"]).items() if k != "id"}, "freq": e.get("f"), "freq_by_source": e.get("freq"),
                "sources": e.get("src"), "diagnostic": e.get("diagnostic"), "from_subtype": bool(e.get("depth"))} for e in rows]
        return sorted(out, key=lambda r: -(r["freq"] or 0))

    def edges(self, node, direction="out", **flt):
        """노드의 나가는(out: 이 노드가 원인)·들어오는(in: 이 노드가 결과) 연결"""
        i = self._id(node)
        es = (self.GO if direction == "out" else self.GI).get(i, [])
        return [self._edge(e) for e in es if self._ok(e, **flt)]

    def reach(self, node, direction=1, **flt):
        """화면 그래프와 같은 인과 트리. direction=1: 결과 쪽(기전 사슬 → 소견), -1: 원인 쪽(기전 ← 질병·노출).
        소견·검사·다른 질병에서는 더 가지 않는다(정방향), 역방향은 질병·노출에서 멈춘다."""
        root = self._id(node)
        nodes, edges, st = {root}, [], [root]
        while st:
            a = st.pop()
            if a != root and (a[0] in "FHTD" if direction > 0 else a[0] in "DE"):
                continue
            for e in (self.GO if direction > 0 else self.GI).get(a, []):
                if e["p"] not in CAUSAL or not self._ok(e, **flt) or e.get("pol") == "absent" or (e.get("tgt") and root[0] == "D" and e["tgt"] != root[2:]):
                    continue
                b = e["o"] if direction > 0 else e["s"]
                if b == root:
                    continue
                edges.append(e)
                if b not in nodes:
                    nodes.add(b)
                    st.append(b)
        return {"root": self.node(root), "nodes": [self.node(n) for n in nodes if n != root], "edges": [self._edge(e) for e in edges]}

    def findings_of(self, disease):
        """질병(코드·병명)에서 기전을 거쳐 닿는 소견 ID 집합 (화면 목록의 '소견 N'과 같은 수)"""
        i = self._id(disease)
        k = i[2:]
        if k in self._fc:
            return self._fc[k]
        ids = [k] if "@" in k else [k] + self.ENTS.get(k, [])
        out = set()
        for z in ids:
            for n in self._reach_ids("D|" + z):
                if n[0] in "FH":
                    out.add(n)
        self._fc[k] = out
        return out

    def _reach_ids(self, root):
        nodes, st = {root}, [root]
        while st:
            a = st.pop()
            if a != root and a[0] in "FHTD":
                continue
            for e in self.GO.get(a, []):
                if e["p"] in CAUSAL and self._ok(e) and e.get("pol") != "absent" and not (e.get("tgt") and e["tgt"] != root[2:]) and e["o"] not in nodes:
                    nodes.add(e["o"])
                    st.append(e["o"])
        return nodes

    def causes_of(self, finding, limit=50):
        """소견을 일으킬 수 있는 질병·노출 (원인 쪽 트리의 잎). 감별 후보 목록"""
        t = self.reach(finding, -1)
        leaves = [n for n in t["nodes"] if n["id"][0] in "DE"]
        return leaves[:limit]

    def tests_for(self, finding):
        """소견을 판정하는 검사 (LOINC2HPO): 검사 묶음 → 결과(H·L·POS…) → 이 소견"""
        i = self._id(finding)
        return [self._edge(e) for e in self.GI.get(i, []) if e["p"] == "indicates"]

    def rank_diseases(self, present, absent=(), limit=20):
        """'있음' 소견을 많이 함께 가진 병명 순 (확률이 아니라 공통점). '없음' 소견이 그 병명 목록에 있으면 어긋남으로 센다.
        넣은 소견의 하위 HPO 용어(예: 빈맥 → 동성 빈맥)를 가진 병도 맞음으로 센다.
        present·absent: HPO ID(HP:…) 또는 노드 ID(F|…·H|…)"""
        P = {self._id(x): self.descendants(self._id(x)) for x in present}  # 하위 용어(더 구체적인 소견)를 가진 병도 맞음
        A = {self._id(x): self.descendants(self._id(x)) for x in absent}
        # 후보: 이름이 다른 병명 + 코드 자체(병명이 없거나, 코드와 같은 병명을 합친 코드). 코드는 그 코드 노드에서 닿는 소견만 센다
        cands = [k for k in self.ENT if k not in self.SAME] + [k for k in self.DIS if len(k) <= 4 and (not self.ENTS.get(k) or k in self.ENT_SAME) and self.GO.get("D|" + k)]
        out = []
        for k in cands:
            fs = self.findings_of("D|" + k) if "@" in k else {n for n in self._reach_ids("D|" + k) if n[0] in "FH"}
            hit = {p for p, ds in P.items() if fs & ds}
            miss = {a for a, ds in A.items() if fs & ds}
            if hit:
                out.append({"id": "D|" + k, "name": self.node("D|" + k)["name"], "matched": len(hit), "conflicts": len(miss),
                            "matched_findings": [self.node(x)["name"] for x in hit], "conflicting": [self.node(x)["name"] for x in miss],
                            "findings_total": len(fs)})
        out.sort(key=lambda r: (-r["matched"], r["conflicts"], r["findings_total"]))
        return out[:limit]

    # ── AI 함수 호출용 ──
    TOOLS = [
        {"name": "search", "description": "질병(KCD 코드·병명)·소견(HPO)·기전·검사를 이름이나 코드로 찾는다. 결과의 id 를 다른 함수에 넘긴다.",
         "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "kind": {"type": "string", "enum": ["disease", "finding", "mechanism", "test"]},
                                                           "limit": {"type": "integer"}}, "required": ["text"]}},
        {"name": "disease", "description": "KCD 코드나 병명 키의 이름·상위·하위 코드·개별 병명(MONDO)·성균관의대 주호소 스키마",
         "input_schema": {"type": "object", "properties": {"code": {"type": "string", "description": "예: E14, E83.0, E830@MONDO:0010200"}}, "required": ["code"]}},
        {"name": "phenotypes", "description": "병명의 HPO 표현형(소견)과 출처별 빈도. 병명 키는 disease 의 names[].id",
         "input_schema": {"type": "object", "properties": {"name_key": {"type": "string"}}, "required": ["name_key"]}},
        {"name": "reach", "description": "노드에서 인과 방향 그래프. direction 1 = 결과 쪽(질병 → 기전 → 소견), -1 = 원인 쪽(소견 ← 기전 ← 질병)",
         "input_schema": {"type": "object", "properties": {"node": {"type": "string"}, "direction": {"type": "integer", "enum": [1, -1]}}, "required": ["node"]}},
        {"name": "rank_diseases", "description": "있음·없음 소견으로 공통점이 많은 병명 순위 (확률 아님)",
         "input_schema": {"type": "object", "properties": {"present": {"type": "array", "items": {"type": "string"}}, "absent": {"type": "array", "items": {"type": "string"}},
                                                           "limit": {"type": "integer"}}, "required": ["present"]}},
        {"name": "tests_for", "description": "소견을 판정하는 검사(LOINC 묶음)와 결과값",
         "input_schema": {"type": "object", "properties": {"finding": {"type": "string"}}, "required": ["finding"]}},
    ]

    def call(self, name, args):
        """AI 의 함수 호출을 실행한다: kb.call('search', {'text': '당뇨'})"""
        if name not in {t["name"] for t in self.TOOLS}:
            raise ValueError(f"없는 함수: {name}")
        return getattr(self, name)(**args)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    ver = next((a.split("=", 1)[1] for a in argv if a.startswith("--version=")), None)
    argv = [a for a in argv if not a.startswith("--version=")]
    if argv[1] == "versions":
        print(json.dumps(KB.versions(), ensure_ascii=False, indent=1))
        return
    kb = KB(version=ver)
    cmd, rest = argv[1], argv[2:]
    if cmd == "search":
        kind = rest[1] if len(rest) > 1 else "disease"
        res = kb.search(rest[0], kind)
    elif cmd == "disease":
        res = kb.disease(rest[0])
    elif cmd == "pheno":
        res = kb.phenotypes(rest[0])[:30]
    elif cmd == "reach":
        res = kb.reach(rest[0], int(rest[1]) if len(rest) > 1 else 1)
    elif cmd == "ddx":
        res = kb.rank_diseases([x for x in rest if not x.startswith("-")], [x[1:] for x in rest if x.startswith("-")])
    elif cmd == "tests":
        res = kb.tests_for(rest[0])
    else:
        sys.exit(f"모르는 명령: {cmd} (search · disease · pheno · reach · ddx · tests)")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv)
