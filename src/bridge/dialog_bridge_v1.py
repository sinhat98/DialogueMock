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

BARGE_IN_UTTERANCE = [
    "DATE_1",
    "TIME_1",
    "N_PERSON_1",
    "NAME_1",
]


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
        self.stack_transcription = ""
        self.bot_speak = False
        
        self.is_final = False
        self.slots = self.streaming_nlu.slot_states
        
    def set_stream_sid(self, stream_sid):
        self.stream_sid = stream_sid
        
    def nlu_step(self, text):
        if text != "":
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
    
    async def handle_barge_in(self, ws, firestore_client):
        # botの音声を停止
        if self.bot_speak:
            logger.info("Barge-in was detected")
            event_data = {
                "message": "BARGE_IN",
                "sender_type": "customer",
                "entity": {},
                "is_ivr": False,
                "created_at": firestore_client.get_timestamp(),
            }
            firestore_client.add_conversation_event(event_data)
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
    def set_barge_in(self):
        self.allow_barge_in = True
        self.reset_turn_taking_status()
        logger.info("set allow_barge_in to True")

    async def send_tts(self, ws, tts_bridge, firestore_client):
        queue_size = tts_bridge.audio_queue.qsize()
        # logger.info(f"TTS queue size: {queue_size}")

        try:
            if queue_size > 0 and not self.bot_speak:
                txt, _out = tts_bridge.audio_queue.get()
                if txt in BARGE_IN_UTTERANCE or self.awaiting_final_confirmation:
                    self.set_barge_in()
                logger.info(f"Send Bot: {txt}")
                firestore_client.add_conversation_event(
                    {"message": txt,
                     "sender_type": "bot",
                     "entity": {},
                     "is_ivr": False,
                     "created_at": firestore_client.get_timestamp(),
                    }
                )
                
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
        


    def get_respose(self, transcription: str, nlu_output: dict):
        response_list = []
        # ユーザーの最終確認応答をチェック
        if self.awaiting_final_confirmation and YES in transcription:
            response = self.nlg.get_confirm_response(self.dst.state_stack[-1][0], YES)  # 最終確認応答を生成
            self.awaiting_final_confirmation = False
            self.waiting_for_confirmation = False
            self.is_final = True
        else:
            nlu_output = {"action_type": "新規予約", "slot": nlu_output} if not self.dst.state_stack else {"action_type": "", "slot": nlu_output}
            # DST状態更新
            self.dst.update_state(nlu_output)

            # 暗黙確認応答生成
            # implicit_confirmation = self.nlg.get_confirmation_response(self.dst.state_stack[-1], prev_state)
            response = self.nlg.get_response(self.dst.state_stack[-1])
            if isinstance(response, tuple):
                response = response[1] # DATA_1など
            # if implicit_confirmation:
            #     response_list.append(implicit_confirmation)

            # 状態確認して全てのスロットが埋まっているかチェック
            if self.dst.is_complete() and not self.waiting_for_confirmation:
                response += "ご予約を確定してもよろしいでしょうか？"
                self.awaiting_final_confirmation = True
        response_list.append(response)
        
        return response_list

    async def __call__(self, ws, asr_bridge, llm_bridge, tts_bridge, **kwargs):
        firestore_client = kwargs.get("firestore_client")
        llm_bridge_for_slot_filling = kwargs.get("llm_bridge_for_slot_filling")
        if self.stream_sid is None:
            raise ValueError("stream_sid is None")

        asr_bridge.set_stability_threshold(0.85)
        turn_taking_status = self.turn_taking(asr_bridge)

        resp = []
        asr_done = False
        
        if turn_taking_status == TurnTakingStatus.END_OF_TURN:
            transcription = asr_bridge.get_transcription()
            

            if self.bot_speak:
                transcription = ""
                logger.info("Transcription reset because of bot_speak")
                asr_bridge.reset()

            llm_slot_filling_resp = None
            if transcription != "":
                logger.info(f"Add request to llm bridge for slot filling: {transcription}")
                llm_bridge_for_slot_filling.add_request(transcription)
                # tts_bridge.add_response("FILLER_LLM")
                # await self.send_tts(ws, tts_bridge, firestore_client)
                while llm_slot_filling_resp is None:
                    llm_slot_filling_resp = llm_bridge_for_slot_filling.get_response()
                self.slots = json.loads(llm_slot_filling_resp)
                logger.info(f"Slots: {self.slots}")
                self.bot_speak = False
            
            if not self.wait_for_llm and self.is_no_slots and transcription != "" and (not YES in transcription or NO in transcription):
                logger.info("FAQ response")
                llm_bridge.add_request(transcription)
                tts_bridge.add_response("FILLER")
                self.wait_for_llm = True
                await self.send_tts(ws, tts_bridge, firestore_client)
        
            if self.bot_speak:
                resp = []
            elif self.wait_for_llm:
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

                # if llm_bridge.output_queue.qsize() > 0:
                    # llm_resp = llm_bridge.output_queue.get()
                    # resp = [llm_resp]
                    # self.wait_for_llm = False
            else:
                if self.is_no_slots and not self.awaiting_final_confirmation:
                    resp = ["APLOGIZE"]
                else:
                    resp = self.get_respose(transcription, self.slots)
                    
            if resp == ["APLOGIZE"] or resp == [""]:
                resp.extend(self.get_respose(transcription, self.slots))

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
        if self.allow_barge_in and asr_bridge.get_transcription() != "":
            await self.handle_barge_in(ws, firestore_client)
        out = {
            "asr_done": asr_done,
        }
        return out