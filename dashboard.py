import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import hashlib

from db import get_connection
from checklist import CHECKLIST
from storage import presigned_url

st.set_page_config(
    page_title="Call Center Analytics",
    page_icon="📞",
    layout="wide",
)

# ── Аутентификация ─────────────────────────────────────────────────────────────
USERS = {
    "Julia": {
        "password_hash": hashlib.sha256("6o5OeXT8lPwuMP".encode()).hexdigest(),
        "role": "admin",
        "display_name": "Julia",
    },
}

def check_login(username: str, password: str) -> bool:
    user = USERS.get(username)
    if not user:
        return False
    return user["password_hash"] == hashlib.sha256(password.encode()).hexdigest()

def show_login():
    col_c = st.columns([1, 1, 1])[1]
    with col_c:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 📞 Call Center Analytics")
        st.markdown("### Вход в систему")
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        if st.button("Войти", use_container_width=True):
            if check_login(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["role"] = USERS[username]["role"]
                st.rerun()
            else:
                st.error("Неверный логин или пароль")

if not st.session_state.get("authenticated"):
    show_login()
    st.stop()


# ── Подключение к локальной базе ──────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data():
    conn = get_connection()
    df = pd.read_sql("""
        SELECT
            file_name, department, call_topic, call_summary,
            call_type, customer_intent, urgency, resolution_status,
            agent_performance_score, customer_satisfaction,
            escalation_flag, key_topics, transcript_text,
            silence_pct, pause_count, operator_talk_ratio, checklist_json,
            compliance_json, audio_key, call_type_override, operator_name, analyzed_at
        FROM call_analysis
        ORDER BY department, call_topic
    """, conn)
    conn.close()
    df["call_type_effective"] = df["call_type_override"].where(
        df["call_type_override"].notna() & (df["call_type_override"] != ""), df["call_type"]
    )
    return df


def set_call_type_override(file_name: str, value: str | None) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE call_analysis SET call_type_override = %s WHERE file_name = %s",
            (value, file_name),
        )
    conn.commit()
    conn.close()


def set_operator_name(file_name: str, value: str | None) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE call_analysis SET operator_name = %s WHERE file_name = %s",
            (value, file_name),
        )
    conn.commit()
    conn.close()


@st.cache_data(ttl=60)
def load_segments(file_name: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql(
        "SELECT seg_index, start_sec, end_sec, speaker, text FROM call_segments "
        "WHERE file_name = %s ORDER BY seg_index",
        conn, params=(file_name,),
    )
    conn.close()
    return df

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("📞 Call Center Analytics")
username = st.session_state.get("username", "")
role = st.session_state.get("role", "")
st.sidebar.markdown(f"👤 **{username}** · {role}")
if st.sidebar.button("Выйти"):
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")

df_all = load_data()

dept_options = ["Все"] + sorted(df_all["department"].unique().tolist())
selected_dept = st.sidebar.selectbox("Отдел", dept_options)

urgency_options = ["Все"] + sorted(df_all["urgency"].dropna().unique().tolist())
selected_urgency = st.sidebar.selectbox("Срочность", urgency_options)

status_options = ["Все"] + sorted(df_all["resolution_status"].dropna().unique().tolist())
selected_status = st.sidebar.selectbox("Статус", status_options)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Обновить данные"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("v1.4 · 2026-07-04")

# ── Фильтрация ─────────────────────────────────────────────────────────────────
df = df_all.copy()
if selected_dept != "Все":
    df = df[df["department"] == selected_dept]
if selected_urgency != "Все":
    df = df[df["urgency"] == selected_urgency]
if selected_status != "Все":
    df = df[df["resolution_status"] == selected_status]

# ── Заголовок и вкладки ───────────────────────────────────────────────────────
st.title("📞 Аналитика колл-центра")
tab_analytics, tab_calls, tab_operators, tab_team = st.tabs(
    ["📊 Аналитика", "📁 Звонки", "🧑‍💼 Операторы", "👥 Команда разработчиков"]
)

with tab_analytics:
    st.caption(f"Локальная база: call_center.db · {len(df)} из {len(df_all)} звонков")

    # ── KPI карточки ──────────────────────────────────────────────────────────
    st.markdown("### Ключевые показатели")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    avg_agent = df["agent_performance_score"].mean()
    avg_client = df["customer_satisfaction"].mean()
    resolved_pct = (df["resolution_status"] == "resolved").mean() * 100
    escalated = df["escalation_flag"].sum()
    avg_silence = df["silence_pct"].mean()
    k1.metric("Звонков", len(df), f"из {len(df_all)} всего")
    k2.metric("Оценка оператора", f"{avg_agent:.1f}/10")
    k3.metric("Удовл. клиента", f"{avg_client:.1f}/10")
    k4.metric("Решено", f"{resolved_pct:.0f}%")
    k5.metric("Эскалаций", int(escalated))
    k6.metric("Тишина в диалоге", f"{avg_silence:.0f}%" if pd.notna(avg_silence) else "—")

    st.markdown("---")

    # ── Графики ───────────────────────────────────────────────────────────────
    col_left, col_mid, col_right = st.columns([2, 1.5, 1.5])

    with col_left:
        st.markdown("#### Оценки по звонкам")
        fig_scores = go.Figure()
        fig_scores.add_trace(go.Bar(
            name="Оператор", x=df["call_topic"],
            y=df["agent_performance_score"], marker_color="#1f77b4",
        ))
        fig_scores.add_trace(go.Bar(
            name="Клиент", x=df["call_topic"],
            y=df["customer_satisfaction"], marker_color="#ff7f0e",
        ))
        fig_scores.update_layout(
            barmode="group", yaxis=dict(range=[0, 10], title="Оценка"),
            xaxis_tickangle=-30, legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=10, b=0), height=300,
        )
        st.plotly_chart(fig_scores, use_container_width=True)

    with col_mid:
        st.markdown("#### Срочность")
        urgency_counts = df["urgency"].value_counts()
        color_map = {"low": "#2ecc71", "medium": "#f39c12", "high": "#e74c3c"}
        fig_urg = px.pie(
            values=urgency_counts.values, names=urgency_counts.index,
            color=urgency_counts.index, color_discrete_map=color_map, hole=0.45,
        )
        fig_urg.update_layout(
            showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            margin=dict(t=10, b=0), height=300,
        )
        st.plotly_chart(fig_urg, use_container_width=True)

    with col_right:
        st.markdown("#### По отделам")
        dept_stats = df_all.groupby("department").agg(
            звонков=("call_topic", "count"),
            оператор=("agent_performance_score", "mean"),
            клиент=("customer_satisfaction", "mean"),
        ).round(1).reset_index()
        dept_stats.columns = ["Отдел", "Звонков", "Оператор", "Клиент"]
        st.dataframe(dept_stats, use_container_width=True, hide_index=True)
        if len(df_all["department"].unique()) > 1:
            fig_dept = px.bar(
                dept_stats, x="Отдел", y=["Оператор", "Клиент"],
                barmode="group", color_discrete_sequence=["#1f77b4", "#ff7f0e"],
            )
            fig_dept.update_layout(
                yaxis=dict(range=[0, 10]), showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=10, b=0), height=200,
            )
            st.plotly_chart(fig_dept, use_container_width=True)

    st.markdown("---")

    # ── Таблица звонков ───────────────────────────────────────────────────────
    st.markdown("### Все звонки")
    display_df = df[[
        "department", "call_topic", "call_type_effective", "urgency",
        "resolution_status", "agent_performance_score", "customer_satisfaction",
        "escalation_flag"
    ]].copy()
    display_df.columns = ["Отдел", "Тема", "Тип", "Срочность", "Статус", "Оператор", "Клиент", "Эскалация"]
    st.dataframe(
        display_df, use_container_width=True, hide_index=True,
        column_config={
            "Оператор": st.column_config.ProgressColumn("Оператор", min_value=0, max_value=10, format="%d/10"),
            "Клиент": st.column_config.ProgressColumn("Клиент", min_value=0, max_value=10, format="%d/10"),
            "Эскалация": st.column_config.CheckboxColumn("Эскалация"),
        },
    )

# ── Вкладка звонков: галерея + плеер ─────────────────────────────────────────
with tab_calls:
    if "selected_call" not in st.session_state:
        st.session_state["selected_call"] = None
    if "seek_time" not in st.session_state:
        st.session_state["seek_time"] = 0.0

    st.caption(f"{len(df)} звонков (после фильтров слева)")

    if df.empty:
        st.info("Нет данных по выбранным фильтрам.")
    else:
        urgency_badge = {"low": "🟢", "medium": "🟠", "high": "🔴"}
        status_icon = {"resolved": "✅", "unresolved": "⏳", "escalated": "🚨"}

        cols_per_row = 3
        rows_of_calls = [df.iloc[i:i + cols_per_row] for i in range(0, len(df), cols_per_row)]
        for chunk in rows_of_calls:
            cols = st.columns(cols_per_row)
            for col, (_, call) in zip(cols, chunk.iterrows()):
                with col, st.container(border=True):
                    st.markdown(f"**{call['call_topic']}**")
                    st.caption(f"{call['department']} · {urgency_badge.get(call['urgency'], '⚪')} {call['urgency']}")
                    type_icon = "🏷️" if pd.notna(call["call_type_override"]) and call["call_type_override"] else ""
                    st.caption(f"{type_icon} {call['call_type_effective']}".strip())
                    if pd.notna(call["operator_name"]) and call["operator_name"]:
                        st.caption(f"🧑‍💼 {call['operator_name']}")
                    score = call["agent_performance_score"]
                    st.progress(
                        (score or 0) / 10,
                        text=f"Оператор {score:.0f}/10" if pd.notna(score) else "Оператор —",
                    )
                    st.caption(f"{status_icon.get(call['resolution_status'], '❔')} {call['resolution_status']}")
                    if st.button("Открыть", key=f"open_{call['file_name']}", use_container_width=True):
                        st.session_state["selected_call"] = call["file_name"]
                        st.session_state["seek_time"] = 0.0
                        st.rerun()

    st.markdown("---")

    selected_file = st.session_state["selected_call"]
    if not selected_file:
        st.info("Выберите звонок в галерее выше, чтобы открыть плеер и транскрипт.")
    else:
        match = df_all[df_all["file_name"] == selected_file]
        if match.empty:
            st.warning("Этот звонок больше не проходит по фильтрам.")
        else:
            row = match.iloc[0]
            st.markdown(f"### {row['call_topic']}")

            audio_url = presigned_url(row.get("audio_key"))
            if audio_url:
                st.audio(audio_url, start_time=st.session_state["seek_time"])
            else:
                st.caption("🔇 Аудио для этого звонка недоступно (хранилище не настроено или файл не заливался).")

            d1, d2 = st.columns([1, 2])
            with d1:
                st.markdown("**Параметры звонка**")
                st.markdown(f"- **Отдел:** {row['department']}")

                has_override = pd.notna(row["call_type_override"]) and row["call_type_override"]
                editing_key = f"editing_type_{row['file_name']}"
                if has_override:
                    st.markdown(f"- **Тип:** {row['call_type_override']} 🏷️")
                    st.caption(f"Подтверждено вручную · AI предложил: {row['call_type']}")
                    if st.button("✏️ Изменить", key=f"redo_{row['file_name']}"):
                        st.session_state[editing_key] = True
                        st.rerun()
                else:
                    st.markdown(f"- **Тип:** {row['call_type']} _(AI, не подтверждено)_")
                    if not st.session_state.get(editing_key):
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            if st.button("✅ Подтвердить", key=f"confirm_{row['file_name']}", use_container_width=True):
                                set_call_type_override(row["file_name"], row["call_type"])
                                st.cache_data.clear()
                                st.rerun()
                        with bc2:
                            if st.button("❌ Исправить", key=f"reject_{row['file_name']}", use_container_width=True):
                                st.session_state[editing_key] = True
                                st.rerun()

                if st.session_state.get(editing_key):
                    new_type = st.text_input(
                        "Новая категория",
                        value=str(row["call_type_effective"]),
                        key=f"new_type_{row['file_name']}",
                    )
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.button("💾 Сохранить", key=f"save_type_{row['file_name']}", use_container_width=True):
                            set_call_type_override(row["file_name"], new_type)
                            st.session_state[editing_key] = False
                            st.cache_data.clear()
                            st.rerun()
                    with ec2:
                        if st.button("Отмена", key=f"cancel_type_{row['file_name']}", use_container_width=True):
                            st.session_state[editing_key] = False
                            st.rerun()

                has_operator = pd.notna(row["operator_name"]) and row["operator_name"]
                operator_editing_key = f"editing_operator_{row['file_name']}"
                if not st.session_state.get(operator_editing_key):
                    st.markdown(f"- **Оператор:** {row['operator_name'] if has_operator else '—'}")
                    if st.button(
                        "✏️ Указать оператора" if not has_operator else "✏️ Изменить оператора",
                        key=f"edit_operator_{row['file_name']}",
                    ):
                        st.session_state[operator_editing_key] = True
                        st.rerun()
                else:
                    new_operator = st.text_input(
                        "Имя оператора",
                        value=str(row["operator_name"]) if has_operator else "",
                        key=f"new_operator_{row['file_name']}",
                    )
                    oc1, oc2 = st.columns(2)
                    with oc1:
                        if st.button("💾 Сохранить", key=f"save_operator_{row['file_name']}", use_container_width=True):
                            set_operator_name(row["file_name"], new_operator)
                            st.session_state[operator_editing_key] = False
                            st.cache_data.clear()
                            st.rerun()
                    with oc2:
                        if st.button("Отмена", key=f"cancel_operator_{row['file_name']}", use_container_width=True):
                            st.session_state[operator_editing_key] = False
                            st.rerun()

                st.markdown(f"- **Намерение клиента:** {row['customer_intent']}")
                st.markdown(f"- **Срочность:** {row['urgency']}")
                st.markdown(f"- **Статус:** {row['resolution_status']}")
                st.markdown(f"- **Оценка оператора (чек-лист):** {row['agent_performance_score']}/10")
                st.markdown(f"- **Удовл. клиента:** {row['customer_satisfaction']}/10")
                st.markdown(f"- **Эскалация:** {'Да' if row['escalation_flag'] else 'Нет'}")
                if pd.notna(row["silence_pct"]):
                    st.markdown(f"- **Тишина в диалоге:** {row['silence_pct']:.0f}% ({int(row['pause_count'])} пауз)")
                if pd.notna(row["operator_talk_ratio"]):
                    st.markdown(f"- **Доля речи оператора:** {row['operator_talk_ratio']:.0f}%")

                topics = row["key_topics"]
                if topics:
                    try:
                        topics_list = json.loads(topics) if isinstance(topics, str) else topics
                        if topics_list:
                            st.markdown("**Ключевые темы:**")
                            for t in topics_list:
                                st.markdown(f"  - {t}")
                    except Exception:
                        pass

                checklist_json = row["checklist_json"]
                if checklist_json:
                    try:
                        checklist_result = json.loads(checklist_json)
                        st.markdown("**Чек-лист:**")
                        for item in CHECKLIST:
                            passed = checklist_result.get(item["key"])
                            icon = "✅" if passed else "❌"
                            st.markdown(f"  {icon} {item['label']} ({item['weight']})")
                    except Exception:
                        pass

                compliance_json = row.get("compliance_json")
                if compliance_json:
                    try:
                        compliance = json.loads(compliance_json)
                        issues = compliance.get("issues") or compliance.get("llm_issues") or []
                        st.markdown("**Compliance:**")
                        if issues:
                            st.warning("⚠️ Найдены замечания:\n" + "\n".join(f"- {i}" for i in issues))
                        else:
                            st.success("✅ Нарушений не найдено")
                    except Exception:
                        pass

            with d2:
                if row["call_summary"]:
                    st.markdown("**Резюме**")
                    st.info(row["call_summary"])

                st.markdown("**📄 Транскрипт** _(клик по ▶ перематывает плеер на реплику)_")
                segments_df = load_segments(row["file_name"])
                if segments_df.empty:
                    st.text(row["transcript_text"])
                else:
                    speaker_label = {"operator": "🧑‍💼 Оператор", "client": "🙋 Клиент", "unknown": "❔"}
                    for _, seg in segments_df.iterrows():
                        label = speaker_label.get(seg["speaker"], seg["speaker"])
                        seg_col1, seg_col2 = st.columns([0.06, 0.94])
                        with seg_col1:
                            if audio_url and st.button(
                                "▶", key=f"seek_{row['file_name']}_{seg['seg_index']}"
                            ):
                                st.session_state["seek_time"] = float(seg["start_sec"])
                                st.rerun()
                        with seg_col2:
                            st.markdown(
                                f"**{label}** _{seg['start_sec']:.0f}–{seg['end_sec']:.0f}с_: {seg['text']}"
                            )

# ── Вкладка операторов: статистика по именованным звонкам ────────────────────
with tab_operators:
    st.markdown("### 🧑‍💼 Статистика по операторам")

    named_df = df_all[df_all["operator_name"].notna() & (df_all["operator_name"] != "")]
    unnamed_count = len(df_all) - len(named_df)

    if named_df.empty:
        st.info(
            "Пока ни один звонок не привязан к оператору. Укажите имя оператора "
            "в деталке звонка (вкладка «📁 Звонки»)."
        )
    else:
        st.caption(
            f"{len(named_df)} из {len(df_all)} звонков привязаны к оператору"
            + (f" · {unnamed_count} ещё без имени" if unnamed_count else "")
        )
        op_stats = named_df.groupby("operator_name").agg(
            звонков=("file_name", "count"),
            оценка=("agent_performance_score", "mean"),
            клиент=("customer_satisfaction", "mean"),
        ).round(1).reset_index()
        op_stats.columns = ["Оператор", "Звонков", "Оценка (чек-лист)", "Удовл. клиента"]
        op_stats = op_stats.sort_values("Звонков", ascending=False)
        st.dataframe(
            op_stats, use_container_width=True, hide_index=True,
            column_config={
                "Оценка (чек-лист)": st.column_config.ProgressColumn(
                    "Оценка (чек-лист)", min_value=0, max_value=10, format="%.1f/10"
                ),
                "Удовл. клиента": st.column_config.ProgressColumn(
                    "Удовл. клиента", min_value=0, max_value=10, format="%.1f/10"
                ),
            },
        )

# ── Вкладка команды ────────────────────────────────────────────────────────────
with tab_team:
    st.markdown("### 👥 Команда разработчиков")
    st.markdown("---")
    # Карточка организации
    with st.container(border=True):
        st.markdown("## 🏢  ЦАР · ds-team prospects, (песочница)")
        st.markdown("**МТБанк, Беларусь**")
        st.markdown("👩‍🏫 **Воспитатель:** Пилипенко Светлана")
        st.markdown("🤱 **Нянечка:** Гуринович Анастасия")

    st.markdown("#### Участники команды")
    team = [
        {"name": "Ксения", "role": "Data Scientist", "icon": "🔬"},
        {"name": "Алексей", "role": "Data Scientist", "icon": "🔬"},
        {"name": "Андрей",  "role": "Data Scientist", "icon": "🔬"},
    ]
    c1, c2, c3 = st.columns(3)
    for col, member in zip([c1, c2, c3], team):
        with col:
            with st.container(border=True):
                st.markdown(f"## {member['icon']}")
                st.markdown(f"**{member['name']}**")
                st.caption(member["role"])
