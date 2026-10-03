from fastapi import APIRouter, Request, Query
from ..security.blocklist import unblock
from ..security.models import ThreatIntelligence, SecurityLog, BlockedIP, ThreatListResponse

router=APIRouter(prefix="/security",tags=["Security Monitoring"])

@router.get("/threats",response_model=ThreatListResponse)
def threats(request:Request,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
    db=request.app.state.mongo_db; total=db.threat_intelligence.count_documents({}); docs=list(db.threat_intelligence.find({}, {"_id":0}).sort("risk_score",-1).skip((page-1)*page_size).limit(page_size))
    return {"total":total,"page":page,"page_size":page_size,"threats":docs}

@router.get("/threats/{ip_address}")
def threat_detail(ip_address:str,request:Request):
    db=request.app.state.mongo_db; threat=db.threat_intelligence.find_one({"ip_address":ip_address},{"_id":0})
    if not threat:return {"detail":"No threat record for this IP."}
    timeline=list(db.security_logs.find({"ip_address":ip_address},{"_id":0}).sort("timestamp",-1).limit(200))
    return {"threat":threat,"timeline":timeline}

@router.get("/blocked-ips",response_model=list[BlockedIP])
def blocked(request:Request):
    return list(request.app.state.mongo_db.blocked_ips.find({},{"_id":0}).sort("expires_at",1))

@router.post("/unblock/{ip_address}")
def manual_unblock(ip_address:str,request:Request):
    return {"ip_address":ip_address,"unblocked":unblock(request.app.state.mongo_db,ip_address)}

@router.get("/logs",response_model=list[SecurityLog])
def logs(request:Request,flagged:bool|None=None,limit:int=Query(100,ge=1,le=500)):
    q={} if flagged is None else {"flagged":flagged}
    return list(request.app.state.mongo_db.security_logs.find(q,{"_id":0}).sort("timestamp",-1).limit(limit))
