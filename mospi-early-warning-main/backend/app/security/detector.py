import json, re
from datetime import datetime, timezone

SIGNATURES = [
    ("nosql_injection_attempt", re.compile(r"\$(where|ne|gt|regex|exists)\b", re.I), 30),
    ("sql_injection_attempt", re.compile(r"(?:'\s*or\s*'1'\s*=\s*'1|\bunion\s+select\b|--|;--|\bdrop\s+table\b)", re.I), 25),
    ("path_traversal_attempt", re.compile(r"(?:\.\.[/\\]|%2e%2e(?:%2f|%5c)|%252e%252e)", re.I), 30),
]
PROBE_PATHS = {"/admin", "/.env", "/wp-admin", "/.git/config", "/phpmyadmin", "/server-status"}

def inspect_request(path, query_string, body_text, content_length=None):
    haystack=f"{path}?{query_string}\n{body_text}"
    reasons=[]; severity=0
    for name, pattern, weight in SIGNATURES:
        if pattern.search(haystack): reasons.append(name); severity += weight
    if path.lower() in PROBE_PATHS or path.lower().startswith("/.git/"):
        reasons.append("endpoint_probe"); severity += 10
    max_body=2048
    if content_length and content_length > max_body:
        reasons.append("oversized_payload"); severity += 20
    elif len(body_text.encode("utf-8", errors="ignore")) > max_body:
        reasons.append("oversized_payload"); severity += 20
    return reasons, severity

def payload_preview(body_text):
    return body_text[:2048]
