import queue

import chess

from client.game.local_board import Game
from client.ai.stockfish import Engine


class Controller:
    def __init__(self, color, minutes, difficulty='Normal'):
        self.game = Game(color, minutes)
        self.engine = Engine(difficulty)
        self.thinking = False
        self.error = None

    def update(self):
        game = self.game
        game.tick()
        if game.result or self.error:
            return None
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
