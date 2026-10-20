import pandas as pd
import numpy as np
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Sample SiS App", page_icon="❄️", layout="wide")

st.title("❄️ Streamlit in Snowflake - サンプルアプリ")
st.caption("Git連携でデプロイされたシンプルなStreamlitアプリです。")

# Snowflakeセッション（SiS上で自動的に発行される実行コンテキストのセッション）
session = get_active_session()

st.header("1. 現在の実行コンテキスト")
try:
    ctx_df = session.sql(
        """
        select
            current_account() as account,
            current_role() as role,
            current_warehouse() as warehouse,
            current_database() as database,
            current_schema() as schema
        """
    ).to_pandas()
    st.dataframe(ctx_df, use_container_width=True)
except Exception as e:
    st.error(f"コンテキスト取得に失敗しました: {e}")

st.divider()

st.header("2. サンプルデータの表示とフィルタ")

# デモ用のダミーデータ（実運用ではsession.sql(...)でテーブルを参照してください）
rng = np.random.default_rng(42)
demo_df = pd.DataFrame(
    {
        "date": pd.date_range("2026-01-01", periods=30, freq="D"),
        "category": rng.choice(["A", "B", "C"], size=30),
        "value": rng.integers(10, 100, size=30),
    }
)

categories = st.multiselect(
    "カテゴリで絞り込み", options=sorted(demo_df["category"].unique()), default=list(demo_df["category"].unique())
)
filtered = demo_df[demo_df["category"].isin(categories)]

col1, col2 = st.columns(2)
with col1:
    st.subheader("データ")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
with col2:
    st.subheader("カテゴリ別推移")
    pivot = filtered.pivot_table(index="date", columns="category", values="value", aggfunc="sum").fillna(0)
    st.line_chart(pivot)

st.divider()

st.header("3. 任意のSQLを実行")
default_sql = "select current_timestamp() as now"
sql_text = st.text_area("SQLを入力してください", value=default_sql, height=100)
if st.button("実行"):
    try:
        result_df = session.sql(sql_text).to_pandas()
        st.success("実行成功")
        st.dataframe(result_df, use_container_width=True)
    except Exception as e:
        st.error(f"クエリ実行に失敗しました: {e}")
