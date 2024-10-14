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

    async def send_audio_chunks_loop(self):
        async with websockets.connect(self.ws_address) as websocket:
            logger.info("Connected to VAP server")
            while not self._ended:
                chunk = self.collect_audio_chunk()
                if chunk is None:
                    break

                current_x1, current_x2 = self.format_chunk(chunk)
                await self.send_audio_chunk(websocket, current_x1, current_x2)
                
                # Process received VAP results
                self.vap_result = await self.receive_vap_result(websocket)
                logger.info(f"VAP Result: {self.vap_result}")

            # Close the WebSocket connection
            await websocket.close()

    def collect_audio_chunk(self):
        while not self._ended:
            chunk = self._queue.get()
            if chunk is None:
                return None
            data = [chunk]

            while True:
                try:
                    chunk = self._queue.get(block=False)
                    if chunk is None:
                        return None
                    data.append(chunk)
                except queue.Empty:
                    break
            return b"".join(data)

    def format_chunk(self, chunk):
        current_x1 = np.zeros(self.vap.frame_contxt_padding)
        current_x2 = np.zeros(self.vap.frame_contxt_padding)
        # Here, you should implement the logic to format the raw audio chunk to x1 and x2
        # which you will send to VAP server
        return current_x1, current_x2

    async def send_audio_chunk(self, websocket, current_x1, current_x2):
        try:
            data_sent = util.conv_2floatarray_2_bytearray(current_x1, current_x2)
            await websocket.send(data_sent)
            logger.info("Sent audio chunk to VAP server")
        except Exception as e:
            logger.error(f"Error sending audio chunk: {e}")

    async def receive_vap_result(self, websocket):
        try:
            data_received = await websocket.recv()
            vap_result = util.conv_bytearray_2_vapresult(data_received)
            logger.info("Received VAP result from server")
            return vap_result
        except Exception as e:
            logger.error(f"Error receiving VAP result: {e}")
            return None

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--vap_model", type=str, default=VAP_MODEL_PATH)
    parser.add_argument("--cpc_model", type=str, default=CPC_MODEL_PATH)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--vap_process_rate", type=int, default=10)
    parser.add_argument("--context_len_sec", type=float, default=5)
    parser.add_argument("--gpu", action='store_true')
    args = parser.parse_args()

    device = torch.device('cuda' if args.gpu and torch.cuda.is_available() else 'cpu')
    vap_bridge = VAPBridge(args.vap_model, args.cpc_model, device, args.vap_process_rate, args.context_len_sec, args.port)
    
    try:
        vap_bridge.start()
    except Exception as e:
        logger.error(f"An error occurred: {e}")