from conftest import register


def test_interview_questions_returns_successful_fallback_when_llm_unavailable(client):
    register(client, "interview@example.com")

    response = client.post(
        "/api/interview/questions",
        json={
            "job_description": "Python backend engineer role requiring Flask, SQL, and APIs.",
            "domains": ["technical"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["fallback"] is True
    assert data["fallback_reason"]
    assert "error" not in data
    assert len(data["questions"]) == 2
