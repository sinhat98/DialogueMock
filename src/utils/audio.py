import base64
import wave
import numpy as np

import librosa
import soundfile as sf


def chunk_generator(
    input_file: str, chunk_seconds: float = 0.02, include_silence=True
):
    chunk_count = 0
    with wave.open(input_file, "rb") as wf:
        sample_rate = wf.getframerate()
        chunk_size = int(sample_rate * chunk_seconds)

        while True:
            data = wf.readframes(chunk_size)
            if not data:
                break

            chunk_count += 1

            samples = np.frombuffer(data, dtype=np.int16)

            data = samples.tobytes()

            encoded_chunk = base64.b64encode(data).decode("utf-8")
            # print("chunk_count", chunk_count)
            yield chunk_count, encoded_chunk

    if include_silence:
        # breakしたら無音を送り続ける
        while True:
            chunk_count += 1
            # 0.02秒分の無音データを生成
            samples = np.zeros(int(sample_rate * chunk_seconds), dtype=np.int16)
            data = samples.tobytes()
            encoded_chunk = base64.b64encode(data).decode("utf-8")
            yield chunk_count, encoded_chunk


def load_audio(file_path, sr=16000):
    """
    Load an audio file.

    Parameters:
    - file_path: str - Path to the audio file.
    - sr: int - Target sample rate (default is 16000).

    Returns:
    A tuple containing the audio data and the sample rate.
    """

    data, samplerate = sf.read(file_path)
    data = data[:, 0]
    if samplerate != sr:
        data = librosa.resample(data, orig_sr=samplerate, target_sr=sr)
    else:
        sr = samplerate

    return data, sr
