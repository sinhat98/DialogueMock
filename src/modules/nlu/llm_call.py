import os
from openai import AzureOpenAI
from src.utils import get_custom_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_custom_logger(__name__)


openai_model = os.environ.get("AZURE_OPENAI_MODEL")
model_version = os.environ.get("AZURE_OPENAI_MODEL_VERSION")
api_key = os.environ.get("AZURE_OPENAI_API_KEY")
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
client = AzureOpenAI(
        api_key=api_key,
        api_version=model_version,
        azure_endpoint=endpoint,
    )
def call_llm(system_prompt, text, json_format=True):
    response_format = {"type": "json_object"} if json_format else {"type": "text"}
    # logger.debug(f"System prompt: {system_prompt}")
    response = client.chat.completions.create(
        model=openai_model,
        response_format=response_format,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        temperature=0,  # Set temperature to 0
    )
    output = response.choices[0].message.content
    logger.info(f"Response: {output}")
    return output