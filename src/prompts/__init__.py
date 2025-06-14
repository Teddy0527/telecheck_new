"""
プロンプト統合モジュール（リファクタリング版）
"""

from .transcription_prompts import TRANSCRIPTION_PROMPTS
from .basic_check_prompts import BASIC_CHECK_PROMPTS
from .advanced_check_prompts import ADVANCED_CHECK_PROMPTS
from .manner_check_prompts import MANNER_CHECK_PROMPTS

# 統合プロンプト辞書クラス（遅延ロード対応）
class _SystemPromptsDict:
    """システムプロンプト統合辞書（遅延ロード対応）"""
    
    def __init__(self):
        self.transcription = TRANSCRIPTION_PROMPTS
        self.basic = BASIC_CHECK_PROMPTS
        self.advanced = ADVANCED_CHECK_PROMPTS
        self.manner = MANNER_CHECK_PROMPTS
    
    def __getitem__(self, key):
        # 各辞書から順次検索
        for prompts_dict in [self.transcription, self.basic, self.advanced, self.manner]:
            if key in prompts_dict:
                return prompts_dict[key]
        raise KeyError(f"プロンプト '{key}' は見つかりません。")
    
    def __contains__(self, key):
        for prompts_dict in [self.transcription, self.basic, self.advanced, self.manner]:
            if key in prompts_dict:
                return True
        return False
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
    
    def keys(self):
        all_keys = []
        for prompts_dict in [self.transcription, self.basic, self.advanced, self.manner]:
            all_keys.extend(prompts_dict.keys())
        return all_keys

# 全プロンプトを統合（後方互換性のため）
SYSTEM_PROMPTS = _SystemPromptsDict()

# ベストプラクティス機能の遅延ロード
def get_teleapo_principles():
    """テレアポ品質チェックの基本原則を取得（遅延ロード）"""
    try:
        from src.quality_check.best_practices import TELEAPO_PRINCIPLES
        return TELEAPO_PRINCIPLES
    except ImportError:
        return {}

def get_quality_check_standards():
    """品質チェック項目別の標準を取得（遅延ロード）"""
    try:
        from src.quality_check.best_practices import QUALITY_CHECK_STANDARDS
        return QUALITY_CHECK_STANDARDS
    except ImportError:
        return {}

def get_judgment_instruction_proxy(check_item: str):
    """判定指示を取得（遅延ロードプロキシ）"""
    try:
        from src.quality_check.best_practices import get_judgment_instruction
        return get_judgment_instruction(check_item)
    except ImportError:
        return f"チェック項目「{check_item}」の基準は利用できません。"

def get_all_principles_proxy():
    """全ての基本原則をテキストとして取得（遅延ロードプロキシ）"""
    try:
        from src.quality_check.best_practices import get_all_principles
        return get_all_principles()
    except ImportError:
        return ""

# 便利関数をエクスポート
__all__ = [
    'SYSTEM_PROMPTS',
    'TRANSCRIPTION_PROMPTS',
    'BASIC_CHECK_PROMPTS', 
    'ADVANCED_CHECK_PROMPTS',
    'MANNER_CHECK_PROMPTS',
    'get_teleapo_principles',
    'get_quality_check_standards',
    'get_judgment_instruction_proxy', 
    'get_all_principles_proxy'
] 