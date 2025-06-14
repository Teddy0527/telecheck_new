"""
統一エラーハンドリング
"""

import streamlit as st
import traceback
import json
from typing import Optional, Dict, Any
from functools import wraps


class TeleCheckError(Exception):
    """テレチェック専用例外クラス"""
    pass


class APIError(TeleCheckError):
    """API呼び出しエラー"""
    pass


class ValidationError(TeleCheckError):
    """入力検証エラー"""
    pass


class ProcessingError(TeleCheckError):
    """処理エラー"""
    pass


class ErrorHandler:
    """統一エラーハンドラー"""
    
    @staticmethod
    def handle_error(error: Exception, context: str = "処理中", show_details: bool = False) -> None:
        """エラーを統一的に処理"""
        error_message = str(error)
        error_type = type(error).__name__
        
        # エラータイプに応じた表示
        if isinstance(error, APIError):
            st.error(f"🔌 API接続エラー: {error_message}")
        elif isinstance(error, ValidationError):
            st.warning(f"⚠️ 入力エラー: {error_message}")
        elif isinstance(error, ProcessingError):
            st.error(f"⚙️ 処理エラー: {error_message}")
        else:
            st.error(f"❌ {context}でエラーが発生しました: {error_message}")
        
        # 詳細情報の表示
        if show_details:
            with st.expander("詳細なエラー情報（開発者向け）"):
                st.code(f"エラータイプ: {error_type}")
                st.code(f"エラーメッセージ: {error_message}")
                st.code(traceback.format_exc())
    
    @staticmethod
    def create_error_response(error: Exception, context: str = "処理") -> Dict[str, Any]:
        """エラー時の標準レスポンスを作成"""
        return {
            "success": False,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "context": context
            },
            "data": None
        }
    
    @staticmethod
    def create_success_response(data: Any, message: str = "処理完了") -> Dict[str, Any]:
        """成功時の標準レスポンスを作成"""
        return {
            "success": True,
            "error": None,
            "message": message,
            "data": data
        }


def safe_execute(context: str = "処理", show_details: bool = False):
    """安全実行デコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ErrorHandler.handle_error(e, context, show_details)
                return None
        return wrapper
    return decorator


def validate_input(text: str, min_length: int = 1, context: str = "入力") -> str:
    """入力検証"""
    if not text or not text.strip():
        raise ValidationError(f"{context}が空です")
    
    if len(text.strip()) < min_length:
        raise ValidationError(f"{context}は{min_length}文字以上である必要があります")
    
    return text.strip()


def create_fallback_json(error_message: str = "処理エラー") -> str:
    """統一フォールバックJSON"""
    fallback_data = {
        "テレアポ担当者名": error_message,
        "報告まとめ": [f"システムエラー: {error_message}"],
        "処理状態": "エラー",
        "エラー詳細": error_message,
        "タイムスタンプ": st.session_state.get('current_time', 'unknown')
    }
    
    # 標準的なチェック項目のエラー値設定
    standard_checks = [
        "社名や担当者名を名乗らない",
        "アプローチで販売店名、ソフト名の先出し",
        "同業他社の悪口等",
        "運転中や電車内でも無理やり続ける",
        "2回断られても食い下がる",
        "暴言・悪口・脅迫・逆上",
        "情報漏洩",
        "共犯（教唆・幇助）",
        "通話対応（無言電話／ガチャ切り）",
        "呼び方",
        "ロングコール",
        "当社の電話お断り",
        "しつこい・何度も電話がある",
        "お客様専用電話番号と言われる",
        "口調を注意された",
        "怒らせた",
        "暴言を受けた",
        "通報する",
        "営業お断り"
    ]
    
    for check in standard_checks:
        fallback_data[check] = error_message
    
    return json.dumps(fallback_data, ensure_ascii=False, indent=2) 