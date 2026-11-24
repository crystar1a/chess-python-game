import chess

from client.gui.board_view import BOARD, BOARD_TOP, SIZE


def square_at(pos, player):
    x, y = pos
    y -= BOARD_TOP
    if not (0 <= x < BOARD and 0 <= y < BOARD):
        return None
    col, row = x // SIZE, y // SIZE
    return chess.square(col if player == chess.WHITE else 7 - col,
                        7 - row if player == chess.WHITE else row)


def select_square(pos, game, selected):
    target = square_at(pos, game.player)
    if target is None:
        return selected, None, None
    if target == selected:
        return None, None, None
    piece = game.board.piece_at(target)
    if piece and piece.color == game.player:
        return target, None, None
    if selected is not None:
        if any(m.from_square == selected and m.to_square == target and m.promotion for m in game.board.legal_moves):
            return selected, (selected, target), None
        return None, None, game.move(chess.Move(selected, target))
    return selected, None, None
