import os
import hashlib
import json
import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DB_FILE = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            my_id TEXT PRIMARY KEY,
            pin_hash TEXT,
            encrypted_contact TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            voter_id TEXT,
            target_hash TEXT,
            PRIMARY KEY (voter_id, target_hash)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def hash_pin(pin):
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

def hash_vote(voter_id, target_id):
    salt = "TPOP_SECRET_SALT_2026"
    raw = f"{voter_id}_{target_id}_{salt}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

# 連絡先の文字シフト暗号化/復号化（運営もすぐ解読不可）
def encrypt_contact(contact, pin):
    return "".join([chr(ord(c) + int(pin[i % len(pin)])) for i, c in enumerate(contact)])

def decrypt_contact(encrypted_str, pin):
    try:
        return "".join([chr(ord(c) - int(pin[i % len(pin)])) for i, c in enumerate(encrypted_str)])
    except Exception:
        return encrypted_str

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vote', methods=['POST'])
def vote():
    data = request.json
    my_id = data.get('my_id')
    pin = data.get('pin')
    contact = data.get('contact')
    target_ids = data.get('target_ids', [])

    if not my_id or not pin or not contact:
        return jsonify({'success': False, 'message': '必須項目を入力してください'}), 400

    pin_h = hash_pin(pin)
    contact_enc = encrypt_contact(contact, pin)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''
        INSERT OR REPLACE INTO users (my_id, pin_hash, encrypted_contact)
        VALUES (?, ?, ?)
    ''', (my_id, pin_h, contact_enc))

    c.execute('DELETE FROM votes WHERE voter_id = ?', (my_id,))

    for tid in target_ids:
        t_hash = hash_vote(my_id, tid)
        c.execute('INSERT OR IGNORE INTO votes (voter_id, target_hash) VALUES (?, ?)', (my_id, t_hash))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/result', methods=['POST'])
def result():
    data = request.json
    my_id = data.get('my_id')
    pin = data.get('pin')

    if not my_id or not pin:
        return jsonify({'success': False, 'message': 'IDとパスワードを入力してください'}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('SELECT pin_hash FROM users WHERE my_id = ?', (my_id,))
    row = c.fetchone()
    if not row or row[0] != hash_pin(pin):
        conn.close()
        return jsonify({'success': False, 'message': 'IDまたはパスワードが正しくありません'}), 400

    c.execute('SELECT my_id, encrypted_contact FROM users WHERE my_id != ?', (my_id,))
    other_users = c.fetchall()

    matches = []

    for other_id, other_contact_enc in other_users:
        my_vote_hash = hash_vote(my_id, other_id)
        other_vote_hash = hash_vote(other_id, my_id)

        c.execute('SELECT 1 FROM votes WHERE voter_id = ? AND target_hash = ?', (my_id, my_vote_hash))
        i_voted = c.fetchone() is not None

        c.execute('SELECT 1 FROM votes WHERE voter_id = ? AND target_hash = ?', (other_id, other_vote_hash))
        they_voted = c.fetchone() is not None

        if i_voted and they_voted:
            matches.append({
                'id': other_id,
                'contact': other_contact_enc  # 暗号化された連絡先を返しフロントで解読
            })

    conn.close()

    return jsonify({'success': True, 'matched': len(matches) > 0, 'matches': matches})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
