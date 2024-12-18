import spacy
from enum import Enum
from dataclasses import dataclass, field
from src.utils import get_custom_logger
from src.modules.nlu.process_text import process_date, process_time, process_person_count
from src.modules.nlu.validation import validate_date, validate_person_count, validate_time

logger = get_custom_logger(__name__)

class EntityLabel(Enum):
    DATE = ("DATE", "日付")
    TIME = ("TIME", "時間")
    PERSON = ("PERSON", "名前")
    N_PERSON = ("N_PERSON", "人数")
    PHONE_NUMBER = ("PHONE_NUMBER", "電話番号")
    LOCATION = ("CITY", "店舗名")

    @classmethod
    def spacy_to_ja(cls, slot_key):
        translated = slot_key
        for label in cls:
            if slot_key == label.value[0]:
                translated = label.value[1]
                break
        return translated

    @classmethod
    def ja_to_spacy(cls, slot_keys):
        result = []
        for key in slot_keys:
            translated = key  # 初期値は元のキー
            for label in cls:
                if key == label.value[1]:
                    translated = label.value[0]
                    break
            result.append(translated)
        return result


@dataclass
class NLUStatus:
    got_entities: bool = False
    got_terminal_forms: bool = False
    is_slot_filled: bool = False
    states: dict = field(default_factory=dict)


class StreamingNLUModule:
    MAX_TOKENS_POST_TERMINAL = 2

    def __init__(self, slot_keys: list[str] = None):
        if slot_keys is None:
            slot_keys = []

        # spaCyの日本語モデルをロード
        try:
            self.nlp = spacy.load("ja_ginza")
        except OSError:
            logger.error("日本語モデル 'ja_ginza' が見つかりません。")
            raise

        self.slot_keys = EntityLabel.ja_to_spacy(slot_keys)
        self.original_slot_keys = slot_keys  # 元の日本語のスロットキーを保持
        self.terminal_labels = []
        self.status = NLUStatus()
        self.cur_states = {k: "" for k in self.slot_keys}
        self.cur_states["terminal_forms"] = ""
        self.num_tokens_post_terminal = 0
        self.num_entity_non_empty = 0
        self.entities = {k: [] for k in self.slot_keys}
        self.terminal_forms = []
        self.faq_response = None
        self._hearing_item = ""  # ヒアリング項目を保持する変数

    def update_doc(self, text: str):
        if not text:
            logger.warning("空のテキストが渡されました。")
            self.doc = None
        else:
            self.doc = self.nlp(text)
            
    def validate_entity(self, label, value):
        flag = False
        if label == EntityLabel.DATE.value[0]:
            flag = validate_date(value)
        elif label == EntityLabel.TIME.value[0]:
            flag = validate_time(value)
        elif label == EntityLabel.N_PERSON.value[0]:
            # 数字以外を削除 (e.g. "6人" -> "6")
            value = ''.join(filter(str.isdigit, value))
            flag = validate_person_count(value)
        else:
            flag = True

        if not flag:
            value = ""

        return value
    
    def detect_hearing_item(self, text: str):
        """
        テキストからヒアリング項目を検出する
        Args:
            text (str): 入力テキスト
        Returns:
            str: 検出されたヒアリング項目
        """
        self._hearing_item = ""  # 初期化
        for slot in self.original_slot_keys:
            if slot in text:
                self._hearing_item = slot
                logger.debug(f"ヒアリング項目を検出: {slot}")
                break  # 最初に見つかったヒアリング項目のみを保持


    def extract_entities(self):
        if not self.doc:
            return

        for ent in self.doc.ents:
            label = ent.label_.upper()
            if label in self.entities:
                self.entities[label].append(self.validate_entity(label, ent.text))

    def extract_terminal_forms(self):
        if not self.doc:
            return

        self.num_tokens_post_terminal = 0
        for token in self.doc:
            morph = token.morph.get("Inflection")

            if len(self.terminal_forms) > 0:
                self.num_tokens_post_terminal += 1
                logger.debug(f"num_tokens_post_terminal: {self.num_tokens_post_terminal}")

                # # スロットが一つも埋まっていない場合はLLMに問い合わせ
                # if len([v for v in self.entities.values() if v]) == 0 and self.faq_response is None:
                #     logger.info("スロットが一つも埋まっていないが終止形を検知。LLMに問い合わせます。")
                #     asyncio.create_task(self.query_llm())

            if "接続助詞" in token.tag_ and self.num_tokens_post_terminal == 1:
                logger.debug(f"接続助詞を検出: {token.text}")
                self.status.got_terminal_forms = False

            else:
                if morph and "終止形" in morph[0]:
                    logger.debug(f"{self.terminal_labels}を検出: {token.text}")
                    self.num_tokens_post_terminal = 0
                    self.terminal_forms.append(token.text)

    def _reset_terminal_forms(self):
        self.terminal_forms = []
        self.status.got_terminal_forms = False
        self.cur_states["terminal_forms"] = ""

    def update_states(self):
        for k, v in self.entities.items():
            if v:
                self.cur_states[k] = v[-1]
        if self.terminal_forms:
            self.cur_states["terminal_forms"] = self.terminal_forms[-1]

    def log_states(self):
        logger.debug(f"Entities: {self.entities}")
        logger.debug(f"Terminal forms: {self.terminal_forms}")
        logger.debug(f"Current states: {self.cur_states}")

    def set_status(self):
        num_entity_non_empty = sum(bool(v) for v in self.entities.values())
        logger.debug(f"num_entity_non_empty: {num_entity_non_empty}, self.num_entity_non_empty: {self.num_entity_non_empty}")
        if len(self.slot_keys) > 0:
            if num_entity_non_empty > self.num_entity_non_empty:
                self.status.got_entities = True
            elif num_entity_non_empty == len(self.slot_keys):
                self.status.is_slot_filled = True
        if len(self.terminal_forms) > 0 and self.num_tokens_post_terminal == self.MAX_TOKENS_POST_TERMINAL - 1:
            self.status.got_terminal_forms = True

        if self.num_tokens_post_terminal >= self.MAX_TOKENS_POST_TERMINAL:
            self._reset_terminal_forms()

        self.num_entity_non_empty = num_entity_non_empty

        self.status.states = self.cur_states

    @property
    def got_entity(self):
        return self.status.got_entities

    @property
    def is_slot_filled(self):
        return self.status.is_slot_filled

    @property
    def is_terminal(self):
        return self.status.got_terminal_forms

    @property
    def states(self):
        return self.status.states

    @property
    def hearing_item(self):
        return self._hearing_item
    
    @property
    def slot_states(self):
        slot_states = {}
        for k, v in self.cur_states.items():
            if k != "terminal_forms":
                slot_states[EntityLabel.spacy_to_ja(k)] = v
        return slot_states

    def _preprocess_text(self, text: str):
        date_maps = process_date(text)
        logger.debug(f"date_maps: {date_maps} text: {text}")
        for k, v in date_maps.items():
            text = text.replace(k, v + ' ')

        time_maps = process_time(text)
        logger.debug(f"time_maps: {time_maps} text: {text}")
        for k, v in time_maps.items():
            text = text.replace(k, v + ' ')
            
        person_count_maps = process_person_count(text)
        logger.debug(f"person_count_maps: {person_count_maps} text: {text}")
        for k, v in person_count_maps.items():
            text = text.replace(k, v + ' ')
        print(text)

        return text

    def _post_process(self):
        pass
        # for k, v in self.cur_states.items():
        #     n_person = process_person_count(v)
        #     logger.debug(f"n_person: {n_person}")
        #     if n_person is not None:
        #         self.cur_states[k] = n_person

    def process(self, text: str):
        self.init_state()
        text = self._preprocess_text(text)
        
        # ヒアリング項目の検出を追加（template_slotsパラメータを削除）
        self.detect_hearing_item(text)
        
        self.update_doc(text)
        if self.doc:
            self.extract_entities()
            self.extract_terminal_forms()
            self.update_states()
            self.set_status()
            self._post_process()
        else:
            logger.error("テキストの処理中にエラーが発生しました。")

    def init_state(self):
        self.status = NLUStatus()
        self.cur_states = {k: "" for k in self.slot_keys}
        self.cur_states["terminal_forms"] = ""
        self.num_tokens_post_terminal = 0
        self.num_entity_non_empty = 0
        self.entities = {k: [] for k in self.slot_keys}
        self.terminal_forms = []
        self.faq_response = None

if __name__ == "__main__":
    import time
    nlu = StreamingNLUModule(slot_keys=["日付", "時間", "人数", "名前"])
    test_texts = [
        "明日の朝10時に6人で予約したいです",
        "日付を変更したいです",
        "人数を4名に変更お願いします",
        "時間を19時にしてください"
    ]

    for text in test_texts:
        tic = time.perf_counter()
        nlu.process(text)
        print(f"入力: {text}")
        print(f"検出されたヒアリング項目: {nlu.hearing_item}")
        print(f"slot_states: {nlu.slot_states}")
        toc = time.perf_counter() - tic
        print(f"処理時間: {toc:.3f} 秒")
        print("-" * 40)

    # async def main():
    #     nlu = StreamingNLUModule(slot_keys=["DATE", "TIME", "N_PERSON", "PERSON"])

    #     interium_text = [
    #         "明日",
    #         "明日の",
    #         "明日の朝10時",
    #         "明日の朝10時に",
    #         "明日の朝10時に6人",
    #         "明日の朝10時に6人で",
    #         "明日の朝10時に6人で予約",
    #         "明日の朝10時に6人で予約でき",
    #         "明日の朝10時に6人で大竹で予約できますか",
    #     ]

    #     for text in interium_text:
    #         tic = time.perf_counter()
    #         nlu.process(text)
    #         print(nlu.cur_states)
    #         toc = time.perf_counter() - tic
    #         print(f"処理時間: {toc:.3f} 秒")

    # asyncio.run(main())
    
    # async def test_process():
    #     nlu = StreamingNLUModule(slot_keys=["DATE", "TIME", "N_PERSON"])

    #     interium_text = [
    #         "駐車場",
    #         "駐車場って",
    #         "駐車場ってあります",
    #         "駐車場ってありますか",
    #         "駐車場ってありますか？"
    #     ]

    #     for text in interium_text:
    #         print(f"テストケース: {text}")
    #         tic = time.perf_counter()
    #         nlu.process(text)
    #         toc = time.perf_counter() - tic
    #         print(f"処理時間: {toc:.3f} 秒")
    #         print(f"最終回答: {nlu.faq_response}")
    #         print("-" * 40)
    # asyncio.run(test_process())