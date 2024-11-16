# src/modules/dialogue/dst.py

from typing import Dict, List, Optional, Set
from src.utils import get_custom_logger

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
        self.intents = list(self.scenes.keys())
        
        # 状態の初期化
        self.reset()
        
        logger.info(f"Initialized RuleDST with intents: {self.intents}")
        logger.info(f"Initial state: {self.state}")

    def reset(self):
        """状態を初期化"""
        self.current_intent = None
        self.state = self.templates["initial_state"].copy()
        self.previous_state = None
        self.dialogue_state = "CONVERSATION_START"
        logger.info("Reset dialogue state")

    def route_intent(self, nlu_out: Dict) -> str:
        """
        NLU出力からintentを判定し、対話をルーティング
        Args:
            nlu_out (Dict): NLU出力
        Returns:
            str: ルーティング結果
        """
        intent = nlu_out.get("intent")
        if not intent:
            logger.warning("No intent detected in NLU output")
            return "NO_INTENT_DETECTED"

        if intent not in self.intents:
            logger.warning(f"Invalid intent detected: {intent}")
            return "INVALID_INTENT"

        if intent != self.current_intent:
            logger.info(f"Intent changed from {self.current_intent} to {intent}")
            self.current_intent = intent
            return "INTENT_CHANGED"

        return "INTENT_UNCHANGED"

    def get_required_slots(self) -> List[str]:
        """
        現在のintentで必要なスロットを取得
        Returns:
            List[str]: 必須スロットのリスト
        """
        if not self.current_intent:
            return []
        return self.scenes[self.current_intent].get("required_slots", [])

    def get_optional_slots(self) -> List[str]:
        """
        現在のintentで任意のスロットを取得
        Returns:
            List[str]: 任意スロットのリスト
        """
        if not self.current_intent:
            return []
        return self.scenes[self.current_intent].get("optional_slots", [])

    def get_missing_slots(self) -> List[str]:
        """
        未入力の必須スロットを取得
        Returns:
            List[str]: 未入力の必須スロットのリスト
        """
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

    def update_state(self, nlu_out: Dict) -> str:
        """
        対話状態を更新
        Args:
            nlu_out (Dict): NLU出力
        Returns:
            str: 対話状態
        """
        # 現在の状態を保存
        self.previous_state = self.state.copy()

        # intentのルーティング
        routing_result = self.route_intent(nlu_out)
        if routing_result in ["INVALID_INTENT", "NO_INTENT_DETECTED"]:
            self.dialogue_state = "CONVERSATION_ERROR"
            return "CONVERSATION_ERROR"

        # スロット値の更新
        self.update_slot_values(nlu_out.get("slot", {}))

        # 対話状態の判定
        if routing_result == "INTENT_CHANGED":
            self.dialogue_state = "INTENT_CHANGED"
            return "INTENT_CHANGED"

        if not self.get_missing_slots():
            self.dialogue_state = "CONVERSATION_COMPLETE"
            return "CONVERSATION_COMPLETE"

        self.dialogue_state = "CONVERSATION_CONTINUE"
        return "CONVERSATION_CONTINUE"

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
            "updated_slots": self.get_updated_slots(),
            "required_slots": self.get_required_slots(),
            "optional_slots": self.get_optional_slots()
        }

    def can_transition_to(self, new_intent: str) -> bool:
        """
        指定されたintentへの遷移が可能か確認
        Args:
            new_intent (str): 遷移先のintent
        Returns:
            bool: 遷移可能な場合True
        """
        return new_intent in self.intents

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
        
        logger.info("Reset dialogue state")
        if keep_slots:
            logger.info(f"Kept values for slots: {kept_values}")