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
        self.thinking = False
        self.error = None

    def apply_uci(self, uci):
        """Áp dụng nước đi từ chuỗi UCI (ví dụ: "e2e4", "e7e8q").

        Trả về tên âm thanh hoặc None.
        """
        move = chess.Move.from_uci(uci)
        game = self.game

        if self.mode == 'online':
            if game.board.turn != game.player:
                self.error = 'Not your turn.'
                return None
            if self.on_online_move_intent:
                self.on_online_move_intent(uci)
            return None

        # mode == 'local'
        if game.result or self.error:
            return None
        if move not in game.board.legal_moves:
            return None
        return game.move(move)

    def apply_server_snapshot(self, fen, remaining=None, result=None):
        """Cập nhật bàn cờ từ trạng thái server (chế độ online)."""
        game = self.game
        game.board = chess.Board(fen)
        if remaining is not None:
            game.remaining = remaining
        if result is not None:
            game.result = result
        game.updated = time.monotonic()
        self.error = None

    def update(self):
        game = self.game
        game.tick()
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
