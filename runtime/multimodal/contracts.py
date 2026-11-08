"""Dependency-free contracts shared by multimodal adapters and the router."""

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Tuple


VALID_MODALITIES = frozenset(("text", "image", "audio", "video", "speech"))


@dataclass(frozen=True)
class AdapterCapabilities:
    adapter_id: str
    display_name: str
    modalities_in: FrozenSet[str]
    modalities_out: FrozenSet[str]
    tasks: FrozenSet[str]
    streaming: bool = False
    estimated_peak_ram_mb: Optional[int] = None
    requires_exclusive_slot: bool = True
    status: str = "unavailable"

    def __post_init__(self):
        if not self.adapter_id or not self.adapter_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid adapter_id")
        unknown = (set(self.modalities_in) | set(self.modalities_out)) - VALID_MODALITIES
        if unknown:
            raise ValueError("Unknown modalities: " + ", ".join(sorted(unknown)))
        if self.estimated_peak_ram_mb is not None and self.estimated_peak_ram_mb < 1:
            raise ValueError("estimated_peak_ram_mb must be positive")
        if self.status not in (
            "available", "installed", "loaded", "busy", "unsupported",
            "unavailable", "error",
        ):
            raise ValueError("Invalid adapter status")


@dataclass(frozen=True)
class DeviceProfile:
    available_ram_mb: Optional[int] = None
    safety_reserve_mb: int = 512
    cpu_only: bool = True

    def __post_init__(self):
        if self.available_ram_mb is not None and self.available_ram_mb < 0:
            raise ValueError("available_ram_mb cannot be negative")
        if self.safety_reserve_mb < 0:
            raise ValueError("safety_reserve_mb cannot be negative")


@dataclass(frozen=True)
class MultimodalTask:
    task_id: str
    task_type: str
    modalities_in: FrozenSet[str]
    modalities_out: FrozenSet[str] = field(default_factory=lambda: frozenset(("text",)))
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.task_type:
            raise ValueError("task_type is required")
        unknown = (set(self.modalities_in) | set(self.modalities_out)) - VALID_MODALITIES
        if unknown:
            raise ValueError("Unknown modalities: " + ", ".join(sorted(unknown)))


@dataclass
class AdapterResult:
    task_id: str
    status: str
    text: str = ""
    artifacts: Tuple[str, ...] = ()
    adapter_id: Optional[str] = None
    error: Optional[Dict[str, str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
