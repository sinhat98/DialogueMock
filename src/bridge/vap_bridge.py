import queue
import asyncio
import websockets
import numpy as np
import logging
from pathlib import Path
from rvap.vap_main.vap_main import VAPRealTime
import rvap.common.util as util
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
        
        # Set up WebSocket address
        self.ws_address = f"ws://localhost:{port}"

    def start(self):
        asyncio.run(self.send_audio_chunks_loop())

    def add_request(self, buffer):
        self._queue.put(bytes(buffer), block=False)

    def terminate(self):
        self._ended = True

    def get_vap_result(self):
        return self.vap_result
    
    def response_loop(self):
                # VAPモデルの読み込み
        encoder = EncoderCPC()
        transformer = TransformerStereo()
        model = VAP(encoder, transformer)
        ckpt = torch.load(self.model_name, map_location=device)['state_dict']
        restored_ckpt = {}
        for k,v in ckpt.items():
            restored_ckpt[k.replace('model.', '')] = v
        model.load_state_dict(restored_ckpt)
        model.eval()
        model.to(device)
        sys.stderr.write('Load VAP model: %s\n' % (self.model_name))
        sys.stderr.write('Device: %s\n' % (device))
        
        s_threshold = self.threshold
        u_threshold = 1 - self.threshold
        while True:
            # 両話者のデータを結合してバッチを作成
            ss_audio = torch.Tensor(self.ss_audio_buffer)
            us_audio = torch.Tensor(self.us_audio_buffer)
            input_audio = torch.stack((ss_audio, us_audio))
            input_audio = input_audio.unsqueeze(0)
            batch = torch.Tensor(input_audio)
            batch = batch.to(device)

            # 推論
            out = model.probs(batch)
            #print(out['vad'].shape,
            #      out['p_now'].shape,
            #      out['p_future'].shape,
            #      out['probs'].shape,
            #      out['H'].shape)

            # 結果の取得
            p_ns = out['p_now'][0, :].cpu()
            p_fs = out['p_future'][0, :].cpu()
            vad_result = out['vad'][0, :].cpu()

            # 最終フレームの結果を判定に利用
            score_n = p_ns[-1].item()
            score_f = p_fs[-1].item()
            score_v = vad_result[-1]

            # イベントの判定
            event = None
            if score_n >= self.threshold and score_f >= self.threshold:
                event = 'SYSTEM_TAKE_TURN'
            if score_n < self.threshold and score_f < self.threshold:
                event = 'USER_TAKE_TURN'

            # メッセージの発出
            # 可視化用スコア
            score = {'p_now': score_n,
                     'p_future': score_f}
            snd_iu = self.createIU(score, 'score',
                                   RemdisUpdateType.ADD)
            self.publish(snd_iu, 'score')

            # 変化があった時のみイベントを発出
            if event and event != self.prev_event:
                snd_iu = self.createIU(event, 'vap',
                                       RemdisUpdateType.ADD)
                print('n:%.3f, f:%.3f, %s' % (score_n,
                                              score_f,
                                              event))
                self.publish(snd_iu, 'vap')
                self.prev_event = event
            else:
                print('n:%.3f, f:%.3f' % (score_n,
                                          score_f))
