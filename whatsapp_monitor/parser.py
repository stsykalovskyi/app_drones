"""
Parse WhatsApp strike/sortie reports.

Supported formats:

Format 1 — key-value (Avenger / mining):
    Циган
    +380 66 538 7679
    0:08
    Ціль: Мінування
    Розташування: Дубово-Василівка
    37U DP 20486 89366
    Дрон: Avenger
    Бк: ПТМ 2.4
    Виліт: 19:00
    Дата: 08.03.2026
    Екіпаж: Гарпія
    Результат: Заміновано

Format 2 — FPV strike (one or many targets):
    20:19 08.03.2026
    FPV ББпС 56:
    Склад ПММ - Знищено
    Генератор - Знищено
    Оскар Червоний 123
    37U DP 22052 89033
"""
import re

# ── shared ────────────────────────────────────────────────────────────────────

_MGRS_RE = re.compile(
    r'\b\d{1,2}[A-Z]\s+[A-Z]{2}\s+\d{4,6}\s+\d{4,6}\b', re.IGNORECASE
)

_RESULT_MAP = {
    'знищено':     'destroyed',
    'знищений':    'destroyed',
    'знищена':     'destroyed',
    'пошкоджено':  'damaged',
    'пошкоджений': 'damaged',
    'не вражено':  'missed',
    'промах':      'missed',
    'невідомо':    'unknown',
    'заміновано':  'destroyed',   # mining mission complete = success
    'замінована':  'destroyed',
}

# Lines to silently skip when scanning for positional tokens
_SKIP_RE = re.compile(
    r'^(\+?\d[\d\s\-\(\)]{7,}'   # phone numbers
    r'|\d{1,2}:\d{2}$'            # bare time  "0:08"
    r'|\d{1,2}:\d{2}\s+\d{2}\.\d{2}\.\d{4}'  # datetime "20:19 08.03.2026"
    r'|https?://\S+'              # URLs
    r')$'
)


def _normalize_result(raw: str) -> str:
    return _RESULT_MAP.get(raw.lower().strip(), 'unknown')


# ── Format 1: key-value ───────────────────────────────────────────────────────

_KV_RE = re.compile(
    r'^(Поз|ЕК|Екіпаж|Засіб|Дрон|БК|Бк|Ціль|Рез|Результат|Розташування)'
    r'[.:\s]+(.+)$',
    re.IGNORECASE | re.UNICODE,
)

_KV_ALIASES = {
    'поз':         'pozyvnyi',
    'ек':          'crew',
    'екіпаж':      'crew',
    'засіб':       'zasib',
    'дрон':        'zasib',
    'бк':          'bk',
    'ціль':        'target',
    'рез':         '_result_raw',
    'результат':   '_result_raw',
    'розташування': '_location',
}

def _parse_kv(lines: list[str]) -> list[dict] | None:
    fields: dict[str, str] = {}
    coordinates = ''
    first_plain = ''   # first non-kv, non-skip, non-MGRS line = pozyvnyi candidate

    for line in lines:
        m = _KV_RE.match(line)
        if m:
            key   = m.group(1).lower()
            value = m.group(2).strip()
            alias = _KV_ALIASES.get(key)
            if alias:
                fields[alias] = value
        elif _MGRS_RE.search(line):
            coordinates = line.strip()
        elif not _SKIP_RE.match(line) and not first_plain:
            first_plain = line.strip()

    # Require at least a target and a result (translated field names)
    if 'target' not in fields or '_result_raw' not in fields:
        return None

    # '_location' can serve as coordinates if no MGRS found
    if not coordinates and '_location' in fields:
        coordinates = fields['_location']

    result_raw = fields.pop('_result_raw', '')
    fields.pop('_location', None)

    if not result_raw:
        return None

    # Pozyvnyi: explicit field > first plain line
    if 'pozyvnyi' not in fields and first_plain:
        fields['pozyvnyi'] = first_plain

    return [{
        'pozyvnyi':    fields.get('pozyvnyi', ''),
        'crew':        fields.get('crew', ''),
        'zasib':       fields.get('zasib', ''),
        'bk':          fields.get('bk', ''),
        'target':      fields.get('target', ''),
        'coordinates': coordinates,
        'result':      _normalize_result(result_raw),
    }]


# ── Format 2: FPV ─────────────────────────────────────────────────────────────

# "FPV ББпС 56:" or "ФПВ ббпс 3:"
_FPV_HEADER_RE = re.compile(
    r'^((?:FPV|ФПВ)\s+ббпс\s+\d+)\s*:?\s*$', re.IGNORECASE
)

# "Склад ПММ - Знищено" or "АТ – Пошкоджено"
_HIT_RE = re.compile(
    r'^(.+?)\s*[-–—]\s*(Знищено\w*|Пошкоджено\w*|Не\s+вражено|Промах|Невідомо)$',
    re.IGNORECASE,
)


def _parse_fpv(lines: list[str]) -> list[dict] | None:
    zasib       = ''
    hits:  list[tuple[str, str]] = []   # (target, result_raw)
    coordinates = ''
    leftover:  list[str] = []           # lines not matched to anything

    for line in lines:
        if _MGRS_RE.search(line):
            coordinates = line.strip()
            continue
        m = _FPV_HEADER_RE.match(line)
        if m:
            zasib = m.group(1).strip()
            continue
        m = _HIT_RE.match(line)
        if m:
            hits.append((m.group(1).strip(), m.group(2).strip()))
            continue
        if not _SKIP_RE.match(line):
            leftover.append(line.strip())

    if not zasib or not hits:
        return None

    # Last leftover line that isn't a date = pozyvnyi
    pozyvnyi = leftover[-1] if leftover else ''

    return [
        {
            'pozyvnyi':    pozyvnyi,
            'crew':        '',
            'zasib':       zasib,
            'bk':          '',
            'target':      target,
            'coordinates': coordinates,
            'result':      _normalize_result(result_raw),
        }
        for target, result_raw in hits
    ]


# ── public API ────────────────────────────────────────────────────────────────

def parse_report(text: str) -> list[dict]:
    """
    Parse a raw WhatsApp message.
    Returns a list of dicts (one per target), or [] if format not recognised.
    Each dict has keys: pozyvnyi, crew, zasib, bk, target, coordinates, result.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return []

    result = _parse_kv(lines)
    if result:
        return result

    result = _parse_fpv(lines)
    if result:
        return result

    return []
