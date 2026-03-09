"""
src/engines/nlp_signals/extractors.py — NLP text analysis primitives.

Lightweight implementations using regex and word-list sentiment.
For production, swap in transformers (FinBERT, GPT-based).
"""
from __future__ import annotations
import re
import math
import logging
from collections import Counter
from src.engines.nlp_signals.models import SentimentResult, KeyPhrase

logger = logging.getLogger("365advisers.nlp.extractors")

# ── Loughran-McDonald financial sentiment lexicons (curated subset) ──────────
_POSITIVE_WORDS = {
    "achieve", "advantage", "beneficial", "better", "boost", "confident",
    "deliver", "efficient", "exceed", "favorable", "gain", "growth",
    "improve", "increase", "innovation", "opportunity", "optimistic",
    "outperform", "positive", "profitable", "progress", "record",
    "recovery", "strength", "strong", "success", "surpass", "upside",
}

_NEGATIVE_WORDS = {
    "adverse", "challenge", "concern", "decline", "default", "deficit",
    "deteriorate", "difficulty", "downturn", "failure", "impairment",
    "inability", "investigation", "lawsuit", "litigation", "loss",
    "negative", "penalty", "recession", "restructuring", "risk",
    "slowdown", "threat", "uncertain", "unfavorable", "volatile",
    "weak", "writedown", "writeoff",
}

_RISK_PHRASES = [
    "material weakness", "going concern", "restatement", "default",
    "covenant violation", "regulatory action", "securities litigation",
    "cybersecurity incident", "supply chain disruption",
    "goodwill impairment", "restructuring charge",
]

_GUIDANCE_PHRASES = [
    "expect revenue", "anticipate growth", "guidance range",
    "full year outlook", "we project", "forecast",
    "target margin", "expected earnings",
]


class TextExtractor:
    """Extract sections and metadata from financial documents."""

    @classmethod
    def extract_sections(cls, text: str) -> dict[str, str]:
        """Split document into named sections."""
        sections = {}
        current = "introduction"
        current_text = []

        for line in text.split("\n"):
            stripped = line.strip()
            # Detect section headers (all-caps or numbered)
            if stripped and (stripped.isupper() or re.match(r'^(Item|ITEM|Part|PART)\s+\d', stripped)):
                if current_text:
                    sections[current] = "\n".join(current_text)
                current = stripped[:80].lower()
                current_text = []
            else:
                current_text.append(line)

        if current_text:
            sections[current] = "\n".join(current_text)
        return sections

    @classmethod
    def word_count(cls, text: str) -> int:
        return len(text.split())

    @classmethod
    def readability_score(cls, text: str) -> float:
        """Flesch reading ease (simplified)."""
        words = text.split()
        sentences = max(text.count(".") + text.count("!") + text.count("?"), 1)
        syllables = sum(cls._count_syllables(w) for w in words)
        n_words = max(len(words), 1)
        score = 206.835 - 1.015 * (n_words / sentences) - 84.6 * (syllables / n_words)
        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _count_syllables(word: str) -> int:
        word = word.lower().rstrip("e")
        return max(1, len(re.findall(r'[aeiouy]+', word)))


class SentimentAnalyser:
    """Financial sentiment analysis using Loughran-McDonald lexicon."""

    @classmethod
    def analyse(cls, text: str) -> SentimentResult:
        words = re.findall(r'\b[a-z]+\b', text.lower())
        n = max(len(words), 1)

        pos = sum(1 for w in words if w in _POSITIVE_WORDS)
        neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
        neu = n - pos - neg

        pos_pct = pos / n
        neg_pct = neg / n
        score = (pos - neg) / max(pos + neg, 1)
        magnitude = (pos + neg) / n

        return SentimentResult(
            score=round(score, 4),
            magnitude=round(magnitude, 4),
            positive_pct=round(pos_pct, 4),
            negative_pct=round(neg_pct, 4),
            neutral_pct=round(neu / n, 4),
        )


class KeyPhraseExtractor:
    """Extract key phrases and risk indicators."""

    @classmethod
    def extract(cls, text: str, top_n: int = 20) -> list[KeyPhrase]:
        text_lower = text.lower()
        results = []

        # Check risk phrases
        for phrase in _RISK_PHRASES:
            count = text_lower.count(phrase)
            if count > 0:
                results.append(KeyPhrase(phrase=phrase, category="risk", sentiment=-0.8, frequency=count))

        # Check guidance phrases
        for phrase in _GUIDANCE_PHRASES:
            count = text_lower.count(phrase)
            if count > 0:
                # Sentiment depends on context (simplified: neutral-positive)
                results.append(KeyPhrase(phrase=phrase, category="guidance", sentiment=0.3, frequency=count))

        # Extract frequent bigrams
        words = re.findall(r'\b[a-z]{3,}\b', text_lower)
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        common = Counter(bigrams).most_common(top_n)

        for phrase, freq in common:
            if freq >= 2 and phrase not in [r.phrase for r in results]:
                sent = 0.0
                cat = "general"
                w1, w2 = phrase.split()
                if w1 in _POSITIVE_WORDS or w2 in _POSITIVE_WORDS:
                    sent = 0.5
                    cat = "growth"
                elif w1 in _NEGATIVE_WORDS or w2 in _NEGATIVE_WORDS:
                    sent = -0.5
                    cat = "concern"
                results.append(KeyPhrase(phrase=phrase, category=cat, sentiment=sent, frequency=freq))

        return sorted(results, key=lambda x: abs(x.sentiment) * x.frequency, reverse=True)[:top_n]

    @classmethod
    def detect_risk_flags(cls, text: str) -> list[str]:
        flags = []
        text_lower = text.lower()
        for phrase in _RISK_PHRASES:
            if phrase in text_lower:
                flags.append(phrase)
        return flags
