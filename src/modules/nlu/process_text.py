import re
import datetime
from typing import Dict, List, Tuple

date_patterns = [
    r"(?P<relative_month_ext>先月|今月|来月|再来月)の?(?P<week_number>\d{1})(週目)の?(?P<extended_weekday>月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)",
    r"(?P<relative_day>一昨日|昨日|今日|明日|明後日)",
    r"(?P<relative_week>先々週|先週|今週|来週|再来週|次)の?(?P<weekday>月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)?",
    r"(?P<relative_month>先月|今月|来月|再来月)の?(?P<relative_day_number>\d{1,2})日?",
    r"(?P<absolute_month>(?:\d{1,2}|[一二三四五六七八九十]+))月の?(?P<absolute_day>(?:\d{1,2}|[一二三四五六七八九十]+))日?",
    r"(?P<weekday_only>月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)",
]

era_date_patterns = [
    r"(?P<era>昭和|平成|令和)(?P<era_year>元|\d{1,2})年(?:の)?(?P<era_month>\d{1,2})月(?:の)?(?P<era_day>\d{1,2})日",
    r"(?P<western_year>\d{4})年(?:の)?(?P<western_month>\d{1,2})月(?:の)?(?P<western_day>\d{1,2})日",
]

time_patterns = [
    r"(?P<time_of_day1>朝|午前|昼|午後|夕方|夜|深夜|正午)(?P<hour1>(?:\d{1,2}|[一二三四五六七八九十]+))時半",
    r"(?P<time_of_day2>朝|午前|昼|午後|夕方|夜|深夜|正午)の(?P<hour2>(?:\d{1,2}|[一二三四五六七八九十]+))時半",
    r"(?P<hour3>(?:\d{1,2}|[一二三四五六七八九十]+))時半",
    r"(?P<time_of_day3>朝|午前|昼|午後|夕方|夜|深夜|正午)(?P<hour4>(?:\d{1,2}|[一二三四五六七八九十]+))時(?:(?P<minute1>\d{1,2}|[一二三四五六七八九十]+)分)?",
    r"(?P<time_of_day4>朝|午前|昼|午後|夕方|夜|深夜|正午)の(?P<hour5>(?:\d{1,2}|[一二三四五六七八九十]+))時(?:(?P<minute2>\d{1,2}|[一二三四五六七八九十]+)分)?",
    r"(?P<hour6>(?:\d{1,2}|[一二三四五六七八九十]+))時(?:(?P<minute3>\d{1,2}|[一二三四五六七八九十]+)分)?",
    r"(?P<special_time>正午|深夜零時|深夜12時|零時|〇時)",
]

person_count_pattern = r"([一二三四五六七八九十壱弐参]+)(人|名)"

special_person_count_map = {
    "ひとり": 1, "ふたり": 2, "一人": 1, "二人": 2,
    "独り": 1, "二名": 2, "一名": 1,
}

# pythonのdatetimeモジュールの曜日のインデックスと合わせる
day_of_week_map = {
    "月曜日": 0, "火曜日": 1, "水曜日": 2, "木曜日": 3, "金曜日": 4, "土曜日": 5, "日曜日": 6,
    "月曜": 0, "火曜": 1, "水曜": 2, "木曜": 3, "金曜": 4, "土曜": 5, "日曜": 6,
}

relative_time_dict = {
    "今日": 0,
    "明日": 1,
    "明後日": 2,
    "来週": 7,
    "再来週": 14,
}

kanji_number_map = {
    "〇": 0, "零": 0,
    "一": 1, "壱": 1,
    "二": 2, "弐": 2,
    "三": 3, "参": 3,
    "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9,
    "十": 10, "十一": 11, "十二": 12,
    "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18,
    "十九": 19, "二十": 20, "二十一": 21,
    "二十二": 22, "二十三": 23, "二十四": 24,
    "二十五": 25, "二十六": 26, "二十七": 27,
    "二十八": 28, "二十九": 29, "三十": 30,
    "三十一": 31,
}

era_to_western_year = {
    "昭和": {"start": 1926, "end": 1989},
    "平成": {"start": 1989, "end": 2019},
    "令和": {"start": 2019, "end": 9999},
}

sorted_kanji_numbers = sorted(kanji_number_map.keys(), key=len, reverse=True)

def get_kanji_number_pattern():
    escaped_numbers = [re.escape(kanji) for kanji in sorted_kanji_numbers]
    return "|".join(escaped_numbers)

kanji_number_pattern = get_kanji_number_pattern()

# 全パターンの結合
all_date_patterns = date_patterns + [
    rf"(?P<kanji_month>{kanji_number_pattern})月の?(?P<kanji_day>{kanji_number_pattern})日?"
] + era_date_patterns

all_time_patterns = time_patterns + [
    rf"(?P<kanji_time_of_day>朝|午前|昼|午後|夕方|夜|深夜)?(?P<kanji_hour>{kanji_number_pattern})時(?:(?P<kanji_minute>{kanji_number_pattern})分)?"
]

# コンパイル済み正規表現
date_regex = re.compile("|".join(all_date_patterns))
time_regex = re.compile("|".join(all_time_patterns))
person_count_regex = re.compile(person_count_pattern)

def get_current_time():
    return datetime.datetime.now()

def process_date(text: str) -> Dict[str, str]:
    results = {}
    matches = date_regex.finditer(text)

    for match in matches:
        now = get_current_time()
        print(now.date())
        target_date = None
        match_dict = match.groupdict()
        original = match.group(0)

        if relative_day := match_dict.get("relative_day"):
            if (offset := relative_time_dict.get(relative_day)) is not None:
                target_date = now + datetime.timedelta(days=offset)

        if relative_month := match_dict.get("relative_month"):
            month_offset = {
                "今月": 0,
                "来月": 1,
                "再来月": 2,
                "先月": -1,
                "先々月":-2,
            }.get(relative_month, 0)

            if day_number := match_dict.get("relative_day_number"):
                try:
                    day = int(day_number)
                    target_date = now + datetime.timedelta(days=month_offset*30)
                    target_date = target_date.replace(day=day)
                    if target_date < now:
                        target_date = None
                except ValueError:
                    pass
                    
        if relative_month_ext := match_dict.get("relative_month_ext"):
            if week_number := match_dict.get("week_number"):
                if extended_weekday := match_dict.get("extended_weekday"):
                    month_offset = {
                        "今月": 0,
                        "来月": 1,
                        "再来月": 2,
                        "先月": -1,
                    }.get(relative_month_ext, 0)

                    # 現在の日付から指定された月の1日を取得
                    first_day = now.replace(day=1) + datetime.timedelta(days=month_offset*30)
                    
                    # 指定された曜日の日付を計算
                    target_weekday = day_of_week_map[extended_weekday]
                    current_weekday = first_day.weekday()
                    
                    # 第1週目の指定曜日までの日数を計算
                    days_until_first = (target_weekday - current_weekday + 7) % 7
                    
                    # 週番号に基づいて日付を計算
                    week_number_int = int(week_number)
                    days_to_add = days_until_first + (week_number_int - 1) * 7
                    
                    target_date = first_day + datetime.timedelta(days=days_to_add)

        if relative_week := match_dict.get("relative_week"):
            if weekday := match_dict.get("weekday"):
                target_weekday = day_of_week_map[weekday]
                current_weekday = now.weekday()
                days_to_add = 0
                print("relative_week", current_weekday, target_weekday)

                if relative_week == "来週":
                    days_to_add = 7 - (current_weekday - target_weekday) if target_weekday > current_weekday else 7 + (target_weekday - current_weekday)
                elif relative_week == "再来週":
                    days_to_add = 14 - (current_weekday - target_weekday) if target_weekday > current_weekday else 14 + (target_weekday - current_weekday)
                elif relative_week == "先週":
                    days_to_add = (current_weekday - target_weekday - 7) % 7
                elif relative_week == "先々週":
                    days_to_add = (current_weekday - target_weekday - 14) % 7
                else:  # "今週"
                    days_to_add = (target_weekday - current_weekday + 7) % 7
                print("relative_week", days_to_add)
                target_date = now + datetime.timedelta(days=days_to_add)
                if target_date < now:
                    target_date = None

        if weekday := match_dict.get("weekday_only"):
            target_weekday = day_of_week_map[weekday]
            current_weekday = now.weekday()
            days_to_add = (target_weekday - current_weekday + 7) % 7
            target_date = now + datetime.timedelta(days=days_to_add)
            if target_date < now:
                target_date = None
                
        if absolute_month := match_dict.get("absolute_month"):
            if absolute_day := match_dict.get("absolute_day"):
                try:
                    # 漢数字または数字を整数に変換
                    month = (int(absolute_month) if absolute_month.isdigit() 
                            else kanji_number_map.get(absolute_month))
                    day = (int(absolute_day) if absolute_day.isdigit() 
                          else kanji_number_map.get(absolute_day))
                    
                    if month and day:
                        # まず現在の年で試みる
                        try:
                            target_date = now.replace(month=month, day=day)
                            # 日付が過去の場合、来年の日付として設定
                            if target_date < now:
                                target_date = target_date.replace(year=now.year + 1)
                        except ValueError:
                            # 無効な日付の場合（例：2月31日）はスキップ
                            pass
                except (ValueError, TypeError):
                    pass

        # kanji_month と kanji_day の処理も追加
        if kanji_month := match_dict.get("kanji_month"):
            if kanji_day := match_dict.get("kanji_day"):
                try:
                    month = kanji_number_map.get(kanji_month)
                    day = kanji_number_map.get(kanji_day)
                    
                    if month and day:
                        try:
                            target_date = now.replace(month=month, day=day)
                            if target_date < now:
                                target_date = target_date.replace(year=now.year + 1)
                        except ValueError:
                            pass
                except (ValueError, TypeError):
                    pass

        if era := match_dict.get("era"):
            era_year_str = match_dict.get("era_year")
            era_month_str = match_dict.get("era_month")
            era_day_str = match_dict.get("era_day")

            era_year = 1 if era_year_str == "元" else int(era_year_str)
            try:
                western_year = convert_era_to_western(era, era_year)
                if western_year is not None:
                    month = int(era_month_str)
                    day = int(era_day_str)
                    target_date = datetime.date(western_year, month, day)
            except (ValueError, TypeError):
                pass

        if target_date:
            if isinstance(target_date, datetime.datetime):
                target_date = target_date.date()
            results[original] = target_date.strftime("%y/%m/%d")

    return results

def process_time(text: str) -> Dict[str, str]:
    results = {}
    matches = time_regex.finditer(text)

    for match in matches:
        match_dict = match.groupdict()
        original = match.group(0)

        hour = ""
        minute = ""
        time_of_day = ""

        # time_of_dayの検出
        for i in range(1, 5):
            key = f"time_of_day{i}"
            if td := match_dict.get(key):
                time_of_day = td
                break

        # hourの検出
        for i in range(1, 7):
            key = f"hour{i}"
            if h := match_dict.get(key):
                hour = h
                break

        # minuteの検出
        for i in range(1, 4):
            key = f"minute{i}"
            if m := match_dict.get(key):
                minute = m
                break

        normalized_time = ""

        if special_time := match_dict.get("special_time"):
            normalized_time = {
                "正午": "12:00",
                "深夜零時": "00:00",
                "深夜12時": "00:00",
                "零時": "00:00",
                "〇時": "00:00",
            }.get(special_time)
        elif hour:
            h = int(hour) if hour.isdigit() else kanji_to_number(hour)
            m = 0
            if minute:
                m = int(minute) if minute.isdigit() else kanji_to_number(minute)
            elif "半" in original:
                m = 30

            h = infer_actual_hour(h, time_of_day)
            normalized_time = f"{h:02}:{m:02}"

        if normalized_time:
            results[original] = normalized_time

    return results

def process_person_count(text: str) -> Dict[str, str]:
    results = {}
    matches = person_count_regex.finditer(text)

    for match in matches:
        original = match.group(0)
        try:
            kanji_number = match.group(1)
            if num := kanji_to_number(kanji_number):
                replacement = f"{num}人"
                results[original] = replacement
        except (ValueError, TypeError, IndexError):
            pass

    for expr, num in special_person_count_map.items():
        if expr in text and expr not in results:
            results[expr] = f"{num}人"

    return results

def convert_era_to_western(era: str, year: int) -> int | None:
    year_range = era_to_western_year.get(era)
    if year_range:
        if year == 1:
            return year_range["start"]
        western_year = year_range["start"] + year - 1
        if year_range["start"] <= western_year <= year_range["end"]:
            return western_year
    return None

def kanji_to_number(text: str) -> int:
    for kanji in sorted_kanji_numbers:
        if kanji in text:
            return kanji_number_map[kanji]
    return 0

def infer_actual_hour(hour: int, time_of_day: str) -> int:
    if time_of_day in ("午後", "夕方", "夜") and hour < 12:
        hour += 12
    elif time_of_day == "深夜":
        if hour == 12:
            hour = 0
    elif time_of_day in ("朝", "午前") and hour == 12:
        hour = 0
    return hour

if __name__ == "__main__":
    test_text_list = [
        # "来週の土曜日の10時からお願いします。",
        # "再来月の15日に予定があります。",
        # "今日は何曜日ですか？",
        # "明日の午前中にお願いします。",
        "11月29日に予約したい",
        "11月の29に予約したい",
        "来月の1週目の水曜日はあいてますか？",
        "来週の土曜日はどうですか？",
        # "次の月曜日は空いてます？",
        # "再来月3週目の金曜日でお願いします。",
        # "再来週の水曜日でお願いします。",
        # "来週の水曜日はどうですか？",
        # "今週の水曜日に会議があります。",
        # "再来週の火曜日に予定を入れてください。",
        # "再来週の木曜日に打ち合わせがあります。",
        # "午後3時に会いましょう。",
        # "午前11時の予約です。",
        # "今日は夜8時に行きます。",
        # "明日の正午に会おう。",
        # "正午の予定です。",
        # "深夜1時に起きました。",
        # "夕方6時に食事です。",
        # "朝10時30分に会議があります。",
        # "今日の夜10時16分から会議があります。",
        # "午後2時15分にランチを食べよう。",
        # "10時半にお会いしましょう。",
        # "3時45分に出発しましょう。",
        # "再来週の日曜日に3名での会議があります。",
        # "1月15日に3人で会食をしましょう。",
        # "来週会議をします。",
        # "再来週に出張があります。",
    ]
    
    for text in test_text_list:
        formatted_dates = process_date(text)
        formatted_times = process_time(text)
        formatted_n_person = process_person_count(text)
        print(f"text: {text}")
        print(f"formatted_dates: {formatted_dates}")
        print(f"formatted_times: {formatted_times}")
        print(f"formatted_n_person: {formatted_n_person}")
        for expression, date in formatted_dates.items():
            print(f"『{expression}』は {date} です。")
        for expression, time in formatted_times.items():
            print(f"『{expression}』は {time} に変換されました。")