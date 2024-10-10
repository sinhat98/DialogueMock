import queue
import time
from google.api_core.exceptions import GoogleAPICallError, RetryError, OutOfRange
from google.cloud import speech
from google.cloud.speech import RecognitionConfig, StreamingRecognitionConfig
from src.utils import setup_custom_logger

logger = setup_custom_logger(__name__)

MODEL = "latest_long"
MAX_RETRIES = 3
RETRY_INTERVAL = 5  # seconds

class ASRBridge:
    def __init__(self):
        self._queue = queue.Queue()
        self._ended = False
        self.stability = 0
        self.transcription = ""
        self.is_final = False
        
        self.bot_speak = False

        config = RecognitionConfig(
            model="latest_long",
            encoding=RecognitionConfig.AudioEncoding.MULAW,
            sample_rate_hertz=8000,
            language_code="ja-JP",
        )
        self.streaming_config = StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False,
        )

    def start(self):
        logger.info("ASR bridge started")
        self.run_with_retries()

    def run_with_retries(self):
        retries = 0
        while retries < MAX_RETRIES and not self._ended:
            try:
                self._run()
                break
            except (OutOfRange, GoogleAPICallError, RetryError) as e:
                logger.error(f"Error occurred: {e}. Retrying in {RETRY_INTERVAL} seconds...")
                retries += 1
                time.sleep(RETRY_INTERVAL)
        if retries == MAX_RETRIES:
            logger.error("Maximum retry attempts reached. Terminating...")
            self.terminate()

    def _run(self):
        client = speech.SpeechClient()
        stream = self.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in stream
        )
        responses = client.streaming_recognize(self.streaming_config, requests)
        self.process_responses_loop(responses)

    def set_bot_speak(self, bot_speak):
        self.bot_speak = bot_speak

    def get_transcription(self):
        return self.transcription

    def terminate(self):
        self._ended = True
        self._queue.put(None)

    def add_request(self, buffer):
        self._queue.put(bytes(buffer), block=False)

    def process_responses_loop(self, responses):
        try:
            for response in responses:
                self._on_response(response)
                if self._ended:
                    break
        except OutOfRange:
            logger.error("Received OutOfRange error. Restarting ASRBridge...")
            self.run_with_retries()
        except Exception as e:
            logger.error(f"Unexpected exception: {e}")
            self.terminate()

    def generator(self):
        while not self._ended:
            chunk = self._queue.get()
            if chunk is None:
                return
            data = [chunk]
            while True:
                try:
                    chunk = self._queue.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b"".join(data)
        self.terminate()

    def reset(self):
        self.transcription = ""
        self.is_final = False

    def _on_response(self, response):
        if not response.results:
            return
        result = response.results[0]
        if not result.alternatives:
            return
        self.is_final = result.is_final
        self.stability = result.stability
        self.transcription = result.alternatives[0].transcript
        if self.transcription:
            logger.info(f"ASR: {self.transcription}")

if __name__ == "__main__":
    asr_bridge = ASRBridge()
    asr_bridge.start()