import httpx
from datetime import datetime
from loguru import logger
from typing import List, Optional
from config.settings import Settings

class OllamaEmbeddings:
    """Wrapper for Ollama Embeddings API with retries and persistent client"""
    
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or Settings.OLLAMA_BASE_URL
        self.model = model or Settings.OLLAMA_EMBEDDING_MODEL
        self.timeout = Settings.QWEN_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None
        
    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_embedding(self, text: str, retries: int = 3) -> Optional[List[float]]:
        """Get embedding for a single text with retries"""
        if not text.strip():
            return None
            
        client = await self.get_client()
        
        for attempt in range(retries):
            try:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("embedding")
                
                error_data = response.json() if response.content else {"error": "Unknown error"}
                error_msg = error_data.get("error", "Unknown error")
                
                logger.warning(f"Ollama error (attempt {attempt+1}/{retries}): {error_msg}")
                
                if "context length" in error_msg.lower():
                    # If it's a context length error, we can't retry the same text
                    # We should probably log it and return None so the caller can handle it (e.g. chunk smaller)
                    logger.error(f"Text too long for model context: {len(text)} chars")
                    return None
                    
            except Exception as e:
                logger.error(f"Request failed (attempt {attempt+1}/{retries}): {e}")
            
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2
                await asyncio.sleep(wait_time)
                
        return None

    async def get_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Get embeddings for a list of texts"""
        embeddings = []
        for text in texts:
            emb = await self.get_embedding(text)
            embeddings.append(emb)
            # Small delay between batch items to be nice to Ollama
            await asyncio.sleep(0.05)
        return embeddings
