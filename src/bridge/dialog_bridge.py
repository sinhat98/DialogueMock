from src.modules import (
    RuleDST,
    TemplateNLG,
    templates,
    StreamingNLUModule,
    VolumeBasedVADModel,
)
from src.modules.dialogue.utils.template import tts_label2text
from src.utils import get_custom_logger
from copy import deepcopy
import json
import asyncio
from enum import IntEnum

from abc import ABC, abstractmethod


logger = get_custom_logger(__name__)

YES = "はい"
NO = "いいえ"

SAMPLE_RATE = 8000
VOLUME_THRESHOLD = 1000
FAST_SPEECH_END_THRESHOLD = 20
SLOW_SPEECH_END_THRESHOLD = 80

NORMAL_RESPONSE = [
    "DATE_1",
    "TIME_1",
    "N_PERSON_1",
    "NAME_1",
]

BARGE_IN_THRESHOLD = 20
BARGE_IN_UTTERANCE = NORMAL_RESPONSE


class TurnTakingStatus(IntEnum):
    END_OF_TURN = 0
    BACKCHANNEL = 1
    CONTINUE = 2

class DialogBridge(ABC):
    def __init__(self, default_state: dict = {}):
        self.stream_sid = None
        self.dst = RuleDST(templates, default_state)
        self.nlg = TemplateNLG(templates)
        self.streaming_nlu = StreamingNLUModule(slot_keys=self.dst.initial_state.keys())
        self.streaming_vad = VolumeBasedVADModel(sample_rate=SAMPLE_RATE, volume_threshold=VOLUME_THRESHOLD, fast_speech_end_threshold=FAST_SPEECH_END_THRESHOLD, slow_speech_end_threshold=SLOW_SPEECH_END_THRESHOLD)
        
        self.waiting_for_confirmation = False
        self.awaiting_final_confirmation = False
        self.use_implied_confirmation = True
        self.is_final = False
        self.allow_barge_in = False
        self.wait_for_llm = False
        self.pre_text = ""
        self.bot_speak = False
        
        self.slots = self.dst.initial_state
        
    def set_stream_sid(self, stream_sid):
        self.stream_sid = stream_sid
        
    def nlu_step(self, text):
        if text != "":
            self.streaming_nlu.process(text)
        
    def vad_step(self, chunk):
        if chunk != "/w==":
            self.streaming_vad.update_vad_status(chunk)
    
    @abstractmethod
    def turn_taking(self, *args) -> TurnTakingStatus:
        raise NotImplementedError
        
    def reset_turn_taking_status(self):
        self.streaming_nlu.init_state()
        self.streaming_vad.init_state()
        self.pre_text = ""
        logger.info("Reset turn taking status")

    @property
    def is_slot_filled(self):
        return self.streaming_nlu.is_slot_filled
    
    @property
    def is_no_slots(self):
        return not any(bool(v) for v in self.slots.values())
    
    @property
    def got_entity(self):
        return self.streaming_nlu.got_entity

    @property
    def is_terminal_form_detected(self):
        return self.streaming_nlu.status.got_terminal_forms

    @property
    def is_fast_speech_end(self):
        return self.streaming_vad.fast_speech_end_flag

    @property
    def is_slow_speech_end(self):
        return self.streaming_vad.slow_speech_end_flag
    
    def get_bargein_flag(self) -> bool:
        # 基本的には、バージインを許可しない
        return False
        

    def get_respose(self, transcription: str, slot_states: dict):
        response_list = []
        # ユーザーの最終確認応答をチェック
        if self.awaiting_final_confirmation and YES in transcription:
            response = self.nlg.get_confirm_response(self.dst.state_stack[-1][0], YES)  # 最終確認応答を生成
            self.awaiting_final_confirmation = False
            self.waiting_for_confirmation = False
        else:
            nlu_output = {"action_type": "新規予約", "slot": slot_states} if not self.dst.state_stack else {"action_type": "", "slot": slot_states}
            # DST状態更新
            prev_state = deepcopy(self.dst.state_stack[-1][1]) if self.dst.state_stack else self.dst.initial_state
            self.dst.update_state(nlu_output)

            # 暗黙確認応答生成
            if self.use_implied_confirmation:
                implicit_confirmation = self.nlg.get_confirmation_response(self.dst.state_stack[-1], prev_state)            
                if implicit_confirmation:
                    response_list.append(implicit_confirmation)
            
            response = self.nlg.get_response(self.dst.state_stack[-1])
            if isinstance(response, tuple):
                response = response[1] # DATA_1など

            # 状態確認して全てのスロットが埋まっているかチェック
            if self.dst.is_complete() and not self.waiting_for_confirmation:
                response += "ご予約を確定してもよろしいでしょうか？はい、または、いいえでお答えください"
                self.awaiting_final_confirmation = True
        response_list.append(response)
        
        return response_list

    
    async def handle_barge_in(self, ws, firestore_client, *args):
        # botの音声を停止
        if self.bot_speak:
            logger.info("Barge-in was detected")
            self.store_event(firestore_client, "BARGE_IN", "customer")
            self.reset_turn_taking_status()
            self.allow_barge_in = False
            self.bot_speak = False
            await ws.send_text(
                json.dumps(
                    {
                        "event": "clear",
                        "streamSid": self.stream_sid,
                    }
                )
            )

    def set_barge_in(self, text):
        if text in BARGE_IN_UTTERANCE or self.awaiting_final_confirmation:    
            self.allow_barge_in = True
            self.reset_turn_taking_status()
            logger.info("set allow_barge_in to True")
            
    def store_event(self, firestore_client, message, sender_type):
        event_data = {
            "message": message,
            "sender_type": sender_type,
            "entity": {},
            "is_ivr": False,
            "created_at": firestore_client.get_timestamp(),
        }
        firestore_client.add_conversation_event(event_data)
    
    async def send_tts(self, ws, tts_bridge, firestore_client):
        queue_size = tts_bridge.audio_queue.qsize()
        # logger.info(f"TTS queue size: {queue_size}")

        try:
            if queue_size > 0 and not self.bot_speak:
                txt, _out = tts_bridge.audio_queue.get()
                self.set_barge_in(txt)
                txt = tts_label2text.get(txt, txt)
                logger.info(f"Send Bot: {txt}")
                self.store_event(firestore_client, txt, "bot")
                # 非同期タスクのタイムアウト設定
                await asyncio.wait_for(ws.send_text(_out), timeout=2)  
                await asyncio.wait_for(ws.send_text(
                    json.dumps({
                        "event": "mark",
                        "streamSid": self.stream_sid,
                        "mark": {"name": "continue"}
                    })), timeout=2)
                self.bot_speak = True

        except asyncio.TimeoutError:
            pass
        
        if self.dst.is_complete() and not self.waiting_for_confirmation and not self.awaiting_final_confirmation:
            self.is_final = True
    
    @abstractmethod
    async def update_slots(self, transcription: str, *args):
        raise NotImplementedError
        

    async def __call__(self, ws, asr_bridge, llm_bridge, tts_bridge, **kwargs):
        firestore_client = kwargs.get("firestore_client")
        llm_bridge_for_slot_filling = kwargs.get("llm_bridge_for_slot_filling")
        
        if self.stream_sid is None:
            raise ValueError("stream_sid is None")
        
        # ターンテイキングステータスの取得(各DialogBridgeの実装によって異なる)
        turn_taking_status = self.turn_taking(asr_bridge)   
        
        transcription = asr_bridge.get_transcription()
        self.pre_text = transcription

        resp = []
        asr_done = False
        
        if turn_taking_status == TurnTakingStatus.END_OF_TURN:
            logger.info("End of turn was detected")
            if self.bot_speak:
                transcription = ""
                logger.info("Transcription reset because of bot_speak")
                asr_bridge.reset()

            if transcription != "":
                self.store_event(firestore_client, transcription, "customer")
                # update slot states (各DialogBridgeの実装によって異なる)
                await self.update_slots(transcription, llm_bridge_for_slot_filling, tts_bridge, firestore_client, ws)
                logger.info(f"Slots: {self.slots}")
                self.bot_speak = False
                
                if not self.wait_for_llm and self.is_no_slots and (not YES in transcription or NO in transcription):
                    logger.info("FAQ response")
                    llm_bridge.add_request(transcription)
                    tts_bridge.add_response("FILLER")
                    await self.send_tts(ws, tts_bridge, firestore_client)
                    self.wait_for_llm = True
            
            if self.wait_for_llm:
                llm_resp = None
                while llm_resp is None:
                    llm_resp = llm_bridge.get_response()
                
                llm_resp = str(llm_resp)

                if llm_resp == "None" or llm_resp.strip() == "":
                    # llmの応答が空の場合は、デフォルトの応答を返す
                    llm_resp = "APLOGIZE"
                    
                logger.info(f"LLM response: {llm_resp}")
                resp = [llm_resp]
    
                self.wait_for_llm = False
                resp.extend(self.get_respose(transcription, self.slots))
                logger.info("Normal response")  
            elif self.bot_speak:
                """FILLER以外でbotに応答が連続しないようにbotが話している間は応答を空にする"""
                resp = []
                logger.info("make response empty because of bot_speak")
            elif self.is_no_slots and not self.awaiting_final_confirmation:
                resp = ["APLOGIZE"]
                logger.info("Apology response")
                resp.extend(self.get_respose(transcription, self.slots))
                logger.info("Normal response")
            else:
                resp = self.get_respose(transcription, self.slots)
                logger.info("Normal response")

            for r in resp:
                logger.info(f"Add request to tts bridge {r}")
                tts_bridge.add_response(r)

            asr_done = True
            logger.info("ASR done")
            self.reset_turn_taking_status()
            
        if self.is_final:
            await ws.send_text(
                json.dumps(
                    {
                        "event": "mark",
                        "streamSid": self.stream_sid,
                        "mark": {"name": "finish"}
                    }
                )
            )

        # 3. TTSを送信
        await self.send_tts(ws, tts_bridge, firestore_client)
        if self.get_bargein_flag():
            await self.handle_barge_in(ws, firestore_client)
        out = {
            "asr_done": asr_done,
        }
        return out
 
 
class DialogBridgeWithLLMSF(DialogBridge):
    def __init__(self, default_state: dict = {}):
        super().__init__(default_state=default_state)
        self.use_implied_confirmation = False
    
    def turn_taking(self, *args):
        asr_bridge = args[0]
        asr_bridge.set_stability_threshold(0.85)
        
        if asr_bridge._ended:
            return TurnTakingStatus.END_OF_TURN
        else:
            return TurnTakingStatus.CONTINUE
    
    async def update_slots(self, transcription: str, *args):
        llm_bridge_for_slot_filling = args[0]
        tts_bridge = args[1]
        firestore_client = args[2]
        ws = args[3]
        llm_slot_filling_resp = None
        logger.info(f"Add request to llm bridge for slot filling: {transcription}")
        llm_bridge_for_slot_filling.add_request(transcription)
        tts_bridge.add_response("LLM_FILLER")
        await self.send_tts(ws, tts_bridge, firestore_client)
        while llm_slot_filling_resp is None:
            llm_slot_filling_resp = llm_bridge_for_slot_filling.get_response()
        self.slots = json.loads(llm_slot_filling_resp)
        
class DialogBridgeWithminiLLMSF(DialogBridge):
    def __init__(self, default_state: dict = {}):
        super().__init__(default_state=default_state)
        self.use_implied_confirmation = True
    
    def turn_taking(self, *args):
        asr_bridge = args[0]
        asr_bridge.set_stability_threshold(0.85)
        
        if asr_bridge._ended:
            return TurnTakingStatus.END_OF_TURN
        else:
            return TurnTakingStatus.CONTINUE
    
    async def update_slots(self, transcription: str, *args):
        llm_bridge_for_slot_filling = args[0]
        tts_bridge = args[1]
        firestore_client = args[2]
        ws = args[3]
        llm_slot_filling_resp = None
        logger.info(f"Add request to llm bridge for slot filling: {transcription}")
        llm_bridge_for_slot_filling.add_request(transcription)
        # tts_bridge.add_response("LLM_FILLER")
        # await self.send_tts(ws, tts_bridge, firestore_client)
        while llm_slot_filling_resp is None:
            llm_slot_filling_resp = llm_bridge_for_slot_filling.get_response()
        self.slots = json.loads(llm_slot_filling_resp)
        
class DialogBridgeWithLLMSFAndVolumeBasedEoT(DialogBridge):
    def __init__(self, default_state: dict = {}):
        super().__init__(default_state=default_state)
        self.use_implied_confirmation = False
        
    def get_bargein_flag(self) -> bool:
        return self.allow_barge_in and len(self.streaming_vad.speech_chunks) > BARGE_IN_THRESHOLD
    
    def turn_taking(self, *args):
        logger.debug(
            (f"is_got_entity: {self.got_entity} " 
             f"is_slot_filled: {self.is_slot_filled} "
             f"is_terminal: {self.is_terminal_form_detected} "
             f"is_fast_speech_end: {self.is_fast_speech_end} "
             f"is_slow_speech_end: {self.is_slow_speech_end} "
             f"pre_text: {self.pre_text}")
            )

        if ((self.is_terminal_form_detected and self.is_fast_speech_end)
            or (self.is_slot_filled and self.is_fast_speech_end)
            or (self.is_slow_speech_end and self.pre_text != "")):
            return TurnTakingStatus.END_OF_TURN
        elif self.got_entity and self.is_fast_speech_end:
            return TurnTakingStatus.BACKCHANNEL
        else:
            return TurnTakingStatus.CONTINUE
    
    async def update_slots(self, transcription: str, *args):
        llm_bridge_for_slot_filling = args[0]
        tts_bridge = args[1]
        firestore_client = args[2]
        ws = args[3]
        llm_slot_filling_resp = None
        logger.info(f"Add request to llm bridge for slot filling: {transcription}")
        llm_bridge_for_slot_filling.add_request(transcription)
        tts_bridge.add_response("LLM_FILLER")
        await self.send_tts(ws, tts_bridge, firestore_client)
        while llm_slot_filling_resp is None:
            llm_slot_filling_resp = llm_bridge_for_slot_filling.get_response()
        self.slots = json.loads(llm_slot_filling_resp)
        
class DialogBridgeWithFastSF(DialogBridge):
    def __init__(self, default_state: dict = {}):
        super().__init__(default_state=default_state)
        
    def turn_taking(self, *args):
        asr_bridge = args[0]
        asr_bridge.set_stability_threshold(0.85)
        
        if asr_bridge._ended:
            return TurnTakingStatus.END_OF_TURN
        else:
            return TurnTakingStatus.CONTINUE
    
    async def update_slots(self, transcription: str, *args):
        self.nlu_step(transcription)
        self.slots = self.streaming_nlu.slot_states
        

        

class DialogBridgeWithFastSFAndVolumeBasedEoT(DialogBridge):
    def __init__(self, default_state: dict = {}):
        super().__init__(default_state=default_state)
        
    def get_bargein_flag(self) -> bool:
        return self.allow_barge_in and len(self.streaming_vad.speech_chunks) > BARGE_IN_THRESHOLD
    
    def turn_taking(self, *args):
        logger.debug(
            (f"is_got_entity: {self.got_entity} " 
             f"is_slot_filled: {self.is_slot_filled} "
             f"is_terminal: {self.is_terminal_form_detected} "
             f"is_fast_speech_end: {self.is_fast_speech_end} "
             f"is_slow_speech_end: {self.is_slow_speech_end} "
             f"pre_text: {self.pre_text}")
            )

        if ((self.is_terminal_form_detected and self.is_fast_speech_end)
            or (self.is_slot_filled and self.is_fast_speech_end)
            or (self.is_slow_speech_end and self.pre_text != "")):
            return TurnTakingStatus.END_OF_TURN
        elif self.got_entity and self.is_fast_speech_end:
            return TurnTakingStatus.BACKCHANNEL
        else:
            return TurnTakingStatus.CONTINUE
    
    async def update_slots(self, transcription: str, *args):
        self.nlu_step(transcription)
        self.slots = self.streaming_nlu.slot_states
        