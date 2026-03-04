class DecisionMatrix:
    """
    Deterministic matrix to classify the Investment Position based on
    Fundamental and Technical scores.
    """

    POSITION_STRONG = "Strong Opportunity"
    POSITION_MODERATE = "Moderate Opportunity"
    POSITION_NEUTRAL = "Neutral"
    POSITION_CAUTION = "Caution"
    POSITION_AVOID = "Avoid"

    @classmethod
    def determine_position(cls, fund_score: float, tech_score: float) -> str:
        """
        Determines the investment posture using a non-linear matrix.
        - Strong Opportunity: Fund >= 8.0 AND Tech >= 7.0
        - Moderate Opportunity: Fund >= 7.0 AND Tech >= 5.0
        - Neutral: Fund 5.0 - 7.0 AND Tech 4.0 - 7.0
        - Caution (Wait for Entry setup): Fund >= 7.0 AND Tech < 4.0
        - Caution (Value Trap / Speculative): Fund < 5.0 AND Tech >= 7.0
        - Avoid: Fund < 5.0 AND Tech < 4.0
        """
        if fund_score >= 8.0:
            if tech_score >= 7.0:
                return cls.POSITION_STRONG
            elif tech_score >= 4.0:
                return cls.POSITION_MODERATE
            else:
                return cls.POSITION_CAUTION  # Wait for entry
        elif fund_score >= 6.0:
            if tech_score >= 7.0:
                return cls.POSITION_MODERATE  # Good fund, great tech
            elif tech_score >= 5.0:
                return cls.POSITION_MODERATE
            elif tech_score >= 4.0:
                return cls.POSITION_NEUTRAL
            else:
                return cls.POSITION_CAUTION  # Wait for entry
        elif fund_score >= 4.0:
            if tech_score >= 7.0:
                return cls.POSITION_CAUTION  # Weak fund, strong momentum (speculative)
            elif tech_score >= 4.0:
                return cls.POSITION_NEUTRAL
            else:
                return cls.POSITION_AVOID
        else:
            if tech_score >= 7.0:
                return cls.POSITION_CAUTION  # Value trap / Speculative
            else:
                return cls.POSITION_AVOID

    @classmethod
    def calculate_confidence(cls, fund_confidence: float, fund_score: float, tech_score: float) -> float:
        """
        Calculates a unified confidence score.
        Divergence between fundamental structure and technical reality reduces confidence.
        """
        divergence = abs(fund_score - tech_score)
        # Max divergence is 10. We penalize up to 30% of confidence for extreme divergence.
        penalty = (divergence / 10.0) * 0.30
        
        final_conf = fund_confidence * (1.0 - penalty)
        return round(max(0.0, min(1.0, final_conf)), 2)

    @classmethod
    def analyze(cls, fund_score: float, tech_score: float, fund_confidence: float) -> dict:
        """
        Returns the unified decision metrics.
        """
        position = cls.determine_position(fund_score, tech_score)
        confidence = cls.calculate_confidence(fund_confidence, fund_score, tech_score)
        
        return {
            "investment_position": position,
            "confidence_score": confidence,
            "fundamental_aggregate": fund_score,
            "technical_aggregate": tech_score
        }
