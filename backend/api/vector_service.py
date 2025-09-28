from typing import List, Dict, Any, Optional
import logging
from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)


class VectorService:
    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None
        )
        self.collection_name = "portfolio_embeddings"
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections()
            if self.collection_name not in [c.name for c in collections.collections]:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)  # sentence-transformers/all-MiniLM-L6-v2
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection: {e}")
    
    def add_portfolio_embedding(self, portfolio_id: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """Add portfolio embedding to vector store"""
        try:
            point = PointStruct(
                id=hash(portfolio_id) % (2**63 - 1),  # Convert to int64
                vector=embedding,
                payload={
                    "portfolio_id": portfolio_id,
                    **metadata
                }
            )
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            logger.info(f"Added embedding for portfolio {portfolio_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding portfolio embedding: {e}")
            return False
    
    def search_similar_portfolios(self, query_embedding: List[float], limit: int = 5, 
                                 filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar portfolios"""
        try:
            search_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                search_filter = Filter(must=conditions)
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=search_filter
            )
            
            return [
                {
                    "portfolio_id": result.payload.get("portfolio_id"),
                    "score": result.score,
                    "metadata": result.payload
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"Error searching similar portfolios: {e}")
            return []
    
    def delete_portfolio_embedding(self, portfolio_id: str) -> bool:
        """Delete portfolio embedding"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="portfolio_id", match=MatchValue(value=portfolio_id))]
                )
            )
            logger.info(f"Deleted embedding for portfolio {portfolio_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting portfolio embedding: {e}")
            return False


# Global instance
vector_service = VectorService()
