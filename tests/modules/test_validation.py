from src.modules.nlu.validation import validate_date, validate_number_of_people, validate_time

def test_validate_time():
    # 正常な時間表現のテスト
    assert validate_time("00:00")
    assert validate_time("12:34")
    assert validate_time("23:59")

    # 異常な時間表現のテスト
    assert not validate_time("24:00")  # 時間は23まで
    assert not validate_time("12:60")  # 分は59まで
    assert not validate_time("99:99")  # 範囲外の値
    assert not validate_time("ab:cd")  # 数字でない
    assert not validate_time("12-34")  # 区切り文字が違う
    assert not validate_time("")       # 空文字

def test_validate_date():
    # 正常な日付表現のテスト
    assert validate_date("01/01")
    assert validate_date("02/28")
    assert validate_date("12/31")

    # 異常な日付表現のテスト
    assert not validate_date("00/01")  # 月は1から12
    assert not validate_date("13/01")  # 月は12まで
    assert not validate_date("02/30")  # 2月は最大29日まで（うるう年を考慮しない場合28日まで）
    assert not validate_date("04/31")  # 4月は30日まで
    assert not validate_date("ab/cd")  # 数字でない
    assert not validate_date("02-28")  # 区切り文字が違う
    assert not validate_date("")       # 空文字

def test_validate_number_of_people():
    # 正常な人数表現のテスト
    assert validate_number_of_people("0")  # ゼロを許可する場合
    assert validate_number_of_people("1")
    assert validate_number_of_people("1234567890")

    # 異常な人数表現のテスト
    assert not validate_number_of_people("-1")    # マイナスは不可
    assert not validate_number_of_people("1.5")   # 小数は不可
    assert not validate_number_of_people("abc")   # 数字でない
    assert not validate_number_of_people("1,000") # カンマ付きは不可
    assert not validate_number_of_people(" ")     # 空白文字
    assert not validate_number_of_people("")      # 空文字

if __name__ == '__main__':
    import pytest
    pytest.main()