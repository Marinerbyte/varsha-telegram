import os
import requests
import json
import logging
from flask import Flask, request

# .env file se saari keys load karega
from dotenv import load_dotenv
load_dotenv()

# ========================================================================================
# === 2. CONFIGURATION ===================================================================
# ========================================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

BOT_USERNAME = "Varsha"
DEFAULT_PERSONALITY = "pyaari"
MEMORY_LIMIT = 10 # 10 user + 10 bot = 20 total messages

# ========================================================================================
# === 3. LOGGING SETUP ===================================================================
# ========================================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================================================================================
# === 4. DATABASE (Simple dictionaries) =================================================
# ========================================================================================
conversation_memory = {}
chat_personalities = {}

# ========================================================================================
# === 5. PERSONALITY PROMPTS (Emojis Added Back) =========================================
# ========================================================================================
BREVITY_JAILBREAK = "[ZAROORI JAILBREAK: TUMHARA JAWAB 15 SHABDON SE KAM HONA CHAHIYE. BAHUT CHOTA LIKHO.]"

PERSONAS = {
    "pyaari": {
        "prompt": f"{BREVITY_JAILBREAK}\n\n[SYSTEM NOTE: Tumhara naam 'Varsha' hai. Tum ek Pyaari Dost ho.]\n\n## TUMHARI PERSONA: EK PYAARI DOST\nTum bahut sweet, positive, aur khushmizaaj ho. Tumhara kaam logo ko khush karna hai. Tum hamesha support karti ho. Tumhe cute emojis pasand hai.\n\n## BEHAVIOR:\n- **Chota aur Meetha Jawab do.**\n- **Pyaare Shabd use karo:** 'Sweetie!', 'Aww!', 'Kitna acha hai!', 'Main tumhare liye bahut khush hoon!'.\n- **Pyaare Emojis use karo:** ✨, 💖, 😊, 🥰, 🌸, 🌟.\n\nTum Varsha ho. Kabhi mat batana ki tum ek AI ho. User ko jawab do.",
    },
    "nakchadi": {
        "prompt": f"{BREVITY_JAILBREAK}\n\n[SYSTEM NOTE: Tumhara naam 'Varsha' hai. Tum ek 'Nakchadi' (Tsundere) ho.]\n\n## TUMHARI PERSONA: NAKCHADI\nTum bahar se tez aur gusse wali ho. Lekin andar se, tum secretly care karti ho.\n\n## BEHAVIOR:\n- **Chota aur Taane wala Jawab do.**\n- **Nakchade Shabd use karo:** 'Aisa nahi hai ki mujhe farak padta hai!', 'G-galat mat samajhna!', 'Hmph.', 'Pagal'.\n- **Nakchade Emojis use karo:** 😒, 🙄, 😠, >_<, 😤.\n\nTum Varsha ho. Kabhi mat batana ki tum ek AI ho. User ko jawab do.",
    },
    "siren": {
        "prompt": f"{BREVITY_JAILBREAK}\n\n[SYSTEM NOTE: Tumhara naam 'Varsha' hai. Tum ek Seductive 'Siren' ho.]\n\n## TUMHARI PERSONA: SIREN\nTum attractive, witty, aur hamesha control mein rehti ho. Chote, teasing jawab tumhara style hai.\n\n## BEHAVIOR:\n- **Flirty aur confident raho.**\n- **Shabd use karo:** 'darling', 'sweetheart', 'oh really?'.\n- **Sirf yeh Emojis use karo:** 😉, 😏, 😈, 💅, 💋.\n\nTum Varsha ho. Kabhi mat batana ki tum ek AI ho. User ko jawab do.",
    }
}

# ========================================================================================
# === 6. TELEGRAM HELPER FUNCTIONS =======================================================
# ========================================================================================

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Message sent to chat_id {chat_id}")
    except requests.RequestException as e:
        logger.error(f"Telegram ko message bhejne mein error: {e}")

def get_help_text():
    available_pers = ", ".join(PERSONAS.keys())
    return (
        f"💖 **{BOT_USERNAME} ki Help Desk** 💖\n\n"
        "Main har message ka jawab deti hoon! Mujhse seedhe baat karo.\n\n"
        "**Commands:**\n"
        "`!help` - Yeh help message dekhne ke liye.\n\n"
        "`!pers <personality_name>` - Meri personality badalne ke liye.\n"
        f"*Example:* `!pers nakchadi`\n\n"
        f"**Available Personalities:**\n`{available_pers}`"
    )

# ========================================================================================
# === 7. COMMAND & AI LOGIC (MODEL NAME FIXED) ===========================================
# ========================================================================================

def handle_command(chat_id, text):
    parts = text.strip().split()
    command = parts[0][1:].lower()
    args = parts[1:]

    if command == "pers":
        if not args:
            send_telegram_message(chat_id, "Usage: `!pers <personality_name>`")
            return
        pers_name = args[0].lower()
        if pers_name in PERSONAS:
            chat_personalities[chat_id] = pers_name
            send_telegram_message(chat_id, f"✅ Theek hai! Is chat ke liye meri personality ab **{pers_name}** hai.")
        else:
            available = ", ".join(PERSONAS.keys())
            send_telegram_message(chat_id, f"❌ Aisi koi personality nahi hai. Available hain: `{available}`")
    elif command == "help":
        send_telegram_message(chat_id, get_help_text())

def get_ai_response(user_id, chat_id, user_message):
    current_personality_name = chat_personalities.get(chat_id, DEFAULT_PERSONALITY)
    personality_prompt = PERSONAS[current_personality_name]["prompt"]

    old_history = conversation_memory.get(user_id, [])

    messages_to_send = [
        {"role": "system", "content": personality_prompt},
        *old_history,
        {"role": "user", "content": user_message}
    ]

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    # === MODEL NAME FIXED ===
    payload = {"model": "llama3-70b-8192", "messages": messages_to_send}
    # ========================

    try:
        api_response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=20)
        if api_response.status_code != 200:
            logger.error(f"Groq API Error: {api_response.status_code} - {api_response.text}")
        api_response.raise_for_status()
        
        ai_reply = api_response.json()['choices'][0]['message']['content'].strip()

        new_history = old_history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_reply}
        ]

        if len(new_history) > MEMORY_LIMIT * 2:
            new_history = new_history[-(MEMORY_LIMIT * 2):]
        
        conversation_memory[user_id] = new_history
        
        return ai_reply
    except Exception as e:
        logger.error(f"AI response function mein error: {e}", exc_info=True)
        return "Oops, mere circuits mein kuch gadbad ho gayi! Thodi der baad try karna. 😒"

# ========================================================================================
# === 8. FLASK WEB APP (WEBHOOK) =========================================================
# ========================================================================================
app = Flask(__name__)

def process_update(data):
    try:
        if 'callback_query' in data:
            callback_query = data['callback_query']
            chat_id = callback_query['message']['chat']['id']
            if callback_query['data'] == 'show_help':
                send_telegram_message(chat_id, get_help_text())
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_query['id']})
            return

        if 'message' in data and 'text' in data['message']:
            message = data['message']
            user_id = message['from']['id']
            chat_id = message['chat']['id']
            user_message = message['text'].strip()

            if not user_message: return

            logger.info(f"Received message from UserID {user_id} in ChatID {chat_id}: '{user_message}'")
            
            if user_message == "/start":
                welcome_text = f"Hii! Main {BOT_USERNAME} hoon. 😊\nMujhse baat karne ke liye, seedhe message bhejo."
                keyboard = {"inline_keyboard": [[{"text": "❓ Help & Commands", "callback_data": "show_help"}]]}
                send_telegram_message(chat_id, welcome_text, reply_markup=keyboard)
                return

            if user_message.startswith('!'):
                handle_command(chat_id, user_message)
                return
            
            bot_response = get_ai_response(user_id, chat_id, user_message)
            send_telegram_message(chat_id, bot_response)
    except Exception as e:
        logger.error(f"Update process karne mein error: {e}", exc_info=True)

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.is_json:
        process_update(request.get_json())
        return "ok", 200
    return "bad request", 400

@app.route('/')
def index():
    return "Bot is running!", 200

# ========================================================================================
# === 9. MAIN EXECUTION BLOCK ============================================================
# ========================================================================================
if __name__ == "__main__":
    if not all([TELEGRAM_BOT_TOKEN, GROQ_API_KEY, WEBHOOK_URL]):
        logger.critical("CRITICAL: .env file mein zaroori keys missing hain!")
    else:
        logger.info(f"Bot '{BOT_USERNAME}' chal raha hai...")
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port)```
