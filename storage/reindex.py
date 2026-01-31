#!/usr/bin/env python3
"""
Script to reindex all existing notes into Qdrant vector store
"""
import sys
import asyncio
from pathlib import Path
from loguru import logger

# Add project root to python path
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import Settings
from storage import VectorStore
from processors import OllamaEmbeddings

async def reindex():
    logger.info("Starting reindexing process...")
    
    # Initialize components
    vector_store = VectorStore()
    vector_store.recreate_collection()
    embeddings = OllamaEmbeddings()
    
    notes_dir = Settings.NOTES_DIR
    if not notes_dir.exists():
        logger.error(f"Notes directory not found: {notes_dir}")
        return

    # Find all MD files
    files = list(notes_dir.rglob("*.md"))
    logger.info(f"Found {len(files)} notes to index")
    
    try:
        for i, file_path in enumerate(files, 1):
            try:
                logger.info(f"Processing [{i}/{len(files)}]: {file_path.name}")
                
                content = file_path.read_text(encoding='utf-8')
                
                # Simple parsing of YAML frontmatter
                parts = content.split('---', 2)
                title = file_path.stem
                category = file_path.parent.name
                
                if len(parts) >= 3:
                    body = parts[2].strip()
                    # Try to extract title from # Header
                    lines = body.split('\n')
                    for line in lines:
                        if line.startswith('# '):
                            title = line[2:].strip()
                            break
                else:
                    # This is a plain markdown file without frontmatter
                    body = content
                    
                    # Check for first line header extraction
                    lines = body.split('\n')
                    if lines and lines[0].startswith('# '):
                        title = lines[0][2:].strip()
                    else:
                        # Use filename as title if no header found
                        title = file_path.stem.replace('_', ' ').capitalize()

                # Combine for embedding
                full_text = f"{title}\n\n{body}"
                
                # Chunking logic for large files
                chunk_size = 1500
                overlap = 150
                
                if len(full_text) > chunk_size:
                    logger.info(f"Note too large ({len(full_text)} chars), splitting into chunks...")
                    chunks = []
                    start = 0
                    while start < len(full_text):
                        end = start + chunk_size
                        chunk = full_text[start:end].strip()
                        if chunk:
                            chunks.append(chunk)
                        start += (chunk_size - overlap)
                    
                    logger.info(f"Generated {len(chunks)} chunks")
                    for idx, chunk in enumerate(chunks):
                        # Add small delay to avoid overwhelming Ollama
                        if idx > 0:
                            await asyncio.sleep(0.1)
                        
                        vector = await embeddings.get_embedding(chunk)
                        if vector:
                            # Create unique ID for chunk
                            chunk_id = f"{file_path}_{idx}"
                            vector_store.add_note(
                                note_id=chunk_id,
                                vector=vector,
                                payload={
                                    "category": category,
                                    "title": f"{title} (Part {idx+1})",
                                    "path": str(file_path),
                                    "chunk_index": idx
                                }
                            )
                        else:
                             logger.warning(f"Failed to embed chunk {idx} for {file_path.name}")
                else:
                    # Normal processing for small files
                    vector = await embeddings.get_embedding(full_text)
                    
                    if vector:
                        vector_store.add_note(
                            note_id=str(file_path),
                            vector=vector,
                            payload={
                                "category": category,
                                "title": title,
                                "path": str(file_path)
                            }
                        )
                    else:
                        logger.warning(f"Failed to generate embedding for {file_path.name}")
                    
            except Exception as e:
                logger.error(f"Failed to index {file_path.name}: {e}")
    finally:
        await embeddings.close()
        
    logger.info("Reindexing completed!")

if __name__ == "__main__":
    asyncio.run(reindex())
