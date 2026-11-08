"""Unit tests for the dependency-free multimodal contracts and router."""

import unittest

from runtime.multimodal.contracts import (
    AdapterCapabilities,
    DeviceProfile,
    MultimodalTask,
)
from runtime.multimodal.registry import AdapterRegistry
from runtime.multimodal.router import MultimodalRouter, RoutingError


class FakeAdapter:
    def __init__(self, capabilities, supported=True, reason=""):
        self._capabilities = capabilities
        self.supported = supported
        self.reason = reason

    def capabilities(self):
        return self._capabilities

    def preflight(self, task, device_profile):
        return self.supported, self.reason


class MultimodalFoundationTests(unittest.TestCase):
    def setUp(self):
        self.task = MultimodalTask(
            task_id="test-1",
            task_type="image_question_answering",
            modalities_in=frozenset(("text", "image")),
            modalities_out=frozenset(("text",)),
        )
        self.device = DeviceProfile(available_ram_mb=2048, safety_reserve_mb=512)

    def test_contract_rejects_unknown_modality(self):
        with self.assertRaises(ValueError):
            MultimodalTask("x", "chat", frozenset(("hologram",)))

    def test_registry_rejects_duplicate_ids(self):
        caps = AdapterCapabilities(
            "vision-a", "Vision A", frozenset(("text", "image")),
            frozenset(("text",)), frozenset(("image_question_answering",)),
            estimated_peak_ram_mb=700, status="installed",
        )
        registry = AdapterRegistry()
        registry.register(FakeAdapter(caps))
        with self.assertRaises(ValueError):
            registry.register(FakeAdapter(caps))

    def test_router_selects_lowest_ram_compatible_adapter(self):
        registry = AdapterRegistry()
        for adapter_id, ram in (("vision-large", 1200), ("vision-small", 600)):
            caps = AdapterCapabilities(
                adapter_id, adapter_id, frozenset(("text", "image")),
                frozenset(("text",)), frozenset(("image_question_answering",)),
                estimated_peak_ram_mb=ram, status="installed",
            )
            registry.register(FakeAdapter(caps))
        router = MultimodalRouter(registry)
        selected = router.select(self.task, self.device)
        self.assertEqual(selected.capabilities().adapter_id, "vision-small")

    def test_router_rejects_insufficient_memory(self):
        registry = AdapterRegistry()
        caps = AdapterCapabilities(
            "vision", "Vision", frozenset(("text", "image")),
            frozenset(("text",)), frozenset(("image_question_answering",)),
            estimated_peak_ram_mb=1800, status="installed",
        )
        registry.register(FakeAdapter(caps))
        router = MultimodalRouter(registry)
        with self.assertRaises(RoutingError):
            router.select(self.task, self.device)

    def test_router_rejects_adapter_preflight_failure(self):
        registry = AdapterRegistry()
        caps = AdapterCapabilities(
            "vision", "Vision", frozenset(("text", "image")),
            frozenset(("text",)), frozenset(("image_question_answering",)),
            estimated_peak_ram_mb=300, status="installed",
        )
        registry.register(FakeAdapter(caps, False, "backend not installed"))
        router = MultimodalRouter(registry)
        with self.assertRaises(RoutingError):
            router.select(self.task, self.device)


if __name__ == "__main__":
    unittest.main()
