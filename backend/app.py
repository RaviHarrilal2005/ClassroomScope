"""
ClassroomScope API Gateway (SS-4) — skeleton entry point.

STATUS: skeleton only. This proves the front end can reach the backend
and get shaped JSON back. Real auth, the data access layer, and the
orchestrator hookup are NOT implemented yet — see TODOs below.
"""
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # TODO: restrict origins before this leaves localhost


@app.get("/api/v1/health")
def health():
    """Lets the front end confirm the backend is reachable."""
    return jsonify({"status": "ok"})


@app.get("/api/v1/results")
def get_results():
    """
    Stub results endpoint.

    Returns hardcoded data shaped like what the real Aggregation
    Service (see design doc, Section 6.5) will eventually produce,
    so the front end can be built against a stable contract before
    the real pipeline exists.

    TODO:
      - accept filter query params (date range, source, topic)
      - replace hardcoded payload with a real call to the
        Data Access Layer once the Core Database is connected
      - add auth check once Session/Auth Context (SS-5) is wired in
    """
    return jsonify({
        "sentiment_distribution": {
            "positive": 0.55,
            "neutral": 0.23,
            "negative": 0.22,
        },
        "top_topics": [
            {"label": "Academic integrity", "count": 42},
            {"label": "Classroom AI tools", "count": 35},
            {"label": "Policy & regulation", "count": 21},
        ],
        "articles": [
            {
                "id": "stub-1",
                "title": "Universities rewrite AI policy amid ChatGPT concerns",
                "source": "National",
                "stakeholder": "Administrator",
                "sentiment": "neutral",
            },
            {
                "id": "stub-2",
                "title": "Teachers embrace AI tutors in the classroom",
                "source": "Trade",
                "stakeholder": "Educator",
                "sentiment": "positive",
            },
        ],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
