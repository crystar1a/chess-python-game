import queue
import time

import chess

from client.game.local_board import Game
from client.ai.stockfish import Engine


class Controller:
    def __init__(self, color, minutes, difficulty='Normal', mode='local',
                 on_online_move_intent=None):
        self.game = Game(color, minutes)
        self.engine = Engine(difficulty)
        self.mode = mode
        self.on_online_move_intent = on_online_move_intent
        self.revision = None
        self._legacy_snapshot = False
        self.thinking = False
        self.error = None

    def apply_uci(self, uci):
        """Áp dụng nước đi từ chuỗi UCI (ví dụ: "e2e4", "e7e8q").

        Trả về tên âm thanh hoặc None.
        """
        move = chess.Move.from_uci(uci)
        game = self.game

        if self.mode == 'online':
            if game.result or (self.revision is None and not self._legacy_snapshot) or game.board.turn != game.player:
                self.error = 'Not your turn.'
                return None
            if self.on_online_move_intent:
                if self._legacy_snapshot:
                    self.on_online_move_intent(uci)
                else:
                    self.on_online_move_intent(uci, self.revision)
            return None

        # mode == 'local'
        if game.result or self.error:
            return None
        if move not in game.board.legal_moves:
            return None
        return game.move(move)

    def apply_server_snapshot(self, message, remaining=None, result=None):
        """Cập nhật bàn cờ từ trạng thái server (chế độ online)."""
        game = self.game
        if isinstance(message, str):
            self._legacy_snapshot = True
            game.board = chess.Board(message)
            game.remaining = remaining
            game.result = result
            game.updated = time.monotonic()
            self.error = None
            return
        self._legacy_snapshot = False
        game.board = chess.Board(message['fen'])
        self.revision = message['revision']
        white_time, black_time = message['white_time'], message['black_time']
        game.remaining = None if white_time is None and black_time is None else {
            chess.WHITE: white_time, chess.BLACK: black_time}
        result, reason = message.get('result'), message.get('reason')
        game.result = (f'{result} - {reason}' if reason else result) if message.get('game_over') else None
        game.updated = time.monotonic()
        self.error = None

    def update(self):
        game = self.game
        previous_result = game.result
        game.tick()
        if self.mode == 'online' and previous_result is None:
            game.result = None
        if game.result or self.error:
            return None
        if self.mode == 'local':
            if self.thinking:
                try:
                    fen, move, error = self.engine.results.get_nowait()
                except queue.Empty:
                    return None
                self.thinking = False
                if error:
                    if self.engine.online:
                        self.error = f'StockfishOnline: {error}'
                    else:
                        self.error = 'Stockfish unavailable. Check client/ai/stockfish and start a new game.'
                elif fen == game.board.fen() and move in game.board.legal_moves:
                    return game.move(move)
                else:
                    self.error = 'Stockfish returned an invalid move.'
            elif game.board.turn != game.player:
                self.engine.start(game.board)
                self.thinking = True
        return None

    def close(self):
        self.engine.close()
