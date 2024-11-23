def validate_date(value: str) -> bool:
    parts = value.split('/')
    if not (2 <= len(parts) <= 3):
        return False

    try:
        if len(parts) == 2:  # mm/dd形式
            month, day = map(int, parts)
            return is_valid_date(month, day)
        else:  # yyyy/mm/dd または yy/mm/dd形式
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])

            # 2桁年の場合は20xx年として扱う
            if year < 100:
                year += 2000

            # 年の範囲を1900年から2100年までに設定
            if not 1900 <= year <= 2100:
                return False

            # 閏年の場合の2月の日数チェック
            if month == 2 and day == 29:
                return is_leap_year(year)

            return is_valid_date(month, day)
    except ValueError:
        return False

def validate_time(value: str) -> bool:
    try:
        parts = value.split(':')
        if len(parts) != 2:
            return False
        hour, minute = map(int, parts)
        return is_valid_time(hour, minute)
    except ValueError:
        return False

def validate_person_count(value: str) -> bool:
    try:
        num = int(value)
        return num > 0
    except ValueError:
        return False

def validate_phone_number(value: str) -> bool:
    # 数字以外の文字を削除
    digits = ''.join(filter(str.isdigit, value))
    
    if len(digits) not in {10, 11}:
        return False

    prefixes = {
        '0', '03', '06', '070', '080', '090',
        '050', '0120', '0800', '0570'
    }

    return any(digits.startswith(prefix) for prefix in prefixes)

def validate_postal_code(value: str) -> bool:
    digits = ''.join(filter(str.isdigit, value))
    return len(digits) == 7

def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def is_valid_date(month: int, day: int) -> bool:
    if not (1 <= month <= 12):
        return False

    days_in_month = {
        1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
    }

    max_days = days_in_month[month]
    return 1 <= day <= max_days

def is_valid_time(hour: int, minute: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59
