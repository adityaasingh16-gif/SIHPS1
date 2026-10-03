from datetime import datetime, timedelta, timezone
import os

BLOCK_THRESHOLD = int(os.getenv("IDS_BLOCK_THRESHOLD", "20"))
BLOCK_DURATION_HOURS = int(os.getenv("IDS_BLOCK_DURATION_HOURS", "24"))

def ensure_indexes(db):
    db.blocked_ips.create_index("ip_address", unique=True)
    db.blocked_ips.create_index("expires_at", expireAfterSeconds=0)
    db.threat_intelligence.create_index("ip_address", unique=True)
    db.security_logs.create_index("timestamp")
    db.security_logs.create_index([("ip_address", 1), ("timestamp", -1)])

def is_blocked(db, ip):
    doc=db.blocked_ips.find_one({"ip_address":ip, "expires_at":{"$gt":datetime.now(timezone.utc)}})
    return doc

def maybe_block(db, ip, reason, violation_count):
    if violation_count < BLOCK_THRESHOLD: return None
    now=datetime.now(timezone.utc); expires=now+timedelta(hours=BLOCK_DURATION_HOURS)
    db.blocked_ips.update_one({"ip_address":ip},{"$set":{"ip_address":ip,"blocked_at":now,"reason":reason,"violation_count":violation_count,"expires_at":expires}},upsert=True)
    db.threat_intelligence.update_one({"ip_address":ip},{"$set":{"is_blocked":True}})
    return db.blocked_ips.find_one({"ip_address":ip})

def unblock(db, ip):
    result=db.blocked_ips.delete_one({"ip_address":ip})
    db.threat_intelligence.update_one({"ip_address":ip},{"$set":{"is_blocked":False}})
    return result.deleted_count > 0
