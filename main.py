from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    my_id = db.Column(db.String(10), nullable=False)
    pin = db.Column(db.String(10), nullable=False)
    contact = db.Column(db.String(200), nullable=False)
    target_id = db.Column(db.String(10), nullable=False)
    message = db.Column(db.Text, nullable=True)
    allow_unrequited = db.Column(db.Boolean, default=False)  # 片思い送信を許可するか

with app.app_context():
    db.create_all()

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
    messages = data.get('messages', {})
    allow_unrequited_map = data.get('allow_unrequited', {})  # { "M-1": True, ... }

    if not my_id or not pin or not contact:
        return jsonify({'message': '必須項目が不足しています'}), 400

    # 既存の自分の投票を削除して上書き更新
    Vote.query.filter_by(my_id=my_id).delete()

    for target in target_ids:
        msg = messages.get(target, "")
        allow_unreq = allow_unrequited_map.get(target, False)
        new_vote = Vote(
            my_id=my_id,
            pin=pin,
            contact=contact,
            target_id=target,
            message=msg,
            allow_unrequited=allow_unreq
        )
        db.session.add(new_vote)

    db.session.commit()
    return jsonify({'message': '投票が完了しました'})

@app.route('/api/result', methods=['POST'])
def result():
    data = request.json
    my_id = data.get('my_id')
    pin = data.get('pin')

    # パスワードの照合
    my_vote = Vote.query.filter_by(my_id=my_id).first()
    if not my_vote:
        return jsonify({'message': '投票データが見つかりません'}), 404
    if my_vote.pin != pin:
        return jsonify({'message': 'パスワードが違います'}), 401

    # 自分が投票した相手一覧
    my_targets = [v.target_id for v in Vote.query.filter_by(my_id=my_id).all()]

    # 自分に投票してくれた人たちを取得
    votes_to_me = Vote.query.filter_by(target_id=my_id).all()

    matched_results = []
    unrequited_results = []

    for v in votes_to_me:
        sender_id = v.my_id
        sender_contact = v.contact
        sender_message = v.message
        sender_allow_unreq = v.allow_unrequited

        if sender_id in my_targets:
            # 両思い（マッチング成立）
            matched_results.append({
                'id': sender_id,
                'contact': sender_contact,
                'message': sender_message
            })
        else:
            # 片思い（相手が自分を選んでおり、かつ片思い送信を許可している場合）
            if sender_allow_unreq:
                unrequited_results.append({
                    'id': sender_id,
                    'contact': sender_contact,
                    'message': sender_message
                })

    is_matched = len(matched_results) > 0
    has_unrequited = len(unrequited_results) > 0

    return jsonify({
        'matched': is_matched,
        'matches': matched_results,
        'has_unrequited': has_unrequited,
        'unrequited_approaches': unrequited_results
    })

if __name__ == '__main__':
    app.run(debug=True)
