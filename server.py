from flask import Flask, request, jsonify
import re

app = Flask(__name__)

COMMON_MISTAKES = {
    "בסדר": ["בסדר"],
    "אוכל": ["אוכל"],
    "ילד": ["ילד"],
}

def check_spelling(text):
    mistakes = []
    words = text.split()
    for word in words:
        clean_word = re.sub(r'[^\u05d0-\u05ea]', '', word)
        if clean_word in COMMON_MISTAKES:
            continue
    return mistakes

@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    text = data.get('text', '')
    user_id = data.get('user_id', 'unknown')
    
    print(f"Received from {user_id}: {text}")
    
    return jsonify({
        "status": "ok",
        "text": text,
        "user_id": user_id
    })

@app.route('/', methods=['GET'])
def health():
    return "SpellingCoach server is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
