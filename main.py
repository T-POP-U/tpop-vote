import json
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_order=True, primary_key=True)
    my_id = db.Column(db.String(20), unique=True, nullable=False)
    pin = db.Column(db.String(10), nullable=False)
    contact = db.Column(db.Text, nullable=False)
    target_ids = db.Column(db.Text, nullable=True) # JSON string
    messages = db.Column(db.Text, nullable=True)   # JSON string
    allow_unrequited = db.Column(db.Text, nullable=True) # JSON string

with app.app_context():
    db.create_all()

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
    messages = data.get('messages', {})
    allow_unrequited = data.get('allow_unrequited', {})

    if not my_id or not pin or not contact:
        return jsonify({'message': '必須項目が不足しています'}), 400

    existing_vote = Vote.query.filter_by(my_id=my_id).first()
    if existing_vote:
        existing_vote.pin = pin
        existing_vote.contact = contact
        existing_vote.target_ids = json.dumps(target_ids)
        existing_vote.messages = json.dumps(messages)
        existing_vote.allow_unrequited = json.dumps(allow_unrequited)
    else:
        new_vote = Vote(
            my_id=my_id,
            pin=pin,
            contact=contact,
            target_ids=json.dumps(target_ids),
            messages=json.dumps(messages),
            allow_unrequited=json.dumps(allow_unrequited)
        )
        db.session.add(new_vote)

    db.session.commit()
    return jsonify({'message': '投票が成功しました'})

@app.route('/api/result', methods=['POST'])
def result():
    data = request.get_json()
    my_id = data.get('my_id')
    pin = data.get('pin')

    user = Vote.query.filter_by(my_id=my_id, pin=pin).first()
    if not user:
        return jsonify({'message': 'IDまたはパスワードが正しくありません'}), 400

    user_targets = json.loads(user.target_ids) if user.target_ids else []
    
    # 1. 両思い（相互マッチング）判定
    all_votes = Vote.query.all()
    matches = []
    for other in all_votes:
        if other.my_id == my_id:
            continue
        other_targets = json.loads(other.target_ids) if other.target_ids else []
        if other.my_id in user_targets and my_id in other_targets:
            other_msgs = json.loads(other.messages) if other.messages else {}
            matches.append({
                'id': other.my_id,
                'contact': other.contact,
                'message': other.msgs.get(my_id, '') if hasattr(other, 'msgs') else other_msgs.get(my_id, '')
            })

    # 2. アプローチ受領（片思い受領）判定
    unrequited_approaches = []
    matched_ids = [m['id'] for m in matches]
    for other in all_votes:
        if other.my_id == my_id or other.my_id in matched_ids:
            continue
        other_targets = json.loads(other.target_ids) if other.target_ids else []
        other_unreq = json.loads(other.allow_unrequited) if other.allow_unrequited else {}
        if my_id in other_targets and other_unreq.get(my_id, False):
            other_msgs = json.loads(other.messages) if other.messages else {}
            unrequited_approaches.append({
                'id': other.my_id,
                'contact': other.contact,
                'message': other_msgs.get(my_id, '')
            })

    # 3. 自分が「片思い送信」を1つでも設定していたか判定
    sent_unrequited = False
    if user.allow_unrequited:
        try:
            unreq_dict = json.loads(user.allow_unrequited)
            sent_unrequited = any(unreq_dict.values())
        except Exception:
            sent_unrequited = False

    return jsonify({
        'matched': len(matches) > 0,
        'matches': matches,
        'has_unrequited': len(unrequited_approaches) > 0,
        'unrequited_approaches': unrequited_approaches,
        'sent_unrequited': sent_unrequited
    })

if __name__ == '__main__':
    app.run(debug=True)
