from __future__ import annotations

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .catalog import Catalogue, TOKEN_RE, normalize_code
from .lexicon import canonical_tokens

STOP = frozenset(
    "a an and are as at be been by for from had has have in into is it its of on or that the their then there this to was were with without".split()
)
DIAGNOSIS_RE = re.compile(
    r"(?:^|\n)\s*(?:a|dx|imp|assessment|diagnosis|impression)\s*[:=-]\s*([^\n]+)"
    r"|\b(?:diagnosed with|working diagnosis(?: is)?|the diagnosis is|this is|assessment is)\s+([^\n.;!?]{1,180})",
    re.IGNORECASE,
)
NEGATORS = frozenset(
    "no not without denies deny denied absent negative nil none never nor excluded ruled unlikely free".split()
)
NEGATION_WINDOW = 2
SCOPE_BREAKERS = frozenset("vs versus against for about due per with of to".split())
POST_NEGATORS = frozenset("excluded ruled negative absent neg".split())
TOP_K = 64
# ICD-11 chapters 21 (symptoms/signs/findings), 23 (factors influencing health)
# and 24 (assessment of health) describe findings, not the visit diagnosis. They stay
# as candidates but must not outrank a documented disease code.
FINDING_CHAPTERS = frozenset({"21", "23", "24"})
FINDING_DISCOUNT = 0.55
# Chapter 26 holds traditional-medicine patterns (TM1/TM2). They are supplementary
# categories, not claimable outpatient diagnoses, so they should not win a slot.
TRADITIONAL_MEDICINE_CHAPTER = "26"
TRADITIONAL_MEDICINE_DISCOUNT = 0.15

# Curated high-precision outpatient terminology. Each target is checked against the
# loaded MMS release, so a rule can never emit a code outside the catalogue.
CLINICAL_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:p\.?\s*falciparum|falciparum)\b.{0,90}\bmalaria\b|\bmalaria\b.{0,90}\b(?:falciparum|p\.?\s*falciparum)\b", re.I | re.S), "1F40.Z", "falciparum malaria evidence"),
    (re.compile(r"\b(?:typhoid|enteric fever)\b", re.I), "1A07.Z", "typhoid or enteric fever term"),
    (re.compile(r"\b(?:vaginal thrush|vulvovaginal candidiasis|vaginal candidiasis)\b", re.I), "1F23.10", "vulvovaginal candidiasis term"),
    (re.compile(r"\b(?:chickenpox|varicella)\b", re.I), "1E90.0", "varicella term"),
    (re.compile(r"\b(?:asthma attack|acute asthma exacerbation|asthma exacerbation)\b", re.I), "CA23.30", "acute asthma exacerbation term"),
    (re.compile(r"\bcommunity[- ]acquired pneumonia\b", re.I), "CA40.Z", "community-acquired pneumonia term"),
    (re.compile(r"\btype\s*2\s*diabetes(?:\s*mellitus)?\b|\bT2DM\b|\bDM\s*2\b", re.I), "5A11", "type 2 diabetes term"),
    (re.compile(r"\bimpaired fasting glucose\b|\braised fasting (?:glucose|sugar)\b", re.I), "5A40.0", "impaired fasting glucose term"),
    (re.compile(r"\bpre-?diabetes\b|\bintermediate hyperglycaemia\b", re.I), "5A40", "intermediate hyperglycaemia term"),
)


def _is_negated(prefix: str) -> bool:
    """True when a short trailing window of the note negates the upcoming finding."""
    window = re.split(r"[.;:\n]", prefix[-80:])[-1]
    tokens = TOKEN_RE.findall(window.lower())[-NEGATION_WINDOW:]
    if any(token in SCOPE_BREAKERS for token in tokens):
        return False
    return any(token in NEGATORS for token in tokens)


def _body_counts(raw: list[str], use_post_negation: bool = True) -> Counter[str]:
    """Token counts with negated findings dropped. Takes pre-tokenised text."""
    counts: Counter[str] = Counter()
    for index, token in enumerate(raw):
        if token in STOP:
            continue
        left = raw[max(0, index - NEGATION_WINDOW):index]
        if any(prev in NEGATORS for prev in left) and not any(prev in SCOPE_BREAKERS for prev in left):
            continue
        # Post-negation: "malaria excluded", "TB ruled out", "pregnancy test negative".
        right = raw[index + 1:index + 1 + NEGATION_WINDOW]
        if use_post_negation and any(next_token in POST_NEGATORS for next_token in right):
            continue
        counts[token] += 1
    return counts


def _anchor_counts(text: str, anchor_weight: float, use_lexicon: bool = True) -> Counter[str]:
    counts: Counter[str] = Counter()
    for match in DIAGNOSIS_RE.finditer(text):
        focused = match.group(1) or match.group(2) or ""
        focus_tokens = canonical_tokens(focused) if use_lexicon else [t.lower() for t in TOKEN_RE.findall(focused)]
        for token in focus_tokens:
            if token not in STOP:
                counts[token] += anchor_weight
    return counts


def _query_tokens(text: str, anchor_weight: float = 3.0, use_lexicon: bool = True,
                  use_post_negation: bool = True) -> Counter[str]:
    """Token counts with the assessment block boosted and negated findings dropped."""
    raw = canonical_tokens(text) if use_lexicon else [token.lower() for token in TOKEN_RE.findall(text)]
    counts = _body_counts(raw, use_post_negation)
    counts.update(_anchor_counts(text, anchor_weight, use_lexicon))
    return counts


def _clip(text: str, head: int = 6000, tail: int = 4000) -> str:
    """Keep the start, the assessment, and the tail instead of blindly truncating."""
    if len(text) <= head + tail:
        return text
    spans = [match.group(1) or match.group(2) or "" for match in DIAGNOSIS_RE.finditer(text)]
    diagnosis = "\n".join(span.strip() for span in spans if span.strip())[:2000]
    return "\n".join(part for part in (text[:head], diagnosis, text[-tail:]) if part)


@dataclass(frozen=True)
class Ranked:
    code: str
    score: float
    evidence: tuple[str, ...]


class Coder:
    def __init__(
        self,
        catalogue: Catalogue,
        training_rows: list[dict[str, Any]] | None = None,
        anchor_weight: float = 3.0,
        idf_power: float = 1.0,
        use_coverage: bool = False,
        use_diversity: bool = False,
        use_lexicon: bool = True,
        use_post_negation: bool = True,
        use_phrase_bonus: bool = True,
        phrase_bonus: float = 5.0,
        use_specificity: bool = True,
        neighbour_weight: float = 12.0,
        neighbour_count: int = 5,
        bm25_b: float = 1.0,
        bm25_k1: float = 1.2,
        use_bigrams: bool = True,
        bigram_weight: float = 8.0,
        use_prf: bool = False,
        prf_weight: float = 2.0,
        prf_docs: int = 2,
    ):
        self.catalogue = catalogue
        self.anchor_weight = anchor_weight
        self.idf_power = idf_power
        self.use_coverage = use_coverage
        self.use_diversity = use_diversity
        self.use_lexicon = use_lexicon
        self.use_post_negation = use_post_negation
        self.use_phrase_bonus = use_phrase_bonus
        self.phrase_bonus = phrase_bonus
        self.use_specificity = use_specificity
        self.neighbour_weight = neighbour_weight
        self.neighbour_count = neighbour_count
        self.bm25_b = bm25_b
        self.bm25_k1 = bm25_k1
        self.use_bigrams = use_bigrams
        self.bigram_weight = bigram_weight
        self.use_prf = use_prf
        self.prf_weight = prf_weight
        self.prf_docs = prf_docs
        self.docs = list(catalogue.categories.values())
        self.df: Counter[str] = Counter()
        self.postings: dict[str, list[tuple[str, float, int]]] = {}
        depths: dict[str, float] = {}
        discount: dict[str, float] = {}
        words_by_code: dict[str, list[str]] = {}
        for category in self.docs:
            words = [token for token in self._tokens(category.title) if token not in STOP]
            words_by_code[category.code] = words
            terms = Counter(words)
            length = sum(terms.values())
            depth_bonus = 0.012 * category.depth + (0.015 if category.leaf else 0.0)
            depths[category.code] = depth_bonus
            discount[category.code] = (
                TRADITIONAL_MEDICINE_DISCOUNT
                if category.chapter == TRADITIONAL_MEDICINE_CHAPTER
                else FINDING_DISCOUNT if category.chapter in FINDING_CHAPTERS else 1.0
            )
            for term, frequency in terms.items():
                self.df[term] += 1
                self.postings.setdefault(term, []).append((category.code, frequency, length))
        self.length_bonus = depths
        self.discount = discount
        self.title_text = {code: " ".join(words) for code, words in words_by_code.items()}
        self.bigrams: dict[str, list[str]] = {}
        for code, words in words_by_code.items():
            for index in range(len(words) - 1):
                self.bigrams.setdefault(f"{words[index]} {words[index + 1]}", []).append(code)
        self.rare_title_token = {
            code: any(self.df.get(token, 0) <= 3 for token in words)
            for code, words in words_by_code.items()
        }
        self.avg_len = sum(len(words) for words in words_by_code.values()) / max(1, len(self.docs))
        self.fallback = "MG26" if "MG26" in catalogue.codes else min(catalogue.codes)
        self.training: list[tuple[str, dict[str, float], list[str]]] = []
        self.training_df: Counter[str] = Counter()
        self.training_count = 0
        if training_rows:
            self._load_training(training_rows)

    def _tokens(self, text: str) -> list[str]:
        return canonical_tokens(text) if self.use_lexicon else [t.lower() for t in TOKEN_RE.findall(text)]

    def _load_training(self, rows: list[dict[str, Any]]) -> None:
        cleaned: list[tuple[str, Counter[str], list[str]]] = []
        frequencies: Counter[str] = Counter()
        for row in rows:
            tokens = _query_tokens(
                str(row.get("text") or ""), self.anchor_weight, self.use_lexicon, self.use_post_negation
            )
            codes = [str(code).upper() for code in row.get("gold", []) if str(code).upper() in self.catalogue.codes]
            if not tokens or not codes:
                continue
            frequencies.update(tokens.keys())
            cleaned.append((str(row.get("id", "")), tokens, codes))
        self.training_df = frequencies
        self.training_count = max(1, len(cleaned))
        for note_id, tokens, codes in cleaned:
            weights = {
                token: (1.0 + math.log(freq)) * math.log(1.0 + self.training_count / (1 + frequencies[token]))
                for token, freq in tokens.items()
            }
            norm = math.sqrt(sum(weight * weight for weight in weights.values())) or 1.0
            self.training.append((note_id, {token: weight / norm for token, weight in weights.items()}, codes))

    def _rank(self, query: Counter[str]) -> list[Ranked]:
        if not query:
            category = self.catalogue.get(self.fallback)
            return [Ranked(self.fallback, 0.0, (category.title if category else "fallback",))]
        n_docs = len(self.docs)
        scores: Counter[str] = Counter()
        matched: dict[str, list[str]] = {}
        for term, qfreq in query.items():
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = math.log(1.0 + (n_docs - self.df[term] + 0.5) / (self.df[term] + 0.5)) ** self.idf_power
            weight = min(qfreq, 2) * idf
            for code, tf, length in postings:
                denom = tf + self.bm25_k1 * (1.0 - self.bm25_b + self.bm25_b * length / max(1.0, self.avg_len))
                scores[code] += weight * (tf * (self.bm25_k1 + 1.0) / denom)
                matched.setdefault(code, []).append(term)
        if not scores:
            return []
        # A candidate that shares only one incidental token with a long note must not
        # beat a candidate that explains much of the note. Coverage guards that.
        query_terms = max(1, len(query))
        adjusted = {}
        for code, score in scores.items():
            if self.use_coverage and query_terms >= 5:
                coverage = len(matched.get(code, ())) / query_terms
                factor = 0.55 + 0.45 * min(1.0, coverage * 3.0)
            else:
                factor = 1.0
            adjusted[code] = score * self.discount.get(code, 1.0) * factor + self.length_bonus.get(code, 0.0)
        best = heapq.nlargest(TOP_K, adjusted.items(), key=lambda item: (item[1], item[0]))
        return [Ranked(code, score, tuple(matched.get(code, ())[:8])) for code, score in best]

    def _example_matches(self, query: Counter[str], exclude_id: str | None = None) -> list[tuple[float, str, list[str]]]:
        if not self.training or not query:
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
        return matches[:self.neighbour_count]

    def _prefer_specific(self, scores: dict[str, float]) -> list[str]:
        """Drop a parent code when a competitive, more specific child is present.

        The scorer awards only exact matches and the brief states gold is the most
        specific supported code, so a parent must never outrank its own child.
        """
        if not self.use_specificity:
            return sorted(scores, key=lambda code: (-scores[code], code))[:TOP_K]
        ordered = sorted(scores, key=lambda code: (-scores[code], code))[:TOP_K]
        present = set(ordered)
        keep: list[str] = []
        for code in ordered:
            prefix = code + "."
            dominated = any(
                other.startswith(prefix) and scores[other] >= 0.35 * scores[code]
                for other in present
                if other != code
            )
            if not dominated:
                keep.append(code)
        return keep or ordered

    def _diverse(self, codes: list[str]) -> list[str]:
        """Keep one code per root family so three spellings of one idea cannot fill slots."""
        if not self.use_diversity:
            return codes
        seen_family: set[str] = set()
        primary: list[str] = []
        overflow: list[str] = []
        for code in codes:
            family = code.split(".")[0]
            if family in seen_family:
                overflow.append(code)
                continue
            seen_family.add(family)
            primary.append(code)
        for code in overflow:
            if len(primary) >= 3:
                break
            primary.append(code)
        return primary

    def predict(self, text: str, note_id: str | None = None) -> tuple[list[str], dict[str, Any]]:
        safe_text = _clip(str(text or ""))
        raw = self._tokens(safe_text)
        query = _body_counts(raw, self.use_post_negation)
        query.update(_anchor_counts(safe_text, self.anchor_weight, self.use_lexicon))
        ranked = self._rank(query)
        if self.use_prf and ranked:
            expanded = Counter(query)
            for item in ranked[:self.prf_docs]:
                for token in self.title_text.get(item.code, "").split()[:8]:
                    if token not in expanded:
                        expanded[token] += self.prf_weight
            if len(expanded) > len(query):
                ranked = self._rank(expanded)
        scores = {item.code: item.score for item in ranked}
        evidence: dict[str, list[str]] = {item.code: list(item.evidence) for item in ranked}
        sources: dict[str, str] = {item.code: "title-search" for item in ranked}
        words = [token for token in raw if token not in STOP]
        if self.use_bigrams:
            seen: Counter[str] = Counter()
            for index in range(len(words) - 1):
                pair = f"{words[index]} {words[index + 1]}"
                if pair in self.bigrams:
                    seen[pair] += 1
            for pair, count in seen.items():
                for code in self.bigrams[pair]:
                    scores[code] = scores.get(code, 0.0) + self.bigram_weight * min(count, 2)
                    evidence.setdefault(code, []).append(f"phrase pair: {pair}")
                    if sources.get(code) != "clinical-rule":
                        sources[code] = "bigram-match"
        if self.use_phrase_bonus:
            note_norm = " " + " ".join(words) + " "
            for item in ranked[:TOP_K]:
                title = self.title_text.get(item.code, "")
                if not title:
                    continue
                words = title.split()
                # A verbatim concept mention is strong evidence, but a one-word title
                # only counts when that word is rare enough to be specific.
                if len(words) < 2 and not self.rare_title_token.get(item.code, False):
                    continue
                if f" {title} " in note_norm:
                    scores[item.code] = scores.get(item.code, 0.0) + self.phrase_bonus
                    evidence.setdefault(item.code, []).append(f"title phrase: {title}")
                    sources[item.code] = "exact-phrase"
        for pattern, code, reason in CLINICAL_RULES:
            if code not in self.catalogue.codes:
                continue
            for match in pattern.finditer(safe_text):
                if _is_negated(safe_text[:match.start()]):
                    continue
                suffix = TOKEN_RE.findall(safe_text[match.end():match.end() + 24].lower())[:2]
                if any(token in POST_NEGATORS for token in suffix):
                    continue
                scores[code] = max(scores.get(code, 0.0), 100.0)
                evidence.setdefault(code, []).append(reason)
                sources[code] = "clinical-rule"
                break
        for similarity, matched_id, matched_codes in self._example_matches(query, note_id):
            for code in matched_codes:
                scores[code] = scores.get(code, 0.0) + similarity * self.neighbour_weight
                evidence.setdefault(code, []).append(f"similar training note {matched_id} ({similarity:.2f})")
                if sources.get(code) != "clinical-rule":
                    sources[code] = "training-neighbor"
        if not scores:
            scores = {self.fallback: 0.0}
            evidence[self.fallback] = ["no lexical match; safe valid fallback"]
            sources[self.fallback] = "fallback"
        elif not query:
            sources[self.fallback] = "fallback"
            evidence.setdefault(self.fallback, ["empty note; safe valid fallback"])
        codes = self._diverse(self._prefer_specific(scores))[:3]
        if not codes:
            codes = [self.fallback]
            scores.setdefault(self.fallback, 0.0)
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
        safe_text = _clip(str(text or ""))
        query = _query_tokens(safe_text, self.anchor_weight, self.use_lexicon, self.use_post_negation)
        codes, _ = self.predict(safe_text, note_id)
        order = list(codes)
        for item in self._rank(query):
            if item.code not in order:
                order.append(item.code)
        return [{"code": code, "title": self.catalogue.categories[code].title} for code in order[:limit]]

    def rerank(self, text: str, proposed: list[str], note_id: str | None = None) -> list[str]:
        chosen: list[str] = []
        for value in proposed:
            code = normalize_code(str(value))
            if code and code in self.catalogue.codes and code not in chosen:
                chosen.append(code)
            if len(chosen) == 3:
                break
        if len(chosen) < 3:
            fallback, _ = self.predict(text, note_id)
            chosen.extend(code for code in fallback if code not in chosen)
        return chosen[:3]
