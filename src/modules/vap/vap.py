# vap.py

import torch
import torch.nn as nn
from torch.nn import functional as F
import numpy as np
from dataclasses import dataclass, field
import time

from src.modules.vap import (
    EncoderCPC,
    GPT,
    GPTStereo,
    ObjectiveVAP,
    VAP_MODEL_PATH,
    CPC_MODEL_PATH,
)
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)


@dataclass
class VapConfig:
    sample_rate: int = 16000
    frame_hz: int = 50
    bin_times: list[float] = field(default_factory=lambda: [0.2, 0.4, 0.6, 0.8])
    encoder_type: str = "cpc"
    wav2vec_type: str = "mms"
    hubert_model: str = "hubert_jp"
    freeze_encoder: int = 1
    load_pretrained: int = 1
    only_feature_extraction: int = 0
    dim: int = 256
    channel_layers: int = 1
    cross_layers: int = 3
    num_heads: int = 4
    dropout: float = 0.1
    context_limit: int = -1
    context_limit_cpc_sec: float = -1
    lid_classify: int = 0
    lid_classify_num_class: int = 3
    lid_classify_adversarial: int = 0
    lang_cond: int = 0


class VapGPT(nn.Module):
    def __init__(self, conf: VapConfig | None = None):
        super().__init__()
        if conf is None:
            conf = VapConfig()
        self.conf = conf
        self.sample_rate = conf.sample_rate
        self.frame_hz = conf.frame_hz

        self.temp_elapse_time = []

        self.ar_channel = GPT(
            dim=conf.dim,
            dff_k=3,
            num_layers=conf.channel_layers,
            num_heads=conf.num_heads,
            dropout=conf.dropout,
            context_limit=conf.context_limit,
        )

        self.ar = GPTStereo(
            dim=conf.dim,
            dff_k=3,
            num_layers=conf.cross_layers,
            num_heads=conf.num_heads,
            dropout=conf.dropout,
            context_limit=conf.context_limit,
        )

        self.objective = ObjectiveVAP(bin_times=conf.bin_times, frame_hz=conf.frame_hz)

        self.va_classifier = nn.Linear(conf.dim, 1)

        if self.conf.lid_classify == 1:
            self.lid_classifier = nn.Linear(conf.dim, conf.lid_classify_num_class)
        elif self.conf.lid_classify == 2:
            self.lid_classifier_middle = nn.Linear(
                conf.dim * 2, conf.lid_classify_num_class
            )

        if self.conf.lang_cond == 1:
            self.lang_condition = nn.Linear(conf.lid_classify_num_class, conf.dim)

        self.vap_head = nn.Linear(conf.dim, self.objective.n_classes)

    def load_encoder(self, cpc_model):
        self.encoder1 = EncoderCPC(
            load_pretrained=True if self.conf.load_pretrained == 1 else False,
            freeze=self.conf.freeze_encoder,
            cpc_model=cpc_model,
        )
        self.encoder1 = self.encoder1.eval()

        self.encoder2 = EncoderCPC(
            load_pretrained=True if self.conf.load_pretrained == 1 else False,
            freeze=self.conf.freeze_encoder,
            cpc_model=cpc_model,
        )
        self.encoder2 = self.encoder2.eval()

        if self.conf.freeze_encoder == 1:
            print("freeze encoder")
            self.encoder1.freeze()
            self.encoder2.freeze()

    @property
    def horizon_time(self):
        return self.objective.horizon_time

    def encode_audio(
        self, audio1: torch.Tensor, audio2: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        x1 = self.encoder1(audio1)  # speaker 1
        x2 = self.encoder2(audio2)  # speaker 2
        return x1, x2

    def vad_loss(self, vad_output, vad):
        return F.binary_cross_entropy_with_logits(vad_output, vad)


class VAPRealTime:
    BINS_P_NOW = [0, 1]
    BINS_PFUTURE = [2, 3]

    def __init__(self, frame_rate: int = 20, context_len_sec: float = 2.5):
        conf = VapConfig()
        self.vap = VapGPT(conf)

        self.device = "cpu"
        sd = torch.load(VAP_MODEL_PATH, map_location=torch.device("cpu"))
        self.vap.load_encoder(cpc_model=CPC_MODEL_PATH)
        self.vap.load_state_dict(sd, strict=False)

        self._init_encoder_params(sd)

        self.vap.to(self.device)
        self.vap = self.vap.eval()

        self.frame_rate = frame_rate
        self.audio_context_len = int(context_len_sec * frame_rate)
        self.frame_contxt_padding = 320
        self.sampling_rate = 16000
        self.audio_frame_size = (
            self.sampling_rate // self.frame_rate + self.frame_contxt_padding
        )

        self.e1_context = []
        self.e2_context = []

        self.result_p_now = 0.0
        self.result_p_future = 0.0

        logger.info(
            f"Initialized VAPRealTime with frame_rate={frame_rate}, context_len={context_len_sec}"
        )

    def _init_encoder_params(self, state_dict):
        self.vap.encoder1.downsample[1].weight = nn.Parameter(
            state_dict["encoder.downsample.1.weight"]
        )
        self.vap.encoder1.downsample[1].bias = nn.Parameter(
            state_dict["encoder.downsample.1.bias"]
        )
        self.vap.encoder1.downsample[2].ln.weight = nn.Parameter(
            state_dict["encoder.downsample.2.ln.weight"]
        )
        self.vap.encoder1.downsample[2].ln.bias = nn.Parameter(
            state_dict["encoder.downsample.2.ln.bias"]
        )

        self.vap.encoder2.downsample[1].weight = nn.Parameter(
            state_dict["encoder.downsample.1.weight"]
        )
        self.vap.encoder2.downsample[1].bias = nn.Parameter(
            state_dict["encoder.downsample.1.bias"]
        )
        self.vap.encoder2.downsample[2].ln.weight = nn.Parameter(
            state_dict["encoder.downsample.2.ln.weight"]
        )
        self.vap.encoder2.downsample[2].ln.bias = nn.Parameter(
            state_dict["encoder.downsample.2.ln.bias"]
        )

    def _pad_audio(self, audio: torch.Tensor) -> torch.Tensor:
        """音声データを必要な長さにパディング"""
        current_size = audio.shape[-1]
        if current_size < self.audio_frame_size:
            padding_size = self.audio_frame_size - current_size
            padded = F.pad(audio, (0, padding_size))
            # logger.debug(f"Padded audio from {current_size} to {padded.shape[-1]}")
            return padded
        return audio

    def process_vap(self, bot_audio: np.ndarray, user_audio: np.ndarray):
        try:
            if (
                len(bot_audio) < self.frame_contxt_padding
                or len(user_audio) < self.frame_contxt_padding
            ):
                logger.warning("Input audio too short, skipping processing")
                return

            with torch.no_grad():
                x1 = (
                    torch.tensor(bot_audio, dtype=torch.float32, device=self.device)
                    .unsqueeze(0)
                    .unsqueeze(0)
                )
                x2 = (
                    torch.tensor(user_audio, dtype=torch.float32, device=self.device)
                    .unsqueeze(0)
                    .unsqueeze(0)
                )

                x1 = self._pad_audio(x1)
                x2 = self._pad_audio(x2)

                # logger.debug(
                #     f"Processing audio shapes after padding - x1: {x1.shape}, x2: {x2.shape}"
                # )

                e1, e2 = self.vap.encode_audio(x1, x2)

                # logger.debug(f"Encoded shapes - e1: {e1.shape}, e2: {e2.shape}")

                self.e1_context.append(e1)
                self.e2_context.append(e2)

                if len(self.e1_context) > self.audio_context_len:
                    self.e1_context = self.e1_context[-self.audio_context_len :]
                if len(self.e2_context) > self.audio_context_len:
                    self.e2_context = self.e2_context[-self.audio_context_len :]

                x1 = torch.cat(self.e1_context, dim=1)
                x2 = torch.cat(self.e2_context, dim=1)

                o1 = self.vap.ar_channel(x1, attention=False)
                o2 = self.vap.ar_channel(x2, attention=False)
                out = self.vap.ar(o1["x"], o2["x"], attention=False)

                logits = self.vap.vap_head(out["x"])
                probs = logits.softmax(dim=-1)

                p_now = self.vap.objective.probs_next_speaker_aggregate(
                    probs, from_bin=self.BINS_P_NOW[0], to_bin=self.BINS_P_NOW[-1]
                )
                p_future = self.vap.objective.probs_next_speaker_aggregate(
                    probs, from_bin=self.BINS_PFUTURE[0], to_bin=self.BINS_PFUTURE[1]
                )

                self.result_p_now = p_now.to("cpu").tolist()[0][-1]  # list[spk1, spk2]
                self.result_p_future = p_future.to("cpu").tolist()[0][
                    -1
                ]  # list[spk1, spk2]
                self.result_p_now = self.result_p_now[0]
                self.result_p_future = self.result_p_future[0]

                logger.debug(
                    f"VAP processing complete - p_now: {self.result_p_now:.3f}, p_future: {self.result_p_future:.3f}"
                )

        except Exception as e:
            logger.error(f"Error in VAP processing: {e}", exc_info=True)
