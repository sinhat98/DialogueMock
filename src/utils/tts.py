import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
# from src.utils import setup_custom_logger
import logging
load_dotenv()
from src.modules.dialogue.utils.template import tts_label2text

from src.utils import get_custom_logger

logger = get_custom_logger(__name__)
# logger = setup_custom_logger(__name__)

def generate_audio(text: str, output_file_path: str, voice_name: str = 'ja-JP-NanamiNeural', style: str = 'customerservice', rate: str = '+10%') -> str:
    """
    指定されたテキストを音声に変換し、WAVファイルとして保存
    Args:
        text: Text to be converted to speech
        output_file_path: Path where the audio file will be saved
        voice_name: Voice model to be used for speech synthesis
        style: Speaking style to be used for the voice synthesis (optional)
        rate: Speaking rate to be used for the voice synthesis (optional)
    Returns:
        Path of the saved audio file, or an empty string if failed
    """
    # 各種パラメータの設定
    api_key = os.getenv("AZURE_API_KEY")
    region = os.getenv("AZURE_REGION")

    if not api_key or not region:
        logger.error("AZURE_API_KEYおよびAZURE_REGIONを環境変数として設定してください。")
        return ""

    # Azure Speech SDK の設定
    speech_config = speechsdk.SpeechConfig(subscription=api_key, region=region)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
    )

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    # TTSリクエストを作成
    ssml = f"""
    <speak version='1.0' xml:lang='ja-JP'>
        <voice name='{voice_name}' style='{style}'>
            <prosody rate='{rate}'>
                {text}
            </prosody>
        </voice>
    </speak>
    """

    # 音声合成を実行
    result = synthesizer.speak_ssml_async(ssml).get()

    # 結果の確認
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        logger.info("音声合成が完了しました。")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        logger.error(f"音声合成がキャンセルされました: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            logger.error(f"エラー詳細: {cancellation_details.error_details}")
        return ""

    # 合成された音声データをWAVファイルとして保存
    stream = speechsdk.AudioDataStream(result)
    stream.save_to_wav_file(output_file_path)
    
    return output_file_path

if __name__ == "__main__":
    from pathlib import Path
    from src.utils.kanji_reading import get_reading
    
    output_dir = Path(__file__).parents[1] / "modules/dialogue/utils/template_audio"
    voice_name = 'ja-JP-NanamiNeural'  # 利用する音声モデルを指定
    style = 'customerservice'  # 話し方のスタイルを指定
    rate = '+10%'  # 話速を指定（この例では20%速く）
    # for key, text in wav_and_text_dict.items():
    #     output_file_path = output_dir / f"{key}.wav"
    #     output_file_path = str(output_file_path)
    #     audio_path = generate_audio(text, output_file_path, voice_name, style, rate)
    #     if audio_path:
    #         logger.info(f"音声ファイルは {audio_path} に保存されました。")
    wav_and_text_dict = tts_label2text
    
    
    # wav_and_text_dict = {
    #     "initial_1": "SHIFT渋谷店です。",
    #     "initial_2": "SHIFT渋谷店です。ご用件をおっしゃってください",
    #     # "select": "<break time='800ms'/>対話パターンを1から4の中から選択してください。回答は「1番」<break time='100ms'/>のようにはっきりとおっしゃってください",
    #     # "initial": "<break time='800ms'/>お電話ありがとうございます新規のご予約を承ります。",
    #     # FAQに回答がなかった場合のbotの返答
    #     #"applogize_1": "申し訳ございません。うまく聞き取れませんでした",
    #     #"applogize_2": "申し訳ございません。お答えできません",
    #     # "date_1": "ご希望の日付をお伺いしてもよろしいでしょうか？",
    #     # "time_1": "ご希望の時間をお伺いしてもよろしいでしょうか？",
    #     # "n_person_1": "ご来店人数をお伺いしてもよろしいでしょうか？",
    #     # "name_1": "ご来店される代表者のお名前をお伺いしてもよろしいでしょうか？",
    # }
    for key, text in wav_and_text_dict.items():
        if not isinstance(key, str):
            key_str = key.value.lower()
        else:
            key_str = key.lower()
        if "initial" in key_str:
            rate = '25%'
            text = f"<break time='500ms'/> {text}"
        output_file_path = output_dir / f"{key_str}.wav"
        output_file_path = str(output_file_path)
        # text = get_reading(text)
        logger.info(f"key: {key}, text: {text}")
        audio_path = generate_audio(text, output_file_path, voice_name, style, rate)
        if audio_path:
            logger.info(f"音声ファイルは {audio_path} に保存されました。")