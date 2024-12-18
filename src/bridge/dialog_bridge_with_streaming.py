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
SLOW_SPEECH_END_THRESHOLD = 80


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
        self.allow_barge_in = False
        self.wait_for_llm = False
        self.pre_text = ""
        self.bot_speak = False
        
    def set_stream_sid(self, stream_sid):
        self.stream_sid = stream_sid
        
    def nlu_step(self, text):
        if text != "":
            if text != self.pre_text:
                self.streaming_nlu.process(text)
            self.pre_text = text
        
    def vad_step(self, chunk):
        if chunk != "/w==":
            self.streaming_vad.update_vad_status(chunk)
        
    def turn_taking(self):
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

    def get_respose(self, transcription: str, nlu_output: dict):
        response_list = []
        # ユーザーの最終確認応答をチェック
        if self.awaiting_final_confirmation and YES in transcription:
            response = self.nlg.get_confirm_response(self.dst.state_stack[-1][0], YES)  # 最終確認応答を生成
            self.awaiting_final_confirmation = False
            self.waiting_for_confirmation = False
        else:
            nlu_output = {"action_type": "新規予約", "slot": nlu_output} if not self.dst.state_stack else {"action_type": "", "slot": nlu_output}
            # DST状態更新
            prev_state = deepcopy(self.dst.state_stack[-1][1]) if self.dst.state_stack else self.dst.initial_state
            self.dst.update_state(nlu_output)

            # 暗黙確認応答生成
            implicit_confirmation = self.nlg.get_confirmation_response(self.dst.state_stack[-1], prev_state)
            response = self.nlg.get_response(self.dst.state_stack[-1])
            if isinstance(response, tuple):
                response = response[1] # DATA_1など
            if implicit_confirmation:
                response_list.append(implicit_confirmation)
                self.allow_barge_in = True
                logger.info("set allow_barge_in to True")

            # 状態確認して全てのスロットが埋まっているかチェック
            if self.dst.is_complete() and not self.waiting_for_confirmation:
                response += "ご予約を確定してもよろしいでしょうか？"
                self.awaiting_final_confirmation = True
                self.allow_barge_in = True
                logger.info("set allow_barge_in to True")
        response_list.append(response)
        
        return response_list
    
    async def handle_barge_in(self, ws):
        # botの音声を停止
        if self.bot_speak:
            logger.info("Barge-in was detected")
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


    async def __call__(self, ws, asr_bridge, llm_bridge, tts_bridge):
        if self.stream_sid is None:
            raise ValueError("stream_sid is None")
       
        # if not self.allow_barge_in:
            # asr_bridge.reset()
            # logger.info(f"ASR reset {asr_bridge.transcription} {self.allow_barge_in}")
        
        transcription = asr_bridge.get_transcription()
        
        self.nlu_step(transcription)
        turn_taking_status = self.turn_taking()
        slots = self.slots
        slots_filled_status = not any(bool(v) for v in slots.values())
        
        resp = None
        asr_done = False
        
        # logger.info(
        #     (f"is_got_entity: {self.got_entity} " 
        #     f"is_slot_filled: {self.is_slot_filled} "
        #     f"is_terminal: {self.is_terminal_form_detected} "
        #     f"is_fast_speech_end: {self.is_fast_speech_end} "
        #     f"is_slow_speech_end: {self.is_slow_speech_end} "
        #     f"pre_text: {self.pre_text}")
        # )
        
        if turn_taking_status == TurnTakingStatus.END_OF_TURN:
            logger.info(
                (f"is_got_entity: {self.got_entity} " 
                f"is_slot_filled: {self.is_slot_filled} "
                f"is_terminal: {self.is_terminal_form_detected} "
                f"is_fast_speech_end: {self.is_fast_speech_end} "
                f"is_slow_speech_end: {self.is_slow_speech_end} "
                f"pre_text: {self.pre_text}")
            )
            transcription = asr_bridge.get_transcription()
            logger.info(f"End of turn detected {slots}")
            
            if self.bot_speak:
                transcription = ""
                logger.info("Transcription reset because of bot_speak")
                self.nlu_step(transcription)
                slots = self.slots
                slots_filled_status = not any(bool(v) for v in slots.values())
                asr_bridge.reset()
            
            
            
            if not self.wait_for_llm and slots_filled_status and transcription != "" and (YES not in transcription or NO in transcription):
                logger.info("FAQ response")
                llm_bridge.add_request(transcription)
                tts_bridge.add_response("FILLER")
                self.wait_for_llm = True
        
            await self.send_tts(ws, tts_bridge)
        
            if self.bot_speak:
                resp = []
            elif self.wait_for_llm:
                llm_resp = None
                while llm_resp is None:
                    llm_resp = llm_bridge.get_response()
                    

                if llm_resp is None or llm_resp.strip() == "":
                    # llmの応答が空の場合は、デフォルトの応答を返す
                    llm_resp = "APPLOGIZE"
                    
                logger.info(f"LLM response: {llm_resp}")
                resp = [llm_resp]
    
                self.wait_for_llm = False

                # if llm_bridge.output_queue.qsize() > 0:
                    # llm_resp = llm_bridge.output_queue.get()
                    # resp = [llm_resp]
                    # self.wait_for_llm = False
            else:
                if len(slots) == 0:
                    resp = ["APPLOGIZE"]
                else:
                    resp = self.get_respose(transcription, slots)

            for r in resp:
                logger.info(f"Add request to tts bridge {r}")
                tts_bridge.add_response(r)
                
            
  
            asr_done = True
            logger.info("ASR done")
            self.reset_turn_taking_status()
        
        await self.send_tts(ws, tts_bridge)
        
        if self.allow_barge_in and not slots_filled_status:
            await self.handle_barge_in(ws)


        out = {
            # "asr_done": asr_bridge.is_final,
            "asr_done": asr_done,
        }
        return out