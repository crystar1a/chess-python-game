import chess

from client.gui.board_view import BOARD, BOARD_TOP, SIZE


def square_at(pos, player, board_origin=(0, BOARD_TOP), square_size=SIZE):
    ox, oy = board_origin
    x, y = pos[0] - ox, pos[1] - oy
    board_px = square_size * 8
    if not (0 <= x < board_px and 0 <= y < board_px):
        return None
    col, row = x // square_size, y // square_size
    return chess.square(
        col if player == chess.WHITE else 7 - col,
        7 - row if player == chess.WHITE else row,
    )


def select_square(pos, controller, selected, board_origin=(0, BOARD_TOP), square_size=SIZE):
    """Xử lý click chuột trên bàn cờ.

    Trả về (selected, promotion, sound).
    """
    game = controller.game
    target = square_at(pos, game.player, board_origin, square_size)
    if target is None:
        return selected, None, None
    if target == selected:
        return None, None, None
    piece = game.board.piece_at(target)
    if piece and piece.color == game.player:
        return target, None, None
    if selected is not None:
        if any(m.from_square == selected and m.to_square == target and m.promotion
               for m in game.board.legal_moves):
            return selected, (selected, target), None
        uci = chess.Move(selected, target).uci()
        sound = controller.apply_uci(uci)
        return None, None, sound
    return selected, None, None


def resolve_drop(from_sq, pos, controller, board_origin=(0, BOARD_TOP), square_size=SIZE):
    """Xử lý thả quân sau khi kéo. Trả về (promotion_pair, sound)."""
    if from_sq is None:
        return None, None
    game = controller.game
    target = square_at(pos, game.player, board_origin, square_size)
    if target is None or target == from_sq:
        return None, None
    if any(m.from_square == from_sq and m.to_square == target and m.promotion
           for m in game.board.legal_moves):
        return (from_sq, target), None
    move = chess.Move(from_sq, target)
    if move not in game.board.legal_moves:
        return None, None
    sound = controller.apply_uci(move.uci())
    return None, sound
