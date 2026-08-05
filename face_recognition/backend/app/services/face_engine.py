import json
import logging
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from sqlalchemy.orm import Session

from config import settings
from models.person import Person, Embedding, TrainingImage

logger = logging.getLogger(__name__)


class FaceEngine:
    """Wrapper for InsightFace face recognition."""

    def __init__(self):
        logger.info(f"Loading InsightFace model: {settings.insightface_model}")
        try:
            self.face_analysis = FaceAnalysis(
                name=settings.insightface_model,
                providers=settings.insightface_providers,
                root=str(settings.data_dir / "models"),
            )
            self.face_analysis.prepare(ctx_id=0, det_size=(640, 480))
            logger.info("FaceAnalysis ready")
        except Exception as e:
            logger.error(f"Failed to initialize FaceAnalysis: {e}")
            raise

        # In-process cache of (person_name, vector) pairs for k-NN matching,
        # lazily built from the embeddings table and invalidated after any
        # training/delete operation. Avoids re-querying + re-parsing every
        # per-image embedding on every single recognition call.
        self._embedding_cache: Optional[List[Tuple[str, np.ndarray]]] = None

    def invalidate_cache(self) -> None:
        """Drop the embedding cache so the next match reloads it from the DB."""
        self._embedding_cache = None

    def _get_cache(self, db_session: Session) -> List[Tuple[str, np.ndarray]]:
        if self._embedding_cache is None:
            cache = []
            for db_embedding in db_session.query(Embedding).all():
                try:
                    vector = np.array(json.loads(db_embedding.vector_json))
                    cache.append((db_embedding.person.name, vector))
                except Exception as e:
                    logger.warning(f"Error loading embedding {db_embedding.id} into cache: {e}")
            self._embedding_cache = cache
        return self._embedding_cache

    def _get_faces(self, img: np.ndarray) -> list:
        """
        Run face detection, with a padded-retry fallback.

        Tightly cropped face chips (e.g. Frigate's own trained-face images,
        which fill almost the entire frame with no surrounding context) often
        fail RetinaFace-style detection outright — the detector expects some
        margin around the face like a normal photo has. If the first pass
        finds nothing, retry once against a padded copy of the image.
        """
        faces = self.face_analysis.get(img)
        if not faces:
            h, w = img.shape[:2]
            pad_h, pad_w = h // 2, w // 2
            padded = cv2.copyMakeBorder(
                img, pad_h, pad_h, pad_w, pad_w, cv2.BORDER_REPLICATE
            )
            faces = self.face_analysis.get(padded)
        return faces

    @staticmethod
    def _largest_face(faces: list):
        """Pick the face with the largest bounding-box area (the subject, not a
        bystander in the background)."""
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    def detect_and_embed(self, image_path: str | Path) -> List[np.ndarray]:
        """
        Detect all faces in image and return embeddings.
        Returns list of 512-dim embedding vectors.
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                logger.warning(f"Failed to read image: {image_path}")
                return []

            faces = self._get_faces(img)
            embeddings = [face.embedding for face in faces]
            logger.debug(f"Detected {len(faces)} faces in {image_path}")
            return embeddings
        except Exception as e:
            logger.error(f"Error detecting faces in {image_path}: {e}")
            return []

    def detect_and_embed_bytes(self, image_bytes: bytes) -> List[np.ndarray]:
        """
        Detect all faces in image bytes and return embeddings.
        """
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.warning("Failed to decode image from bytes")
                return []

            faces = self._get_faces(img)
            embeddings = [face.embedding for face in faces]
            logger.debug(f"Detected {len(faces)} faces from bytes")
            return embeddings
        except Exception as e:
            logger.error(f"Error detecting faces from bytes: {e}")
            return []

    def detect_primary_embedding(self, image_path: str | Path) -> Optional[np.ndarray]:
        """
        Detect faces in a training image and return only the embedding of the
        largest (primary subject) face — a training photo with a bystander in
        the background should not have that second face's embedding blended
        into the person's profile.
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                logger.warning(f"Failed to read image: {image_path}")
                return None

            faces = self._get_faces(img)
            if not faces:
                return None
            return self._largest_face(faces).embedding
        except Exception as e:
            logger.error(f"Error detecting primary face in {image_path}: {e}")
            return None

    def detect_primary_embedding_bytes(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Bytes variant of detect_primary_embedding."""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.warning("Failed to decode image from bytes")
                return None

            faces = self._get_faces(img)
            if not faces:
                return None
            return self._largest_face(faces).embedding
        except Exception as e:
            logger.error(f"Error detecting primary face from bytes: {e}")
            return None

    def assess_quality(self, image_bytes: bytes) -> Optional[str]:
        """
        Cheap heuristic check for common, otherwise-silent causes of bad
        training embeddings: blur (Laplacian variance) and low contrast
        (grayscale stddev). Returns a comma-separated warning string, or
        None if the image passes both checks. Never blocks saving/training —
        purely informational for the user.
        """
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            issues = []
            if cv2.Laplacian(gray, cv2.CV_64F).var() < settings.quality_blur_threshold:
                issues.append("blurry")
            if gray.std() < settings.quality_contrast_threshold:
                issues.append("low_contrast")

            return ",".join(issues) if issues else None
        except Exception as e:
            logger.warning(f"Error assessing image quality: {e}")
            return None

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))

    def find_best_match(
        self, embedding: np.ndarray, db_session: Session
    ) -> Tuple[Optional[str], float, float]:
        """
        Find best matching person via a k-NN majority vote over per-image
        embeddings, with a margin check against the best-matching different
        person.

        Returns (person_name, similarity, margin). person_name is "unknown",
        "uncertain", or a real person's name (the same three-way
        classification as before) — never None once there is at least one
        embedding in the database.
        """
        cache = self._get_cache(db_session)
        if not cache:
            logger.debug("No embeddings in database yet")
            return None, 0.0, 0.0

        scored = sorted(
            ((self.similarity(embedding, vec), name) for name, vec in cache),
            key=lambda x: x[0],
            reverse=True,
        )

        top_k = scored[: settings.knn_k]
        votes = Counter(name for _, name in top_k)
        winner_name, _ = votes.most_common(1)[0]
        winner_sim = max(sim for sim, name in top_k if name == winner_name)

        runner_up_sim = next((sim for sim, name in scored if name != winner_name), 0.0)
        margin = winner_sim - runner_up_sim

        if (
            winner_sim >= settings.similarity_threshold_known
            and margin >= settings.similarity_margin_min
        ):
            return winner_name, winner_sim, margin
        elif winner_sim >= settings.similarity_threshold_unknown:
            return "uncertain", winner_sim, margin
        else:
            return "unknown", winner_sim, margin

    def compute_person_embedding(self, person_id: int, db_session: Session) -> bool:
        """
        Compute one embedding per training image for a person (instead of a
        single averaged vector), refresh TrainingImage.face_detected/
        has_embedding flags, and flag statistical outliers (images whose
        embedding deviates far from the person's own other images) via the
        existing quality_warning field.
        """
        try:
            person = db_session.query(Person).filter_by(id=person_id).first()
            if not person:
                logger.error(f"Person {person_id} not found")
                return False

            if not person.training_images:
                logger.warning(f"Person {person.name} has no training images")
                return False

            # (training_image, embedding_vector) pairs for images with a
            # detected face.
            image_embeddings: list[tuple[TrainingImage, np.ndarray]] = []
            for training_image in person.training_images:
                image_path = settings.data_dir / "images" / training_image.filename
                vector = self.detect_primary_embedding(image_path)
                training_image.face_detected = vector is not None
                training_image.has_embedding = vector is not None
                if vector is not None:
                    image_embeddings.append((training_image, vector))

            if not image_embeddings:
                logger.warning(f"No faces found in {len(person.training_images)} images for {person.name}")
                return False

            # Leave-one-out outlier detection: an image is an outlier if it
            # deviates far from the mean of the person's *other* images.
            # Only meaningful with enough images to form a stable mean.
            if len(image_embeddings) >= settings.outlier_min_images:
                vectors = np.array([v for _, v in image_embeddings])
                total = vectors.sum(axis=0)
                for i, (training_image, vector) in enumerate(image_embeddings):
                    others_mean = (total - vector) / (len(vectors) - 1)
                    sim_to_others = self.similarity(vector, others_mean)

                    existing_tags = (
                        [t for t in training_image.quality_warning.split(",") if t]
                        if training_image.quality_warning
                        else []
                    )
                    is_outlier = sim_to_others < settings.outlier_similarity_threshold
                    has_outlier_tag = "outlier" in existing_tags
                    if is_outlier and not has_outlier_tag:
                        existing_tags.append("outlier")
                    elif not is_outlier and has_outlier_tag:
                        existing_tags.remove("outlier")
                    training_image.quality_warning = ",".join(existing_tags) or None

            # Upsert one Embedding row per training image; remove rows for
            # images that no longer have a usable embedding (deleted image,
            # or face no longer detected on retrain).
            embedded_image_ids = {ti.id for ti, _ in image_embeddings}
            existing_embeddings = {
                e.training_image_id: e
                for e in db_session.query(Embedding).filter_by(person_id=person_id).all()
                if e.training_image_id is not None
            }
            for training_image, vector in image_embeddings:
                vector_json = json.dumps(vector.tolist())
                existing = existing_embeddings.get(training_image.id)
                if existing:
                    existing.vector_json = vector_json
                else:
                    db_session.add(
                        Embedding(
                            person_id=person_id,
                            training_image_id=training_image.id,
                            vector_json=vector_json,
                            image_count=1,
                        )
                    )
            for training_image_id, embedding in existing_embeddings.items():
                if training_image_id not in embedded_image_ids:
                    db_session.delete(embedding)

            db_session.commit()
            self.invalidate_cache()
            logger.info(f"Computed {len(image_embeddings)} per-image embeddings for {person.name}")
            return True
        except Exception as e:
            logger.error(f"Error computing person embedding: {e}")
            db_session.rollback()
            return False

    def analyze_image(self, image_bytes: bytes, db_session: Session) -> dict:
        """
        Analyze image bytes: detect faces, find matches.
        Returns dict with recognition results.
        """
        embeddings = self.detect_and_embed_bytes(image_bytes)
        results = []

        for embedding in embeddings:
            person_name, confidence, margin = self.find_best_match(embedding, db_session)
            results.append(
                {
                    "name": person_name or "unknown",
                    "confidence": float(confidence),
                    "margin": float(margin),
                }
            )

        return {
            "faces_detected": len(embeddings),
            "results": results if results else [{"name": "unknown", "confidence": 0.0, "margin": 0.0}],
        }
