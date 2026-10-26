"""Formatting and state selection for the M10's 240 x 320 display."""
import re
import unicodedata


def clean_text(text):
    lines = []
    for line in str(text).splitlines():
        line = ''.join(c for c in line if not (
            0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF or
            unicodedata.category(c) == 'Cs' or c in ('\ufe0f', '\u200d')))
        line = line.strip()
        line = re.sub(r'(?<=\d)[ \u3000]+dBFS\b', 'dBFS', line)
        if line and re.fullmatch(r'[━─═_\-=\s]{3,}', line):
            continue
        lines.append(line)
    # Strip surrounding blank lines only; meaningful paragraph breaks survive.
    return '\n'.join(lines).strip()


def wrap_text(text, measure, width):
    """Wrap using the installed font's measured pixel width, preserving content."""
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue
        line = ''
        for char in paragraph:
            if line and measure(line + char) > width:
                token = re.search(r'[A-Za-z0-9._/-]+$', line)
                if (char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-'
                        and token and token.start() > 0
                        and measure(token.group() + char) <= width):
                    lines.append(line[:token.start()])
                    line = token.group() + char
                    continue
                # Keep closing punctuation with the word before it. A lone
                # Chinese full stop on a 240 px screen looks like a stray dot.
                if char in '，。！？；：、' and len(line) > 2:
                    if token and token.start() > 0 and measure(token.group() + char) <= width:
                        lines.append(line[:token.start()])
                        line = token.group() + char
                        continue
                    boundary = max(line.rfind(mark) for mark in '，。！？；：、')
                    if max(4, len(line) // 3) <= boundary < len(line) - 2:
                        lines.append(line[:boundary + 1])
                        line = line[boundary + 1:] + char
                    else:
                        lines.append(line[:-2])
                        line = line[-2:] + char
                else:
                    lines.append(line)
                    line = char
            else:
                line += char
        lines.append(line)
    return lines or ['']


def paginate(text, measure, width, rows=4):
    pages = []
    current = []
    for paragraph in text.split('\n\n'):
        block = wrap_text(paragraph, measure, width)
        # Keep a short paragraph together instead of leaving its first line
        # at the foot of one page and its continuation at the next page's top.
        if current and len(current) + 1 + len(block) > rows:
            pages.append(current)
            current = []
        elif current:
            current.append('')
        while block:
            capacity = rows - len(current)
            current.extend(block[:capacity])
            block = block[capacity:]
            if block:
                pages.append(current)
                current = []
    if current or not pages:
        pages.append(current or [''])
    return pages


def paginate_message(text, measure, width, rows=6):
    """Keep each explicit reply line together where it fits on one page."""
    pages = []
    current = []
    for source_line in text.split('\n'):
        if not source_line:
            if current and current[-1] != '' and len(current) < rows - 1:
                current.append('')
            continue
        block = wrap_text(source_line, measure, width)
        if current and len(current) + len(block) > rows:
            pages.append(current)
            current = []
        while len(block) > rows:
            take = rows - 1 if len(block) == rows + 1 else rows
            pages.append(block[:take])
            block = block[take:]
        current.extend(block)
    if current or not pages:
        pages.append(current or [''])
    return pages


def shorten(text, measure, width):
    if measure(text) <= width:
        return text
    while text and measure(text + '…') > width:
        text = text[:-1]
    return text + '…'


def screen_state(data, mode):
    if mode == 'dashboard' and not data.get('preview'):
        return 'dashboard'
    text = data.get('text', '')
    source = data.get('source', '')
    # Explicit phase is available for UI previews and future agent revisions.
    explicit = data.get('ui_state')
    if explicit in ('dashboard', 'ready', 'recording', 'sending', 'sent', 'failed', 'message'):
        return explicit
    if not text:
        return 'ready' if mode == 'work' else 'dashboard'
    if source == 'm10_agent':
        if 'Voice send failed' in text:
            return 'failed'
        if 'Recording finished' in text or 'Sending to' in text:
            return 'sending'
        if 'Recording' in text:
            return 'recording'
        if 'Voice sent' in text:
            return 'sent'
        if 'Returning to dashboard' in text:
            return 'dashboard'
        if 'Press A again' in text:
            return 'ready'
    return 'message'


def memory_available(path='/proc/meminfo'):
    with open(path) as stream:
        values = dict(line.split(':', 1) for line in stream if ':' in line)
    return round(int(values['MemAvailable'].split()[0]) / 1024)


def chip_temperature(base):
    # Select the CPU/SoC thermal zone rather than labelling arbitrary sensors CPU.
    for zone in sorted(base.glob('thermal_zone*')):
        try:
            kind = (zone / 'type').read_text().strip().lower()
            if any(label in kind for label in ('cpu', 'soc', 'rockchip')):
                return round(int((zone / 'temp').read_text()) / 1000, 1)
        except (OSError, ValueError):
            continue
    return None
