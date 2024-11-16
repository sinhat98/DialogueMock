from typing import Dict, Optional, Tuple
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

class TemplateNLG:
    def __init__(self, templates: Dict):
        """
        Args:
            templates (Dict): 応答生成に必要なテンプレート情報
        """
        self.templates = templates
        self.scenes = templates["scenes"]
        self.common = templates["common"]
        logger.info("Initialized TemplateNLG")

    def get_scene_initial_response(self, intent: str) -> Optional[str]:
        """
        シーン開始時の応答を生成
        Args:
            intent (str): 現在のintent
        Returns:
            Optional[str]: 応答文
        """
        initial_response = self.common["scene_initial"].get(intent)
        if initial_response:
            logger.debug(f"Generated initial response for {intent}: {initial_response}")
        return initial_response

    def get_scene_complete_response(self, intent: str) -> Optional[str]:
        """
        シーン完了時の応答を生成
        Args:
            intent (str): 現在のintent
        Returns:
            Optional[str]: 応答文
        """
        complete_response = self.common["scene_complete"].get(intent)
        if complete_response:
            logger.debug(f"Generated complete response for {intent}: {complete_response}")
        return complete_response

    def get_next_question(self, intent: str, slot: str) -> Optional[Tuple[str, str]]:
        """
        次の質問を生成
        Args:
            intent (str): 現在のintent
            slot (str): 質問するスロット
        Returns:
            Optional[Tuple[str, str]]: (質問文, 発話ラベル)
        """
        scene = self.scenes.get(intent, {})
        prompts = scene.get("prompts", {})
        
        if slot in prompts:
            question = prompts[slot]
            logger.debug(f"Generated question for slot {slot}: {question[0]}")
            return question
        return None

    def get_intent_response(self, intent: str, state: Dict[str, str], 
                          response_type: str = "COMPLETE") -> Optional[str]:
        """
        intentに基づく応答を生成
        Args:
            intent (str): 現在のintent
            state (Dict[str, str]): 現在の状態
            response_type (str): 応答の種類
        Returns:
            Optional[str]: 応答文
        """
        scene = self.scenes.get(intent, {})
        response_template = scene.get("responses", {}).get(response_type)
        
        if response_template:
            try:
                response = response_template.format(**state)
                logger.debug(f"Generated {response_type} response for {intent}: {response}")
                return response
            except KeyError as e:
                logger.error(f"Missing key in state for response template: {e}")
                return None
        return None

    def get_implicit_confirmation(self, intent: str, 
                                updated_slots: Dict[str, str]) -> Optional[str]:
        """
        暗黙の確認応答を生成
        Args:
            intent (str): 現在のintent
            updated_slots (Dict[str, str]): 更新されたスロットと値
        Returns:
            Optional[str]: 確認応答文
        """
        if not updated_slots:
            return None

        scene = self.scenes.get(intent, {})
        confirmation_templates = scene.get("implicit_confirmation", {})

        # 複数スロットの組み合わせ確認
        slots_key = frozenset(updated_slots.keys())
        if slots_key in confirmation_templates:
            try:
                message = confirmation_templates[slots_key].format(**updated_slots)
                logger.debug(f"Generated multiple slots confirmation: {message}")
                return message
            except KeyError as e:
                logger.error(f"Missing key in updated_slots for confirmation: {e}")
                return None

        # 単一スロットの確認
        if len(updated_slots) == 1:
            slot = list(updated_slots.keys())[0]
            if slot in confirmation_templates:
                try:
                    message = confirmation_templates[slot].format(**updated_slots)
                    logger.debug(f"Generated single slot confirmation: {message}")
                    return message
                except KeyError as e:
                    logger.error(f"Missing key in updated_slots for confirmation: {e}")
                    return None

        return None

    def get_explicit_confirmation(self, intent: str, user_response: str) -> Optional[str]:
        """
        明示的な確認応答を生成
        Args:
            intent (str): 現在のintent
            user_response (str): ユーザーの応答
        Returns:
            Optional[str]: 確認応答文
        """
        scene = self.scenes.get(intent, {})
        confirm_responses = scene.get("confirm", {})
        
        response = confirm_responses.get(user_response)
        if response:
            logger.debug(f"Generated explicit confirmation: {response}")
        return response

    def get_correction_prompt(self, intent: str, slot: str) -> Optional[Tuple[str, str]]:
        """
        修正用の質問を生成
        Args:
            intent (str): 現在のintent
            slot (str): 修正対象のスロット
        Returns:
            Optional[Tuple[str, str]]: (質問文, 発話ラベル)
        """
        scene = self.scenes.get(intent, {})
        correction = scene.get("correction", {}).get(slot)
        
        if correction:
            logger.debug(f"Generated correction prompt for {slot}: {correction[0]}")
            return correction
        return None

    def get_fallback_message(self, fallback_type: str) -> str:
        """
        フォールバックメッセージを生成
        Args:
            fallback_type (str): フォールバックの種類
        Returns:
            str: フォールバックメッセージ
        """
        fallback_templates = self.common["fallback"]
        message = fallback_templates.get(fallback_type, fallback_templates["DEFAULT"])
        logger.debug(f"Generated fallback message for {fallback_type}: {message}")
        return message

    def format_response(self, template: str, state: Dict[str, str]) -> Optional[str]:
        """
        テンプレートを状態に基づいてフォーマット
        Args:
            template (str): 応答テンプレート
            state (Dict[str, str]): 現在の状態
        Returns:
            Optional[str]: フォーマットされた応答文
        """
        try:
            response = template.format(**state)
            return response
        except KeyError as e:
            logger.error(f"Missing key in state for template: {e}")
            return None