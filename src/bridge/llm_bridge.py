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

        self.openai_model = os.environ.get("AZURE_OPENAI_MODEL")
        model_version = os.environ.get("AZURE_OPENAI_MODEL_VERSION")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        logger.info(
            f"Model: {self.openai_model}, Version: {model_version}, Endpoint: {endpoint}"
        )
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=model_version,
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
                model=self.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )
        else:
            response = self.client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )
        output = response.choices[0].message.content
        logger.info(f"Response: {output}")
        return output

def get_sf_llm_bridge():
    return LLMBridge(system_prompt_for_slot_filling, json_format=True)


def get_faq_llm_bridge():
    return LLMBridge(system_prompt_for_faq)


if __name__ == "__main__":
    from src.modules.nlu.prompt import get_base_system_prompt
    from src.modules.dialogue.utils.template import templates

    initial_state = templates["initial_state"]
    prompt = get_base_system_prompt(initial_state)
    llm_bridge = LLMBridge(prompt, json_format=True)
    sample_text = "はいお願いします"
    response = llm_bridge.call_llm(sample_text)
    logger.info(f"Response: {response}")
    print(type(response))
    response_dict = eval(response)
    print(type(response_dict))

    # import threading
    # import time

    # llm_bridge = LLMBridge(system_prompt_for_faq)
    # t_llm = threading.Thread(target=llm_bridge.response_loop)
    # t_llm.start()

    # # 例1: リクエストとレスポンスの処理
    # llm_bridge.add_request("2席で別々のコースを注文できますか？")

    # tic = time.time()
    # response = llm_bridge.get_response(timeout=10)  # 最大10秒待機
    # if response:
    #     logger.info(f"Response: {response}")
    # else:
    #     logger.info("No response received.")

    # toc = time.time() - tic
    # logger.info(f"Elapsed time: {toc}")

    # # 例2: FAQにない質問の例
    # llm_bridge.add_request("ディナーの営業時間は何時からですか？")
    # tic = time.time()
    # response = llm_bridge.get_response(timeout=10)
    # if response:
    #     logger.info(f"Response: {response}")
    # else:
    #     logger.info("No response received.")
    # toc = time.time() - tic
    # logger.info(f"Elapsed time: {toc}")

    # llm_bridge.terminate()

    # # スロットフィリングのテスト
    # llm_bridge = LLMBridge(system_prompt_for_slot_filling, json_format=True)
    # # t_llm = threading.Thread(target=llm_bridge.response_loop)
    # # t_llm.start()

    # tic = time.time()
    # response = llm_bridge.call_llm("来週の土曜日の11時からお願いします。")
    # if response:
    #     logger.info(f"Response: {response}")
    # else:
    #     logger.info("No response received.")
    # toc = time.time() - tic
    # logger.info(f"Elapsed time: {toc}")

    # tic = time.time()
    # response = llm_bridge.call_llm("次の土曜日の13時から2人でお願いします。")
    # print(response)
    # import json

    # json_response = json.loads(response)
    # print(json_response)
    # if response:
    #     logger.info(f"Response: {response}")
    # else:
    #     logger.info("No response received.")
    # toc = time.time() - tic
    # logger.info(f"Elapsed time: {toc}")

    # llm_bridge.terminate()
    # t_llm.join()
