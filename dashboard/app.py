import boto3
import awswrangler as wr
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="GCC YouTube Trends",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
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

REGION_ORDER = ["SA", "AE", "KW", "QA", "BH", "OM"]

PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#B279A2", "#EECA3B", "#9D755D", "#BAB0AC",
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
            return f"{n / cut:.1f}{suffix}"
    return f"{int(n):,}"


def delta(current, previous):
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return None
    diff = int(current) - int(previous)
    if diff == 0:
        return None
    return f"{diff:+,}"


def shorten(text, limit=16):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def style(fig, height=380, legend="none"):
    top_margin = 46 if legend == "top" else 10
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=top_margin, b=8),
        legend_title_text="",
        colorway=PALETTE,
        hoverlabel=dict(font_size=13),
        font=dict(size=13),
        showlegend=(legend == "top"),
    )
    if legend == "top":
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.0,
                x=0,
                font=dict(size=12),
                itemwidth=30,
            )
        )
    fig.update_xaxes(showgrid=False, tickangle=0, automargin=True)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.16)", automargin=True)
    return fig


dates = available_dates()

if not dates:
    st.title("GCC YouTube Trends")
    st.warning("No data yet. The pipeline has not produced any partitions.")
    st.stop()

st.title("GCC YouTube Trends")

pick_left, pick_right = st.columns([1, 2])

with pick_left:
    selected_date = st.selectbox("Date", dates)

with pick_right:
    picked_regions = st.multiselect(
        "Regions",
        options=REGION_ORDER,
        default=REGION_ORDER,
        format_func=lambda r: f"{r} · {REGION_NAMES[r]}",
    )

if not picked_regions:
    st.warning("Select at least one region.")
    st.stop()

region_list = ", ".join(f"'{r}'" for r in picked_regions)
scope = f"ingest_date = '{selected_date}' AND region_code IN ({region_list})"
order = [r for r in REGION_ORDER if r in picked_regions]

st.caption(
    f"Most popular videos in {len(picked_regions)} Gulf "
    f"{'region' if len(picked_regions) == 1 else 'regions'} on {selected_date}. "
    f"{len(dates)} day(s) collected."
)


def overview_for(date_value: str) -> pd.DataFrame:
    return run_query(f"""
        SELECT
          COUNT(*)                           AS row_count,
          COUNT(DISTINCT video_id)           AS unique_videos,
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

m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Chart rows",
    fmt(current["row_count"][0]),
    delta(current["row_count"][0], prev_value("row_count")),
)
m2.metric(
    "Unique videos",
    fmt(current["unique_videos"][0]),
    delta(current["unique_videos"][0], prev_value("unique_videos")),
)
m3.metric(
    "Median views",
    fmt_compact(current["median_views"][0]),
    delta(current["median_views"][0], prev_value("median_views")),
)
m4.metric("In two or more charts", f"{shared_pct:.0f}%")

if previous_date:
    st.caption(f"Change measured against {previous_date}.")

st.divider()

tab_regions, tab_content, tab_videos, tab_history = st.tabs(
    ["Regions", "Content", "Videos", "History"]
)


with tab_regions:
    st.subheader("Categories by region")
    st.caption("Percentages, because chart length differs by country.")
    categories = run_query(f"""
        WITH totals AS (
          SELECT category_name, COUNT(*) AS c
          FROM most_popular
          WHERE {scope}
          GROUP BY category_name
        ),
        ranked AS (
          SELECT category_name, ROW_NUMBER() OVER (ORDER BY c DESC) AS rn
          FROM totals
        )
        SELECT
          m.region_code,
          CASE WHEN r.rn <= 5 THEN m.category_name ELSE 'Other' END AS category,
          COUNT(*) AS videos,
          ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY m.region_code), 1) AS pct
        FROM most_popular m
        JOIN ranked r ON m.category_name = r.category_name
        WHERE m.ingest_date = '{selected_date}'
          AND m.region_code IN ({region_list})
        GROUP BY m.region_code,
                 CASE WHEN r.rn <= 5 THEN m.category_name ELSE 'Other' END
    """)
    legend_order = [
        c for c in categories.groupby("category")["videos"].sum()
        .sort_values(ascending=False).index if c != "Other"
    ] + (["Other"] if "Other" in categories["category"].values else [])

    fig = px.bar(
        categories,
        x="region_code",
        y="pct",
        color="category",
        custom_data=["category", "videos"],
        category_orders={"region_code": order, "category": legend_order},
        labels={"pct": "% of chart", "region_code": ""},
    )
    fig.update_traces(
        hovertemplate="%{customdata[0]}<br>%{y}% · %{customdata[1]} videos<extra></extra>"
    )
    st.plotly_chart(style(fig, 460, legend="top"), use_container_width=True,
                    config=PLOT_CONFIG)

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
    """)
    sizes["country"] = sizes["region_code"].map(REGION_NAMES)
    fig = px.bar(
        sizes,
        x="region_code",
        y="videos",
        text="videos",
        custom_data=["country", "total_views"],
        category_orders={"region_code": order},
        labels={"videos": "Videos", "region_code": ""},
    )
    fig.update_traces(
        marker_color=PALETTE[0],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{customdata[0]}<br>%{y} videos<br>"
                      "%{customdata[1]:,} views<extra></extra>",
    )
    st.plotly_chart(style(fig, 340), use_container_width=True, config=PLOT_CONFIG)

    st.subheader("Shared videos between countries")
    st.caption("How many videos appear in both charts.")
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
        .reindex(index=order, columns=order)
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
    st.plotly_chart(style(fig, 360), use_container_width=True, config=PLOT_CONFIG)

    st.subheader("Exclusive vs shared")
    st.caption("Videos in one chart only, against those in several.")
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
        category_orders={"region_code": order},
        labels={"videos": "Videos", "region_code": ""},
    )
    st.plotly_chart(style(fig, 380, legend="top"), use_container_width=True,
                    config=PLOT_CONFIG)


with tab_content:
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
        text="avg_hours",
        custom_data=["videos", "median_hours"],
        labels={"avg_hours": "Average hours", "category_name": ""},
    )
    fig.update_traces(
        marker_color=PALETTE[1],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>mean %{x} h · median %{customdata[1]} h<br>"
                      "%{customdata[0]} videos<extra></extra>",
    )
    fig.update_yaxes(tickmode="linear")
    st.plotly_chart(style(fig, max(320, 46 * len(speed))), use_container_width=True,
                    config=PLOT_CONFIG)

    st.subheader("Publishing hour")
    st.caption("Riyadh time, five largest categories.")
    hours = run_query(f"""
        WITH top_categories AS (
          SELECT category_name
          FROM most_popular
          WHERE {scope}
          GROUP BY category_name
          ORDER BY COUNT(*) DESC
          LIMIT 5
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
    grid.index = [shorten(name, 14) for name in grid.index]
    fig = px.imshow(
        grid,
        color_continuous_scale="Oranges",
        aspect="auto",
        labels={"x": "Hour", "y": "", "color": "Videos"},
    )
    fig.update_layout(coloraxis_showscale=False)
    fig.update_xaxes(dtick=4)
    fig.update_traces(hovertemplate="%{y}<br>%{x}:00 · %{z} videos<extra></extra>")
    st.plotly_chart(style(fig, 330), use_container_width=True, config=PLOT_CONFIG)

    st.subheader("Top tags")
    st.caption("Lowercased so one tag is not counted twice.")
    tags = run_query(f"""
        SELECT LOWER(tag) AS tag, COUNT(*) AS uses
        FROM most_popular
        CROSS JOIN UNNEST(video_tags) AS t(tag)
        WHERE {scope}
        GROUP BY LOWER(tag)
        ORDER BY uses DESC
        LIMIT 12
    """)
    tags["label"] = tags["tag"].map(lambda t: shorten(t, 18))
    fig = px.bar(
        tags.sort_values("uses"),
        x="uses",
        y="label",
        orientation="h",
        text="uses",
        custom_data=["tag"],
        labels={"uses": "Occurrences", "label": ""},
    )
    fig.update_traces(
        marker_color=PALETTE[2],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{customdata[0]}<br>%{x} videos<extra></extra>",
    )
    fig.update_yaxes(tickmode="linear")
    st.plotly_chart(style(fig, 460), use_container_width=True, config=PLOT_CONFIG)

    st.subheader("Likes per view")
    st.caption("Videos under 10k views are left out. Tap a point for details.")
    engagement = run_query(f"""
        SELECT
          video_title,
          channel_title,
          region_code,
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
    engagement["short_title"] = engagement["video_title"].map(lambda t: shorten(t, 40))
    fig = px.scatter(
        engagement,
        x="view_count",
        y="like_rate",
        color="region_code",
        category_orders={"region_code": order},
        hover_name="short_title",
        custom_data=["channel_title", "view_count", "like_rate"],
        log_x=True,
        labels={"view_count": "Views", "like_rate": "Like rate %", "region_code": ""},
    )
    fig.update_traces(
        marker=dict(size=11, opacity=0.85),
        hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]}<br>"
                      "%{customdata[1]:,} views · %{customdata[2]}%<extra></extra>",
    )
    st.plotly_chart(style(fig, 420, legend="top"), use_container_width=True,
                    config=PLOT_CONFIG)


with tab_videos:
    st.subheader("In more than one chart")
    cross = run_query(f"""
        SELECT
          COUNT(DISTINCT region_code)       AS regions,
          ARRAY_JOIN(ARRAY_AGG(DISTINCT region_code ORDER BY region_code), ' ') AS charts,
          MAX(view_count)                   AS views,
          MAX(channel_title)                AS channel,
          MAX(video_title)                  AS title
        FROM most_popular
        WHERE {scope}
        GROUP BY video_id
        HAVING COUNT(DISTINCT region_code) > 1
        ORDER BY regions DESC, views DESC
        LIMIT 30
    """)
    st.dataframe(
        cross,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            "regions": st.column_config.NumberColumn("In", width="small"),
            "charts": st.column_config.TextColumn("Charts", width="small"),
            "views": st.column_config.NumberColumn("Views", width="small"),
            "channel": st.column_config.TextColumn("Channel", width="medium"),
            "title": st.column_config.TextColumn("Title", width="large"),
        },
    )

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
        height=400,
        hide_index=True,
        column_config={
            "region_code": st.column_config.TextColumn("Region", width="small"),
            "regional_rank": st.column_config.NumberColumn("Rank", width="small"),
            "view_count": st.column_config.NumberColumn("Views", width="small"),
            "channel_title": st.column_config.TextColumn("Channel", width="medium"),
            "video_title": st.column_config.TextColumn("Title", width="large"),
        },
    )

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
        LIMIT 15
    """)
    st.dataframe(
        channels,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            "channel_title": st.column_config.TextColumn("Channel", width="large"),
            "appearances": st.column_config.NumberColumn("Spots", width="small"),
            "regions": st.column_config.NumberColumn("Regions", width="small"),
            "total_views": st.column_config.NumberColumn("Views", width="small"),
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
        st.info("Only one day so far. This view fills in as days accumulate.")
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

        fig = px.line(
            history,
            x="ingest_date",
            y="unique_videos",
            markers=True,
            labels={"unique_videos": "Unique videos", "ingest_date": ""},
        )
        fig.update_traces(line_color=PALETTE[0], line_width=2.5, marker_size=8)
        fig.update_xaxes(type="category")
        st.plotly_chart(style(fig, 320), use_container_width=True, config=PLOT_CONFIG)

        fig = px.line(
            history,
            x="ingest_date",
            y="total_views",
            markers=True,
            labels={"total_views": "Total views", "ingest_date": ""},
        )
        fig.update_traces(line_color=PALETTE[1], line_width=2.5, marker_size=8)
        fig.update_xaxes(type="category")
        st.plotly_chart(style(fig, 320), use_container_width=True, config=PLOT_CONFIG)

        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ingest_date": st.column_config.TextColumn("Date", width="small"),
                "row_count": st.column_config.NumberColumn("Rows", width="small"),
                "unique_videos": st.column_config.NumberColumn("Videos", width="small"),
                "total_views": st.column_config.NumberColumn("Views"),
            },
        )
        st.caption("This is the only view that reads every partition.")

st.divider()
st.caption(
    "Collected daily at 21:00 Asia/Riyadh from the YouTube Data API, "
    "processed on AWS Lambda, queried with Athena."
)