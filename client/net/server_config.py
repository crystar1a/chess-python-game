from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / '.server_address'


def parse_address(value):
    value = value.strip()
    host, sep, port_text = value.partition(':')
    if not host or any(ch.isspace() for ch in host) or ':' in port_text:
        raise ValueError('Địa chỉ server không hợp lệ')
    try:
        port = int(port_text) if sep else 8765
    except ValueError:
        raise ValueError('Cổng server không hợp lệ') from None
    if not 1 <= port <= 65535:
        raise ValueError('Cổng server không hợp lệ')
    return host, port


def load_address():
    try:
        value = CONFIG_PATH.read_text(encoding='utf-8').strip()
        parse_address(value)
        return value
    except (OSError, UnicodeError, ValueError):
        return '127.0.0.1:8765'


def save_address(value):
    host, port = parse_address(value)
    CONFIG_PATH.write_text(f'{host}:{port}', encoding='utf-8')
    return host, port
