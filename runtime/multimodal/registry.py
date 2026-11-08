"""Explicit adapter registry; never imports adapter names supplied by a request."""

import threading


class AdapterRegistry:
    def __init__(self):
        self._adapters = {}
        self._lock = threading.RLock()

    def register(self, adapter):
        capabilities = adapter.capabilities()
        adapter_id = capabilities.adapter_id
        with self._lock:
            if adapter_id in self._adapters:
                raise ValueError("Adapter already registered: " + adapter_id)
            self._adapters[adapter_id] = adapter
        return capabilities

    def get(self, adapter_id):
        with self._lock:
            return self._adapters.get(adapter_id)

    def list_capabilities(self):
        with self._lock:
            adapters = list(self._adapters.values())
        return [adapter.capabilities() for adapter in adapters]
