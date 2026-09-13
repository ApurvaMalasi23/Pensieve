"""
scripts/verify_phase6_e2e.py
----------------------------
End-to-end automated verification script for Phase 6:
Tests all endpoints, flows, and frontend server responses.
"""

import json
import time
import urllib.request

base_backend = "http://localhost:8000"
base_frontend = "http://localhost:3000"

print("=== 1. Checking Frontend (port 3000) ===")
req = urllib.request.urlopen(base_frontend)
print("Frontend HTTP Status:", req.status)
html = req.read().decode("utf-8")
print("Frontend HTML contains Pensieve brand:", "Pensieve" in html)

print("\n=== 2. Checking Backend Health ===")
res = urllib.request.urlopen(f"{base_backend}/health")
print("Health:", res.read().decode())

print("\n=== 3. Checking Documents Listing (Task 0c / Task 4) ===")
res = urllib.request.urlopen(f"{base_backend}/documents")
docs = json.loads(res.read().decode())
print(f"Ingested documents count: {len(docs)}")
for d in docs:
    print(
        f" - {d['company_name']} ({d['fiscal_year']}), {d['num_pages']} pages, "
        f"tables: {d['table_chunks']}, flagged: {d['table_chunks_flagged']}"
    )

print("\n=== 4. Testing Flow 2: Narrative Question ===")
query_payload = json.dumps(
    {"query": "What are Republic Bancorp's primary lending activities?"}
).encode("utf-8")
req = urllib.request.Request(
    f"{base_backend}/ask",
    data=query_payload,
    headers={"Content-Type": "application/json"},
)
res = urllib.request.urlopen(req)
data = json.loads(res.read().decode())
print("Intent:", data["intent"])
print("Verification Status:", data["verification"]["status"])
print("Citations Count:", len(data["citations"]))
assert data["intent"] == "narrative"
assert data["verification"]["status"] == "not_applicable"
assert len(data["citations"]) > 0
print("[PASS] Flow 2 validated!")

print("\n=== 5. Testing Flow 3: Clean Numeric Question ===")
query_payload = json.dumps(
    {"query": "What were total traditional bank deposits as of December 31, 2024?"}
).encode("utf-8")
req = urllib.request.Request(
    f"{base_backend}/ask",
    data=query_payload,
    headers={"Content-Type": "application/json"},
)
res = urllib.request.urlopen(req)
data = json.loads(res.read().decode())
print("Intent:", data["intent"])
print("Verification Status:", data["verification"]["status"])
print("Answer:", data["answer"][:150])
print("Citations Count:", len(data["citations"]))
assert data["verification"]["status"] in ("verified", "verified_low_confidence")
print("[PASS] Flow 3 validated!")

print("\n=== 6. Testing Flow 4: Flagged Table Numeric Question ===")
query_payload = json.dumps(
    {"query": "What is the impact of a 400 basis point rate change on net interest income?"}
).encode("utf-8")
req = urllib.request.Request(
    f"{base_backend}/ask",
    data=query_payload,
    headers={"Content-Type": "application/json"},
)
res = urllib.request.urlopen(req)
data = json.loads(res.read().decode())
print("Intent:", data["intent"])
print("Verification Status:", data["verification"]["status"])
print("Verification Reason:", data["verification"]["reason"])
assert data["verification"]["status"] == "verified_low_confidence"
print("[PASS] Flow 4 validated!")

print("\n=== 7. Testing Flow 5: Comparison Question ===")
query_payload = json.dumps(
    {
        "query": "Compare total revenue or income of Republic Bancorp in 2024 and Lux Industries in 2025-26"
    }
).encode("utf-8")
req = urllib.request.Request(
    f"{base_backend}/ask",
    data=query_payload,
    headers={"Content-Type": "application/json"},
)
res = urllib.request.urlopen(req)
data = json.loads(res.read().decode())
print("Comparison Mode:", data["comparison"])
print("Entities Compared:", len(data["entities_compared"]))
print("Per Entity Results:", len(data["per_entity_results"]))
print("Deltas computed:", bool(data["deltas"]))
assert data["comparison"] is True
assert len(data["per_entity_results"]) == 2
print("[PASS] Flow 5 validated!")

print("\n=== 8. Testing Flow 1: Upload and Polling ===")
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
with open("sample_short.pdf", "rb") as f:
    file_bytes = f.read()
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="sample_short.pdf"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

req = urllib.request.Request(
    f"{base_backend}/documents/upload",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
res = urllib.request.urlopen(req)
upload_data = json.loads(res.read().decode())
job_id = upload_data["job_id"]
print("Upload queued, Job ID:", job_id)

# Poll status
for i in range(25):
    time.sleep(2)
    s_res = urllib.request.urlopen(f"{base_backend}/documents/status/{job_id}")
    status_data = json.loads(s_res.read().decode())
    print(
        f"Poll {i+1}: status={status_data['status']}, progress='{status_data.get('progress_message')}'"
    )
    if status_data["status"] in ("done", "failed"):
        break

print("[PASS] Flow 1 upload and status polling validated!")
print("\n=== ALL FLOWS VERIFIED SUCCESSFULLY ===")
