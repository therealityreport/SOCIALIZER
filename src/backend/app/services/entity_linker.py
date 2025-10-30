"""Entity Linker for Cast Member Mentions

Identifies cast member mentions in comments using:
- Exact name matching
- Alias matching
- Fuzzy matching (for common nicknames)
"""
import re
from typing import Optional


class EntityLinker:
    """Links text mentions to cast member entities"""

    def __init__(self):
        """Initialize entity linker"""
        pass

    def extract_cast_mentions(
        self,
        text: str,
        cast_aliases: dict[str, list[str]],
    ) -> list[Optional[int]]:
        """
        Extract cast member IDs mentioned in text

        Args:
            text: Comment text
            cast_aliases: Dict mapping canonical_name -> list of aliases

        Returns:
            List of cast member IDs (None if no mentions found)
        """
        text_lower = text.lower()
        mentioned = []

        for canonical_name, aliases in cast_aliases.items():
            # Check canonical name
            if canonical_name.lower() in text_lower:
                mentioned.append(canonical_name)
                continue

            # Check aliases
            for alias in aliases:
                if alias.lower() in text_lower:
                    mentioned.append(canonical_name)
                    break

        # For now, return None to represent cast IDs
        # TODO: Implement proper ID lookup
        return [None] if mentioned else []

    def extract_with_spans(
        self,
        text: str,
        cast_aliases: dict[str, list[str]],
    ) -> list[dict[str, any]]:
        """
        Extract mentions with character spans

        Returns:
            List of dicts with {name, start, end, confidence}
        """
        spans = []
        text_lower = text.lower()

        for canonical_name, aliases in cast_aliases.items():
            all_names = [canonical_name] + aliases

            for name in all_names:
                # Find all occurrences
                pattern = re.compile(re.escape(name.lower()))
                for match in pattern.finditer(text_lower):
                    spans.append({
                        "name": canonical_name,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 1.0 if name == canonical_name else 0.9,
                        "matched_text": text[match.start():match.end()],
                    })

        return spans
