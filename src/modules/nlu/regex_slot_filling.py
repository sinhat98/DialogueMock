import re

# 半角・全角の数字に対応する数字パターン
digit_pattern = r'[0-9０-９]'

# 既存の正規表現パターン
date_pattern = fr'(?P<date>{digit_pattern}{{1,2}}/{digit_pattern}{{1,2}})'
time_pattern = fr'(?P<time>{digit_pattern}{{1,2}}:{digit_pattern}{{2}})'
n_person_pattern = r'(?P<people>(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)(?:人|名))'

# 任意の単語リストからパターンを作成する関数
def create_word_pattern(word_list, slot_name):
    # 特殊文字をエスケープ
    escaped_words = [re.escape(word) for word in word_list]
    # 単語をパイプで連結してパターンを作成
    pattern = '|'.join(escaped_words)
    # 名前付きグループを作成
    return f'(?P<{slot_name}>{pattern})'

# 名前のリスト
name_list = ['山田', '佐藤', '小田']

# 名前のパターンを作成
name_pattern = create_word_pattern(name_list, 'name')

# すべてのパターンを結合
combined_pattern = f'{date_pattern}|{time_pattern}|{n_person_pattern}|{name_pattern}'

def extract_slots(slots: dict, text: str) -> dict:
    
    matches = re.finditer(combined_pattern, text)
    for slot_key in slots.keys():
        for match in matches:
            if match.group(slot_key):
                slots[slot_key].append(match.group(slot_key))
                
    # for match in matches:
    #     if match.group('date'):
    #         slots['date'].append(match.group('date'))
    #     if match.group('time'):
    #         slots['time'].append(match.group('time'))
    #     if match.group('people'):
    #         slots['people'].append(match.group('people'))
    #     if match.group('name'):
    #         slots['name'].append(match.group('name'))

    return slots

# テスト用サンプルテキスト
text = "山田さんと佐藤さんは12/25の18:30に十五人で集まります。小田さんは1/1の12:00に四名で参加します。さらに、３/３に８人で会います。"

slots = {'date': [], 'time': [], 'people': [], 'name': []}

# スロットフィリングの実行
extracted_slots = extract_slots(slots, text)

# 結果の表示
print("Extracted Slots:")
print("Dates:", extracted_slots['date'])
print("Times:", extracted_slots['time'])
print("People:", extracted_slots['people'])
print("Names:", extracted_slots['name'])