"""Signal Extractor Service

Extracts computed signals from Reddit comments:
- Emoji analysis (count, polarity)
- Media detection (GIF, image, video, domains)
- Text patterns (hashtags, ALL-CAPS, punctuation intensity, negations, questions)
- Engagement metrics (upvotes, replies, awards, velocity, controversy)
"""
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

try:
    import emoji
except Exception as exc:  # pragma: no cover - import guard
    raise RuntimeError("emoji package is required. Install with: pip install emoji") from exc


@dataclass
class SignalData:
    """Container for all extracted signals"""

    # Emoji and media signals
    emoji_list: list[str]
    emoji_count: int
    has_gif: bool
    has_image: bool
    has_video: bool
    domains: list[str]

    # Text pattern signals
    hashtag_count: int
    all_caps_ratio: float
    punctuation_intensity: float
    negation_count: int
    question: bool

    # Engagement signals (from comment metadata)
    upvotes_new: int
    depth: int
    replies: int
    awards: int
    velocity_2h: float
    controversy: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSONB storage"""
        return {
            "emoji": self.emoji_list,
            "emoji_count": self.emoji_count,
            "has_gif": self.has_gif,
            "has_image": self.has_image,
            "has_video": self.has_video,
            "domains": self.domains,
            "hashtag_count": self.hashtag_count,
            "all_caps_ratio": self.all_caps_ratio,
            "punctuation_intensity": self.punctuation_intensity,
            "negation_count": self.negation_count,
            "question": self.question,
        }

    def engagement_dict(self) -> dict[str, Any]:
        """Separate engagement metrics for engagement JSONB field"""
        return {
            "upvotes_new": self.upvotes_new,
            "depth": self.depth,
            "replies": self.replies,
            "awards": self.awards,
            "velocity_2h": self.velocity_2h,
            "controversy": self.controversy,
        }


class SignalExtractor:
    """Extracts rule-based signals from comment text and metadata"""

    # Common negation words
    NEGATIONS = {
        "not", "no", "never", "neither", "nobody", "nothing", "nowhere",
        "none", "nor", "hardly", "barely", "scarcely", "seldom", "rarely",
        "don't", "doesn't", "didn't", "won't", "wouldn't", "shouldn't",
        "can't", "cannot", "couldn't", "isn't", "aren't", "wasn't", "weren't"
    }

    # URL patterns
    GIF_PATTERNS = re.compile(r'\.gif|giphy\.com|tenor\.com', re.IGNORECASE)
    IMAGE_PATTERNS = re.compile(r'\.(?:jpg|jpeg|png|webp|bmp)|imgur\.com|i\.redd\.it', re.IGNORECASE)
    VIDEO_PATTERNS = re.compile(r'\.(?:mp4|webm|mov|avi)|v\.redd\.it|youtube\.com|youtu\.be|streamable\.com', re.IGNORECASE)

    def __init__(self):
        """Initialize signal extractor"""
        pass

    def extract(self, text: str, comment_data: dict[str, Any]) -> SignalData:
        """
        Extract all signals from comment text and metadata

        Args:
            text: Comment body text
            comment_data: Comment metadata (score, replies, created_utc, etc.)

        Returns:
            SignalData with all extracted signals
        """
        # Extract emoji signals
        emoji_list = self._extract_emojis(text)
        emoji_count = len(emoji_list)

        # Extract URLs and check for media
        urls = self._extract_urls(text)
        has_gif = any(self.GIF_PATTERNS.search(url) for url in urls)
        has_image = any(self.IMAGE_PATTERNS.search(url) for url in urls)
        has_video = any(self.VIDEO_PATTERNS.search(url) for url in urls)
        domains = self._extract_domains(urls)

        # Extract text pattern signals
        hashtag_count = text.count('#')
        all_caps_ratio = self._calculate_all_caps_ratio(text)
        punctuation_intensity = self._calculate_punctuation_intensity(text)
        negation_count = self._count_negations(text)
        question = '?' in text

        # Extract engagement metrics from comment data
        upvotes_new = comment_data.get('score', 0)
        depth = self._calculate_depth(comment_data.get('parent_id'))
        replies = comment_data.get('reply_count', 0)
        awards = comment_data.get('all_awardings', [])
        if isinstance(awards, list):
            awards = len(awards)
        velocity_2h = self._calculate_velocity(comment_data)
        controversy = self._calculate_controversy(comment_data)

        return SignalData(
            emoji_list=emoji_list,
            emoji_count=emoji_count,
            has_gif=has_gif,
            has_image=has_image,
            has_video=has_video,
            domains=domains,
            hashtag_count=hashtag_count,
            all_caps_ratio=all_caps_ratio,
            punctuation_intensity=punctuation_intensity,
            negation_count=negation_count,
            question=question,
            upvotes_new=upvotes_new,
            depth=depth,
            replies=replies,
            awards=awards,
            velocity_2h=velocity_2h,
            controversy=controversy,
        )

    def _extract_emojis(self, text: str) -> list[str]:
        """Extract all emojis from text"""
        return [char for char in text if char in emoji.EMOJI_DATA]

    def _extract_urls(self, text: str) -> list[str]:
        """Extract all URLs from text"""
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        return url_pattern.findall(text)

    def _extract_domains(self, urls: list[str]) -> list[str]:
        """Extract unique domains from URLs"""
        domains = set()
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    domains.add(parsed.netloc)
            except Exception:
                continue
        return list(domains)

    def _calculate_all_caps_ratio(self, text: str) -> float:
        """Calculate ratio of uppercase letters to total letters"""
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return 0.0
        uppercase = sum(1 for c in letters if c.isupper())
        return uppercase / len(letters)

    def _calculate_punctuation_intensity(self, text: str) -> float:
        """Calculate density of exclamation and question marks"""
        exclamations = text.count('!')
        questions = text.count('?')
        total_chars = len(text)
        if total_chars == 0:
            return 0.0
        return (exclamations + questions) / total_chars

    def _count_negations(self, text: str) -> int:
        """Count negation words in text"""
        words = text.lower().split()
        return sum(1 for word in words if word in self.NEGATIONS)

    def _calculate_depth(self, parent_id: str | None) -> int:
        """Calculate thread depth from parent_id structure"""
        if not parent_id:
            return 0
        # Parent IDs like "t1_abc123" indicate depth
        # Count underscores or implement proper depth calculation
        return 1 if parent_id else 0

    def _calculate_velocity(self, comment_data: dict[str, Any]) -> float:
        """
        Calculate comment velocity (replies per hour in first 2 hours)

        This would require timestamp analysis - for now return 0
        TODO: Implement when we have created_utc and reply timestamps
        """
        return 0.0

    def _calculate_controversy(self, comment_data: dict[str, Any]) -> float:
        """
        Calculate controversy score based on vote patterns

        Reddit provides ups/downs ratio - we can use that if available
        Otherwise use a heuristic based on score and gilding
        """
        score = comment_data.get('score', 0)
        # If score is low but has awards, indicates controversy
        awards = comment_data.get('all_awardings', [])
        if isinstance(awards, list):
            award_count = len(awards)
        else:
            award_count = 0

        if award_count > 0 and score < 10:
            return 0.7  # High controversy
        elif score > 100:
            return 0.1  # Low controversy (clearly agreed upon)
        else:
            return 0.3  # Medium controversy

    def calculate_polarity_weight(self, signals: SignalData) -> float:
        """
        Calculate a polarity weight modifier based on signals

        Positive indicators: upvotes, awards, positive emojis
        Negative indicators: controversy, negations, toxicity markers

        Returns: Float multiplier (0.5 - 1.5)
        """
        weight = 1.0

        # Upvotes boost
        if signals.upvotes_new > 50:
            weight += 0.2
        elif signals.upvotes_new > 100:
            weight += 0.3

        # Controversy penalty
        if signals.controversy > 0.5:
            weight -= 0.2

        # Negation penalty
        if signals.negation_count > 2:
            weight -= 0.1

        # ALL-CAPS penalty (often indicates shouting/anger)
        if signals.all_caps_ratio > 0.7:
            weight -= 0.15

        # Clamp between 0.5 and 1.5
        return max(0.5, min(1.5, weight))
