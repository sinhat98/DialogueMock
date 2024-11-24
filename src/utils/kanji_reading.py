from pykakasi import kakasi

kakasi_instance = kakasi()
# モードの設定：J(Kanji) to H(Hiragana)
kakasi_instance.setMode('J', 'H') 

# 変換して出力
conv = kakasi_instance.getConverter()

def get_reading(text: str) -> str:
    return conv.do(text)
