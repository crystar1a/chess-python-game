import json
import queue
import sys
import threading
from pathlib import Path
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import chess.engine


SEARCH_DEPTHS = {'Easy': 3, 'Normal': 8, 'Hard': 15}
API_URL = 'https://stockfish.online/api/s/v2.php'
ENGINE_DIR = Path(__file__).resolve().parent / 'stockfish'
API_KEY_FILE = ENGINE_DIR / 'api.txt'


def engine_path():
    executable = {
        'win32': 'stockfish-windows-x86-64-universal.exe',
        'linux': 'stockfish-linux-x86-64-universal',
    }.get(sys.platform, 'stockfish')
    return str(ENGINE_DIR / executable)


class Engine:
    def __init__(self, difficulty='Normal'):
        self.depth = SEARCH_DEPTHS[difficulty]
        self.api_key = ''
        self.online = not Path(engine_path()).is_file()
        if self.online:
            try:
                self.api_key = API_KEY_FILE.read_text(encoding='utf-8-sig').strip()
            except (OSError, UnicodeError):
                pass
        self.results = queue.Queue()
        self.process = None
        self.thread = None
        self.closed = False
        self.lock = threading.Lock()

    def online_move(self, board):
        query = urlencode({'fen': board.fen(), 'depth': self.depth})
        headers = {'X-API-Key': self.api_key} if self.api_key else {}
        request = Request(f'{API_URL}?{query}', headers=headers)
        with urlopen(request, timeout=12) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get('success') is not True:
            raise ValueError('StockfishOnline rejected the request.')
        best = data.get('bestmove')
        tokens = best.split() if isinstance(best, str) else []
        if len(tokens) < 2 or tokens[0] != 'bestmove':
            raise ValueError('Invalid StockfishOnline response.')
        return board.parse_uci(tokens[1])

    def start(self, board):
        snapshot = board.copy()

        def work():
            engine = None
            try:
                if self.online:
                    move = self.online_move(snapshot)
                    self.results.put((snapshot.fen(), move, None))
                    return
                engine = chess.engine.SimpleEngine.popen_uci(engine_path())
                with self.lock:
                    self.process = engine
                    closed = self.closed
                if closed:
                    return
                result = engine.play(snapshot, chess.engine.Limit(depth=self.depth))
                self.results.put((snapshot.fen(), result.move, None))
            except (HTTPException, ValueError, OSError, chess.engine.EngineError, RuntimeError) as exc:
                self.results.put((snapshot.fen(), None, str(exc)))
            finally:
                if engine:
                    try:
                        engine.quit()
                    except (chess.engine.EngineError, OSError, RuntimeError):
                        engine.close()
                with self.lock:
                    self.process = None

        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def close(self):
        with self.lock:
            self.closed = True
            process = self.process
        if process:
            process.close()
