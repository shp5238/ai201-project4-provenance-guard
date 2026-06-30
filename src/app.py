import uuid

from flask import Flask, render_template, request, jsonify
from audit_logger import log_event, mark_classification_under_review, read_log
from detector import classify_text

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():

    data = request.get_json()

    if not data:
        return jsonify({"message": "Missing JSON body."}), 400

    result = classify_text(
        text=data.get("text", ""),
        creator_id=data.get("creator_id", "anonymous")
    )

    if result.get("status") != "error":
        result["content_id"] = str(uuid.uuid4())
        log_event(result)

    return jsonify(result)


@app.route("/appeal", methods=["POST"])
def appeal():

    data = request.get_json()

    if not data:
        return jsonify({"message": "Missing JSON body."}), 400

    content_id = data.get("content_id")
    creator_id = data.get("creator_id")
    reasoning = data.get("creator_reasoning")

    if not content_id or not creator_id or not reasoning:
        return jsonify({
            "message": "content_id, creator_id, and creator_reasoning are required."
        }), 400

    updated_classification = mark_classification_under_review(
        content_id=content_id,
        creator_id=creator_id,
        reasoning=reasoning
    )

    if updated_classification is None:
        return jsonify({
            "message": "No classified submission found for this content_id and creator_id."
        }), 404

    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": "appeal_submitted",
        "confidence": None,
        "label": "Creator submitted an appeal.",
        "creator_reasoning": reasoning,
        "status": "under_review"
    }

    log_event(entry)

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "classification_status": updated_classification["status"],
        "message": "Your appeal was received and is under review."
    })


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({
        "entries": read_log()
    })


if __name__ == "__main__":
    app.run(debug=True, port=5050)
