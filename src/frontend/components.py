import streamlit as st
import streamlit.components.v1 as st_components

from data_loader import image_to_base64
import front_config as config


def render_hero() -> None:
    st.markdown(
        """
        <section class="ob-hero">
          <h1 class="ob-hero-title">Innovation Radar</h1>
          <p class="ob-hero-copy">Demo viewer</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def scroll_to_top_once() -> None:
    if not st.session_state.pop("scroll_to_top", False):
        return

    st_components.html(
        """
        <script>
          window.parent.scrollTo({ top: 0, left: 0, behavior: "instant" });
        </script>
        """,
        height=0,
    )


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


def render_sidebar_source_link() -> None:
    st.sidebar.markdown("---")
    if not config.GITHUB_LOGO_PATH.exists():
        st.sidebar.link_button("Source code", config.GITHUB_URL)
        return

    github_logo_base64 = image_to_base64(config.GITHUB_LOGO_PATH)
    st.sidebar.markdown(
        (
            '<div class="ob-sidebar-source-wrap">'
            f'<a class="ob-sidebar-source-link" href="{config.GITHUB_URL}" target="_blank" rel="noopener noreferrer">'
            f'<img class="ob-github-logo-sidebar" src="data:image/png;base64,{github_logo_base64}" alt="GitHub source code">'
            "</a>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
