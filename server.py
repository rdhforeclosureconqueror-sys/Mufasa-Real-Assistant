from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os

# ===============================
# 🔥 Mufasa AI Server — Flask
# ===============================

app = Flask(__name__)
CORS(app)  # enable cross-origin requests for local testing

# Load your OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/")
def home():
    return jsonify({"message": "🦁 Mufasa AI is online — Pan-African Portal active."})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"reply": "I didn’t catch that. Try again."})

    try:
        # Call OpenAI’s API
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Fast & affordable model
            messages=[
                {"role": "system", "content": "You are Mufasa, a wise Pan-African AI mentor who speaks with warmth and clarity."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=200
        )

        reply = response["choices"][0]["message"]["content"].strip()
        return jsonify({"reply": reply})

    except Exception as e:
        print("Error:", e)
        return jsonify({"reply": "Mufasa encountered a problem processing that request."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
