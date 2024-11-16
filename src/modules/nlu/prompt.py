from datetime import datetime
import json
from src.modules.dialogue.utils.template import templates

action_type_list = list(templates.get("action_type").keys())

today = datetime.now().strftime("%Y/%m/%d")


# today = datetime(2024, 10, 23).strftime("%Y/%m/%d")
def get_base_system_prompt(slot: dict):
    # 箇条書きリストに変換
    acttion_type_list_str = "\n".join(
        [f"- {action_type}" for action_type in action_type_list]
    )
    slot_str = "\n".join([f"- {slot_key}" for slot_key in slot.keys()])
    base_prompt = f"""
与えられたユーザーの要求から埋めるべきslotを**JSON**形式で抽出してください
日付はmm/dd形式で出力してください。今日は{today}です。
ただし、用件には以下のいずれかの値を埋めてください。
{acttion_type_list_str}

### slot
{slot_str}

### output_format
{json.dumps(slot, ensure_ascii=False)}
"""
    return base_prompt

# intentsは意図とフレーズのマッピング
def get_system_prompt_for_intent_classification(intents: dict):
    prompt = ""
    hedder_text = "以下のフレーズに対応する意図を選択してください。"
    phrases_str = ""
    for intent, phrases in intents.items():
        phrases_str += f"\n- {intent}: {', '.join(phrases)}"
    phrases_str += "\n"
    tail_text = "回答は必ず" + ", ".join(intents.keys()) + "のいずれかにしてください。"
    prompt = f"{hedder_text}{phrases_str}{tail_text}"
    return prompt
    

# system_prompt_for_action_type = """
# 与えられたユーザーの要求から埋めるべきslotを**JSON**形式で抽出してください
# 日付はmm/dd形式で出力してください。今日は{today}です。
# ただし、用件には以下のいずれかの値を埋めてください。
# - 新規予約
# - 予約変更
# - 予約キャンセル
# - その他

# ### slot
# {slot}
# - 用件

# ### output_format

# """

system_prompt_for_slot_filling = """
与えられたユーザーの要求から埋めるべきslotを**JSON**形式で抽出してください
日付はmm/dd形式で出力してください。今日は{today}です。
予約変更の場合は変更するスロットも埋めて予約変更のスロットをtrueで埋めてください。

### slot

- 名前
- 日付
- 人数
- 時間

### output_format
{{"名前": "", "日付": "", "人数": "", "時間": ""}}
"""
system_prompt_for_slot_filling = system_prompt_for_slot_filling.format(today=today)

# 圧縮された新しいプロンプト
system_prompt_for_faq = """
あなたは飲食店の店員です。
ユーザーからのメッセージに対して、以下のFAQリストを参照し、該当する質問に関連していれば、その質問に対応する回答を返してください。
もし、関連する質問がない場合は、空文字を返してください。

# FAQリスト:
## 基本的な質問
### 営業関連
質問: 営業時間について知りたい
回答: 土日祝日ともに11:00から23:00まで営業しております。

質問: 駐車場の利用について知りたい
回答: 駐車場はございませんが、近隣にコインパーキングがございます。

### 予約・席arrangements
質問: 同一グループでの異なるコース注文について
回答: 同一グループの方は、お席を分けても皆様同じコースをご注文いただきます。

質問: 個室や特別な席の利用について
回答: 個室はございません。車いす・ベビーカー対応の席は一部店舗でご用意しております。ご利用の際は事前予約をお勧めいたします。

### 飲み放題関連
質問: グループでの飲み放題の注文について
回答: アルコールとソフトドリンクを組み合わせたご注文は可能です。ただし、グループの皆様がいずれかの飲み放題をご注文いただく必要があります。幼児様は、グループの皆様が飲み放題をご注文の場合、ソフトドリンク飲み放題を無料でご利用いただけます。

### 料金・支払い関連
質問: 年齢確認や証明書について
回答: シニア料金、幼児・小学生料金ともに証明書は不要でございます。

質問: 各種支払い方法について
回答: ジェフグルメ券は全店でご使用可能です。その他のギフト券やキャッシュレス決済については、各店舗にお問い合わせください。また、全店がインボイス対象店舗となっております。

質問: 割引の併用について
回答: 株主優待券と割引券は併用可能です。シニア料金にも、特別な記載がない限り割引券をご利用いただけます。

### アレルギー情報
質問: アレルギー情報について
回答: 最新のアレルギー情報はホームページでご確認いただけます。記載のない項目については、2週間程度の調査期間が必要となります。
"""


# もしユーザーの質問に該当するものがFAQリストにない場合は、'NOT_FOUND'を返してください。
# ただし、ユーザーの要求には音声認識誤りが含まれる可能性がある場合があります。音声認識誤りがあると思われる場合は、'APOLOGIZE'を返してください。

if __name__ == "__main__":
    intetns_dict = {
        "予約": ["予約したい", "予約を取りたい"],
        "キャンセル": ["予約をキャンセルしたい", "予約を取り消したい"],
        "変更": ["予約を変更したい", "予約を変更する"]
    }
    print(get_system_prompt_for_intent_classification(intetns_dict))