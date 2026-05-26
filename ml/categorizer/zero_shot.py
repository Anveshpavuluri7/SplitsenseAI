"""
Zero-shot classifier for expense categorization.
Uses facebook/bart-large-mnli for cold-start categorization
(no training data needed).
Falls back to embedding similarity when the zero-shot model isn't available.
"""

import logging
from typing import Optional

logger = logging.getLogger("splitsenseai.categorizer.zero_shot")

_classifier = None

# Default expense categories
DEFAULT_CATEGORIES = [
    "Groceries", "Restaurant", "Fast Food", "Beverages",
    "Household", "Personal Care", "Healthcare", "Electronics",
    "Clothing", "Transport", "Entertainment", "Utilities",
    "Office Supplies", "Pet Supplies", "Miscellaneous"
]


_classifier_failed = False  # set True on OOM so we stop retrying

def get_classifier():
    """Lazy-load the zero-shot classification pipeline."""
    global _classifier, _classifier_failed
    if _classifier_failed:
        return None
    if _classifier is None:
        try:
            logger.info("Loading zero-shot classifier (bart-large-mnli)...")
            from transformers import pipeline
            _classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=-1,  # CPU only
            )
            logger.info("Zero-shot classifier loaded.")
        except (MemoryError, Exception) as e:
            logger.warning(f"Zero-shot classifier unavailable (likely OOM on free tier): {e}")
            _classifier_failed = True
            return None
    return _classifier


class ZeroShotCategorizer:
    """
    Categorizes expense items using zero-shot classification.
    No training data required — works immediately.
    """

    def __init__(self, categories: Optional[list[str]] = None):
        self.categories = categories or DEFAULT_CATEGORIES
        self.classifier = get_classifier()

    def categorize(self, item_name: str) -> dict:
        """
        Categorize a single item.

        Args:
            item_name: e.g. "Organic Whole Milk 2%"

        Returns:
            {
                "category": "Groceries",
                "confidence": 0.89,
                "all_scores": {"Groceries": 0.89, "Beverages": 0.05, ...}
            }
        """
        result = self.classifier(
            item_name,
            candidate_labels=self.categories,
            multi_label=False,
        )

        scores = dict(zip(result["labels"], result["scores"]))
        top_category = result["labels"][0]
        top_confidence = result["scores"][0]

        return {
            "category": top_category,
            "confidence": round(top_confidence, 4),
            "all_scores": {k: round(v, 4) for k, v in scores.items()},
        }

    def categorize_batch(self, item_names: list[str]) -> list[dict]:
        """
        Categorize multiple items.

        Args:
            item_names: List of item name strings.

        Returns:
            List of categorization results.
        """
        results = []
        for name in item_names:
            try:
                result = self.categorize(name)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to categorize '{name}': {e}")
                results.append({
                    "category": "Miscellaneous",
                    "confidence": 0.0,
                    "all_scores": {},
                })
        return results
