"""Abstract Publisher Interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class PublisherInterface(ABC):
    """Interface for publishing verified blog drafts."""

    @abstractmethod
    def publish(
        self,
        article_version_id: str,
        content_hash: str,
        approval_record_id: str,
    ) -> Dict[str, Any]:
        """Publish an approved article version."""
        pass
