from typing import Dict, Optional, Tuple
from src.utils import get_custom_logger

from src.modules.dialogue.utils.inverse_entity_normalization import format_entity

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
        # self.confirmation = templates.get("confirmation", {})  # 追加
        logger.info("Initialized TemplateNLG")

    def get_confirmation(self, intent):
        intents_template = self.scenes.get(intent, {})
        # logger.debug(f"Intents template: {intents_template}")
        final_confirmation_config = intents_template.get("final_confirmation", {})
        # logger.debug(f"Final confirmation config: {final_confirmation_config}")
        return final_confirmation_config

    def get_confirmation_prompt(self, intent: str, state: Dict[str, str]) -> Optional[str]:
        """
        確認シーンのプロンプトを生成
        Args:
            intent (str): 現在のintent
            state (Dict[str, str]): 現在の状態
        Returns:
            Optional[str]: 確認プロンプト
        """
        logger.debug(f"Current intent: {intent} and state: {state}")
        confirmation_config = self.get_confirmation(intent)
        
        try:
            formated_state = format_entity(state)
            logger.debug(f"Formatted state for confirmation prompt: {formated_state}")
            prompt = confirmation_config["prompt"].format(**formated_state)
            logger.debug(f"Generated confirmation prompt: {prompt}")
            return prompt
        except KeyError as e:
            logger.error(f"Missing key in state for confirmation prompt: {e}")
            return None

    def get_confirmation_response(self, intent: str, confirmation_type: str) -> Optional[str]:
        """
        確認シーンの応答を生成
        Args:
            intent (str): 現在のintent
            confirmation_type (str): 確認応答の種類 (confirm/change/cancel)
        Returns:
            Optional[str]: 確認応答文
        """
        confirmation = self.get_confirmation(intent)
        if len(confirmation) == 0:
            return None
        response = confirmation["responses"].get(confirmation_type)
        if response:
            logger.debug(f"Generated confirmation response for {confirmation_type}: {response}")
            return response
        return None

    def get_correction_guidance(self, intent: str) -> Optional[str]:
        """
        修正項目の選択ガイダンスを生成
        Args:
            intent (str): 現在のintent
        Returns:
            Optional[str]: 修正ガイダンス文
        """
        confirmation = self.get_confirmation(intent)
        if len(confirmation) == 0:
            return None
            
        guidance = confirmation["responses"].get("change")
        if guidance:
            logger.debug(f"Generated correction guidance: {guidance}")
            return guidance
        return None

    def get_slot_correction_prompt(self, intent: str, slot: str) -> Optional[str]:
        """
        スロット修正用のプロンプトを生成
        Args:
            intent (str): 現在のintent
            slot (str): 修正対象のスロット
        Returns:
            Optional[str]: 修正プロンプト
        """
        scene = self.scenes.get(intent, {})
        
        correction = scene.get("correction", {}).get(slot)
        
        if correction:
            logger.debug(f"Generated slot correction prompt for {slot}: {correction}")
            return correction
        return None

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
            logger.debug(f"Generated question for slot {slot}: {question}")
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
                formatted_state = format_entity(state)
                response = response_template.format(**formatted_state)
                logger.debug(f"Generated {response_type} response for {intent}: {response}")
                return response
            except KeyError as e:
                logger.error(f"Missing key in state for response template: {e}")
                return None
        return None

    def get_implicit_confirmation(self, intent: str, 
                                updated_slots: dict) -> Optional[str]:
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
        
        logger.debug(f"Updated slots: {updated_slots} for intent: {intent}")

        scene = self.scenes.get(intent, {})
        logger.debug(f"Scene config: {scene}")
        confirmation_templates = scene.get("implicit_confirmation", {})
        logger.debug(f"Implicit confirmation config: {confirmation_templates}")

        # 複数スロットの組み合わせ確認
        slots_key = frozenset(updated_slots.keys())
        logger.debug(f"Slots key: {slots_key}")
        
        # 固有表現の逆正規化
        formatted_slots = format_entity(updated_slots)
        
        if slots_key in confirmation_templates:
            try:
                message = confirmation_templates[slots_key].format(**formatted_slots)
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
                    message = confirmation_templates[slot].format(**formatted_slots)
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

    def get_correction_prompt(self, intent: str, slot: str) -> Optional[str]:
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
            logger.debug(f"Generated correction prompt for {slot}: {correction}")
            return correction
        return None
    
    def get_final_confrmation_response(self, intent: str, local_intent: str) -> Optional[str]:
        """
        最終確認応答を生成
        Args:
            intent (str): 現在のintent
        Returns:
            Optional[str]: 最終確認応答文
        """
        scene = self.scenes.get(intent, {})
        logger.debug(f"Scene config: {scene}")
        final_confirmation = scene.get("final_confirmation", {})
        logger.debug(f"Final confirmation config: {final_confirmation}")
        response = final_confirmation.get("responses", {}).get(local_intent)
        logger.debug(f"Generated final confirmation response: {response} for {local_intent}")
        return response

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
            formatted_state = format_entity(state)
            response = template.format(**formatted_state)
            return response
        except KeyError as e:
            logger.error(f"Missing key in state for template: {e}")
            return None