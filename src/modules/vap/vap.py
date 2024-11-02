import numpy as np
from typing import list

class ObjectiveVAP:
    def __init__(
        self,
        bin_times: list[float] = [0.2, 0.4, 0.6, 0.8],
        frame_hz: int = 50,
        threshold_ratio: float = 0.5,
    ):
        self.frame_hz = frame_hz
        self.bin_times = bin_times
        self.bin_frames = self._bin_times_to_frames(bin_times, frame_hz)
        self.horizon = sum(self.bin_frames)
        self.horizon_time = sum(bin_times)

        self.projection_window_extractor = ProjectionWindow(
            bin_times, frame_hz, threshold_ratio
        )

        self.lid_n_classes = 3


    @property
    def n_classes(self) -> int:
        return self.codebook.n_classes

    @property
    def n_bins(self) -> int:
        return self.codebook.n_bins

    def _bin_times_to_frames(self, bin_times: list[float], frame_hz: int) -> list[int]:
        return [round(t * frame_hz) for t in bin_times]

    def probs_next_speaker_aggregate(
        self,
        probs: np.ndarray,
        from_bin: int = 0,
        to_bin: int = 3,
        scale_with_bins: bool = False,
    ) -> np.ndarray:
        assert (
            probs.ndim == 3
        ), f"Expected probs of shape (B, n_frames, n_classes) but got {probs.shape}"
        
        idx = np.arange(self.codebook.n_classes)
        states = self.codebook.decode(idx)

        if scale_with_bins:
            states = states * np.array(self.bin_frames)[:, None]
            
        abp = states[:, :, from_bin:to_bin + 1].sum(-1)  # sum speaker activity bins
        
        # Dot product over all states
        p_all = np.einsum('bid,dc->bic', probs, abp)
        
        # normalize
        p_all /= p_all.sum(axis=-1, keepdims=True) + 1e-5
        
        return p_all