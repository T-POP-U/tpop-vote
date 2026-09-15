import json
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    my_id = db.Column(db.String(20), unique=True, nullable=False)
    pin = db.Column(db.String(10), nullable=False)
    contact = db.Column(db.Text, nullable=False)
    target_ids = db.Column(db.Text, nullable=True)
    messages = db.Column(db.Text, nullable=True)

with app.app_context():
    db.create_all()

def is_opposite_sex(my_id, target_id):
    return ((my_id.startswith('M-') and target_id.startswith('F-')) or
            (my_id.startswith('F-') and target_id.startswith('M-')))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vote', methods=['POST'])
def vote():
    data = request.get_json(silent=True) or {}
    my_id = str(data.get('my_id', '')).strip()
    pin = str(data.get('pin', '')).strip()
    contact = str(data.get('contact', '')).strip()
    target_ids = data.get('target_ids', [])
    messages = data.get('messages', {})

    if not my_id or not pin or not contact:
        return jsonify({'success': False, 'message': '必須項目が不足しています'}), 400
    if not pin.isdigit() or len(pin) != 4:
        return jsonify({'success': False, 'message': 'パスワードは数字4桁で入力してください'}), 400

    if not isinstance(target_ids, list):
        target_ids = []
    target_ids = list(dict.fromkeys(
        x for x in target_ids
        if isinstance(x, str) and x != my_id and is_opposite_sex(my_id, x)
    ))

    if not isinstance(messages, dict):
        messages = {}
    clean_messages = {}
    for target_id in target_ids:
        msg = messages.get(target_id, '')
        if isinstance(msg, str) and msg.strip():
            clean_messages[target_id] = msg.strip()[:100]

    row = Vote.query.filter_by(my_id=my_id).first()
    if row:
        row.pin = pin
        row.contact = contact
        row.target_ids = json.dumps(target_ids, ensure_ascii=False)
        row.messages = json.dumps(clean_messages, ensure_ascii=False)
    else:
        db.session.add(Vote(
            my_id=my_id, pin=pin, contact=contact,
            target_ids=json.dumps(target_ids, ensure_ascii=False),
            messages=json.dumps(clean_messages, ensure_ascii=False)
        ))
    db.session.commit()
    return jsonify({'success': True, 'message': '送信が完了しました'})

@app.route('/api/result', methods=['POST'])
def result():
    data = request.get_json(silent=True) or {}
    my_id = str(data.get('my_id', '')).strip()
    pin = str(data.get('pin', '')).strip()
    user = Vote.query.filter_by(my_id=my_id, pin=pin).first()

    if not user:
        return jsonify({'success': False, 'message': 'IDまたはパスワードが正しくありません'}), 400

    try:
        user_targets = json.loads(user.target_ids) if user.target_ids else []
    except (TypeError, json.JSONDecodeError):
        user_targets = []

    matches = []
    for other in Vote.query.all():
        if other.my_id == my_id:
            continue
        try:
            other_targets = json.loads(other.target_ids) if other.target_ids else []
        except (TypeError, json.JSONDecodeError):
            other_targets = []

        if other.my_id in user_targets and my_id in other_targets:
            try:
                other_messages = json.loads(other.messages) if other.messages else {}
            except (TypeError, json.JSONDecodeError):
                other_messages = {}
            matches.append({
                'id': other.my_id,
                'contact': other.contact,
                'message': other_messages.get(my_id, '')
            })

    return jsonify({'success': True, 'matched': bool(matches), 'matches': matches})

if __name__ == '__main__':
    app.run(debug=True)
