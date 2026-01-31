"""Processors package"""
from .audio import AudioProcessor
from .transcription import WhisperTranscriber
from .semantic import SemanticProcessor
from .validator import TranscriptionValidator
from .embeddings import OllamaEmbeddings

__all__ = [
    'AudioProcessor',
    'WhisperTranscriber', 
    'SemanticProcessor',
    'TranscriptionValidator',
    'OllamaEmbeddings'
]
