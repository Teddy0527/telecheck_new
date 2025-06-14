"""
OpenAI APIクライアント - 品質チェック専用
"""

from openai import OpenAI
import streamlit as st
import time
from src.config import config


def init_openai_client():
    """OpenAI クライアントを初期化（品質チェック専用）"""
    try:
        if not config.openai_api_key:
            st.markdown("""
            <div class="error-box">
            ❌ OpenAI APIキーが設定されていません。
            <br>・ローカル環境: .envファイルにOPENAI_API_KEYを設定
            <br>・Streamlit Share: シークレット設定で以下のいずれかの形式で設定してください
            <br>　1. openai.api_key
            <br>　2. OPENAI_API_KEY
            <br>　3. api_keys.openai
            </div>
            """, unsafe_allow_html=True)
            st.stop()
        
        try:
            client = OpenAI(api_key=config.openai_api_key)
            
            # 軽量な接続テスト
            try:
                test_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1,
                    temperature=0
                )
                st.success("✅ OpenAI APIに正常に接続しました")
                return client
                
            except Exception as connection_error:
                st.warning(f"⚠️ 接続テストは失敗しましたが、クライアントを作成しました: {str(connection_error)}")
                return client
                
        except Exception as e:
            st.markdown(f"""
            <div class="error-box">
            ❌ OpenAI API接続エラー: {str(e)}
            </div>
            """, unsafe_allow_html=True)
            st.stop()
            
    except Exception as e:
        st.markdown(f"""
        <div class="error-box">
        ❌ OpenAI クライアントの初期化エラー: {str(e)}
        </div>
        """, unsafe_allow_html=True)
        st.stop()


def chat_with_retry(client, system_prompt, user_prompt, temperature=0.0, model="gpt-4o-mini", max_retries=3, response_format=None):
    """OpenAI Chat APIを使用してプロンプトの応答を取得（リトライ機能付き）"""
    retry_count = 0
    while retry_count < max_retries:
        try:
            params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature
            }
            if response_format:
                params["response_format"] = response_format

            response = client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                st.markdown(f"""
                <div class="error-box">
                ❌ APIリクエストに失敗しました（{max_retries}回試行）: {str(e)}
                </div>
                """, unsafe_allow_html=True)
                return None
            st.markdown(f"""
            <div class="warning-box">
            ⚠️ APIリクエストに失敗しました。リトライします ({retry_count}/{max_retries})...
            </div>
            """, unsafe_allow_html=True)
            time.sleep(1)

# 以下は互換性のため残しておくが、新しい話者分離機能ではAssemblyAIを使用
def transcribe_audio(audio_file, client):
    """音声ファイルを文字起こし（従来のWhisper API）"""
    st.warning("⚠️ この機能は非推奨です。話者分離機能付きの文字起こしを使用してください。")
    
    import tempfile
    tmp_file_path = None
    try:
        # 処理ステータス表示
        status_msg = st.empty()
        status_msg.markdown("""
        <div class="info-box">
        🎤 音声ファイルを文字起こし中です。これには数分かかる場合があります...
        </div>
        """, unsafe_allow_html=True)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_file.getvalue())
            tmp_file_path = tmp_file.name
        
        with open(tmp_file_path, "rb") as audio:
            try:
                transcript = client.audio.transcriptions.create(
                    file=audio,
                    model="whisper-1",
                    language="ja",
                    response_format="text"
                )
                
                # 完了表示をクリア
                status_msg.empty()
                return transcript
                
            except Exception as e:
                status_msg.markdown(f"""
                <div class="error-box">
                ❌ 文字起こし処理に失敗しました: {str(e)}
                </div>
                """, unsafe_allow_html=True)
                st.write(f"DEBUG: 文字起こしエラー詳細: {str(e)}")
                return None
                
    finally:
        # 一時ファイルの削除
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)