from src.modules import (
    RuleDST,
    TemplateNLG,
    templates,
    StreamingNLUModule,
    VolumeBasedVADModel,
)
from src.utils import get_custom_logger
from copy import deepcopy
import json
import asyncio
from enum import IntEnum


logger = get_custom_logger(__name__)

YES = "はい"
NO = "いいえ"

SAMPLE_RATE = 8000
VOLUME_THRESHOLD = 1000
FAST_SPEECH_END_THRESHOLD = 20
SLOW_SPEECH_END_THRESHOLD = 100


class TurnTakingStatus(IntEnum):
    END_OF_TURN = 0
    BACKCHANNEL = 1
    CONTINUE = 2

class DialogBridge:
    def __init__(self, default_state: dict = {}):
        self.stream_sid = None
        self.dst = RuleDST(templates, default_state)
        self.nlg = TemplateNLG(templates)
        self.streaming_nlu = StreamingNLUModule(slot_keys=self.dst.initial_state.keys())
        self.streaming_vad = VolumeBasedVADModel(sample_rate=SAMPLE_RATE, volume_threshold=VOLUME_THRESHOLD, fast_speech_end_threshold=FAST_SPEECH_END_THRESHOLD, slow_speech_end_threshold=SLOW_SPEECH_END_THRESHOLD)
        
        self.waiting_for_confirmation = False
        self.awaiting_final_confirmation = False
        # self.allow_barge_in = False
        self.wait_for_llm = False
        self.pre_text = ""
        self.stack_transcription = ""
        self.bot_speak = False
        
    def set_stream_sid(self, stream_sid):
        self.stream_sid = stream_sid
        
    def nlu_step(self, text):
        if text != "":
            if text != self.pre_text:
                self.streaming_nlu.process(text)
        
    def vad_step(self, chunk):
        if chunk != "/w==":
            self.streaming_vad.update_vad_status(chunk)
        
    def turn_taking(self, asr_bridge):
        if asr_bridge._ended:
            return TurnTakingStatus.END_OF_TURN

    def reset_turn_taking_status(self):
        self.streaming_nlu.init_state()
        self.streaming_vad.init_state()
        self.pre_text = ""

    @property
    def is_slot_filled(self):
        return self.streaming_nlu.is_slot_filled

    @property
    def slots(self):
        return self.streaming_nlu.slot_states
    
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

    async def send_tts(self, ws, tts_bridge):
        queue_size = tts_bridge.audio_queue.qsize()
        # logger.info(f"TTS queue size: {queue_size}")

        try:
            if queue_size > 0 and not self.bot_speak:
                txt, _out = tts_bridge.audio_queue.get()
                logger.info(f"Bot: {txt}")
                
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
        
    def generate_llm_response(self, transcription, llm_bridge, tts_bridge):
        logger.info("Requesting LLM response")
        tts_bridge.add_response("FILLER")
        llm_bridge.add_request(transcription)
        self.wait_for_llm = True

    async def get_llm_response(self, llm_bridge):
        llm_resp = None
        logger.info("Waiting for LLM response")
        timeout = 5  # seconds
        interval = 0.1  # check every 0.1 seconds
        total_time = 0
        while llm_resp is None and total_time < timeout:
            llm_resp = llm_bridge.get_response()
            if llm_resp is None:
                await asyncio.sleep(interval)
                total_time += interval
        if not llm_resp:
            logger.warning("LLM response timeout or empty")
            llm_resp = "申し訳ありませんが、お手伝いできません。"
        logger.info(f"LLM response: {llm_resp}")
        self.wait_for_llm = False
        return [llm_resp]

    def handle_final_confirmation(self, transcription):
        if self.awaiting_final_confirmation:
            if YES in transcription:
                response = self.nlg.get_confirm_response(self.dst.state_stack[-1][0], YES)
                self.awaiting_final_confirmation = False
                self.waiting_for_confirmation = False
                return [response]
            elif NO in transcription:
                response = self.nlg.get_confirm_response(self.dst.state_stack[-1][0], NO)
                self.awaiting_final_confirmation = False
                self.waiting_for_confirmation = False
                # Handle negative confirmation, possibly reset state
                return [response]
            else:
                # Unclear response, ask again
                response = "申し訳ありません。もう一度確認させていただけますか？ご予約を確定してもよろしいでしょうか？"
                return [response]
        return None  # Not awaiting confirmation

    def get_response(self, transcription: str, slot_states: dict):
        # First, check for final confirmation
        confirmation_response = self.handle_final_confirmation(transcription)
        if confirmation_response is not None:
            return confirmation_response

        response_list = []

        # Prepare nlu_output for DST update
        if not self.dst.state_stack:
            nlu_output = {"action_type": "新規予約", "slot": slot_states}
        else:
            nlu_output = {"action_type": "", "slot": slot_states}

        # Update DST state
        prev_state = deepcopy(self.dst.state_stack[-1][1]) if self.dst.state_stack else self.dst.initial_state
        self.dst.update_state(nlu_output)

        # Generate implicit confirmation if any
        implicit_confirmation = self.nlg.get_confirmation_response(self.dst.state_stack[-1], prev_state)
        if implicit_confirmation:
            response_list.append(implicit_confirmation)

        # Generate response based on current state
        response = self.nlg.get_response(self.dst.state_stack[-1])
        if isinstance(response, tuple):
            response = response[1]  # Handle tuple responses

        # Check if all slots are filled and not waiting for confirmation
        if self.dst.is_complete() and not self.waiting_for_confirmation:
            response += "ご予約を確定してもよろしいでしょうか？"
            self.awaiting_final_confirmation = True

        response_list.append(response)

        return response_list

    async def __call__(self, ws, asr_bridge, llm_bridge, tts_bridge):
        if self.stream_sid is None:
            raise ValueError("stream_sid is None")

        asr_bridge.set_stability_threshold(0.85)
        turn_taking_status = self.turn_taking(asr_bridge)

        resp = []
        asr_done = False
        
        # 1. LLMの応答を待っている場合は、まず応答を取得する
        if self.wait_for_llm:
            resp = await self.get_llm_response(llm_bridge)
            for r in resp:
                if r != "":
                    logger.info(f"Bot: {r}")
                    tts_bridge.add_response(r)
            asr_done = True  # LLMの応答を得たので、ASRの処理は完了とする
            
        

        # 2. LLMの応答を待っていない場合は、通常の処理を行う
        elif turn_taking_status == TurnTakingStatus.END_OF_TURN:
            transcription = asr_bridge.get_transcription()
            

            if self.bot_speak:
                transcription = ""
                logger.info("ボットが話しているため、音声認識結果をリセットします")

            if transcription != "":
                self.streaming_nlu.process(transcription)

            slots = self.slots
            slots_filled = any(bool(v) for v in slots.values())

            if not slots_filled and transcription != "" and not self.awaiting_final_confirmation:
                # スロットが埋まっていない場合、LLMに応答をリクエスト
                self.generate_llm_response(transcription, llm_bridge, tts_bridge)
            else:
                # NLGを使用して応答を生成
                resp = self.get_response(transcription, slots)
                for r in resp:
                    if r != "":
                        logger.info(f"Bot: {r}")
                        tts_bridge.add_response(r)

            if asr_bridge.bot_speak:
                resp = []

            asr_done = True
            logger.info("ASRの処理が完了しました")
            self.reset_turn_taking_status()

        # 3. TTSを送信
        await self.send_tts(ws, tts_bridge)

        out = {
            "asr_done": asr_done,
            "bot_speak": self.bot_speak,
        }
        return out