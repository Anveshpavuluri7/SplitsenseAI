"""
Named Entity Recognition for receipt text.
Extracts store names, product brands, and locations using spaCy.
"""

import logging
from typing import Optional

logger = logging.getLogger("splitsenseai.ner.entity_extractor")

_nlp = None

# Known store names for pattern matching (supplements NER)
KNOWN_STORES = {
    "walmart", "target", "costco", "kroger", "safeway", "whole foods",
    "trader joe's", "aldi", "publix", "walgreens", "cvs", "7-eleven",
    "mcdonald's", "starbucks", "subway", "chipotle", "wendy's",
    "home depot", "lowe's", "best buy", "amazon", "dollar tree",
}


def get_nlp():
    """Lazy-load spaCy NLP model."""
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded: en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
            _nlp = spacy.blank("en")
    return _nlp


class EntityExtractor:
    """
    Extracts named entities from receipt text using spaCy NER
    supplemented with pattern matching for known stores.
    """

    def __init__(self):
        self.nlp = get_nlp()

    def extract_entities(self, text: str) -> dict:
        """
        Extract entities from receipt text.

        Args:
            text: Raw OCR text from receipt.

        Returns:
            {
                "store_names": ["Walmart"],
                "product_brands": ["Coca-Cola", "Lays"],
                "locations": ["Springfield, IL"],
                "dates": ["04/27/2026"],
                "money_amounts": ["$25.47"],
            }
        """
        doc = self.nlp(text)

        entities = {
            "store_names": [],
            "product_brands": [],
            "locations": [],
            "dates": [],
            "money_amounts": [],
        }

        for ent in doc.ents:
            if ent.label_ == "ORG":
                entities["store_names"].append(ent.text)
            elif ent.label_ == "PRODUCT":
                entities["product_brands"].append(ent.text)
            elif ent.label_ in ("GPE", "LOC"):
                entities["locations"].append(ent.text)
            elif ent.label_ == "DATE":
                entities["dates"].append(ent.text)
            elif ent.label_ == "MONEY":
                entities["money_amounts"].append(ent.text)

        # Supplement with known store matching
        text_lower = text.lower()
        for store in KNOWN_STORES:
            if store in text_lower and store.title() not in entities["store_names"]:
                entities["store_names"].insert(0, store.title())

        # Deduplicate
        for key in entities:
            entities[key] = list(dict.fromkeys(entities[key]))

        logger.info(f"Extracted entities: {sum(len(v) for v in entities.values())} total")
        return entities

    def extract_store_name(self, text: str) -> Optional[str]:
        """
        Extract the most likely store name from receipt text.
        Prioritizes known stores, then spaCy ORG entities.
        """
        entities = self.extract_entities(text)
        stores = entities.get("store_names", [])
        return stores[0] if stores else None
