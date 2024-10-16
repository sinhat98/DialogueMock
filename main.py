from dotenv import load_dotenv

load_dotenv()

import os
import base64
import threading
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
from starlette.websockets import WebSocketState

from src.bridge import DialogBridge, ASRBridge, TTSBridge, LLMBridge
from src.bridge.dialog_bridge_v2 import DialogBridge as DialogBridgeV2
from src.bridge.dialog_bridge_v3 import DialogBridge as DialogBridgeV3
import logging
from pathlib import Path

from dotenv import load_dotenv

from twilio.twiml.voice_response import Connect, Stream, VoiceResponse
from google.cloud.firestore import SERVER_TIMESTAMP

load_dotenv()

from src.utils import get_custom_logger
logger = get_custom_logger(__name__)


for logger_name in logging.Logger.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.INFO)

templates_dir = Path(__file__).parent / "templates"
templates_wav_dir = templates_dir / "wav"

app = FastAPI()
NGROK = os.environ["NGROK"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@app.post("/twiml")
async def twiml():
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f"wss://{NGROK}/ws")
    # response.say("お電話ありがとうございます。SHIFT渋谷店でございます。お電話のご用件をお話しください。", voice="alice", language="ja-JP")

    connect.append(stream)
    response.append(connect)
    logger.info(response)

    return Response(
        content=str(response),
        status_code=200,
        headers={"Content-Type": "text/html"},
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    print("WS connection opened")

    await ws.accept()

    asr_bridge = ASRBridge()
    tts_bridge = TTSBridge()
    llm_bridge = LLMBridge()
    # dialog_bridge = DialogBridge()
    # dialog_bridge = DialogBridgeV2()
    dialog_bridge = DialogBridgeV3()
    

    

    t_tts = threading.Thread(target=tts_bridge.response_loop)
    t_llm = threading.Thread(target=llm_bridge.response_loop)
    
    t_tts.start()
    t_llm.start()
    
    # llm_bridge.add_request("サンプル")
    # response = llm_bridge.get_response()
    
    import asyncio

    def start_async_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    # 新しいイベントループを作成し、それを別のスレッドで実行
    new_loop = asyncio.new_event_loop()
    t_loop = threading.Thread(target=start_async_loop, args=(new_loop,))
    t_loop.start()

    # first = [0, "お電話ありがとうございます。SHIFT渋谷店でございます。お電話のご用件をお話しください。",]
    first = [
        0,
        "お電話ありがとうございます。新規ご予約を承ります。"
    ]

    while ws.application_state == WebSocketState.CONNECTED:
        data = await ws.receive_json()

        if data["event"] in ("connected", "start"):
            logger.info(f"Media WS: Received event '{data['event']}': {data}")
            if data["event"] == "start":
                dialog_bridge.set_stream_sid(data["start"]["streamSid"])
                tts_bridge.set_connect_info(data["start"]["streamSid"])
                tts_bridge.add_response("INITIAL")
                logger.info(f"Bot: {first[1]} INITIAL")

                _, out = tts_bridge.audio_queue.get()
                await ws.send_text(out)
                threading.Thread(target=asr_bridge.start).start()
                # t_asr_lst = [threading.Thread(target=asr_bridge.start)]
                # t_asr_lst[0].start()

        elif data["event"] == "stop":
            logger.info(f"Media WS: Received event 'stop': {data}")
            break

        elif data["event"] == "media":
            media = data["media"]
            chunk = base64.b64decode(media["payload"])
            asr_bridge.add_request(chunk)
            dialog_bridge.vad_step(chunk)
            out = await dialog_bridge(ws, asr_bridge, llm_bridge, tts_bridge)

            if out["asr_done"]:
                logger.info("ASR done")
                asr_bridge.terminate()
                asr_bridge = ASRBridge()
                threading.Thread(target=asr_bridge.start).start()
                logger.info("Restarted asr bridge")
            
            # if out["bot_speak"]:
            #     asr_bridge.set_bot_speak(True)
            
        elif data["event"] == "mark" and data["mark"]["name"] == "continue":
            logger.info(f"Media WS: Received event 'mark': {data}")
            logger.info("Bot: Speaking is done")
            # asr_bridge.reset()
            dialog_bridge.bot_speak = False
            # 暗黙確認時にのみバージインを許可するため、botが話し終わったタイミングでバージインを毎回オフにする
            dialog_bridge.allow_barge_in = False 
            logger.info("set allow_barge_in to False")
            # asr_bridge.set_bot_speak(False)
            # dialog_bridge.bot_speak = False
            # asr_bridge.terminate()
            # asr_bridge = ASRBridge()
            # threading.Thread(target=asr_bridge.start).start()
        elif data["event"] == "mark" and data["mark"]["name"] == "finish":
            logger.info(f"Media WS: Received event 'finish': {data}")
            break
        else:
            raise "Media WS: Received unknown event"
        
        

    logger.info("Media WS: Connection closed")
    asr_bridge.terminate()
    # t_tts.join()

    logger.info("WS connection completedly closed")