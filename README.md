# TeleCheck Test - テレアポ品質チェックシステム

## プロジェクト概要

音声ファイルの文字起こしとテレアポ品質チェックを自動化するStreamlitアプリケーションです。
AssemblyAIによる話者分離機能とOpenAI GPTによる品質分析を組み合わせています。

## 🎯 主な機能

- **話者分離付き文字起こし**: AssemblyAI APIによる高精度な音声認識と話者識別
- **自動品質チェック**: 29項目にわたるテレアポ品質の自動判定
- **バッチ処理**: 複数ファイルの一括処理に対応
- **Google Sheets連携**: 結果の自動保存と管理
- **リアルタイム進捗表示**: 処理状況の可視化

## 🏗️ プロジェクト構造（リファクタリング版）

```
telecheck-test/
├── app.py                      # メインアプリケーション
├── requirements.txt            # 依存パッケージ
├── README.md                   # プロジェクト説明
├── src/                        # ソースコード
│   ├── config.py              # 設定管理
│   ├── ui/                    # ユーザーインターフェース
│   │   ├── main_app.py        # メインアプリロジック
│   │   ├── components.py      # UI コンポーネント
│   │   └── styles.py          # スタイル定義
│   ├── api/                   # API クライアント
│   │   ├── openai_client.py   # OpenAI API
│   │   ├── assemblyai_client.py # AssemblyAI API
│   │   └── sheets_client.py   # Google Sheets API
│   ├── prompts/               # プロンプト管理（分割版）
│   │   ├── __init__.py        # 統合インターフェース
│   │   ├── transcription_prompts.py    # 文字起こし関連
│   │   ├── basic_check_prompts.py      # 基本品質チェック
│   │   ├── advanced_check_prompts.py   # 高度品質チェック
│   │   └── system_prompts.py  # 旧版（移行案内）
│   ├── quality_check/         # 品質チェックシステム（新版）
│   │   ├── __init__.py        # 統合インターフェース
│   │   ├── base.py            # 基底クラス群
│   │   └── checks.py          # 具体的実装クラス
│   ├── common/                # 共通機能
│   │   ├── __init__.py        
│   │   └── error_handler.py   # 統一エラーハンドリング
│   └── utils/                 # ユーティリティ
│       ├── batch_processor.py # バッチ処理（更新版）
│       ├── quality_check.py   # 旧版（後方互換）
│       └── speaker_detection.py # 話者検出
└── secrets/                   # API キー（git ignored）
    └── service_account.json
```

## 🔧 リファクタリングの改善点

### 1. モジュール分割
- **35KB の巨大プロンプトファイル** → 3つの専門ファイルに分割
- **18KB の品質チェックファイル** → クラスベースの柔軟な構造
- **責務の論理的分離**: プロンプト・チェック・エラー処理

### 2. 設計パターン導入
- **抽象基底クラス**: 新チェック追加の容易性
- **ワークフローマネージャー**: 処理の統一管理
- **エラーハンドラー**: 統一されたエラー処理

### 3. 後方互換性維持
- 既存コードは警告付きで継続動作
- 段階的移行をサポート
- フォールバック機能完備

## 📦 セットアップ

### 1. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定
```bash
# Streamlit secrets または環境変数で設定
OPENAI_API_KEY="your-openai-api-key"
ASSEMBLYAI_API_KEY="your-assemblyai-api-key"
```

### 3. Google Sheets 認証
1. Google Cloud Console でサービスアカウントを作成
2. 認証JSONファイルを `secrets/service_account.json` に配置
3. スプレッドシートをサービスアカウントと共有

### 4. アプリケーション起動
```bash
streamlit run app.py
```

## 🚀 使用方法

### 話者分離文字起こし
1. 音声ファイル（MP3, WAV, M4A）をアップロード
2. 担当者名リストを設定
3. 「話者分離文字起こし開始」をクリック
4. 結果をGoogle Sheetsに保存

### 品質チェック
1. 担当者を選択
2. 最大処理行数を設定
3. 「品質チェック実行」をクリック
4. 29項目の自動判定結果を確認

## 🔍 品質チェック項目

### 基本チェック（2項目）
- 社名・担当者名の名乗り確認
- ロングコール検出

### テレアポ対応（9項目）
- アプローチ方法
- 競合他社への言及
- 運転中・電車内での対応
- 断られた際の対応
- 暴言・脅迫の有無
- 情報漏洩チェック
- 違法行為への関与
- 通話対応マナー
- 相手の呼び方

### 顧客反応（8項目）
- 電話お断りの意思表示
- しつこさへの苦情
- 専用番号への誤電話
- 口調への注意
- 顧客の怒り
- 暴言を受けた状況
- 通報の言及
- 営業全般のお断り

### マナー・心構え（10項目）
- 適切な敬語使用
- ビジネス用語の正しい使用
- 謝罪表現の適切性
- 口調・態度の丁寧さ
- 会話の成立度
- 誠実な説明
- その他問題行動

## 🛠️ 開発者向け情報

### 新しいチェック項目を追加する方法
```python
from src.quality_check.base import QualityCheckBase

class NewCheck(QualityCheckBase):
    def get_check_name(self) -> str:
        return "新しいチェック"
    
    def check(self, text_input: str, **kwargs) -> str:
        # チェックロジックを実装
        return "問題なし"
```

### エラーハンドリングの使用
```python
from src.common.error_handler import safe_execute, ErrorHandler

@safe_execute("処理名")
def my_function():
    # 処理内容
    pass
```

## 📝 移行ガイド

### 旧コードから新コードへの移行
```python
# 旧：
from src.utils.quality_check import run_workflow
result = run_workflow(text, checker_str, client)

# 新：
from src.quality_check import run_quality_check_workflow
result = run_quality_check_workflow(text, checker_str, client)
```

### プロンプトの使用方法
```python
# 旧：
from src.prompts.system_prompts import SYSTEM_PROMPTS

# 新：
from src.prompts import SYSTEM_PROMPTS  # 統合辞書
# または
from src.prompts.basic_check_prompts import BASIC_CHECK_PROMPTS
```

## 🎨 技術スタック

- **フロントエンド**: Streamlit
- **音声処理**: AssemblyAI API
- **AI分析**: OpenAI GPT API
- **データ保存**: Google Sheets API
- **言語**: Python 3.8+

## 📊 パフォーマンス

- **処理速度**: ファイルサイズに依存（1MB ≈ 1分）
- **バッチ処理**: 最大50件まで一括処理可能
- **API制限**: 各サービスの制限に準拠
- **メモリ使用量**: 音声ファイルサイズの約2-3倍

## 🔐 セキュリティ

- APIキーはStreamlit Secretsで管理
- 音声ファイルは一時的にのみ保存
- Google Sheetsは適切な権限設定が必要
- 処理ログにセンシティブ情報は含まない

## 🤝 貢献

1. このリポジトリをフォーク
2. 新しいブランチを作成（`git checkout -b feature/AmazingFeature`）
3. 変更をコミット（`git commit -m 'Add some AmazingFeature'`）
4. ブランチにプッシュ（`git push origin feature/AmazingFeature`）
5. Pull Requestを作成

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。
