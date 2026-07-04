import streamlit as st
import snowflake.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import hashlib
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Call Center Analytics",
    page_icon="📞",
    layout="wide",
)

# ── Аутентификация ─────────────────────────────────────────────────────────────
USERS = {
    "Julia": {
        "password_hash": hashlib.sha256("Julia".encode()).hexdigest(),
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


# ── Подключение к Snowflake ────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.environ.get("SF_ACCOUNT", "vwxavxk-uq47134"),
        user=os.environ.get("SF_USER", "DYMSIA"),
        password=os.environ.get("SF_PASSWORD", "Leha31Jeka04Leha31Jeka04"),
        role=os.environ.get("SF_ROLE", "ACCOUNTADMIN"),
        warehouse=os.environ.get("SF_WAREHOUSE", "CCA_WH"),
        database=os.environ.get("SF_DATABASE", "CALL_CENTER_DB"),
        schema=os.environ.get("SF_SCHEMA", "ANALYTICS"),
    )

@st.cache_data(ttl=60)
def load_data():
    conn = get_connection()
    df = pd.read_sql("""
        SELECT
            file_name, department, call_topic, call_summary,
            call_type, customer_intent, urgency, resolution_status,
            agent_performance_score, customer_satisfaction,
            escalation_flag, key_topics, transcript_text,
            analyzed_at
        FROM CALL_ANALYSIS
        ORDER BY department, call_topic
    """, conn)
    df.columns = [c.lower() for c in df.columns]
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
tab_analytics, tab_team = st.tabs(["📊 Аналитика", "👥 Команда разработчиков"])

with tab_analytics:
    st.caption(f"Snowflake: CALL_CENTER_DB.ANALYTICS · {len(df)} из {len(df_all)} звонков")

    # ── KPI карточки ──────────────────────────────────────────────────────────
    st.markdown("### Ключевые показатели")
    k1, k2, k3, k4, k5 = st.columns(5)
    avg_agent = df["agent_performance_score"].mean()
    avg_client = df["customer_satisfaction"].mean()
    resolved_pct = (df["resolution_status"] == "resolved").mean() * 100
    escalated = df["escalation_flag"].sum()
    k1.metric("Звонков", len(df), f"из {len(df_all)} всего")
    k2.metric("Оценка оператора", f"{avg_agent:.1f}/10")
    k3.metric("Удовл. клиента", f"{avg_client:.1f}/10")
    k4.metric("Решено", f"{resolved_pct:.0f}%")
    k5.metric("Эскалаций", int(escalated))

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
        "department", "call_topic", "call_type", "urgency",
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

    # ── Детальный просмотр звонка ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Детали звонка")
    topic_options = df["call_topic"].tolist()
    if not topic_options:
        st.info("Нет данных по выбранным фильтрам.")
    else:
        selected_topic = st.selectbox(
            "Выберите звонок", options=topic_options,
            format_func=lambda t: f"{df[df['call_topic']==t]['department'].values[0]} — {t}",
        )
        row = df[df["call_topic"] == selected_topic].iloc[0]
        d1, d2 = st.columns([1, 2])
        with d1:
            st.markdown("**Параметры звонка**")
            st.markdown(f"- **Отдел:** {row['department']}")
            st.markdown(f"- **Тип:** {row['call_type']}")
            st.markdown(f"- **Намерение клиента:** {row['customer_intent']}")
            st.markdown(f"- **Срочность:** {row['urgency']}")
            st.markdown(f"- **Статус:** {row['resolution_status']}")
            st.markdown(f"- **Оценка оператора:** {row['agent_performance_score']}/10")
            st.markdown(f"- **Удовл. клиента:** {row['customer_satisfaction']}/10")
            st.markdown(f"- **Эскалация:** {'Да' if row['escalation_flag'] else 'Нет'}")
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
        with d2:
            if row["call_summary"]:
                st.markdown("**Резюме**")
                st.info(row["call_summary"])
            with st.expander("📄 Транскрипт звонка", expanded=False):
                st.text(row["transcript_text"])

# ── Вкладка команды ────────────────────────────────────────────────────────────
with tab_team:
    st.markdown("### 👥 Команда разработчиков")
    st.markdown("---")
    # Карточка организации
    with st.container(border=True):
        st.markdown("## 🏢  ЦАР · ds-team, ясли")
        st.markdown("**МТБанк, Беларусь**")

    st.markdown("#### Участники команды")
    team = [
        {"name": "Масловская Ксения", "role": "Data Scientist", "icon": "🔬"},
        {"name": "Дымков Алексей",    "role": "Data Scientist", "icon": "🔬"},
        {"name": "Шилкин Андрей",     "role": "Data Scientist", "icon": "🔬"},
    ]
    c1, c2, c3 = st.columns(3)
    for col, member in zip([c1, c2, c3], team):
        with col:
            with st.container(border=True):
                st.markdown(f"## {member['icon']}")
                st.markdown(f"**{member['name']}**")
                st.caption(member["role"])
