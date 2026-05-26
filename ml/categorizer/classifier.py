"""
Trained classifier for expense categorization.
Uses embeddings from sentence-transformers + Logistic Regression.
This is the Phase 2 upgrade: trained on user-corrected data for higher accuracy.
"""

import os
import pickle
import numpy as np
import logging
from typing import Optional

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder

from ml.categorizer.embedder import ItemEmbedder

logger = logging.getLogger("splitsenseai.categorizer.classifier")

MODEL_PATH = "ml/models/expense_classifier.pkl"
ENCODER_PATH = "ml/models/label_encoder.pkl"


class TrainedClassifier:
    """
    Logistic Regression classifier trained on item embeddings.
    Trained incrementally as users correct categories.
    """

    def __init__(self):
        self.embedder = ItemEmbedder()
        self.model: Optional[LogisticRegression] = None
        self.encoder: Optional[LabelEncoder] = None
        self._load_model()

    def _load_model(self):
        """Load saved model if it exists."""
        if os.path.exists(MODEL_PATH) and os.path.exists(ENCODER_PATH):
            with open(MODEL_PATH, "rb") as f:
                self.model = pickle.load(f)
            with open(ENCODER_PATH, "rb") as f:
                self.encoder = pickle.load(f)
            logger.info(f"Loaded trained classifier with {len(self.encoder.classes_)} categories")
        else:
            logger.info("No trained classifier found. Using zero-shot fallback.")

    @property
    def is_ready(self) -> bool:
        """Check if the trained model is available."""
        return self.model is not None and self.encoder is not None

    def predict(self, item_name: str) -> dict:
        """
        Predict category for a single item.

        Returns:
            {"category": "Groceries", "confidence": 0.92}
        """
        if not self.is_ready:
            raise RuntimeError("Trained classifier not available. Use zero-shot instead.")

        embedding = self.embedder.embed(item_name).reshape(1, -1)
        proba = self.model.predict_proba(embedding)[0]
        top_idx = np.argmax(proba)

        return {
            "category": self.encoder.inverse_transform([top_idx])[0],
            "confidence": round(float(proba[top_idx]), 4),
        }

    def train(self, item_names: list[str], categories: list[str]):
        """
        Train or retrain the classifier on labeled data.

        Args:
            item_names: List of item name strings.
            categories: Corresponding category labels.
        """
        if len(item_names) < 10:
            logger.warning("Need at least 10 labeled items to train. Skipping.")
            return

        logger.info(f"Training classifier on {len(item_names)} items...")

        # Generate embeddings
        embeddings = self.embedder.embed_batch(item_names)

        # Encode labels
        self.encoder = LabelEncoder()
        y = self.encoder.fit_transform(categories)

        # Train logistic regression
        self.model = LogisticRegression(
            max_iter=1000,
            multi_class="multinomial",
            solver="lbfgs",
            C=1.0,
        )
        self.model.fit(embeddings, y)

        # Save model
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(ENCODER_PATH, "wb") as f:
            pickle.dump(self.encoder, f)

        logger.info(f"Classifier trained and saved. Categories: {list(self.encoder.classes_)}")
