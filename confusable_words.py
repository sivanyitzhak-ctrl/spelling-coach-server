from flask import Flask, request, jsonify
import re
import os
import json
import random
import requests
from datetime import datetime
from twilio.rest import Client
from confusable_words import CONFUSABLE_LOOKUP

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

CHILDREN = {
    "child_1": {
        "phone": "whatsapp:+972524470045",
        "parent_phone": os.environ.get("PARENT_WHATSAPP", ""),
    },
}

LEARNED_THRESHOLD = 5

DATA_DIR = os.path.dirname(__file__)
DICTIONARY_PATH = os.path.join(DATA_DIR, "growing_dictionary.json")
BASE_WORDS_PATH = os.path.join(DATA_DIR, "base_hebrew_words.json")
LEARNED_CONFUSABLES_PATH = os.path.join(DATA_DIR, "learned_confusables.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


base_words = set(load_json(BASE_WORDS_PATH, []))
growing_dictionary = set(load_json(DICTIONARY_PATH, []))
learned_confusables = load_json(LEARNED_CONFUSABLES_PATH, {})

print(f"Loaded {len(base_words)} base words, {len(growing_dictionary)} growing-dictionary words")

ANI_VERB_TIP = "כשמדברים על עצמך בלשון עתיד, הפועל מתחיל באות א' ולא ב-י' - למשל 'אני אלך', 'אני אדבר', 'אני אכתוב'. נסה/י לזכור: אני = א בהתחלה!"

daily_mistakes = {}
weekly_mistakes = {}

DAY_OPENERS = {
    6: "היי, כאן לקסי.\nהיו לך כמה שגיאות כתיב בהודעות היום. שווה לתקן אותן זריז כדי שמחר הכל יראה אש! 🔥",
    0: "היי, לקסי כאן.\nאספתי את טעויות הכתיב מההודעות שלך היום. הנה התיקונים המדויקים, כמה שניות וזה מאחורינו. ⚡",
    1: "כאן לקסי.\nהגיע הזמן לסגור פינה על שגיאות הכתיב שהיו היום. הנה הגרסה הנכונה: 💬",
    2: "מה הולך? לקסי על הקו.\nיש כמה שגיאות כתיב בהודעות מהיום. בואו ננעל את התיקונים ונמשיך. 🧼",
    3: "היי, כאן לקסי.\nהנה רשימת התיקונים לשגיאות הכתיב מהיום. מעבר זריז על הטיפים וזה סגור: 👑",
}

DAILY_WIN_MESSAGES = [
    """👋 מה הולך? לקסי כאן.

יום כתיבה של 100% דיוק עבר עלינו!!

🔥 שום פספוס. כתיבה אש
🧹 הכל נקי ומדויק!
💎 10 יהלומים של "בונוס יום נקי" נכנסו הרגע לחשבון.

ניפגש מחר! 🚀""",
    """👋 כאן לקסי.

יום שלם, אפס שגיאות.

✨ דיוק מושלם מהתחלה ועד הסוף
🎯 כל מילה נחתה בול
💎 10 יהלומים נוספו לחשבון שלך

מחר ממשיכים באותו קצב! 🚀""",
    """👋 לקסי כאן.

וואו. יום נקי לגמרי!

🔥 בלי אף תיקון אחד
🧹 הכתיבה שלך הייתה אש מההתחלה
💎 10 יהלומים נחתו בחשבון

ניפגש מחר, תמשיכי ככה! 🚀""",
    """👋 מה קורה? לקסי כאן.

יום אחד, אפס טעויות. רשמית מושלם.

🔥 כל הודעה הייתה מדויקת
✨ אין מה להוסיף, פשוט נקי
💎 10 יהלומים נכנסו הרגע

נתראה מחר! 🚀""",
    """👋 לקסי על הקו.

בדקתי את ההודעות שלך היום - הכל נקי.

🎯 אפס שגיאות, אפס תיקונים
💎 ביצוע אש מההתחלה ועד הסוף
🧹 10 יהלומים נוספו לחשבון

נמשיך באותו קצב מחר! 🚀""",
    """👋 היי, כאן לקסי.

יום מושלם נסגר.

✨ כתיבה נקייה לגמרי
🔥 בלי שום פספוס
💎 10 יהלומים התווספו לחשבון שלך

נתראה מחר באתגר הבא! 🚀""",
]

WEEKLY_WIN_MESSAGE_CHILD = """👋 סופ"ש הגיע! לקסי כאן.

זה משהו שלא קורה כל יום: שבוע שלם, אפס שגיאות כתיב.

🏆 שבוע של דיוק מושלם בכל יום.
✨ כל מילה שכתבת השבוע - נכונה. בלי יוצא מן הכלל.
💎 50 יהלומים נכנסו הרגע לחשבון - בונוס שבוע מושלם!

זה לא מקרה. זו עבודה אמיתית, ויש לך כל הזכות להיות גאה בעצמך.

שבוע טוב, ונתראה ביום ראשון! 🚀"""

WEEKLY_OPENER_CHILD = "👋 סופ\"ש הגיע! לקסי כאן.\n\nזמן לסיכום השבועי.\nבלי חפירות.\nרק רשימת הניצחונות שלך - הנה מחסן המילים שינעלו השבוע בזיכרון, ומהיום יראו אש בהודעות:"

WEEKLY_PARENT_OPENER = "👋 שלום! כאן לקסי, עוזרת ה-AI האישית להודעות מדויקות.\n\nעדכון שבועי קצר:"

WEEKLY_WIN_MESSAGE_PARENT = f"""{WEEKLY_PARENT_OPENER}

לא נמצאה אף שגיאת כתיב השבוע! 🎉

זו עבודה אמיתית, ויש סיבה טובה להיות גאים.

שבוע טוב! 🚀"""


def is_friday():
    return datetime.now().weekday() == 4


def is_shabbat():
    return datetime.now().weekday() == 5


def normalize(word):
    return re.sub(r'[^\u05d0-\u05ea]', '', word)


def is_hebrew_only(word):
    clean = word.strip()
    if not clean:
        return False
    return bool(re.fullmatch(r'[\u05d0-\u05ea]+', clean))


def is_known_word(word):
    return word in base_words or word in growing_dictionary


def call_claude_raw(prompt, max_tokens=500):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(ANTHROPIC_API_URL, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    data = response.json()
    text_blocks = [block["text"] for block in data["content"] if block["type"] == "text"]
    return "".join(text_blocks).strip()


def check_word_validity_with_claude(word):
    prompt = f"""בדוק/בדקי האם המילה הבאה בעברית כתובה נכון: "{word}"

אם המילה תקינה (כולל אם זה שם פרטי עברי, מילת סלנג מקובלת, או נטייה תקנית) - השב/השיבי בדיוק:
VALID

אם יש בה שגיאת כתיב - השב/השיבי בפורמט הבא בדיוק (שתי שורות):
CORRECT: <המילה המתוקנת>
TIP: <טיפ קצר המבוסס על שורש או משפחת מילים בעברית>

אל תוסיף/תוסיפי שום הסבר נוסף, רק את התשובה בפורמט המדויק.
"""
    try:
        result = call_claude_raw(prompt, max_tokens=200)
        if result.strip().startswith("VALID"):
            return {"valid": True}
        correct_match = re.search(r'CORRECT:\s*(.+)', result)
        tip_match = re.search(r'TIP:\s*(.+)', result)
        if correct_match and tip_match:
            return {
                "valid": False,
                "correct": correct_match.group(1).strip(),
                "tip": tip_match.group(1).strip(),
            }
        print(f"Unexpected Claude response for word check: {result}")
        return {"valid": True}
    except Exception as e:
        print(f"Claude API error (word check): {e}")
        return {"valid": True}


def check_word_in_context_with_claude(sentence, word):
    candidates = sorted(CONFUSABLE_LOOKUP.get(word, []))
    candidates_str = ", ".join(f'"{c}"' for c in [word] + candidates)

    prompt = f"""בעברית, המילים הבאות עלולות להתבלבל זו בזו עקב הגייה דומה: {candidates_str}

המשפט הבא נכתב על ידי ילד/ה:
"{sentence}"

המילה "{word}" שבמשפט - האם היא נכונה בהקשר הזה, או שהילד/ה התכוון/ה למילה אחרת מהרשימה?

אם המילה "{word}" נכונה ומתאימה להקשר - השב/השיבי בדיוק:
VALID

אם הילד/ה התכוון/ה למילה אחרת - השב/השיבי בפורמט הבא בדיוק (שתי שורות):
CORRECT: <המילה הנכונה שהתכוון/ה אליה>
TIP: <טיפ קצר וברור שמסביר מתי כותבים כל מילה, מבוסס על המשמעות וההקשר - לא רק על האיות>

השב/השיבי אך ורק בפורמט המדויק, בלי הסברים נוספים.
"""
    try:
        result = call_claude_raw(prompt, max_tokens=200)
        if result.strip().startswith("VALID"):
            return {"valid": True}
        correct_match = re.search(r'CORRECT:\s*(.+)', result)
        tip_match = re.search(r'TIP:\s*(.+)', result)
        if correct_match and tip_match:
            return {
                "valid": False,
                "correct": correct_match.group(1).strip(),
                "tip": tip_match.group(1).strip(),
            }
        print(f"Unexpected Claude response for context check: {result}")
        return {"valid": True}
    except Exception as e:
        print(f"Claude API error (context check): {e}")
        return {"valid": True}


def update_learned_confusable(user_id, word, was_correct):
    user_record = learned_confusables.setdefault(user_id, {})
    if was_correct:
        user_record[word] = user_record.get(word, 0) + 1
    else:
        user_record[word] = 0
    save_json(LEARNED_CONFUSABLES_PATH, learned_confusables)


def is_confusable_learned(user_id, word):
    user_record = learned_confusables.get(user_id, {})
    return user_record.get(word, 0) >= LEARNED_THRESHOLD


def check_text(text, user_id):
    words = text.strip().split()

    for i, word in enumerate(words):
        if word == "אני" and i + 1 < len(words):
            next_word = normalize(words[i + 1])
            if next_word.startswith("י"):
                corrected = "א" + next_word[1:]
                return f"אני {next_word}", f"אני {corrected}", ANI_VERB_TIP, "grammar"

    for word in words:
        clean = normalize(word)
        if not clean or not is_hebrew_only(clean):
            continue
        if clean in CONFUSABLE_LOOKUP and not is_confusable_learned(user_id, clean):
            result = check_word_in_context_with_claude(text, clean)
            if result["valid"]:
                update_learned_confusable(user_id, clean, was_correct=True)
                continue
            else:
                update_learned_confusable(user_id, clean, was_correct=False)
                return clean, result["correct"], result["tip"], "context"

    for word in words:
        clean = normalize(word)
        if not clean or not is_hebrew_only(clean):
            continue
        if clean in CONFUSABLE_LOOKUP:
            continue
        if is_known_word(clean):
            continue

        result = check_word_validity_with_claude(clean)
        if result["valid"]:
            growing_dictionary.add(clean)
            save_json(DICTIONARY_PATH, sorted(growing_dictionary))
            continue
        else:
            return clean, result["correct"], result["tip"], "spelling"

    return None, None, None, None


def send_whatsapp(to_number, message):
    if not to_number:
        print("Skipped sending - no phone number provided")
        return
    client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=to_number,
        body=message
    )


def build_lexi_blocks_prompt(mistakes):
    mistakes_list = "\n".join(
        f"- מילה שגויה: \"{m['wrong']}\" | מילה תקינה: \"{m['correct']}\""
        for m in mistakes
    )
    prompt = f"""את/ה לקסי, עוזר/ת כתיב לילדים ובני נוער. כתוב/כתבי בלשון א-מגדרית בלבד (ניטרלית), בטון ישיר וקליל אך לא מתיילד.

הנה רשימת שגיאות הכתיב שהילד/ה כתב/ה היום:
{mistakes_list}

עבור כל מילה ברשימה, כתוב/כתבי בלוק בפורמט הבא בדיוק (ללא כוכביות, ללא markdown - רק טקסט רגיל):
🎯 המילה התקינה (ולא המילה השגויה)
💎 טיפ: הסבר קצר וברור. אם זו שגיאת איות - מבוסס על שורש או משפחת מילים בעברית. אם זה בלבול בין שתי מילים תקינות - הסבר את ההבדל במשמעות ומתי כותבים כל אחת.

אחרי כל בלוק - שורת רווח ריקה מלאה. אל תשתמש בכוכביות (**) או בכל markdown אחר.

החזר/החזירי אך ורק את הבלוקים (בלי הקדמות, בלי הסברים).
"""
    return prompt


def build_challenge_sentence_prompt(challenge_words):
    words_str = ", ".join(f'"{w}"' for w in challenge_words)
    prompt = f"""כתוב/כתבי משפט אחד קצר, הגיוני וטבעי בעברית, שמשלב בתוכו את כל המילים הבאות: {words_str}.

המילים האלה חייבות להופיע במשפט בדיוק כפי שהן (אל תשני אותן). המשפט צריך להישמע טבעי לגמרי, כאילו ילד/ה כתב/ה אותו.

החזר/החזירי אך ורק את המשפט עצמו, בלי הקדמות, בלי גרשיים מיותרים, בלי כוכביות.
"""
    return prompt


def bold_words_whatsapp(sentence, words):
    for w in words:
        if w in sentence:
            sentence = sentence.replace(w, f"*{w}*")
    return sentence


def build_daily_summary_message(mistakes):
    today_weekday = datetime.now().weekday()
    opener = DAY_OPENERS.get(today_weekday, DAY_OPENERS[0])

    if not mistakes:
        return f"{opener}\n\n{random.choice(DAILY_WIN_MESSAGES)}"

    grammar = []
    other = []
    seen_grammar = set()
    seen_other = set()

    for m in mistakes:
        key = (m['wrong'], m['correct'])
        if m.get('category') == 'grammar':
            if key not in seen_grammar:
                seen_grammar.add(key)
                grammar.append(m)
        else:
            if key not in seen_other:
                seen_other.add(key)
                other.append(m)

    grammar_blocks = "\n\n".join(
        f"🎯 {m['correct']} ({m['wrong']})\n💎 טיפ: {m['tip']}"
        for m in grammar
    )

    other_body = ""
    if other:
        try:
            prompt = build_lexi_blocks_prompt(other)
            other_body = call_claude_raw(prompt, max_tokens=1000)
        except Exception as e:
            print(f"Claude API error (blocks): {e}")
            other_body = "\n\n".join(f"🎯 {m['correct']} ({m['wrong']})" for m in other)

    all_blocks = "\n\n".join(filter(None, [grammar_blocks, other_body]))

    challenge_words = ([m['correct'] for m in grammar] + [m['correct'] for m in other])[:4]
    try:
        challenge_prompt = build_challenge_sentence_prompt(challenge_words)
        challenge_raw = call_claude_raw(challenge_prompt, max_tokens=200)
        challenge_sentence = bold_words_whatsapp(challenge_raw, challenge_words)
    except Exception as e:
        print(f"Claude API error (challenge sentence): {e}")
        challenge_sentence = " ".join(f"*{w}*" for w in challenge_words)

    challenge_block = f"🏆 אתגר 50 הנקודות:\nפשוט להקליד לי את המשפט הבא נכון והנקודות אצלך:\n\"{challenge_sentence}\""

    return f"{opener}\n\n{all_blocks}\n\n{challenge_block}"


def build_weekly_summary_message_child(week_mistakes):
    if not week_mistakes:
        return WEEKLY_WIN_MESSAGE_CHILD

    seen = set()
    unique_words = []
    for m in week_mistakes:
        if m['correct'] not in seen:
            seen.add(m['correct'])
            unique_words.append(m['correct'])

    lines = [WEEKLY_OPENER_CHILD]
    for w in unique_words:
        lines.append(f"✅ {w}")
    return "\n".join(lines)


def build_weekly_summary_message_parent(week_mistakes):
    if not week_mistakes:
        return WEEKLY_WIN_MESSAGE_PARENT

    seen = set()
    unique_words = []
    for m in week_mistakes:
        if m['correct'] not in seen:
            seen.add(m['correct'])
            unique_words.append(m['correct'])

    lines = [
        WEEKLY_PARENT_OPENER,
        "",
        "השבוע זוהו כמה שגיאות כתיב בהודעות הוואטסאפ - כל אחת תוקנה והוצגה עם הסבר קצר. אלו המילים שתורגלו:",
        "",
    ]
    for w in unique_words:
        lines.append(f"✅ {w}")
    lines.append("")
    lines.append("שבוע טוב! 🚀")
    return "\n".join(lines)


@app.route('/check', methods=['POST'])
def check():
    if is_friday() or is_shabbat():
        return jsonify({"status": "rest_day_off"})

    data = request.get_json()
    text = data.get('text', '')
    user_id = data.get('user_id', 'unknown')

    print(f"Received from {user_id}: {text}")

    wrong, correct, tip, category = check_text(text, user_id)

    if wrong:
        print(f"Mistake found: {wrong} -> {correct}: {tip} [{category}]")
        entry = {
            "wrong": wrong,
            "correct": correct,
            "tip": tip,
            "category": category,
            "time": datetime.now().isoformat()
        }
        daily_mistakes.setdefault(user_id, []).append(entry)
        weekly_mistakes.setdefault(user_id, []).append(entry)
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

    if is_friday() or is_shabbat():
        return jsonify({"status": "skipped_rest_day"})

    results = {}
    for child_id, info in CHILDREN.items():
        mistakes = daily_mistakes.get(child_id, [])
        message = build_daily_summary_message(mistakes)
        send_whatsapp(info["phone"], message)
        results[child_id] = {"mistakes_count": len(mistakes), "sent": True}
        daily_mistakes[child_id] = []

    print(f"Daily summary sent: {results}")
    return jsonify({"status": "sent", "results": results})


@app.route('/send-weekly-summary', methods=['POST'])
def send_weekly_summary():
    secret = request.headers.get("X-Cron-Secret")
    if secret != os.environ.get("CRON_SECRET"):
        return jsonify({"status": "unauthorized"}), 401

    results = {}
    for child_id, info in CHILDREN.items():
        mistakes = weekly_mistakes.get(child_id, [])

        child_message = build_weekly_summary_message_child(mistakes)
        send_whatsapp(info["phone"], child_message)

        if info.get("parent_phone"):
            parent_message = build_weekly_summary_message_parent(mistakes)
            send_whatsapp(info["parent_phone"], parent_message)

        results[child_id] = {"mistakes_count": len(mistakes), "sent": True}
        weekly_mistakes[child_id] = []

    print(f"Weekly summary sent: {results}")
    return jsonify({"status": "sent", "results": results})


@app.route('/', methods=['GET'])
def health():
    return "SpellingCoach server is running!"


@app.route('/dictionary-stats', methods=['GET'])
def dictionary_stats():
    return jsonify({
        "base_words_count": len(base_words),
        "growing_dictionary_count": len(growing_dictionary),
        "learned_confusables": learned_confusables,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
