from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams
from loguru import logger
from typing import List, Dict, Any, Optional
from pathlib import Path
from config.settings import Settings
import uuid

class VectorStore:
    """Wrapper for Qdrant Vector Store"""
    
    def __init__(self):
        # Initialize client with local path (Embedded mode)
        self.collection_name = Settings.QDRANT_COLLECTION_NAME
        qdrant_path = Settings.QDRANT_PATH
        
        # Ensure path exists
        if not qdrant_path.exists():
            qdrant_path.mkdir(parents=True, exist_ok=True)
            
        try:
            self.client = QdrantClient(path=str(qdrant_path))
            logger.info(f"Initialized Qdrant at {qdrant_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            raise

    def init_collection(self, vector_size: int = 768):
        """Initialize collection if it doesn't exist"""
        if not self.client.collection_exists(self.collection_name):
            logger.info(f"Creating collection {self.collection_name} with size {vector_size}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            logger.info(f"Collection {self.collection_name} already exists")

    def add_note(self, 
                 note_id: str, 
                 vector: List[float], 
                 payload: Dict[str, Any]):
        """Add or update a note in the vector store"""
        try:
            # Use UUID for point ID or hash of note_id if it's a file path
            # Generate deterministic UUID from note_id (filepath)
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, note_id))
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.info(f"Indexed note: {note_id}")
        except Exception as e:
            logger.error(f"Failed to index note {note_id}: {e}")

    def search(self, 
               query_vector: List[float], 
               limit: int = 5, 
               score_threshold: float = None) -> List[Any]:
        """Search for similar notes"""
        try:
            threshold = score_threshold or Settings.QDRANT_SCORE_THRESHOLD
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=threshold
            ).points
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_note(self, note_id: str):
        """Delete note from vector store"""
        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, note_id))
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[point_id]
                )
            )
            logger.info(f"Deleted note from index: {note_id}")
        except Exception as e:
            logger.error(f"Failed to delete note {note_id}: {e}")

    def close(self):
        """Close connection to Qdrant"""
        try:
            if self.client:
                self.client.close()
                logger.info("Qdrant connection closed")
        except Exception as e:
            logger.error(f"Error closing Qdrant connection: {e}")
