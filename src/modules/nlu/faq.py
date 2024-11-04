from janome.tokenizer import Tokenizer
from rank_bm25 import BM25Okapi

from pathlib import Path

import gensim
import numpy as np

from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

class BM25FAQ:
    def __init__(self):
        # 質問キーワードと回答のペアを用意（質問ごとに複数の回答を持つ）
        self.faq_dict = {
            "営業時間": [
                "ランチの営業時間は11:00から15:00です",
                "ディナーの営業時間は17:00から23:00です",
                "営業時間は日によって異なる場合がありますので、お問い合わせください"
            ],
            "駐車場": [
                "駐車場は2台まで停められます",
                "近隣にコインパーキングもございます"
            ],
            "席代": [
                "ランチは席代がかかりませんが、ディナーは席代がかかります",
                "ディナータイムの席代はお一人様500円です"
            ],
            "予約": [
                "ランチは予約できません",
                "ディナーのご予約はお電話で承っております"
            ]
        }

        # 質問キーワードのリストを作成
        self.questions = list(self.faq_dict.keys())

        # 日本語の形態素解析器を初期化
        self.tokenizer = Tokenizer()

        # 質問キーワードをトークン化してBM25を初期化
        tokenized_questions = [self.tokenize(question) for question in self.questions]
        self.bm25 = BM25Okapi(tokenized_questions)
    
    def tokenize(self, text):
        # ストップワードを定義
        stop_words = set(['は', 'の', 'が', 'を', 'に', 'で', 'と', 'から', 'まで', 'です', 'ます', 'や', 'について', 'できますか', '必要', 'ありますか', 'ください'])
        
        tokens = [token.surface for token in self.tokenizer.tokenize(text) if token.surface not in stop_words]
        return tokens

    def get_answer(self, query):
        # ユーザーの質問をトークン化
        tokenized_query = self.tokenize(query)
        # BM25でスコアを計算
        scores = self.bm25.get_scores(tokenized_query)
        max_score = max(scores)
        threshold = 0.1  # 閾値を適切に設定

        if max_score > threshold:
            # 最もスコアの高い質問キーワードを取得
            best_match_index = scores.tolist().index(max_score)
            best_question = self.questions[best_match_index]
            # 質問キーワードに対応するすべての回答を取得
            answers = self.faq_dict[best_question]
            # 回答を結合して返す
            return "\n".join(answers)
        else:
            return "申し訳ありませんが、そのご質問にはお答えできません。"



class FastTextFAQ:
    # モデルファイルのパスを指定
    vector_dict_dir = Path(__file__).parent / "asset" / "cc.ja.300.vec.gz"
    binary_model_path = Path(__file__).parent / "asset" / "cc.ja.300.bin"

    def __init__(self):
        # 日本語の形態素解析器を初期化
        self.tokenizer = Tokenizer()

        # モデルをロード
        self.load_model()

        # 質問キーワードと回答のペアを用意（複数の回答を含む）
        self.faq_dict = {
            "営業時間": [
                "ランチの営業時間は11:00から15:00です",
                "ディナーの営業時間は17:00から23:00です",
                "営業時間は日によって異なる場合がありますので、お問い合わせください"
            ],
            "駐車場": [
                "駐車場は2台まで停められます",
                "近隣にコインパーキングもございます"
            ],
            "席代": [
                "ランチは席代がかかりませんが、ディナーは席代がかかります",
                "ディナータイムの席代はお一人様500円です"
            ],
            "予約": [
                "ランチは予約できません",
                "ディナーのご予約はお電話で承っております"
            ]
        }

        # 質問キーワードのリストを作成
        self.questions = list(self.faq_dict.keys())

        # 質問キーワードをベクトル化
        self.question_vectors = [self.vectorize(question) for question in self.questions]

        # 質問キーワードに対応する回答リストの各回答をベクトル化
        self.answer_vectors = {}
        for key in self.faq_dict:
            answers = self.faq_dict[key]
            vectors = [self.vectorize(answer) for answer in answers]
            self.answer_vectors[key] = vectors

    def load_model(self):
        # バイナリ形式のモデルが存在すればロード
        if self.binary_model_path.exists():
            logger.info("Loading FastText model from binary file...")
            self.model = gensim.models.KeyedVectors.load_word2vec_format(str(self.binary_model_path), binary=True)
        else:
            # テキスト形式のモデルをロードしてバイナリ形式で保存
            logger.info("Loading FastText model from text file...")
            self.model = gensim.models.KeyedVectors.load_word2vec_format(str(self.vector_dict_dir), binary=False)
            logger.info("Saving FastText model in binary format for faster loading...")
            self.model.save_word2vec_format(str(self.binary_model_path), binary=True)

    def tokenize(self, text):
        tokens = [token.surface for token in self.tokenizer.tokenize(text)]
        return tokens

    def vectorize(self, text):
        tokens = self.tokenize(text)
        vectors = []
        for token in tokens:
            if token in self.model.key_to_index:
                vectors.append(self.model[token])
            else:
                # 未知語の場合、サブワードの平均でベクトル化
                sub_vectors = []
                for i in range(len(token)):
                    for j in range(i+1, min(i+5, len(token))+1):
                        subword = token[i:j]
                        if subword in self.model.key_to_index:
                            sub_vectors.append(self.model[subword])
                if sub_vectors:
                    sub_vector = np.mean(sub_vectors, axis=0)
                    vectors.append(sub_vector)
        if vectors:
            return np.mean(vectors, axis=0)
        else:
            # ベクトル化できない場合、ゼロベクトルを返す
            return np.zeros(self.model.vector_size)

    def get_answer(self, query):
        query_vector = self.vectorize(query)
        if np.linalg.norm(query_vector) == 0:
            return "申し訳ありませんが、そのご質問にはお答えできません。"

        # 質問キーワードとの類似度計算
        similarities = []
        for vec in self.question_vectors:
            if np.linalg.norm(vec) == 0:
                sim = 0
            else:
                sim = np.dot(query_vector, vec) / (np.linalg.norm(query_vector) * np.linalg.norm(vec))
            similarities.append(sim)
        max_sim = max(similarities)
        threshold = 0.3  # 類似度の閾値を適切に設定

        if max_sim > threshold:
            best_match_index = similarities.index(max_sim)
            best_question = self.questions[best_match_index]
            # 対応する回答リストを取得
            answers = self.faq_dict[best_question]
            answer_vectors = self.answer_vectors[best_question]
            # ユーザーの質問と各回答の類似度を計算
            answer_similarities = []
            for vec in answer_vectors:
                if np.linalg.norm(vec) == 0:
                    sim = 0
                else:
                    sim = np.dot(query_vector, vec) / (np.linalg.norm(query_vector) * np.linalg.norm(vec))
                answer_similarities.append(sim)
            # 最も類似度の高い回答を選択
            max_answer_sim = max(answer_similarities)
            best_answer_index = answer_similarities.index(max_answer_sim)
            best_answer = answers[best_answer_index]
            return best_answer
        else:
            return "申し訳ありませんが、そのご質問にはお答えできません。"

def test_bm25():
    bm25_faq = BM25FAQ()
    queries = [
        "ランチの時間を教えてください",
        "ディナーは何時からですか？",
        "駐車場はありますか？",
        "席料はいくらですか？",
        "予約は可能ですか？"
    ]

    for query in queries:
        answer = bm25_faq.get_answer(query)
        print(f"質問: {query}")
        print(f"回答:\n{answer}\n")
def test_fasttext():
    faq = FastTextFAQ()
    queries = [
        "ランチの時間を教えてください",
        "ディナーは何時からですか？",
        "駐車場はありますか？",
        "席代はいくらですか？",
        "予約は可能ですか？"
    ]

    for query in queries:
        answer = faq.get_answer(query)
        print(f"質問: {query}")
        print(f"回答:\n{answer}\n")


if __name__ == "__main__":
    test_fasttext()

