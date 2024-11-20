# src/modules/dialogue/dst.py

from typing import Dict, List, Optional, Set
from src.utils import get_custom_logger
from src.modules.dialogue.utils.constants import RoutingResult, DialogueState, Intent, GLOBAL_INTENTS

logger = get_custom_logger(__name__)


class RuleDST:
    def __init__(self, templates: Dict):
        """
        対話状態を管理するDSTの初期化
        Args:
            templates (Dict): 対話管理に必要なテンプレート情報
        """
        self.templates = templates
        self.scenes = templates["scenes"]
        
        
        # 状態の初期化
        self.reset()
        
        logger.info(f"Initial state: {self.state}")

    def reset(self):
        """状態を初期化"""
        self.current_intent = None
        self.state = self.templates["initial_state"].copy()
        self.previous_state = None
        self.dialogue_state = DialogueState.START
        self.correction_slot = None
        logger.info("Reset dialogue state")


    def route_intent(self, nlu_out: Dict) -> RoutingResult:
        """
        NLU出力からintentを判定し、対話をルーティング
        """
        intent = nlu_out.get("intent")
        if not intent:
            logger.warning("No intent detected in NLU output")
            return RoutingResult.NO_INTENT

        # 確認シーンでの特別な処理
        if self.dialogue_state == DialogueState.WAITING_CONFIRMATION:
            if intent == Intent.CONFIRM:
                return RoutingResult.CONFIRM
            elif intent == Intent.CHANGE:
                return RoutingResult.CHANGE
            elif intent == Intent.CANCEL:
                return RoutingResult.CANCEL

        if intent in GLOBAL_INTENTS and intent != self.current_intent:
            logger.info(f"Intent changed from {self.current_intent} to {intent}")
            self.current_intent = intent
            return RoutingResult.INTENT_CHANGED

        return RoutingResult.INTENT_UNCHANGED

    def get_required_slots(self) -> List[str]:
        """
        現在のintentで必要なスロットを取得
        Returns:
            List[str]: 必須スロットのリスト
        """
        if not self.current_intent or self.current_intent in [RoutingResult.CONFIRM, RoutingResult.CHANGE, RoutingResult.CANCEL]:
            return []
        return self.scenes[self.current_intent].get("required_slots", [])

    def get_optional_slots(self) -> List[str]:
        """
        現在のintentで任意のスロットを取得
        Returns:
            List[str]: 任意スロットのリスト
        """
        if not self.current_intent or self.current_intent in [RoutingResult.CONFIRM, RoutingResult.CHANGE, RoutingResult.CANCEL]:
            return []
        return self.scenes[self.current_intent].get("optional_slots", [])

    def get_missing_slots(self) -> List[str]:
        """
        未入力の必須スロットを取得
        Returns:
            List[str]: 未入力の必須スロットのリスト
        """
        if self.dialogue_state == "CORRECTION" and self.correction_slot:
            return [self.correction_slot]
        required_slots = self.get_required_slots()
        return [slot for slot in required_slots if not self.state.get(slot)]

    def get_updated_slots(self) -> Set[str]:
        """
        前回の状態から更新されたスロットを取得
        Returns:
            Set[str]: 更新されたスロットの集合
        """
        if not self.previous_state:
            return set(k for k, v in self.state.items() if v)
        
        return {
            slot for slot, value in self.state.items()
            if value and value != self.previous_state.get(slot)
        }
        
    def get_updated_slots_dict(self) -> Dict[str, str]:
        """
        前回の状態から更新されたスロットと値の辞書を取得
        Returns:
            Dict[str, str]: 更新されたスロットと値の辞書
        """
        updated_slots = self.get_updated_slots()
        return {slot: self.state[slot] for slot in updated_slots}

    def update_slot_values(self, slot_values: Dict[str, str]):
        """
        スロット値を更新
        Args:
            slot_values (Dict[str, str]): 更新するスロットと値の辞書
        """
        for slot, value in slot_values.items():
            if value:
                self.state[slot] = value
                logger.debug(f"Updated slot {slot}: {value}")

    def set_correction_slot(self, slot: str):
        """
        修正対象のスロットを設定
        Args:
            slot (str): 修正対象のスロット
        """
        self.correction_slot = slot
        self.dialogue_state = "CORRECTION"
        logger.info(f"Set correction slot: {slot}")

    def update_state(self, nlu_out: Dict) -> DialogueState:
        """
        対話状態を更新
        """
        self.previous_state = self.state.copy()
        self.update_slot_values(nlu_out.get("slot", {}))

        # intentのルーティング
        routing_result = self.route_intent(nlu_out)
        
        if routing_result in [RoutingResult.NO_INTENT, RoutingResult.INVALID_INTENT]:
            self.dialogue_state = DialogueState.ERROR
            return self.dialogue_state

        # 確認待ち状態での処理
        if self.dialogue_state == DialogueState.WAITING_CONFIRMATION:
            if routing_result == RoutingResult.CONFIRM:
                self.dialogue_state = DialogueState.COMPLETE
            elif routing_result == RoutingResult.CHANGE:
                self.dialogue_state = DialogueState.CORRECTION
            elif routing_result == RoutingResult.CANCEL:
                self.dialogue_state = DialogueState.CANCELLED
            return self.dialogue_state

        # 修正状態での処理
        if self.dialogue_state == DialogueState.CORRECTION:
            if self.correction_slot and self.state.get(self.correction_slot):
                self.dialogue_state = DialogueState.WAITING_CONFIRMATION
                self.correction_slot = None
            return self.dialogue_state

        # 通常の対話処理
        if routing_result == RoutingResult.INTENT_CHANGED:
            self.dialogue_state = DialogueState.INTENT_CHANGED
        elif len(self.get_required_slots()) > 0 and not self.get_missing_slots():
            self.dialogue_state = DialogueState.SLOTS_FILLED
        else:
            self.dialogue_state = DialogueState.CONTINUE

        return self.dialogue_state

    
    def set_dialogue_state(self, state: str):
        """
        対話状態を設定
        Args:
            state (str): 対話状態
        """
        self.dialogue_state = state
        logger.info(f"Set dialogue state: {state}")

    def get_current_state(self) -> Dict:
        """
        現在の状態を取得
        Returns:
            Dict: 現在の状態の情報
        """
        return {
            "intent": self.current_intent,
            "state": self.state.copy(),
            "previous_state": self.previous_state.copy() if self.previous_state else None,
            "dialogue_state": self.dialogue_state,
            "missing_slots": self.get_missing_slots(),
            "updated_slots": list(self.get_updated_slots()),
            "required_slots": self.get_required_slots(),
            "optional_slots": self.get_optional_slots(),
            "correction_slot": self.correction_slot
        }

    # def can_transition_to(self, new_intent: str) -> bool:
    #     """
    #     指定されたintentへの遷移が可能か確認
    #     Args:
    #         new_intent (str): 遷移先のintent
    #     Returns:
    #         bool: 遷移可能な場合True
    #     """
    #     return new_intent in self.intents

    def reset_state(self, keep_slots: Optional[List[str]] = None):
        """
        状態を部分的にリセット
        Args:
            keep_slots (Optional[List[str]]): 値を保持するスロットのリスト
        """
        kept_values = {}
        if keep_slots:
            kept_values = {
                slot: self.state[slot]
                for slot in keep_slots
                if slot in self.state
            }

        self.state = self.templates["initial_state"].copy()
        self.state.update(kept_values)
        self.previous_state = None
        self.dialogue_state = "CONVERSATION_CONTINUE"
        self.correction_slot = None
        
        logger.info("Reset dialogue state")
        if keep_slots:
            logger.info(f"Kept values for slots: {kept_values}")