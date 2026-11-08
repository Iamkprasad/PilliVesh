"""Phone-first multimodal runtime foundation.

Inference backends are optional adapters. Importing this package does not
load models or optional third-party dependencies.
"""

from runtime.multimodal.contracts import (
    AdapterCapabilities,
    AdapterResult,
    DeviceProfile,
    MultimodalTask,
)

__all__ = [
    "AdapterCapabilities",
    "AdapterResult",
    "DeviceProfile",
    "MultimodalTask",
]
