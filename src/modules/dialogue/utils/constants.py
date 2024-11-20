# src/modules/dialogue/constants/dialogue_state.py

from enum import Enum

class DialogueState(str, Enum):
    """対話の状態を表すEnum"""
    START = "START"
    CONTINUE = "CONTINUE"
    SLOTS_FILLED = "SLOTS_FILLED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    CORRECTION = "CORRECTION"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    INTENT_CHANGED = "INTENT_CHANGED"

class Intent(str, Enum):
    """対話の意図を表すEnum"""
    NEW_RESERVATION = "新規予約"
    CONFIRM_RESERVATION = "予約内容の確認"
    CANCEL_RESERVATION = "予約のキャンセル"
    ASK_ABOUT_STORE = "店舗についての質問"
    CHANGE = "CHANGE"
    CANCEL = "CANCEL"
    CONFIRM = "CONFIRM"
    YES = "YES"
    NO = "NO"

GLOBAL_INTENTS = [Intent.NEW_RESERVATION, Intent.CONFIRM_RESERVATION, Intent.CANCEL_RESERVATION, Intent.ASK_ABOUT_STORE] 
    
class RoutingResult(str, Enum):
    """意図のルーティング結果を表すEnum"""
    NO_INTENT = "NO_INTENT"
    INVALID_INTENT = "INVALID_INTENT"
    CONFIRM = "CONFIRM"
    CHANGE = "CHANGE"
    CANCEL = "CANCEL"
    INTENT_CHANGED = "INTENT_CHANGED"
    INTENT_UNCHANGED = "INTENT_UNCHANGED"
    YES = "YES"
    NO = "NO"

class Slot(str, Enum):
    """スロットの種類を表すEnum"""
    NAME = "名前"
    DATE = "日付"
    TIME = "時間"
    N_PERSON = "人数"
    

class TTSLabel(str, Enum):
    """音声合成のラベルを表すEnum"""
    SELECT = "SELECT"
    INITIAL = "INITIAL"
    FILLER = "FILLER"
    APOLOGIZE = "APOLOGIZE"
    DATE_1 = "DATE_1"
    TIME_1 = "TIME_1"
    N_PERSON_1 = "N_PERSON_1"
    NAME_1 = "NAME_1"
