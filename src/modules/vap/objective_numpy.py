import numpy as np


from typing import Dict, List, Tuple

def bin_times_to_frames(bin_times: List[float], frame_hz: int) -> List[int]:
    return (np.array(bin_times) * frame_hz).astype(int).tolist()

class Codebook:
    def __init__(self, bin_frames):
        self.bin_frames = bin_frames
        self.n_bins = len(self.bin_frames)
        self.total_bins = self.n_bins * 2
        self.n_classes = 2 ** self.total_bins
        self.codes = self.create_code_vectors(self.total_bins)

    def single_idx_to_onehot(self, idx: int, d: int = 8) -> np.ndarray:
        """PyTorch実装と完全に一致"""
        assert idx < 2 ** d, f"must be possible with {d} binary digits"
        z = np.zeros(d, dtype=np.float32)
        b = bin(idx).replace("0b", "")  # '0b' prefixを削除
        # 右から左（LSB->MSB）の順で値を設定
        for i, v in enumerate(b[::-1]):  # [::-1]で文字列を逆順に
            z[i] = float(v)
        return z

    def create_code_vectors(self, n_bins: int) -> np.ndarray:
        """PyTorch実装と完全に一致"""
        n_codes = 2 ** n_bins
        embs = np.zeros((n_codes, n_bins), dtype=np.float32)
        for i in range(n_codes):
            embs[i] = self.single_idx_to_onehot(i, d=n_bins)
        return embs

    def encode(self, x: np.ndarray) -> np.ndarray:
        """PyTorch実装と完全に一致するように実装"""
        assert x.shape[-2:] == (2, self.n_bins), \
            f"Codebook expects (..., 2, {self.n_bins}) got {x.shape}"

        shape = x.shape
        flatten = x.reshape(-1, 2 * self.n_bins)
        
        # PyTorch実装の計算順序を完全に模倣
        x_squared = np.sum(flatten**2, axis=1, keepdims=True)  # [N, 1]
        embed = self.codes.T  # [D, C]
        
        # dot product
        dot_prod = np.dot(flatten, embed)  # [N, C]
        
        # embed squared sum
        embed_squared = np.sum(self.codes**2, axis=1, keepdims=True).T  # [1, C]
        
        # 距離計算
        dist = -(x_squared - 2 * dot_prod + embed_squared)
        
        # 最大値のインデックスを取得
        indices = np.argmax(dist, axis=1)
        
        # 元の形状に戻す
        return indices.reshape(shape[:-2])

    def decode(self, idx: np.ndarray) -> np.ndarray:
        """デコード処理"""
        codes = self.codes[idx]
        return codes.reshape(*codes.shape[:-1], 2, -1)
    

class ProjectionWindow:
    def __init__(
        self,
        bin_times: List = [0.2, 0.4, 0.6, 0.8],
        frame_hz: int = 50,
        threshold_ratio: float = 0.5,
    ):
        self.bin_times = bin_times
        self.frame_hz = frame_hz
        self.threshold_ratio = threshold_ratio
        self.bin_frames = bin_times_to_frames(bin_times, frame_hz)
        self.n_bins = len(self.bin_frames)
        self.total_bins = self.n_bins * 2
        self.horizon = sum(self.bin_frames)

    def projection(self, va: np.ndarray) -> np.ndarray:
        """Extract projection (bins)
        PyTorch's unfold operation equivalent
        """
        batch_size, time_steps, n_channels = va.shape
        n_frames = time_steps - self.horizon
        
        # Skip first frame like PyTorch implementation
        va = va[:, 1:, :]
        
        windows = np.zeros((batch_size, n_frames, n_channels, self.horizon))
        for i in range(n_frames):
            windows[:, i, :, :] = va[:, i:i+self.horizon, :].transpose(0, 2, 1)
        
        return windows

    def projection_bins(self, projection_window: np.ndarray) -> np.ndarray:
        """Exactly match PyTorch implementation"""
        start = 0
        v_bins = []
        for b in self.bin_frames:
            end = start + b
            # Use exact same operations as PyTorch
            m = projection_window[..., start:end].sum(axis=-1) / float(b)
            m = (m >= self.threshold_ratio).astype(np.float32)  # Use float32 to match PyTorch
            v_bins.append(m)
            start = end
        return np.stack(v_bins, axis=-1)

    def __call__(self, va: np.ndarray) -> np.ndarray:
        projection_windows = self.projection(va)
        return self.projection_bins(projection_windows)

class ObjectiveVAP:
    def __init__(
        self,
        bin_times: List[float] = [0.2, 0.4, 0.6, 0.8],
        frame_hz: int = 50,
        threshold_ratio: float = 0.5,
    ):
        self.frame_hz = frame_hz
        self.bin_times = bin_times
        self.bin_frames = bin_times_to_frames(bin_times, frame_hz)
        self.horizon = sum(self.bin_frames)
        self.horizon_time = sum(bin_times)

        self.codebook = Codebook(self.bin_frames)
        self.projection_window_extractor = ProjectionWindow(
            bin_times, frame_hz, threshold_ratio
        )
        self.lid_n_classes = 3

    def window_to_win_dialog_states(self, wins):
        return (wins.sum(-1) > 0).sum(-1)

    def get_labels(self, va: np.ndarray) -> np.ndarray:
        projection_windows = self.projection_window_extractor(va)
        return self.codebook.encode(projection_windows)

    def get_da_labels(self, va: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        projection_windows = self.projection_window_extractor(va)
        idx = self.codebook.encode(projection_windows)
        ds = self.window_to_win_dialog_states(projection_windows)
        return idx, ds

    def get_probs(self, logits: np.ndarray) -> Dict[str, np.ndarray]:
        """音声アクティビティの予測確率を計算し、異なる時間窓での確率を返す。

        Parameters
        ----------
        logits : np.ndarray, shape (batch_size, n_frames, n_classes)
            モデルから出力されたロジット値。
            n_classesは2^8=256で、8ビット(2話者×4時間ビン)の全パターンを表現。

        Returns
        -------
        Dict[str, np.ndarray]
            以下の要素を含む辞書:
            - "probs": np.ndarray, shape (batch_size, n_frames, n_classes)
                全クラスに対するソフトマックス確率。
            
            - "p_now": np.ndarray, shape (batch_size, n_frames, 2)
                現在の時間窓(最初の2ビン)における各話者の発話確率。
                [0]は話者1、[1]は話者2の確率を表す。
            
            - "p_future": np.ndarray, shape (batch_size, n_frames, 2)
                将来の時間窓(後ろの2ビン)における各話者の発話確率。
                [0]は話者1、[1]は話者2の確率を表す。
            
            - "p_tot": np.ndarray, shape (batch_size, n_frames, 2)
                全時間窓(全4ビン)における各話者の発話確率。
                [0]は話者1、[1]は話者2の確率を表す。

        """
        probs = np.exp(logits) / np.sum(np.exp(logits), axis=-1, keepdims=True)
        
        return {
            "probs": probs,
            "p_now": self._aggregate_probs(probs, 0, 1),
            "p_future": self._aggregate_probs(probs, 2, 3),
            "p_tot": self._aggregate_probs(probs, 0, 3),
        }
    def _aggregate_probs(self, probs: np.ndarray, from_bin: int, to_bin: int) -> np.ndarray:
        """Match PyTorch implementation exactly"""
        states = self.codebook.decode(np.arange(self.codebook.n_classes))
        bin_sum = states[:, :, from_bin:to_bin + 1].sum(-1)
        # Use same einsum operation
        p_all = np.einsum('bid,dc->bic', probs, bin_sum)
        # Normalize exactly like PyTorch
        return p_all / (p_all.sum(-1, keepdims=True) + 1e-5)
