from src.modules.dialogue.utils import constants


state_templte = {
    "名前": "",
    "日付": "",
    "店舗": "",
    "人数": ""
}

templates = {
    constants.INITIAL_UTTERANCE: "お電話ありがとうございます。SHIFT渋谷店でございます。お電話のご用件をお話しください。",
    constants.FALLBACK: "すみません、よく聞き取れなかったのでもう一度お願いします。",
    constants.FILLER: "FILLER",
    "action_type": {
        "新規予約": {
            constants.SCENE_INITIAL: "ご予約ですね。",
            constants.BACK_SCENE: "新規ご予約のヒアリングに戻ります。",
            constants.COMPLETED: "予約が完了しました。当日はお気を付けてお越しください。",
            "slot": {
                "日付": ("ご希望の日付をお伺いしてもよろしいでしょうか？", "DATE_1"),
                "時間": ("ご希望の時間をお伺いしてもよろしいでしょうか？", "TIME_1"),
                "人数": ("ご来店人数をお伺いしてもよろしいでしょうか？", "N_PERSON_1"),
                "名前": ("ご来店される代表者のお名前をお伺いしてもよろしいでしょうか？", "NAME_1"),
            },
            "inheriting_slot": ["名前"],
            "unrequited_slot": [],
            "function": {
                "name": "new_reservation",
                "response": {
                    "COMPLETE": "渋谷店にて{日付}に{時間}に{人数}名で{名前}さまのご予約を承りました。",
                    "HOLIDAY": "申し訳ございません、水曜日は定休日のため、ご予約を承ることができません。",
                    "FAILED": "申し訳ございません、{日付}は満席のため、ご予約を承ることができません。",
                },
                "implicit_confirmation": {
                    frozenset(["日付", "時間", "人数"]): "{日付}の{時間}に{人数}名ですね。",
                    frozenset(["日付", "時間"]): "{日付}の{時間}ですね。",
                    frozenset(["日付", "人数"]): "{日付}に{人数}名ですね。",
                    frozenset(["時間", "人数"]): "{時間}に{人数}名ですね。",
                    "名前": "{名前}様ですね。",
                    "日付": "{日付}ですね。",
                    "時間": "{時間}ですね。",
                    "人数": "{人数}名ですね。"
                },
                "confirm": {
                    "はい": "予約が完了しました。当日はお気を付けてお越しください。",
                    "いいえ": "新規予約をキャンセルしました。",
                },
                "confirm_response": ["COMPLETE"],
            },
        },
        "予約内容の確認": {
            constants.SCENE_INITIAL: "ご予約の詳細をご確認させていただきます。",
            constants.BACK_SCENE: "ご予約の詳細の確認に戻ります。",
            constants.COMPLETED: "ご予約されている内容は以上です。",
            "slot": {
                "名前": "ご予約された際の代表者のお名前をお伺いしてもよろしいでしょうか？",
                "日付": "",
                "店舗": "",
                "人数": "",
            },
            "inheriting_slot": ["名前"],
            "unrequited_slot": ["日付", "人数", "店舗"],
            "function": {
                "name": "confirm_reservation",
                "response": {
                    "FIND": "{店舗}にて{日付}に{人数}でのご予約が確認されました。",
                    "NOT_FOUND": "{名前}様の予約情報は見つかりませんでした。",
                },
                "confirm": {},
                "confirm_response": [],
            },
        },
        "予約のキャンセル": {
            constants.SCENE_INITIAL: "ご予約のキャンセルですね。",
            constants.BACK_SCENE: "ご予約のキャンセルの確認に戻ります。",
            constants.COMPLETED: "ご予約のキャンセルが完了しました。またのご利用をお待ちしております。",
            "slot": {
                "名前": "ご予約された際の代表者のお名前をお伺いしてもよろしいでしょうか？",
                "日付": "",
                "店舗": "",
                "人数": "",
            },
            "inheriting_slot": ["名前"],
            "unrequited_slot": ["日付", "人数", "店舗"],
            "function": {
                "name": "cancel_reservation",
                "response": {
                    "COMPLETE": "{店舗}にて{日付}に{人数}名様のご予約が確認されました。キャンセルしても良いでしょうか？",
                    "NOT_FOUND": "ご予約されている内容が見つかりませんでした。",
                },
                "confirm": {
                    "はい": "ご予約のキャンセルが完了しました。またのご利用をお待ちしております。",
                    "いいえ": "キャンセル作業を中断しました。",
                },
                "confirm_response": ["COMPLETE"],
            },
        },
        "店舗についての質問": {
            constants.SCENE_INITIAL: "店舗についてのご質問ですね。",
            constants.BACK_SCENE: "",
            constants.COMPLETED: "",
            "slot": {
                "名前": "",
                "日付": "",
                "店舗": "",
                "人数": "",
            },
            "inheriting_slot": [],
            "unrequited_slot": ["名前", "日付", "人数", "店舗"],
            "function": {
                "name": "ask_about_store",
                "response": {
                    "COMPLETE": "{" + constants.USE_AS_IS + "}",
                },
                "confirm": {},
                "confirm_response": [],
            },
        },
    },
}