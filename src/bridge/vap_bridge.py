import queue
import asyncio
import websockets
import numpy as np
import logging
from pathlib import Path
from src.modules.vap.vap_main import VAPRealTime
from src.modules.vap import util
import torch

# ログ設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# websocketsモジュールのロギングレベルをERRORに設定
websockets_logger = logging.getLogger('websockets')
websockets_logger.setLevel(logging.ERROR)

ASSET_DIR = Path(__file__).parents[1] / 'vap_realtime/asset'
VAP_MODEL_PATH = ASSET_DIR / 'vap/vap_state_dict_jp_20hz_2500msec.pt'
CPC_MODEL_PATH = ASSET_DIR / 'cpc/60k_epoch4-d0f474de.pt'

class VAPBridge:
    def __init__(self, vap_model_path, cpc_model_path, device, frame_rate, context_len_sec, port):
        self._queue = queue.Queue()
        self._ended = False
        
        self.vap_result = None

        # VAP initialization
        self.vap = VAPRealTime(vap_model_path, cpc_model_path, device, frame_rate, context_len_sec)

    def start(self):
        asyncio.run(self.send_audio_chunks_loop())

    def add_request(self, buffer):
        self._queue.put(bytes(buffer), block=False)

    def terminate(self):
        self._ended = True

    def get_vap_result(self):
        return self.vap_result
    
    def response_loop(self):
        pass