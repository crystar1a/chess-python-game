import unittest

import chess

from server.game.chess_match import ChessMatch
from server.rooms import RoomManager
from shared.protocol import MessageType


class ChessMatchTests(unittest.TestCase):
    def setUp(self):
        self.match = ChessMatch('conn_white', 'conn_black', white_minutes=5, black_minutes=5)

    def test_legal_move_increments_revision(self):
        resp = self.match.apply_move(chess.WHITE, 'e2e4', 0)
        self.assertEqual(resp['type'], MessageType.MOVE_ACCEPTED)
        self.assertEqual(resp['revision'], 1)
        self.assertEqual(resp['turn'], 'black')
        self.assertEqual(self.match.board.peek(), chess.Move.from_uci('e2e4'))

    def test_expired_clock_rejects_move_and_reports_result(self):
        from unittest.mock import patch
        with patch('server.game.chess_match.time.monotonic', return_value=0) as clock:
            match = ChessMatch('a', 'b', 5, 5)
            clock.return_value = 301
            response = match.apply_move(chess.WHITE, 'e2e4', 0)
        self.assertTrue(response['game_over'])
        self.assertEqual(response['result'], '0-1')
        self.assertEqual(response['reason'], 'Timeout')
        self.assertEqual(match.board.fen(), chess.STARTING_FEN)
        self.assertEqual(match.apply_move(chess.WHITE, 'e2e4', match.revision)['reason'], 'game_over')

    def test_wrong_turn_rejected(self):
        # Deny black moving first
        resp = self.match.apply_move(chess.BLACK, 'e7e5', 0)
        self.assertEqual(resp['type'], MessageType.MOVE_REJECTED)
        self.assertEqual(resp['reason'], 'not_your_turn')
        self.assertEqual(self.match.revision, 0)

    def test_stale_revision_rejected(self):
        self.match.apply_move(chess.WHITE, 'e2e4', 0)
        # Try same revision again
        resp = self.match.apply_move(chess.BLACK, 'e7e5', 0)
        self.assertEqual(resp['type'], MessageType.MOVE_REJECTED)
        self.assertEqual(resp['reason'], 'stale_revision')
        # Correct revision should work
        resp = self.match.apply_move(chess.BLACK, 'e7e5', 1)
        self.assertEqual(resp['type'], MessageType.MOVE_ACCEPTED)
        self.assertEqual(resp['revision'], 2)

    def test_illegal_move_rejected(self):
        resp = self.match.apply_move(chess.WHITE, 'e2e5', 0)
        self.assertEqual(resp['type'], MessageType.MOVE_REJECTED)
        self.assertEqual(resp['reason'], 'illegal_move')
        self.assertEqual(self.match.revision, 0)

    def test_promotion(self):
        self.match.board = chess.Board('8/4P3/8/8/8/8/8/8 w - - 0 1')
        resp = self.match.apply_move(chess.WHITE, 'e7e8q', 0)
        self.assertEqual(resp['type'], MessageType.MOVE_ACCEPTED)
        self.assertEqual(self.match.board.piece_at(chess.E8).piece_type, chess.QUEEN)

    def test_checkmate_ends_game(self):
        # Fool's mate: 1. f3 e5 2. g4 Qh4#
        self.match.apply_move(chess.WHITE, 'f2f3', 0)
        self.match.apply_move(chess.BLACK, 'e7e5', 1)
        resp = self.match.apply_move(chess.WHITE, 'g2g4', 2)
        self.assertEqual(resp['type'], MessageType.MOVE_ACCEPTED)
        resp = self.match.apply_move(chess.BLACK, 'd8h4', 3)
        self.assertEqual(resp['type'], MessageType.MOVE_ACCEPTED)
        self.assertTrue(resp['game_over'])
        self.assertEqual(resp['result'], '0-1')
        self.assertEqual(self.match.result, '0-1 - Checkmate')


class RoomManagerTests(unittest.TestCase):
    def setUp(self):
        self.rm = RoomManager()

    def _message_type(self, msg):
        return msg.get('type')

    def test_chat_only_reaches_players_in_active_room(self):
        self.rm.handle_message('a', {'type': 'AUTH_GUEST', 'username': 'Alice'})
        self.addCleanup(self.rm.auth_service.store.close)
        self.rm.handle_message('b', {'type': 'AUTH_GUEST', 'username': 'Bob'})
        code = self.rm.handle_message('a', {'type': 'CREATE_ROOM'})[0][1]['room_code']
        self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': code})
        self.rm.handle_message('other', {'type': 'CREATE_ROOM'})
        deliveries = self.rm.handle_message('a', {'type': 'CHAT_SEND', 'sender': 'Fake', 'text': 'Xin chào'})
        self.assertEqual({conn for conn, _ in deliveries}, {'a', 'b'})
        self.assertTrue(all(msg['sender'] == 'Alice' and msg['text'] == 'Xin chào' for _, msg in deliveries))
        self.assertEqual(self.rm.handle_message('other', {'type': 'CHAT_SEND', 'text': 'Hi'})[0][1]['type'], 'CHAT_REJECTED')

    def test_chat_rejects_invalid_disconnected_and_finished(self):
        code = self.rm.handle_message('a', {'type': 'CREATE_ROOM'})[0][1]['room_code']
        self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': code})
        for text in ('', '   ', 'x' * 501, None, 'hi\nthere'):
            with self.subTest(text=text):
                self.assertEqual(self.rm.handle_message('a', {'type': 'CHAT_SEND', 'text': text})[0][1]['type'], 'CHAT_REJECTED')
        self.assertEqual(self.rm.handle_message('a', {'type': 'CHAT_SEND', 'text': 'x' * 500})[0][1]['type'], 'CHAT_MESSAGE')
        self.rm.on_disconnect('b')
        self.assertEqual(self.rm.handle_message('a', {'type': 'CHAT_SEND', 'text': 'hi'})[0][1]['reason'], 'chat_unavailable')
        self.rm._rooms[code]['match'].result = '1-0'
        self.assertEqual(self.rm.handle_message('a', {'type': 'CHAT_SEND', 'text': 'hi'})[0][1]['reason'], 'chat_unavailable')

    def test_list_rooms_only_shows_waiting_rooms(self):
        self.rm.handle_message('host', {'type': 'AUTH_GUEST', 'username': 'Alice'})
        self.addCleanup(self.rm.auth_service.store.close)
        waiting = self.rm.handle_message('host', {'type': 'CREATE_ROOM', 'minutes': 10})[0][1]['room_code']
        full = self.rm.handle_message('other', {'type': 'CREATE_ROOM'})[0][1]['room_code']
        self.rm.handle_message('guest', {'type': 'JOIN_ROOM', 'room_code': full})
        listing = self.rm.handle_message('viewer', {'type': 'LIST_ROOMS'})[0][1]
        self.assertEqual(listing['type'], 'ROOM_LIST')
        self.assertEqual(listing['rooms'], [{'room_code': waiting, 'host': 'Alice', 'minutes': 10}])
        self.rm.on_disconnect('host')
        self.assertEqual(self.rm.handle_message('viewer', {'type': 'LIST_ROOMS'})[0][1]['rooms'], [])

    def test_list_rooms_chunks_all_entries(self):
        for index in range(205):
            self.rm.handle_message(f'host{index}', {'type': 'CREATE_ROOM'})
        pages = [msg for _, msg in self.rm.handle_message('viewer', {'type': 'LIST_ROOMS'})]
        self.assertEqual(sum(len(page['rooms']) for page in pages), 205)
        self.assertTrue(pages[0]['first'])
        self.assertFalse(pages[0]['complete'])
        self.assertTrue(pages[-1]['complete'])

    def test_rematch_accept_starts_fresh_game(self):
        welcome = self.rm.handle_message('a', {'type': 'CREATE_ROOM', 'minutes': 5})[0][1]
        self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': welcome['room_code']})
        self.rm.handle_message('a', {'type': 'RESIGN'})
        offer = self.rm.handle_message('a', {'type': 'REMATCH_REQUEST'})
        self.assertEqual(offer[0][0], 'b')
        self.assertEqual(offer[0][1]['type'], 'REMATCH_REQUEST')
        response = self.rm.handle_message('b', {'type': 'REMATCH_ACCEPT'})
        self.assertEqual({conn for conn, _ in response}, {'a', 'b'})
        self.assertTrue(all(msg['type'] == 'GAME_START' and msg['revision'] == 0 and msg['white_time'] == 300 for _, msg in response))

    def test_rematch_declined_reopens_room_for_new_opponent(self):
        welcome = self.rm.handle_message('a', {'type': 'CREATE_ROOM'})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': code})
        self.rm.handle_message('a', {'type': 'RESIGN'})
        self.rm.handle_message('b', {'type': 'REMATCH_REQUEST'})
        result = self.rm.handle_message('a', {'type': 'REMATCH_DECLINE'})
        self.assertTrue(any(conn == 'a' and msg['type'] == 'REMATCH_DECLINE' for conn, msg in result))
        self.assertTrue(any(conn == 'b' and msg['type'] == 'WELCOME' and msg['color'] == 'white' for conn, msg in result))
        joined = self.rm.handle_message('c', {'type': 'JOIN_ROOM', 'room_code': code})
        self.assertEqual(sum(msg['type'] == 'GAME_START' for _, msg in joined), 2)

    def test_rematch_requires_finished_game_and_other_player_response(self):
        code = self.rm.handle_message('a', {'type': 'CREATE_ROOM'})[0][1]['room_code']
        self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': code})
        self.assertEqual(self.rm.handle_message('a', {'type': 'REMATCH_REQUEST'})[0][1]['reason'], 'rematch_unavailable')
        self.rm.handle_message('a', {'type': 'RESIGN'})
        self.rm.handle_message('a', {'type': 'REMATCH_REQUEST'})
        self.assertEqual(self.rm.handle_message('a', {'type': 'REMATCH_ACCEPT'})[0][1]['reason'], 'rematch_unavailable')

    def test_create_room_clock_and_snapshot(self):
        for minutes in (5, 10, 15, None):
            rm = RoomManager()
            welcome = rm.handle_message('a', {'type': 'CREATE_ROOM', 'minutes': minutes})[0][1]
            starts = rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': welcome['room_code']})
            snapshot = next(msg for _, msg in starts if msg['type'] == 'GAME_START')
            self.assertEqual(snapshot['white_time'], None if minutes is None else minutes * 60)
            self.assertEqual(snapshot['black_time'], None if minutes is None else minutes * 60)
            self.assertFalse(snapshot['game_over'])
            self.assertIsNone(snapshot['result'])
            self.assertIsNone(snapshot['reason'])

    def test_invalid_minutes_rejected(self):
        for minutes in (True, 0, 7, '5'):
            self.assertEqual(self.rm.handle_message('a', {'type': 'CREATE_ROOM', 'minutes': minutes})[0][1]['type'], 'ERROR')

    def test_disconnect_keeps_room_and_notifies_opponent(self):
        code = self.rm.handle_message('a', {'type': 'CREATE_ROOM'})[0][1]['room_code']
        self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': code})
        deliveries = self.rm.on_disconnect('a')
        self.assertEqual(deliveries[0][0], 'b')
        self.assertEqual(deliveries[0][1]['reason'], 'opponent_disconnected')
        self.assertEqual(self.rm.handle_message('b', {'type': 'MOVE_REQUEST', 'uci': 'e7e5', 'expected_revision': 0})[0][1]['reason'], 'not_your_turn')

    def test_timeout_broadcast_without_move(self):
        from unittest.mock import patch
        with patch('server.game.chess_match.time.monotonic', return_value=0) as clock:
            code = self.rm.handle_message('a', {'type': 'CREATE_ROOM', 'minutes': 5})[0][1]['room_code']
            self.rm.handle_message('b', {'type': 'JOIN_ROOM', 'room_code': code})
            clock.return_value = 301
            deliveries = self.rm.check_timeouts()
            self.assertEqual({recipient for recipient, _ in deliveries}, {'a', 'b'})
            self.assertEqual(deliveries[0][1]['result'], '0-1')
            self.assertEqual(self.rm.check_timeouts(), [])

    def test_create_room_returns_welcome(self):
        results = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        self.assertEqual(len(results), 1)
        recipient, msg = results[0]
        self.assertEqual(recipient, 'conn_a')
        self.assertEqual(self._message_type(msg), MessageType.WELCOME)
        self.assertIn('room_code', msg)
        self.assertIn('token', msg)
        self.assertEqual(msg['color'], 'white')

    def test_join_room_starts_game(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        results = self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': None})
        # room_code None -> not found
        self.assertEqual(self._message_type(results[0][1]), MessageType.ERROR)

        # Get the room code from the welcome message
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']

        results = self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})
        # White gets GAME_START, black gets WELCOME + GAME_START
        types = [self._message_type(m) for _, m in results]
        self.assertIn(MessageType.GAME_START, types)
        self.assertEqual(types.count(MessageType.GAME_START), 2)
        self.assertIn(MessageType.WELCOME, types)

    def test_join_full_room_rejected(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})
        results = self.rm.handle_message('conn_c', {'type': MessageType.JOIN_ROOM, 'room_code': code})
        self.assertEqual(self._message_type(results[0][1]), MessageType.ERROR)
        self.assertEqual(results[0][1]['reason'], 'room_full')

    def test_wrong_turn_move_rejected(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})

        # Black tries to move first (wrong turn)
        results = self.rm.handle_message('conn_b', {
            'type': MessageType.MOVE_REQUEST,
            'uci': 'e7e5',
            'expected_revision': 0,
        })
        for _, msg in results:
            if msg.get('type') == MessageType.MOVE_REJECTED:
                self.assertEqual(msg['reason'], 'not_your_turn')
                return
        self.fail('No MOVE_REJECTED for wrong turn')

    def test_rejected_move_only_goes_to_requester(self):
        code = self.rm.handle_message('white', {'type': 'CREATE_ROOM'})[0][1]['room_code']
        self.rm.handle_message('black', {'type': 'JOIN_ROOM', 'room_code': code})
        results = self.rm.handle_message('black', {'type': 'MOVE_REQUEST', 'uci': 'e7e5', 'expected_revision': 0})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 'black')
        self.assertEqual(results[0][1]['type'], 'MOVE_REJECTED')

    def test_stale_revision_rejected(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})

        # White moves correctly (revision 0 -> 1)
        self.rm.handle_message('conn_a', {
            'type': MessageType.MOVE_REQUEST,
            'uci': 'e2e4',
            'expected_revision': 0,
        })
        # Black tries with stale revision (0 instead of 1)
        results = self.rm.handle_message('conn_b', {
            'type': MessageType.MOVE_REQUEST,
            'uci': 'e7e5',
            'expected_revision': 0,
        })
        for _, msg in results:
            if msg.get('type') == MessageType.MOVE_REJECTED:
                self.assertEqual(msg['reason'], 'stale_revision')
                return
        self.fail('No MOVE_REJECTED for stale revision')

    def test_illegal_move_rejected(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})

        results = self.rm.handle_message('conn_a', {
            'type': MessageType.MOVE_REQUEST,
            'uci': 'e2e5',
            'expected_revision': 0,
        })
        for _, msg in results:
            if msg.get('type') == MessageType.MOVE_REJECTED:
                self.assertEqual(msg['reason'], 'illegal_move')
                return
        self.fail('No MOVE_REJECTED for illegal move')

    def test_full_game_flow(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})

        # 1. f3 e5 2. g4 Qh4# (Fool's mate)
        self.rm.handle_message('conn_a', {'type': MessageType.MOVE_REQUEST, 'uci': 'f2f3', 'expected_revision': 0})
        self.rm.handle_message('conn_b', {'type': MessageType.MOVE_REQUEST, 'uci': 'e7e5', 'expected_revision': 1})
        self.rm.handle_message('conn_a', {'type': MessageType.MOVE_REQUEST, 'uci': 'g2g4', 'expected_revision': 2})
        results = self.rm.handle_message('conn_b', {'type': MessageType.MOVE_REQUEST, 'uci': 'd8h4', 'expected_revision': 3})

        accepted = [msg for _, msg in results if msg.get('type') == MessageType.MOVE_ACCEPTED]
        self.assertTrue(accepted, 'Expected at least one MOVE_ACCEPTED')
        self.assertTrue(accepted[0]['game_over'])
        self.assertEqual(accepted[0]['result'], '0-1')

    def test_resign_ends_game(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})

        results = self.rm.handle_message('conn_a', {'type': MessageType.RESIGN})
        for _, msg in results:
            if msg.get('reason') == 'resigned':
                self.assertTrue(msg['game_over'])
                return
        self.fail('No resigned message found')

    def test_draw_offer_and_accept(self):
        self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})
        welcome = self.rm.handle_message('conn_a', {'type': MessageType.CREATE_ROOM})[0][1]
        code = welcome['room_code']
        self.rm.handle_message('conn_b', {'type': MessageType.JOIN_ROOM, 'room_code': code})

        # White offers draw
        results = self.rm.handle_message('conn_a', {'type': MessageType.DRAW_OFFER})
        draw_offer = [msg for _, msg in results if msg.get('type') == MessageType.DRAW_OFFER]
        self.assertEqual(len(draw_offer), 1)

        # Black accepts
        results = self.rm.handle_message('conn_b', {'type': MessageType.DRAW_ACCEPT})
        accepted = [msg for _, msg in results if msg.get('reason') == 'draw_accepted']
        self.assertTrue(accepted, 'Expected draw_accepted message')


if __name__ == '__main__':
    unittest.main()
