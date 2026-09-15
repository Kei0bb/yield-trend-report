# bin_mappings/

製品ごとの bin マッピング CSV を配置するディレクトリ。

## 使い方

1. `<bin_group>.csv` という名前でファイルを作成
   - 例: `main.csv`, `main_b.csv`, `custom_xyz.csv`
2. `backend/product_config.yaml` の当該製品エントリで、拡張子なしのファイル名を
   `bin_group:` に指定
   - 例:
     ```yaml
     products:
       Product-A:
         display_name: Product-A
         product_id: P12345-A
         bin_group: main
     ```
   - CP と FT で別ファイルを使いたい場合は `bin_groups:` で process 別に上書きできる
     （`bin_group:` は共通フォールバック）:
     ```yaml
         bin_group: main       # フォールバック（主に CP）
         bin_groups:
           ft: main_ft          # FT だけ別ファイル
     ```
   - SLT は `bin_groups.slt` を書いても使われない。SLT は bin マッピング CSV を
     経由せず、常に DB の `BIN_NAME` をそのまま表示する（`yield_service.py` の
     `RAW_BIN_PROCESSES`）
   - 詳細な書式は `backend/product_config.yaml.example` を参照

## ファイルフォーマット

### Process 別マッピング

```csv
process,bin_code,bin_group_name
CP,3,Open/Short
CP,5,Open/Short
FT,2,DC-Fail
```

CP と FT で BIN_CODE 体系が異なる場合に使用。

### 全 Process 共通マッピング

```csv
bin_code,bin_group_name
3,Open/Short
5,Open/Short
```

`process` 列を省略すると全 process に適用。

## マッピング解決ルール

1. `bin_mappings/<bin_group>.csv` の process 完全一致行
2. `bin_mappings/<bin_group>.csv` の process 列なし行 (ワイルドカード)
3. DB の BIN_NAME をそのまま使用 (上記でヒットしない場合)

## ファイル管理

- 各品種で独立した bin マッピングが必要な場合: 品種ごとに別ファイルを作成
- 改版品種で同じマッピングを共有したい場合: 同じファイル名を `product_config.yaml` の
  `bin_group`（または `bin_groups`）で指定

## 注意

- マッピングは `load_bin_mapping()` がプロセス内に `lru_cache` で保持するため、
  ファイル更新は**サーバー再起動が必要**（`--reload` モードでも自動反映されない —
  `--reload` はデフォルトで `.py` の変更しか監視せず、CSV の変更は検知しない）
- `*.csv` は `.gitignore` 対象（環境ごとに別管理）。このディレクトリでリポジトリに
  コミットされているのは本 README のみで、サンプル CSV は配布していない
