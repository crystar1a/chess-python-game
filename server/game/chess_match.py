import time

import chess

from shared.protocol import MessageType, make_message


class ChessMatch:
    """Một ván cờ authoritative trên server. Giữ Board duy nhất và revision."""

    def __init__(self, white_player_id, black_player_id, white_minutes=None, black_minutes=None):
        self.board = chess.Board()
        self.revision = 0
        self.white_player_id = white_player_id
        self.black_player_id = black_player_id
        self.white_time = None if white_minutes is None else float(white_minutes) * 60.0
        self.black_time = None if black_minutes is None else float(black_minutes) * 60.0
        self.updated = time.monotonic()
        self.result = None

    @staticmethod
    def _color_name(color):
        return 'white' if color == chess.WHITE else 'black'

    def _deduct_elapsed(self, color):
        """Trừ thời gian đã trôi qua của bên vừa đi (đồng hồ của họ đang chạy)."""
        now = time.monotonic()
        elapsed = now - self.updated
        if color == chess.WHITE and self.white_time is not None:
            self.white_time = max(0.0, self.white_time - elapsed)
        elif color == chess.BLACK and self.black_time is not None:
            self.black_time = max(0.0, self.black_time - elapsed)
        self.updated = now

    def check_timeout(self):
        if self.result is not None:
            return None
        color = self.board.turn
        self._deduct_elapsed(color)
        remaining = self.white_time if color == chess.WHITE else self.black_time
        if remaining is None or remaining > 0:
            return None
        winner = not color
        result = '1/2-1/2' if self.board.has_insufficient_material(winner) else ('1-0' if winner else '0-1')
        self.result = f'{result} - Timeout'
        self.revision += 1
        return make_message(MessageType.MOVE_ACCEPTED, fen=self.board.fen(),
                            turn=self._color_name(self.board.turn), revision=self.revision,
                            white_time=self.white_time, black_time=self.black_time,
                            game_over=True, result=result, reason='Timeout')

    def apply_move(self, color, uci_move, expected_revision):
        """Áp dụng nước đi UCI nếu hợp lệ. Trả về message MOVE_ACCEPTED hoặc MOVE_REJECTED."""
        if self.result is not None:
            return make_message(MessageType.MOVE_REJECTED, reason='game_over')
        if expected_revision != self.revision:
            return make_message(
                MessageType.MOVE_REJECTED,
                reason='stale_revision',
                expected=self.revision,
                current=self.revision,
            )

        if self.board.turn != color:
            return make_message(
                MessageType.MOVE_REJECTED,
                reason='not_your_turn',
                current_turn=self._color_name(self.board.turn),
            )

        try:
            move = chess.Move.from_uci(uci_move)
        except (ValueError, TypeError):
            return make_message(MessageType.MOVE_REJECTED, reason='invalid_uci')

        if move not in self.board.legal_moves:
            return make_message(MessageType.MOVE_REJECTED, reason='illegal_move')

        timeout = self.check_timeout()
        if timeout:
            return timeout

        self.board.push(move)
        self.revision += 1
        self.updated = time.monotonic()

        outcome = self.board.outcome(claim_draw=True)
        game_over = bool(outcome)
        result = outcome.result() if outcome else None
        reason = outcome.termination.name.replace('_', ' ').title() if outcome else None
        if outcome:
            self.result = f"{result} - {reason}"

        return make_message(
            MessageType.MOVE_ACCEPTED,
            fen=self.board.fen(),
            turn=self._color_name(self.board.turn),
            revision=self.revision,
            white_time=self.white_time,
            black_time=self.black_time,
            game_over=game_over,
            result=result,
            reason=reason,
        )
