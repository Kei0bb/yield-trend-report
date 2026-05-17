# bin_mappings/

製品ごとの bin マッピング CSV を配置するディレクトリ。

## 使い方

1. `<bin_group>.csv` という名前でファイルを作成
   - 例: `main.csv`, `main_b.csv`, `custom_xyz.csv`
2. `backend/product_config.csv` の `bin_group` 列に拡張子なしのファイル名を指定
   - 例: `Product-A,P12345-A,Q67890-A,main`

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
- 改版品種で同じマッピングを共有したい場合: 同じファイル名を product_config.csv で指定

## 注意

- ファイル更新後はサーバー再起動で反映されます（`--reload` モードでは自動反映）
- `*.csv` は `.gitignore` 対象（環境ごとに別管理）
- `*.csv.example` をコミットしてサンプルを共有
