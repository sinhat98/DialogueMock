import re

# 正規表現パターン
date_patterns = [
    
    # 相対的な月の週と曜日（例：'再来月3週目の金曜日'）
    r'(?P<relative_month_ext>先月|今月|来月|再来月)の?(?P<week_number>\d{1})(週目)の?(?P<extended_weekday>月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)',
    
    # 相対的な日付（例：'明後日'）
    r'(?P<relative_day>一昨日|昨日|今日|明日|明後日)',
    
    # 相対的な週と曜日（例：'再来週の金曜日'）
    r'(?P<relative_week>先々週|先週|今週|来週|再来週|次)の?(?P<weekday>月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)?',
    
    # 相対的な月と日（例：'来月の15日'）
    r'(?P<relative_month>先月|今月|来月|再来月)の?(?P<relative_day_number>\d{1,2})日?',
    
    # 絶対的な月と日（例：'12月25日'）
    r'(?P<absolute_month>\d{1,2})月の?(?P<absolute_day>\d{1,2})日?',
    
    # 曜日のみ（例：'金曜日'）
    r'(?P<weekday_only>月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)',
]

time_patterns = [
    r'(?P<time_of_day>朝|午前|昼|午後|夕方|夜|深夜|正午)?の?(?P<hour>\d{1,2})時(?P<minute>\d{1,2})?分?',
]

# 人数を表す文字列から数値を取得するための正規表現
# e.g. '2人' -> 2, '1名' -> 1, 
n_person_pattern = r'(?P<n_person>\d{1,2})(人|名)'


# 正規表現のコンパイル
date_regex = re.compile('|'.join(date_patterns))
time_regex = re.compile('|'.join(time_patterns))
n_person_regex = re.compile(n_person_pattern)