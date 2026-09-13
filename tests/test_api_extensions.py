"""
tests/test_api_extensions.py
----------------------------
Tests for Task 0 backend extensions:
- GET  /documents
- POST /documents/upload
- GET  /documents/status/{job_id}
- CORS preflight headers
"""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
import pytest

from pensieve.api import app, _jobs, _jobs_lock

client = TestClient(app)


def test_cors_preflight():
    """Verify CORS preflight headers for http://localhost:3000."""
    response = client.options(
        "/documents",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_list_documents_endpoint():
    """Verify GET /documents returns aggregated documents from Qdrant."""
    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "doc_id" in first
        assert "company_name" in first
        assert "fiscal_year" in first
        assert "reporting_period_type" in first
        assert "num_pages" in first
        assert "narrative_chunks" in first
        assert "table_chunks" in first
        assert "table_chunks_flagged" in first


def test_upload_non_pdf_rejected():
    """Verify uploading a non-PDF file returns HTTP 400."""
    response = client.post(
        "/documents/upload",
        files={"file": ("test.txt", io.BytesIO(b"Hello world"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]


def test_upload_pdf_accepted_and_status():
    """Verify uploading a PDF returns HTTP 202 and a valid job_id that can be polled."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 dummy pdf header and trailer %%EOF")
    response = client.post(
        "/documents/upload",
        files={"file": ("sample.pdf", fake_pdf, "application/pdf")},
    )
    assert response.status_code == 202
    res_data = response.json()
    assert "job_id" in res_data
    assert res_data["status"] == "queued"
    job_id = res_data["job_id"]

    # Poll status endpoint
    status_res = client.get(f"/documents/status/{job_id}")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["job_id"] == job_id
    assert s_data["status"] in ("queued", "processing", "failed", "done")


def test_status_not_found():
    """Verify GET /documents/status for a non-existent job returns 404."""
    response = client.get("/documents/status/non-existent-job-id")
    assert response.status_code == 404


def test_delete_document_not_found():
    """Verify DELETE /documents/{doc_id} for a non-existent doc_id returns 404."""
    response = client.delete("/documents/non-existent-doc-id")
    assert response.status_code == 404
