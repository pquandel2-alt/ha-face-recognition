import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from sqlalchemy.orm import Session

from config import settings
from models.person import Person, Embedding

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

            faces = self.face_analysis.get(img)
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

            faces = self.face_analysis.get(img)
            embeddings = [face.embedding for face in faces]
            logger.debug(f"Detected {len(faces)} faces from bytes")
            return embeddings
        except Exception as e:
            logger.error(f"Error detecting faces from bytes: {e}")
            return []

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))

    def find_best_match(
        self, embedding: np.ndarray, db_session: Session
    ) -> Tuple[Optional[str], float]:
        """
        Find best matching person in database.
        Returns (person_name, confidence) or (None, 0.0) if no match.
        """
        embeddings = db_session.query(Embedding).all()
        if not embeddings:
            logger.debug("No embeddings in database yet")
            return None, 0.0

        best_similarity = 0.0
        best_person_name = None

        for db_embedding in embeddings:
            try:
                vector = np.array(json.loads(db_embedding.vector_json))
                sim = self.similarity(embedding, vector)
                if sim > best_similarity:
                    best_similarity = sim
                    best_person_name = db_embedding.person.name
            except Exception as e:
                logger.warning(f"Error comparing with person {db_embedding.person_id}: {e}")
                continue

        # Determine confidence threshold
        if best_similarity >= settings.similarity_threshold_known:
            return best_person_name, best_similarity
        elif best_similarity >= settings.similarity_threshold_unknown:
            return "uncertain", best_similarity
        else:
            return "unknown", best_similarity

    def compute_person_embedding(self, person_id: int, db_session: Session) -> bool:
        """
        Compute average embedding for a person from all training images.
        Stores result in embeddings table.
        """
        try:
            person = db_session.query(Person).filter_by(id=person_id).first()
            if not person:
                logger.error(f"Person {person_id} not found")
                return False

            if not person.training_images:
                logger.warning(f"Person {person.name} has no training images")
                return False

            all_embeddings = []
            for training_image in person.training_images:
                image_path = settings.data_dir / "images" / training_image.filename
                embeddings = self.detect_and_embed(image_path)
                if embeddings:
                    all_embeddings.extend(embeddings)
                    training_image.face_detected = True
                    training_image.has_embedding = True

            if not all_embeddings:
                logger.warning(f"No faces found in {len(person.training_images)} images for {person.name}")
                return False

            # Compute average embedding
            avg_embedding = np.mean(all_embeddings, axis=0)
            vector_json = json.dumps(avg_embedding.tolist())

            # Store or update embedding
            existing = db_session.query(Embedding).filter_by(person_id=person_id).first()
            if existing:
                existing.vector_json = vector_json
                existing.image_count = len(all_embeddings)
            else:
                embedding = Embedding(
                    person_id=person_id,
                    vector_json=vector_json,
                    image_count=len(all_embeddings),
                )
                db_session.add(embedding)

            db_session.commit()
            logger.info(f"Computed embedding for {person.name} from {len(all_embeddings)} faces")
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
            person_name, confidence = self.find_best_match(embedding, db_session)
            results.append(
                {
                    "name": person_name or "unknown",
                    "confidence": float(confidence),
                }
            )

        return {
            "faces_detected": len(embeddings),
            "results": results if results else [{"name": "unknown", "confidence": 0.0}],
        }
