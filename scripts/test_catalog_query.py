import urllib.request
import json

payload = json.dumps({
    "query": "Who is the Executive Chairperson of Ravindra Energy Limited?",
    "top_k": 4
}).encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:8000/ask",
    data=payload,
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=90) as res:
        data = json.loads(res.read().decode("utf-8"))
        print("Status: SUCCESS")
        print("Intent:", data.get("intent"))
        print("Answer:\n", data.get("answer"))
        print("\nCitations:")
        for c in data.get("citations", []):
            print(f"  {c.get('marker')} - {c.get('company_name')} (pages {c.get('page_start')}-{c.get('page_end')}): {c.get('excerpt')[:100]}...")
except Exception as e:
    print("Error:", e)
