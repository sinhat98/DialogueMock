from src.utils import get_custom_logger
logger = get_custom_logger(__name__)

class RuleDST:

    def __init__(self, nlg_template, state_template):
        self.action_types = list(nlg_template["action_type"].keys())
        self.inheriting_slots = {k: v["inheriting_slot"] for k, v in nlg_template["action_type"].items()}
        self.unrequited_slots = {k: v["unrequited_slot"] for k, v in nlg_template["action_type"].items()}
        self.slots = list(next(iter(nlg_template["action_type"].values()))["slot"].keys())

        self.initial_state = {s: state_template.get(s, "") for s in self.slots}
        self.state_stack = []
        
        logger.info(f"Initial state: {self.initial_state}")
        

    def _validate_action_type(self, action_type):
        assert action_type in self.action_types, "Unknown action type detected."

    def _initial_update_state(self, nlu_out):
        state = {k: (v if v else self.initial_state[k]) for k, v in nlu_out["slot"].items()}
        self.state_stack.append((nlu_out["action_type"], state))

    def update_state(self, nlu_out):
        logger.debug(f"Pre state: {self.state_stack}")
        
        if not self.state_stack:
            self._initial_update_state(nlu_out)
            self.fill_unrequited_state()
            return "CONVERSATION_CONTINUE"
        else:
            if nlu_out["action_type"] == "":
                action, state = self.state_stack.pop()
                state.update({k: v for k, v in nlu_out["slot"].items() if v})
                self.state_stack.append((action, state))
                logger.debug(f"Current state: {self.state_stack}")
                return "CONVERSATION_CONTINUE"
            else:
                self._initial_update_state(nlu_out)
                return "SWITCH_SCENE"

    def inheriting_state(self):
        assert len(self.state_stack) > 1, "No previous state to inherit from."
        curr_action, curr_state = self.state_stack.pop()
        prev_action, prev_state = self.state_stack[-1]
        for slot in self.inheriting_slots[curr_action]:
            curr_state[slot] = prev_state[slot]
        self.state_stack.append((curr_action, curr_state))

    def fill_unrequited_state(self):
        action, state = self.state_stack.pop()
        for slot in self.unrequited_slots[action]:
            state[slot] = "UNREQUITED_SLOT"
        self.state_stack.append((action, state))

    def del_state(self, del_slots):
        action, state = self.state_stack.pop()
        for slot in del_slots:
            state[slot] = ""
        self.state_stack.append((action, state))

    # クラスメソッドにチェック用のメソッドを追加
    def is_complete(self):
        if not self.state_stack:
            return False
        _, state = self.state_stack[-1]
        return all(state.values())

    # check_complete メソッドはそのままにして、新しいメソッドを呼び出す
    def check_complete(self):
        if self.is_complete():
            self.state_stack.pop()
            return "CONVERSATION_END" if not self.state_stack else "BACK_PREV_SCENE"
        return "CONVERSATION_CONTINUE"


if __name__ == "__main__":
    from src.dialogue.utils.template import templates
    from src.dialogue.module.nlg import TemplateNLG
    from copy import deepcopy
    
    # state_template = {
    #     "店舗": "渋谷店",
    #     "日付": "",
    #     "時間": "",
    #     "人数": "",
    #     "名前": "",
    # }


    state_template = {
        "名前": "",
    }

    # RuleDST と TemplateNLG の初期化
    dst = RuleDST(templates, state_template)
    nlg = TemplateNLG(templates)
    
    # 初期状態の確認
    print("初期状態:", dst.initial_state)
    print(dst.state_stack)

    # 最初のユーザー入力を処理 日付と時間を一度に指定
    print("\nユーザー: 10/1の15:00に予約したいのですが")
    state = deepcopy(dst.initial_state)
    state["日付"] = "10/1"
    state["時間"] = "15:00"
    # prev_stateとstateを比較して変更があったslot_keyを取得
    nlu_output = {"action_type": "新規予約", "slot": state}
    prev_state = deepcopy(dst.state_stack[-1][1]) if dst.state_stack else dst.initial_state
    dst.update_state(nlu_output)
    
    implicit_confirmation = nlg.get_confirmation_response((nlu_output["action_type"], state), prev_state)
    print("システム:", implicit_confirmation)
    response = nlg.get_response(dst.state_stack[-1])
    print("システム:", response)
    print("現在の状態:", dst.state_stack)

    # 追加のユーザー入力を処理 人数のみ
    print("\nユーザー: 2人でお願いします。")
    state["人数"] = "2"
    nlu_output = {"action_type": "", "slot": state}
    prev_state = deepcopy(dst.state_stack[-1][1])
    dst.update_state(nlu_output)
    implicit_confirmation = nlg.get_confirmation_response((dst.state_stack[-1][0], state), prev_state)
    print("システム:", implicit_confirmation)
    response = nlg.get_response(dst.state_stack[-1])
    print("システム:", response)
    print("現在の状態:", dst.state_stack)
    
    # 追加のユーザー入力を処理 名前のみ
    print("\nユーザー: 山田です。")
    state["名前"] = "山田"
    nlu_output = {"action_type": "", "slot": state}
    prev_state = deepcopy(dst.state_stack[-1][1])
    dst.update_state(nlu_output)
    implicit_confirmation = nlg.get_confirmation_response((dst.state_stack[-1][0], state), prev_state)
    print("システム:", implicit_confirmation)
    response = nlg.get_response(dst.state_stack[-1])
    print("システム:", response)
    print("現在の状態:", dst.state_stack)
    
    # 確認応答
    print("\nシステム: ご予約を確定してもよろしいでしょうか？")
    user_confirm = "はい"  # この応答はユーザーが行うと仮定しています。
    confirm_response = nlg.get_confirm_response(dst.state_stack[-1][0], user_confirm)
    print("ユーザー:", user_confirm)
    print("システム:", confirm_response)