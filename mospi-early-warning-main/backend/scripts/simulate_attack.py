"""Local-only IDS demonstration. Never targets a remote host by default."""
import argparse, time, requests

DEFAULT_BASE="http://localhost:8000"

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base-url",default=DEFAULT_BASE,help="LOCAL server URL; default is http://localhost:8000")
    args=ap.parse_args()
    base=args.base_url.rstrip("/")
    if not (base.startswith("http://localhost") or base.startswith("http://127.0.0.1")):
        raise SystemExit("Safety check: this demo only permits localhost/127.0.0.1 targets.")
    cases=[
        ("/projects",{"q":"$ne"}),
        ("/projects",{"q":"' OR '1'='1"}),
        ("/../../etc/passwd",{}),
        ("/.env",{}),
        ("/.git/config",{}),
    ]
    for path,params in cases:
        try:
            r=requests.get(base+path,params=params,timeout=3); print(f"{r.status_code:3} GET {r.url}")
        except requests.RequestException as e: print("request failed:",e)
    print("Rapid-fire phase: sending local requests until rate/block policy responds.")
    for i in range(75):
        try:
            r=requests.get(base+"/security/unknown-demo",timeout=2)
            if r.status_code in (403,429): print(f"stopped at request {i+1}: HTTP {r.status_code}"); break
        except requests.RequestException as e: print("request failed:",e); break
    print(f"Review: {base}/security/threats and {base}/security/blocked-ips")

if __name__=="__main__": main()
