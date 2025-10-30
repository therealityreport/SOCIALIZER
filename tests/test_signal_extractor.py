"""Tests for SignalExtractor service"""
import pytest

from app.services.signal_extractor import SignalExtractor, SignalData


class TestSignalExtractor:
    """Test suite for SignalExtractor"""

    def setup_method(self):
        """Set up test fixtures"""
        self.extractor = SignalExtractor()

    def test_extract_emojis(self):
        """Test emoji extraction"""
        text = "She is absolutely amazing! 😍❤️ Love her so much 🔥"
        comment_data = {"score": 50, "reply_count": 5, "parent_id": None}

        signals = self.extractor.extract(text, comment_data)

        assert signals.emoji_count == 3
        assert len(signals.emoji_list) == 3
        assert "😍" in signals.emoji_list
        assert "❤️" in signals.emoji_list
        assert "🔥" in signals.emoji_list

    def test_extract_urls_and_media(self):
        """Test URL and media detection"""
        text = "Check this out! https://imgur.com/abc123.jpg and https://giphy.com/gifs/xyz789"
        comment_data = {"score": 10, "reply_count": 0, "parent_id": None}

        signals = self.extractor.extract(text, comment_data)

        assert signals.has_image is True
        assert signals.has_gif is True
        assert signals.has_video is False
        assert "imgur.com" in signals.domains
        assert "giphy.com" in signals.domains

    def test_all_caps_ratio(self):
        """Test ALL-CAPS detection"""
        text_high_caps = "SHE IS THE WORST!!!"
        text_low_caps = "She is the worst"

        comment_data = {"score": 5, "reply_count": 0, "parent_id": None}

        signals_high = self.extractor.extract(text_high_caps, comment_data)
        signals_low = self.extractor.extract(text_low_caps, comment_data)

        assert signals_high.all_caps_ratio > 0.9
        assert signals_low.all_caps_ratio < 0.2

    def test_punctuation_intensity(self):
        """Test punctuation intensity calculation"""
        text_high = "What?!?! Are you kidding me??!!"
        text_low = "I think she's nice"

        comment_data = {"score": 5, "reply_count": 0, "parent_id": None}

        signals_high = self.extractor.extract(text_high, comment_data)
        signals_low = self.extractor.extract(text_low, comment_data)

        assert signals_high.punctuation_intensity > signals_low.punctuation_intensity
        assert signals_high.punctuation_intensity > 0.1

    def test_negation_count(self):
        """Test negation word counting"""
        text_negations = "I don't think she's not wrong about this. Never would I trust her."
        text_no_negations = "I think she is right about this. I trust her."

        comment_data = {"score": 5, "reply_count": 0, "parent_id": None}

        signals_with = self.extractor.extract(text_negations, comment_data)
        signals_without = self.extractor.extract(text_no_negations, comment_data)

        assert signals_with.negation_count >= 3  # don't, not, never
        assert signals_without.negation_count == 0

    def test_question_detection(self):
        """Test question detection"""
        text_question = "Is she serious?"
        text_statement = "She is serious."

        comment_data = {"score": 5, "reply_count": 0, "parent_id": None}

        signals_question = self.extractor.extract(text_question, comment_data)
        signals_statement = self.extractor.extract(text_statement, comment_data)

        assert signals_question.question is True
        assert signals_statement.question is False

    def test_hashtag_count(self):
        """Test hashtag counting"""
        text = "Love this episode! #RHONY #BravoTV #TeamSonja"
        comment_data = {"score": 5, "reply_count": 0, "parent_id": None}

        signals = self.extractor.extract(text, comment_data)

        assert signals.hashtag_count == 3

    def test_engagement_metrics(self):
        """Test engagement metric extraction"""
        comment_data = {
            "score": 150,
            "reply_count": 25,
            "parent_id": "t1_abc123",
            "all_awardings": [{"name": "Gold"}, {"name": "Silver"}],
        }

        signals = self.extractor.extract("Test comment", comment_data)

        assert signals.upvotes_new == 150
        assert signals.replies == 25
        assert signals.awards == 2
        assert signals.depth >= 1  # Has parent

    def test_to_dict_conversion(self):
        """Test conversion to dict for JSONB storage"""
        text = "Amazing! 😍 https://imgur.com/test.jpg #test"
        comment_data = {"score": 10, "reply_count": 2, "parent_id": None}

        signals = self.extractor.extract(text, comment_data)
        signal_dict = signals.to_dict()

        assert isinstance(signal_dict, dict)
        assert "emoji" in signal_dict
        assert "emoji_count" in signal_dict
        assert "has_gif" in signal_dict
        assert "has_image" in signal_dict
        assert "domains" in signal_dict
        assert signal_dict["emoji_count"] == 1
        assert signal_dict["has_image"] is True

    def test_engagement_dict_conversion(self):
        """Test engagement dict for separate storage"""
        comment_data = {"score": 50, "reply_count": 10, "parent_id": None}

        signals = self.extractor.extract("Test", comment_data)
        engagement_dict = signals.engagement_dict()

        assert isinstance(engagement_dict, dict)
        assert "upvotes_new" in engagement_dict
        assert "replies" in engagement_dict
        assert "awards" in engagement_dict
        assert "velocity_2h" in engagement_dict
        assert "controversy" in engagement_dict
        assert engagement_dict["upvotes_new"] == 50
        assert engagement_dict["replies"] == 10

    def test_empty_text(self):
        """Test handling of empty text"""
        text = ""
        comment_data = {"score": 0, "reply_count": 0, "parent_id": None}

        signals = self.extractor.extract(text, comment_data)

        assert signals.emoji_count == 0
        assert signals.hashtag_count == 0
        assert signals.all_caps_ratio == 0.0
        assert signals.punctuation_intensity == 0.0
        assert signals.question is False

    def test_polarity_weight_calculation(self):
        """Test polarity weight modifier calculation"""
        # High upvotes should boost weight
        high_upvote_signals = SignalData(
            emoji_list=[],
            emoji_count=0,
            has_gif=False,
            has_image=False,
            has_video=False,
            domains=[],
            hashtag_count=0,
            all_caps_ratio=0.1,
            punctuation_intensity=0.05,
            negation_count=0,
            question=False,
            upvotes_new=150,
            depth=0,
            replies=10,
            awards=2,
            velocity_2h=5.0,
            controversy=0.2,
        )

        # High controversy and negations should penalize
        controversial_signals = SignalData(
            emoji_list=[],
            emoji_count=0,
            has_gif=False,
            has_image=False,
            has_video=False,
            domains=[],
            hashtag_count=0,
            all_caps_ratio=0.8,  # High ALL-CAPS
            punctuation_intensity=0.15,
            negation_count=5,  # Many negations
            question=False,
            upvotes_new=5,
            depth=0,
            replies=2,
            awards=0,
            velocity_2h=1.0,
            controversy=0.8,  # High controversy
        )

        weight_high = self.extractor.calculate_polarity_weight(high_upvote_signals)
        weight_controversial = self.extractor.calculate_polarity_weight(controversial_signals)

        assert weight_high > 1.0  # Should be boosted
        assert weight_controversial < 1.0  # Should be penalized
        assert 0.5 <= weight_high <= 1.5  # Within bounds
        assert 0.5 <= weight_controversial <= 1.5  # Within bounds
