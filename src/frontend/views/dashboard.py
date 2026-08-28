from collections import defaultdict

import streamlit as st

from components import render_sidebar_source_link
import front_config as config


DOMAIN_COLORS = {
    "Smart Industries": "#6c6c6c",
    "Connectivity Solutions": "#1f77b4",
    "Cybersecurity": "#ff7900",
    "Cloud": "#8f8f8f",
    "Customer Experience": "#00a3a3",
    "Employee Experience": "#7a4db3",
    "Sustainability": "#4b8f29",
}

HIGH_PRIORITY_THRESHOLD = 8.0


def format_score_value(score: int | float | None) -> float | None:
    if isinstance(score, (int, float)):
        return round(float(score), 1)
    return None


def get_score(space: dict, score_name: str, default: float = 0.0) -> float:
    score = space.get("scoring", {}).get(score_name, default)
    if isinstance(score, (int, float)):
        return max(0.0, min(10.0, float(score)))
    return default


def get_signal_count(space: dict) -> int:
    signals = space.get("signals_and_sources", {})
    return sum(len(items) for items in signals.values())


def build_domain_summary(opportunity_spaces: list[dict]) -> list[dict]:
    grouped_spaces = defaultdict(list)

    for space in opportunity_spaces:
        grouped_spaces[space.get("domain", "Unassigned")].append(space)

    summary = []
    for domain in config.ORANGE_BUSINESS_DOMAINS:
        spaces = grouped_spaces.get(domain, [])
        if not spaces:
            continue

        total_scores = [get_score(space, "final_score") for space in spaces]
        market_scores = [
            get_score(space, "market_signal_strength")
            for space in spaces
        ]
        strategic_scores = [
            get_score(space, "weighted_score")
            for space in spaces
        ]
        high_priority_count = sum(
            1
            for space in spaces
            if get_score(space, "final_score") >= HIGH_PRIORITY_THRESHOLD
        )

        summary.append(
            {
                "Domain": domain,
                "Opportunity spaces": len(spaces),
                "Avg total score": round(sum(total_scores) / len(total_scores), 1),
                "Avg market signal": round(sum(market_scores) / len(market_scores), 1),
                "Avg strategic potential": round(
                    sum(strategic_scores) / len(strategic_scores),
                    1,
                ),
                "High priority": high_priority_count,
            }
        )

    return summary


def get_leading_domain(
    domain_summary: list[dict],
    metric_name: str,
) -> tuple[str, str]:
    if not domain_summary:
        return "N/A", ""

    leading_domain = max(domain_summary, key=lambda row: row[metric_name])
    return f"{leading_domain[metric_name]:g}", leading_domain["Domain"]


def render_kpi_card(label: str, value: str | int, detail: str = "") -> None:
    st.markdown(
        f"""
        <div class="ob-kpi-card">
          <div class="ob-kpi-label">{label}</div>
          <div class="ob-kpi-value">{value}</div>
          <div class="ob-kpi-detail">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard_metrics(
    opportunity_spaces: list[dict],
    domain_summary: list[dict],
) -> None:
    total_spaces = len(opportunity_spaces)
    active_domains = len(domain_summary)
    high_priority_total = sum(row["High priority"] for row in domain_summary)
    top_total_score, top_total_domain = get_leading_domain(
        domain_summary,
        "Avg total score",
    )
    top_market_score, top_market_domain = get_leading_domain(
        domain_summary,
        "Avg market signal",
    )

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    with metric_1:
        render_kpi_card("Opportunity spaces", total_spaces)

    with metric_2:
        render_kpi_card("Active domains", active_domains)

    with metric_3:
        render_kpi_card("Top total score", top_total_score, top_total_domain)

    with metric_4:
        render_kpi_card("Number of high priority spaces", high_priority_total, "Spaces where score >= 8")


def build_dashboard_rows(opportunity_spaces: list[dict]) -> list[dict]:
    rows = []

    for space in opportunity_spaces:
        scoring = space.get("scoring", {})
        rows.append(
            {
                "ID": space.get("id", ""),
                "Domain": space.get("domain", "Unassigned"),
                "Opportunity space": space.get("technology_name", "Untitled opportunity"),
                "Total score": format_score_value(scoring.get("final_score")),
                "Market signal": format_score_value(scoring.get("market_signal_strength")),
                "Source diversity": format_score_value(scoring.get("source_diversity")),
                "Strategic potential": format_score_value(scoring.get("weighted_score")),
                "Signal count": get_signal_count(space),
            }
        )

    return rows


def render_domain_summary_chart(domain_summary: list[dict]) -> None:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
        return

    metric_options = {
        "Total opportunity spaces": "Opportunity spaces",
        "Avg total score": "Avg total score",
        "Avg market signal": "Avg market signal",
        "Avg strategic potential": "Avg strategic potential",
        "Total high priority spaces": "High priority",
    }
    selected_metric_label = st.selectbox(
        "Domain metrics",
        list(metric_options.keys()),
    )
    selected_metric = metric_options[selected_metric_label]
    is_count_metric = selected_metric in ["Opportunity spaces", "High priority"]

    domains = [row["Domain"] for row in domain_summary]
    values = [row[selected_metric] for row in domain_summary]
    colors = [DOMAIN_COLORS.get(domain, "#ff7900") for domain in domains]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=domains,
            orientation="h",
            marker=dict(color=colors),
            hovertemplate=f"<b>%{{y}}</b><br>{selected_metric_label}: %{{x}}<extra></extra>",
        )
    )

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=20, t=10, b=10),
        xaxis=dict(
            title=selected_metric_label,
            dtick=1 if is_count_metric else None,
            tickformat="d" if is_count_metric else ".1f",
        ),
        yaxis_title="",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# def render_opportunity_matrix(opportunity_spaces: list[dict]) -> None:
#     try:
#         import plotly.express as px
#     except ModuleNotFoundError:
#         st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
#         return

#     rows = build_dashboard_rows(opportunity_spaces)
#     if not rows:
#         return

#     fig = px.scatter(
#         rows,
#         x="Market signal",
#         y="Evidence quality",
#         color="Domain",
#         size="Source diversity",
#         hover_name="Opportunity space",
#         hover_data=["ID", "Final score", "Signal count"],
#         color_discrete_map=DOMAIN_COLORS,
#         range_x=[0, 10],
#         range_y=[0, 10],
#     )

#     fig.update_layout(
#         height=520,
#         font=dict(family="Arial, sans-serif", size=13, color="#1f3d58"),
#         margin=dict(l=20, r=20, t=20, b=20),
#         paper_bgcolor="#ffffff",
#         plot_bgcolor="#ffffff",
#     )

#     st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_domain_scorecards(domain_summary: list[dict]) -> None:
    if not domain_summary:
        return

    for index in range(0, len(domain_summary), 3):
        cols = st.columns(3)
        for col, row in zip(cols, domain_summary[index:index + 3]):
            with col:
                with st.container(border=True):
                    if st.button(
                        row["Domain"],
                        key=f"open_domain_{row['Domain']}",
                        use_container_width=True,
                        ):
                            st.session_state["selected_domain"] = row["Domain"]
                            st.session_state["pending_view"] = "Opportunity detail"
                            st.session_state["scroll_to_top"] = True
                            st.rerun()

                    metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
                    with metric_col_1:
                        render_domain_card_stat("Spaces", row["Opportunity spaces"])
                    with metric_col_2:
                        render_domain_card_stat("Total", row["Avg total score"])
                    with metric_col_3:
                        render_domain_card_stat("Market", row["Avg market signal"])

                    st.caption(f"{row['High priority']} high priority spaces")


def render_domain_card_stat(label: str, value: str | int | float) -> None:
    st.markdown(
        f"""
        <div class="ob-domain-stat">
          <div class="ob-domain-stat-value">{value}</div>
          <div class="ob-domain-stat-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def normalize_clicked_id(value) -> str | None:
    if value is None:
        return None

    if hasattr(value, "tolist"):
        value = value.tolist()

    while isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
        if hasattr(value, "tolist"):
            value = value.tolist()

    if value is None:
        return None

    value = str(value)
    return value if value else None


def get_clicked_opportunity_id(clicked_point: dict, fig, rows: list[dict]) -> str | None:
    selected_point_id = normalize_clicked_id(clicked_point.get("customdata"))
    if selected_point_id:
        return selected_point_id

    curve_number = clicked_point.get("curveNumber")
    point_index = clicked_point.get("pointIndex", clicked_point.get("pointNumber"))
    if isinstance(curve_number, int) and isinstance(point_index, int):
        trace_customdata = fig.data[curve_number].customdata
        if trace_customdata is not None and 0 <= point_index < len(trace_customdata):
            return normalize_clicked_id(trace_customdata[point_index])

    if isinstance(point_index, int) and len(fig.data) == 1 and 0 <= point_index < len(rows):
        return normalize_clicked_id(rows[point_index]["ID"])

    return None


def render_domain_bubble_chart(opportunity_spaces: list[dict]) -> None:
    try:
        import plotly.express as px
    except ModuleNotFoundError:
        st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
        return

    try:
        from streamlit_plotly_events2 import plotly_events
    except ModuleNotFoundError:
        st.error(
            "Clickable bubble dots require streamlit-plotly-events2. "
            "Install it with: pip install streamlit-plotly-events2"
        )
        return

    rows = build_dashboard_rows(opportunity_spaces)
    if not rows:
        return

    fig = px.scatter(
        rows,
        x="Domain",
        y="Total score",
        size="Source diversity",
        color="Domain",
        hover_name="Opportunity space",
        hover_data=["ID", "Market signal", "Strategic potential", "Signal count"],
        custom_data=["ID"],
        color_discrete_map=DOMAIN_COLORS,
        range_y=[0, 10],
    )

    fig.update_layout(
        height=520,
        font=dict(family="Arial, sans-serif", size=13, color="#1f3d58"),
        margin=dict(l=20, r=20, t=20, b=80),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        xaxis=dict(tickangle=-30),
        showlegend=False,
    )

    clicked_points = plotly_events(
        fig,
        click_event=True,
        hover_event=False,
        select_event=False,
        override_height=520,
        key="domain_bubble_chart",
        config={"displayModeBar": False},
    )

    if not clicked_points:
        return

    clicked_point = clicked_points[0]
    selected_point_id = get_clicked_opportunity_id(clicked_point, fig, rows)

    if selected_point_id:
        st.session_state["selected_opportunity_id"] = selected_point_id
        st.session_state["pending_view"] = "Opportunity detail"
        st.session_state["scroll_to_top"] = True
        st.rerun()


def render_visual_exploration(
    opportunity_spaces: list[dict],
    domain_summary: list[dict],
) -> None:
    render_domain_scorecards(domain_summary)
    st.subheader("Domain bubbles")
    st.caption("X = domain | Y = Total score | Dot size = score")
    render_domain_bubble_chart(opportunity_spaces)


def render_dashboard(opportunity_spaces: list[dict]) -> None:
    render_sidebar_source_link()
    st.header("Dashboard")

    domain_summary = build_domain_summary(opportunity_spaces)
    render_dashboard_metrics(opportunity_spaces, domain_summary)

    st.markdown('<div class="ob-dashboard-section-spacer"></div>', unsafe_allow_html=True)

    st.subheader("Domain scorecards")
    render_visual_exploration(opportunity_spaces, domain_summary)

    summary_col, table_col = st.columns([1, 2])

    with summary_col:
        st.subheader("By domain")
        render_domain_summary_chart(domain_summary)

    with table_col:
        st.subheader("Opportunity spaces")
        selected_table_domain = st.selectbox(
            "Opportunity spaces per domain",
            ["All domains"] + config.ORANGE_BUSINESS_DOMAINS,
        )
        table_spaces = (
            opportunity_spaces
            if selected_table_domain == "All domains"
            else [
                space
                for space in opportunity_spaces
                if space.get("domain") == selected_table_domain
            ]
        )
        st.dataframe(
            build_dashboard_rows(table_spaces),
            use_container_width=True,
            hide_index=True,
        )
