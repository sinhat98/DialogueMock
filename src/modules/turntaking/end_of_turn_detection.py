
from src.utils import setup_custom_logger
from src.vad import VolumeBasedVADModel
from src.nlu import StreamingNLUModule
from .status import TurnTakingStatus
logger = setup_custom_logger(__name__)

SAMPLE_RATE = 8000
VOLUME_THRESHOLD = 500
FAST_SPEECH_END_THRESHOLD = 20
SLOW_SPEECH_END_THRESHOLD = 100
# FAST_TEXT_BASED_SPEECH_END_THRESHOLD = 30
# SLOW_TEXT_BASED_SPEECH_END_THRESHOLD = 100



class EndOfTurnDetector:
    def __init__(self, slot_keys: list[str]):
        self.streaming_vad = VolumeBasedVADModel(
            sample_rate=SAMPLE_RATE,
            volume_threshold=VOLUME_THRESHOLD,
            fast_speech_end_threshold=FAST_SPEECH_END_THRESHOLD,
            slow_speech_end_threshold=SLOW_SPEECH_END_THRESHOLD,
        )
        self.streaming_nlu = StreamingNLUModule(slot_keys=slot_keys)
        self.pre_text = ""
        self.stability_count = 0

    def nlu_step(self, text):
        if text != "":
            if text != self.pre_text:
                self.stability_count = 0
                self.streaming_nlu.process(text)
            else:
                self.stability_count += 1
        self.pre_text = text

    def vad_step(self, chunk):
        if chunk != "/w==":
            self.streaming_vad.update_vad_status(chunk)

    def step(self, text):
        self.nlu_step(text)

        logger.debug(
            (f"is_got_entity: {self.got_entity} " 
             f"is_slot_filled: {self.is_slot_filled} "
             f"is_terminal: {self.is_terminal} "
             f"is_fast_speech_end: {self.is_fast_speech_end} "
             f"is_slow_speech_end: {self.is_slow_speech_end}"
             f"stability_count: {self.stability_count}"
             f"pre_text: {self.pre_text}")   
            )

        if ((self.is_terminal and self.is_fast_speech_end)
            or (self.is_slot_filled and self.is_fast_speech_end)
            or self.is_slow_speech_end):
            return TurnTakingStatus.END_OF_TURN
        elif self.got_entity and self.is_fast_speech_end:
            return TurnTakingStatus.BACKCHANNEL
        else:
            return TurnTakingStatus.CONTINUE
        # return (
        #     (self.is_slot_filled and self.is_fast_speech_end) or 
        #     (self.is_terminal and self.is_fast_speech_end) or 
        #     self.is_slow_speech_end)
    
    def reset(self):
        self.streaming_nlu.init_state()
        # self.pre_text = ""
        # self.stability_count = 0
        self.streaming_vad.init_state()
    
    @property
    def is_slot_filled(self):
        return self.streaming_nlu.is_slot_filled
    
    @property
    def got_entity(self):
        return self.streaming_nlu.got_entity

    @property
    def is_terminal(self):
        return self.streaming_nlu.is_terminal

    @property
    def is_fast_speech_end(self):
        return len(self.streaming_vad.speech_chunks) > 5 and self.streaming_vad.fast_speech_end_flag
        # return self.stability_count >= FAST_SPEECH_END_THRESHOLD
    @property
    def is_slow_speech_end(self):
        return self.streaming_vad.slow_speech_end_flag
        # return self.stability_count >= SLOW_SPEECH_END_THRESHOLD