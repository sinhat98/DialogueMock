from src.modules.dialogue.utils.constants import DialogueState, Intent, RoutingResult, Slot, TTSLabel

conversation_flow = {
    "initial_message": "お電話ありがとうございます。SHIFT渋谷店でございます。ご予約のお電話でしょうか？",
    "scene_intents": {
        DialogueState.START: {
            Intent.NEW_RESERVATION: [
                "そうです",
                "はいお願いします",
                "予約したい",
                "予約をお願いします",
                "新しく予約を取りたい",
                "テーブルを予約したい"
            ],
            Intent.CONFIRM_RESERVATION: [
                "予約を確認したい",
                "予約の内容を教えてください",
                "予約の詳細を知りたい",
                "予約状況を確認したい"
            ],
            Intent.CANCEL_RESERVATION: [
                "予約をキャンセルしたい",
                "予約を取り消したい",
                "予約を取り消し",
                "キャンセルをお願いします"
            ],
            Intent.ASK_ABOUT_STORE: [
                "店舗の場所を教えてください",
                "営業時間は何時までですか",
                "定休日を教えてください",
                "駐車場はありますか"
            ]
        },
        DialogueState.WAITING_CONFIRMATION: {
            Intent.NEW_RESERVATION: {
                Intent.CONFIRM: [
                    "はい",
                    "お願いします",
                    "確定でお願いします",
                    "その内容で大丈夫です",
                    "確定します"
                ],
                Intent.CHANGE: [
                    "変更をお願いします",
                    "修正をお願いします",
                    "訂正したいです",
                    "内容を変えたいです",
                    "違います"
                ],
                Intent.CANCEL: [
                    "予約をキャンセルします",
                    "やっぱりやめます",
                    "予約を取り消します",
                    "キャンセルでお願いします"
                ]
            },
            Intent.CONFIRM_RESERVATION: {
                Intent.CONFIRM: [
                    "はい",
                    "お願いします",
                    "確定でお願いします",
                    "その内容で大丈夫です",
                    "確定します"
                ],
                # Intent.CHANGE: [
                #     "変更をお願いします",
                #     "修正をお願いします",
                #     "訂正したいです",
                #     "内容を変えたいです",
                #     "違います"
                # ],
                Intent.CANCEL: [
                    "予約をキャンセルします",
                    "やっぱりやめます",
                    "予約を取り消します",
                    "キャンセルでお願いします"
                ]
            },
            Intent.CANCEL_RESERVATION: {
                Intent.YES: [
                    "はい",
                    "お願いします",
                    "確定でお願いします",
                    "その内容で大丈夫です",
                    "確定します"
                ],
                Intent.NO: [
                    "キャンセルしないです",
                    "やっぱりやめます",
                ],
            },
            
        },
    }
}
tts_label2text = {
    TTSLabel.SELECT: "ご用件をお話しください。",
    TTSLabel.INITIAL: "お電話ありがとうございます。SHIFT渋谷店でございます。",
    TTSLabel.FILLER: "確認いたします",
    TTSLabel.APOLOGIZE: "申し訳ございません、うまく聞き取れませんでした",
    TTSLabel.DATE_1: "ご希望の日付をお伺いしてもよろしいでしょうか？",
    TTSLabel.TIME_1: "ご希望の時間をお伺いしてもよろしいでしょうか？",
    TTSLabel.N_PERSON_1: "ご来店人数をお伺いしてもよろしいでしょうか？",
    TTSLabel.NAME_1: "ご来店される代表者のお名前をお伺いしてもよろしいでしょうか？",
}

tts_text2label = {t: l for l, t in tts_label2text.items()}

templates = {
    "initial_state": {
        Slot.NAME: "",
        Slot.DATE: "",
        Slot.TIME: "",
        Slot.N_PERSON: "",
    },
    "scenes": {
        Intent.NEW_RESERVATION: {
            "required_slots": [Slot.DATE, Slot.TIME, Slot.N_PERSON, Slot.NAME],
            "optional_slots": [],
            "prompts": {
                Slot.DATE: ("ご希望の日付をお伺いしてもよろしいでしょうか？", TTSLabel.DATE_1),
                Slot.TIME: ("ご希望の時間をお伺いしてもよろしいでしょうか？", TTSLabel.TIME_1),
                Slot.N_PERSON: ("ご来店人数をお伺いしてもよろしいでしょうか？", TTSLabel.N_PERSON_1),
                Slot.NAME: ("ご来店される代表者のお名前をお伺いしてもよろしいでしょうか？", TTSLabel.NAME_1),
            },
            "responses": {
                DialogueState.COMPLETE: "承知いたしました。{日付}の{時間}に{人数}名様で{名前}様のご予約を承りました。",
            },
            "implicit_confirmation": {
                frozenset([Slot.DATE, Slot.TIME, Slot.N_PERSON]): "{日付}の{時間}に{人数}名様ですね。",
                frozenset([Slot.DATE, Slot.TIME]): "{日付}の{時間}ですね。",
                frozenset([Slot.DATE, Slot.N_PERSON]): "{日付}に{人数}名様ですね。",
                frozenset([Slot.TIME, Slot.N_PERSON]): "{時間}に{人数}名様ですね。",
                Slot.NAME: "{名前}様ですね。",
                Slot.DATE: "{日付}ですね。",
                Slot.TIME: "{時間}ですね。",
                Slot.N_PERSON: "{人数}名様ですね。",
            },
            "final_confirmation": {
                "prompt": "{日付}の{時間}に{人数}名様でご予約をお取りしてもよろしいでしょうか？",
                "responses": {
                    RoutingResult.CANCEL: "新規のご予約をキャンセルいたします。またのご利用をお待ちしております。",
                    RoutingResult.CHANGE: "日付、時間、人数、名前、どの項目を変更しますか？",
                },
            },
            "correction": {
                Slot.DATE: ("ご希望の日付を改めてお伺いいたします。", "DATE_2"),
                Slot.TIME: ("ご希望の時間を改めてお伺いいたします。", "TIME_2"),
                Slot.N_PERSON: ("ご来店人数を改めてお伺いいたします。", "N_PERSON_2"),
                Slot.NAME: ("代表者のお名前を改めてお伺いいたします。", "NAME_2"),
            },
        },

        Intent.CONFIRM_RESERVATION: {
            "required_slots": [Slot.NAME],
            "optional_slots": [Slot.DATE, Slot.TIME, Slot.N_PERSON],
            "prompts": {
                Slot.NAME: ("ご予約者のお名前をお伺いできますでしょうか？", "CONFIRM_NAME_1"),
                Slot.DATE: ("ご予約の日付は分かりますでしょうか？", "CONFIRM_DATE_1"),
            },
            "responses": {
                DialogueState.COMPLETE: "{名前}様の{日付}のご予約を確認いたしました。",
                "NOT_FOUND": "申し訳ございません。{名前}様のご予約は見つかりませんでした。",
            },
            "implicit_confirmation": {
                Slot.NAME: "{名前}様のご予約ですね。",
                Slot.DATE: "{日付}のご予約ですね。",
            },
            "final_confirmation": {
                "prompt": "{日付}の{時間}に{人数}名様で{名前}様のご予約を承っております。こちらの内容で間違いありませんでしょうか？",
                "responses": {
                    RoutingResult.CONFIRM: "ご予約内容を確認いたしました。当日のご来店を心よりお待ちしております。",
                    # RoutingResult.CHANGE: "ご希望の日付、時間、人数、をおっしゃってください。",
                    RoutingResult.CANCEL: "申し訳ございません。もう一度最初から予約内容の確認をさせていただきます。"
                }
            }
        },

        Intent.CANCEL_RESERVATION: {
            "required_slots": [Slot.NAME],
            "optional_slots": [Slot.DATE, Slot.TIME, Slot.N_PERSON],
            "prompts": {
                Slot.NAME: ("キャンセルされるご予約のお名前をお伺いできますでしょうか？", "CANCEL_NAME_1"),
            },
            "responses": {
                DialogueState.COMPLETE: "{名前}様のご予約をキャンセルいたしました。",
                "NOT_FOUND": "申し訳ございません。{名前}様のご予約は見つかりませんでした。",
                "FOUND": "{日付}の{時間}に{人数}名様で{名前}様のご予約を確認いたしました。",
            },
            "implicit_confirmation": {
                Slot.NAME: "{名前}様ですね。",
            },
            "final_confirmation": {
                "prompt": "{日付}の{時間}に{人数}名様で{名前}様のご予約をキャンセルしてもよろしいでしょうか？",
                "responses": {
                    RoutingResult.YES: "ご予約をキャンセルいたしました。またのご利用をお待ちしております。",
                    RoutingResult.NO: "キャンセルを取り消しました。"
                },
            },
        },

        Intent.ASK_ABOUT_STORE: {
            "required_slots": [],
            "optional_slots": [],
            "responses": {
                DialogueState.COMPLETE: "ご質問ありがとうございます。",
                "NOT_FOUND": "申し訳ございませんが、その件についてはお手伝いできる情報がありません。何か他にご質問はございますか？",
            },
            "final_confirmation": {
                "prompt": "他にご質問はございますか？",
                "responses": {
                    RoutingResult.CONFIRM: "ご質問ありがとうございます。",
                },
            },
        },
    },

    "common": {
        "fallback": {
            RoutingResult.INVALID_INTENT: "申し訳ございません。ご要件を理解できませんでした。",
            RoutingResult.NO_INTENT: "申し訳ございません。もう一度ご要件をお聞かせください。",
            "CONVERSATION_ERROR": "申し訳ございません。対応できない状況が発生しました。",
            "DEFAULT": "申し訳ございません。",
        },
        "scene_initial": {
            Intent.NEW_RESERVATION: "ご予約ですね。承知いたしました。",
            Intent.CONFIRM_RESERVATION: "ご予約の確認ですね。",
            Intent.CANCEL_RESERVATION: "ご予約のキャンセルですね。",
            Intent.ASK_ABOUT_STORE: "店舗についてのご質問ですね。",
        },
        "scene_complete": {
            Intent.NEW_RESERVATION: "ご予約ありがとうございました。当日のご来店をお待ちしております。",
            Intent.CONFIRM_RESERVATION: "ご予約内容のご確認は以上です。",
            Intent.CANCEL_RESERVATION: "ご予約のキャンセルが完了いたしました。またのご利用をお待ちしております。",
            Intent.ASK_ABOUT_STORE: "またのご利用をお待ちしております。",
        }
    }
}