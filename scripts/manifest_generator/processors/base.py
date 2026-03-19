# scripts/manifest_generator/processors/base.py
from abc import ABC, abstractmethod

class BaseProcessor(ABC):
    """Interface for all manifest data processors."""
    @abstractmethod
    def process(self, context: dict) -> dict:
        """Modify the context and return it."""
        pass