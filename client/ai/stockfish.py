import json
import queue
import sys
import threading
from pathlib import Path
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import chess.engine


SEARCH_DEPTHS = {'Easy': 5, 'Normal': 10, 'Hard': 15}
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
        params = {'fen': board.fen(), 'depth': self.depth}
        headers = {'User-Agent': 'PixelChess/1.0', 'Accept': 'application/json'}
        if self.api_key:
            params['key'] = self.api_key
        for attempt in range(2):
            request = Request(f'{API_URL}?{urlencode(params)}', headers=headers)
            try:
                with urlopen(request, timeout=20) as response:
                    data = json.load(response)
                break
            except HTTPError as exc:
                if exc.code in (401, 403) and not attempt and self.api_key and not self.closed:
                    exc.close()
                    del params['key']
                    continue
                if exc.code == 403:
                    mode = 'key' if 'key' in params else 'guest'
                    with exc:
                        try:
                            body = json.loads(exc.read(8192))
                        except (ValueError, UnicodeError):
                            body = None
                    detail = body.get('data') if isinstance(body, dict) else None
                    reason = str(detail)[:180] if detail else 'Access refused.'
                    raise ValueError(f'HTTP 403 ({mode}): {reason}') from exc
                if attempt or exc.code not in (502, 503, 504) or self.closed:
                    raise
            except (URLError, TimeoutError, ConnectionError, HTTPException):
                if attempt or self.closed:
                    raise
        if not isinstance(data, dict) or data.get('success') is not True:
            reason = data.get('data') if isinstance(data, dict) else None
            raise ValueError(str(reason or 'Request rejected.')[:180])
        best = data.get('bestmove')
        tokens = best.split() if isinstance(best, str) else []
        if len(tokens) < 2 or tokens[0] != 'bestmove':
            raise ValueError('Invalid StockfishOnline response.')
        move = board.parse_uci(tokens[1])
        if 'key' not in params:
            self.api_key = ''
        return move

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
                message = str(exc) or type(exc).__name__
                if self.api_key:
                    message = message.replace(self.api_key, '[redacted]')
                self.results.put((snapshot.fen(), None, message))
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
