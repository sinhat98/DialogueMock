import queue
import threading
import time
import numpy as np
from scipy import signal
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
        self.frame_length = frame_size / sample_rate  # 20ms

        # アップサンプリング後のフレームサイズ
        self.upsampled_frame_size = int(frame_size * (target_sample_rate / sample_rate))

        # 固定長バッファ
        self.buffer_size = self.upsampled_frame_size * 10
        self.bot_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.user_buffer = np.zeros(self.buffer_size, dtype=np.float32)

        # タイムスタンプ付きバッファ用のキュー
        self.bot_queue = queue.Queue()
        self.user_queue = queue.Queue()

        # 同期済みフレームキュー
        self.sync_queue = queue.Queue()
        self._ended = False

        # 同期処理用スレッド
        self.sync_thread = threading.Thread(target=self._sync_loop)
        self.sync_thread.daemon = True
        self.sync_thread.start()

        logger.info(
            f"Initialized AudioSynchronizer with frame_size={frame_size}, "
            f"upsampled_frame_size={self.upsampled_frame_size}, "
            f"frame_length={self.frame_length:.3f}s"
        )

    def _upsample(self, audio: np.ndarray) -> np.ndarray:
        """8kHzから16kHzへアップサンプリング"""
        return signal.resample(
            audio, int(len(audio) * (self.target_sample_rate / self.sample_rate))
        )

    def _shift_buffer(self, buffer: np.ndarray, chunk: np.ndarray) -> np.ndarray:
        """バッファを更新"""
        chunk_size = len(chunk)
        buffer[:-chunk_size] = buffer[chunk_size:]
        buffer[-chunk_size:] = chunk
        return buffer

    def _sync_loop(self):
        """音声同期処理ループ"""
        while not self._ended:
            try:
                # 両方のキューからフレームを取得
                bot_frame = None
                user_frame = None

                # botの音声フレーム取得
                try:
                    bot_frame, bot_timestamp = self.bot_queue.get_nowait()
                    self.bot_buffer = self._shift_buffer(self.bot_buffer, bot_frame)
                except queue.Empty:
                    bot_frame = np.zeros(self.upsampled_frame_size)
                    bot_timestamp = time.time()

                # userの音声フレーム取得
                try:
                    user_frame, user_timestamp = self.user_queue.get_nowait()
                    self.user_buffer = self._shift_buffer(self.user_buffer, user_frame)
                except queue.Empty:
                    user_frame = np.zeros(self.upsampled_frame_size)
                    user_timestamp = time.time()

                # タイムスタンプの差が許容範囲内なら同期フレームとして処理
                if abs(bot_timestamp - user_timestamp) < self.frame_length:
                    sync_frame = np.stack([self.bot_buffer, self.user_buffer])
                    self.sync_queue.put((sync_frame, bot_timestamp))
                    logger.debug(
                        f"Synced frame - bot_ts: {bot_timestamp:.3f}, "
                        f"user_ts: {user_timestamp:.3f}, "
                        f"diff: {abs(bot_timestamp - user_timestamp):.3f}s"
                    )

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

            # フレーム長の半分の間隔で処理
            time.sleep(self.frame_length / 2)

    def add_bot_audio(self, audio_chunk: np.ndarray):
        """システム音声の追加（8kHz）"""
        try:
            upsampled_audio = self._upsample(audio_chunk)
            timestamp = time.time()
            self.bot_queue.put((upsampled_audio, timestamp))
            logger.debug(
                f"Added bot audio - original size: {len(audio_chunk)}, "
                f"upsampled size: {len(upsampled_audio)}, "
                f"timestamp: {timestamp:.3f}"
            )
        except Exception as e:
            logger.error(f"Error adding bot audio: {e}")

    def add_user_audio(self, audio_chunk: np.ndarray):
        """ユーザー音声の追加（8kHz）"""
        try:
            upsampled_audio = self._upsample(audio_chunk)
            timestamp = time.time()
            self.user_queue.put((upsampled_audio, timestamp))
            logger.debug(
                f"Added user audio - original size: {len(audio_chunk)}, "
                f"upsampled size: {len(upsampled_audio)}, "
                f"timestamp: {timestamp:.3f}"
            )
        except Exception as e:
            logger.error(f"Error adding user audio: {e}")

    def get_sync_frame(self, timeout=0.1):
        """同期済みフレームの取得"""
        try:
            return self.sync_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def terminate(self):
        """終了処理"""
        self._ended = True
        if hasattr(self, "sync_thread") and self.sync_thread.is_alive():
            self.sync_thread.join()
        logger.info("AudioSynchronizer terminated")

    def __del__(self):
        """デストラクタ"""
        self.terminate()


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
                    # VAPでの処理
                    self.vap.process_vap(sync_frame[0], sync_frame[1])

                    # 結果の更新
                    self.vap_result = {
                        "t": time.time(),
                        "p_now": self.vap.result_p_now,
                        "p_future": self.vap.result_p_future,
                    }

            except Exception as e:
                logger.error(f"Error in VAP processing: {e}", exc_info=True)

            time.sleep(0.001)  # CPU負荷軽減

    def add_bot_audio(self, audio_chunk: np.ndarray):
        """システム音声の追加"""
        self.synchronizer.add_bot_audio(audio_chunk)

    def add_user_audio(self, audio_chunk: np.ndarray):
        """ユーザー音声の追加"""
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
