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
    r'(?:'
    r'\b\d{1,2}[A-Z]\s+[A-Z]{2}\s+\d{4,6}\s+\d{4,6}\b'   # spaced: 37U DP 20486 89366
    r'|'
    r'\b\d{1,2}[A-Z]\s+[A-Z]{2}\s*\d{8,12}\b'             # compact: 37U DP1844185789
    r')',
    re.IGNORECASE,
)

_RESULT_MAP = {
    # Standard terms
    'знищено':          'destroyed',
    'знищений':         'destroyed',
    'знищена':          'destroyed',
    'пошкоджено':       'damaged',
    'пошкоджений':      'damaged',
    'не вражено':       'missed',
    'промах':           'missed',
    'невідомо':         'unknown',
    # Mission-success synonyms
    'заміновано':       'destroyed',   # mining complete
    'замінована':       'destroyed',
    'доставлено':       'destroyed',   # logistics delivery complete
    'влучання':         'destroyed',   # confirmed hit
    'відпрацював':      'destroyed',   # completed attack run
    # Miss / abort synonyms
    'не знайдено':      'missed',
    'ціль не знайдено': 'missed',
    'цілей не знайдено': 'missed',
    'нерозрив':         'missed',      # didn't detonate
    'не розрив':        'missed',      # variant spelling with space
    'волокно':          'missed',      # FPV fiber ran out / was cut = mission aborted
    'обри':             'missed',      # обрив = connection break (substring match)
    # Verbal-noun forms
    'знищення':         'destroyed',   # verbal noun "destruction"
    'уражено':          'destroyed',   # hit / struck
    'уражений':         'destroyed',
    'уражена':          'destroyed',
    'повернулись':      'missed',      # returned / aborted sortie
    'повернення':       'missed',
    # Casualty-count slang (FPV reports)
    '200':              'destroyed',   # KIA (killed in action)
    '300':              'damaged',     # WIA (wounded in action)
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
    s = raw.lower().strip()
    if s in _RESULT_MAP:
        return _RESULT_MAP[s]
    # Substring fallback for free-text result lines (e.g. "Ціль не знайдено, …")
    # Short keys (≤3 chars like '200', '300') are exact-match only to avoid
    # false positives in ammo names like 'Ф3000', 'КУ3000'.
    for key, val in _RESULT_MAP.items():
        if len(key) > 3 and key in s:
            return val
    return 'unknown'


# ── Format 1: key-value ───────────────────────────────────────────────────────

_KV_RE = re.compile(
    r'^(?:\w+\s+)?'   # optional prefix word (e.g. "планова" before "Ціль")
    r'(Поз|Позиція|ЕК|Екіпаж|Засіб|Дрон|БК|Бк|Б[/.]К|Ціль|Рез|Результат|Розташування)'
    r'[.:/\s]+(.+)$',
    re.IGNORECASE | re.UNICODE,
)

_KV_ALIASES = {
    'поз':         'pozyvnyi',
    'позиція':     '_location',
    'ек':          'crew',
    'екіпаж':      'crew',
    'засіб':       'zasib',
    'дрон':        'zasib',
    'бк':          'bk',
    'б/к':         'bk',
    'б.к':         'bk',
    'ціль':        'target',
    'рез':         '_result_raw',
    'результат':   '_result_raw',
    'розташування': '_location',
}

def _parse_kv(lines: list[str]) -> list[dict] | None:
    fields: dict[str, str] = {}
    coordinates = ''
    plain_lines: list[str] = []   # non-kv, non-skip, non-MGRS lines

    for line in lines:
        mgrs_m = _MGRS_RE.search(line)
        if mgrs_m:
            coordinates = mgrs_m.group(0)   # store just the MGRS token
            # Also parse any KV key on the same line (e.g. "Ціль:37U DP 21438 88685")
            kv_m = _KV_RE.match(line)
            if kv_m:
                key = kv_m.group(1).lower()
                alias = _KV_ALIASES.get(key)
                if alias and alias not in fields:
                    raw_val = kv_m.group(2).strip()
                    non_mgrs = _MGRS_RE.sub('', raw_val).strip()
                    fields[alias] = non_mgrs if non_mgrs else raw_val
            continue
        if _SKIP_RE.match(line):
            continue
        m = _KV_RE.match(line)
        if m:
            key   = m.group(1).lower()
            value = m.group(2).strip()
            alias = _KV_ALIASES.get(key)
            if alias and alias not in fields:   # first occurrence wins
                fields[alias] = value
                continue
        # Not absorbed as a KV field → keep as plain text
        plain_lines.append(line.strip())

    # If no explicit "Результат:" line, scan plain lines for result keywords
    if '_result_raw' not in fields:
        for pl in plain_lines:
            if _normalize_result(pl) != 'unknown':
                fields['_result_raw'] = pl
                break

    # "Позиція/Екіпаж" positional format: infer zasib, bk, target from plain_lines order
    # Triggers when a location was parsed (via "Позиція X") but target label was absent.
    if 'target' not in fields and '_location' in fields and plain_lines:
        # Exclude lines that are recognised result keywords
        structural = [pl for pl in plain_lines if _normalize_result(pl) == 'unknown']
        if structural:
            # If index 0 has no digits it is likely a sender callsign — skip it
            start = 0
            if len(structural) > 1 and not re.search(r'\d', structural[0]):
                start = 1
            remaining = structural[start:]
            if remaining:
                if 'zasib' not in fields:
                    fields['zasib'] = remaining[0]
                if 'bk' not in fields and len(remaining) >= 3:
                    fields['bk'] = remaining[1]
                # Target: 3rd item if available, otherwise the last item
                fields['target'] = remaining[2] if len(remaining) >= 3 else remaining[-1]

    # Require at least a target (checked after positional inference above)
    if 'target' not in fields:
        return None

    # '_location' can serve as coordinates if no MGRS found
    if not coordinates and '_location' in fields:
        coordinates = fields['_location']

    result_raw = fields.pop('_result_raw', '')
    fields.pop('_location', None)

    # Pozyvnyi: explicit field > first plain line
    if 'pozyvnyi' not in fields and plain_lines:
        fields['pozyvnyi'] = plain_lines[0]

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

# "Склад ПММ - Знищено" or "АТ – Пошкоджено" or "1 - 300" (casualty slang)
# Trailing notes in parentheses are allowed: "Квадроцикл - Знищено (допрацювання…)"
_HIT_RE = re.compile(
    r'^(.+?)\s*[-–—]\s*(Знищен\w*|Пошкоджен\w*|Уражен\w*|Не\s+вражено|Промах|Невідомо|200|300).*$',
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


# ── Format 3: positional "засіб з" ────────────────────────────────────────────
# e.g.: Сузукі / Бешкет 10 з ПГ-9С 20км / Влучання в квадроцикл / Венера Синій 34

# Drone + number + "з" + payload:  "Бешкет 10 з АО 2.5 20км"
_ZASIB_INLINE_RE = re.compile(
    r'^\S+\s+\d+[\w.]*\s+з\s+\S', re.IGNORECASE | re.UNICODE
)


def _parse_zasib_inline(lines: list[str]) -> list[dict] | None:
    """Format 3: pozyvnyi / zasib (inline z payload) / result description / [crew]"""
    zasib_idx = next(
        (i for i, l in enumerate(lines) if _ZASIB_INLINE_RE.match(l)), -1
    )
    if zasib_idx < 0:
        return None

    zasib = lines[zasib_idx]
    pozyvnyi = lines[zasib_idx - 1] if zasib_idx > 0 and not _SKIP_RE.match(lines[zasib_idx - 1]) else ''

    # Collect remaining non-skip, non-MGRS lines after zasib
    coordinates = ''
    after: list[str] = []
    for line in lines[zasib_idx + 1:]:
        if _MGRS_RE.search(line):
            coordinates = _MGRS_RE.search(line).group(0)
            continue
        if _SKIP_RE.match(line):
            continue
        after.append(line.strip())

    if not after:
        return None

    # First line after zasib is the result/description; last is crew if >1 lines
    result_line = after[0]
    crew = after[-1] if len(after) > 1 else ''

    return [{
        'pozyvnyi':    pozyvnyi,
        'crew':        crew,
        'zasib':       zasib,
        'bk':          '',
        'target':      result_line,   # target described in result line
        'coordinates': coordinates,
        'result':      _normalize_result(result_line),
    }]


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

    result = _parse_zasib_inline(lines)
    if result:
        return result

    return []
