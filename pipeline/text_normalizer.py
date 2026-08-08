"""Tiền xử lý văn bản tiếng Việt cho TTS."""
import re

DIGITS = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']

UNIT_MAP = {
    'km/h': 'ki-lô-mét trên giờ', 'km²': 'ki-lô-mét vuông',
    'm²': 'mét vuông', 'km': 'ki-lô-mét', 'cm': 'xen-ti-mét',
    'mm': 'mi-li-mét', 'kg': 'ki-lô-gam', 'mg': 'mi-li-gam',
    'ml': 'mi-li-lít', 'm': 'mét', 'g': 'gam', 'l': 'lít',
}

# ===== SỐ → CHỮ =====
def _read_tens(n, after_hundred=False):
    if n == 0:
        return ''
    if n < 10:
        return ('lẻ ' if after_hundred else '') + DIGITS[n]
    if n == 10:
        return 'mười'
    if n < 20:
        ones = n % 10
        return 'mười ' + ('lăm' if ones == 5 else DIGITS[ones])
    tens, ones = n // 10, n % 10
    result = DIGITS[tens] + ' mươi'
    if ones == 1:
        result += ' mốt'
    elif ones == 4:
        result += ' tư'
    elif ones == 5:
        result += ' lăm'
    elif ones > 0:
        result += ' ' + DIGITS[ones]
    return result

def _read_group(n, leading=True):
    if n == 0:
        return ''
    h, rest = n // 100, n % 100
    if h > 0:
        result = DIGITS[h] + ' trăm'
        if rest > 0:
            result += ' ' + _read_tens(rest, True)
        return result
    if leading:
        return _read_tens(rest)
    return 'không trăm ' + _read_tens(rest, True)

SCALES = ['', 'nghìn', 'triệu', 'tỷ']

def num_to_words(n):
    """Chuyển số nguyên thành chữ tiếng Việt."""
    if n < 0:
        return 'âm ' + num_to_words(-n)
    if n == 0:
        return 'không'
    groups = []
    while n > 0:
        groups.append(n % 1000)
        n //= 1000
    if len(groups) > len(SCALES):
        return ' '.join(DIGITS[int(d)] for d in str(n))
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i] == 0:
            continue
        text = _read_group(groups[i], i == len(groups) - 1)
        if SCALES[i]:
            text += ' ' + SCALES[i]
        parts.append(text)
    return ' '.join(parts) or 'không'

def _read_decimal(s):
    """Đọc phần thập phân (giữ leading zeros)."""
    if s.startswith('0'):
        return ' '.join(DIGITS[int(d)] for d in s)
    return num_to_words(int(s))

# ===== NORMALIZE =====
def normalize_text_for_tts(text):
    """Chuẩn hoá văn bản tiếng Việt để TTS đọc đúng."""

    # 1. Bỏ dấu phẩy phân cách hàng nghìn: 71,173 → 71173
    while True:
        new = re.sub(r'(\d),(\d{3})(?!\d)', r'\1\2', text)
        if new == text:
            break
        text = new

    # 2. Đơn vị đo (xử lý TRƯỚC khi số biến thành chữ)
    for unit, word in sorted(UNIT_MAP.items(), key=lambda x: -len(x[0])):
        text = re.sub(
            r'(\d)\s*' + re.escape(unit) + r'(?![a-zA-Z])',
            r'\1 ' + word, text
        )

    # 3. Luỹ thừa: 10^20
    text = re.sub(
        r'(\d+)\s*\^\s*(\d+)',
        lambda m: f"{num_to_words(int(m[1]))} mũ {num_to_words(int(m[2]))}",
        text
    )

    # 4. Phân số: 1/1000
    text = re.sub(
        r'(\d+)\s*/\s*(\d+)',
        lambda m: f"{num_to_words(int(m[1]))} phần {num_to_words(int(m[2]))}",
        text
    )

    # 5. Phần trăm thập phân: 8.02%
    text = re.sub(
        r'(\d+)\.(\d+)\s*%',
        lambda m: f"{num_to_words(int(m[1]))} phẩy {_read_decimal(m[2])} phần trăm",
        text
    )

    # 6. Phần trăm nguyên: 50%
    text = re.sub(
        r'(\d+)\s*%',
        lambda m: f"{num_to_words(int(m[1]))} phần trăm",
        text
    )

    # 7. Số thập phân: 71173.2
    text = re.sub(
        r'(\d+)\.(\d+)',
        lambda m: f"{num_to_words(int(m[1]))} phẩy {_read_decimal(m[2])}",
        text
    )

    # 8. Dải số: 400-499 (chỉ khi 2 bên là số, tránh dấu gạch ngang thường)
    text = re.sub(
        r'(?<!\w)(\d+)\s*-\s*(\d+)(?!\w)',
        lambda m: f"{num_to_words(int(m[1]))} đến {num_to_words(int(m[2]))}",
        text
    )

    return text


if __name__ == '__main__':
    test = (
        "rộng thêm 71,173.2 m, tức là hơn 71 km "
        "chỉ số GDP tăng 8.02%; tốc độ là 1/1000 giây. "
        "Boss cấp Trụ Thần từ level 400-499. chỉ số 10^20"
    )
    print("=== GỐC ===")
    print(test)
    print("\n=== SAU NORMALIZE ===")
    print(normalize_text_for_tts(test))
