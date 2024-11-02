import re
from typing import TypedDict
from enum import Enum

class PatternType(Enum):
    DATE = "date"
    TIME = "time"
    N_PERSON = "n_person"
    NAME = "name"
    
class Slots(TypedDict):
    date: str | None
    time: str | None
    n_person: int | None
    name: str | None


class RuleBasedSlotFiller:
    def __init__(self, patterns: list):
        self.pattern = re.compile('|'.join(patterns))
        
    def extract_slots(self, slots: dict, text: str) -> dict:
        # matchesをリストに変換
        matches = list(re.finditer(self.pattern, text))
        for slot_key in slots.keys():
            for match in matches:
                slot_value = match.group(slot_key)
                if slot_value is not None:
                    slots[slot_key] = self._convert_type(slot_key, slot_value)

        return slots
    
    def _convert_type(self, slot_key: str, slot_value: str) -> str:
        if slot_key == PatternType.N_PERSON.value:
            slot_value = int(slot_value)
        return slot_value
    
if __name__ == "__main__":
    
    # テスト用サンプルテキスト
    text = "10/25の11:00に4名で予約をお願いします。"

    # スロットの初期化
    slots = Slots(date=None, time=None, n_person=None, name=None)

    # 既存の正規表現パターン
    date_pattern = r'(?P<date>[0-9]{1,2}/[0-9]{1,2})'
    time_pattern = r'(?P<time>[0-9]{1,2}:[0-9]{2})'
    n_person_pattern = r'(?P<n_person>(?:[0-9]+))(?:人|名)'
    name_pattern = r'(?P<name>)'

    # パターンを結合
    all_patterns = [date_pattern, time_pattern, n_person_pattern, name_pattern]

    # スロットフィリングの実行
    slot_filler = RuleBasedSlotFiller(all_patterns)
    extracted_slots = slot_filler.extract_slots(slots, text)

    # 結果の表示
    print("Extracted Slots:")
    print(extracted_slots)