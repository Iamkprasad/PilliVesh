"""Base class for optional multimodal inference adapters."""

from abc import ABC, abstractmethod


class MultimodalAdapter(ABC):
    @abstractmethod
    def capabilities(self):
        """Return an AdapterCapabilities instance."""

    @abstractmethod
    def preflight(self, task, device_profile):
        """Return (supported: bool, reason: str) without loading model weights."""

    @abstractmethod
    def run(self, task, cancel_token=None, progress_callback=None):
        """Execute a validated task and return an AdapterResult."""

    def cancel(self, task_id):
        """Optional cooperative cancellation hook."""

    def close(self):
        """Release model/runtime resources. Must be safe when already closed."""
