---
inclusion: always
---

# ディレクトリ構成

```
task_box_it_develop/
├── memo/        # 構想メモ、エージェントのプロンプト草案、見積もり基準（memo/雑多な/ITビジネス/タスク百葉箱/ 配下）
├── .kiro/
│   ├── steering/  # 常時参照される永続的なプロジェクトコンテキスト（このファイルを含む）
│   ├── specs/     # 機能ごとの requirements.md / design.md / tasks.md
│   └── hooks/     # イベント駆動の自動化の一覧（実体は .claude/settings.json のhooks設定）
├── logs/        # 作業ログ（未作成。最初のログ作成時に作る）
└── CLAUDE.md    # 索引。詳細は .kiro/ と docs/ を参照
```

以下は未作成で、実装開始時に追加する。

```
├── backend/     # Django REST Framework API
├── frontend/    # Next.js フロントエンド
└── docs/        # バックエンド/フロントエンドの詳細ドキュメント
```

## memo/ の内容

`memo/雑多な/ITビジネス/タスク百葉箱/` 配下がこのプロダクトの一次情報。

- `アイデア.md` — 事業構想（需要、競合、強み、ターゲティング、見積もりの基準）
- `エージェント/` — エージェント一覧と、ヒアリングbot・要件サマリー作成エージェントのプロンプト草案、チャットのサポート機能の案
- `見積もり/` — 相場見積もり・自分見積もりのエージェントのプロンプト草案、エンドポイント単価のランク表
- `アプリ開発/webサイト作成.md` — アプリ本体の要件と技術選定
- `TODO.md` — 残作業

## 配置の指針

- 新機能に着手する際は、まず `.kiro/specs/<feature-slug>/` に requirements → design → tasks を作成してから実装に入る（詳細は [.kiro/specs/README.md](../specs/README.md)）。
- `memo/` は構想段階の草案置き場。仕様として確定した内容は `.kiro/specs/` や `.kiro/steering/` に反映し、実装は `memo/` ではなくそちらを正とする。
- ドキュメントの詳細情報は `docs/` に一本化し、`.kiro/steering/` や `CLAUDE.md` からはリンクのみ行う（重複させない）。
