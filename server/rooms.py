import string
import threading
import uuid

import chess

from shared.protocol import MessageType, make_message

from server.game.chess_match import ChessMatch


class RoomManager:
    """Quản lý phòng 2 người và phiên trên RAM, bảo vệ bởi threading.RLock."""

    def __init__(self):
        self._lock = threading.RLock()
        self._rooms = {}        # room_code -> room dict
        self._conn_to_room = {} # conn_id -> room_code
        self._conn_to_color = {}# conn_id -> chess.WHITE / chess.BLACK

    def handle_message(self, conn_id, msg):
        """Router thuần logic. Trả về danh sách (recipient_conn_id, message_dict)."""
        msg_type = msg.get('type')
        with self._lock:
            if msg_type == MessageType.CREATE_ROOM:
                return self._handle_create_room(conn_id, msg)
            if msg_type == MessageType.JOIN_ROOM:
                return self._handle_join_room(conn_id, msg)
            if msg_type == MessageType.MOVE_REQUEST:
                return self._handle_move_request(conn_id, msg)
            if msg_type == MessageType.RESIGN:
                return self._handle_resign(conn_id, msg)
            if msg_type == MessageType.DRAW_OFFER:
                return self._handle_draw_offer(conn_id, msg)
            if msg_type == MessageType.DRAW_ACCEPT:
                return self._handle_draw_accept(conn_id, msg)
            return [(conn_id, make_message(MessageType.ERROR, reason='unknown_message_type'))]

    @staticmethod
    def _make_room_code():
        return ''.join(__import__('random').choices(string.ascii_uppercase + string.digits, k=6))

    def _handle_create_room(self, conn_id, msg):
        code = self._make_room_code()
        token = str(uuid.uuid4())
        room = {
            'code': code,
            'token': token,
            'white_conn': conn_id,
            'black_conn': None,
            'match': None,
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
        if room['black_conn'] is not None:
            return [(conn_id, make_message(MessageType.ERROR, reason='room_full'))]

        room['black_conn'] = conn_id
        self._conn_to_room[conn_id] = code
        self._conn_to_color[conn_id] = chess.BLACK

        match = ChessMatch(room['white_conn'], room['black_conn'])
        room['match'] = match

        game_start = make_message(
            MessageType.GAME_START,
            room_code=code,
            fen=match.board.fen(),
            turn=match._color_name(match.board.turn),
            revision=match.revision,
            white_time=match.white_time,
            black_time=match.black_time,
        )

        return [
            (room['white_conn'], game_start),
            (conn_id, make_message(
                MessageType.WELCOME,
                room_code=code,
                token=room['token'],
                color='black',
            )),
            (conn_id, game_start),
        ]

    def _get_match(self, conn_id):
        code = self._conn_to_room.get(conn_id)
        if code is None:
            return None, None
        room = self._rooms.get(code)
        if room is None:
            return None, None
        return room, room['match']

    def _handle_move_request(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        if match is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='no_active_match'))]

        color = self._conn_to_color.get(conn_id)
        uci = msg.get('uci')
        expected_revision = msg.get('expected_revision', 0)

        response = match.apply_move(color, uci, expected_revision)

        recipients = [room['white_conn'], room['black_conn']]
        return [(rid, response) for rid in recipients]

    def _handle_resign(self, conn_id, msg):
        room, match = self._get_match(conn_id)
        if match is None:
            return [(conn_id, make_message(MessageType.ERROR, reason='no_active_match'))]

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
