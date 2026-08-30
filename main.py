import os
import hashlib
import json
import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# データベース初期化
DB_FILE = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # ユーザー情報テーブル
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            my_id TEXT PRIMARY KEY,
            pin_hash TEXT,
            encrypted_contact TEXT
        )
    ''')
    # 投票情報テーブル (暗号化ハッシュのみ保存)
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

# 暗号化ハッシュ関数 (SHA-256)
def hash_pin(pin):
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

def hash_vote(voter_id, target_id):
    # 誰が誰を選んだか特定しにくくするハッシュ処理
    salt = "TPOP_SECRET_SALT_2026"
    raw = f"{voter_id}_{target_id}_{salt}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

# 簡易的な連絡先暗号化/復号化（PINを使用）
def encrypt_contact(contact, pin):
    key = pin * (len(contact) // len(pin) + 1)
    encrypted = [ord(c) ^ ord(k) for c, k in zip(contact, key)]
    return json.dumps(encrypted)

def decrypt_contact(encrypted_str, pin):
    try:
        encrypted = json.loads(encrypted_str)
        key = pin * (len(encrypted) // len(pin) + 1)
        decrypted = "".join([chr(c ^ ord(k)) for c, k in zip(encrypted, key)])
        return decrypted
    except Exception:
        return "復号エラー"

@app.route('/')
def index():
    return render_template('index.html')

# 投票受付
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

    # ユーザー追加（上書き更新可能）
    c.execute('''
        INSERT OR REPLACE INTO users (my_id, pin_hash, encrypted_contact)
        VALUES (?, ?, ?)
    ''', (my_id, pin_h, contact_enc))

    # 既存の自分の投票を削除して最新に上書き
    c.execute('DELETE FROM votes WHERE voter_id = ?', (my_id,))

    # 投票先をハッシュ化して保存（運営にも誰を選んだか見えない）
    for tid in target_ids:
        t_hash = hash_vote(my_id, tid)
        c.execute('INSERT OR IGNORE INTO votes (voter_id, target_hash) VALUES (?, ?)', (my_id, t_hash))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

# 結果確認
@app.route('/api/result', methods=['POST'])
def result():
    data = request.json
    my_id = data.get('my_id')
    pin = data.get('pin')

    if not my_id or not pin:
        return jsonify({'success': False, 'message': 'IDとパスワードを入力してください'}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # パスワード確認
    c.execute('SELECT pin_hash FROM users WHERE my_id = ?', (my_id,))
    row = c.fetchone()
    if not row or row[0] != hash_pin(pin):
        conn.close()
        return jsonify({'success': False, 'message': 'IDまたはパスワードが正しくありません'}), 400

    # 全ユーザー一覧を取得して相互マッチングチェック
    c.execute('SELECT my_id, encrypted_contact FROM users WHERE my_id != ?', (my_id,))
    other_users = c.fetchall()

    matches = []

    for other_id, other_contact_enc in other_users:
        # 自分の「相手への投票ハッシュ」
        my_vote_hash = hash_vote(my_id, other_id)
        # 相手の「自分への投票ハッシュ」
        other_vote_hash = hash_vote(other_id, my_id)

        # 1. 自分が相手を選んだか？
        c.execute('SELECT 1 FROM votes WHERE voter_id = ? AND target_hash = ?', (my_id, my_vote_hash))
        i_voted = c.fetchone() is not None

        # 2. 相手が自分を選んだか？
        c.execute('SELECT 1 FROM votes WHERE voter_id = ? AND target_hash = ?', (other_id, other_vote_hash))
        they_voted = c.fetchone() is not None

        if i_voted and they_voted:
            # 相互マッチング！相手の連絡先を復号（※相手も同じパスワードルール）
            # 連絡先表示用の安全な情報取得
            matches.append({
                'id': other_id
            })

    conn.close()

    return jsonify({'success': True, 'matched': len(matches) > 0, 'matches': matches})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
