from src.modules.dialogue.utils.constants import DialogueState, Intent, RoutingResult, Slot, TTSLabel

import random
random.seed(0)

conversation_flow = {
    "initial_message": lambda: random.choice([TTSLabel.INITIAL_1, TTSLabel.INITIAL_2]),
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
            Intent.CHANGE_RESERVATION: [
                "予約を変更したい",
                "予約を修正したい",
                "予約を変更する",
                "予約を修正する"
            ],
            Intent.ASK_ABOUT_STORE: [
                "場所・アクセス",
                "店舗の所在地",
                "駐車場の有無",
                "営業時間",
                "定休日",
                "予約可能な人数（最大）",
                "メニューの種類",
                "価格帯・予算",
                "個室の有無",
                "禁煙・喫煙",
                "席数・テーブル形態"
            ],
            Intent.OTHER: [
                "他のIntentに分類されない発話"
            ]
        },
        DialogueState.WAITING_CONFIRMATION: {
            Intent.NEW_RESERVATION: {
                Intent.YES: [
                    "はい",
                    "お願いします",
                    "確定でお願いします",
                    "その内容で大丈夫です",
                    "確定します"
                ],
                Intent.CHANGE: [
                    "変更したい",
                    "修正したい",
                    "訂正したいです",
                    "内容を変えたいです",
                    "違います",
                    "〇〇時でお願いします",
                    "〇〇人でお願いします",
                    "〇〇日でお願いします",
                ],
                Intent.NO: [
                    "予約をキャンセルします",
                    "やっぱりやめます",
                    "予約を取り消します",
                    "キャンセルでお願いします"
                ],
                Intent.OTHER: [
                    "他のIntentに分類されない発話"
                ]
            },
            Intent.CONFIRM_RESERVATION: {
                Intent.YES: [
                    "はい",
                    "お願いします",
                    "確定でお願いします",
                    "その内容で大丈夫です",
                    "確定します"
                ],
                Intent.NO: [
                    "いいえ",
                    "間違っています",
                    "予約をキャンセルします",
                    "やっぱりやめます",
                    "予約を取り消します",
                    "キャンセルでお願いします"
                ],
                # Intent.NEW_RESERVATION: [
                #     "いいえ",
                #     "間違っています",
                #     "違います",
                # ],
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
            Intent.ASK_ABOUT_STORE: {
                Intent.YES: [
                    "はい",
                    "質問があります",
                ],
                Intent.NO: [
                    "いいえ",
                    "もう大丈夫です",
                ],
                Intent.NEW_RESERVATION: [
                    "予約をお願いします",
                    "予約したい"
                ],
                Intent.CONFIRM_RESERVATION: [
                    "予約の内容を教えてください",
                    "予約の詳細を知りたい"
                ],
                Intent.CHANGE_RESERVATION: [
                    "予約を変更したい",
                    "予約を修正したい",
                    "予約を変更する",
                    "予約を修正する"
                ],
                Intent.CANCEL_RESERVATION: [
                    "予約をキャンセルしたい",
                    "予約を取り消したい"
                ],
                Intent.ASK_ABOUT_STORE: [
                    "場所・アクセス",
                    "店舗の所在地",
                    "駐車場の有無",
                    "営業時間",
                    "定休日",
                    "予約可能な人数（最大）",
                    "メニューの種類",
                    "価格帯・予算",
                    "個室の有無",
                    "禁煙・喫煙",
                    "席数・テーブル形態"
                ],
                Intent.OTHER: [
                    "他のIntentに分類されない発話"
                ],
            }
        },
    }
}
tts_label2text = {
    # 基本的な応答
    TTSLabel.SELECT: "ご用件をお話しください。",
    TTSLabel.INITIAL_1: "お電話ありがとうございます。SHIFT渋谷店です。",
    TTSLabel.INITIAL_2: "お電話ありがとうございます。SHIFT渋谷店です。ごようけんをおっしゃってください", 
    TTSLabel.FILLER: "確認いたします",
    TTSLabel.APOLOGIZE: "申し訳ございません、うまく聞き取れませんでした",

    # 初期の質問
    TTSLabel.DATE_1: "ご希望の日付をお伺いしてもよろしいでしょうか？",
    TTSLabel.TIME_1: "ご希望の時間をお伺いしてもよろしいでしょうか？", 
    TTSLabel.N_PERSON_1: "ご来店人数をお伺いしてもよろしいでしょうか？",
    TTSLabel.NAME_1: "ご来店される代表者のお名前をお伺いしてもよろしいでしょうか？",
    
    # 修正時の質問
    TTSLabel.DATE_2: "ご希望の日付を改めてお伺いいたします。",
    TTSLabel.TIME_2: "ご希望の時間を改めてお伺いいたします。",
    TTSLabel.N_PERSON_2: "ご来店人数を改めてお伺いいたします。",
    TTSLabel.NAME_2: "代表者のお名前を改めてお伺いいたします。",

    # 新規予約関連
    TTSLabel.NEW_RESERVATION_INTRO: "ご予約ですね。承知いたしました。",
    TTSLabel.NEW_RESERVATION_COMPLETE: "ご予約ありがとうございました。当日のご来店をお待ちしております。",
    TTSLabel.NEW_RESERVATION_CANCEL: "新規のご予約をキャンセルいたします。またのご利用をお待ちしております。",
    TTSLabel.NEW_RESERVATION_CHANGE: "日付、時間、人数、名前、どの項目を変更しますか？",
    
    # 予約確認関連
    TTSLabel.CONFIRM_RESERVATION_INTRO: "ご予約の確認ですね。",
    TTSLabel.CONFIRM_RESERVATION_COMPLETE: "ご予約内容のご確認は以上です。",
    
    TTSLabel.CONFIRM_RESERVATION_NAME: "ご予約者のお名前をお伺いできますでしょうか？",
    TTSLabel.CONFIRM_RESERVATION_DATE: "ご予約の日付は分かりますでしょうか？",

    TTSLabel.CONFIRM_RESERVATION_CONFIRM: "ご予約内容を確認いたしました。当日のご来店を心よりお待ちしております。",
    TTSLabel.CONFIRM_RESERVATION_CANCEL: "申し訳ございません。もう一度最初から予約内容の確認をさせていただきます。",
    
    # 予約キャンセル関連
    TTSLabel.CANCEL_RESERVATION_INTRO: "ご予約のキャンセルですね。",
    TTSLabel.CANCEL_RESERVATION_COMPLETE: "ご予約のキャンセルが完了いたしました。またのご利用をお待ちしております。",
    TTSLabel.CANCEL_RESERVATION_CONFIRM: "ご予約をキャンセルいたしました。またのご利用をお待ちしております。",
    TTSLabel.CANCEL_RESERVATION_CANCEL: "かしこまりました。ご来店お待ちしております。",
    
    TTSLabel.CANCEL_RESERVATION_NAME: "ご予約いただいたお名前をお伺いできますでしょうか？",
    
    # 店舗案内関連
    TTSLabel.STORE_INFO_INTRO: "店舗についてのご質問ですね。",
    TTSLabel.STORE_INFO_COMPLETE: "またのご利用をお待ちしております。",
    TTSLabel.STORE_INFO_NOT_FOUND: "申し訳ございませんが、その件についてはお手伝いできる情報がありません。何か他にご質問はございますか？",
    
    # 共通のフォールバック応答
    TTSLabel.FALLBACK_INVALID_INTENT: "申し訳ございません。ご要件を理解できませんでした。",
    TTSLabel.FALLBACK_NO_INTENT: "申し訳ございません。もう一度ご要件をお聞かせください。",
    TTSLabel.FALLBACK_CONVERSATION_ERROR: "申し訳ございません。対応できない状況が発生しました。",
    TTSLabel.FALLBACK_DEFAULT: "申し訳ございません。もう一度お話しいただけますか？",
    
    # 確認関連の定型文
    TTSLabel.ASK_OTHER_QUESTIONS: "他にご用件はございますか？",
    TTSLabel.THANKS_FOR_QUESTION: "ご質問ありがとうございます。",
    
    # 予約変更関連（予約変更の場合は店舗へ転送するメッセージ）
    TTSLabel.CHANGE_RESERVATION_INTRO: "ご予約の変更は店舗スタッフが承ります。ただいま店舗へお繋ぎいたしますので、少々お待ちください。",
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
                Slot.DATE: TTSLabel.DATE_1,
                Slot.TIME: TTSLabel.TIME_1,
                Slot.N_PERSON: TTSLabel.N_PERSON_1,
                Slot.NAME: TTSLabel.NAME_1,
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
                    RoutingResult.CANCEL: TTSLabel.NEW_RESERVATION_CANCEL,
                    RoutingResult.CHANGE: TTSLabel.NEW_RESERVATION_CHANGE,
                },
            },
            "correction": {
                Slot.DATE: TTSLabel.DATE_2,
                Slot.TIME: TTSLabel.TIME_2,
                Slot.N_PERSON: TTSLabel.N_PERSON_2,
                Slot.NAME: TTSLabel.NAME_2,
            },
        },

        Intent.CONFIRM_RESERVATION: {
            "required_slots": [Slot.NAME],
            "optional_slots": [Slot.DATE, Slot.TIME, Slot.N_PERSON],
            "prompts": {
                Slot.NAME: TTSLabel.CONFIRM_RESERVATION_NAME,
                Slot.DATE: TTSLabel.CONFIRM_RESERVATION_DATE,
            },
            "responses": {
                DialogueState.COMPLETE: "{日付}の{時間}から{人数}名様でご予約いただいております。ご来店をお待ちしております。",
                "NOT_FOUND": "申し訳ございません。{名前}様のご予約は見つかりませんでした。",
            },
            "implicit_confirmation": {
                Slot.NAME: "{名前}様ですね。",
                Slot.DATE: "{日付}ですね。",
            },
            "final_confirmation": {
                "prompt": "{日付}の{時間}から{人数}名様で{名前}様のご予約いただいております。ご来店をお待ちしております。",
                "responses": {
                    RoutingResult.CONFIRM: TTSLabel.CONFIRM_RESERVATION_CONFIRM,
                    # RoutingResult.CHANGE: "ご希望の日付、時間、人数、をおっしゃってください。",
                    RoutingResult.CANCEL: TTSLabel.CONFIRM_RESERVATION_CANCEL,
                }
            }
        },

        Intent.CANCEL_RESERVATION: {
            "required_slots": [Slot.NAME],
            "optional_slots": [Slot.DATE, Slot.TIME, Slot.N_PERSON],
            "prompts": {
                Slot.NAME: TTSLabel.CANCEL_RESERVATION_NAME,
            },
            "responses": {
                DialogueState.COMPLETE: "{名前}様のご予約をキャンセルいたしました。",
                "NOT_FOUND": "申し訳ございません。{名前}様のご予約は見つかりませんでした。",
                "FOUND": "{日付}の{時間}から{人数}名様で{名前}様のご予約を確認いたしました。",
            },
            "implicit_confirmation": {
                Slot.NAME: "{名前}様ですね。",
            },
            "final_confirmation": {
                "prompt": "{日付}の{時間}から{人数}名様でご予約いただいております。キャンセルしてもよろしいでしょうか？",
                "responses": {
                    RoutingResult.YES: TTSLabel.CANCEL_RESERVATION_CONFIRM,
                    RoutingResult.CANCEL: TTSLabel.CANCEL_RESERVATION_CANCEL,
                },
            },
        },
        
        Intent.CHANGE_RESERVATION: {
            "required_slots": [],
            "optional_slots": [],
            "prompts": {},
            "responses": {},
            "implicit_confirmation": {},
            "final_confirmation": {},
        },

        Intent.ASK_ABOUT_STORE: {
            "required_slots": [],
            "optional_slots": [],
            "responses": {
                DialogueState.COMPLETE: "ご質問を伺ってもよろしいでしょうか。",
                DialogueState.CONTINUE: "ご用件を伺います。"
            },
            "final_confirmation": {
                "prompt": TTSLabel.ASK_OTHER_QUESTIONS,
                "responses": {
                    RoutingResult.CANCEL: TTSLabel.STORE_INFO_COMPLETE,
                    RoutingResult.CONFIRM: "ご質問ありがとうございます。",
                },
            },
        },
    }, 
    
    "common": {
        "fallback": {
            RoutingResult.INVALID_INTENT: TTSLabel.FALLBACK_INVALID_INTENT,
            RoutingResult.NO_INTENT: TTSLabel.FALLBACK_NO_INTENT,
            "CONVERSATION_ERROR": TTSLabel.FALLBACK_CONVERSATION_ERROR,
            "DEFAULT": TTSLabel.FALLBACK_DEFAULT,
        },
        "scene_initial": {
            Intent.NEW_RESERVATION: TTSLabel.NEW_RESERVATION_INTRO,
            Intent.CONFIRM_RESERVATION: TTSLabel.CONFIRM_RESERVATION_INTRO,
            Intent.CANCEL_RESERVATION: TTSLabel.CANCEL_RESERVATION_INTRO,
            Intent.ASK_ABOUT_STORE: TTSLabel.STORE_INFO_INTRO,
            Intent.CHANGE_RESERVATION: TTSLabel.CHANGE_RESERVATION_INTRO,
        },
        "scene_complete": {
            Intent.NEW_RESERVATION: TTSLabel.NEW_RESERVATION_COMPLETE,
            Intent.CONFIRM_RESERVATION: TTSLabel.CONFIRM_RESERVATION_COMPLETE,
            Intent.CANCEL_RESERVATION: TTSLabel.CANCEL_RESERVATION_COMPLETE,
            Intent.ASK_ABOUT_STORE: TTSLabel.STORE_INFO_COMPLETE,
        }
    }
}

