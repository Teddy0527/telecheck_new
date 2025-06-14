"""
新しい品質チェックのコアロジック
"""

import json
import re
import streamlit as st
from typing import Dict, Optional

from src.api.openai_client import chat_with_retry
from .prompts import SYSTEM_PROMPT, extract_checker_name


class QualityChecker:
    """
    テレアポの品質チェックを行い、結果を構造化されたJSONとして返すクラス。
    単一のAPI呼び出しで全項目を評価し、結果を整形する。
    """
    
    # スプレッドシートのヘッダー順を定義
    SPREADSHEET_HEADERS = [
        # 基本情報
        "テレアポ担当者名", "報告まとめ",
        # スプレッドシート専用項目
        "ガチャ切りされた△",
        # チェック項目（プロンプトのキーと一致）
        "社名や担当者名を名乗らない", "アプローチで販売店名、ソフト名の先出し", "同業他社の悪口等",
        "運転中や電車内でも無理やり続ける", "2回断られても食い下がる", "暴言・悪口・脅迫・逆上",
        "情報漏洩", "共犯（教唆・幇助）", "通話対応（無言電話／ガチャ切り）", "呼び方", "ロングコール",
        "当社の電話お断り", "しつこい・何度も電話がある", "お客様専用電話番号と言われる", "口調を注意された",
        "怒らせた", "暴言を受けた", "通報する", "営業お断り",
        "事務員に対して代表者のことを「社長」「オーナー」「代表」", "一人称が「僕」「自分」「俺」",
        "「弊社」のことを「うち」「僕ら」と言う", "謝罪が「すみません」「ごめんなさい」",
        "口調や態度が失礼", "会話が成り立っていない", "残債の「下取り」「買い取り」トーク",
        "嘘・真偽不明", "その他問題"
    ]

    def __init__(self, client):
        """
        Args:
            client: 初期化済みのOpenAIクライアント。
        """
        self.client = client

    def run_check(self, text_input: str, checkers: list = None) -> Optional[str]:
        """
        品質チェックを実行し、UIを更新しながら結果を返すラッパーメソッド。
        インタラクティブな単一チェック用。

        Args:
            text_input: 分析対象の会話テキスト。
            checkers: テレアポ担当者リスト。

        Returns:
            整形済みの結果を含むJSON文字列。エラー時はエラー情報を含むJSON文字列。
        """
        if not text_input or not text_input.strip():
            st.warning("入力テキストが空です。")
            return self._create_error_fallback("入力テキストが空です。")

        status_text = st.empty()
        progress_bar = st.progress(0)

        try:
            # UI更新とコアロジックの呼び出し
            status_text.markdown("**ステップ 1/2**: AIによる分析を実行中...")
            progress_bar.progress(0.25)
            
            # コアロジックの呼び出し
            result_dict = self.check(text_input, checkers)
            
            status_text.markdown("**ステップ 2/2**: 結果を整形中...")
            progress_bar.progress(0.75)
            
            # JSON文字列に変換
            final_json = json.dumps(result_dict, ensure_ascii=False, indent=2)

            progress_bar.progress(1.0)
            status_text.success("✅ 品質チェックが完了しました。")
            
            return final_json

        except Exception as e:
            st.error(f"品質チェック実行中にエラーが発生しました: {str(e)}")
            return self._create_error_fallback(str(e))
        finally:
            # UI要素をクリア
            progress_bar.empty()
            status_text.empty()

    def check(self, text_input: str, checkers: list = None) -> Optional[Dict]:
        """
        品質チェックのコアロジック。UIコンポーネントを含まない。
        バッチ処理から呼び出すことを想定。

        Args:
            text_input: 分析対象の会話テキスト。
            checkers: テレアポ担当者リスト。

        Returns:
            整形済みの結果の辞書。エラー時はNone。
        """
        if not text_input or not text_input.strip():
            # バッチ処理では呼び出し元でログを出す想定
            return None

        try:
            checker_name = ""
            if checkers:
                checker_name = extract_checker_name(text_input, checkers, self.client)

            prompt_with_checker = f"この会話のテレアポ担当者は「{checker_name}」です。\\n\\n{SYSTEM_PROMPT}" if checker_name else SYSTEM_PROMPT

            raw_response = self._safe_api_call(prompt_with_checker, text_input)
            if not raw_response or raw_response == "チェック失敗":
                raise Exception("AIからの応答が空か、失敗しました。")

            parsed_result = self._parse_json_response(raw_response)
            final_result = self._format_for_spreadsheet(parsed_result, text_input, checker_name)
            
            return final_result
        except Exception as e:
            # エラーは呼び出し元で処理する
            st.error(f"チェック処理中にエラー: {str(e)}") # Streamlitコンテキストがある場合に備える
            raise e

    def _safe_api_call(self, system_prompt: str, user_prompt: str) -> str:
        """安全なAPI呼び出し。JSONモードを有効にする。"""
        return chat_with_retry(
            self.client,
            system_prompt,
            user_prompt,
            response_format={"type": "json_object"}
        )

    def _parse_json_response(self, response: str) -> Dict[str, str]:
        """AIからの応答（JSON文字列）をパースする。"""
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            # st.warningはUIに影響するので、ここではログ出力に留めるか、
            # 呼び出し元でハンドリングする。今回はエラーを上に投げる。
            raise Exception(f"JSON解析エラー: {e}。応答: {response}")

    def _format_for_spreadsheet(self, parsed_result: Dict[str, str], original_text: str, checker_name: str = "") -> Dict[str, str]:
        """パースされた結果を最終的なスプレッドシート形式に整形する。"""
        final_result = {header: "" for header in self.SPREADSHEET_HEADERS}

        # AIの判定結果をコピー
        for key, value in parsed_result.items():
            if key in final_result:
                final_result[key] = value

        # 担当者名が抽出されていれば設定
        if checker_name:
            final_result["テレアポ担当者名"] = checker_name

        # 報告まとめを作成
        final_result["報告まとめ"] = self._create_summary_report(final_result)
        
        # ガチャ切り検出（フォールバック）
        if self._detect_gachakiri(original_text):
            final_result["ガチャ切りされた△"] = "問題あり"
        
        return final_result

    def _create_summary_report(self, result: Dict[str, str]) -> str:
        """問題あり項目から報告まとめを生成する。"""
        problems = [key for key, value in result.items() if value == "問題あり"]
        
        if problems:
            # 報告まとめ自身や担当者名、ガチャ切りは除外
            problem_items = [p for p in problems if p not in ["報告まとめ", "テレアポ担当者名", "ガチャ切りされた△"]]
            if problem_items:
                return f"問題あり項目: {', '.join(problem_items[:5])}"
        
        return "特に問題は検出されませんでした"

    def _detect_gachakiri(self, text: str) -> bool:
        """元のテキストからガチャ切りを検出する（フォールバック用）。"""
        gachakiri_patterns = [
            r'ガチャ切り', r'電話を切られ', r'一方的に切', r'途中で切',
            r'会話が途中で終了', r'通話が切断', r'突然終了', r'無言で切'
        ]
        # 正常終了パターン（これらがあればガチャ切りとしない）
        normal_end_patterns = [
            r'失礼[しい]たします', r'ありがとうございました', r'お時間をいただき'
        ]

        if any(re.search(p, text, re.IGNORECASE) for p in normal_end_patterns):
            return False
        
        return any(re.search(p, text, re.IGNORECASE) for p in gachakiri_patterns)

    def _create_error_fallback(self, error_message: str) -> str:
        """エラー発生時のフォールバックJSONを作成する。"""
        fallback_result = {header: "" for header in self.SPREADSHEET_HEADERS}
        fallback_result["テレアポ担当者名"] = "処理エラー"
        fallback_result["報告まとめ"] = f"処理エラー: {error_message}"
        return json.dumps(fallback_result, ensure_ascii=False, indent=2) 