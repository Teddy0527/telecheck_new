"""
バッチ処理用のワークフロー管理モジュール（リファクタリング版）
新しい品質チェック構造に対応
"""

import streamlit as st
import time
import re
import json
from src.api.sheets_client import get_target_rows, update_quality_check_results
from src.common.error_handler import ErrorHandler, safe_execute
from src.quality_check.core import QualityChecker
from typing import Optional


def run_quality_check_batch(sheets_client, openai_client, progress_bar, status_text, max_rows, batch_size, checkers):
    """
    スプレッドシートからデータを読み込み、品質チェックを実行して結果を書き込む。
    checkers引数を追加。
    """
    try:
        # 処理対象の行を取得
        header_row, target_rows = get_target_rows(sheets_client, max_rows)
        
        if not target_rows:
            st.markdown('<div class="info-box">処理対象のデータがありません</div>', unsafe_allow_html=True)
            return
        
        # ヘッダーマップを作成
        header_map = _create_header_map(header_row)
        
        # 進捗表示の初期化
        _initialize_progress_display(progress_bar, status_text, len(target_rows))
        
        # メトリクス表示
        metrics_containers = _setup_metrics_display(len(target_rows))
        
        # スプレッドシートを取得
        spreadsheet = sheets_client.open("テレアポチェックシート")
        worksheet = spreadsheet.worksheet("Difyテスト")
        
        # 新しい品質チェッカーをインスタンス化
        quality_checker = QualityChecker(openai_client)
        
        # バッチ処理実行
        _process_batch(
            target_rows, quality_checker, worksheet, header_map,
            batch_size, progress_bar, status_text, metrics_containers, checkers
        )
        
    except Exception as e:
        ErrorHandler.handle_error(e, "バッチ処理", show_details=True)


def _is_conversation_too_short(raw_transcript: str, min_utterances: int = 3) -> bool:
    """
    会話が品質チェックを行うには短すぎるかどうかを判定する。
    """
    if not raw_transcript:
        return True
    utterances = re.findall(r'\[(?:テレアポ担当者|顧客)\]\s*\S+', raw_transcript)
    return len(utterances) < min_utterances

def _create_no_conversation_result(quality_checker: QualityChecker) -> str:
    """「会話記録なし」という結果のJSON文字列を作成する。"""
    result_dict = {header: "" for header in quality_checker.SPREADSHEET_HEADERS}
    result_dict["報告まとめ"] = "会話記録なし"
    return json.dumps(result_dict, ensure_ascii=False, indent=2)


def _create_header_map(header_row):
    """ヘッダー行からカラムマップを作成"""
    header_map = {}
    for i, header in enumerate(header_row):
        if header.strip():
            header_map[header.strip()] = i + 1  # gspreadは1ベース
    return header_map


def _initialize_progress_display(progress_bar, status_text, total_rows):
    """進捗表示を初期化"""
    progress_bar.progress(0)
    status_text.markdown(
        f"<p style='text-align: center; font-weight: 500;'>🔍 品質チェック開始: {total_rows}件を処理します</p>", 
        unsafe_allow_html=True
    )


def _setup_metrics_display(total_rows):
    """メトリクス表示を設定"""
    st.markdown("### 📊 処理状況")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        processed_container = st.empty()
    with col2:
        success_container = st.empty()
    with col3:
        total_container = st.empty()
        total_container.markdown(f"""
        <div class="metric-card">
          <h3>📋 総件数</h3>
          <p>{total_rows}</p>
        </div>
        """, unsafe_allow_html=True)
    
    return {
        'processed': processed_container,
        'success': success_container,
        'total': total_container
    }


def _process_batch(target_rows, quality_checker, worksheet, header_map,
                  batch_size, progress_bar, status_text, metrics_containers, checkers):
    """実際のバッチ処理を実行（新しいQualityCheckerを使用）"""
    results_batch = []
    total_processed = 0
    total_success = 0
    
    for i, (row_index, row) in enumerate(target_rows):
        try:
            # テキストとファイル名を取得
            raw_transcript = row[0] if row else ""
            if not raw_transcript:
                continue
                
            filename = row[1] if len(row) > 1 else f"行 {row_index}"
            
            # 現在処理中のファイル表示
            current_file = _show_current_processing(filename)
            
            # 会話が短すぎるかチェック
            if _is_conversation_too_short(raw_transcript):
                result_json = _create_no_conversation_result(quality_checker)
                st.info(f"ℹ️ {filename}: 会話記録がほとんどないため、品質チェックをスキップしました。")
            else:
                # 品質チェック実行
                result_json = _execute_quality_check(raw_transcript, quality_checker, checkers)
            
            if result_json:
                results_batch.append((row_index, result_json))
                total_success += 1
            
            # 現在処理中の表示をクリア
            current_file.empty()
            total_processed += 1
            
            # メトリクス更新
            _update_metrics(metrics_containers, total_processed, total_success, len(target_rows))
            
            # バッチサイズに達した場合、または最後の処理の場合にスプレッドシート更新
            if len(results_batch) >= batch_size or i == len(target_rows) - 1:
                if results_batch:
                    _update_spreadsheet_batch(worksheet, header_map, results_batch)
                    results_batch = []
            
            # 進捗更新
            progress = (i + 1) / len(target_rows)
            progress_bar.progress(progress)
            status_text.markdown(
                f"<p style='text-align: center; font-weight: 500;'>{i + 1}/{len(target_rows)} 処理完了</p>", 
                unsafe_allow_html=True
            )
            
        except Exception as e:
            ErrorHandler.handle_error(e, f"行 {row_index} の処理", show_details=False)
            continue


@safe_execute("品質チェック実行")
def _execute_quality_check(raw_transcript: str, quality_checker: QualityChecker, checkers) -> Optional[str]:
    """新しいQualityCheckerを使用して品質チェックを実行し、結果をJSON文字列で返す"""
    result_dict = quality_checker.check(raw_transcript, checkers)
    if result_dict:
        return json.dumps(result_dict, ensure_ascii=False, indent=2)
    return None


def _show_current_processing(filename):
    """現在処理中のファイル名を表示"""
    current_file = st.empty()
    current_file.markdown(f"""
    <div class="info-box">
      🔄 処理中: {filename}
    </div>
    """, unsafe_allow_html=True)
    return current_file


def _update_metrics(metrics_containers, processed, success, total):
    """メトリクス表示を更新"""
    success_rate = (success / processed * 100) if processed > 0 else 0
    
    metrics_containers['processed'].markdown(f"""
    <div class="metric-card">
      <h3>✅ 処理済み</h3>
      <p>{processed}/{total}</p>
    </div>
    """, unsafe_allow_html=True)
    
    metrics_containers['success'].markdown(f"""
    <div class="metric-card">
      <h3>🎯 成功率</h3>
      <p>{success_rate:.1f}%</p>
    </div>
    """, unsafe_allow_html=True)


@safe_execute("スプレッドシート更新")
def _update_spreadsheet_batch(worksheet, header_map, results_batch):
    """バッチ単位でスプレッドシートを更新"""
    batch_status = st.empty()
    batch_status.markdown("""
    <div class="info-box">
      ⏳ Googleスプレッドシートを更新中...
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # 正しいパラメータでupdate_quality_check_results関数を呼び出し
        update_quality_check_results(worksheet, header_map, results_batch)
        time.sleep(1)  # API制限を避けるための待機
        batch_status.empty()
    except Exception as e:
        batch_status.markdown(f"""
        <div class="error-box">
          ❌ スプレッドシート更新エラー: {str(e)}
        </div>
        """, unsafe_allow_html=True)
        time.sleep(2)
        batch_status.empty()
        raise 