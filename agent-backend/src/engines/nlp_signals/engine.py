"""
src/engines/nlp_signals/engine.py — NLP Signal Engine orchestrator.
"""
from __future__ import annotations
import logging
from src.engines.nlp_signals.models import (
    DocumentType, NLPSignal, SentimentResult, FilingAnalysis,
)
from src.engines.nlp_signals.extractors import TextExtractor, SentimentAnalyser, KeyPhraseExtractor

logger = logging.getLogger("365advisers.nlp.engine")


class NLPSignalEngine:
    """Unified NLP signal extraction from financial documents."""

    @classmethod
    def analyse_document(
        cls,
        text: str,
        ticker: str,
        doc_type: DocumentType = DocumentType.EARNINGS_CALL,
    ) -> NLPSignal:
        """Full NLP analysis pipeline."""
        sentiment = SentimentAnalyser.analyse(text)
        phrases = KeyPhraseExtractor.extract(text)
        risk_flags = KeyPhraseExtractor.detect_risk_flags(text)
        readability = TextExtractor.readability_score(text)
        wc = TextExtractor.word_count(text)

        # Composite signal: sentiment + risk flag penalty
        risk_penalty = min(len(risk_flags) * 0.1, 0.5)
        signal = sentiment.score - risk_penalty
        signal = max(-1.0, min(1.0, signal))

        confidence = sentiment.magnitude * 0.7 + (1 - risk_penalty) * 0.3

        return NLPSignal(
            ticker=ticker, document_type=doc_type,
            signal=round(signal, 4),
            confidence=round(min(confidence, 1.0), 4),
            sentiment=sentiment,
            key_phrases=phrases[:10],
            risk_flags=risk_flags,
            readability_score=readability,
            word_count=wc,
        )

    @classmethod
    def analyse_filing(
        cls,
        text: str,
        ticker: str,
        doc_type: DocumentType = DocumentType.FORM_10K,
    ) -> FilingAnalysis:
        """Structured filing analysis with section-level sentiment."""
        sections = TextExtractor.extract_sections(text)
        section_sentiments = {}

        for name, content in sections.items():
            if len(content.split()) > 20:
                section_sentiments[name] = SentimentAnalyser.analyse(content)

        risk_flags = KeyPhraseExtractor.detect_risk_flags(text)
        overall = SentimentAnalyser.analyse(text)

        # Count litigation mentions
        lit_count = text.lower().count("litigation") + text.lower().count("lawsuit") + text.lower().count("legal proceedings")

        return FilingAnalysis(
            ticker=ticker, document_type=doc_type,
            sections=section_sentiments,
            management_tone=overall.score,
            risk_factor_count=len(risk_flags),
            new_risk_factors=risk_flags,
            guidance_sentiment=overall.score,
            litigation_mentions=lit_count,
        )

    @classmethod
    def compare_periods(
        cls,
        current_text: str,
        previous_text: str,
        ticker: str,
    ) -> dict:
        """Compare sentiment between two periods."""
        current = SentimentAnalyser.analyse(current_text)
        previous = SentimentAnalyser.analyse(previous_text)
        tone_change = current.score - previous.score

        return {
            "ticker": ticker,
            "current_sentiment": current.score,
            "previous_sentiment": previous.score,
            "tone_change": round(tone_change, 4),
            "direction": "improving" if tone_change > 0.05 else ("deteriorating" if tone_change < -0.05 else "stable"),
        }

    @classmethod
    def batch_analyse(
        cls,
        documents: list[dict],
    ) -> list[NLPSignal]:
        """Batch analyse multiple documents."""
        results = []
        for doc in documents:
            signal = cls.analyse_document(
                doc.get("text", ""),
                doc.get("ticker", ""),
                DocumentType(doc.get("doc_type", "earnings_call")),
            )
            results.append(signal)
        return results
