"""API Route Modules

Available routes:
- /persons: Person CRUD operations
- /training: Training and embedding computation
- /recognition: Image analysis and event history
- /frigate: Frigate integration and snapshot import
"""

from . import persons, training, recognition, frigate

__all__ = ["persons", "training", "recognition", "frigate"]
