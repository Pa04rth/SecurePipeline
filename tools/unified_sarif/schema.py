from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class NormalizedFinding:
    scanner: str          
    rule_id: str         
    severity: str       
    message: str
    file: Optional[str] = None
    start_line: Optional[int] = None
    help_uri: Optional[str] = None

    def to_dict(self):
        return asdict(self)
