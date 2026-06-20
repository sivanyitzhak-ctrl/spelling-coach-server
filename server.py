from flask import Flask, request, jsonify
import re
import os
from datetime import datetime
from twilio.rest import Client

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

CHILDREN = {
    "child_1": "whatsapp:+972524470045",
}

SPELLING_MISTAKES = {
    "בצפר": ("בית ספר", "כותבים 'בית ספר' — שתי מילים נפרדות!"),
    "מקולת": ("מכולת", "כותבים 'מכולת' עם כ ולא ק!"),
    "אחכ": ("אחר כך", "כותבים 'אחר כך' — שתי מילים נפרדות!"),
    "היתה": ("הייתה", "כותבים 'הייתה' עם יי!"),
    "אחשב": ("אחשוב", "כותבים 'אחשוב' עם ו!"),
}

daily_mistakes = {}


def check_text(text):
    words = text.strip().split()

    for i, word in enumerate(words):
        if word == "אני" and i + 1 < len(words):
            next_word = re.sub(r'[^\u05d0-\u05ea]', '', words[i + 1])
            if next_word.startswith("י"):
                corrected = "א" + next_word[1:]
                return f"אני {next_word}", f"אני {corrected}", f"כותבים 'אני {corrected}' ולא 'אני {next_word}'!"

    for word in words:
        clean = re.sub(r'[^\u05d0-\u05ea]', '', word)
        if clean in SPELLING_MISTAKES:
            correct, tip = SPELLING_MISTAKES[clean]
            return clean, correct, tip

    return None, None, None


def send_whatsapp(to_number, message):
    client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=to_number,
        body=message
    )


def build_summary_message(mistakes):
    if not mistakes:
        return "🌟 כל הכבוד! היום כתבת בלי אף שגיאה אחת!\nתמשיכי ככה, את מדהימה! 💪"

    lines = ["📚 סיכום היום שלך:"]
    for i, m in enumerate(mistakes, start=1):
        lines.append(f"{i}. {m['wrong']} ← {m['correct']}")
    lines.append("\nכל הכבוד שאת מתאמנת! 🌟")
    return "\n".join(lines)


@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    text = data.get('text', '')
    user_id = data.get('user_id', 'unknown')

    print(f"Received from {user_id}: {text}")

    wrong, correct, tip = check_text(text)

    if wrong:
        print(f"Mistake found: {wrong} -> {correct}: {tip}")
        daily_mistakes.setdefault(user_id, []).append({
            "wrong": wrong,
            "correct": correct,
            "tip": tip,
            "time": datetime.now().isoformat()
        })
        return jsonify({
            "status": "mistake",
            "wrong": wrong,
            "correct": correct,
            "tip": tip
        })

    return jsonify({"status": "ok"})


@app.route('/send-daily-summary', methods=['POST'])
def send_daily_summary():
    secret = request.headers.get("X-Cron-Secret")
    if secret != os.environ.get("CRON_SECRET"):
        return jsonify({"status": "unauthorized"}), 401

    results = {}
    for child_id, phone in CHILDREN.items():
        mistakes = daily_mistakes.get(child_id, [])
        message = build_summary_message(mistakes)
        send_whatsapp(phone, message)
        results[child_id] = {"mistakes_count": len(mistakes), "sent": True}
        daily_mistakes[child_id] = []

    print(f"Daily summary sent: {results}")
    return jsonify({"status": "sent", "results": results})


@app.route('/', methods=['GET'])
def health():
    return "SpellingCoach server is running!"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
