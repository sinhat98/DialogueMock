from src.utils import get_custom_logger

logger = get_custom_logger(__name__)


class RuleDST:
    def __init__(self, nlg_template, state_template):
        """
        Args:
            nlg_template (dict): NLGテンプレート
            state_template (dict): 初期状態のテンプレート
                        global slotsの値をあらかじめ埋めておきたい場合はここに記述する
        """
        self.action_types = list(nlg_template["action_type"].keys())
        self.inheriting_slots = {
            k: v["inheriting_slot"] for k, v in nlg_template["action_type"].items()
        }
        self.unrequited_slots = {
            k: v["unrequited_slot"] for k, v in nlg_template["action_type"].items()
        }

        # action_typeをキーとしslotのリストを値とする辞書を作成
        global_slots = set()
        slots_dict = {}
        for k, v in nlg_template["action_type"].items():
            slots_dict[k] = list(v["slot"].keys())
            global_slots |= set(slots_dict[k])

        self.slots = slots_dict
        self.initial_state = state_template
        self.state_stack = []
        self.current_action_type = None  # action_typeを保持する変数を追加

        logger.info(f"Initial state: {self.initial_state}")

    def _validate_action_type(self, action_type):
        """action_typeが有効かどうかを検証"""
        assert action_type in self.action_types, "Unknown action type detected."

    def _initial_update_state(self, nlu_out):
        """初期状態の更新処理"""
        state = {
            k: (v if v else self.initial_state[k]) for k, v in nlu_out["slot"].items()
        }
        if nlu_out["action_type"]:  # action_typeが指定されている場合のみ更新
            self._validate_action_type(nlu_out["action_type"])
            self.current_action_type = nlu_out["action_type"]
        self.state_stack.append((self.current_action_type, state))

    def update_state(self, nlu_out):
        """状態を更新"""
        logger.debug(f"Pre state: {self.state_stack}")

        if not self.state_stack:
            self._initial_update_state(nlu_out)
            self.fill_unrequited_state()
            return "CONVERSATION_CONTINUE"
        else:
            action, state = self.state_stack.pop()
            state.update({k: v for k, v in nlu_out["slot"].items() if v})
            self.state_stack.append((self.current_action_type, state))
            logger.debug(f"Current state: {self.state_stack}")
            return "CONVERSATION_CONTINUE"
    def detect_updated_slots(self, nlu_out, current_state):
        """
        NLU出力と現在の状態を比較して、更新されたスロットを検出
        Args:
            nlu_out (dict): NLUの出力
            current_state (dict): 現在の状態
        Returns:
            list: 更新されたスロットのリスト
        """
        updated_slots = []
        for slot, value in nlu_out["slot"].items():
            if value and value != current_state.get(slot, ""):
                updated_slots.append(slot)
                logger.debug(f"Updated slot: {slot}")
        return updated_slots

    def update_state_with_slots(self, nlu_out, updated_slots):
        """
        特定のスロットのみを更新
        Args:
            nlu_out (dict): NLUの出力
            updated_slots (list): 更新するスロットのリスト
        """
        action, state = self.state_stack.pop()
        for slot in updated_slots:
            state[slot] = nlu_out["slot"][slot]
        logger.debug(f"Updated state: {state}")
        self.state_stack.append((self.current_action_type, state))
    def inheriting_state(self):
        """前の状態から継承すべきスロットの値を継承"""
        assert len(self.state_stack) > 1, "No previous state to inherit from."
        curr_action, curr_state = self.state_stack.pop()
        prev_action, prev_state = self.state_stack[-1]
        for slot in self.inheriting_slots[curr_action]:
            curr_state[slot] = prev_state[slot]
        self.state_stack.append((curr_action, curr_state))

    def fill_unrequited_state(self):
        """不要なスロットに値を設定"""
        action, state = self.state_stack.pop()
        for slot in self.unrequited_slots[action]:
            state[slot] = "UNREQUITED_SLOT"
        self.state_stack.append((action, state))

    def del_state(self, del_slots):
        """指定されたスロットの値を削除"""
        action, state = self.state_stack.pop()
        for slot in del_slots:
            state[slot] = ""
        self.state_stack.append((action, state))

    def is_complete(self):
        """全てのスロットが埋まっているかチェック"""
        if not self.state_stack:
            return False
        
        _, state = self.state_stack[-1]
        
        # 現在のaction_typeに必要なスロットを取得
        required_slots = self.slots.get(self.current_action_type, [])
        
        # 必要なスロットが全て埋まっているかチェック
        for slot in required_slots:
            if not state.get(slot):  # スロットが空または存在しない場合
                return False
                
        return True

    def check_complete(self):
        """対話の完了状態をチェック"""
        if self.is_complete():
            self.state_stack.pop()
            return "CONVERSATION_END" if not self.state_stack else "BACK_PREV_SCENE"
        return "CONVERSATION_CONTINUE"

    def get_current_action_type(self):
        """現在のaction_typeを取得"""
        return self.current_action_type

    def get_current_state(self):
        """現在の状態を取得"""
        if not self.state_stack:
            return None, self.initial_state
        return self.state_stack[-1]

    def reset(self):
        """状態をリセット"""
        self.state_stack = []
        self.current_action_type = None

    def get_required_slots(self):
        """現在のaction_typeで必要なスロットのリストを取得"""
        if not self.current_action_type:
            return []
        return self.slots.get(self.current_action_type, [])
