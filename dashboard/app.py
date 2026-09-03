import boto3
import awswrangler as wr
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="GCC YouTube Trends", layout="wide")

DATABASE = st.secrets["athena_database"]
OUTPUT = st.secrets["athena_output"]

REGION_NAMES = {
    "SA": "Saudi Arabia",
    "AE": "UAE",
    "KW": "Kuwait",
    "QA": "Qatar",
    "BH": "Bahrain",
    "OM": "Oman",
}


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


@st.cache_data(ttl=300)
def available_dates() -> list:
    df = run_query(
        "SELECT DISTINCT ingest_date FROM most_popular ORDER BY ingest_date DESC"
    )
    return df["ingest_date"].tolist()


def fmt(n) -> str:
    if pd.isna(n):
        return "-"
    return f"{int(n):,}"


st.title("GCC YouTube Trends")
st.caption("Daily most popular videos across six Gulf regions")

if st.sidebar.button("Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

dates = available_dates()

if not dates:
    st.warning("No data yet. The pipeline has not produced any partitions.")
    st.stop()

selected_date = st.sidebar.selectbox("Ingest date", dates)
st.sidebar.caption(f"{len(dates)} day(s) available")

all_regions = list(REGION_NAMES.keys())
picked_regions = st.sidebar.multiselect(
    "Regions",
    options=all_regions,
    default=all_regions,
    format_func=lambda r: f"{r} ({REGION_NAMES[r]})",
)

if not picked_regions:
    st.warning("Select at least one region.")
    st.stop()

region_list = ", ".join(f"'{r}'" for r in picked_regions)
scope = f"ingest_date = '{selected_date}' AND region_code IN ({region_list})"

overview = run_query(f"""
    SELECT
      COUNT(*)                           AS row_count,
      COUNT(DISTINCT video_id)           AS unique_videos,
      COUNT(DISTINCT channel_title)      AS channels,
      SUM(view_count)                    AS total_views,
      APPROX_PERCENTILE(view_count, 0.5) AS median_views
    FROM most_popular
    WHERE {scope}
""")

spread = run_query(f"""
    WITH per_video AS (
      SELECT video_id, COUNT(DISTINCT region_code) AS regions
      FROM most_popular
      WHERE {scope}
      GROUP BY video_id
    )
    SELECT
      COUNT(*)                                     AS videos,
      SUM(CASE WHEN regions > 1 THEN 1 ELSE 0 END) AS shared_videos
    FROM per_video
""")

shared_pct = 0.0
if spread["videos"][0]:
    shared_pct = 100.0 * spread["shared_videos"][0] / spread["videos"][0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Chart rows", fmt(overview["row_count"][0]))
c2.metric("Unique videos", fmt(overview["unique_videos"][0]))
c3.metric("Channels", fmt(overview["channels"][0]))
c4.metric("Median views", fmt(overview["median_views"][0]))
c5.metric("In multiple charts", f"{shared_pct:.0f}%")

st.divider()

tab_regions, tab_content, tab_videos, tab_history = st.tabs(
    ["Regions", "Content", "Videos and channels", "History"]
)


with tab_regions:
    left, right = st.columns(2)

    with left:
        st.subheader("Categories by region")
        st.caption("Shown as percentages because chart length varies by country.")
        categories = run_query(f"""
            SELECT
              region_code,
              category_name,
              COUNT(*) AS videos,
              ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY region_code), 1) AS pct
            FROM most_popular
            WHERE {scope}
            GROUP BY region_code, category_name
        """)
        fig = px.bar(
            categories,
            x="region_code",
            y="pct",
            color="category_name",
            labels={"pct": "% of region", "region_code": "", "category_name": "Category"},
        )
        fig.update_layout(height=430, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Chart size")
        st.caption("How many videos each country returned, and the views behind them.")
        sizes = run_query(f"""
            SELECT
              region_code,
              COUNT(*)                           AS videos,
              SUM(view_count)                    AS total_views,
              APPROX_PERCENTILE(view_count, 0.5) AS median_views
            FROM most_popular
            WHERE {scope}
            GROUP BY region_code
            ORDER BY videos DESC
        """)
        sizes["country"] = sizes["region_code"].map(REGION_NAMES)
        fig = px.bar(
            sizes,
            x="region_code",
            y="videos",
            hover_data=["country", "total_views", "median_views"],
            labels={"videos": "Videos", "region_code": ""},
        )
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Shared videos between countries")
        st.caption("Count of videos appearing in both charts on this date.")
        overlap = run_query(f"""
            SELECT
              a.region_code AS region_a,
              b.region_code AS region_b,
              COUNT(*)      AS shared
            FROM most_popular a
            JOIN most_popular b
              ON a.video_id = b.video_id
             AND a.ingest_date = b.ingest_date
            WHERE a.ingest_date = '{selected_date}'
              AND a.region_code IN ({region_list})
              AND b.region_code IN ({region_list})
            GROUP BY a.region_code, b.region_code
        """)
        matrix = (
            overlap.pivot(index="region_a", columns="region_b", values="shared")
            .fillna(0)
            .astype(int)
        )
        fig = px.imshow(
            matrix,
            text_auto=True,
            color_continuous_scale="Blues",
            aspect="auto",
            labels={"x": "", "y": "", "color": "Shared"},
        )
        fig.update_layout(height=420, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with right2:
        st.subheader("Exclusive vs shared")
        st.caption("Videos found in one chart only, against those found in several.")
        local = run_query(f"""
            WITH per_video AS (
              SELECT video_id, COUNT(DISTINCT region_code) AS regions
              FROM most_popular
              WHERE {scope}
              GROUP BY video_id
            )
            SELECT
              m.region_code,
              SUM(CASE WHEN p.regions = 1 THEN 1 ELSE 0 END) AS exclusive,
              SUM(CASE WHEN p.regions > 1 THEN 1 ELSE 0 END) AS shared
            FROM most_popular m
            JOIN per_video p ON m.video_id = p.video_id
            WHERE m.ingest_date = '{selected_date}'
              AND m.region_code IN ({region_list})
            GROUP BY m.region_code
            ORDER BY m.region_code
        """)
        melted = local.melt(
            id_vars="region_code",
            value_vars=["exclusive", "shared"],
            var_name="kind",
            value_name="videos",
        )
        fig = px.bar(
            melted,
            x="region_code",
            y="videos",
            color="kind",
            barmode="stack",
            labels={"videos": "Videos", "region_code": "", "kind": ""},
        )
        fig.update_layout(height=420, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)


with tab_content:
    left, right = st.columns(2)

    with left:
        st.subheader("Hours to trend")
        st.caption("Time between publishing and appearing in the chart.")
        speed = run_query(f"""
            SELECT
              category_name,
              COUNT(*) AS videos,
              ROUND(AVG(DATE_DIFF('hour',
                from_iso8601_timestamp(published_at),
                from_iso8601_timestamp(pulled_at))), 1) AS avg_hours,
              ROUND(APPROX_PERCENTILE(
                CAST(DATE_DIFF('hour',
                  from_iso8601_timestamp(published_at),
                  from_iso8601_timestamp(pulled_at)) AS DOUBLE), 0.5), 1) AS median_hours
            FROM most_popular
            WHERE {scope}
            GROUP BY category_name
            HAVING COUNT(*) >= 5
            ORDER BY avg_hours
        """)
        fig = px.bar(
            speed,
            x="avg_hours",
            y="category_name",
            orientation="h",
            hover_data=["videos", "median_hours"],
            labels={"avg_hours": "Average hours", "category_name": ""},
        )
        fig.update_layout(height=460)
        fig.update_yaxes(tickmode="linear")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Publishing hour")
        st.caption("Riyadh time, for the six largest categories.")
        hours = run_query(f"""
            WITH top_categories AS (
              SELECT category_name
              FROM most_popular
              WHERE {scope}
              GROUP BY category_name
              ORDER BY COUNT(*) DESC
              LIMIT 6
            )
            SELECT
              m.category_name,
              HOUR(from_iso8601_timestamp(m.published_at) + INTERVAL '3' HOUR) AS publish_hour,
              COUNT(*) AS videos
            FROM most_popular m
            JOIN top_categories t ON m.category_name = t.category_name
            WHERE m.ingest_date = '{selected_date}'
              AND m.region_code IN ({region_list})
            GROUP BY m.category_name,
                     HOUR(from_iso8601_timestamp(m.published_at) + INTERVAL '3' HOUR)
        """)
        grid = (
            hours.pivot(index="category_name", columns="publish_hour", values="videos")
            .reindex(columns=range(24))
            .fillna(0)
            .astype(int)
        )
        fig = px.imshow(
            grid,
            color_continuous_scale="Oranges",
            aspect="auto",
            labels={"x": "Hour (Riyadh)", "y": "", "color": "Videos"},
        )
        fig.update_layout(height=460, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Top tags")
        st.caption("Lowercased so the same tag is not counted twice.")
        tags = run_query(f"""
            SELECT LOWER(tag) AS tag, COUNT(*) AS uses
            FROM most_popular
            CROSS JOIN UNNEST(video_tags) AS t(tag)
            WHERE {scope}
            GROUP BY LOWER(tag)
            ORDER BY uses DESC
            LIMIT 15
        """)
        fig = px.bar(
            tags.sort_values("uses"),
            x="uses",
            y="tag",
            orientation="h",
            labels={"uses": "Occurrences", "tag": ""},
        )
        fig.update_layout(height=560)
        fig.update_yaxes(tickmode="linear")
        st.plotly_chart(fig, use_container_width=True)

    with right2:
        st.subheader("Likes per view")
        st.caption("Videos under 10k views are left out.")
        engagement = run_query(f"""
            SELECT
              video_title,
              channel_title,
              region_code,
              category_name,
              view_count,
              like_count,
              ROUND(100.0 * like_count / NULLIF(view_count, 0), 2) AS like_rate
            FROM most_popular
            WHERE {scope}
              AND view_count > 10000
              AND like_count IS NOT NULL
            ORDER BY like_rate DESC
            LIMIT 40
        """)
        fig = px.scatter(
            engagement,
            x="view_count",
            y="like_rate",
            color="category_name",
            hover_name="video_title",
            hover_data=["channel_title", "region_code"],
            log_x=True,
            labels={
                "view_count": "Views (log)",
                "like_rate": "Like rate %",
                "category_name": "",
            },
        )
        fig.update_layout(height=560, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)


with tab_videos:
    st.subheader("Videos in more than one chart")
    cross = run_query(f"""
        SELECT
          MAX(video_title)            AS title,
          MAX(channel_title)          AS channel,
          MAX(category_name)          AS category,
          COUNT(DISTINCT region_code) AS regions,
          ARRAY_JOIN(ARRAY_AGG(DISTINCT region_code ORDER BY region_code), ' ') AS in_charts,
          MIN(regional_rank)          AS best_rank,
          MAX(view_count)             AS views
        FROM most_popular
        WHERE {scope}
        GROUP BY video_id
        HAVING COUNT(DISTINCT region_code) > 1
        ORDER BY regions DESC, views DESC
        LIMIT 40
    """)
    st.dataframe(cross, use_container_width=True, height=420, hide_index=True)

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Top five per country")
        top = run_query(f"""
            SELECT
              region_code,
              regional_rank,
              video_title,
              channel_title,
              category_name,
              view_count,
              like_count
            FROM most_popular
            WHERE {scope}
              AND regional_rank <= 5
            ORDER BY region_code, regional_rank
        """)
        st.dataframe(top, use_container_width=True, height=460, hide_index=True)

    with right:
        st.subheader("Top channels")
        channels = run_query(f"""
            SELECT
              channel_title,
              COUNT(*)                    AS appearances,
              COUNT(DISTINCT region_code) AS regions,
              COUNT(DISTINCT video_id)    AS videos,
              SUM(view_count)             AS total_views
            FROM most_popular
            WHERE {scope}
            GROUP BY channel_title
            ORDER BY appearances DESC, total_views DESC
            LIMIT 20
        """)
        st.dataframe(channels, use_container_width=True, height=460, hide_index=True)

    concentration = run_query(f"""
        WITH ranked AS (
          SELECT
            channel_title,
            COUNT(*) AS appearances,
            ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rn
          FROM most_popular
          WHERE {scope}
          GROUP BY channel_title
        )
        SELECT
          SUM(CASE WHEN rn <= 10 THEN appearances ELSE 0 END) AS top10_rows,
          SUM(appearances)                                    AS all_rows
        FROM ranked
    """)
    if concentration["all_rows"][0]:
        share = 100.0 * concentration["top10_rows"][0] / concentration["all_rows"][0]
        st.info(f"The ten largest channels hold {share:.1f}% of all chart positions.")


with tab_history:
    st.subheader("Daily history")

    if len(dates) < 2:
        st.info("Only one day of data so far. This view fills in as days accumulate.")
    else:
        history = run_query("""
            SELECT
              ingest_date,
              COUNT(*)                 AS row_count,
              COUNT(DISTINCT video_id) AS unique_videos,
              SUM(view_count)          AS total_views
            FROM most_popular
            GROUP BY ingest_date
            ORDER BY ingest_date
        """)

        left, right = st.columns(2)

        with left:
            fig = px.line(
                history,
                x="ingest_date",
                y="unique_videos",
                markers=True,
                labels={"unique_videos": "Unique videos", "ingest_date": ""},
            )
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)

        with right:
            fig = px.line(
                history,
                x="ingest_date",
                y="total_views",
                markers=True,
                labels={"total_views": "Total views", "ingest_date": ""},
            )
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(history, use_container_width=True, hide_index=True)
        st.caption("This is the only view that reads every partition.")