"""
AssemblyAI APIクライアント - 話者分離機能付き文字起こし
"""

import os
import assemblyai as aai
import streamlit as st
import tempfile
import time
from typing import Dict, List, Optional
from src.config import config
from src.api.openai_client import chat_with_retry


def init_assemblyai_client():
    """AssemblyAI クライアントを初期化"""
    try:
        if not config.assemblyai_api_key:
            st.markdown("""
            <div class="error-box">
            ❌ AssemblyAI APIキーが設定されていません。
            <br>・ローカル環境: .envファイルにASSEMBLYAI_API_KEYを設定
            <br>・Streamlit Share: シークレット設定で以下のいずれかの形式で設定してください
            <br>　1. assemblyai.api_key
            <br>　2. ASSEMBLYAI_API_KEY
            <br>　3. api_keys.assemblyai
            </div>
            """, unsafe_allow_html=True)
            st.stop()
        
        # AssemblyAI設定
        aai.settings.api_key = config.assemblyai_api_key
        
        # 接続テスト
        try:
            transcriber = aai.Transcriber()
            st.success("✅ AssemblyAI APIに正常に接続しました")
            return transcriber
        except Exception as connection_error:
            st.warning(f"⚠️ 接続テストは失敗しましたが、クライアントを作成しました: {str(connection_error)}")
            return aai.Transcriber()
            
    except Exception as e:
        st.markdown(f"""
        <div class="error-box">
        ❌ AssemblyAI クライアントの初期化エラー: {str(e)}
        </div>
        """, unsafe_allow_html=True)
        st.stop()


def transcribe_with_speaker_diarization(audio_file, transcriber, on_progress=None) -> Optional[Dict]:
    """音声ファイルを話者分離付きで文字起こし（非同期ポーリング対応）"""
    tmp_file_path = None
    
    try:
        # ファイルサイズ情報取得
        file_info = config.get_file_size_info(audio_file.size)
        
        # 一時ファイル作成
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # AssemblyAI設定
        transcript_config = aai.TranscriptionConfig(
            speaker_labels=True,
            speakers_expected=config.default_speakers_expected,
            language_code=config.default_language
        )
        
        # 文字起こしジョブを非同期で投入
        if on_progress:
            on_progress("文字起こしジョブをサーバーに送信中...")
        transcript = transcriber.submit(tmp_file_path, config=transcript_config)
        if on_progress:
            on_progress(f"ジョブ投入完了 (ID: {transcript.id})。完了までポーリングします。")

        # ポーリングループで完了を待つ
        polling_interval = 3  # 3秒ごとにステータス確認
        timeout = 1800  # 30分でタイムアウト
        start_time = time.time()
        spinner_frames = ["⠟", "⠯", "⠷", "⠾", "⠽", "⠻"]
        spinner_index = 0

        while transcript.status not in [aai.TranscriptStatus.completed, aai.TranscriptStatus.error]:
            # タイムアウトチェック
            if time.time() - start_time > timeout:
                st.error("文字起こし処理がタイムアウトしました。")
                return None
            
            time.sleep(polling_interval)
            
            # 最新のステータスを取得
            transcript = aai.Transcript.get_by_id(transcript.id)
            
            # UI更新コールバック
            if on_progress:
                spinner_frame = spinner_frames[spinner_index % len(spinner_frames)]
                on_progress(f"{spinner_frame} 文字起こし処理中... (ステータス: {transcript.status})")
                spinner_index += 1
        
        # エラーチェック
        if transcript.status == aai.TranscriptStatus.error:
            st.error(f"文字起こしエラー: {transcript.error}")
            return None
        
        if on_progress:
            on_progress("文字起こし完了。結果を処理中...")

        # 結果を構造化して返す
        result = {
            "full_text": transcript.text,
            "utterances": transcript.utterances,
            "speakers": _extract_speakers(transcript.utterances),
            "raw_transcript": transcript,
            "file_info": file_info
        }
        
        return result
        
    except Exception as e:
        st.error(f"文字起こし処理中に予期せぬエラーが発生しました: {str(e)}")
        return None
        
    finally:
        # 一時ファイルの削除
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def _extract_speakers(utterances) -> Dict[str, List[str]]:
    """話者別に発言を整理"""
    speakers = {}
    
    for utterance in utterances:
        speaker = utterance.speaker
        if speaker not in speakers:
            speakers[speaker] = []
        speakers[speaker].append(utterance.text)
    
    return speakers


def format_transcript_with_speakers(transcript_result: Dict, teleapo_speaker: str, checker_str: str = "", openai_client=None) -> str:
    """話者分離結果をフォーマット（Google Sheets保存用）- 固有名詞置換+意味のあるラベル対応"""
    if not transcript_result or not transcript_result.get("utterances"):
        return "文字起こし結果が取得できませんでした。"
    
    # ファイル情報
    file_info = transcript_result.get("file_info", {})
    size_info = f"（ファイルサイズ: {file_info.get('size_mb', 0):.1f}MB）" if file_info else ""
    
    # 話者ラベルのマッピング作成
    def get_speaker_label(speaker: str) -> str:
        """話者の技術的ラベル（A, B）を意味のあるラベルに変換"""
        if speaker == teleapo_speaker:
            return "テレアポ担当者"
        else:
            return "顧客"
    
    # 全体の会話を構築（意味のあるラベルを使用）
    raw_conversation = ""
    for utterance in transcript_result["utterances"]:
        speaker_label = get_speaker_label(utterance.speaker)
        raw_conversation += f"[{speaker_label}] {utterance.text}\n"
    
    # 最終的なフォーマット
    final_output = f"=== 全体の会話 {size_info} ===\n{raw_conversation}"
    
    return final_output


def format_transcript_for_quality_check(transcript_result: Dict, teleapo_speaker: str, checker_str: str = "", openai_client=None) -> str:
    """品質チェック用のフォーマット（[テレアポ担当者]/[顧客]ラベル使用+固有名詞置換済み）"""
    if not transcript_result or not transcript_result.get("utterances"):
        return "文字起こし結果が取得できませんでした。"
    
    # 話者ラベルのマッピング作成
    def get_speaker_label(speaker: str) -> str:
        if speaker == teleapo_speaker:
            return "テレアポ担当者"
        else:
            return "顧客"
    
    # 品質チェック用フォーマット
    formatted_text = ""
    for utterance in transcript_result["utterances"]:
        speaker_label = get_speaker_label(utterance.speaker)
        formatted_text += f"[{speaker_label}] {utterance.text}\n"
    
    # 固有名詞の置換処理（品質チェック用）
    if openai_client and checker_str:
        try:
            replace_prompt = f"""以下の会話記録に登場する可能性のある固有名詞（特に「{checker_str}」）を「テレアポ担当者」に統一してください。会話の他の部分は変更しないでください。

会話記録：
{{text}}"""
            cleaned_text = chat_with_retry(openai_client, replace_prompt, formatted_text)
            
            if cleaned_text and cleaned_text.strip():
                return cleaned_text
            else:
                return formatted_text
                
        except Exception as e:
            st.warning(f"⚠️ 品質チェック用の固有名詞置換でエラー: {str(e)}")
            return formatted_text
    
    return formatted_text


def get_teleapo_speaker_content(transcript_result: Dict, teleapo_speaker: str) -> str:
    """テレアポ担当者の発言のみを取得（品質チェック用）"""
    if not transcript_result or not transcript_result.get("utterances"):
        return ""
    
    teleapo_statements = []
    for utterance in transcript_result["utterances"]:
        if utterance.speaker == teleapo_speaker:
            teleapo_statements.append(utterance.text)
    
    return "\n".join(teleapo_statements) 