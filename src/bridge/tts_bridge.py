import io
import json
import queue
import requests
import base64
import pydub
import audioop
import numpy as np
from pydub import AudioSegment
from openai import OpenAI
import threading
from dotenv import load_dotenv
import os
from pathlib import Path
import random
import re
from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk
from abc import abstractmethod

from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

load_dotenv()


template_dir = Path(__file__).parents[1] / "modules/dialogue/utils/template_audio"

# 共通の親クラス
class BaseTTSBridge:
    def __init__(self):
        self.text_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self._ended = False
        self.stream_sid = None

    def add_response(self, text):
        if text != "":
            logger.info(f"Add response: {text}")
        self.text_queue.put(text, block=False)

    def response_loop(self):
        logger.info("Response loop called.")
        while not self._ended:
            text = self.text_queue.get()
            self.stream_use_endpoint(text)

    def terminate(self):
        self._ended = True
        self.text_queue.put("", block=False)
        self.audio_queue.put(("", ""), block=False)

    def adjust_text(self, text):
        # 02/27などの日付を2月27日などに変換
        # まず月日を抜き出す
        date = re.search(r"\d{1,2}/\d{1,2}", text)
        if date:
            date = date.group()
            month, day = date.split("/")
            month = int(month)
            day = int(day)
            text = text.replace(date, f"{month}月{day}日")

        # 12:30などの時間を12時半などに変換
        # 12:00は12時、12:30は12時半、12:45は12時45分
        time = re.search(r"\d{1,2}:\d{2}", text)
        if time:
            time = time.group()
            hour, minute = time.split(":")
            hour = int(hour)
            minute = int(minute)
            if minute == 0:
                text = text.replace(time, f"{hour}時")
            elif minute == 30:
                text = text.replace(time, f"{hour}時半")
            else:
                text = text.replace(time, f"{hour}時{minute}分")

        return text

    @staticmethod
    def trans4twilio(audio: AudioSegment) -> str:
        """Convert audio to Twilio media stream

        Args:
            audio (AudioSegment): Audio data

        Returns:
            str: Base64 encoded audio payload
        """
        d = np.array(audio.get_array_of_samples())
        # factor = 3
        # d = d[::factor]
        d = np.clip(d, -30000, 30000, out=None)
        width = 2
        mulaw = audioop.lin2ulaw(d, width)
        audio_payload = base64.b64encode(mulaw).decode("ascii")
        return audio_payload

    @staticmethod
    def get_twilio_media_stream(audio_payload: str, stream_sid: str) -> str:
        """Get Twilio media stream
        Args:
            audio_payload (str): Base64 encoded audio payload
            stream_sid (str): Stream SID
        Returns:
            str: JSON string for Twilio media stream
        """

        out_message = {
            "event": "media",
            "media": {"payload": audio_payload},
            "streamSid": stream_sid,
        }
        out_data = json.dumps(out_message)
        return out_data

    @abstractmethod
    def get_template_audio(text):
        raise NotImplementedError


class GoogleTTSBridge(BaseTTSBridge):
    def __init__(self):
        super().__init__()
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="ja-JP",
            name="ja-JP-Wavenet-A",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            sample_rate_hertz=8000,
        )

    def set_connect_info(self, stream_sid):
        self.stream_sid = stream_sid

    def stream_use_endpoint(self, text):
        if not self.get_template_audio(text):
            synthesis_input = texttospeech.SynthesisInput(text=text)
            response = self.client.synthesize_speech(
                input=synthesis_input, voice=self.voice, audio_config=self.audio_config
            )
            audio = AudioSegment.from_file(
                io.BytesIO(response.audio_content), format="mp3"
            )
            audio_payload = self.trans4twilio(audio)
            out_data = self.get_twilio_media_stream(audio_payload, self.stream_sid)
            self.audio_queue.put((text, out_data), block=False)

    def get_template_audio(self, text):
        flag = False
        if text == "INITIAL":
            # 無音をqueueに入れる
            audio = AudioSegment.silent(duration=0.2)
            audio_payload = self.trans4twilio(audio)
            out_data = self.get_twilio_media_stream(audio_payload, self.stream_sid)
            self.audio_queue.put((text, out_data), block=False)
            flag = True
        elif text == "FILLER":
            filler_text = random.choice(
                ["承知しました。", "はい", "少々お待ちください。"]
            )
            self.stream_use_endpoint(filler_text)
            flag = True
        return flag


class AzureTTSBridge(BaseTTSBridge):
    def __init__(self):
        super().__init__()
        api_key = os.getenv("AZURE_API_KEY")
        region = os.getenv("AZURE_REGION")

        self.config = speechsdk.SpeechConfig(subscription=api_key, region=region)
        self.config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
        )
        self.client = speechsdk.SpeechSynthesizer(
            speech_config=self.config, audio_config=None
        )

    def set_connect_info(self, stream_sid):
        self.stream_sid = stream_sid

    def stream_use_endpoint(self, text):
        try:
            if not self.get_template_audio(text):
                text = self.adjust_text(text)
                # 「。」を破線（break）に変換して無音を挿入
                text_with_breaks = text.replace("。", "。<break time='500ms'/>")
                ssml = f"""
                <speak version='1.0' xml:lang='ja-JP'>
                    <voice xml:lang='ja-JP' name='ja-JP-NanamiNeural' style='customerservice'>
                        <prosody rate='+10%'>
                            {text_with_breaks}
                        </prosody>
                    </voice>
                </speak>
                """
                result = self.client.speak_ssml_async(ssml).get()
                audio = AudioSegment.from_file(io.BytesIO(result.audio_data), format="wav")
                audio = audio.set_frame_rate(8000)
                audio_payload = self.trans4twilio(audio)
                out_data = self.get_twilio_media_stream(audio_payload, self.stream_sid)
                self.audio_queue.put((text, out_data), block=False)
        except Exception as e:
            logger.warning(f"AzureTTSBridge: {e}")
            
    def get_template_audio(self, text):
        flag = False
        audiofile_candidates = list(template_dir.glob(f"{text.lower()}*.wav"))
        logger.info(f"audiofile_candidates: {audiofile_candidates}") 
        if len(audiofile_candidates) > 0:
            audiofile = random.choice(audiofile_candidates)
            logger.info(audiofile)
            audio = AudioSegment.from_file(audiofile, format="wav")
            audio = audio.set_frame_rate(8000)
            audio_payload = self.trans4twilio(audio)
            out_data = self.get_twilio_media_stream(audio_payload, self.stream_sid)
            self.audio_queue.put((text, out_data), block=False)
            flag = True
        return flag


# OpenAITTSBridgeクラス
class OpenAITTSBridge(BaseTTSBridge):
    def __init__(self):
        super().__init__()
        self.client = OpenAI()
        self.headers = {}

    def set_connect_info(self, stream_sid, openai_api_key):
        self.stream_sid = stream_sid
        self.headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        }

    def stream_use_endpoint(self, text):
        data = {
            "model": "tts-1",
            "input": text,
            "voice": "alloy",
        }
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers=self.headers,
            data=json.dumps(data),
            stream=True,
        )
        idx = 0
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                byte_stream = io.BytesIO(chunk)
                try:
                    audio = AudioSegment.from_file(byte_stream, format="mp3")
                except pydub.exceptions.CouldntDecodeError:
                    continue

                audio_payload = self.trans4twilio(audio)
                out_data = self.get_twilio_media_stream(audio_payload, self.stream_sid)
                self.audio_queue.put((text + f"->{idx}", out_data), block=False)
                idx += 1

    def get_template_audio(self, text):
        pass


# VoiceVoxTTSBridgeクラス
class VoiceVoxTTSBridge(BaseTTSBridge):
    tenant = os.getenv("TENANT")
    initial_utterance = os.getenv("INITIAL_UTTERANCE")

    if tenant is None:
        template_wav_dir = Path(__file__).parents[1] / "templates" / "wav"
    else:
        template_wav_dir = (
            Path(__file__).parents[2] / f"tenant_server/{tenant}" / "template" / "wav"
        )

    HOST = os.getenv("VOICEVOX_HOST")
    PORT = os.getenv("VOICEVOX_PORT")
    SERVER_URL = f"http://{HOST}:{PORT}"

    def __init__(self, speaker=0):
        super().__init__()
        self.lock = threading.Lock()
        self.finish_chars = ["。", "、", "!", "！", "?", "？", "\n", "を", "の"]
        self.partial_text = ""
        self.speaker = speaker

    def set_connect_info(self, stream_sid):
        self.stream_sid = stream_sid

    def generate_voice(self, text, speed=1.0) -> bytes:
        params = (
            ("text", text),
            ("speaker", self.speaker),
        )

        query = requests.post(f"{self.SERVER_URL}/audio_query", params=params)
        query_json = query.json()
        query_json["speedScale"] = speed
        try:
            synthesis = requests.post(
                f"{self.SERVER_URL}/synthesis",
                headers={"Content-Type": "application/json"},
                params=params,
                data=json.dumps(query_json),
            )
        except BaseException as e:
            logger.error(f"Failed to generate voice: {e}")
            return b""
        voice = synthesis.content
        return voice

    def stream_use_endpoint(self, text):
        logger.info(f"Got text: {text}")
        with self.lock:
            self.partial_text += text
            audio = self._get_template_audio(text)
            if audio is not None:
                audio = audio.set_frame_rate(8000)
                audio_payload = self.trans4twilio(audio)
                out_data = self.get_twilio_media_stream(audio_payload, self.stream_sid)
                self.audio_queue.put((text, out_data), block=False)
                self.partial_text = ""
            else:
                if any(char in self.partial_text for char in self.finish_chars):
                    text = self.adjust_text(self.partial_text)
                    voice = self.generate_voice(text)
                    # audio = AudioSegment.from_file(io.BytesIO(voice), format="wav")
                    # # resample to 8kHz
                    # audio = audio.set_frame_rate(8000)
                    audio = self._load_audio(io.BytesIO(voice), format="wav")
                    audio_payload = self.trans4twilio(audio)
                    out_data = self.get_twilio_media_stream(
                        audio_payload, self.stream_sid
                    )
                    logger.info(f"VoiceVoxTTSBridge: synthesize {text}")

                    self.audio_queue.put((text, out_data), block=False)
                    self.partial_text = ""

    def _load_audio(self, path, format=None):
        audio = AudioSegment.from_file(path, format=format)
        audio = audio.set_frame_rate(8000)
        return audio

    def _get_template_audio(self, text):
        audio = None
        if text == "FILLER":
            audio_file_candidates = list(self.template_wav_dir.glob("filler_*.wav"))
            audio_file = random.choice(audio_file_candidates)
            audio = self._load_audio(audio_file)
        elif text == "INITIAL":
            audio_file = self.template_wav_dir / f"{self.initial_utterance}.wav"
            audio = self._load_audio(audio_file)
        else:
            pass

        return audio

    def adjust_text(self, text):
        # 02/27などの日付を2月27日などに変換
        # まず月日を抜き出す
        date = re.search(r"\d{1,2}/\d{1,2}", text)
        if date:
            date = date.group()
            month, day = date.split("/")
            month = int(month)
            day = int(day)
            text = text.replace(date, f"{month}月{day}日")

        # 12:30などの時間を12時半などに変換
        # 12:00は12時、12:30は12時半、12:45は12時45分
        time = re.search(r"\d{1,2}:\d{2}", text)
        if time:
            time = time.group()
            hour, minute = time.split(":")
            hour = int(hour)
            minute = int(minute)
            if minute == 0:
                text = text.replace(time, f"{hour}時")
            elif minute == 30:
                text = text.replace(time, f"{hour}時半")
            else:
                text = text.replace(time, f"{hour}時{minute}分")

        return text


class GetTemplateAudio:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.template = json.load(f)

    def __call__(self, text):
        sp_text = text.split("|")

        # initial text or no parroting
        if len(sp_text) == 1:
            try:
                return self.template[sp_text[0]], "", True
            except KeyError:
                return sp_text[0], "", False

        # parroting
        elif len(sp_text) == 2:
            try:
                return self.template[sp_text[0]] + self.template[sp_text[1]], "", True
            except KeyError:
                try:
                    return self.template[sp_text[0]], sp_text[1], True
                except KeyError:
                    print(sp_text[0])
                    return sp_text[0], sp_text[1], False

        # end of conversation
        elif len(sp_text) == 3:
            try:
                return self.template[sp_text[0]], sp_text[1] + sp_text[2], True
            except KeyError:
                return sp_text[0], sp_text[1] + sp_text[2], False
        else:
            raise ValueError("Invalid text format")