from datetime import datetime

def validate_time(time_str):
    """
    時間表現 HH:MM 形式のバリデーションを行う（00:00から23:59まで）。
    """
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False

def validate_date(date_str):
    """
    日付表現 mm:dd 形式のバリデーションを行う（1月1日から12月31日まで）。
    """
    try:
        datetime.strptime(date_str, "%m/%d")
        return True
    except ValueError:
        return False

def validate_n_person(num_str):
    """
    人数表現のバリデーションを行う。整数のみ許可。
    """
    try:
        num = int(num_str)
        return num >= 0
    except ValueError:
        return False