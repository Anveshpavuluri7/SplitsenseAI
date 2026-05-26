"""
Item clustering using HDBSCAN on sentence-transformer embeddings.
Groups similar items across receipts (e.g., all "milk" variants together).
"""

import numpy as np
import logging
from typing import Optional

from ml.categorizer.embedder import ItemEmbedder

logger = logging.getLogger("splitsenseai.clustering.item_cluster")


class ItemClusterer:
    """
    Clusters similar items using HDBSCAN on semantic embeddings.
    HDBSCAN is chosen over K-Means because:
    - No need to predefine number of clusters
    - Handles variable-density clusters
    - Identifies noise/outlier items
    """

    def __init__(self, min_cluster_size: int = 3, min_samples: int = 2):
        self.embedder = ItemEmbedder()
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples

    def cluster(self, item_names: list[str]) -> dict:
        """
        Cluster a list of item names.

        Args:
            item_names: List of item name strings.

        Returns:
            {
                "clusters": {
                    0: {"items": ["Milk 2%", "Whole Milk", "Organic Milk"], "label": "Milk"},
                    1: {"items": ["White Bread", "Wheat Bread"], "label": "Bread"},
                    -1: {"items": ["Random Item"], "label": "Unclustered"},
                },
                "n_clusters": 2,
                "n_noise": 1,
            }
        """
        if len(item_names) < self.min_cluster_size:
            logger.info(f"Too few items ({len(item_names)}) for clustering.")
            return {"clusters": {0: {"items": item_names, "label": "All Items"}}, "n_clusters": 1, "n_noise": 0}

        # Generate embeddings
        embeddings = self.embedder.embed_batch(item_names)

        # Run DBSCAN (sklearn, no compilation needed)
        from sklearn.cluster import DBSCAN
        from sklearn.preprocessing import StandardScaler
        scaled = StandardScaler().fit_transform(embeddings)
        clusterer = DBSCAN(
            eps=0.5,
            min_samples=self.min_samples,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(scaled)

        # Group items by cluster
        clusters = {}
        for idx, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = {"items": [], "label": ""}
            clusters[label]["items"].append(item_names[idx])

        # Generate cluster labels (shortest common item name)
        for label, data in clusters.items():
            if label == -1:
                data["label"] = "Unclustered"
            else:
                # Use the shortest item name as a representative label
                data["label"] = min(data["items"], key=len)

        n_clusters = len([l for l in set(labels) if l >= 0])
        n_noise = int(sum(1 for l in labels if l == -1))

        logger.info(f"Clustered {len(item_names)} items into {n_clusters} clusters ({n_noise} noise)")
        return {"clusters": clusters, "n_clusters": n_clusters, "n_noise": n_noise}
