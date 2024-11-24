from src.modules import (
    VolumeBasedVADModel,
)
from src.modules.dialogue.utils.template import tts_text2label, tts_label2text
from src.modules.dialogue.dialogue_system import DialogueSystem
from src.utils import get_custom_logger, ulaw_decode
import json
import asyncio
from abc import abstractmethod

from src.modules.dialogue.utils.constants import VADConfig, BargeInConfig, TurnTakingStatus

logger = get_custom_logger(__name__)

class DialogBridgeWithIntentClassification:
    def __init__(self, default_state: dict = {}):
        self.stream_sid = None
        self.dialogue_system = DialogueSystem()
        self.streaming_vad = VolumeBasedVADModel(
            sample_rate=VADConfig.SAMPLE_RATE,
            volume_threshold=VADConfig.VOLUME_THRESHOLD,
            fast_speech_end_threshold=VADConfig.FAST_SPEECH_END_THRESHOLD,
            slow_speech_end_threshold=VADConfig.SLOW_SPEECH_END_THRESHOLD,
        )

        self.waiting_for_confirmation = False
        self.awaiting_final_confirmation = False
        self.is_final = False
        self.allow_barge_in = False
        self.pre_text = ""
        self.bot_speak = False

        self.slots = self.dialogue_system.current_state["state"]

    def set_stream_sid(self, stream_sid):
        self.stream_sid = stream_sid

    def vad_step(self, chunk):
        if chunk != "/w==":
            chunk = ulaw_decode(chunk)
            self.streaming_vad.update_vad_status(chunk)
            

    def turn_taking(self, *args):
        logger.debug(
            "is_fast_speech_end: %s is_slow_speech_end: %s pre_text: %s",
            self.is_fast_speech_end,
            self.is_slow_speech_end,
            self.pre_text,
        )

        if self.is_slow_speech_end and self.pre_text != "":
            return TurnTakingStatus.END_OF_TURN
        else:
            return TurnTakingStatus.CONTINUE

    def reset_turn_taking_status(self):
        self.streaming_vad.init_state()
        self.pre_text = ""
        logger.info("Reset turn taking status")


    @property
    def is_fast_speech_end(self):
        return self.streaming_vad.fast_speech_end_flag

    @property
    def is_slow_speech_end(self):
        return self.streaming_vad.slow_speech_end_flag

    def get_bargein_flag(self) -> bool:
        # 基本的には、バージインを許可しない
        return self.allow_barge_in and len(self.streaming_vad.speech_chunks) > BargeInConfig.BARGE_IN_THRESHOLD

    async def handle_barge_in(self, ws, firestore_client, conversation_logger):
        # botの音声を停止
        if self.bot_speak:
            logger.info("Barge-in was detected")
            self.store_event(firestore_client, "BARGE_IN", "customer")
            conversation_logger.add_log_entry(
                speaker="customer", message="BARGE_IN"
            )
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

    def set_bargein_flag(self, text):
        if text in BargeInConfig.BARGE_IN_UTTERANCE or self.dialogue_system.awaiting_final_confirmation:
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

    async def send_tts(self, ws, tts_bridge, firestore_client, conversation_logger):
        queue_size = tts_bridge.audio_queue.qsize()

        try:
            if queue_size > 0 and not self.bot_speak:
                txt, _out, _ = tts_bridge.audio_queue.get()
                self.set_bargein_flag(txt)
                txt = tts_label2text.get(txt, txt)
                logger.info(f"Send Bot: {txt}")
                self.store_event(firestore_client, txt, "bot")
                conversation_logger.add_log_entry(
                    speaker="bot", message=txt
                )
                # 非同期タスクのタイムアウト設定
                await asyncio.wait_for(ws.send_text(_out), timeout=2)
                await asyncio.wait_for(
                    ws.send_text(
                        json.dumps(
                            {
                                "event": "mark",
                                "streamSid": self.stream_sid,
                                "mark": {"name": "continue"},
                            }
                        )
                    ),
                    timeout=2,
                )
                self.bot_speak = True

        except asyncio.TimeoutError:
            pass

        if self.dialogue_system.is_complete() and tts_bridge.is_empty:
            self.is_final = True

    @abstractmethod
    async def update_slots(self, transcription: str, *args):
        raise NotImplementedError

    async def __call__(self, ws, asr_bridge, tts_bridge, **kwargs):
        firestore_client = kwargs.get("firestore_client")
        conversation_logger = kwargs.get("conversation_logger")

        if self.stream_sid is None:
            raise ValueError("stream_sid is None")

        # ターンテイキングステータスの取得(各DialogBridgeの実装によって異なる)
        turn_taking_status = self.turn_taking(asr_bridge)

        transcription = asr_bridge.get_transcription()
        self.pre_text = transcription

        asr_done = False
        
        responses = []

        if turn_taking_status == TurnTakingStatus.END_OF_TURN:
            logger.info("End of turn was detected")
            if self.bot_speak:
                transcription = ""
                logger.info("Transcription reset because of bot_speak")
                asr_bridge.reset()

            if transcription != "":
                self.store_event(firestore_client, transcription, "customer")
                responses.extend(self.dialogue_system.process_message(transcription))
                conversation_logger.add_log_entry(
                    speaker="customer", message=transcription, dst_state=self.dialogue_system.dst.get_current_state()
                )
                self.bot_speak = False

            for r in responses:
                logger.info("Add request to tts bridge %s", r)
                # cache音声を使うために、tts_text2labelを使ってラベルに変換
                tts_label = tts_text2label.get(r, r)
                tts_bridge.add_response(tts_label)

            asr_done = True
            logger.info("ASR done")
            self.reset_turn_taking_status()

        if self.is_final:
            await ws.send_text(
                json.dumps(
                    {
                        "event": "mark",
                        "streamSid": self.stream_sid,
                        "mark": {"name": "finish"},
                    }
                )
            )

        # 3. TTSを送信
        await self.send_tts(ws, tts_bridge, firestore_client, conversation_logger)
        if self.get_bargein_flag():
            await self.handle_barge_in(ws, firestore_client, conversation_logger)
        if asr_done:
            asr_bridge.reset()
        out = {
            "asr_done": asr_done,
        }
        return out
    
    def get_initial_message(self):
        return tts_text2label.get(self.dialogue_system.initial_message, self.dialogue_system.initial_message)

    
