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


def select_square(pos, controller, selected):
    """Xử lý click chuột trên bàn cờ.

    Trả về (selected, promotion, sound):
    - selected: ô được chọn (hoặc None)
    - promotion: tuple (from_square, to_square) nếu cần phong cấp, hoặc None
    - sound: tên âm thanh từ controller.apply_uci (hoặc None)

    Mọi thao tác đi quân và phong cấp được chuyển thành chuỗi UCI
    rồi đẩy qua controller.apply_uci().
    """
    game = controller.game
    target = square_at(pos, game.player)
    if target is None:
        return selected, None, None
    if target == selected:
        return None, None, None
    piece = game.board.piece_at(target)
    if piece and piece.color == game.player:
        return target, None, None
    if selected is not None:
        # Nếu là nước đi phong cấp, yêu cầu chọn peça phong cấp
        if any(m.from_square == selected and m.to_square == target and m.promotion
               for m in game.board.legal_moves):
            return selected, (selected, target), None
        # Xây dựng UCI và đẩy qua controller
        uci = chess.Move(selected, target).uci()
        sound = controller.apply_uci(uci)
        return None, None, sound
    return selected, None, None
