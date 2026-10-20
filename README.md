# Streamlit in Snowflake（Git連携デプロイ）セットアップ手順

このフォルダには、Git経由でStreamlit in Snowflake（SiS）にデプロイするためのサンプルアプリ一式が含まれています。

## フォルダ構成

| ファイル | 役割 |
|---|---|
| `streamlit_app.py` | サンプルアプリ本体（Snowpark Session取得、データ表示、SQL実行フォーム） |
| `environment.yml` | ウェアハウスランタイム用の依存パッケージ定義（Anacondaチャネル） |
| `snowflake.yml` | Snowflake CLI（`snow streamlit deploy`）を使う場合の定義ファイル（任意） |

---

## 全体の流れ

1. このフォルダをGitリポジトリとして初期化し、GitHub等のリモートにpush
2. Snowflake側でそのリモートリポジトリへの接続を作成（API統合 → Gitリポジトリオブジェクト）
3. Gitリポジトリ上のファイルから `STREAMLIT` オブジェクトを作成
4. 以降はリポジトリを更新 → Snowflake側でfetch → アプリに反映、を繰り返す

---

## 手順1. ローカルでGitリポジトリ化してpush

```bash
cd <このフォルダ>
git init
git add .
git commit -m "Initial commit: Streamlit in Snowflake sample app"
git branch -M main
git remote add origin https://github.com/<your-account>/<your-repo>.git
git push -u origin main
```

GitHubの場合、認証にはパスワードではなく **Personal Access Token (PAT)** が必要です（Settings → Developer settings → Personal access tokens）。

---

## 手順2. SnowflakeでAPI統合とGitリポジトリオブジェクトを作成

Snowsightのワークシート、またはSnowflake CLIで以下のSQLを実行します（`ACCOUNTADMIN`など、十分な権限を持つロールで実行）。

```sql
-- 2-1. GitHub認証用のSecretを作成（PATを使用）
CREATE OR REPLACE SECRET my_db.my_schema.git_secret
  TYPE = PASSWORD
  USERNAME = '<github_username>'
  PASSWORD = '<github_personal_access_token>';

-- 2-2. API統合を作成（GitHubの場合。GitLab/Bitbucket等も同様にAPI_ALLOWED_PREFIXESを変更）
CREATE OR REPLACE API INTEGRATION git_api_integration
  API_PROVIDER = git_https_api
  API_ALLOWED_PREFIXES = ('https://github.com/<your-account>/')
  ALLOWED_AUTHENTICATION_SECRETS = (my_db.my_schema.git_secret)
  ENABLED = TRUE;

-- 2-3. Gitリポジトリオブジェクトを作成（Snowflake内にリモートリポジトリのクローンを作る）
CREATE OR REPLACE GIT REPOSITORY my_db.my_schema.streamlit_repo
  API_INTEGRATION = git_api_integration
  GIT_CREDENTIALS = my_db.my_schema.git_secret
  ORIGIN = 'https://github.com/<your-account>/<your-repo>.git';

-- 2-4. 最新状態を取得（以降、リポジトリを更新するたびに実行）
ALTER GIT REPOSITORY my_db.my_schema.streamlit_repo FETCH;

-- 中身の確認（任意）
LS @my_db.my_schema.streamlit_repo/branches/main;
```

公開リポジトリでもAPI統合・Secretの作成自体は必要です（`ORIGIN`にHTTPS URLを指定する点がポイント）。

---

## 手順3. Gitリポジトリから `STREAMLIT` オブジェクトを作成

### ウェアハウスランタイムの場合（デフォルト、最も手軽）

```sql
CREATE STREAMLIT my_db.my_schema.sample_sis_app
  FROM @my_db.my_schema.streamlit_repo/branches/main
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = <your_warehouse>;

-- 作成直後はまだ「ライブ」ではないため、以下を実行して公開
ALTER STREAMLIT my_db.my_schema.sample_sis_app ADD LIVE VERSION FROM LAST;
```

### コンテナランタイムの場合（GPU/大きめの依存関係が必要な場合）

```sql
CREATE STREAMLIT my_db.my_schema.sample_sis_app
  FROM @my_db.my_schema.streamlit_repo/branches/main
  MAIN_FILE = 'streamlit_app.py'
  RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11'
  COMPUTE_POOL = <your_compute_pool>
  QUERY_WAREHOUSE = <your_warehouse>;

ALTER STREAMLIT my_db.my_schema.sample_sis_app ADD LIVE VERSION FROM LAST;
```

作成後、Snowsightの **Projects → Streamlit** から `SAMPLE_SIS_APP` を開いて動作確認できます。

### Snowsight UIから作成する場合（SQLを書きたくない場合）

1. Snowsight → **Projects** → **Streamlit** → **+ Streamlit App**
2. 「Create from existing file」等でGitリポジトリを選択 → 対象のリポジトリ・ブランチ・`streamlit_app.py` を指定
3. データベース／スキーマ、ウェアハウス（またはコンピュートプール）を選択して作成

---

## 手順4. コード更新時の反映方法

1. ローカルで `streamlit_app.py` 等を編集 → `git commit` → `git push`
2. Snowflakeで最新を取得:
   ```sql
   ALTER GIT REPOSITORY my_db.my_schema.streamlit_repo FETCH;
   ```
3. アプリに最新コードを反映:
   ```sql
   ALTER STREAMLIT my_db.my_schema.sample_sis_app ADD LIVE VERSION FROM LAST;
   ```
   または、Snowsightでアプリを開き **Refresh from repository**（Filesタブ）を実行。

CI/CDで自動化する場合は、Snowflake CLI（`snow streamlit deploy`）とGitHub Actionsを組み合わせる方法もあります（`snowflake.yml`を使用）。

---

## 参考（公式ドキュメント）

- [Create your Streamlit app](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/creating-your-app)
- [CREATE STREAMLIT](https://docs.snowflake.com/en/sql-reference/sql/create-streamlit)
- [CREATE GIT REPOSITORY](https://docs.snowflake.com/en/sql-reference/sql/create-git-repository)
- [Using a Git repository in Snowflake](https://docs.snowflake.com/developer-guide/git/git-overview)

## 注意点

- `ORIGIN` のURLは必ずHTTPSで指定してください（SSH不可）。
- プライベートリポジトリの場合、Secretに設定するパスワードは **Personal Access Token** を推奨します（通常のパスワードではなく）。
- `ROOT_LOCATION` を使って作成した既存アプリはGit連携・マルチファイル編集に対応していないため、Git連携したい場合は `FROM` 句を使う新方式で作成してください。
- コンテナランタイムを使う場合は `COMPUTE_POOL` の権限（USAGE）が必要です。外部パッケージ（PyPI）を使う場合は `EXTERNAL_ACCESS_INTEGRATIONS` の設定も必要になります。
