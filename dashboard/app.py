import boto3
import awswrangler as wr
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="GCC YouTube Trends",
    page_icon="📈",
    layout="wide",
)

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

PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#B279A2", "#FF9DA6", "#9D755D", "#EECA3B", "#BAB0AC",
]

PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


@st.cache_resource
def get_session():
    return boto3.Session(
        aws_access_key_id=st.secrets["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws_secret_access_key"],
        region_name=st.secrets["aws_region"],
    )


@st.cache_data(ttl=1800, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    return wr.athena.read_sql_query(
        sql=sql,
        database=DATABASE,
        s3_output=OUTPUT,
        boto3_session=get_session(),
        ctas_approach=False,
    )


@st.cache_data(ttl=300, show_spinner=False)
def available_dates() -> list:
    df = run_query(
        "SELECT DISTINCT ingest_date FROM most_popular ORDER BY ingest_date DESC"
    )
    return df["ingest_date"].tolist()


def fmt(n) -> str:
    if n is None or pd.isna(n):
        return "-"
    return f"{int(n):,}"


def fmt_compact(n) -> str:
    if n is None or pd.isna(n):
        return "-"
    n = float(n)
    for cut, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= cut:
            return f"{n / cut:.2f}{suffix}"
    return f"{int(n):,}"


def delta(current, previous):
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return None
    diff = int(current) - int(previous)
    if diff == 0:
        return None
    return f"{diff:+,}"


def style(fig, height=420, legend_bottom=False):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        legend_title_text="",
        hoverlabel=dict(font_size=12),
        colorway=PALETTE,
    )
    if legend_bottom:
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=-0.28, x=0)
        )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)")
    return fig


dates = available_dates()

if not dates:
    st.title("GCC YouTube Trends")
    st.warning("No data yet. The pipeline has not produced any partitions.")
    st.stop()

head_left, head_right = st.columns([3, 1])

with head_right:
    selected_date = st.selectbox("Ingest date", dates, label_visibility="collapsed")

with head_left:
    st.title(f"GCC YouTube Trends · {selected_date}")

st.caption(
    f"Most popular videos in six Gulf regions. "
    f"{len(dates)} day(s) collected so far."
)

with st.expander("Filter regions"):
    all_regions = list(REGION_NAMES.keys())
    picked_regions = st.multiselect(
        "Included in every view below",
        options=all_regions,
        default=all_regions,
        format_func=lambda r: f"{r} · {REGION_NAMES[r]}",
        label_visibility="collapsed",
    )

if not picked_regions:
    st.warning("Select at least one region.")
    st.stop()

region_list = ", ".join(f"'{r}'" for r in picked_regions)
scope = f"ingest_date = '{selected_date}' AND region_code IN ({region_list})"

if len(picked_regions) < len(REGION_NAMES):
    st.info(f"Showing {len(picked_regions)} of 6 regions: {' '.join(picked_regions)}")


def overview_for(date_value: str) -> pd.DataFrame:
    return run_query(f"""
        SELECT
          COUNT(*)                           AS row_count,
          COUNT(DISTINCT video_id)           AS unique_videos,
          COUNT(DISTINCT channel_title)      AS channels,
          SUM(view_count)                    AS total_views,
          APPROX_PERCENTILE(view_count, 0.5) AS median_views
        FROM most_popular
        WHERE ingest_date = '{date_value}' AND region_code IN ({region_list})
    """)


current = overview_for(selected_date)

position = dates.index(selected_date)
previous_date = dates[position + 1] if position + 1 < len(dates) else None
previous = overview_for(previous_date) if previous_date else None


def prev_value(column):
    if previous is None or previous.empty:
        return None
    return previous[column][0]


c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Chart rows",
    fmt(current["row_count"][0]),
    delta(current["row_count"][0], prev_value("row_count")),
)
c2.metric(
    "Unique videos",
    fmt(current["unique_videos"][0]),
    delta(current["unique_videos"][0], prev_value("unique_videos")),
)
c3.metric(
    "Channels",
    fmt(current["channels"][0]),
    delta(current["channels"][0], prev_value("channels")),
)
c4.metric(
    "Median views",
    fmt_compact(current["median_views"][0]),
    delta(current["median_views"][0], prev_value("median_views")),
)
c5.metric("Total views", fmt_compact(current["total_views"][0]))

if previous_date:
    st.caption(f"Change shown against {previous_date}.")

st.divider()

tab_regions, tab_content, tab_videos, tab_history = st.tabs(
    ["Regions", "Content", "Videos and channels", "History"]
)


with tab_regions:
    left, right = st.columns(2)

    with left:
        st.subheader("Categories by region")
        st.caption("Percentages, since chart length differs by country.")
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
            custom_data=["category_name", "videos"],
            labels={"pct": "% of region", "region_code": ""},
        )
        fig.update_traces(
            hovertemplate="%{customdata[0]}<br>%{y}%% · %{customdata[1]} videos<extra></extra>"
        )
        st.plotly_chart(style(fig, 440, legend_bottom=True), use_container_width=True,
                        config=PLOT_CONFIG)

    with right:
        st.subheader("Chart size")
        st.caption("Videos returned per country.")
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
            text="videos",
            custom_data=["country", "total_views", "median_views"],
            labels={"videos": "Videos", "region_code": ""},
        )
        fig.update_traces(
            marker_color=PALETTE[0],
            textposition="outside",
            hovertemplate="%{customdata[0]}<br>%{y} videos<br>"
                          "%{customdata[1]:,} total views<extra></extra>",
        )
        st.plotly_chart(style(fig, 440), use_container_width=True, config=PLOT_CONFIG)

    st.divider()
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Shared videos between countries")
        st.caption("Videos appearing in both charts.")
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
        fig.update_layout(coloraxis_showscale=False)
        fig.update_traces(hovertemplate="%{y} and %{x}<br>%{z} shared<extra></extra>")
        st.plotly_chart(style(fig, 420), use_container_width=True, config=PLOT_CONFIG)

    with right2:
        st.subheader("Exclusive vs shared")
        st.caption("Videos found in one chart only, against several.")
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
            labels={"videos": "Videos", "region_code": ""},
        )
        st.plotly_chart(style(fig, 420, legend_bottom=True), use_container_width=True,
                        config=PLOT_CONFIG)


with tab_content:
    left, right = st.columns(2)

    with left:
        st.subheader("Hours to trend")
        st.caption("Time between publishing and reaching the chart.")
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
            custom_data=["videos", "median_hours"],
            labels={"avg_hours": "Average hours", "category_name": ""},
        )
        fig.update_traces(
            marker_color=PALETTE[1],
            hovertemplate="%{y}<br>mean %{x} h · median %{customdata[1]} h<br>"
                          "%{customdata[0]} videos<extra></extra>",
        )
        fig.update_yaxes(tickmode="linear")
        st.plotly_chart(style(fig, 460), use_container_width=True, config=PLOT_CONFIG)

    with right:
        st.subheader("Publishing hour")
        st.caption("Riyadh time, six largest categories.")
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
            labels={"x": "Hour", "y": "", "color": "Videos"},
        )
        fig.update_layout(coloraxis_showscale=False)
        fig.update_xaxes(dtick=3)
        fig.update_traces(hovertemplate="%{y}<br>%{x}:00 · %{z} videos<extra></extra>")
        st.plotly_chart(style(fig, 460), use_container_width=True, config=PLOT_CONFIG)

    st.divider()
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Top tags")
        st.caption("Lowercased so one tag is not counted twice.")
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
        fig.update_traces(marker_color=PALETTE[2])
        fig.update_yaxes(tickmode="linear")
        st.plotly_chart(style(fig, 560), use_container_width=True, config=PLOT_CONFIG)

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
            size="like_count",
            size_max=22,
            hover_name="video_title",
            custom_data=["channel_title", "region_code"],
            log_x=True,
            labels={"view_count": "Views", "like_rate": "Like rate %"},
        )
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]} · %{customdata[1]}"
                          "<br>%{x:,} views · %{y}%<extra></extra>"
        )
        st.plotly_chart(style(fig, 560, legend_bottom=True), use_container_width=True,
                        config=PLOT_CONFIG)


with tab_videos:
    st.subheader("Videos in more than one chart")
    cross = run_query(f"""
        SELECT
          COUNT(DISTINCT region_code)       AS regions,
          ARRAY_JOIN(ARRAY_AGG(DISTINCT region_code ORDER BY region_code), ' ') AS charts,
          MIN(regional_rank)                AS best_rank,
          MAX(view_count)                   AS views,
          MAX(channel_title)                AS channel,
          MAX(category_name)                AS category,
          MAX(video_title)                  AS title
        FROM most_popular
        WHERE {scope}
        GROUP BY video_id
        HAVING COUNT(DISTINCT region_code) > 1
        ORDER BY regions DESC, views DESC
        LIMIT 40
    """)
    st.dataframe(
        cross,
        use_container_width=True,
        height=420,
        hide_index=True,
        column_config={
            "regions": st.column_config.NumberColumn("Regions", width="small"),
            "charts": st.column_config.TextColumn("In charts", width="small"),
            "best_rank": st.column_config.NumberColumn("Best rank", width="small"),
            "views": st.column_config.NumberColumn("Views"),
            "channel": st.column_config.TextColumn("Channel"),
            "category": st.column_config.TextColumn("Category"),
            "title": st.column_config.TextColumn("Title", width="large"),
        },
    )

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Top five per country")
        top = run_query(f"""
            SELECT
              region_code,
              regional_rank,
              view_count,
              channel_title,
              video_title
            FROM most_popular
            WHERE {scope}
              AND regional_rank <= 5
            ORDER BY region_code, regional_rank
        """)
        st.dataframe(
            top,
            use_container_width=True,
            height=460,
            hide_index=True,
            column_config={
                "region_code": st.column_config.TextColumn("Region", width="small"),
                "regional_rank": st.column_config.NumberColumn("Rank", width="small"),
                "view_count": st.column_config.NumberColumn("Views"),
                "channel_title": st.column_config.TextColumn("Channel"),
                "video_title": st.column_config.TextColumn("Title", width="large"),
            },
        )

    with right:
        st.subheader("Top channels")
        channels = run_query(f"""
            SELECT
              channel_title,
              COUNT(*)                    AS appearances,
              COUNT(DISTINCT region_code) AS regions,
              SUM(view_count)             AS total_views
            FROM most_popular
            WHERE {scope}
            GROUP BY channel_title
            ORDER BY appearances DESC, total_views DESC
            LIMIT 20
        """)
        st.dataframe(
            channels,
            use_container_width=True,
            height=460,
            hide_index=True,
            column_config={
                "channel_title": st.column_config.TextColumn("Channel", width="medium"),
                "appearances": st.column_config.NumberColumn("Spots", width="small"),
                "regions": st.column_config.NumberColumn("Regions", width="small"),
                "total_views": st.column_config.NumberColumn("Views"),
            },
        )

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
        st.caption(f"The ten largest channels hold {share:.1f}% of all chart positions.")


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
            fig.update_traces(line_color=PALETTE[0], line_width=2.5)
            st.plotly_chart(style(fig, 380), use_container_width=True, config=PLOT_CONFIG)

        with right:
            fig = px.line(
                history,
                x="ingest_date",
                y="total_views",
                markers=True,
                labels={"total_views": "Total views", "ingest_date": ""},
            )
            fig.update_traces(line_color=PALETTE[1], line_width=2.5)
            st.plotly_chart(style(fig, 380), use_container_width=True, config=PLOT_CONFIG)

        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ingest_date": st.column_config.TextColumn("Date"),
                "row_count": st.column_config.NumberColumn("Chart rows"),
                "unique_videos": st.column_config.NumberColumn("Unique videos"),
                "total_views": st.column_config.NumberColumn("Total views"),
            },
        )
        st.caption("This is the only view that reads every partition.")

st.divider()
st.caption(
    "Collected daily at 21:00 Asia/Riyadh from the YouTube Data API, "
    "processed on AWS Lambda and queried with Athena."
)