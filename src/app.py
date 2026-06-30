from flask import Flask, render_template, request, jsonify
from detector import classify_text

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():

    data = request.get_json()

    result = classify_text(
        text=data.get("text", ""),
        creator_id=data.get("creator_id", "anonymous")
    )

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5050)