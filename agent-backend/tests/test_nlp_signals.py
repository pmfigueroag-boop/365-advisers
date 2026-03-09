"""
tests/test_nlp_signals.py — NLP signal extraction tests.
"""
import pytest
from src.engines.nlp_signals.extractors import TextExtractor, SentimentAnalyser, KeyPhraseExtractor
from src.engines.nlp_signals.engine import NLPSignalEngine
from src.engines.nlp_signals.models import DocumentType

# Sample earnings call text
EARNINGS_CALL = """
Good morning everyone. We are pleased to report strong growth this quarter.
Revenue exceeded expectations and we achieved record profitability.
Our innovation pipeline continues to deliver positive results.
We remain optimistic about the future and expect revenue growth to continue.
However, we note some uncertainty in the macro environment and potential
regulatory challenges ahead. There is also an ongoing litigation matter
that we are monitoring closely. We anticipate growth of 15% next year.
"""

RISK_TEXT = """
ITEM 1A. RISK FACTORS
The company faces material weakness in internal controls.
There is a going concern related to our debt obligations.
We have experienced a cybersecurity incident affecting customer data.
A restructuring charge of $50M was recorded this quarter.
Legal proceedings include securities litigation from shareholders.
"""


class TestTextExtractor:
    def test_word_count(self):
        assert TextExtractor.word_count("Hello world foo bar") == 4

    def test_readability(self):
        score = TextExtractor.readability_score(EARNINGS_CALL)
        assert 0 <= score <= 100

    def test_extract_sections(self):
        text = "INTRODUCTION\nHello world.\nRISK FACTORS\nSome risks here."
        sections = TextExtractor.extract_sections(text)
        assert len(sections) >= 1


class TestSentimentAnalyser:
    def test_positive_text(self):
        result = SentimentAnalyser.analyse("strong growth profitable success outperform record")
        assert result.score > 0

    def test_negative_text(self):
        result = SentimentAnalyser.analyse("decline loss failure recession weakness threat")
        assert result.score < 0

    def test_neutral(self):
        result = SentimentAnalyser.analyse("the company held a meeting today")
        assert abs(result.score) < 0.5

    def test_earnings_call(self):
        result = SentimentAnalyser.analyse(EARNINGS_CALL)
        assert result.positive_pct > 0


class TestKeyPhraseExtractor:
    def test_detect_risk_flags(self):
        flags = KeyPhraseExtractor.detect_risk_flags(RISK_TEXT)
        assert "material weakness" in flags
        assert "going concern" in flags
        assert "cybersecurity incident" in flags

    def test_extract_phrases(self):
        phrases = KeyPhraseExtractor.extract(EARNINGS_CALL)
        assert len(phrases) > 0

    def test_no_risk_in_clean(self):
        flags = KeyPhraseExtractor.detect_risk_flags("Revenue grew 20% this quarter")
        assert len(flags) == 0


class TestNLPEngine:
    def test_analyse_document(self):
        signal = NLPSignalEngine.analyse_document(EARNINGS_CALL, "AAPL", DocumentType.EARNINGS_CALL)
        assert signal.ticker == "AAPL"
        assert -1 <= signal.signal <= 1
        assert signal.word_count > 0

    def test_analyse_risky_document(self):
        signal = NLPSignalEngine.analyse_document(RISK_TEXT, "XYZ", DocumentType.FORM_10K)
        assert signal.signal < 0  # risk-heavy → bearish
        assert len(signal.risk_flags) > 0

    def test_filing_analysis(self):
        filing = NLPSignalEngine.analyse_filing(RISK_TEXT, "XYZ", DocumentType.FORM_10K)
        assert filing.risk_factor_count > 0
        assert filing.litigation_mentions > 0

    def test_compare_periods(self):
        current = "Strong growth record profitability success"
        previous = "Decline loss restructuring concern"
        result = NLPSignalEngine.compare_periods(current, previous, "AAPL")
        assert result["tone_change"] > 0
        assert result["direction"] == "improving"

    def test_batch_analyse(self):
        docs = [
            {"text": EARNINGS_CALL, "ticker": "AAPL", "doc_type": "earnings_call"},
            {"text": RISK_TEXT, "ticker": "XYZ", "doc_type": "10-K"},
        ]
        results = NLPSignalEngine.batch_analyse(docs)
        assert len(results) == 2
