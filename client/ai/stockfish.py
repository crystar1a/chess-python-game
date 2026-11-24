import queue
import sys
import threading
from pathlib import Path

import chess.engine


SKILL_LEVELS = {'Easy': 0, 'Normal': 10, 'Hard': 20}


def engine_path():
    executable = {
        'win32': 'stockfish-windows-x86-64-universal.exe',
        'linux': 'stockfish-linux-x86-64-universal',
    }.get(sys.platform, 'stockfish')
    return str(Path(__file__).resolve().parent / 'stockfish' / executable)


class Engine:
    def __init__(self, difficulty='Normal'):
        self.skill = SKILL_LEVELS[difficulty]
        self.results = queue.Queue()
        self.process = None
        self.thread = None
        self.closed = False
        self.lock = threading.Lock()

    def start(self, board):
        snapshot = board.copy()

        def work():
            engine = None
            try:
                engine = chess.engine.SimpleEngine.popen_uci(engine_path())
                with self.lock:
                    self.process = engine
                    closed = self.closed
                if closed:
                    return
                engine.configure({'Skill Level': self.skill})
                result = engine.play(snapshot, chess.engine.Limit(time=0.5))
                self.results.put((snapshot.fen(), result.move, None))
            except (OSError, chess.engine.EngineError, RuntimeError) as exc:
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
