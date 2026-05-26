"""
SplitsenseAI — Streamlit Dashboard
Interactive dashboard for expense analytics, receipt management, and settlements.
"""

import streamlit as st
import requests
import os

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_URL = f"{API_BASE}/api/v1"

st.set_page_config(
    page_title="SplitsenseAI",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp { font-family: 'Inter', sans-serif; }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 24px;
        color: white;
        margin-bottom: 16px;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    .metric-card h3 { margin: 0; font-size: 14px; opacity: 0.8; font-weight: 400; }
    .metric-card h1 { margin: 4px 0; font-size: 32px; font-weight: 700; }
    
    .card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
    }
    
    .header-gradient {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 32px;
        border-radius: 20px;
        color: white;
        margin-bottom: 24px;
    }
</style>
""", unsafe_allow_html=True)


def init_session():
    if "token" not in st.session_state:
        st.session_state.token = None
    if "user" not in st.session_state:
        st.session_state.user = None


def api_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def login_page():
    st.markdown("""
    <div class="header-gradient">
        <h1>💰 SplitsenseAI</h1>
        <p>AI Expense Intelligence & Smart Bill Splitting</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", use_container_width=True):
            try:
                resp = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.user = data["user"]
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except requests.ConnectionError:
                st.error("Cannot connect to API. Is the backend running?")

    with tab2:
        username = st.text_input("Username", key="reg_user")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register", use_container_width=True):
            try:
                resp = requests.post(f"{API_URL}/auth/register", json={
                    "email": email, "username": username, "password": password
                })
                if resp.status_code == 201:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.user = data["user"]
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Registration failed"))
            except requests.ConnectionError:
                st.error("Cannot connect to API")


def dashboard_page():
    st.markdown("""
    <div class="header-gradient">
        <h1>💰 SplitsenseAI Dashboard</h1>
        <p>Welcome back, {username}!</p>
    </div>
    """.format(username=st.session_state.user.get("username", "")), unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio("Go to", ["📊 Overview", "📈 Insights", "📸 Upload Receipt", "👥 Groups", "💳 Settlements", "📥 Export"])

        st.markdown("---")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()

    if page == "📊 Overview":
        show_overview()
    elif page == "📈 Insights":
        show_insights()
    elif page == "📸 Upload Receipt":
        show_upload()
    elif page == "👥 Groups":
        show_groups()
    elif page == "💳 Settlements":
        show_settlements()
    elif page == "📥 Export":
        show_export()


def show_overview():
    import plotly.express as px

    col1, col2, col3 = st.columns(3)

    # Fetch analytics
    try:
        spending = requests.get(f"{API_URL}/analytics/spending", headers=api_headers()).json()
        trends = requests.get(f"{API_URL}/analytics/trends", headers=api_headers()).json()
        receipts_resp = requests.get(f"{API_URL}/receipts/", headers=api_headers(), params={"page": 1, "per_page": 5})

        cat_data = spending.get("category_spending", [])
        store_data = spending.get("store_spending", [])
        trend_data = trends.get("monthly_trends", [])

        total = sum(c["total"] for c in cat_data)
        receipts_data = receipts_resp.json() if receipts_resp.status_code == 200 else {}
        total_receipts = receipts_data.get("total", 0)

        with col1:
            st.markdown(f'<div class="metric-card"><h3>Total Spending</h3><h1>${total:,.2f}</h1></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><h3>Categories</h3><h1>{len(cat_data)}</h1></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><h3>Receipts</h3><h1>{total_receipts}</h1></div>', unsafe_allow_html=True)

        # Charts
        c1, c2 = st.columns(2)
        with c1:
            if cat_data:
                fig = px.pie(cat_data, values="total", names="category", title="Spending by Category",
                             color_discrete_sequence=px.colors.qualitative.Set3, hole=0.4)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Upload some receipts to see spending by category.")

        with c2:
            if store_data:
                fig = px.bar(store_data[:10], x="store_name", y="total", title="Top Stores",
                             color="total", color_continuous_scale="Viridis")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

        if trend_data:
            fig = px.line(trend_data, x="month", y="total", title="Monthly Spending Trend",
                         markers=True, line_shape="spline")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Recent receipts
        recent = receipts_data.get("receipts", [])
        if recent:
            st.markdown("### Recent Receipts")
            for r in recent:
                cols = st.columns([3, 2, 2, 1])
                cols[0].write(r.get("store_name") or "Unknown Store")
                cols[1].write(r.get("receipt_date") or r.get("created_at", "")[:10])
                cols[2].write(f"${r.get('total_amount', 0):.2f}")
                cols[3].write(r.get("status", ""))

    except requests.ConnectionError:
        st.warning("Cannot connect to API")
    except Exception:
        st.info("Upload some receipts to see analytics!")


def show_insights():
    import plotly.express as px
    import plotly.graph_objects as go

    st.subheader("📈 Personal Insights & Reports")

    try:
        resp = requests.get(f"{API_URL}/analytics/insights", headers=api_headers())
        if resp.status_code != 200:
            st.info("Upload some receipts to generate insights.")
            return
        data = resp.json()
    except requests.ConnectionError:
        st.error("Cannot connect to API")
        return

    cat_data       = data.get("category_spending", [])
    store_data     = data.get("store_spending", [])
    trend_data     = data.get("monthly_trends", [])
    top_items      = data.get("top_items", [])
    month_comp     = data.get("month_comparison", {})
    insight_cards  = data.get("insight_cards", [])
    anomalies      = data.get("anomalies", [])

    if not cat_data and not store_data:
        st.info("Upload some receipts to generate insights.")
        return

    # ── AI Insight Cards ─────────────────────────────────────────────────────
    if insight_cards:
        st.markdown("### 🤖 AI Insights")
        icon_col_count = min(len(insight_cards), 3)
        cols = st.columns(icon_col_count)
        for i, card in enumerate(insight_cards):
            col = cols[i % icon_col_count]
            bg = {
                "category": "linear-gradient(135deg,#667eea,#764ba2)",
                "store":    "linear-gradient(135deg,#f093fb,#f5576c)",
                "trend":    "linear-gradient(135deg,#4facfe,#00f2fe)",
                "item":     "linear-gradient(135deg,#43e97b,#38f9d7)",
                "anomaly":  "linear-gradient(135deg,#fa709a,#fee140)",
            }.get(card["type"], "linear-gradient(135deg,#667eea,#764ba2)")
            col.markdown(
                f"""<div style="background:{bg};border-radius:14px;padding:18px;color:white;margin-bottom:12px;">
                    <div style="font-size:28px">{card['icon']}</div>
                    <div style="font-weight:600;font-size:15px;margin:6px 0">{card['title']}</div>
                    <div style="font-size:12px;opacity:0.85">{card['detail']}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Month Comparison ─────────────────────────────────────────────────────
    if month_comp.get("previous_month", 0) > 0 or month_comp.get("current_month", 0) > 0:
        st.markdown("### 📅 Month-over-Month")
        m1, m2, m3 = st.columns(3)
        m1.metric(
            month_comp.get("current_label", "This Month"),
            f"${month_comp.get('current_month', 0):.2f}",
        )
        m2.metric(
            month_comp.get("previous_label", "Last Month"),
            f"${month_comp.get('previous_month', 0):.2f}",
        )
        change = month_comp.get("change_pct", 0)
        m3.metric(
            "Change",
            f"{'+' if change >= 0 else ''}{change:.1f}%",
            delta=f"{change:.1f}%",
            delta_color="inverse",  # red if spending went up, green if down
        )
        st.markdown("---")

    # ── Category Breakdown ───────────────────────────────────────────────────
    if cat_data:
        st.markdown("### 🏷️ Spending by Category")
        c1, c2 = st.columns([1, 1])

        with c1:
            fig = px.pie(
                cat_data, values="total", names="category",
                title="Share of Total Spending",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig.update_traces(
                texttemplate="%{label}<br>%{percent}",
                textposition="outside",
                hovertemplate="<b>%{label}</b><br>$%{value:.2f}<br>%{percent}<extra></extra>",
            )
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("**Category Details**")
            for cat in cat_data:
                pct = cat["percentage"]
                bar_color = "#667eea"
                st.markdown(
                    f"""<div style="margin-bottom:10px;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                            <span style="font-weight:500">{cat['category']}</span>
                            <span style="color:#666">${cat['total']:.2f} &nbsp;·&nbsp; <b>{pct}%</b></span>
                        </div>
                        <div style="background:#e2e8f0;border-radius:4px;height:8px;">
                            <div style="background:{bar_color};width:{min(pct,100)}%;height:8px;border-radius:4px;"></div>
                        </div>
                        <div style="font-size:11px;color:#888;margin-top:2px">{cat['item_count']} item{'s' if cat['item_count']!=1 else ''}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── Store Breakdown ──────────────────────────────────────────────────────
    if store_data:
        st.markdown("### 🏪 Spending by Store")
        grand = sum(s["total"] for s in store_data)
        c1, c2 = st.columns([1, 1])

        with c1:
            fig = px.bar(
                store_data[:10], x="total", y="store_name",
                orientation="h", title="Top 10 Stores",
                color="total", color_continuous_scale="Viridis",
                labels={"total": "Total Spent ($)", "store_name": ""},
                text="total",
            )
            fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"},
                margin=dict(l=0, r=60, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("**Store Details**")
            for store in store_data[:10]:
                pct = round(store["total"] / grand * 100, 1) if grand > 0 else 0
                st.markdown(
                    f"""<div style="margin-bottom:10px;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                            <span style="font-weight:500">{store['store_name']}</span>
                            <span style="color:#666">${store['total']:.2f} &nbsp;·&nbsp; <b>{pct}%</b></span>
                        </div>
                        <div style="background:#e2e8f0;border-radius:4px;height:8px;">
                            <div style="background:#f093fb;width:{min(pct,100)}%;height:8px;border-radius:4px;"></div>
                        </div>
                        <div style="font-size:11px;color:#888;margin-top:2px">{store['visit_count']} visit{'s' if store['visit_count']!=1 else ''}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── Monthly Trend ────────────────────────────────────────────────────────
    if trend_data:
        st.markdown("### 📆 Monthly Spending Trend")
        fig = px.bar(
            trend_data, x="month", y="total",
            title="Monthly Spending",
            labels={"month": "Month", "total": "Total Spent ($)"},
            color="total", color_continuous_scale="Blues",
            text="total",
        )
        fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")

        # Overlay line for trend
        fig.add_scatter(
            x=[d["month"] for d in trend_data],
            y=[d["total"] for d in trend_data],
            mode="lines+markers", name="Trend",
            line=dict(color="#667eea", width=2),
            marker=dict(size=6),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Most-Bought Items ────────────────────────────────────────────────────
    if top_items:
        st.markdown("---")
        st.markdown("### 🛒 Most Frequently Bought Items")
        cols = st.columns([3, 2, 1, 2])
        cols[0].markdown("**Item**")
        cols[1].markdown("**Category**")
        cols[2].markdown("**Times**")
        cols[3].markdown("**Total Spent**")
        for item in top_items:
            c1, c2, c3, c4 = st.columns([3, 2, 1, 2])
            c1.write(item["name"])
            c2.write(item["category"])
            c3.write(item["frequency"])
            c4.write(f"${item['total_spent']:.2f}")

    # ── Anomaly Alerts ───────────────────────────────────────────────────────
    if anomalies:
        st.markdown("---")
        st.markdown("### ⚠️ Unusual Spending Detected")
        for a in anomalies:
            color = "#fa709a" if a["severity"] == "high" else "#fee140"
            st.markdown(
                f"""<div style="background:{color}22;border-left:4px solid {color};
                    padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:8px;">
                    <b>{a['description']}</b><br>
                    <span style="color:#666;font-size:13px">Normal range: {a['expected_range']} · Severity: {a['severity']}</span>
                </div>""",
                unsafe_allow_html=True,
            )


def show_upload():
    st.subheader("📸 Upload Receipt")
    st.markdown("Take a photo of your receipt or upload an image file.")

    # --- Group selector ---
    selected_group_id = None
    try:
        groups_resp = requests.get(f"{API_URL}/groups/", headers=api_headers())
        groups = groups_resp.json() if groups_resp.status_code == 200 else []
    except requests.ConnectionError:
        groups = []

    if groups:
        group_options = {"— Personal (no group) —": None}
        group_options.update({g["name"]: g["id"] for g in groups})
        chosen_group = st.selectbox(
            "Assign to Group",
            list(group_options.keys()),
            key="upload_group_select",
            help="Select a group to split this receipt with others, or leave as Personal.",
        )
        selected_group_id = group_options[chosen_group]
        if selected_group_id:
            chosen_members = next(g for g in groups if g["id"] == selected_group_id).get("members", [])
            st.caption(f"Members: {', '.join(m['username'] for m in chosen_members)}")
    else:
        st.info("💡 Create a group first (Groups tab) to split receipts with others.")

    uploaded = st.file_uploader("Choose a receipt image", type=["jpg", "jpeg", "png", "webp"])

    if uploaded:
        st.image(uploaded, caption="Uploaded Receipt", width=300)

        if st.button("🔍 Process Receipt", use_container_width=True):
            with st.spinner("Processing receipt with AI... (first run may take a minute to load models)"):
                try:
                    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                    params = {}
                    if selected_group_id:
                        params["group_id"] = selected_group_id

                    resp = requests.post(
                        f"{API_URL}/receipts/upload",
                        files=files,
                        params=params,
                        headers=api_headers(),
                    )

                    if resp.status_code == 201:
                        data = resp.json()
                        store = data.get("store_name") or "Unknown Store"
                        st.success(f"✅ Receipt processed: **{store}**")
                        if selected_group_id:
                            st.info("🔄 Items are being categorized in the background. Refresh to see categories.")

                        st.markdown("### Extracted Items")
                        items = data.get("items", [])
                        if items:
                            col_h1, col_h2, col_h3, col_h4 = st.columns([4, 1, 1, 2])
                            col_h1.markdown("**Item**")
                            col_h2.markdown("**Qty**")
                            col_h3.markdown("**Price**")
                            col_h4.markdown("**Category**")
                            for item in items:
                                c1, c2, c3, c4 = st.columns([4, 1, 1, 2])
                                c1.write(item["name"])
                                c2.write(item.get("quantity", 1))
                                c3.write(f"${item['price']:.2f}")
                                c4.write(item.get("category") or "—")
                        else:
                            st.warning("No items extracted. The image may be unclear — try a higher-quality photo.")

                        st.markdown(f"**Total: ${data.get('total_amount', 0):.2f}**")

                        if selected_group_id and items:
                            st.markdown("---")
                            st.markdown("**Next step:** Go to **Settlements** to see how much each member owes after splitting.")
                    else:
                        st.error(f"Processing failed: {resp.json().get('detail', 'Unknown error')}")
                except requests.ConnectionError:
                    st.error("Cannot connect to API. Is the backend running?")


def show_groups():
    st.subheader("👥 Groups")

    with st.expander("➕ Create New Group"):
        name = st.text_input("Group Name", key="new_group_name")
        desc = st.text_input("Description (optional)", key="new_group_desc")
        if st.button("Create Group", key="btn_create_group"):
            if not name.strip():
                st.warning("Group name is required.")
            else:
                resp = requests.post(
                    f"{API_URL}/groups/",
                    json={"name": name.strip(), "description": desc.strip() or None},
                    headers=api_headers(),
                )
                if resp.status_code == 201:
                    st.success(f"Group '{name}' created!")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Failed to create group"))

    # Fetch and display user's groups
    try:
        groups_resp = requests.get(f"{API_URL}/groups/", headers=api_headers())
        groups = groups_resp.json() if groups_resp.status_code == 200 else []
    except requests.ConnectionError:
        st.error("Cannot connect to API")
        return

    if not groups:
        st.info("You don't belong to any groups yet. Create one above!")
        return

    st.markdown("### Your Groups")
    group_names = [g["name"] for g in groups]
    selected_name = st.selectbox("Select a group to manage", group_names, key="selected_group")
    selected_group = next((g for g in groups if g["name"] == selected_name), None)

    if not selected_group:
        return

    gid = selected_group["id"]
    members = selected_group.get("members", [])

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"**Group ID:** `{gid}`")
        st.markdown(f"**Members ({len(members)}):**")
        for m in members:
            role_badge = "👑" if m["role"] == "admin" else "👤"
            st.write(f"{role_badge} {m['username']} ({m['role']})")

    with col2:
        st.markdown("**Add Member**")
        search_q = st.text_input("Search by username or email", key="member_search")
        if search_q and len(search_q) >= 2:
            search_resp = requests.get(
                f"{API_URL}/auth/users/search",
                params={"q": search_q},
                headers=api_headers(),
            )
            if search_resp.status_code == 200:
                results = search_resp.json()
                if results:
                    user_options = {f"{u['username']} ({u['email']})": u["id"] for u in results}
                    chosen = st.selectbox("Select user to add", list(user_options.keys()), key="add_member_select")
                    if st.button("Add to Group", key="btn_add_member"):
                        chosen_id = user_options[chosen]
                        add_resp = requests.post(
                            f"{API_URL}/groups/{gid}/members",
                            json={"user_id": chosen_id, "role": "member"},
                            headers=api_headers(),
                        )
                        if add_resp.status_code == 201:
                            st.success(f"Member added!")
                            st.rerun()
                        else:
                            st.error(add_resp.json().get("detail", "Failed to add member"))
                else:
                    st.info("No users found.")

        # Remove member
        if len(members) > 1:
            st.markdown("**Remove Member**")
            removable = [m for m in members if m["role"] != "admin"]
            if removable:
                rm_options = {m["username"]: m["user_id"] for m in removable}
                rm_user = st.selectbox("Select member to remove", list(rm_options.keys()), key="rm_member_select")
                if st.button("Remove Member", key="btn_rm_member"):
                    rm_id = rm_options[rm_user]
                    rm_resp = requests.delete(
                        f"{API_URL}/groups/{gid}/members/{rm_id}",
                        headers=api_headers(),
                    )
                    if rm_resp.status_code == 200:
                        st.success("Member removed!")
                        st.rerun()
                    else:
                        st.error("Failed to remove member")


def show_settlements():
    st.subheader("💳 Settlements")

    # Fetch user's groups for dropdown
    try:
        groups_resp = requests.get(f"{API_URL}/groups/", headers=api_headers())
        groups = groups_resp.json() if groups_resp.status_code == 200 else []
    except requests.ConnectionError:
        st.error("Cannot connect to API")
        return

    if not groups:
        st.info("You don't belong to any groups yet. Create a group first in the Groups tab.")
        return

    group_names = [g["name"] for g in groups]
    selected_name = st.selectbox("Select Group", group_names, key="settle_group_select")
    selected_group = next((g for g in groups if g["name"] == selected_name), None)
    if not selected_group:
        return

    gid = selected_group["id"]
    members = {m["user_id"]: m["username"] for m in selected_group.get("members", [])}

    tab_bal, tab_hist = st.tabs(["💰 Balances", "📋 History"])

    with tab_bal:
        if st.button("Refresh Balances", key="btn_refresh_bal"):
            st.rerun()

        try:
            resp = requests.get(f"{API_URL}/settlements/group/{gid}/balances", headers=api_headers())
            if resp.status_code == 200:
                data = resp.json()
                total_unsettled = data.get("total_unsettled", 0)
                balances = data.get("balances", [])

                st.metric("Total Unsettled", f"${total_unsettled:.2f}")

                if not balances:
                    st.success("✅ All settled up!")
                else:
                    st.markdown("**Settlement Plan** (minimum transactions needed):")
                    for b in balances:
                        from_name = members.get(b["from_user"], b["from_user"][:8] + "...")
                        to_name = members.get(b["to_user"], b["to_user"][:8] + "...")
                        cols = st.columns([3, 1])
                        cols[0].write(f"💸 **{from_name}** → **{to_name}**: ${b['amount']:.2f}")
                        if cols[1].button("Mark Paid", key=f"settle_{b['from_user']}_{b['to_user']}"):
                            settle_resp = requests.post(
                                f"{API_URL}/settlements/group/{gid}/settle",
                                json={
                                    "from_user": b["from_user"],
                                    "to_user": b["to_user"],
                                    "amount": b["amount"],
                                },
                                headers=api_headers(),
                            )
                            if settle_resp.status_code == 200:
                                st.success("Settlement recorded!")
                                st.rerun()
                            else:
                                st.error("Failed to record settlement")
            else:
                st.error("Failed to load balances")
        except Exception:
            st.error("Failed to load balances")

    with tab_hist:
        try:
            hist_resp = requests.get(f"{API_URL}/settlements/group/{gid}/history", headers=api_headers())
            if hist_resp.status_code == 200:
                history = hist_resp.json()
                if not history:
                    st.info("No settlement history yet.")
                else:
                    for s in history:
                        from_name = members.get(s.get("from_user"), "Unknown")
                        to_name = members.get(s.get("to_user"), "Unknown")
                        settled_at = (s.get("settled_at") or "")[:10]
                        st.write(f"✅ **{from_name}** paid **{to_name}** ${s.get('amount', 0):.2f} on {settled_at}")
            else:
                st.error("Failed to load history")
        except Exception:
            st.error("Failed to load settlement history")


def show_export():
    st.subheader("📥 Export Data")

    if st.button("Download Excel Report", use_container_width=True):
        try:
            resp = requests.get(f"{API_URL}/exports/excel", headers=api_headers())
            if resp.status_code == 200:
                st.download_button(
                    "📄 Save Excel File",
                    data=resp.content,
                    file_name="splitsenseai_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception:
            st.error("Failed to generate report")


# --- Main ---
init_session()

if st.session_state.token:
    dashboard_page()
else:
    login_page()
