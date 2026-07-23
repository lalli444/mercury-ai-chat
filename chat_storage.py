import json
import os
from datetime import datetime
import uuid

CHATS_DIR = "chats"
os.makedirs(CHATS_DIR, exist_ok=True)

def get_chat_file(chat_id):
    return os.path.join(CHATS_DIR, f"{chat_id}.json")

def get_all_chats():
    """Return list of chat metadata: id, title, last_updated, message_count"""
    chats = []
    for filename in os.listdir(CHATS_DIR):
        if filename.endswith(".json"):
            chat_id = filename[:-5]
            with open(os.path.join(CHATS_DIR, filename), 'r') as f:
                data = json.load(f)
                chats.append({
                    "id": chat_id,
                    "title": data.get("title", "New Chat"),
                    "last_updated": data.get("last_updated"),
                    "message_count": len(data.get("messages", []))
                })
    # Sort by last_updated descending
    chats.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
    return chats

def get_chat(chat_id):
    filepath = get_chat_file(chat_id)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r') as f:
        return json.load(f)

def save_chat(chat_id, title, messages):
    filepath = get_chat_file(chat_id)
    data = {
        "id": chat_id,
        "title": title,
        "messages": messages,
        "last_updated": datetime.now().isoformat()
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return data

def create_new_chat(title="New Chat"):
    chat_id = str(uuid.uuid4())[:8]  # short unique id
    messages = []  # start empty
    save_chat(chat_id, title, messages)
    return chat_id

def delete_chat(chat_id):
    filepath = get_chat_file(chat_id)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False

def rename_chat(chat_id, new_title):
    chat = get_chat(chat_id)
    if chat:
        chat["title"] = new_title
        save_chat(chat_id, new_title, chat["messages"])
        return True
    return False

def search_chats(query):
    """Search all messages for query, return chat_ids where found."""
    results = []
    for filename in os.listdir(CHATS_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(CHATS_DIR, filename), 'r') as f:
                data = json.load(f)
                for msg in data.get("messages", []):
                    if query.lower() in msg.get("content", "").lower():
                        results.append({
                            "chat_id": data["id"],
                            "title": data["title"],
                            "matched_message": msg["content"][:100] + "..."
                        })
                        break  # one match per chat is enough
    return results