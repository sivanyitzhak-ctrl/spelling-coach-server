from flask import Flask, request, jsonify
import re

app = Flask(__name__)

SPELLING_MISTAKES = {
    "בצפר": ("בית ספר", "כותבים 'בית ספר' — שתי מילים נפרדות!"),
    "מקולת": ("מכולת", "כותבים 'מכולת' עם כ ולא ק!"),
    "אחכ": ("אחר כך", "כותבים 'אחר כך' — שתי מילים נפרדות!"),
    "היתה": ("הייתה", "כותבים 'הייתה' עם יי!"),
    "אחשב": ("אחשוב", "כותבים 'אחשוב' עם ו!"),
}

def check_text(text):
    words = text.strip().split()
    
    # בדיקת תבנית "אני י..."
    for i, word in enumerate(words):
        if word == "אני" and i + 1 < len(words):
            next_word = re.sub(r'[^\u05d0-\u05ea]', '', words[i + 1])
            if next_word.startswith("י"):
                corrected = "א" + next_word[1:]
                return f"אני {next_word}", f"אני {corrected}", f"כותבים 'אני {corrected}' ולא 'אני {next_word}'!"
    
    # בדיקת שגיאות כתיב
    for word in words:
        clean = re.sub(r'[^\u05d0-\u05ea]', '', word)
        if clean in SPELLING_MISTAKES:
            correct, tip = SPELLING_MISTAKES[clean]
            return clean, correct, tip
    
    return None, None, None

@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    text = data.get('text', '')
    user_id = data.get('user_id', 'unknown')

    print(f"Received from {user_id}: {text}")

    wrong, correct, tip = check_text(text)

    if wrong:
        print(f"Mistake found: {wrong} -> {correct}: {tip}")
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
