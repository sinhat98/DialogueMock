from datetime import datetime
import re
from src.modules.dialogue.utils import Slot

def convert_date_format(text: str) -> str:
    # 日付パターンの正規表現
    date_patterns = [
        r'(\d{2})/(\d{2})/(\d{2})',  # YY/MM/DD
        r'(\d{4})/(\d{2})/(\d{2})',  # YYYY/MM/DD
        r'(\d{1,2})/(\d{1,2})',      # MM/DD
        r'(\d{2})月(\d{2})日'        # MM月DD日
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 3 and len(groups[0]) == 2:  # YY/MM/DD形式の場合
                    year = int('20' + groups[0])  # 20XX年と仮定
                    month = int(groups[1])
                    day = int(groups[2])
                elif len(groups) == 3 and len(groups[0]) == 4:  # YYYY/MM/DD形式の場合
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                elif len(groups) == 2:  # MM/DD形式またはMM月DD日形式の場合
                    current_year = datetime.now().year
                    month = int(groups[0])
                    day = int(groups[1])
                    year = current_year

                # datetime オブジェクトに変換
                date_obj = datetime(year, month, day)
                
                # M月D日 形式に変換して返す
                return date_obj.strftime("%-m月%-d日")  # Windowsの場合は "#" を使用

            except ValueError:
                continue
    
    return ""

def convert_time_format(text: str) -> str:
    def replace_time(match: re.Match) -> str:
        try:
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            # minuteが0の場合は分の部分を省略
            if minute == 0:
                return f"{hour}時"
            
            return f"{hour}時{minute}分"
            
        except ValueError:
            return match.group(0)

    # HH:MM形式の時間を変換
    pattern = r'(\d{1,2}):(\d{2})'
    return re.sub(pattern, replace_time, text)


def format_entity(slots: dict):
    formatted_slots = {}
    for key, value in slots.items():
        if key == Slot.DATE:
            formatted_slots[key] = convert_date_format(value)
        elif key == Slot.TIME:
            formatted_slots[key] = convert_time_format(value)
        else:
            formatted_slots[key] = value
    return formatted_slots