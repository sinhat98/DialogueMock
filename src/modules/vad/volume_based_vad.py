import numpy as np

from g711 import decode_ulaw  # type: ignore
from numpy.typing import NDArray

from src.utils import get_custom_logger, chunk_generator

logger = get_custom_logger(__name__)


class VolumeBasedVADModel:
    def __init__(
        self,
        sample_rate,
        sample_window=0.01,
        sample_overlap=0.005,
        volume_threshold=1000,
        # 発話終了と判定するための連続したフレーム数
        fast_speech_end_threshold=20,  # 20ms * 20 = 400ms
        slow_speech_end_threshold=50,  # 20ms * 50 = 1000ms
    ):
        self.sample_rate = sample_rate
        self.sample_window = sample_window
        self.sample_overlap = sample_overlap
        self.volume_threshold = volume_threshold

        self.buffer = np.array([])
        self.processed_samples = 0
        self.fast_speech_end_threshold = fast_speech_end_threshold
        self.slow_speech_end_threshold = slow_speech_end_threshold
        self.fast_speech_end_flag = False
        self.slow_speech_end_flag = False
        self.chunk_speech_end_results = []
        self.speech_chunks = []
        
    def init_state(self):
        self.buffer = np.array([])
        self.processed_samples = 0
        self.fast_speech_end_flag = False
        self.slow_speech_end_flag = False
        self.chunk_speech_end_results = []
        self.speech_chunks = []

    def update_vad_status(self, chunk: str):
        # chunk_bytes = base64.b64decode(chunk)
        # chunk_array = np.frombuffer(chunk, dtype=np.int16)
        chunk_array= self.ulaw_decode(chunk)
        self.buffer = np.concatenate((self.buffer, chunk_array))
        self.processed_samples += len(chunk_array)

        sample_window = int(self.sample_rate * self.sample_window)
        sample_overlap = int(self.sample_rate * self.sample_overlap)

        speech_flags = []
        while len(self.buffer) >= sample_window:
            window = self.buffer[:sample_window]
            self.buffer = self.buffer[sample_overlap:]

            power = np.abs(window).sum() / sample_window
            _is_speech = power > self.volume_threshold
            speech_flags.append(_is_speech)
            # logger.info(f"power: {power}")
        # logger.debug(self.buffer)
        is_speech = any(speech_flags)
        if is_speech:
            self.speech_chunks.append(is_speech)
            logger.debug(f"Speech detected: {len(self.speech_chunks)}")
        self.chunk_speech_end_results.append(not is_speech)
        self.fast_speech_end_flag = all(
            self.chunk_speech_end_results[-self.fast_speech_end_threshold :]
        )
        non_speech_length = sum(
            self.chunk_speech_end_results[-self.slow_speech_end_threshold :]
        )
        logger.debug(f"Non speech length: {non_speech_length}")
        self.slow_speech_end_flag = all(
            self.chunk_speech_end_results[-self.slow_speech_end_threshold :]
        )
    @staticmethod
    def ulaw_decode(x: bytes) -> NDArray[np.int16]:
        """u-law エンコードされた配列をデコードし、16ビット整数として返す"""

        x_inv = decode_ulaw(x)  # u-law デコード

        # 結果を16ビット整数にスケーリングして変換
        x_inv_int16 = (x_inv * 32768).astype(
            np.int16
        )  # [-1, 1) -> [-32768, 32767)

        return x_inv_int16

if __name__ == "__main__":
    # Load audio file
    audio_file = (
        "/Users/s23326/Dev/turn-taking-vad/data_preparation/08011991889_0.8.wav"
    )

    # Create streaming model
    model = VolumeBasedVADModel(sample_rate=8000, debug=True)

    # Process audio in chunks
    chunk_msec = 20  # ms
    for chunk_num, chunk in chunk_generator(audio_file, chunk_msec):
        vad_result = model.process_chunk(chunk)
        logger.info(
            f"Processed chunk {chunk_num*chunk_msec/1000}s: {vad_result} {model.speech_end_flag}"
        )
