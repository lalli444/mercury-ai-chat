import requests
import json
import os
import bcrypt
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, jsonify, stream_with_context, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Chat
from chat_storage import get_chat, save_chat, create_new_chat, get_all_chats, delete_chat, rename_chat, search_chats

# Load environment variables from .env file

load_dotenv()


app = Flask(__name__)
@app.errorhandler(500)
def internal_error(error):
    print("🔥 500 Error:", error)
    import traceback
    traceback.print_exc()
    return "Internal Server Error", 500

# ====== CONFIGURATION ======
API_KEY = os.getenv('MERCURY_API_KEY')
API_URL = "https://api.inceptionlabs.ai/v1/chat/completions"

# Secret key for sessions (important for login)
app.secret_key = 'your-secret-key-here-change-this-in-production'

# Database configuration (SQLite)
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db.init_app(app)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # redirect to login page if not logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ====== PAGE ROUTES ======

@app.route('/')
@login_required
def home():
    """Render the main chat page (only for logged-in users)."""
    return render_template('index.html')

@app.route('/about')
def about():
    """Render the about page."""
    return render_template('about.html')


# ====== AUTHENTICATION ROUTES ======

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered. Please <a href='/login'>login</a>."
        
        # Hash the password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create new user
        new_user = User(email=email, password=hashed.decode('utf-8'), name=name)
        db.session.add(new_user)
        db.session.commit()
        
        # Log the user in automatically after registration
        login_user(new_user)
        return redirect('/')
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            return redirect('/')
        else:
            return "Invalid email or password. Please <a href='/login'>try again</a>."
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


# ====== CHAT API ENDPOINTS ======



@app.route('/api/chats', methods=['GET'])
@login_required
def api_get_chats():
    """Return list of all conversations for the logged-in user."""
    user_id = current_user.id
    chats = get_all_chats(user_id)
    return jsonify(chats)

@app.route('/api/chat/<chat_id>', methods=['GET'])
@login_required
def api_get_chat(chat_id):
    """Return all messages for a specific chat (only if it belongs to the user)."""
    user_id = current_user.id
    chat = get_chat(chat_id, user_id)
    if chat:
        return jsonify(chat)
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/chat', methods=['POST'])
@login_required
def api_create_chat():
    """Create a new empty chat for the logged-in user."""
    user_id = current_user.id
    title = request.json.get('title', 'New Chat')
    chat_id = create_new_chat(title, user_id)
    return jsonify({"id": chat_id, "title": title})

@app.route('/api/chat/<chat_id>', methods=['DELETE'])
@login_required
def api_delete_chat(chat_id):
    """Delete a chat (only if it belongs to the user)."""
    user_id = current_user.id
    if delete_chat(chat_id, user_id):
        return jsonify({"success": True})
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/chat/<chat_id>', methods=['PUT'])
@login_required
def api_rename_chat(chat_id):
    """Rename a chat (only if it belongs to the user)."""
    user_id = current_user.id
    new_title = request.json.get('title')
    if not new_title:
        return jsonify({"error": "Title required"}), 400
    if rename_chat(chat_id, new_title, user_id):
        return jsonify({"success": True})
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/search', methods=['GET'])
@login_required
def api_search():
    """Search for a query in all chat messages for the logged-in user."""
    user_id = current_user.id
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    results = search_chats(query, user_id)
    return jsonify(results)

# ====== MAIN CHAT ENDPOINT (with saving) ======
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    """
    Handle the user's message, send it to Mercury API,
    save the conversation, and return the AI's reply.
    """
    user_id = current_user.id  # <-- Get the logged-in user's ID
    
    # 1. Get the user's message and optional chat_id from the request
    data = request.get_json()
    user_message = data.get('message', '')
    chat_id = data.get('chat_id')

    if not user_message:
        return jsonify({'reply': 'Please send a message.'}), 400

    # 2. If no chat_id is provided, create a new chat for this user
    if not chat_id:
        chat_id = create_new_chat(user_id=user_id)
        chat_data = get_chat(chat_id, user_id)
        messages = []
    else:
        # Load existing chat (scoped to this user)
        chat_data = get_chat(chat_id, user_id)
        if not chat_data:
            # If chat_id is invalid or doesn't belong to this user, create a new one
            chat_id = create_new_chat(user_id=user_id)
            chat_data = get_chat(chat_id, user_id)
            messages = []
        else:
            messages = chat_data.get("messages", [])

    # 3. Append the user's message to the history
    messages.append({"role": "user", "content": user_message})

    # 4. Prepare the request to Mercury API
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mercury-2",
        "messages": [
            {"role": "system", "content": "You are Lalli AI, a helpful assistant."},
            *messages
        ],
        "stream": False
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        bot_reply = result['choices'][0]['message']['content']

        messages.append({"role": "assistant", "content": bot_reply})

        # 5. Save the chat (scoped to this user)
        title = chat_data.get("title", "New Chat")
        if len(messages) == 2:
            title = user_message[:30]
        save_chat(chat_id, title, messages, user_id)

        return jsonify({'reply': bot_reply, 'chat_id': chat_id})

    except requests.exceptions.RequestException as e:
        print(f"Mercury API error: {e}")
        return jsonify({'reply': 'Sorry, I could not reach the AI service. Please try again later.'}), 500

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'reply': 'An unexpected error occurred.'}), 500


# ====== RUN THE SERVER ======
if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        print("✅ Database tables created!")
    
    app.run(debug=True)