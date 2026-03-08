"""
Parse WhatsApp strike reports.

Expected format (fields may be in any order, case-insensitive):
    Поз: Шнурок
    ЕК: Злюка
    Засіб: Бомбус 10 20км
    БК: ку900
    Ціль: мотоцикл
    37U DP 16599 89378
    Рез. знищено
"""
import re

# Matches MGRS coordinates: e.g. "37U DP 16599 89378"
_MGRS_RE = re.compile(r'\d{1,2}[A-Z]\s+[A-Z]{2}\s+\d{4,6}\s+\d{4,6}', re.IGNORECASE)

# Matches labelled field lines: "Поз: value", "Рез. value", "Рез: value"
_FIELD_RE = re.compile(
    r'^(Поз|ЕК|Засіб|БК|Ціль|Рез)[.:\s]+(.+)$',
    re.IGNORECASE,
)

# Normalize result string → model constant
_RESULT_MAP = {
    'знищено':    'destroyed',
    'знищений':   'destroyed',
    'знищена':    'destroyed',
    'знищений':   'destroyed',
    'пошкоджено': 'damaged',
    'пошкоджений':'damaged',
    'не вражено': 'missed',
    'промах':     'missed',
    'невідомо':   'unknown',
}

# Minimum required fields to consider a message a valid report
_REQUIRED = {'поз', 'ціль', 'рез'}


def parse_report(text: str) -> dict | None:
    """
    Parse a raw WhatsApp message.
    Returns a dict with keys matching StrikeReport fields, or None if the
    message does not match the expected format.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    fields: dict[str, str] = {}
    coordinates = ''

    for line in lines:
        m = _FIELD_RE.match(line)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            fields[key] = val
        elif _MGRS_RE.search(line):
            coordinates = line.strip()

    # Check required fields present
    if not _REQUIRED.issubset(fields.keys()):
        return None

    # Normalize result
    raw_result = fields.get('рез', '').lower().strip()
    result = _RESULT_MAP.get(raw_result, 'unknown')

    return {
        'pozyvnyi':    fields.get('поз', ''),
        'crew':        fields.get('ек', ''),
        'zasib':       fields.get('засіб', ''),
        'bk':          fields.get('бк', ''),
        'target':      fields.get('ціль', ''),
        'coordinates': coordinates,
        'result':      result,
    }
