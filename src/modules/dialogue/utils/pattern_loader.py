# src/config/pattern_loader.py
import json
import os
from typing import Dict, List, Tuple

# 探索範囲はこのディレクトリ以下
src_dir = os.path.dirname(os.path.abspath(__file__))

class PatternLoader:
    def __init__(self):
        self.patterns_dir = os.path.join(src_dir, 'template_intents')
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> List[Tuple[str, Dict]]:
        """すべてのパターンファイルを読み込む"""
        patterns = []
        for filename in os.listdir(self.patterns_dir):
            if filename.endswith('.json'):
                with open(os.path.join(self.patterns_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    patterns.append((data['initial_message'], data['scene_intents']))
        return patterns

    def get_pattern(self, index: int = 0) -> Tuple[str, Dict]:
        """指定されたインデックスのパターンを取得"""
        if 0 <= index < len(self.patterns):
            return self.patterns[index]
        raise IndexError(f"Pattern index {index} is out of range")

    def add_pattern(self, initial_message: str, intents: dict):
        """新しいパターンを追加して保存"""
        pattern_number = len(self.patterns) + 1
        filename = f"pattern{pattern_number}.json"
        
        data = {
            "initial_message": initial_message,
            "intents": intents,
        }
        
        with open(os.path.join(self.patterns_dir, filename), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        self.patterns = self._load_patterns()