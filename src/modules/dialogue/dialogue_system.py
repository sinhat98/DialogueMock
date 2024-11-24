from src.utils import get_custom_logger
from src.modules.dialogue.dst import RuleDST
from src.modules.dialogue.nlg import TemplateNLG
from src.modules.nlu.streaming_nlu import StreamingNLUModule
from src.modules.nlu.llm_call import call_llm
from src.modules.nlu.prompt import get_system_prompt_for_intent_classification, system_prompt_for_faq
from src.modules.dialogue.utils import (
    templates,
    conversation_flow,
    tts_label2text,
    RoutingResult,
    DialogueState,
    Intent,
    Slot,
)

logger = get_custom_logger(__name__)


class DialogueSystem:
    def __init__(self):
        """対話システムの初期化"""
        self.initial_message = self._convert_label_to_text(conversation_flow["initial_message"]())
        self.scene_intents = conversation_flow["scene_intents"]
        
        self.dst = RuleDST(templates)
        self.nlg = TemplateNLG(templates)
        
        # NLUモジュールの初期化
        self.rule_based_sf = StreamingNLUModule(
            slot_keys=list(templates["initial_state"].keys())
        )
        
        self.reset_dialogue()
        
    @property
    def dialogue_state(self):
        return self.dst.dialogue_state
    
    @property
    def current_intent(self):
        return self.dst.current_intent
    
    @property
    def current_state(self):
        return self.dst.get_current_state()
        
    
    def reset_dialogue(self):
        """対話状態のリセット"""
        self.dst.reset()
        self.rule_based_sf.init_state()
        self.initial_message = self._convert_label_to_text(conversation_flow["initial_message"]())
        logger.info("Dialogue state reset")

    def _need_intent_classification(self, message: str, current_state: dict) -> bool:
        """intentの分類が必要かどうかを判断"""
        is_needed = False
        current_intent = current_state["intent"]
        dialogue_state = current_state["dialogue_state"]
        logger.info(f"[need_intent_classificaiton] current dialog state: {dialogue_state} scene_intents: {list(self.scene_intents.keys())}")

        if not current_intent:
            is_needed = True
            
        if dialogue_state in self.scene_intents:
            is_needed = True

        return is_needed

    def _get_reservation_state(self) -> dict:
        from datetime import datetime, timedelta
        mock_slots = {
            Slot.DATE: (datetime.today() + timedelta(days=7)).strftime("%m/%d"),
            Slot.TIME: "19:00",
            Slot.N_PERSON: 2,
        }
        return mock_slots

    def process_message(
        self, 
        user_message: str, 
    ) -> list[str]:
        responses = []
        
        current_state = self.dst.get_current_state()
        logger.debug(f"Current state: {current_state}")
        
        # NLU処理
        self.rule_based_sf.process(user_message)

        if self._need_intent_classification(user_message, current_state):
            if current_state["dialogue_state"] == DialogueState.WAITING_CONFIRMATION:
                intents = self.scene_intents.get(current_state["dialogue_state"], {}).get(current_state["intent"], {})
            else:
                intents = self.scene_intents.get(current_state["dialogue_state"], {})
            logger.debug(f"Intents for classification: {intents}")
            nlu_result = self._classify_intent(
                intents,
                user_message
            )
            if nlu_result:
                nlu_result["slot"] = self.rule_based_sf.slot_states
            else:
                nlu_result = {
                    "intent": current_state["intent"],
                    "slot": self.rule_based_sf.slot_states
                }
        else:
            nlu_result = {
                "intent": current_state["intent"],
                "slot": self.rule_based_sf.slot_states
            }

        # 状態を更新
        previous_state = current_state.copy()
        self.dst.update_state(nlu_result)
        updated_state = self.dst.get_current_state()
        logger.debug(f"Updated dialogue state: {updated_state['dialogue_state']}")
        
        logger.debug(f"Updated state: {updated_state}")
        
        if updated_state["dialogue_state"] == DialogueState.FALLBACK:
            response = [self.nlg.get_fallback_message("DEFAULT")]
            self.dst.set_dialogue_state(DialogueState.WAITING_CONFIRMATION)
        else:
            
            # 応答を生成
            if updated_state["dialogue_state"] == DialogueState.SLOTS_FILLED or \
                (previous_state["dialogue_state"] == DialogueState.START and self.dst.is_slots_filled):
                update_slots_dict = {
                    slot: updated_state["state"][slot]
                    for slot in updated_state.get("updated_slots", [])
                }
                implicit_confirmation = self.nlg.get_implicit_confirmation(
                    updated_state["intent"],
                    update_slots_dict
                )
                logger.debug(f"Implicit confirmation: {implicit_confirmation}")
                if (updated_state["intent"] in [Intent.CANCEL_RESERVATION, Intent.CONFIRM_RESERVATION]):
                    # mockのスロット情報で埋める
                    filled_slots = updated_state["state"]
                    mock_slots = self._get_reservation_state()
                    for slot, value in filled_slots.items():
                        mock_value = mock_slots.get(slot)
                        if value == "":
                            filled_slots[slot] = mock_value
                    logger.debug(f"Mock slots: {mock_slots} and filled slots: {filled_slots}")
                    updated_state["state"] = filled_slots

                # 予約確認の場合、名前スロットが埋まった場合にCOMPLETEに遷移
                if updated_state["intent"] == Intent.CONFIRM_RESERVATION:
                    self.dst.set_dialogue_state(DialogueState.COMPLETE)

                    response = [implicit_confirmation] if implicit_confirmation else []
                    response += [self.nlg.get_intent_response(
                        updated_state["intent"],
                        updated_state["state"],
                        self.dst.dialogue_state,
                    )]
                else:
                    response = self._generate_slots_filled_response(updated_state)
                    self.dst.set_dialogue_state(DialogueState.WAITING_CONFIRMATION)

            elif updated_state["dialogue_state"] == DialogueState.CORRECTION:
                response = self._generate_correction_response(updated_state, current_state, user_message)
            else:
                response = self._generate_response(updated_state, previous_state, user_message)
            
        responses.extend(response)
        responses = [self._convert_label_to_text(response) for response in responses]
        
        return responses

    def _generate_slots_filled_response(self, state: dict) -> list[str]:
        implicit_confirmation = self.nlg.get_implicit_confirmation(
            state["intent"],
            {slot: state["state"][slot] for slot in state.get("updated_slots", [])}
        )
        confirmation_prompt = self.nlg.get_confirmation_prompt(
            state["intent"],
            state["state"]
        )
        if implicit_confirmation:
            return [implicit_confirmation, confirmation_prompt]
        else:
            return [confirmation_prompt]
        
    def _generate_correction_response(self, updated_state: dict, current_state: dict, user_message: str) -> list[str]:
        updated_slots = updated_state["updated_slots"]
        if updated_slots:
            correction_slot = updated_slots[0]
            self.dst.set_correction_slot(correction_slot)
            confirmation = self.nlg.get_implicit_confirmation(
                current_state["intent"],
                self.dst.get_updated_slots_dict()
            )
            final_prompt = self.nlg.get_confirmation_prompt(
                updated_state["intent"],
                updated_state["state"]
            )
            # 訂正完了した場合
            self.dst.set_dialogue_state(DialogueState.WAITING_CONFIRMATION)
            return [confirmation, final_prompt] if confirmation else [final_prompt]
        else:
            correction_slot = self.rule_based_sf.hearing_item
            if correction_slot == "":
                # 訂正スロットを特定できない場合
                return [self.nlg.get_final_confrmation_response(
                    updated_state["intent"],
                    RoutingResult.CHANGE
                )]
            else:
                # 訂正スロットを特定できた場合
                self.dst.set_correction_slot(correction_slot)
                return [self.nlg.get_correction_prompt(
                    updated_state["intent"],
                    self.dst.correction_slot
                )]

    def _generate_next_question(self, current_state: dict) -> str:
        if missing_slots := current_state.get("missing_slots", []):
            logger.debug(f"Missing slots: {missing_slots}")
            if question := self.nlg.get_next_question(
                current_state["intent"],
                missing_slots[0]
            ):
                logger.debug(f"Generated next question: {question}")
                return question
        return ""
        

    def _generate_response(
        self, 
        current_state: dict,
        previous_state: dict,
        user_message: str,
    ) -> list[str]:
        
        """状態に応じた応答を生成"""
        logger.debug(f"[response_generation] Generating response for dialogue state: {current_state['dialogue_state']}")

        next_question = self._generate_next_question(current_state)
        
        # 店舗質問の処理
        if current_state["intent"] == Intent.ASK_ABOUT_STORE:
            if current_state["dialogue_state"] == DialogueState.CANCELLED:
                self.dst.set_dialogue_state(DialogueState.COMPLETE)
                return [self.nlg.get_final_confrmation_response(current_state["intent"], RoutingResult.CANCEL)]
            elif current_state["dialogue_state"] == DialogueState.COMPLETE: # 本当はCOMPLETEではない
                return [self.nlg.get_scene_complete_response(current_state["intent"])]
            elif current_state["dialogue_state"] == DialogueState.CONTINUE:
                self.dst.set_dialogue_state(DialogueState.WAITING_CONFIRMATION)
                return [self.nlg.get_intent_response(
                    current_state["intent"],
                    current_state["state"],
                    current_state["dialogue_state"]
                )]
            else:
                responses:list[str] = self._handle_store_questions(current_state, user_message)
                self.dst.set_dialogue_state(DialogueState.WAITING_CONFIRMATION)
                return responses
                # return self._handle_store_questions(current_state, user_message)

        # エラー状態の処理
        if current_state["dialogue_state"] == DialogueState.ERROR:
            return self.nlg.get_fallback_message(RoutingResult.INVALID_INTENT)

        # 新しいintentの場合
        if current_state["dialogue_state"] == DialogueState.INTENT_CHANGED:
            # slotに更新がある場合スロットの暗黙の確認を行う
            if updated_slots := current_state.get("updated_slots"):
                updated_slots_dict = {
                    slot: current_state["state"][slot]
                    for slot in updated_slots
                }
                if confirmation := self.nlg.get_implicit_confirmation(
                    current_state["intent"],
                    updated_slots_dict
                ):
                    return [confirmation, next_question]
            logger.debug("next question: %s", next_question)
            if current_state["intent"] == Intent.CHANGE_RESERVATION:
                self.dst.set_dialogue_state(DialogueState.COMPLETE)
            return [self.nlg.get_scene_initial_response(current_state["intent"]), next_question]

        # 全スロットが埋まった場合
        if current_state["dialogue_state"] == DialogueState.SLOTS_FILLED:
            updated_slots = {
                slot: current_state["state"][slot]
                for slot in current_state.get("updated_slots", [])
            }
            confirmation = self.nlg.get_implicit_confirmation(
                current_state["intent"],
                updated_slots
            )
            
            final_prompt = self.nlg.get_confirmation_prompt(
                current_state["intent"],
                current_state["state"]
            )
            
            if confirmation and final_prompt:
                return [confirmation, final_prompt]
            elif final_prompt:
                return [final_prompt]
            
        
        # 修正入力中の処理
        if current_state["dialogue_state"] == DialogueState.CORRECTION:
            return [self.nlg.get_correction_prompt(
                current_state["intent"],
                self.dst.correction_slot
            )]

        # 修正完了時の処理
        if current_state["dialogue_state"] in [DialogueState.CORRECTION, DialogueState.WAITING_CONFIRMATION]:
            updated_slots = {
                slot: current_state["state"][slot]
                for slot in current_state["updated_slots"]
            }
            implicit_confirmation = self.nlg.get_implicit_confirmation(
                current_state["intent"],
                updated_slots
            )
            final_confirmation = self.nlg.get_confirmation_prompt(
                current_state["intent"],
                current_state["state"]
            )
            if implicit_confirmation:
                return [implicit_confirmation, final_confirmation]
            else:
                return [final_confirmation]
            
            
        # 対話完了時の処理
        if current_state["dialogue_state"] == DialogueState.COMPLETE:
            return [self.nlg.get_scene_complete_response(current_state["intent"])]
        
        # キャンセル時の処理
        if current_state["dialogue_state"] == DialogueState.CANCELLED:
            logger.debug(f"{current_state['intent']}")
            
            responses = [self.nlg.get_final_confrmation_response(current_state["intent"], RoutingResult.CANCEL)]

            if current_state["intent"] == Intent.CANCEL_RESERVATION or \
                current_state["intent"] == Intent.NEW_RESERVATION:
                self.dst.set_dialogue_state(DialogueState.COMPLETE)

            if current_state["intent"] == Intent.CONFIRM_RESERVATION:
                self.dst.set_dialogue_state(DialogueState.WAITING_CONFIRMATION)
                self.dst.update_state({"intent": Intent.NEW_RESERVATION, "slot": current_state["state"]})
                logger.debug(f"Updated state: {self.dst.get_current_state()}")
                responses += [self._generate_next_question(self.dst.get_current_state())]
        
            return responses
               
        # 通常の対話進行処理
        # スロットが更新された場合の暗黙の確認
        if updated_slots := current_state.get("updated_slots"):
            updated_slots_dict = {
                slot: current_state["state"][slot]
                for slot in updated_slots
            }
            if confirmation := self.nlg.get_implicit_confirmation(
                current_state["intent"],
                updated_slots_dict
            ):
                return [confirmation, next_question]
            
        if current_state["dialogue_state"] == DialogueState.CONTINUE:
            return [next_question]

        return [self.nlg.get_fallback_message("DEFAULT")]

    def _handle_store_questions(self, current_state: dict, user_message: str) -> list[str]:
        llm_response = call_llm(system_prompt_for_faq, user_message, json_format=False)
        if llm_response:
            return [llm_response, self.nlg.get_confirmation_prompt(current_state["intent"], current_state["state"])]
        return [self.nlg.get_intent_response(
            current_state["intent"],
            current_state["state"],
            "NOT_FOUND"
        )]
        
    def _need_intent_classification(self, message: str, current_state: dict) -> bool:
        """
        intentの分類が必要かどうかを判断
        """
        is_needed = False
        current_intent = current_state["intent"]
        dialogue_state = current_state["dialogue_state"]

        if not current_intent:
            is_needed = True
            
        if dialogue_state in self.scene_intents:
            is_needed = True

        return is_needed

    def _classify_intent(self, intents: dict, message: str) -> dict | None:
        """
        LLMを使用してintentを分類
        スロット情報は空のディクショナリを返す
        """
        assert type(intents) == dict, f"Intents must be a dictionary, but got {type(intents)}"
        system_prompt = get_system_prompt_for_intent_classification(intents) 
        try:
            llm_output = eval(call_llm(system_prompt, message))
            logger.info(f"LLM output: {llm_output}")
            intent = llm_output.get("intent", "")
            nlu_result = {
                "intent": intent,
                "slot": {}  # スロット情報は空のディクショナリを返す
            }
            logger.info(f"LLM intent classification result: {nlu_result}")
            return nlu_result
        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            return None
    
    def _convert_label_to_text(self, label_or_text: str) -> str:
        return tts_label2text.get(label_or_text, label_or_text)
    
    def is_complete(self):
        return self.dialogue_state == DialogueState.COMPLETE


    @property
    def awaiting_final_confirmation(self):
        return self.dst.dialogue_state == DialogueState.WAITING_CONFIRMATION