import re
from datetime import datetime, timedelta
from src.modules.nlu.regular_expression import date_regex, time_regex, n_person_regex
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

# 基準日を現在の日付に設定
# today = datetime.today()
today = datetime(2024, 10, 23)

# 相対的な時間表現の辞書
relative_time_dict = {
    '今日': 0,
    '明日': 1,
    '明後日': 2,
    '来週': 7,
    '再来週': 14,
    '来月': 'next_month',
}

# 曜日のマッピング
day_of_week_map = {
    '月曜日': 0,
    '火曜日': 1,
    '水曜日': 2,
    '木曜日': 3,
    '金曜日': 4,
    '土曜日': 5,
    '日曜日': 6,
    '月曜': 0,
    '火曜': 1,
    '水曜': 2,
    '木曜': 3,
    '金曜': 4,
    '土曜': 5,
    '日曜': 6,
}

# 日時表現を解析して具体的な日に変換する関数
def process_date(text):
    results = {}
    match = date_regex.search(text)
    # for match in date_regex.search(text):
    if match:
        date_info = match.groupdict()
        logger.debug("date_info: %s", date_info)
        target_date = today

        # 絶対的な月と日（例: 10月の25日, 10月の25）
        if date_info.get('absolute_month_no_day') and date_info.get('absolute_day_no_month'):
            month = int(date_info['absolute_month_no_day'])
            day = int(date_info['absolute_day_no_month'])
            year = target_date.year
            # 日付が過去の場合、翌年とする
            if month < target_date.month or (month == target_date.month and day <= target_date.day):
                year += 1
            target_date = datetime(year, month, day)
        # 相対的な月と週と曜日（例: 来月の1週目の水曜日）
        elif date_info.get('relative_month_ext') and date_info.get('week_number') and date_info.get('extended_weekday'):
            relative_month_ext = date_info['relative_month_ext']
            week_number = int(date_info['week_number'])
            extended_weekday = date_info['extended_weekday']
            
            if relative_month_ext == '今月':
                months_offset = 0
            elif relative_month_ext == '来月':
                months_offset = 1
            elif relative_month_ext == '再来月':
                months_offset = 2
            else:
                months_offset = 0
            target_weekday = day_of_week_map[extended_weekday]
            
            # 月を調整
            month = (target_date.month + months_offset - 1) % 12 + 1
            year = target_date.year + ((target_date.month + months_offset - 1) // 12)
            
            # 指定された月の最初の日を取得
            first_day_of_month = datetime(year, month, 1)
            
            # 最初の指定された曜日を見つける
            if first_day_of_month.weekday() <= target_weekday:
                first_target_weekday = first_day_of_month + timedelta(days=(target_weekday - first_day_of_month.weekday()))
            else:
                first_target_weekday = first_day_of_month + timedelta(days=(7 - (first_day_of_month.weekday() - target_weekday)))
                
            # 週番号を考慮して日時を調整（1週目はそのまま、2週目なら+7日など）
            target_date = first_target_weekday + timedelta(weeks=(week_number - 1))

        # 相対的な日付（例: 今日、明日、一昨日など）
        elif date_info.get('relative_day'):
            days_offset = relative_time_dict[date_info['relative_day']]
            target_date += timedelta(days=days_offset)
        
        # 相対的な週と曜日
        elif date_info.get('relative_week'):
            relative_week = date_info['relative_week']
            weekday = date_info.get('weekday')
            if relative_week == '今週':
                pass  # 何もしない
            elif relative_week == '来週':
                target_date += timedelta(weeks=1)
            elif relative_week == '再来週':
                target_date += timedelta(weeks=2)

            if weekday:
                logger.debug("weekday: %s", weekday)
                target_weekday = day_of_week_map[weekday]
                diff_weak_day = target_weekday - target_date.weekday()
                logger.debug("diff_weak_day: %s", diff_weak_day)
                days_ahead = (diff_weak_day + 7) % 7
                if diff_weak_day < 0:
                    days_ahead = days_ahead - 7
                target_date += timedelta(days=days_ahead)
                # この部分を削除またはコメントアウト
                # if days_ahead == 0 and relative_week:
                #     target_date += timedelta(weeks=1)

                # 相対的な月と日（例: 来月の15日）
        elif date_info.get('relative_month') and date_info.get('relative_day_number'):
            relative_month = date_info['relative_month']
            months_offset = 0
            if relative_month == '今月':
                months_offset = 0
            elif relative_month == '来月':
                months_offset = 1
            elif relative_month == '再来月':
                months_offset = 2
            day = int(date_info['relative_day_number'])
            
            # 月を調整
            month = (target_date.month + months_offset - 1) % 12 + 1
            year = target_date.year + ((target_date.month + months_offset - 1) // 12)
            target_date = datetime(year, month, day)

        # 絶対的な月と日（例: 12月25日）
        elif date_info.get('absolute_month') and date_info.get('absolute_day'):
            month = int(date_info['absolute_month'])
            day = int(date_info['absolute_day'])
            year = target_date.year
            # 日付が過去の場合、翌年とする
            if month < target_date.month or (month == target_date.month and day <= target_date.day):
                year += 1
            target_date = datetime(year, month, day)
        
        # 曜日のみ（例: 月曜日）
        elif date_info.get('weekday_only'):
            target_weekday = day_of_week_map[date_info['weekday_only']]
            days_ahead = (target_weekday - target_date.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead += 7  # 次の週の同じ曜日
            target_date += timedelta(days=days_ahead)


        # 時刻の解析を無視
        finalized_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        results[match.group()] = finalized_date.strftime('%m/%d')

    return results

def process_time(text):
    results = {}
    for match in time_regex.finditer(text):
        time_info = match.groupdict()
        logger.debug("time_info: %s", time_info)

        # 時刻の部分が見つかった場合
        if time_info.get('hour') is not None:
            hour = int(time_info['hour'])
            # 分の部分が見つかった場合
            minute = int(time_info['minute']) if time_info.get('minute') else 0

            # 午前・午後の区別が必要
            if time_info.get('time_of_day') is not None:
                time_of_day = time_info['time_of_day']
                if time_of_day in ['午後', '夕方', '夜'] and hour < 12:
                    hour += 12
                elif time_of_day in ['午前', '朝'] and hour == 12:
                    hour = 0
            formatted_time = f'{hour:02}:{minute:02}'
            results[match.group()] = formatted_time

    return results

def process_n_person(text) -> int | None:
    """人数を表す文字列から数値を取得する
    Args:
        text (str): 人数を表す文字列 (e.g. '2人', '3名')
    Returns:
        int: 人数
    """
    match = re.search(n_person_regex, text)
    if match:
        n_person = int(match.group('n_person'))
        return n_person
    return None

if __name__ == "__main__":
    test_text_list = [
        "来週の土曜日の10時からお願いします。",
        "再来月の15日に予定があります。",
        "今日は何曜日ですか？",
        "明日の午前中にお願いします。",
        "来月の1週目の水曜日はあいてますか？",
        "次の月曜日は空いてます？",
        "再来月3週目の金曜日でお願いします。",
        "再来週の水曜日でお願いします。",
        "来週の水曜日はどうですか？",           # 来週の水曜日
        "今週の水曜日に会議があります。",       # 今週の水曜日
        "再来週の火曜日に予定を入れてください。", # 再来週の火曜日
        "再来週の木曜日に打ち合わせがあります。", # 再来週の木曜日
        "午後3時に会いましょう。",
        "午前11時の予約です。",
        "今日は夜8時に行きます。",
        "明日の正午に会おう。",
        "正午の予定です。",
        "深夜1時に起きました。",
        "夕方6時に食事です。",
        "朝10時30分に会議があります。",
        "今日の夜10時16分から会議があります。",
        "午後2時15分にランチを食べよう。",
        "10時半にお会いしましょう。",
        "3時45分に出発しましょう。"
        "再来週の日曜日に3名での会議があります。",
        "1月15日に3人で会食をしましょう。",
        "2月の25に5人で会議をしましょう。",
    ]
    for text in test_text_list:
        # 関数の実行
        formatted_dates = process_date(text)
        formatted_times = process_time(text)
        formatted_n_person = process_n_person(text)
        logger.info("text: %s", text)
        logger.info("formatted_dates: %s", formatted_dates)
        logger.info("formatted_times: %s", formatted_times)
        logger.info("formatted_n_person: %s", formatted_n_person)
        for expression, date in formatted_dates.items():
            print(f"『{expression}』は {date} です。")
        for expression, time in formatted_times.items():
            print(f"『{expression}』は {time} に変換されました。")