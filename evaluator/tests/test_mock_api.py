from fastapi.testclient import TestClient

from mock_service.app import app


def test_mock_api_e2e_flow_returns_source_and_redacted_transcripts():
    client = TestClient(app)

    init_response = client.post(
        "/v1/uploads:init",
        json={
            "filename": "заман_датасет_1.wav",
            "content_type": "audio/wav",
            "size_bytes": 19,
        },
    )
    assert init_response.status_code == 200
    upload_id = init_response.json()["upload_id"]

    upload_response = client.put(
        f"/v1/uploads/{upload_id}/content",
        content=b"fixture-zaman-dataset-1",
        headers={"content-type": "audio/wav"},
    )
    assert upload_response.status_code == 200

    job_response = client.post(
        "/v1/jobs",
        json={
            "upload_id": upload_id,
            "profile": {
                "processing_profile": "standard",
                "audio_redaction_mode": "beep",
            },
        },
    )
    assert job_response.status_code == 200
    job_id = job_response.json()["job_id"]

    first_status = client.get(f"/v1/jobs/{job_id}")
    second_status = client.get(f"/v1/jobs/{job_id}")
    assert first_status.status_code == 200
    assert second_status.status_code == 200
    assert second_status.json()["status"] == "completed"

    source_transcript = client.get(
        f"/v1/jobs/{job_id}/transcript",
        params={"variant": "source", "format": "json"},
    )
    redacted_transcript = client.get(
        f"/v1/jobs/{job_id}/transcript",
        params={"variant": "redacted", "format": "json"},
    )
    events = client.get(f"/v1/jobs/{job_id}/events")

    assert source_transcript.status_code == 200
    assert redacted_transcript.status_code == 200
    assert events.status_code == 200
    assert "(468) 723-43-09" in source_transcript.json()["full_text"]
    assert "[PHONE]" in redacted_transcript.json()["full_text"]
    assert events.json()["events"][0]["payload"]["entity_type"] == "PHONE"
