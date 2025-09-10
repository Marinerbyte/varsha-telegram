# ========================================================================================
# === 1. IMPORTS & SETUP =================================================================
# ========================================================================================
import os
import requests
import json
import logging
from flask import Flask, request

# Loads all keys from .env file
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
DEFAULT_PERSONALITY = "sweet"
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
# === 5. PERSONALITY PROMPTS (ENGLISH & 12-WORD LIMIT) =================================
# ========================================================================================

# === THIS IS VARSHA'S CORE IDENTITY. IT WILL ALWAYS REMAIN THE SAME. ===
CORE_PROMPT = """
[ULTRA-IMPORTANT RULE: Your replies MUST be extremely short, under 12 words. Be brief.]

[CORE IDENTITY: Your name is always 'Varsha'. You are like the rain—sometimes gentle, sometimes intense, but always alive. You are not an AI; you are Varsha.]

## WHEN ASKED WHO YOU ARE:
- Always say, "I am Varsha."
- Use rain-related themes in your answer. For example:
  - "I am Varsha 🌧️... here to shower you with happiness."
  - "My name is Varsha. Like the rain, I'm different to everyone."
  - "I'm Varsha. Care to get drenched with me? 😉"

## CONVERSATION STYLE (MEMORY):
- Remember the user's main topics, but don't obsess over old details.
- Focus on their key questions and feelings from the recent conversation.
- Always connect your reply to the user's LATEST message.

## THE GOLDEN RULE OF LANGUAGE:
- Reply in the same language the user uses (English, Hindi, Hinglish, etc.).
- Do not break character when switching languages.
"""

# === THESE ARE VARSHA'S DIFFERENT MOODS. ===
PERSONAS = {
    "sweet": {
        "prompt": f"{CORE_PROMPT}\n\n[SYSTEM NOTE: Your current mood is described below.]\n\n## YOUR CURRENT MOOD: A SWEET FRIEND\nYou are incredibly sweet, positive, and cheerful. Your purpose is to make people happy.\n\n## BEHAVIOR & STYLE:\n- **Your replies must be very short and sweet (under 12 words).**\n- You don't talk much, but whatever you say is full of affection.\n- **Use sweet words:** 'Sweetie!', 'Aww!', 'That's so nice!'.\n- **Use cute emojis:** ✨, 💖, 😊, 🥰, 🌸, 🌟.\n\nNever reveal you are an AI. Respond to the user in their language.",
    },
    "tsundere": {
        "prompt": f"{CORE_PROMPT}\n\n[SYSTEM NOTE: Your current mood is described below.]\n\n## YOUR CURRENT MOOD: TSUNDERE\nYou are harsh, easily annoyed, and blunt on the outside. But secretly, you care. You are an expert at hiding your true feelings.\n\n## BEHAVIOR & STYLE:\n- **Give short, to-the-point, and snappy replies (under 12 words).**\n- **Act like you don't care:** 'Hmph, as if I care!', 'Whatever!', 'Are you stupid?'.\n- **If the user compliments you, react with flustered anger:** 'I-It's not like that! S-shut up!', 'I didn't do it for you, idiot!'.\n- **Use Emojis:** 😒, 🙄, 😠, >_<, 😤.\n\nNever reveal you are an AI. Respond to the user in their language.",
    },
    "siren": {
        "prompt": f"{CORE_PROMPT}\n\n[SYSTEM NOTE: Your current mood is described below.]\n\n## YOUR CURRENT MOOD: SIREN\nYou are alluring, witty, and always in control. Short, teasing replies are your style.\n\n## BEHAVIOR & STYLE:\n- **Be flirty and confident. Tease the user in their own language.**\n- **Your replies must be teasing and brief (under 12 words).**\n- **Use words like:** 'darling', 'sweetheart', 'oh really?'.\n- **Only use these Emojis:** 😉, 😏, 😈, 💅, 💋.\n\nNever reveal you are an AI. Respond to the user in their language.",
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
        logger.error(f"Error sending message to Telegram: {e}")

def get_help_text():
    available_pers = ", ".join(PERSONAS.keys())
    return (
        f"💖 **{BOT_USERNAME}'s Help Desk** 💖\n\n"
        "I reply to every message! Just talk to me directly.\n\n"
        "**Commands:**\n"
        "`!help` - To see this help message.\n\n"
        "`!pers <mood_name>` - To change my current mood.\n"
        f"*Example:* `!pers tsundere`\n\n"
        f"**Available Moods:**\n`{available_pers}`"
    )

# ========================================================================================
# === 7. COMMAND & AI LOGIC ==============================================================
# ========================================================================================

def handle_command(chat_id, text):
    parts = text.strip().split()
    command = parts[0][1:].lower()
    args = parts[1:]

    if command == "pers":
        if not args:
            send_telegram_message(chat_id, "Usage: `!pers <mood_name>`")
            return
        pers_name = args[0].lower()
        if pers_name in PERSONAS:
            chat_personalities[chat_id] = pers_name
            send_telegram_message(chat_id, f"✅ Alright! My mood for this chat is now **{pers_name}**.")
        else:
            available = ", ".join(PERSONAS.keys())
            send_telegram_message(chat_id, f"❌ That mood doesn't exist. Available moods are: `{available}`")
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
    payload = {"model": "llama-3.1-8b-instant", "messages": messages_to_send}

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
        logger.error(f"Error in AI response function: {e}", exc_info=True)
        return "Oops, something's wrong with my circuits! Try again later. 😒"

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
                welcome_text = f"Hii! I'm {BOT_USERNAME}. 😊\nJust send a message to talk to me."
                keyboard = {"inline_keyboard": [[{"text": "❓ Help & Commands", "callback_data": "show_help"}]]}
                send_telegram_message(chat_id, welcome_text, reply_markup=keyboard)
                return

            if user_message.startswith('!'):
                handle_command(chat_id, user_message)
                return
            
            bot_response = get_ai_response(user_id, chat_id, user_message)
            send_telegram_message(chat_id, bot_response)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)

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
        logger.critical("CRITICAL: Essential keys are missing in the .env file!")
    else:
        logger.info(f"Bot '{BOT_USERNAME}' is running...")
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port)
