# app.py

import gradio as gr
from typing import List, Tuple, Dict, Optional
from src.utils import get_custom_logger
from src.modules.dialogue.new_dst import RuleDST
from src.modules.dialogue.new_nlg import TemplateNLG
from src.modules.dialogue.utils.new_template import templates, intents
from src.modules.nlu.streaming_nlu import StreamingNLUModule
from src.modules.nlu.prompt import get_system_prompt_for_intent_classification
from src.bridge.llm_bridge import LLMBridge

logger = get_custom_logger(__name__)

class DialogueSystem:
    def __init__(self):
        """対話システムの初期化"""
        self.dst = RuleDST(templates)
        self.nlg = TemplateNLG(templates)
        
        # NLUモジュールの初期化
        self.rule_based_sf = StreamingNLUModule(
            slot_keys=list(templates["initial_state"].keys())
        )
        # LLM用のプロンプトを生成
        intent_prompt = get_system_prompt_for_intent_classification(intents)
        self.llm_nlu = LLMBridge(
            intent_prompt,
            json_format=True
        )
        
        self.reset_dialogue()

    def reset_dialogue(self):
        """対話状態のリセット"""
        self.dst.reset()
        self.rule_based_sf.reset()
        logger.info("Dialogue state reset")

    def _need_intent_classification(self, message: str, current_state: Dict) -> bool:
        """
        intentの分類が必要かどうかを判断
        """
        if not current_state["intent"]:
            return True

        if (current_state["dialogue_state"] == "CONVERSATION_COMPLETE" and 
            "いいえ" in message):
            return True

        intent_trigger_words = ["予約", "確認", "キャンセル", "質問"]
        if any(word in message for word in intent_trigger_words):
            return True

        return False

    def _classify_intent(self, message: str) -> Optional[Dict]:
        """
        LLMを使用してintentを分類
        """
        try:
            llm_output = eval(self.llm_nlu.call_llm(message))
            intent = llm_output.pop("用件", "")
            nlu_result = {
                "intent": intent,
                "slot": llm_output
            }
            logger.info(f"LLM intent classification result: {nlu_result}")
            return nlu_result
        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            return None

    def process_message(
        self, 
        user_message: str, 
        chat_history: List[Tuple[str, str]]
    ) -> Tuple[str, List[Tuple[str, str]], str]:
        """
        ユーザーメッセージの処理
        """
        current_state = self.dst.get_current_state()

        # intent分類の必要性を判断
        if self._need_intent_classification(user_message, current_state):
            nlu_result = self._classify_intent(user_message)
            if not nlu_result:
                return "", chat_history, "Intent classification failed"
        else:
            # スロットフィリング
            self.rule_based_sf.process(user_message)
            nlu_result = {
                "intent": current_state["intent"],
                "slot": self.rule_based_sf.slot_states
            }
            logger.info(f"Rule-based slot filling result: {nlu_result}")

        # 状態を更新
        previous_state = current_state["state"].copy()
        dialogue_status = self.dst.update_state(nlu_result)
        updated_state = self.dst.get_current_state()
        
        # 応答を生成
        response = self._generate_response(
            dialogue_status, 
            updated_state,
            previous_state
        )
        
        # 対話履歴を更新
        chat_history.append((user_message, response))

        # 状態表示を更新
        state_display = self._format_state_display(updated_state)

        return "", chat_history, state_display

    def _generate_response(
        self, 
        dialogue_status: str, 
        current_state: Dict,
        previous_state: Dict
    ) -> str:
        """状態に応じた応答を生成"""
        if dialogue_status == "CONVERSATION_ERROR":
            return self.nlg.get_fallback_message("INVALID_INTENT")

        # 新しいintentの場合、初期応答を生成
        if dialogue_status == "INTENT_CHANGED":
            return self.nlg.get_scene_initial_response(current_state["intent"])

        # 更新されたスロットの確認応答
        if current_state["updated_slots"]:
            updated_slots = {
                slot: current_state["state"][slot]
                for slot in current_state["updated_slots"]
            }
            confirmation = self.nlg.get_implicit_confirmation(
                current_state["intent"],
                updated_slots
            )
            if confirmation:
                return confirmation

        # 対話完了時の処理
        if dialogue_status == "CONVERSATION_COMPLETE":
            return self.nlg.get_intent_response(
                current_state["intent"],
                current_state["state"],
                "COMPLETE"
            )

        # 次の質問生成
        if missing_slots := current_state["missing_slots"]:
            question = self.nlg.get_next_question(
                current_state["intent"],
                missing_slots[0]
            )
            if question:
                return question[0]

        return self.nlg.get_fallback_message("DEFAULT")

    def _format_state_display(self, state: Dict) -> str:
        """現在の状態を表示用に整形"""
        lines = [
            "現在の状態:",
            f"意図: {state['intent'] or '未特定'}",
            f"対話状態: {state['dialogue_state']}",
            "\nスロット値:"
        ]
        for slot, value in state['state'].items():
            lines.append(f"  {slot}: {value or '未入力'}")
        
        if state['missing_slots']:
            lines.append("\n未入力のスロット:")
            for slot in state['missing_slots']:
                lines.append(f"  - {slot}")
        
        if state['updated_slots']:
            lines.append("\n更新されたスロット:")
            for slot in state['updated_slots']:
                lines.append(f"  - {slot}")
        
        return "\n".join(lines)

def create_interface():
    dialogue_system = DialogueSystem()

    def process_message(message: str, history: List[Tuple[str, str]]):
        return dialogue_system.process_message(message, history)

    def reset_chat():
        dialogue_system.reset_dialogue()
        return None, None

    with gr.Blocks() as demo:
        gr.Markdown("# レストラン予約対話システム")
        
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot()
                msg = gr.Textbox(
                    show_label=False,
                    placeholder="メッセージを入力してください"
                )
                
            with gr.Column(scale=1):
                state_display = gr.Markdown()

        with gr.Row():
            clear = gr.Button("対話をリセット")

        msg.submit(process_message, [msg, chatbot], [msg, chatbot, state_display])
        clear.click(reset_chat, None, [chatbot, state_display])

    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch()