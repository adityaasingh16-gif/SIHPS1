import json, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import unquote, unquote_plus
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from .detector import inspect_request, payload_preview
from .rate_limiter import rate_limiter
from .anomaly_detector import anomaly_detector
from .blocklist import is_blocked, maybe_block

# On cheap shared Mongo (Atlas M0) a single round-trip can cost hundreds of
# milliseconds, and the middleware touched Mongo ~5 times per request. Keep
# the enforcement reads (short per-IP caches) but never block requests on the
# telemetry writes -- they fire off in a pool instead.
_log_pool = ThreadPoolExecutor(max_workers=8)
_BLOCK_CACHE_TTL = 10
_TELE_CACHE_TTL = 15
_block_cache = {}
_tele_cache = {}


def _write_security_log(db, doc):
    try:
        db.security_logs.insert_one(doc)
    except Exception:
        pass

class SecurityMonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Mongo is where the IDS writes its telemetry. When it is not
        # configured or not reachable, `app.state.mongo_db` is never set, and
        # there is nowhere to record anything -- but the monitoring portal
        # itself must keep serving. Pass the request through uninspected rather
        # than failing it, so an IDS outage degrades to "not watching" instead
        # of "down".
        db=getattr(request.app.state, "mongo_db", None)
        if db is None:
            return await call_next(request)
        ip=request.client.host if request.client else "unknown"
        now=datetime.now(timezone.utc)
        now_ts=time.time()
        block_key=(ip, int(now_ts)//_BLOCK_CACHE_TTL)
        blocked=_block_cache.get(block_key)
        if blocked is None:
            blocked=is_blocked(db, ip)
            _block_cache[block_key]=blocked
        if blocked:
            return JSONResponse({"detail":"Request blocked by security policy."}, status_code=403)

        start=time.perf_counter()
        raw=await request.body()
        body_text=raw[:2048].decode("utf-8", errors="replace")
        # Restore body for downstream handlers.
        async def receive(): return {"type":"http.request","body":raw,"more_body":False}
        request._receive=receive
        # Inspect the decoded query alongside the wire form. Clients percent-
        # encode payloads (httpx sends `$ne` as `%24ne`, a browser sends `'` as
        # `%27`), while every signature regex matches the literal characters --
        # so inspecting only the raw string lets any encoder walk past the
        # detector. The raw form is kept because a few signatures deliberately
        # match still-encoded traversal tricks (%2e%2e, %252e%252e).
        raw_query=request.url.query
        query=f"{raw_query} {unquote(raw_query)} {unquote_plus(raw_query)}"
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            content_length = 0
        reasons, severity=inspect_request(request.url.path, query, body_text, content_length)
        # Bulk read-only traffic on the citizen-facing endpoints is the dashboard's
        # normal load (a rail card fans out one `/public/projects/{id}` per row), not
        # an intrusion signature. Exempt it from the rate limiter, so healthy public
        # browsing can never 429/403 itself. Login, security and every write path
        # stay rate-limited.
        allowed, rpm = True, 0
        if not (request.method == "GET" and request.url.path.startswith("/public")):
            allowed, rpm = rate_limiter.check(ip)
            if not allowed:
                reasons.append("rate_limit_exceeded"); severity += 25

        tele_key=(ip, int(now_ts)//_TELE_CACHE_TTL)
        tele=_tele_cache.get(tele_key)
        if tele is None:
            unique_endpoints=db.security_logs.distinct("path", {"ip_address":ip})
            recent_count=db.security_logs.count_documents({"ip_address":ip,"timestamp":{"$gte":datetime.fromtimestamp(now_ts-60,timezone.utc)}})
            errors=db.security_logs.count_documents({"ip_address":ip,"timestamp":{"$gte":datetime.fromtimestamp(now_ts-60,timezone.utc)},"status_code":{"$gte":400}})
            tele=(unique_endpoints, recent_count, errors)
            _tele_cache[tele_key]=tele
        unique_endpoints, recent_count, errors=tele
        anomaly_score=anomaly_detector.score_request([recent_count, len(unique_endpoints), len(raw), (errors/max(1,recent_count)), int(now.hour < 6 or now.hour >= 22)])
        if anomaly_score >= anomaly_detector.threshold:
            reasons.append("ml_anomaly"); severity += 20

        if reasons:
            await self._record_threat(db, ip, reasons, severity, body_text, request.url.path, request.headers.get("user-agent", ""))
            threat=db.threat_intelligence.find_one({"ip_address":ip})
            maybe_block(db, ip, ", ".join(reasons), int(threat.get("violation_count",0)) if threat else 1)
            if not allowed:
                response=JSONResponse({"detail":"Rate limit exceeded."},status_code=429)
            elif is_blocked(db,ip):
                response=JSONResponse({"detail":"Request blocked by security policy."},status_code=403)
            else:
                # Let signature hits be visible to the legitimate handler unless auto-blocked.
                response=await call_next(request)
        else:
            response=await call_next(request)

        elapsed=(time.perf_counter()-start)*1000
        if response.status_code == 404 and "endpoint_probe" not in reasons:
            reasons.append("endpoint_probe")
            await self._record_threat(db, ip, ["endpoint_probe"], 10, body_text, request.url.path, request.headers.get("user-agent", ""))
        _log_pool.submit(_write_security_log, db, {"timestamp":now,"ip_address":ip,"method":request.method,"path":request.url.path,"query_params":dict(request.query_params),"body_preview":payload_preview(body_text),"user_agent":request.headers.get("user-agent",""),"status_code":response.status_code,"response_time_ms":round(elapsed,3),"flagged":bool(reasons),"flag_reasons":reasons})
        return response

    async def _record_threat(self, db, ip, reasons, severity, body, path, ua):
        now=datetime.now(timezone.utc)
        doc=db.threat_intelligence.find_one({"ip_address":ip})
        if not doc:
            doc={"ip_address":ip,"first_seen":now,"last_seen":now,"violation_count":0,"violation_types":[],"risk_score":0.0,"sample_payloads":[],"endpoints_targeted":[],"is_blocked":False,"user_agent_samples":[]}
        doc["last_seen"]=now; doc["violation_count"]=int(doc.get("violation_count",0))+1
        doc["risk_score"]=min(100.0, float(doc.get("risk_score",0))+max(1,severity))
        doc["violation_types"]=list(dict.fromkeys((doc.get("violation_types",[])+reasons)))[-20:]
        if body: doc["sample_payloads"]=(doc.get("sample_payloads",[])+[body[:2048]])[-10:]
        doc["endpoints_targeted"]=list(dict.fromkeys((doc.get("endpoints_targeted",[])+[path])))[-50:]
        if ua: doc["user_agent_samples"]=list(dict.fromkeys((doc.get("user_agent_samples",[])+[ua])))[-10:]
        db.threat_intelligence.replace_one({"ip_address":ip},doc,upsert=True)
