import boto3
import awswrangler as wr
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="GCC YouTube Trends", layout="wide")

DATABASE = st.secrets["athena_database"]
OUTPUT = st.secrets["athena_output"]


@st.cache_resource
def get_session():
    return boto3.Session(
        aws_access_key_id=st.secrets["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws_secret_access_key"],
        region_name=st.secrets["aws_region"],
    )


@st.cache_data(ttl=3600)
def run_query(sql: str) -> pd.DataFrame:
    return wr.athena.read_sql_query(
        sql=sql,
        database=DATABASE,
        s3_output=OUTPUT,
        boto3_session=get_session(),
        ctas_approach=False,
    )


@st.cache_data(ttl=3600)
def available_dates() -> list:
    df = run_query(
        "SELECT DISTINCT ingest_date FROM most_popular ORDER BY ingest_date DESC"
    )
    return df["ingest_date"].tolist()


st.title("GCC YouTube Trends")
st.caption("Daily most-popular videos across six Gulf regions")

dates = available_dates()

if not dates:
    st.warning("No data yet. The pipeline has not produced any partitions.")
    st.stop()

selected_date = st.sidebar.selectbox("Ingest date", dates)
st.sidebar.caption(f"{len(dates)} day(s) available")

overview = run_query(f"""
    SELECT
      COUNT(*) AS rows_total,
      COUNT(DISTINCT video_id) AS unique_videos,
      COUNT(DISTINCT channel_title) AS channels,
      SUM(view_count) AS total_views
    FROM most_popular
    WHERE ingest_date = '{selected_date}'
""")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{overview['rows_total'][0]:,}")
c2.metric("Unique videos", f"{overview['unique_videos'][0]:,}")
c3.metric("Channels", f"{overview['channels'][0]:,}")
c4.metric("Total views", f"{overview['total_views'][0]:,}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Category mix by region")
    categories = run_query(f"""
        SELECT
          region_code,
          category_name,
          COUNT(*) AS videos,
          ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY region_code), 1) AS pct
        FROM most_popular
        WHERE ingest_date = '{selected_date}'
        GROUP BY region_code, category_name
    """)
    fig = px.bar(
        categories,
        x="region_code",
        y="pct",
        color="category_name",
        labels={"pct": "% of region", "region_code": "Region", "category_name": "Category"},
    )
    fig.update_layout(height=420, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Cross-border videos")
    cross = run_query(f"""
        SELECT
          MAX(video_title) AS title,
          MAX(channel_title) AS channel,
          COUNT(DISTINCT region_code) AS regions,
          MAX(view_count) AS views
        FROM most_popular
        WHERE ingest_date = '{selected_date}'
        GROUP BY video_id
        HAVING COUNT(DISTINCT region_code) > 1
        ORDER BY regions DESC, views DESC
        LIMIT 15
    """)
    st.dataframe(cross, use_container_width=True, height=420, hide_index=True)

st.divider()

left2, right2 = st.columns(2)

with left2:
    st.subheader("Engagement rate")
    engagement = run_query(f"""
        SELECT
          video_title,
          channel_title,
          region_code,
          view_count,
          like_count,
          ROUND(100.0 * like_count / NULLIF(view_count, 0), 2) AS like_rate
        FROM most_popular
        WHERE ingest_date = '{selected_date}'
          AND view_count > 10000
          AND like_count IS NOT NULL
        ORDER BY like_rate DESC
        LIMIT 20
    """)
    fig = px.scatter(
        engagement,
        x="view_count",
        y="like_rate",
        color="region_code",
        hover_name="video_title",
        log_x=True,
        labels={"view_count": "Views (log)", "like_rate": "Like rate %", "region_code": "Region"},
    )
    fig.update_layout(height=400, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

with right2:
    st.subheader("Hours to trend by category")
    speed = run_query(f"""
        SELECT
          category_name,
          COUNT(*) AS videos,
          ROUND(AVG(DATE_DIFF('hour',
            from_iso8601_timestamp(published_at),
            from_iso8601_timestamp(pulled_at))), 1) AS avg_hours
        FROM most_popular
        WHERE ingest_date = '{selected_date}'
        GROUP BY category_name
        HAVING COUNT(*) >= 5
        ORDER BY avg_hours
    """)
    fig = px.bar(
        speed,
        x="avg_hours",
        y="category_name",
        orientation="h",
        labels={"avg_hours": "Average hours", "category_name": ""},
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

left3, right3 = st.columns(2)

with left3:
    st.subheader("Top channels")
    channels = run_query(f"""
        SELECT
          channel_title,
          COUNT(*) AS appearances,
          COUNT(DISTINCT region_code) AS regions,
          SUM(view_count) AS total_views
        FROM most_popular
        WHERE ingest_date = '{selected_date}'
        GROUP BY channel_title
        ORDER BY appearances DESC
        LIMIT 15
    """)
    st.dataframe(channels, use_container_width=True, height=400, hide_index=True)

with right3:
    st.subheader("Top tags")
    tags = run_query(f"""
        SELECT tag, COUNT(*) AS uses
        FROM most_popular
        CROSS JOIN UNNEST(video_tags) AS t(tag)
        WHERE ingest_date = '{selected_date}'
        GROUP BY tag
        ORDER BY uses DESC
        LIMIT 20
    """)
    fig = px.bar(
        tags.sort_values("uses"),
        x="uses",
        y="tag",
        orientation="h",
        labels={"uses": "Occurrences", "tag": ""},
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)