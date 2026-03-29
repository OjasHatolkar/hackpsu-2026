from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import random
import string
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

rooms = {}

public_rooms = []

DIRECTIVE_TYPES = ['coolant', 'voltage', 'hydraulics']

def pick_directive():
    directive_type = random.choice(DIRECTIVE_TYPES)
    if directive_type == 'coolant' or directive_type == 'voltage':
        directive_value = random.randint(1, 100)
    else:
        directive_value = random.choice(['ON', 'OFF'])
    return {'type': directive_type, 'value': directive_value}

def start_round(room_id):
    directive = pick_directive()

    if room_id not in rooms:
        return

    rooms[room_id]['state']['current_directive'] = directive

    emit('new_directive', directive, room = room_id)

@socketio.on('start_round')
def handle_start_round(data):
    room_id = data.get('room')
    if room_id in rooms:
        start_round(room_id)

def generate_room_code(length = 4):
    room_code = ''
    while True:
        for i in range(length):
            room_code = room_code + random.choice(string.ascii_uppercase)
        if room_code not in rooms:
            return room_code
        room_code = ''
        
def create_room(room_id, public = False):
    if room_id in rooms:
        return
    
    rooms[room_id] = {
        'public' : public,
        'players' : {
            'A' : None,
            'B' : None,
            'C' : None
        },
        'state' : {
            'round' : 1,
            'current_directive' : None,
            'values' : {
                'coolant' : None,
                'voltage' : None,
                'hydraulics' : None
            },
            'score' : {
                'successes' : 0,
                'failures' : 0
            }
        }
    }
    if public and room_id not in public_rooms:
        public_rooms.append(room_id)

@socketio.on('host_crew')
def handle_host_crew():
    room_id = generate_room_code()
    create_room(room_id, public = False)

    sid = request.sid
    role = assign_role(room_id, sid)
    join_room(room_id)

    emit('host_created', {'room': room_id, 'role' : role})

@socketio.on('join_crew')
def handle_join_crew(data):
    room_id = data.get('room')

    if room_id not in rooms or rooms[room_id]["public"]:
        emit('join_error', {'error': 'Room not found'})
        return
    
    sid = request.sid
    role = assign_role(room_id, sid)

    if role is None:
        emit('join_error', {'error': 'Room is full'})
        return

    join_room(room_id)
    emit('joined_room', {'room' : room_id, 'role' : role})

def room_has_space(room_id):
    if room_id not in rooms:
        return False
    players = rooms[room_id]['players']
    return any(sid is None for sid in players.values())

def assign_role(room_id, sid):
    if room_id not in rooms:
        return
    for role, current_sid in rooms[room_id]['players'].items():
        if current_sid is None:
            rooms[room_id]['players'][role] = sid
            return role
    return None

@socketio.on('auto_deploy')
def handle_auto_deploy():
    sid = request.sid

    target_room = None
    for room_id in public_rooms:
        if room_has_space(room_id):
            target_room = room_id
            break
    
    if target_room is None:
        target_room = generate_room_code()
        create_room(target_room, public = True)

    role = assign_role(target_room, sid)
    join_room(target_room)

    emit('auto_deployed', {'room': target_room, 'role': role})

@socketio.on('button_press')
def handle_button_press(data):
    room_id = data['room']
    role = data['role']

    action = data['action']

    if room_id not in rooms:
        return

    c_sid = rooms[room_id]['players']['C']
    if c_sid:
       emit('action_update', {'from' : role, 'action' : action}, to = c_sid)

@socketio.on('directive')
def handle_directive(data):
    room_id = data['room']
    directive = data['directive']

    if room_id not in rooms:
        return

    for role in ['A', 'B']:
        sid = rooms[room_id]['players'][role]
        if sid:
            emit('directive_update', {'directive': directive}, to = sid)

@socketio.on("player_response")
def handle_player_response(data):
    room_id = data.get('room')
    role = data.get('role')

    response_type = data.get('type')
    response_value = data.get('value')

    if room_id not in rooms:
        return
    if role not in ['A', 'B']:
        return
    if response_type not in ['coolant', 'voltage', 'hydraulics']:
        return
    
    rooms[room_id]['state']['values'][response_type] = response_value
    
    check_round_completion(room_id)

def both_players_responded(room_id):

    if room_id not in rooms:
        return

    values = rooms[room_id]['state']['values']
    return (
        values['coolant'] is not None and
        values['voltage'] is not None and
        values['hydraulics'] is not None
    )

def check_round_completion(room_id, TOLERANCE = 5):
    if room_id not in rooms:
        return

    directive = rooms[room_id]['state']['current_directive']
    values = rooms[room_id]['state']['values']

    directive_type = directive['type']
    target = directive['value']
    actual = values[directive_type]

    if actual is None:
        return
    
    if directive_type == 'coolant' or directive_type == 'voltage':
        success = abs(actual - target) <= TOLERANCE
    elif directive_type == 'hydraulics':
        success = actual == target
    else:
        success = False
    
    if success:
        rooms[room_id]['state']['score']['successes'] += 1
    else:
        rooms[room_id]['state']['score']['failures'] += 1

    emit('round_result', {'directive': directive, 'actual': actual, 'success': success, 'score': rooms[room_id]['state']['score']}, room = room_id)

    reset_round_state(room_id)

    socketio.start_background_task(auto_next_round, room_id)

def reset_round_state(room_id):
    if room_id not in rooms:
        return
    
    directive_type = rooms[room_id]['state']['current_directive']['type']

    rooms[room_id]['state']['values'][directive_type] = None

@socketio.on('next_round')
def handle_next_round(data):
    room_id = data.get('room')
    if room_id in rooms:
        start_round(room_id)

# Time limit is currently 2 seconds
def auto_next_round(room_id, TIME_LIMIT = 2):
    time.sleep(TIME_LIMIT)
    if room_id in rooms:
        start_round(room_id)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    for room_id, room in list(rooms.items()):
        players = room['players']
        for role, player_sid in players.items():
            if player_sid == sid:
                players[role] = None
                emit('player_disconnected', {'role': role}, room = room_id)
                if all(v is None for v in players.values()):
                    del rooms[room_id]
                    if room_id in public_rooms:
                        public_rooms.remove(room_id)
                    return

if __name__ == '__main__':
    socketio.run(app, debug = True)