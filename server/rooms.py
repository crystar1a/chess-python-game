import string
import threading
import secrets
import time

import chess

from shared.protocol import MessageType, make_message

from server.game.chess_match import ChessMatch
from server.auth import AuthService, UserStore


class RoomManager:
    """Quản lý phòng 2 người và phiên trên RAM, bảo vệ bởi threading.RLock."""

    def __init__(self, auth_service=None):
        self._lock = threading.RLock()
        self.auth_service = auth_service
        self._conn_to_user = {}
        self._rooms = {}        # room_code -> room dict
        self._conn_to_room = {} # conn_id -> room_code
        self._conn_to_color = {}# conn_id -> chess.WHITE / chess.BLACK

    def handle_message(self, conn_id, msg):
        """Router thuần logic. Trả về danh sách (recipient_conn_id, message_dict)."""
        msg_type = msg.get('type')
        with self._lock:
            if msg_type in (MessageType.AUTH_GUEST, MessageType.AUTH_SUBMIT, MessageType.AUTH_REGISTER, MessageType.AUTH_TOKEN):
                return self._handle_auth(conn_id, msg_type, msg)
            if msg_type == MessageType.CREATE_ROOM:
                return self._handle_create_room(conn_id, msg)
            if msg_type == MessageType.JOIN_ROOM:
                return self._handle_join_room(conn_id, msg)
            if msg_type == MessageType.LIST_ROOMS:
                rooms = [{'room_code': room['code'], 'host': self._conn_to_user.get(room['white_conn'], {}).get('username', 'White'), 'minutes': room['minutes']} for room in self._rooms.values() if room['white_conn'] is not None and room['black_conn'] is None and room['match'] is None]
                chunks = [rooms[i:i + 200] for i in range(0, len(rooms), 200)] or [[]]
                return [(conn_id, make_message(MessageType.ROOM_LIST, rooms=chunk, first=i == 0, complete=i == len(chunks) - 1)) for i, chunk in enumerate(chunks)]
            if msg_type == MessageType.MOVE_REQUEST:
                return self._handle_move_request(conn_id, msg)
            if msg_type == MessageType.CHAT_SEND:
                return self._handle_chat(conn_id, msg)
            if msg_type == MessageType.RESUME:
                return self._handle_resume(conn_id, msg)
            if msg_type == MessageType.PING:
                return [(conn_id, make_message(MessageType.PONG))]
            if msg_type == MessageType.RESIGN:
                return self._handle_resign(conn_id, msg)
            if msg_type == MessageType.DRAW_OFFER:
                return self._handle_draw_offer(conn_id, msg)
            if msg_type == MessageType.DRAW_ACCEPT:
                return self._handle_draw_accept(conn_id, msg)
            if msg_type in (MessageType.REMATCH_REQUEST, MessageType.REMATCH_ACCEPT, MessageType.REMATCH_DECLINE):
                return self._handle_rematch(conn_id, msg_type)
            return [(conn_id, make_message(MessageType.ERROR, reason='unknown_message_type'))]

    def _handle_auth(self, conn_id, kind, msg):
        self._conn_to_user.pop(conn_id, None)
        if self.auth_service is None:
            self.auth_service = AuthService(UserStore(':memory:'))
        service = self.auth_service
        if kind == MessageType.AUTH_GUEST:
            result = service.check_guest(msg.get('username'))
        elif kind == MessageType.AUTH_SUBMIT:
            result = service.submit_login_or_probe(msg.get('username'), msg.get('password'))
        elif kind == MessageType.AUTH_REGISTER:
            result = service.register(msg.get('username'), msg.get('password'))
        else:
            name = service.verify_token(msg.get('token'))
            result = {'status': 'ok', 'username': name, 'token': msg.get('token')} if name else {'status': 'invalid_token'}
        status = result['status']
        if status == 'ok':
            guest = kind == MessageType.AUTH_GUEST
            self._conn_to_user[conn_id] = {'username': result['username'], 'is_guest': guest}
            response = make_message(MessageType.AUTH_OK, username=result['username'], is_guest=guest, token=result.get('token'))
        elif status == 'needs_register':
            response = make_message(MessageType.AUTH_NEEDS_REGISTER, username=result['username'])
        else:
            response = make_message(MessageType.AUTH_ERROR, reason=status)
        return [(conn_id, response)]

    @staticmethod
    def _make_room_code():
        return ''.join(__import__('random').choices(string.ascii_uppercase + string.digits, k=6))

    def _handle_create_room(self, conn_id, msg):
        minutes = msg.get('minutes')
        if minutes is not None and (type(minutes) is not int or minutes not in (5, 10, 15)):
            return [(conn_id, make_message(MessageType.ERROR, reason='invalid_minutes'))]
        code = self._make_room_code()
        while code in self._rooms:
            code = self._make_room_code()
        token = secrets.token_urlsafe(32)
        room = {
            'code': code,
            'token': token,
            'black_token': secrets.token_urlsafe(32),
            'disconnected': {},
            'white_conn': conn_id,
            'black_conn': None,
            'match': None,
            'minutes': minutes,
        }
        self._rooms[code] = room
        self._conn_to_room[conn_id] = code
        self._conn_to_color[conn_id] = chess.WHITE
        return [(conn_id, make_message(
            MessageType.WELCOME,
            room_code=code,
            token=token,
            color='white',
        ))]

    def _handle_join_room(self, conn_id, msg):
        code = msg.get('room_code')
        room = self._rooms.get(code)
        if room is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='room_not_found'))]
        if room['black_conn'] is not None or room['match'] is not None:
            return [(conn_id, make_message(MessageType.ERROR, reason='room_full'))]

        room['black_conn'] = conn_id
        self._conn_to_room[conn_id] = code
        self._conn_to_color[conn_id] = chess.BLACK

        game_start = self._start_match(room)
        return [
            (room['white_conn'], game_start),
            (conn_id, make_message(MessageType.WELCOME, room_code=code, token=room['black_token'], color='black')),
            (conn_id, game_start),
        ]

    def _start_match(self, room):
        code = room['code']
        conn_id = room['black_conn']
        match = ChessMatch(room['white_conn'], room['black_conn'], room['minutes'], room['minutes'])
        room['match'] = match

        game_start = make_message(
            MessageType.GAME_START,
            room_code=code,
            fen=match.board.fen(),
            turn=match._color_name(match.board.turn),
            revision=match.revision,
            white_time=match.white_time,
            black_time=match.black_time,
            game_over=False,
            result=None,
            reason=None,
            white_name=self._conn_to_user.get(room['white_conn'], {}).get('username', 'White'),
            black_name=self._conn_to_user.get(conn_id, {}).get('username', 'Black'),
        )
        room['white_name'] = game_start['white_name']
        room['black_name'] = game_start['black_name']

        room['rematch_offer'] = None
        return game_start

    def _handle_rematch(self, conn_id, kind):
        room, match = self._get_match(conn_id)
        if match is None or match.result is None or room['disconnected']:
            return [(conn_id, make_message(MessageType.ERROR, reason='rematch_unavailable'))]
        opponent = room['black_conn'] if conn_id == room['white_conn'] else room['white_conn']
        if not opponent:
            return [(conn_id, make_message(MessageType.ERROR, reason='rematch_unavailable'))]
        if kind == MessageType.REMATCH_REQUEST:
            if room.get('rematch_offer'):
                return [(conn_id, make_message(MessageType.ERROR, reason='rematch_pending'))]
            room['rematch_offer'] = conn_id
            return [(opponent, make_message(MessageType.REMATCH_REQUEST))]
        if room.get('rematch_offer') != opponent:
            return [(conn_id, make_message(MessageType.ERROR, reason='rematch_unavailable'))]
        if kind == MessageType.REMATCH_ACCEPT:
            start = self._start_match(room)
            return [(room['white_conn'], start), (room['black_conn'], start)]
        self._conn_to_room.pop(conn_id, None)
        self._conn_to_color.pop(conn_id, None)
        room.update(white_conn=opponent, black_conn=None, match=None, rematch_offer=None,
                    token=secrets.token_urlsafe(32), black_token=secrets.token_urlsafe(32), disconnected={})
        self._conn_to_color[opponent] = chess.WHITE
        return [(conn_id, make_message(MessageType.REMATCH_DECLINE)),
                (opponent, make_message(MessageType.WELCOME, room_code=room['code'], token=room['token'], color='white')),
                (opponent, make_message(MessageType.ROOM_STATE, reason='waiting_for_opponent'))]

    def _get_match(self, conn_id):
        code = self._conn_to_room.get(conn_id)
        if code is None:
            return None, None
        room = self._rooms.get(code)
        if room is None:
            return None, None
        return room, room['match']

    def _handle_chat(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        text = msg.get('text')
        if match is None or match.result is not None or room['disconnected'] or not room['white_conn'] or not room['black_conn']:
            return [(conn_id, make_message(MessageType.CHAT_REJECTED, reason='chat_unavailable'))]
        if not isinstance(text, str) or not text.strip() or len(text) > 500 or any(ord(ch) < 32 for ch in text):
            return [(conn_id, make_message(MessageType.CHAT_REJECTED, reason='invalid_message'))]
        side = 'white' if self._conn_to_color.get(conn_id) == chess.WHITE else 'black'
        name = room[side + '_name']
        message = make_message(MessageType.CHAT_MESSAGE, sender=name, color=side, text=text.strip())
        return [(room['white_conn'], message), (room['black_conn'], message)]

    def _handle_move_request(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        if match is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='no_active_match'))]

        color = self._conn_to_color.get(conn_id)
        uci = msg.get('uci')
        expected_revision = msg.get('expected_revision', 0)

        response = match.apply_move(color, uci, expected_revision)

        if response['type'] == MessageType.MOVE_REJECTED:
            return [(conn_id, response)]
        recipients = [room['white_conn'], room['black_conn']]
        return [(rid, response) for rid in recipients]

    def on_disconnect(self, conn_id):
        with self._lock:
            self._conn_to_user.pop(conn_id, None)
            code = self._conn_to_room.pop(conn_id, None)
            color = self._conn_to_color.pop(conn_id, None)
            room = self._rooms.get(code)
            if room is None:
                return []
            if room['match'] is None:
                self._rooms.pop(code, None)
                return []
            room['disconnected'][color] = time.monotonic() + 60
            room['white_conn' if color == chess.WHITE else 'black_conn'] = None
            opponent = room['black_conn' if color == chess.WHITE else 'white_conn']
            if opponent is None:
                return []
            return [(opponent, make_message(MessageType.ROOM_STATE, reason='opponent_disconnected', game_over=False))]

    def _handle_resume(self, conn_id, msg):
        token = msg.get('token')
        if not isinstance(token, str) or not token or not token.isascii():
            return [(conn_id, make_message(MessageType.ERROR, reason='invalid_resume_token'))]
        for code, room in self._rooms.items():
            color = chess.WHITE if secrets.compare_digest(token, room['token']) else chess.BLACK if secrets.compare_digest(token, room['black_token']) else None
            if color is None:
                continue
            deadline = room['disconnected'].get(color)
            if deadline is None:
                return [(conn_id, make_message(MessageType.ERROR, reason='resume_expired'))]
            match = room['match']
            deliveries = self.check_timeouts()
            room['disconnected'].pop(color)
            room['white_conn' if color == chess.WHITE else 'black_conn'] = conn_id
            self._conn_to_room[conn_id] = code
            self._conn_to_color[conn_id] = color
            result, _, reason = (match.result or '').partition(' - ')
            snapshot = make_message(MessageType.GAME_START, room_code=code, color=match._color_name(color), fen=match.board.fen(), turn=match._color_name(match.board.turn), revision=match.revision, white_time=match.white_time, black_time=match.black_time, game_over=bool(match.result), result=result or None, reason=reason or None, moves=[move.uci() for move in match.board.move_stack], white_name=room['white_name'], black_name=room['black_name'], opponent_disconnected=not color in room['disconnected'])
            opponent = room['black_conn' if color == chess.WHITE else 'white_conn']
            return deliveries + [(conn_id, snapshot)] + ([(opponent, make_message(MessageType.ROOM_STATE, reason='opponent_reconnected'))] if opponent else [])
        return [(conn_id, make_message(MessageType.ERROR, reason='invalid_resume_token'))]

    def check_timeouts(self):
        with self._lock:
            deliveries = []
            for room in self._rooms.values():
                if room['match'] is not None:
                    message = room['match'].check_timeout()
                    if message:
                        deliveries.extend((conn_id, message) for conn_id in (room['white_conn'], room['black_conn']) if conn_id)
                    expired = [color for color, deadline in room['disconnected'].items() if time.monotonic() >= deadline]
                    if expired and room['match'].result is None:
                        result = '1/2-1/2' if len(room['disconnected']) == 2 else ('0-1' if expired[0] == chess.WHITE else '1-0')
                        room['match'].result = result + ' - Disconnected'
                        room['match'].revision += 1
                        message = make_message(MessageType.MOVE_ACCEPTED, fen=room['match'].board.fen(), turn=room['match']._color_name(room['match'].board.turn), revision=room['match'].revision, white_time=room['match'].white_time, black_time=room['match'].black_time, game_over=True, result=result, reason='Disconnected')
                        deliveries.extend((conn_id, message) for conn_id in (room['white_conn'], room['black_conn']) if conn_id)
            return deliveries

    def _handle_resign(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        if match is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='no_active_match'))]
        if room['disconnected']:
            return [(conn_id, make_message(MessageType.MOVE_REJECTED, reason='opponent_disconnected'))]

        color = self._conn_to_color.get(conn_id)
        winner = not color
        winner_name = match._color_name(winner)
        loser_name = match._color_name(color)

        match.result = f"{winner_name} wins by resignation"

        response = make_message(
            MessageType.ERROR,
            reason='resigned',
            winner=winner_name,
            game_over=True,
            result=f"{winner_name} wins",
        )

        recipients = [room['white_conn'], room['black_conn']]
        return [(rid, response) for rid in recipients]

    def _handle_draw_offer(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        if match is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='no_active_match'))]

        color = self._conn_to_color.get(conn_id)
        opponent = room['black_conn'] if color == chess.WHITE else room['white_conn']
        return [(opponent, make_message(MessageType.DRAW_OFFER, offered_by=conn_id))]

    def _handle_draw_accept(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        if match is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='no_active_match'))]

        match.result = '1/2-1/2 - Draw by agreement'

        response = make_message(
            MessageType.ERROR,
            reason='draw_accepted',
            game_over=True,
            result='1/2-1/2',
        )

        recipients = [room['white_conn'], room['black_conn']]
        return [(rid, response) for rid in recipients]
