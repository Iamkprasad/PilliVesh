"""Resource-aware adapter selection. This module does not load or execute models."""

import threading


class RoutingError(Exception):
    pass


class MultimodalRouter:
    def __init__(self, registry, exclusive_slots=1):
        if exclusive_slots < 1:
            raise ValueError("exclusive_slots must be at least one")
        self.registry = registry
        self._slots = threading.BoundedSemaphore(exclusive_slots)

    def candidates(self, task, device_profile):
        matches = []
        reasons = []
        for adapter in self.registry.list_capabilities():
            if adapter.status not in ("available", "installed", "loaded"):
                continue
            if task.task_type not in adapter.tasks:
                continue
            if not set(task.modalities_in).issubset(adapter.modalities_in):
                continue
            if not set(task.modalities_out).issubset(adapter.modalities_out):
                continue
            estimate = adapter.estimated_peak_ram_mb
            if estimate is not None and device_profile.available_ram_mb is not None:
                required = estimate + device_profile.safety_reserve_mb
                if required > device_profile.available_ram_mb:
                    reasons.append(
                        "%s needs about %d MB including reserve; %d MB available"
                        % (adapter.adapter_id, required, device_profile.available_ram_mb)
                    )
                    continue
            instance = self.registry.get(adapter.adapter_id)
            supported, reason = instance.preflight(task, device_profile)
            if supported:
                matches.append(adapter)
            elif reason:
                reasons.append("%s: %s" % (adapter.adapter_id, reason))
        matches.sort(
            key=lambda item: (
                item.estimated_peak_ram_mb is None,
                item.estimated_peak_ram_mb or 0,
                item.adapter_id,
            )
        )
        return matches, reasons

    def select(self, task, device_profile):
        matches, reasons = self.candidates(task, device_profile)
        if not matches:
            detail = "; ".join(reasons) if reasons else "No installed adapter declares these capabilities"
            raise RoutingError("No compatible local adapter: " + detail)
        return self.registry.get(matches[0].adapter_id)

    def acquire_slot(self, blocking=False):
        return self._slots.acquire(blocking=blocking)

    def release_slot(self):
        self._slots.release()
