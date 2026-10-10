from __future__ import annotations

from pathlib import Path

import streamlit as st

from config import ConfigError, Settings, load_settings
from mission_engine import MissionOutcome, generate_mission
from models import (
    DIFFICULTY_LABELS,
    ENVIRONMENT_LABELS,
    INTEREST_LABELS,
    MissionRequest,
)
from storage import MAX_REFLECTION_LENGTH, MissionStore

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
CSS_PATH = ASSETS_DIR / "style.css"

st.set_page_config(
    page_title="OutsideQuest AI",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="auto",
)


def _load_css() -> None:
    st.markdown(
        f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    defaults = {
        "outcome": None,
        "outside_mode": False,
        "show_complete_form": False,
        "saved_completion": False,
        "confirm_delete": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _source_badge(mission) -> str:
    if mission.source == "ai":
        model = mission.model or "unknown model"
        provider = mission.provider or "unknown provider"
        return f"<span class='oq-badge-ai'>AI-generated · {provider} · {model}</span>"
    return (
        "<span class='oq-badge-fallback'>Curated fallback mission "
        "(written by humans, not AI)</span>"
    )


def _render_mission(mission, outcome: MissionOutcome | None = None) -> None:
    environment = ENVIRONMENT_LABELS.get(mission.environment, mission.environment)
    difficulty = DIFFICULTY_LABELS.get(mission.difficulty, mission.difficulty)
    steps_html = "".join(f"<li>{step}</li>" for step in mission.steps)
    safety_html = "".join(f"<li>{note}</li>" for note in mission.safety_notes)

    st.markdown(
        f"""
        <div class="oq-card">
          {_source_badge(mission)}
          <h2>{mission.title}</h2>
          <div class="oq-meta">
            <span class="oq-chip">{mission.duration_minutes} min</span>
            <span class="oq-chip">{environment}</span>
            <span class="oq-chip">{difficulty}</span>
          </div>
          <p>{mission.introduction}</p>
          <h3>Mission steps</h3>
          <ol class="oq-steps">{steps_html}</ol>
          <h3>Observation goal</h3>
          <p>{mission.observation_goal}</p>
          <h3>Done when</h3>
          <p>{mission.completion_condition}</p>
          <div class="oq-safety">
            <h3>Safety first</h3>
            <ul>{safety_html}</ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if outcome is not None:
        for warning in outcome.warnings:
            st.warning(warning)
        if outcome.error and mission.source == "curated_fallback":
            st.caption("Reason for fallback: " + outcome.error[:400])


def _render_print_control() -> None:
    st.markdown("<div class='oq-no-print'>", unsafe_allow_html=True)
    try:
        st.html(
            "<button class='oq-print-button' type='button' "
            "onclick=\"window.print()\">Print mission card</button>"
        )
    except AttributeError:
        pass
    st.caption("Or press Ctrl+P (Windows) to print a clean card.")
    st.markdown("</div>", unsafe_allow_html=True)


def _completion_block(mission, store: MissionStore) -> None:
    if st.session_state.saved_completion:
        st.success("Mission saved to your local history. Now go outside.")
        return

    if not st.session_state.show_complete_form:
        if st.button("Mark mission complete", type="primary"):
            st.session_state.show_complete_form = True
            st.rerun()
        return

    reflection = st.text_area(
        "One-line reflection (optional)",
        max_chars=MAX_REFLECTION_LENGTH,
        placeholder="What did you notice that you would have missed online?",
    )
    col_save, col_skip, col_cancel = st.columns(3)
    with col_save:
        save_clicked = st.button("Save with reflection")
    with col_skip:
        skip_clicked = st.button("Save without reflection")
    with col_cancel:
        cancel_clicked = st.button("Not yet")

    if cancel_clicked:
        st.session_state.show_complete_form = False
        st.rerun()
    if save_clicked or skip_clicked:
        store.save_completion(mission, reflection if save_clicked else None)
        st.session_state.show_complete_form = False
        st.session_state.saved_completion = True
        st.rerun()


def _outside_mode_view(mission, outcome: MissionOutcome, store: MissionStore) -> None:
    st.markdown("<div class='oq-hero'><h1>Outside mode</h1></div>", unsafe_allow_html=True)
    st.caption("Phone stays pocketed. Come back when the mission is done.")
    _render_mission(mission, outcome)
    _render_print_control()
    st.markdown("<div class='oq-no-print'>", unsafe_allow_html=True)
    _completion_block(mission, store)
    if st.button("Exit outside mode"):
        st.session_state.outside_mode = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _quest_tab(settings: Settings, store: MissionStore) -> None:
    outcome: MissionOutcome | None = st.session_state.outcome

    if st.session_state.outside_mode and outcome is not None:
        _outside_mode_view(outcome.mission, outcome, store)
        return

    with st.form("quest_form"):
        st.subheader("Design your quest")
        col_a, col_b = st.columns(2)
        with col_a:
            duration = st.radio(
                "How much time do you have?",
                options=[10, 20, 30],
                format_func=lambda d: f"{d} minutes",
                horizontal=True,
            )
            environment = st.selectbox(
                "Where will you go?",
                options=list(ENVIRONMENT_LABELS),
                format_func=lambda e: ENVIRONMENT_LABELS[e],
            )
        with col_b:
            difficulty = st.radio(
                "Challenge level",
                options=list(DIFFICULTY_LABELS),
                format_func=lambda d: DIFFICULTY_LABELS[d],
                horizontal=True,
            )
            interests = st.multiselect(
                "Interests (optional)",
                options=list(INTEREST_LABELS),
                format_func=lambda i: INTEREST_LABELS[i],
            )
        submitted = st.form_submit_button("Generate my mission", type="primary")

    if submitted:
        request = MissionRequest(
            duration_minutes=duration,
            environment=environment,
            difficulty=difficulty,
            interests=interests,
        )
        with st.spinner("Asking the open-weight model for a mission..."):
            outcome = generate_mission(request, settings)
        st.session_state.outcome = outcome
        st.session_state.show_complete_form = False
        st.session_state.saved_completion = False
        st.rerun()

    if outcome is None:
        st.info(
            "Pick your time, place, and challenge level, then generate a mission. "
            "The screen time ends when the mission begins."
        )
        return

    _render_mission(outcome.mission, outcome)
    st.markdown("<div class='oq-no-print'>", unsafe_allow_html=True)
    if st.button("Go outside (hide controls)"):
        st.session_state.outside_mode = True
        st.rerun()
    _render_print_control()
    _completion_block(outcome.mission, store)
    st.markdown("</div>", unsafe_allow_html=True)


def _history_tab(store: MissionStore) -> None:
    st.subheader("Local mission history")
    st.caption(
        "Stored only in the SQLite database on this device. No location, account, "
        "or credentials are recorded."
    )
    rows = store.list_completions(limit=100)
    if not rows:
        st.info("No completed missions yet.")
    else:
        for row in rows:
            reflection = row["reflection"] or "No reflection"
            st.markdown(
                f"**{row['title']}** · {row['duration_minutes']} min · "
                f"{ENVIRONMENT_LABELS.get(row['environment'], row['environment'])} · "
                f"{row['completed_at']}"
            )
            st.caption(f"{row['source']} · {reflection}")
        st.caption(f"{len(rows)} completed mission(s) shown.")

    col_a, _col_b = st.columns([1, 1])
    with col_a:
        if st.button("Delete my local history"):
            st.session_state.confirm_delete = True
            st.rerun()
    if st.session_state.confirm_delete:
        st.warning("Delete all local mission history? This cannot be undone.")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, delete everything"):
                removed = store.clear()
                st.session_state.confirm_delete = False
                st.success(f"Deleted {removed} record(s).")
                st.rerun()
        with col_no:
            if st.button("Keep my history"):
                st.session_state.confirm_delete = False
                st.rerun()


def main() -> None:
    _load_css()
    _init_state()

    try:
        settings = load_settings()
    except ConfigError as exc:
        st.error(f"Configuration error: {exc}")
        st.stop()

    store = MissionStore(settings.db_path)

    with st.sidebar:
        st.markdown("**OutsideQuest AI**")
        st.caption("Less scrolling. More exploring.")
        st.divider()
        st.markdown("**Inference setup**")
        st.code(
            f"provider: {settings.provider}\nmodel: {settings.model}",
            language=None,
        )
        if settings.has_credentials:
            st.caption(f"API key detected via {settings.api_key_env}.")
        else:
            st.warning(
                f"No API key found ({settings.api_key_env}). "
                "Missions will come from the curated fallback set, honestly labeled."
            )
        st.divider()
        st.markdown("**Privacy**")
        st.caption(
            "AI requests send only your quest settings (time, place type, difficulty, "
            "interests) to the selected provider. History stays in local SQLite. "
            "No GPS or account data is collected."
        )
        st.caption(f"Database: {settings.db_path}")

    st.markdown(
        "<div class='oq-hero'><h1>🌿 OutsideQuest AI</h1>"
        "<p class='oq-tagline'>Less scrolling. More exploring.</p></div>",
        unsafe_allow_html=True,
    )

    quest_tab, history_tab = st.tabs(["New quest", "History"])
    with quest_tab:
        _quest_tab(settings, store)
    with history_tab:
        _history_tab(store)


main()
