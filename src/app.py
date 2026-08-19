import base64
import json
from pathlib import Path

import streamlit as st


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "os_example.json"
CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "alt_styles.css"
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "ob_logo.png"

ORANGE_BUSINESS_DOMAINS = [
    "Smart Industries",
    "Connectivity Solutions",
    "Cybersecurity",
    "Cloud",
    "Customer Experience",
    "Employee Experience",
    "Sustainability",
]


@st.cache_data
def load_opportunity_spaces(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("opportunity_space", [])


def load_css(path: Path) -> None:
    with path.open("r", encoding="utf-8") as file:
        st.markdown(f"<style>{file.read()}</style>", unsafe_allow_html=True)


@st.cache_data
def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def get_logo_img_html(class_name: str) -> str:
    if not LOGO_PATH.exists():
        return ""

    logo_base64 = image_to_base64(LOGO_PATH)
    return f'<img class="{class_name}" src="data:image/png;base64,{logo_base64}" alt="Orange Business logo">'


def render_empty_state(message: str) -> None:
    st.markdown(f'<div class="ob-empty">{message}</div>', unsafe_allow_html=True)


def render_signal_group(title: str, signals: list[dict]) -> None:
    st.subheader(title)

    if not signals:
        render_empty_state(f"No {title.lower()} found.")
        return

    for signal in signals:
        signal_title = signal.get("title")
        insight = signal.get("insight", "No insight provided.")
        url = signal.get("url")

        if signal_title:
            st.markdown(f"**{signal_title}**")
        st.write(insight)
        if url:
            st.link_button("Open source", url)


def render_list_section(title: str, items: list[str]) -> None:
    st.subheader(title)

    if not items:
        render_empty_state(f"No {title.lower()} listed.")
        return

    for item in items:
        st.write(f"- {item}")


def render_sidebar_logo() -> None:
    st.sidebar.markdown("---")
    if not LOGO_PATH.exists():
        return

    logo_base64 = image_to_base64(LOGO_PATH)
    st.sidebar.markdown(
        (
            '<div class="ob-sidebar-logo-wrap">'
            f'<img class="ob-logo-sidebar" src="data:image/png;base64,{logo_base64}" alt="Orange Business logo">'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Orange Business Innovation Radar",
    page_icon="",
    layout="wide",
)

load_css(CSS_PATH)

st.markdown(
    f"""
    <section class="ob-hero">
      {get_logo_img_html("ob-logo-main")}
      <h1 class="ob-hero-title">Innovation Radar</h1>
      <p class="ob-hero-copy">Draft viewer for Orange Business Opportunity Spaces</p>
    </section>
    """,
    unsafe_allow_html=True,
)

opportunity_spaces = load_opportunity_spaces(DATA_PATH)

if not opportunity_spaces:
    st.error("No opportunity spaces found.")
    st.stop()

selected_domain = st.sidebar.selectbox("Domain", ORANGE_BUSINESS_DOMAINS)

domain_opportunity_spaces = [
    space
    for space in opportunity_spaces
    if space.get("domain", "Unassigned") == selected_domain
]

if not domain_opportunity_spaces:
    st.sidebar.markdown("**Opportunity spaces**")
    st.sidebar.caption("No opportunity spaces for this domain yet.")
    render_sidebar_logo()
    st.caption(f"Domain: {selected_domain}")
    st.header("No opportunity spaces found")
    render_empty_state("This domain is ready in the interface, but the demo JSON has no opportunity spaces for it yet.")
    st.stop()

selected_name = st.sidebar.selectbox(
    "Opportunity space",
    [
        space.get("technology_name", "Untitled opportunity")
        for space in domain_opportunity_spaces
    ],
)

render_sidebar_logo()

selected_space = next(
    space
    for space in domain_opportunity_spaces
    if space.get("technology_name", "Untitled opportunity") == selected_name
)

st.caption(f"Domain: {selected_space.get('domain', 'Unassigned')}")
st.header(selected_space.get("technology_name", "Untitled opportunity"))
st.write(selected_space.get("overview_definition", "No overview available."))

scoring = selected_space.get("scoring", {})
score_col_1, score_col_2 = st.columns(2)

with score_col_1:
    st.metric(
        "Attractiveness",
        f"{scoring.get('attractiveness_score', 'N/A')}/10",
    )
    st.write(scoring.get("attractiveness_rationale", "No text available."))

with score_col_2:
    st.metric(
        "Urgency",
        f"{scoring.get('urgency_score', 'N/A')}/10",
    )
    st.write(scoring.get("urgency_rationale", "No text available."))

signals_tab, use_cases_tab, audience_tab, raw_data_tab = st.tabs(
    ["Signals", "Use cases", "Target audience", "Raw data"]
)

with signals_tab:
    signals = selected_space.get("signals_and_sources", {})
    render_signal_group("Regulation", signals.get("regulation", []))
    render_signal_group("Buying signals", signals.get("buying_signals", []))
    render_signal_group("Market trends", signals.get("market_trends", []))

with use_cases_tab:
    use_cases = selected_space.get("use_cases_and_value_drivers", [])

    if not use_cases:
        render_empty_state("No use cases listed.")
    else:
        for use_case in use_cases:
            st.subheader(use_case.get("use_case", "Untitled use case"))
            st.write(use_case.get("value_driver", "No value driver provided."))

with audience_tab:
    audience = selected_space.get("target_audience", {})
    audience_col_1, audience_col_2, audience_col_3 = st.columns(3)

    with audience_col_1:
        render_list_section("Personas", audience.get("personas", []))

    with audience_col_2:
        render_list_section("Verticals", audience.get("verticals", []))

    with audience_col_3:
        render_list_section("Geographies", audience.get("geographies", []))

with raw_data_tab:
    st.json(selected_space)
