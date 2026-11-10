from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .catalog import Catalogue, Category, TOKEN_RE

STOP = frozenset("a an and are as at be been by for from had has have in into is it its of on or that the their then there this to was were with without".split())
DIAGNOSIS_RE = re.compile(
    r"(?:^|\n)\s*(?:a|dx|imp|assessment|diagnosis|impression)\s*[:=-]\s*([^\n]+)"
    r"|\b(?:diagnosed with|working diagnosis(?: is)?|the diagnosis is|this is|assessment is)\s+([^\n.;!?]{1,180})",
    re.IGNORECASE,
)


# High-precision terminology for common outpatient diagnoses. Every target is checked
# against the selected MMS release at runtime; unsupported targets are ignored.
CLINICAL_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:p\.?\s*falciparum|falciparum)\b.{0,90}\bmalaria\b|\bmalaria\b.{0,90}\b(?:falciparum|p\.?\s*falciparum)\b", re.I | re.S), "1F40.Z", "falciparum malaria evidence"),
    (re.compile(r"\b(?:typhoid|enteric fever)\b", re.I), "1A07.Z", "typhoid or enteric fever term"),
    (re.compile(r"\b(?:vaginal thrush|vulvovaginal candidiasis|vaginal candidiasis)\b", re.I), "1F23.10", "vulvovaginal candidiasis term"),
    (re.compile(r"\b(?:chickenpox|varicella)\b", re.I), "1E90.0", "varicella term"),
    (re.compile(r"\b(?:asthma attack|acute asthma exacerbation|asthma exacerbation)\b", re.I), "CA23.30", "acute asthma exacerbation term"),
    (re.compile(r"\bcommunity[- ]acquired pneumonia\b", re.I), "CA40.Z", "community-acquired pneumonia term"),
    (re.compile(r"\btype\s*2\s*diabetes(?: mellitus)?\b", re.I), "5A11.0", "type 2 diabetes term"),
)

def _weighted_tokens(text: str) -> Counter[str]:
    counts = Counter(token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOP)
    for match in DIAGNOSIS_RE.finditer(text):
        focused = match.group(1) or match.group(2) or ""
        counts.update({token.lower(): 3 for token in TOKEN_RE.findall(focused) if token.lower() not in STOP})
    return counts


@dataclass(frozen=True)
class Ranked:
    code: str
    score: float
    evidence: tuple[str, ...]


class Coder:
    def __init__(self, catalogue: Catalogue, training_rows: list[dict[str, Any]] | None = None):
        self.catalogue = catalogue
        self.docs = list(catalogue.categories.values())
        self.df: Counter[str] = Counter()
        self.doc_tokens: dict[str, Counter[str]] = {}
        self.postings: dict[str, list[tuple[str, int, int]]] = {}
        for category in self.docs:
            terms = Counter(token for token in category.tokens if token not in STOP)
            self.doc_tokens[category.code] = terms
            length = sum(terms.values())
            for term, frequency in terms.items():
                self.df[term] += 1
                self.postings.setdefault(term, []).append((category.code, frequency, length))
        self.avg_len = sum(sum(v.values()) for v in self.doc_tokens.values()) / max(1, len(self.docs))
        self.fallback = "MG26" if "MG26" in catalogue.codes else min(catalogue.codes)
        self.training = []
        if training_rows:
            self._load_training(training_rows)

    def _load_training(self, rows: list[dict[str, Any]]) -> None:
        cleaned = []
        frequencies: Counter[str] = Counter()
        for row in rows:
            note_text = str(row.get("text") or "")
            tokens = _weighted_tokens(note_text)
            codes = [str(code).upper() for code in row.get("gold", []) if str(code).upper() in self.catalogue.codes]
            if not tokens or not codes:
                continue
            frequencies.update(tokens.keys())
            cleaned.append((str(row.get("id", "")), tokens, codes))
        count = max(1, len(cleaned))
        self.training_df = frequencies
        self.training_count = count
        for note_id, tokens, codes in cleaned:
            weights = {token: (1.0 + math.log(freq)) * math.log(1.0 + count / (1 + frequencies[token])) for token, freq in tokens.items()}
            norm = math.sqrt(sum(weight * weight for weight in weights.values())) or 1.0
            self.training.append((note_id, {token: weight / norm for token, weight in weights.items()}, codes))

    def _rank(self, text: str) -> list[Ranked]:
        query = _weighted_tokens(text)
        if not query:
            category = self.catalogue.get(self.fallback)
            return [Ranked(self.fallback, 0.0, (category.title if category else "fallback",))]
        n_docs = len(self.docs)
        scores: Counter[str] = Counter()
        matched_terms: dict[str, list[str]] = {}
        for term, qfreq in query.items():
            postings = self.postings.get(term, ())
            if not postings:
                continue
            idf = math.log(1.0 + (n_docs - self.df[term] + 0.5) / (self.df[term] + 0.5))
            for code, tf, length in postings:
                denom = tf + 1.2 * (1.0 - 0.75 + 0.75 * length / max(1.0, self.avg_len))
                scores[code] += idf * (tf * 2.2 / denom) * min(qfreq, 2)
                matched_terms.setdefault(code, []).append(term)
        results: list[Ranked] = []
        for code, score in scores.items():
            category = self.catalogue.categories[code]
            score += 0.012 * category.depth
            if category.leaf:
                score += 0.015
            results.append(Ranked(code, score, tuple(matched_terms[code][:8])))
        results.sort(key=lambda item: (-item.score, item.code))
        return results

    def _example_matches(self, text: str, exclude_id: str | None = None) -> list[tuple[float, str, list[str]]]:
        if not self.training:
            return []
        query = _weighted_tokens(text)
        if not query:
            return []
        weights = {
            token: (1.0 + math.log(freq)) * math.log(1.0 + self.training_count / (1 + self.training_df[token]))
            for token, freq in query.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in weights.values())) or 1.0
        query_weights = {token: weight / norm for token, weight in weights.items()}
        matches = []
        for note_id, vector, codes in self.training:
            if exclude_id is not None and note_id == exclude_id:
                continue
            similarity = sum(weight * vector.get(token, 0.0) for token, weight in query_weights.items())
            if similarity > 0.02:
                matches.append((similarity, note_id, codes))
        matches.sort(reverse=True, key=lambda item: item[0])
        return matches[:5]

    def predict(self, text: str, note_id: str | None = None) -> tuple[list[str], dict[str, Any]]:
        safe_text = str(text or "")[:12000]
        ranked = self._rank(safe_text)
        scores = {item.code: item.score for item in ranked}
        evidence: dict[str, list[str]] = {item.code: list(item.evidence) for item in ranked[:8]}
        sources: dict[str, str] = {item.code: "title-search" for item in ranked[:8]}
        for pattern, code, reason in CLINICAL_RULES:
            if code in self.catalogue.codes and pattern.search(safe_text):
                scores[code] = max(scores.get(code, 0.0), 100.0)
                evidence.setdefault(code, []).append(reason)
                sources[code] = "clinical-rule"
        for similarity, matched_id, matched_codes in self._example_matches(safe_text, note_id):
            for code in matched_codes:
                scores[code] = scores.get(code, 0.0) + similarity * 12.0
                evidence.setdefault(code, []).append(f"similar training note {matched_id} ({similarity:.2f})")
                sources[code] = "training-neighbor"
        ordered = sorted(scores, key=lambda code: (-scores[code], code))
        if not ordered:
            ordered = [self.fallback]
            evidence[self.fallback] = ["no lexical match; safe valid fallback"]
            sources[self.fallback] = "fallback"
        codes = ordered[:3]
        for code in codes:
            evidence.setdefault(code, [])
            sources.setdefault(code, "title-search")
        margin = scores[codes[0]] - (scores[codes[1]] if len(codes) > 1 else 0.0)
        confidence = 0.5 if scores[codes[0]] <= 0 else min(0.99, 0.45 + 0.06 * margin + 0.02 * min(5, scores[codes[0]]))
        audit = {
            "confidence": round(confidence, 3),
            "margin": round(margin, 4),
            "evidence": {code: evidence[code][:5] for code in codes},
            "sources": {code: sources[code] for code in codes},
        }
        return codes, audit

    def candidate_details(self, text: str, limit: int = 24, note_id: str | None = None) -> list[dict[str, str]]:
        codes, _ = self.predict(text, note_id)
        ranked = self._rank(str(text or "")[:12000])
        order = list(codes)
        order.extend(item.code for item in ranked if item.code not in order)
        return [
            {"code": code, "title": self.catalogue.categories[code].title}
            for code in order[:limit]
        ]

    def rerank(self, text: str, proposed: list[str]) -> list[str]:
        chosen: list[str] = []
        for value in proposed:
            code = value.strip().upper()
            if code in self.catalogue.codes and code not in chosen:
                chosen.append(code)
            if len(chosen) == 3:
                break
        fallback, _ = self.predict(text)
        chosen.extend(code for code in fallback if code not in chosen)
        return chosen[:3]
