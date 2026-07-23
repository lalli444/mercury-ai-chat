import requests
import json
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, jsonify, stream_with_context

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

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle the user's message, send it to Mercury API,
    and return the AI's reply.
    """
    # 1. Get the user's message from the browser's POST request
    data = request.get_json()
    user_message = data.get('message', '')

    # 2. Validate that the message is not empty
    if not user_message:
        return jsonify({'reply': 'Please send a message.'}), 400

    # 3. Prepare the headers for the Mercury API
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 4. Prepare the payload (data) to send to Mercury
    #    - "model": which AI model to use
    #    - "messages": the conversation history
    #      * system: sets the assistant's personality (pirate!)
    #      * user: the user's actual question
    #    - "stream": False (we'll switch to True in the next lesson)
    payload = {
        "model": "mercury-2",
        "messages": [
   {"role": "system", "content": "You are Lalli AI, a helpful assistant. Always introduce yourself as Lalli AI."},
    {"role": "user", "content": user_message}
],
        "stream": False
    }

    try:
        # 5. Send the request to Mercury
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()   # Raises an error if status is not 200

        # 6. Parse the JSON response
        result = response.json()

        # 7. Extract the AI's reply from the nested structure
        bot_reply = result['choices'][0]['message']['content']

        # 8. Return the AI's reply as JSON to the browser
        return jsonify({'reply': bot_reply})

    except requests.exceptions.RequestException as e:
        # Network errors, timeouts, bad status codes, etc.
        print(f"Mercury API error: {e}")
        return jsonify({'reply': 'Sorry, I could not reach the AI service. Please try again later.'}), 500

    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error: {e}")
        return jsonify({'reply': 'An unexpected error occurred.'}), 500

# ====== RUN THE SERVER ======
if __name__ == '__main__':
    app.run(debug=True)