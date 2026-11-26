import time

import chess


class Game:
    def __init__(self, player, minutes):
        self.board = chess.Board()
        self.player = player
        self.remaining = None if minutes is None else {chess.WHITE: minutes * 60.0, chess.BLACK: minutes * 60.0}
        self.updated = time.monotonic()
        self.result = None
        self.move_history = []
        self.last_move = None

    def tick(self):
        now = time.monotonic()
        if self.remaining is not None and self.result is None:
            color = self.board.turn
            self.remaining[color] = max(0, self.remaining[color] - (now - self.updated))
            if self.remaining[color] == 0:
                winner = not color
                if self.board.is_insufficient_material() or self.board.has_insufficient_material(winner):
                    self.result = "Draw: time / insufficient material"
                else:
                    self.result = f"{'White' if winner else 'Black'} wins on time"
        self.updated = now

    def move(self, move):
        self.tick()
        if self.result or move not in self.board.legal_moves:
            return None
        board = self.board
        san = board.san(move)
        sound = ('promote' if move.promotion else 'castle' if board.is_castling(move)
                 else 'capture' if board.is_capture(move) else None)
        board.push(move)
        self.move_history.append(san)
        self.last_move = move
        if board.is_check():
            sound = 'move-check'
        outcome = board.outcome(claim_draw=True)
        if outcome:
            self.result = f"{outcome.result()} - {outcome.termination.name.replace('_', ' ').title()}"
        self.updated = time.monotonic()
        return sound or ('move-self' if board.turn != self.player else 'move-opponent')
