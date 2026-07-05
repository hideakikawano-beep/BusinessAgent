# テストフィクスチャ

| ファイル | 作成フェーズ | 内容 |
|---|---|---|
| `frames_day1.jsonl` | Phase 2 | 1日分の擬似フレーム列（framesテーブル行のJSONL）。アプリ切替・60秒以内の中断・アイドル分断・会議アプリ・マーク区間を含み、sessionizerの境界テストの正解データとなる |
| `sample_analyses.json` | Phase 2 | SessionAnalysisの正例（FakeAnthropicの応答テンプレート） |
| `tiny_images/` | Phase 1 | pHashテスト用の小さな合成画像（Pillowで生成するヘルパがあれば不要） |
