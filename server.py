from flask import Flask, request, jsonify
import re
import os
import json
import requests
from datetime import datetime
from twilio.rest import Client

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

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

DAY_OPENERS = {
    # weekday(): 0=Monday ... 6=Sunday in Python. We map explicitly by Hebrew day.
    6: "היי, כאן לקסי.\nהיו לך כמה שגיאות כתיב בהודעות היום. שווה לתקן אותן זריז כדי שמחר הכל יראה אש! 🔥",  # ראשון
    0: "היי, לקסי כאן.\nאספתי את טעויות הכתיב מההודעות שלך היום. הנה התיקונים המדויקים, כמה שניות וזה מאחורינו. ⚡",  # שני
    1: "כאן לקסי.\nהגיע הזמן לסגור פינה על שגיאות הכתיב שהיו היום. הנה הגרסה הנכונה: 💬",  # שלישי
    2: "מה הולך? לקסי על הקו.\nיש כמה שגיאות כתיב בהודעות מהיום. בואו ננעל את התיקונים ונמשיך. 🧼",  # רביעי
    3: "היי, כאן לקסי.\nהנה רשימת התיקונים לשגיאות הכתיב מהיום. מעבר זריז על הטיפים וזה סגור: 👑",  # חמישי
    4: "סוף שבוע מרגיע, לקסי כאן.\nאלו שגיאות הכתיב שעלו היום. סוגרים את התיקונים זריז והנקודות אצלך בחשבון. 📱",  # שישי
    5: "שבוע טוב! לקסי כאן.\nזמן לתקן את טעויות הכתיב של היום. מעבר על הטיפים, וישר לאתגר. 🧠",  # שבת
}

NO_MISTAKES_MESSAGE = "🌟 כל הכבוד! היום כתבת בלי אף שגיאה אחת!\nתמשיכי ככה, את מדהימה! 💪"


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


def build_lexi_prompt(unique_mistakes, opener):
    """
    בונה את ה-prompt שנשלח ל-Claude כדי לייצר את גוף ההודעה (טיפים + אתגר).
    unique_mistakes: list of dicts {wrong, correct}
    """
    mistakes_list = "\n".join(
        f"- מילה שגויה: \"{m['wrong']}\" | מילה תקינה: \"{m['correct']}\""
        for m in unique_mistakes
    )

    prompt = f"""את/ה לקסי, עוזר/ת כתיב לילדים ובני נוער. כתוב/כתבי בלשון א-מגדרית בלבד (ניטרלית, ללא פנייה ספציפית לבן/בת), בטון ישיר וקליל אך לא מתיילד.

הנה רשימת השגיאות שהילד/ה כתב/ה היום:
{mistakes_list}

המשימה שלך:

1. עבור כל מילה שגויה ברשימה, כתוב/כתבי בלוק בפורמט הבא בדיוק:
🎯 **המילה התקינה** (ולא המילה השגויה)
💎 טיפ: הסבר קצר המבוסס אך ורק על שורש או משפחת מילים בעברית (לדוגמה: "שייכת למשפחת ה-X" או "מאותו שורש כמו Y"). הטיפ חייב להיות מדויק לשונית ואמיתי, לא מומצא.

אחרי כל בלוק (כולל האחרון) — שורת רווח ריקה מלאה.

2. בסוף, תחת הכותרת "🏆 אתגר 50 הנקודות:", כתוב/כתבי את המשפט:
"פשוט להקליד לי את המשפט הבא נכון והנקודות אצלך:"
ואז משפט אחד קצר, הגיוני וטבעי בעברית שמשלב בתוכו את כל המילים התקינות (לא את השגויות) מהרשימה, כשכל מילה תקינה מודגשת ב-**. המשפט חייב להישמע טבעי, לא מאולץ.

החזר/החזירי אך ורק את הטקסט הסופי המוכן לשליחה (בלי הקדמות, בלי הסברים, בלי markdown fences) - מתחיל ישירות מהבלוק הראשון (🎯) ומסתיים במשפט האתגר.
"""
    return prompt


def call_claude(prompt):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(ANTHROPIC_API_URL, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    data = response.json()
    text_blocks = [block["text"] for block in data["content"] if block["type"] == "text"]
    return "".join(text_blocks).strip()


def build_summary_message(mistakes):
    today_weekday = datetime.now().weekday()  # Monday=0 ... Sunday=6 (Python)
    # ממירים לפי המיפוי שלנו (שמבוסס על ה-index של Python: 0=שני...6=ראשון)
    opener = DAY_OPENERS.get(today_weekday, DAY_OPENERS[0])

    if not mistakes:
        return f"{opener}\n\n{NO_MISTAKES_MESSAGE}"

    # איחוד שגיאות זהות
    unique = {}
    for m in mistakes:
        key = (m['wrong'], m['correct'])
        if key not in unique:
            unique[key] = True
    unique_mistakes = [{"wrong": w, "correct": c} for (w, c) in unique.keys()]

    prompt = build_lexi_prompt(unique_mistakes, opener)

    try:
        lexi_body = call_claude(prompt)
    except Exception as e:
        print(f"Claude API error: {e}")
        # Fallback - הודעה בסיסית בלי AI אם הקריאה נכשלת
        lines = [f"🎯 {m['correct']} (ולא {m['wrong']})" for m in unique_mistakes]
        lexi_body = "\n\n".join(lines)

    return f"{opener}\n\n{lexi_body}"


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
