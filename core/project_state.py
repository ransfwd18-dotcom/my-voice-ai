from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProjectState:
    project_id: str = ""
    project_name: str = ""
    script: str = ""
    voice: str = "en-US-AriaNeural"
    status: str = "idle"
    target_duration: Optional[float] = None
    actual_duration: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def add_warning(self, message: str):
        if message and message not in self.warnings:
            self.warnings.append(message)

    def clear_warnings(self):
        self.warnings.clear()
