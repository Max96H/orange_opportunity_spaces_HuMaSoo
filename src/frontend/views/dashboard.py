from collections import defaultdict

import streamlit as st

from components import render_sidebar_logo
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


def get_score(space: dict, score_name: str, default: float = 0.0) -> float:
    score = space.get("scoring", {}).get(score_name, default)
    if isinstance(score, (int, float)):
        return max(0.0, min(10.0, float(score)))
    return default


def get_domain_angles() -> dict[str, float]:
    slice_width = 360 / len(config.ORANGE_BUSINESS_DOMAINS)
    return {
        domain: index * slice_width
        for index, domain in enumerate(config.ORANGE_BUSINESS_DOMAINS)
    }


def get_clicked_point_id(clicked_points: list[dict], point_ids: list[str]) -> str | None:
    if not clicked_points:
        return None

    point = clicked_points[0]
    customdata = point.get("customdata")
    if customdata:
        return customdata[0] if isinstance(customdata, list) else customdata

    point_index = point.get("pointIndex", point.get("pointNumber"))
    if isinstance(point_index, int) and 0 <= point_index < len(point_ids):
        return point_ids[point_index]

    return None


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

        final_scores = [get_score(space, "final_score") for space in spaces]
        market_scores = [
            get_score(space, "market_signal_strength")
            for space in spaces
        ]
        evidence_scores = [
            get_score(space, "evidence_quality")
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
                "Avg final score": round(sum(final_scores) / len(final_scores), 1),
                "Avg market signal": round(sum(market_scores) / len(market_scores), 1),
                "Avg evidence quality": round(
                    sum(evidence_scores) / len(evidence_scores),
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
    top_final_score, top_final_domain = get_leading_domain(
        domain_summary,
        "Avg final score",
    )
    top_market_score, top_market_domain = get_leading_domain(
        domain_summary,
        "Avg market signal",
    )

    metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)

    with metric_1:
        render_kpi_card("Opportunity spaces", total_spaces)

    with metric_2:
        render_kpi_card("Active domains", active_domains)

    with metric_3:
        render_kpi_card("Top final score", top_final_score, top_final_domain)

    with metric_4:
        render_kpi_card("Top market signal", top_market_score, top_market_domain)

    with metric_5:
        render_kpi_card("High priority spaces", high_priority_total)


def build_dashboard_rows(opportunity_spaces: list[dict]) -> list[dict]:
    rows = []

    for space in opportunity_spaces:
        scoring = space.get("scoring", {})
        rows.append(
            {
                "ID": space.get("id", ""),
                "Domain": space.get("domain", "Unassigned"),
                "Opportunity space": space.get("technology_name", "Untitled opportunity"),
                "Final score": scoring.get("final_score"),
                "Market signal": scoring.get("market_signal_strength"),
                "Source diversity": scoring.get("source_diversity"),
                "Evidence quality": scoring.get("evidence_quality"),
                "Signal count": get_signal_count(space),
            }
        )

    return rows


def render_dashboard_radar(opportunity_spaces: list[dict]) -> None:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
        return

    try:
        from streamlit_plotly_events2 import plotly_events
    except ModuleNotFoundError:
        st.error(
            "Clickable radar dots require streamlit-plotly-events2. "
            "Install it with: pip install streamlit-plotly-events2"
        )
        return

    domain_angles = get_domain_angles()
    slice_width = 360 / len(config.ORANGE_BUSINESS_DOMAINS)
    theta = []
    radius = []
    sizes = []
    colors = []
    labels = []
    point_ids = []
    hover_text = []

    for space in opportunity_spaces:
        domain = space.get("domain")
        if domain not in domain_angles:
            continue

        final_score = get_score(space, "final_score")
        market_signal = get_score(space, "market_signal_strength")
        source_diversity = get_score(space, "source_diversity")
        evidence_quality = get_score(space, "evidence_quality")

        theta.append(domain_angles[domain])
        radius.append(final_score)
        sizes.append(14 + final_score * 4)
        colors.append(DOMAIN_COLORS.get(domain, "#ff7900"))
        labels.append(space.get("id", ""))
        point_ids.append(space.get("id", ""))
        hover_text.append(
            f"<b>{space.get('technology_name', 'Untitled opportunity')}</b><br>"
            f"ID: {space.get('id', 'N/A')}<br>"
            f"Domain: {domain}<br>"
            f"Final score: {final_score:g}/10<br>"
            f"Market signal: {market_signal:g}/10<br>"
            f"Source diversity: {source_diversity:g}/10<br>"
            f"Evidence quality: {evidence_quality:g}/10"
        )

    fig = go.Figure()

    for domain in config.ORANGE_BUSINESS_DOMAINS:
        fig.add_trace(
            go.Barpolar(
                r=[10],
                theta=[domain_angles[domain]],
                width=[slice_width],
                marker=dict(
                    color="#f4f4f4",
                    line=dict(color="#dedede", width=1),
                    opacity=0.55,
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.add_trace(
        go.Scatterpolar(
            r=radius,
            theta=theta,
            mode="markers+text",
            text=labels,
            textposition="top center",
            customdata=point_ids,
            marker=dict(
                size=sizes,
                color=colors,
                line=dict(color="#000000", width=1),
                opacity=0.9,
            ),
            hovertext=hover_text,
            hoverinfo="text",
            showlegend=False,
        )
    )

    fig.update_layout(
        height=650,
        showlegend=False,
        font=dict(family="Arial, sans-serif", size=13, color="#1f3d58"),
        polar=dict(
            radialaxis=dict(
                range=[0, 10],
                tickvals=[2, 5, 8],
                ticktext=["Low", "Medium", "High"],
                gridcolor="#cfcfcf",
                showline=False,
            ),
            angularaxis=dict(
                tickmode="array",
                tickvals=list(domain_angles.values()),
                ticktext=[f"<b>{domain.upper()}</b>" for domain in config.ORANGE_BUSINESS_DOMAINS],
                direction="clockwise",
                rotation=90,
                gridcolor="#dedede",
                tickfont=dict(size=14),
            ),
            bgcolor="#ffffff",
        ),
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )

    clicked_points = plotly_events(
        fig,
        click_event=True,
        hover_event=False,
        select_event=False,
        override_height=650,
        key="dashboard_opportunity_radar",
        config={"displayModeBar": False},
    )

    selected_point_id = get_clicked_point_id(clicked_points, point_ids)
    if selected_point_id:
        st.session_state["selected_opportunity_id"] = selected_point_id
        st.session_state["pending_view"] = "Opportunity detail"
        st.rerun()


def render_domain_summary_chart(domain_summary: list[dict]) -> None:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
        return

    metric_options = {
        "Total opportunity spaces": "Opportunity spaces",
        "Avg final score": "Avg final score",
        "Avg market signal": "Avg market signal",
        "Avg evidence quality": "Avg evidence quality",
        "Total high priority spaces": "High priority",
    }
    selected_metric_label = st.selectbox(
        "Domain metric",
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
                st.markdown(
                    f"""
                    <div class="ob-domain-card">
                      <div class="ob-domain-card-title">{row["Domain"]}</div>
                      <div class="ob-domain-card-grid">
                        <div>
                          <div class="ob-domain-card-value">{row["Opportunity spaces"]}</div>
                          <div class="ob-domain-card-label">Spaces</div>
                        </div>
                        <div>
                          <div class="ob-domain-card-value">{row["Avg final score"]}</div>
                          <div class="ob-domain-card-label">Final</div>
                        </div>
                        <div>
                          <div class="ob-domain-card-value">{row["Avg market signal"]}</div>
                          <div class="ob-domain-card-label">Market</div>
                        </div>
                      </div>
                      <div class="ob-domain-card-priority">{row["High priority"]} high priority spaces</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_domain_bubble_chart(opportunity_spaces: list[dict]) -> None:
    try:
        import plotly.express as px
    except ModuleNotFoundError:
        st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
        return

    rows = build_dashboard_rows(opportunity_spaces)
    if not rows:
        return

    fig = px.scatter(
        rows,
        x="Domain",
        y="Final score",
        size="Source diversity",
        color="Domain",
        hover_name="Opportunity space",
        hover_data=["ID", "Market signal", "Evidence quality", "Signal count"],
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

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# def render_domain_heatmap(domain_summary: list[dict]) -> None:
#     try:
#         import plotly.graph_objects as go
#     except ModuleNotFoundError:
#         st.error("Plotly is required for dashboard charts. Install it with: pip install plotly")
#         return

#     metrics = [
#         "Opportunity spaces",
#         "Avg final score",
#         "Avg market signal",
#         "Avg evidence quality",
#         "High priority",
#     ]
#     domains = [row["Domain"] for row in domain_summary]
#     values = [[row[metric] for metric in metrics] for row in domain_summary]

#     fig = go.Figure(
#         data=go.Heatmap(
#             z=values,
#             x=metrics,
#             y=domains,
#             colorscale=[
#                 [0, "#f6f6f6"],
#                 [0.5, "#ffb366"],
#                 [1, "#ff7900"],
#             ],
#             hovertemplate="<b>%{y}</b><br>%{x}: %{z}<extra></extra>",
#         )
#     )

#     fig.update_layout(
#         height=420,
#         font=dict(family="Arial, sans-serif", size=13, color="#1f3d58"),
#         margin=dict(l=10, r=20, t=10, b=10),
#         paper_bgcolor="#ffffff",
#         plot_bgcolor="#ffffff",
#     )

#     st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_visual_exploration(
    opportunity_spaces: list[dict],
    domain_summary: list[dict],
) -> None:
    # matrix_tab, scorecards_tab, bubble_tab, heatmap_tab = st.tabs(
    scorecards_tab, bubble_tab = st.tabs(
        [
            # "Opportunity matrix",
            "Domain scorecards",
            "Domain bubbles",
            # "Domain heatmap",
        ]
    )

    # with matrix_tab:
    #     st.caption("X = market signal | Y = evidence quality | Size = source diversity")
    #     render_opportunity_matrix(opportunity_spaces)

    with scorecards_tab:
        render_domain_scorecards(domain_summary)

    with bubble_tab:
        st.caption("X = domain | Y = final score | Dot size = source diversity")
        render_domain_bubble_chart(opportunity_spaces)

    # with heatmap_tab:
    #     render_domain_heatmap(domain_summary)


def render_dashboard(opportunity_spaces: list[dict]) -> None:
    render_sidebar_logo()
    st.header("Dashboard")
    st.caption("Portfolio overview for Orange Business opportunity spaces")

    domain_summary = build_domain_summary(opportunity_spaces)
    render_dashboard_metrics(opportunity_spaces, domain_summary)

    st.subheader("Radar")
    st.caption("Slice = domain | Ring = final score | Dot size = final score")
    radar_left, radar_center, radar_right = st.columns([0.5, 5, 0.5])
    with radar_center:
        render_dashboard_radar(opportunity_spaces)

    st.subheader("Alternative views")
    render_visual_exploration(opportunity_spaces, domain_summary)

    summary_col, table_col = st.columns([1, 2])

    with summary_col:
        st.subheader("By domain")
        render_domain_summary_chart(domain_summary)

    with table_col:
        st.subheader("Opportunity spaces")
        selected_table_domain = st.selectbox(
            "Table domain",
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
