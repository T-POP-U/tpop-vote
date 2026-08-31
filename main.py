from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 簡易メモリデータベース（本番運用時はSQLiteやPostgreSQL等に永続化してください）
votes = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vote', methods=['POST'])
def vote():
    data = request.get_json()
    my_id = data.get('my_id')
    pin = data.get('pin')
    contact = data.get('contact')
    target_ids = data.get('target_ids', [])
    messages = data.get('messages', {})  # 例: {"M-1": "よろしく！", "M-2": "話しましょう"}

    if not my_id or not pin or not contact:
        return jsonify({'message': '必須項目が不足しています'}), 400

    # 投票データの保存・更新
    votes[my_id] = {
        'pin': pin,
        'contact': contact,
        'targets': target_ids,
        'messages': messages
    }

    return jsonify({'message': '投票が正常に完了しました'}), 200

@app.route('/api/result', methods=['POST'])
def result():
    data = request.get_json()
    my_id = data.get('my_id')
    pin = data.get('pin')

    if not my_id or not pin:
        return jsonify({'message': 'IDとパスワードを入力してください'}), 400

    user_data = votes.get(my_id)
    if not user_data:
        return jsonify({'message': '投票データが見つかりません'}), 404

    if user_data['pin'] != pin:
        return jsonify({'message': 'パスワードが正しくありません'}), 401

    my_targets = user_data.get('targets', [])
    matches = []

    # 相互マッチング判定
    for target_id in my_targets:
        target_data = votes.get(target_id)
        if target_data and my_id in target_data.get('targets', []):
            # お相手が自分(my_id)宛てに書いたメッセージを取得
            partner_msg = target_data.get('messages', {}).get(my_id, '')
            matches.append({
                'id': target_id,
                'contact': target_data.get('contact', ''),
                'message': partner_msg
            })

    if len(matches) > 0:
        return jsonify({
            'matched': True,
            'matches': matches
        }), 200
    else:
        return jsonify({
            'matched': False
        }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
