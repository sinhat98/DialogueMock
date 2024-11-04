# vap_bridge.py

import queue
import threading
import time
import numpy as np

from scipy import signal

# from src.modules.vap.vap_main import VAPRealTime
from src.modules.vap.vap import VAPRealTime
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)


class AudioSynchronizer:
    def __init__(self, frame_size=160, sample_rate=8000, target_sample_rate=16000):
        """
        Args:
            frame_size: 入力フレームサイズ（8kHzでの160サンプル = 20ms）
            sample_rate: 入力サンプリングレート（8kHz）
            target_sample_rate: 目標サンプリングレート（16kHz）
        """
        self.frame_size = frame_size
        self.sample_rate = sample_rate
        self.target_sample_rate = target_sample_rate

        # アップサンプリング後のフレームサイズを計算
        self.upsampled_frame_size = int(frame_size * (target_sample_rate / sample_rate))

        # 各話者のバッファ（アップサンプリング後のデータを保持）
        self.bot_buffer = []
        self.user_buffer = []

        # 同期済みフレームを保持するキュー
        self.sync_queue = queue.Queue()

        # TTS音声バッファリング用
        self.tts_frame_length = self.frame_size / self.sample_rate
        self.tts_buffer = queue.Queue()
        self._ended = False

        # バッファリング用スレッド
        self.buffer_thread = threading.Thread(target=self._buffer_loop)
        self.buffer_thread.daemon = True
        self.buffer_thread.start()

        logger.info(
            f"Initialized AudioSynchronizer with frame_size={frame_size}, "
            f"upsampled_frame_size={self.upsampled_frame_size}"
        )

    def _buffer_loop(self):
        """TTSバッファリングループ"""
        delay_time = 0.0
        while not self._ended:
            start_time = time.time()
            try:
                # TTSの音声チャンクがあればバッファに格納
                chunk = self.tts_buffer.get(block=False)
                # logger.debug(f"Processing TTS chunk, size: {len(chunk)}")
                self.add_bot_audio(chunk)
            except queue.Empty:
                # ない場合は遅延時間とフレーム長を合わせた分の無音を処理
                chunk_time = delay_time + self.tts_frame_length
                chunk_size = int(chunk_time * self.sample_rate)
                if chunk_size > 0:  # サイズが0より大きい場合のみ処理
                    silence_chunk = np.zeros(chunk_size)
                    # logger.debug(f"Adding silence chunk, size: {chunk_size}")
                    self.add_bot_audio(silence_chunk)
                delay_time = 0.0

            # フレーム長に同期してループ
            proc_time = time.time() - start_time
            sleep_time = max(0, self.tts_frame_length - proc_time)
            # logger.debug(
            #     f"Buffer loop timing - proc_time: {proc_time:.4f}, sleep_time: {sleep_time:.4f}"
            # )
            time.sleep(sleep_time)

            delay_time += proc_time

    def _upsample(self, audio: np.ndarray) -> np.ndarray:
        """8kHzから16kHzへアップサンプリング"""
        return signal.resample(
            audio, int(len(audio) * (self.target_sample_rate / self.sample_rate))
        )

    def add_bot_audio(self, audio_chunk: np.ndarray):
        """システム音声の追加（8kHz）"""
        upsampled_audio = self._upsample(audio_chunk)
        # logger.debug(
        #     f"Bot audio added - original size: {len(audio_chunk)}, upsampled size: {len(upsampled_audio)}"
        # )
        self.bot_buffer.extend(upsampled_audio)
        self._try_sync()

    def add_user_audio(self, audio_chunk: np.ndarray):
        """ユーザー音声の追加（8kHz）"""
        upsampled_audio = self._upsample(audio_chunk)
        # logger.debug(
        #     f"User audio added - original size: {len(audio_chunk)}, upsampled size: {len(upsampled_audio)}"
        # )
        self.user_buffer.extend(upsampled_audio)
        self._try_sync()

    def add_bot_audio_to_buffer(self, audio_chunk: np.ndarray):
        """TTS音声をバッファに追加"""
        self.tts_buffer.put(audio_chunk)

    def _try_sync(self):
        """フレームサイズに達したら同期処理を実行"""
        bot_frames = len(self.bot_buffer) // self.upsampled_frame_size
        user_frames = len(self.user_buffer) // self.upsampled_frame_size
        min_frames = min(bot_frames, user_frames)

        # logger.debug(
        #     f"Sync status - bot frames: {bot_frames}, user frames: {user_frames}, "
        #     f"bot buffer size: {len(self.bot_buffer)}, user buffer size: {len(self.user_buffer)}"
        # )

        for _ in range(min_frames):
            bot_frame = np.array(self.bot_buffer[: self.upsampled_frame_size])
            user_frame = np.array(self.user_buffer[: self.upsampled_frame_size])

            self.bot_buffer = self.bot_buffer[self.upsampled_frame_size :]
            self.user_buffer = self.user_buffer[self.upsampled_frame_size :]

            sync_frame = np.stack([bot_frame, user_frame])
            self.sync_queue.put(sync_frame)
            # logger.debug(
            #     f"Synced frame processed - frame size: {self.upsampled_frame_size}"
            # )

        # バッファサイズの制限
        max_buffer = self.upsampled_frame_size * 10
        if len(self.bot_buffer) > max_buffer:
            self.bot_buffer = self.bot_buffer[-max_buffer:]
        if len(self.user_buffer) > max_buffer:
            self.user_buffer = self.user_buffer[-max_buffer:]

    def get_sync_frame(self, timeout=0.1):
        """同期済みフレームの取得"""
        try:
            return self.sync_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def terminate(self):
        """終了処理"""
        self._ended = True
        if self.buffer_thread.is_alive():
            self.buffer_thread.join()


class VAPBridge:
    def __init__(
        self,
        frame_rate: int = 20,
        context_len_sec: float = 2.5,
    ):
        self._ended = False

        # VAP初期化
        self.vap = VAPRealTime(
            frame_rate=frame_rate,
            context_len_sec=context_len_sec,
        )

        # 音声同期用（8kHz入力を16kHzにアップサンプリング）
        self.synchronizer = AudioSynchronizer(
            frame_size=160, sample_rate=8000, target_sample_rate=16000  # 20ms @ 8kHz
        )

        # 結果保持用
        self.vap_result = {"t": time.time(), "p_now": 0.0, "p_future": 0.0}

        # 処理スレッド
        self.process_thread = threading.Thread(target=self.process_loop)
        self.process_thread.daemon = True
        self.process_thread.start()

        logger.info("Initialized VAPBridge")

    def process_loop(self):
        """VAP処理ループ（別スレッドで実行）"""
        while not self._ended:
            try:
                # 同期済みフレームの取得
                sync_frame = self.synchronizer.get_sync_frame()
                if sync_frame is not None:
                    # logger.debug(
                    #     f"Processing VAP frame - shape: {sync_frame.shape}, "
                    #     f"bot mean: {np.mean(np.abs(sync_frame[0])):.4f}, "
                    #     f"user mean: {np.mean(np.abs(sync_frame[1])):.4f}"
                    # )

                    # VAPでの処理
                    self.vap.process_vap(sync_frame[0], sync_frame[1])

                    # 結果の更新
                    self.vap_result = {
                        "t": time.time(),
                        "p_now": self.vap.result_p_now,
                        "p_future": self.vap.result_p_future,
                    }

                    # logger.debug(
                    #     f"VAP results - p_now: {self.vap_result['p_now']:.3f}, "
                    #     f"p_future: {self.vap_result['p_future']:.3f}, "
                    #     f"time since last: {time.time() - self.vap_result['t']:.3f}s"
                    # )

            except Exception as e:
                logger.error(f"Error in VAP processing: {e}", exc_info=True)

            time.sleep(0.001)  # CPU負荷軽減

    def add_bot_audio(self, audio_chunk: np.ndarray):
        """システム音声の追加（バッファリング処理を通して追加）"""
        # logger.debug(f"Adding bot audio to buffer - chunk size: {len(audio_chunk)}")
        self.synchronizer.add_bot_audio_to_buffer(audio_chunk)

    def add_user_audio(self, audio_chunk: np.ndarray):
        """ユーザー音声の追加（直接追加）"""
        # logger.debug(f"Adding user audio - chunk size: {len(audio_chunk)}")
        self.synchronizer.add_user_audio(audio_chunk)

    def get_result(self) -> dict[str, float]:
        """最新のVAP結果を取得"""
        return self.vap_result.copy()

    def terminate(self):
        """終了処理"""
        self._ended = True
        self.synchronizer.terminate()
        if self.process_thread.is_alive():
            self.process_thread.join()
        logger.info("Terminated VAPBridge")
