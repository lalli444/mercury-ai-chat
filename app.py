import requests
import json
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, jsonify, stream_with_context
from chat_storage import get_chat, save_chat, create_new_chat, get_all_chats, delete_chat, rename_chat, search_chats

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# ====== CONFIGURATION ======
API_KEY = os.getenv('MERCURY_API_KEY')
API_URL = "https://api.inceptionlabs.ai/v1/chat/completions"


# ====== ROUTES ======

@app.route('/')
def home():
    """Render the main chat page."""
    return render_template('index.html')

@app.route('/about')
def about():
    """Render the about page."""
    return render_template('about.html')


# ====== CHAT API ENDPOINTS ======

@app.route('/api/chats', methods=['GET'])
def api_get_chats():
    """Return list of all conversations (metadata only)."""
    chats = get_all_chats()
    return jsonify(chats)

@app.route('/api/chat/<chat_id>', methods=['GET'])
def api_get_chat(chat_id):
    """Return all messages for a specific chat."""
    chat = get_chat(chat_id)
    if chat:
        return jsonify(chat)
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/chat', methods=['POST'])
def api_create_chat():
    """Create a new empty chat."""
    title = request.json.get('title', 'New Chat')
    chat_id = create_new_chat(title)
    return jsonify({"id": chat_id, "title": title})

@app.route('/api/chat/<chat_id>', methods=['DELETE'])
def api_delete_chat(chat_id):
    """Delete a chat by its ID."""
    if delete_chat(chat_id):
        return jsonify({"success": True})
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/chat/<chat_id>', methods=['PUT'])
def api_rename_chat(chat_id):
    """Rename a chat."""
    new_title = request.json.get('title')
    if not new_title:
        return jsonify({"error": "Title required"}), 400
    if rename_chat(chat_id, new_title):
        return jsonify({"success": True})
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/search', methods=['GET'])
def api_search():
    """Search for a query in all chat messages."""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    results = search_chats(query)
    return jsonify(results)


# ====== MAIN CHAT ENDPOINT (with saving) ======

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle the user's message, send it to Mercury API,
    save the conversation, and return the AI's reply.
    """
    # 1. Get the user's message and optional chat_id from the request
    data = request.get_json()
    user_message = data.get('message', '')
    chat_id = data.get('chat_id')   # Optional – if not provided, create new chat

    if not user_message:
        return jsonify({'reply': 'Please send a message.'}), 400

    # 2. If no chat_id is provided, create a new chat
    if not chat_id:
        chat_id = create_new_chat()
        chat_data = get_chat(chat_id)
        messages = []
    else:
        # Load existing chat
        chat_data = get_chat(chat_id)
        if not chat_data:
            # If chat_id is invalid, create a new one
            chat_id = create_new_chat()
            chat_data = get_chat(chat_id)
            messages = []
        else:
            messages = chat_data.get("messages", [])

    # 3. Append the user's message to the history
    messages.append({"role": "user", "content": user_message})

    # 4. Prepare the request to Mercury API (using the full conversation history)
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mercury-2",
        "messages": [
            {"role": "system", "content": "You are Lalli AI, a helpful assistant."},
            *messages   # This includes all previous messages (user + bot)
        ],
        "stream": False
    }

    try:
        # 5. Send to Mercury
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        bot_reply = result['choices'][0]['message']['content']

        # 6. Append the bot's reply to the history
        messages.append({"role": "assistant", "content": bot_reply})

        # 7. Save everything back to the JSON file
        #    If this is the first message, use the user's message as the chat title
        title = chat_data.get("title", "New Chat")
        if len(messages) == 2:  # Only user + bot so far
            title = user_message[:30]  # First 30 characters as title
        save_chat(chat_id, title, messages)

        # 8. Return the reply AND the chat_id to the browser
        return jsonify({'reply': bot_reply, 'chat_id': chat_id})

    except requests.exceptions.RequestException as e:
        print(f"Mercury API error: {e}")
        return jsonify({'reply': 'Sorry, I could not reach the AI service. Please try again later.'}), 500

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'reply': 'An unexpected error occurred.'}), 500


# ====== RUN THE SERVER ======
if __name__ == '__main__':
    app.run(debug=True)