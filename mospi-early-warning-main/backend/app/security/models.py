from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ThreatIntelligence(BaseModel):
    ip_address: str
    first_seen: datetime
    last_seen: datetime
    violation_count: int = 0
    violation_types: List[str] = Field(default_factory=list)
    risk_score: float = 0.0
    sample_payloads: List[str] = Field(default_factory=list)
    endpoints_targeted: List[str] = Field(default_factory=list)
    is_blocked: bool = False
    user_agent_samples: List[str] = Field(default_factory=list)

class SecurityLog(BaseModel):
    timestamp: datetime
    ip_address: str
    method: str
    path: str
    query_params: Dict[str, Any] = Field(default_factory=dict)
    body_preview: str = ""
    user_agent: str = ""
    status_code: int
    response_time_ms: float
    flagged: bool = False
    flag_reasons: List[str] = Field(default_factory=list)

class BlockedIP(BaseModel):
    ip_address: str
    blocked_at: datetime
    reason: str
    violation_count: int
    expires_at: datetime

class ThreatListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    threats: List[ThreatIntelligence]
