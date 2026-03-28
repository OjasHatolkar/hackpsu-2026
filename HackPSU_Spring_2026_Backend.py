from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

rooms = {}

@socketio.on('join_room')
def handle_join(data):
    room_id = data['room']
    role = data['role']

    if room_id not in rooms:
        rooms[room_id] = {'A': None, 'B': None, 'C': None, 'state': {}}

    rooms[room_id][role] = request.sid
    join_room(room_id)

    emit('room_joined', {'role': role, 'state': rooms[room_id]['state']})
    emit('player_joined', {'role': role}, room = room_id, include_self = False)

    @socketio.on('button_press')
    def handle_button_press(data):
       roomd_id = data['room']
       role = data['role']

       action = data['action']

       c_sid = rooms[room_id]['C']
       if c_sid:
           emit('action_update', {'from' : role, 'action' : action}, to = c_sid)

    @socketio.on('directive')
    def handle_directive(data):
        room_id = data['room']
        directive = data['directive']

        for role in ['A', 'B']:
            sid = rooms[room_id][role]
            if sid:
                emit('directive_update', {'directive': directive}, to=sid)

if __name__ == '__main__':
    socketio.run(app, debug = True)