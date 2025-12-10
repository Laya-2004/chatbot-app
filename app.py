from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import time
from datetime import datetime
import requests
from markdown import markdown

app = Flask(__name__)

# Load static questions
with open('static_questions.json', 'r', encoding='utf-8') as f:
    STATIC_QUESTIONS = json.load(f)

# Chat history storage
CHAT_HISTORY = {}

# OpenRouter configuration
OPENROUTER_API_KEY = "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"  # Replace with your actual key
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "mistralai/mistral-7b-instruct"  # Using free model

def get_ai_response(prompt, chat_history=[]):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "user", "content": prompt}]
    
    # Include chat history for context
    if chat_history:
        for msg in chat_history[-4:]:  # Last 4 messages for context
            messages.insert(0, {
                "role": "user" if msg['sender'] == 'user' else 'assistant',
                "content": msg['content']
            })
    
    data = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return markdown(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        return f"Error getting AI response: {str(e)}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data['message']
    mode = data['mode']
    chat_id = data.get('chat_id', str(int(time.time())))
    
    if chat_id not in CHAT_HISTORY:
        CHAT_HISTORY[chat_id] = {
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'messages': [],
            'mode': mode,
            'title': user_message[:30] + ('...' if len(user_message) > 30 else '')
        }
    
    # Add user message to history
    CHAT_HISTORY[chat_id]['messages'].append({
        'sender': 'user',
        'content': user_message,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })
    
    # Get response based on mode
    if mode == 'static':
        response = STATIC_QUESTIONS.get(user_message.lower(), 
                                      "I don't have a predefined answer for that. Try switching to dynamic mode.")
    else:
        response = get_ai_response(user_message, CHAT_HISTORY[chat_id]['messages'])
    
    # Add bot response to history
    CHAT_HISTORY[chat_id]['messages'].append({
        'sender': 'bot',
        'content': response,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })
    
    # Update chat title if it's the first message
    if len(CHAT_HISTORY[chat_id]['messages']) == 2:  # First user + bot message
        CHAT_HISTORY[chat_id]['title'] = user_message[:30] + ('...' if len(user_message) > 30 else '')
    
    return jsonify({
        'response': response,
        'chat_id': chat_id,
        'title': CHAT_HISTORY[chat_id]['title'],
        'history': CHAT_HISTORY[chat_id]['messages']
    })

@app.route('/history', methods=['GET'])
def get_history():
    # Sort chats by most recent first
    sorted_chats = dict(sorted(CHAT_HISTORY.items(), 
                             key=lambda item: item[1]['created_at'], 
                             reverse=True))
    return jsonify({
        'chats': {k: {'created_at': v['created_at'], 
                     'mode': v['mode'],
                     'title': v['title']} 
                 for k, v in sorted_chats.items()}
    })

@app.route('/history/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    if chat_id in CHAT_HISTORY:
        return jsonify(CHAT_HISTORY[chat_id])
    return jsonify({'error': 'Chat not found'}), 404

@app.route('/history/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    if chat_id in CHAT_HISTORY:
        del CHAT_HISTORY[chat_id]
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Chat not found'}), 404

@app.route('/download/<chat_id>', methods=['GET'])
def download_chat(chat_id):
    if chat_id in CHAT_HISTORY:
        chat = CHAT_HISTORY[chat_id]
        content = f"Chat from {chat['created_at']} (Mode: {chat['mode']})\n\n"
        for msg in chat['messages']:
            content += f"[{msg['timestamp']}] {msg['sender'].title()}: {msg['content']}\n"
        
        filename = f"chat_{chat_id}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return send_file(filename, as_attachment=True)
    return jsonify({'error': 'Chat not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)