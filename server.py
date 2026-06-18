from flask import Flask, request, jsonify
import re
import os
from twilio.rest import Client

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
CHILD_WHATSAPP = os.environ.get("CHILD_WHATSAPP")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

SPELLING_MISTAKES = {
    "בצפר": ("בית ספר", "כותבים 'בית ספר' — שתי מילים נפרדות!"),
    "מקולת": ("מכולת", "כותבים 'מכולת' עם כ ולא ק!"),
    "אחכ": ("אחר כך", "כותבים 'אחר כך' — שתי מילים נפרדות!"),
    "היתה": ("הייתה", "כותבים 'הייתה' עם יי!"),
    "אחשב": ("אחשוב", "כותבים 'אחשוב' עם ו!"),
}

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

def send_whatsapp(message):
    client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=CHILD_WHATSAPP,
        body=message
    )

@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    text = data.get('text', '')
    user_id = data.get('user_id', 'unknown')

    print(f"Received from {user_id}: {text}")

    wrong, correct, tip = check_text(text)

    if wrong:
        print(f"Mistake found: {wrong} -> {correct}: {tip}")
        message = f"✏️ שגיאת כתיב!\n{tip}\n⭐ נסי לכתוב את המילה הנכונה 3 פעמים!"
        send_whatsapp(message)
        return jsonify({
            "status": "mistake",
            "wrong": wrong,
            "correct": correct,
            "tip": tip
        })

    return jsonify({"status": "ok"})

@app.route('/', methods=['GET'])
def health():
    return "SpellingCoach server is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
