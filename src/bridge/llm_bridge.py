import os
from openai import AzureOpenAI
from src.utils import setup_custom_logger

from dotenv import load_dotenv
import queue

load_dotenv()

logger = setup_custom_logger(__name__)

system_prompt = """
あなたは飲食店の店員です。
ユーザーからのメッセージに対してFAQのAnswerリストに関連する場合は返信を行います。
関連するものがない場合は、空文字を返してください。
Answerリスト:
- ランチの営業時間は11:00から15:00
- ディナーの営業時間は17:00から23:00
- 駐車場は2台停められます。
- ランチは席代がかかりませんが、ディナーは席代がかかります。
- ランチは予約できません。
"""

class LLMBridge:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.stream_sid = None

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
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
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

    llm_bridge = LLMBridge()
    t_llm = threading.Thread(target=llm_bridge.response_loop)
    t_llm.start()
    llm_bridge.add_request("ランチの営業時間は何時からですか？")

    tic = time.time()
    response = llm_bridge.get_response(timeout=10)  # 最大10秒待機
    if response:
        logger.info(f"Response: {response}")
    else:
        logger.info("No response received.")

    toc = time.time() - tic
    logger.info(f"Elapsed time: {toc}")
    
    llm_bridge.add_request("ディナーの営業時間は何時からですか？")
    tic = time.time()
    response = llm_bridge.get_response()
    logger.info(f"Response: {response}")
    toc = time.time() - tic
    logger.info(f"Elapsed time: {toc}")

    llm_bridge.terminate()
    t_llm.join()  # スレッドの終了を待つ