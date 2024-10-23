import os
from openai import AzureOpenAI
from src.utils import get_custom_logger
from src.modules.nlu.prompt import system_prompt_for_faq, system_prompt_for_slot_filling
from dotenv import load_dotenv
import queue

load_dotenv()

logger = get_custom_logger(__name__)


class LLMBridge:
    def __init__(self, system_prompt, json_format=False):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.stream_sid = None
        self.system_prompt = system_prompt
        self.json_format = json_format

        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version="2024-02-01",
            azure_endpoint=endpoint,
        )

    def add_request(self, text):
        if text:
            logger.info(f"Add request: {text}")
            self.input_queue.put(text)

    def response_loop(self):
        logger.info("Response loop called.")
        while True:
            text = self.input_queue.get()
            if text is None:
                logger.info("Received exit signal.")
                break
            else:
                response = self.call_llm(text)
                self.output_queue.put(response)
        logger.info("Response loop ended.")

    def get_response(self, timeout=None):
        try:
            response = self.output_queue.get(timeout=timeout)
            return response
        except queue.Empty:
            logger.info("Response queue is empty.")
            return None

    def terminate(self):
        self.input_queue.put(None)

    def call_llm(self, text):
        if self.json_format:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                response_format={"type":"json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ]
            )
        else:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ]
            )
        return response.choices[0].message.content
    
if __name__ == "__main__":
    import threading
    import time

    llm_bridge = LLMBridge(system_prompt_for_faq)
    t_llm = threading.Thread(target=llm_bridge.response_loop)
    t_llm.start()

    # 例1: リクエストとレスポンスの処理
    llm_bridge.add_request("2席で別々のコースを注文できますか？")

    tic = time.time()
    response = llm_bridge.get_response(timeout=10)  # 最大10秒待機
    if response:
        logger.info(f"Response: {response}")
    else:
        logger.info("No response received.")

    toc = time.time() - tic
    logger.info(f"Elapsed time: {toc}")

    # 例2: FAQにない質問の例
    llm_bridge.add_request("ディナーの営業時間は何時からですか？")
    tic = time.time()
    response = llm_bridge.get_response(timeout=10)
    if response:
        logger.info(f"Response: {response}")
    else:
        logger.info("No response received.")
    toc = time.time() - tic
    logger.info(f"Elapsed time: {toc}")

    llm_bridge.terminate()
    
    # スロットフィリングのテスト
    llm_bridge = LLMBridge(system_prompt_for_slot_filling, json_format=True)
    # t_llm = threading.Thread(target=llm_bridge.response_loop)
    # t_llm.start()
    
    tic = time.time()
    response = llm_bridge.call_llm("来週の土曜日の11時からお願いします。")
    if response:
        logger.info(f"Response: {response}")
    else:
        logger.info("No response received.")
    toc = time.time() - tic
    logger.info(f"Elapsed time: {toc}")
    
    tic = time.time()
    response = llm_bridge.call_llm("次の土曜日の13時から2人でお願いします。")
    print(response)
    import json
    json_response = json.loads(response)
    print(json_response)
    if response:
        logger.info(f"Response: {response}")
    else:
        logger.info("No response received.")
    toc = time.time() - tic
    logger.info(f"Elapsed time: {toc}")
    
    llm_bridge.terminate()
    t_llm.join()
    