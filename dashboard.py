"""
SplitsenseAI — Streamlit Dashboard
"""

import os
import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/") + "/api/v1"

st.set_page_config(
    page_title="SplitsenseAI",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1a1a2e; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
.metric-card {
    background: #f8f9fa; border-radius: 12px; padding: 20px;
    text-align: center; border: 1px solid #e9ecef;
}
.metric-card h2 { color: #667eea; margin: 0; font-size: 2rem; }
.metric-card p  { color: #6c757d; margin: 4px 0 0; font-size: 0.9rem; }
.badge-admin  { background:#667eea; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; }
.badge-member { background:#28a745; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; }
</style>
""", unsafe_allow_html=True)

# ── API helpers ───────────────────────────────────────────────────────────────
def _h():
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}

_COLD_START_MSG = "detail"
_COLD_START_ERR = "Backend is waking up (cold start can take ~30s on free tier). Please wait and try again."

def _safe_json(r):
    try:
        return r.json()
    except Exception:
        if r.status_code in (502, 503, 504):
            return {"detail": _COLD_START_ERR}
        return {"detail": f"Server returned a non-JSON response (HTTP {r.status_code})"}

def api_get(path, params=None):
    try:
        r = requests.get(f"{API}{path}", headers=_h(), params=params, timeout=60)
        return _safe_json(r) if r.ok else None
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None

def api_post(path, json=None, files=None, data=None, expected=201):
    try:
        timeout = 120 if files else 60
        r = requests.post(f"{API}{path}", headers=_h(), json=json, files=files, data=data, timeout=timeout)
        return _safe_json(r), r.status_code == expected
    except requests.exceptions.Timeout:
        return {"detail": _COLD_START_ERR}, False
    except requests.exceptions.ConnectionError:
        return {"detail": "Cannot reach backend — check API_BASE_URL is set in Streamlit secrets."}, False
    except Exception as e:
        return {"detail": str(e)}, False

def api_delete(path):
    try:
        r = requests.delete(f"{API}{path}", headers=_h(), timeout=30)
        return r.ok
    except Exception:
        return False

def api_patch(path, json=None):
    try:
        r = requests.patch(f"{API}{path}", headers=_h(), json=json, timeout=60)
        return _safe_json(r), r.ok
    except Exception as e:
        return {"detail": str(e)}, False

# ── Login / Register ──────────────────────────────────────────────────────────
def page_auth():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align:center'>🧾 SplitsenseAI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#6c757d'>AI-powered bill splitting</p>", unsafe_allow_html=True)
        st.markdown("---")

        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("login_form"):
                email    = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
            if submitted:
                resp, ok = api_post("/auth/login", json={"email": email, "password": password}, expected=200)
                if ok:
                    st.session_state.token    = resp["access_token"]
                    st.session_state.user     = resp["user"]
                    st.session_state.page     = "Overview"
                    st.rerun()
                else:
                    st.error(resp.get("detail", "Login failed"))

        with tab_register:
            with st.form("register_form"):
                r_email    = st.text_input("Email", key="r_email")
                r_username = st.text_input("Username", key="r_username")
                r_password = st.text_input("Password", type="password", key="r_password")
                submitted  = st.form_submit_button("Create Account", use_container_width=True)
            if submitted:
                resp, ok = api_post("/auth/register", json={
                    "email": r_email, "username": r_username, "password": r_password
                })
                if ok:
                    st.session_state.token = resp["access_token"]
                    st.session_state.user  = resp["user"]
                    st.session_state.page  = "Overview"
                    st.rerun()
                else:
                    st.error(resp.get("detail", "Registration failed"))

# ── Overview ──────────────────────────────────────────────────────────────────
def page_overview():
    user = st.session_state.get("user", {})
    st.markdown(f"## Welcome back, **{user.get('username', '')}** 👋")
    st.markdown("---")

    receipts_data = api_get("/receipts/") or {}
    groups        = api_get("/groups/") or []
    spending      = api_get("/analytics/spending") or {}

    receipts  = receipts_data.get("receipts", [])
    total_rec = receipts_data.get("total", 0)
    cat_spend = spending.get("category_spending", [])
    total_spent = sum(r.get("total_amount") or 0 for r in receipts)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="metric-card"><h2>{total_rec}</h2><p>Total Receipts</p></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card"><h2>${total_spent:.2f}</h2><p>Total Spent</p></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card"><h2>{len(groups)}</h2><p>Groups</p></div>""", unsafe_allow_html=True)
    with c4:
        top_cat = cat_spend[0]["category"] if cat_spend else "—"
        st.markdown(f"""<div class="metric-card"><h2 style="font-size:1.2rem">{top_cat}</h2><p>Top Category</p></div>""", unsafe_allow_html=True)

    st.markdown("---")
    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        st.markdown("### Recent Receipts")
        if receipts:
            rows = []
            for r in receipts[:8]:
                rows.append({
                    "Store":   r.get("store_name") or "Unknown",
                    "Date":    r.get("receipt_date") or "—",
                    "Total":   f"${r.get('total_amount') or 0:.2f}",
                    "Items":   len(r.get("items", [])),
                    "Status":  r.get("status", "").capitalize(),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No receipts yet — upload one in the Receipts page.")

    with col_right:
        st.markdown("### Spending by Category")
        if cat_spend:
            fig = px.pie(
                pd.DataFrame(cat_spend), values="total", names="category",
                color_discrete_sequence=px.colors.qualitative.Pastel,
                hole=0.4,
            )
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True, height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No spending data yet.")

# ── Groups ────────────────────────────────────────────────────────────────────
def page_groups():
    st.markdown("## Groups")
    st.markdown("---")

    col_list, col_create = st.columns([2, 1])

    with col_create:
        st.markdown("### Create Group")
        with st.form("create_group"):
            name  = st.text_input("Group Name")
            desc  = st.text_area("Description", height=80)
            if st.form_submit_button("Create", use_container_width=True):
                resp, ok = api_post("/groups/", json={"name": name, "description": desc})
                if ok:
                    st.success(f"Group '{name}' created!")
                    st.rerun()
                else:
                    st.error(resp.get("detail", "Failed"))

        st.markdown("### Add Member")
        groups = api_get("/groups/") or []
        if groups:
            with st.form("add_member"):
                group_options = {g["name"]: g["id"] for g in groups}
                sel_group = st.selectbox("Group", list(group_options.keys()))
                search_q  = st.text_input("Search user (email or username)")
                user_id_input = st.text_input("User ID to add")
                if st.form_submit_button("Add Member", use_container_width=True):
                    gid = group_options[sel_group]
                    resp, ok = api_post(f"/groups/{gid}/members", json={"user_id": user_id_input, "role": "member"}, expected=201)
                    if ok:
                        st.success("Member added!")
                        st.rerun()
                    else:
                        st.error(resp.get("detail", "Failed"))

                if search_q and len(search_q) >= 2:
                    results = api_get("/auth/users/search", params={"q": search_q}) or []
                    if results:
                        st.markdown("**Search results:**")
                        for u in results:
                            st.code(f"{u['username']} ({u['email']})  →  ID: {u['id']}")
                    else:
                        st.caption("No users found")

    with col_list:
        st.markdown("### Your Groups")
        groups = api_get("/groups/") or []
        if not groups:
            st.info("No groups yet — create one!")
        for g in groups:
            with st.expander(f"**{g['name']}**  —  {len(g.get('members', []))} member(s)"):
                if g.get("description"):
                    st.caption(g["description"])
                members = g.get("members", [])
                if members:
                    rows = []
                    for m in members:
                        rows.append({"Username": m.get("username", "—"), "Role": m.get("role", "member").capitalize()})
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                st.caption(f"Group ID: `{g['id']}`")

# ── Receipts ──────────────────────────────────────────────────────────────────
CATEGORIES = [
    "Groceries", "Restaurant", "Fast Food", "Beverages", "Household",
    "Personal Care", "Healthcare", "Electronics", "Clothing", "Transport",
    "Entertainment", "Utilities", "Office Supplies", "Pet Supplies", "Miscellaneous",
]


def _render_receipt_card(r, tab=""):
    """Render one receipt expander with items table, edit form, and delete control."""
    store  = r.get("store_name") or "Unknown Store"
    date   = r.get("receipt_date") or "No date"
    total  = r.get("total_amount")
    status = r.get("status", "")
    items  = r.get("items", [])
    rid    = r["id"]
    k      = f"{tab}_{rid}"   # unique key prefix per tab+receipt

    color = {"ready": "🟢", "processing": "🟡", "error": "🔴"}.get(status, "⚪")
    label = f"{color} **{store}** — {date} — ${total:.2f}" if total else f"{color} **{store}** — {date}"

    with st.expander(label):
        st.caption(f"Receipt ID: `{rid}`  |  Status: **{status}**")

        if r.get("image_path"):
            st.image(r["image_path"], width=200, caption="Receipt image")

        if items:
            rows = [{"Item": i["name"], "Qty": i["quantity"], "Price": f"${i['price']:.2f}",
                     "Category": i.get("category") or "—"} for i in items]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            # ── Edit items toggle ──
            if st.button("✏️ Edit Items", key=f"edit_toggle_{k}"):
                st.session_state[f"show_edit_{k}"] = not st.session_state.get(f"show_edit_{k}", False)

            if st.session_state.get(f"show_edit_{k}", False):
                st.markdown("**Edit Items**")
                with st.form(f"edit_items_{k}"):
                    edits = {}
                    for item in items:
                        iid = item["id"]
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                        edits[iid] = {
                            "name":     c1.text_input("Name",     value=item["name"],     key=f"en_{k}_{iid}"),
                            "price":    c2.number_input("Price",  value=float(item["price"]), min_value=0.0, step=0.01, key=f"ep_{k}_{iid}"),
                            "quantity": c3.number_input("Qty",    value=int(item["quantity"]), min_value=1, step=1, key=f"eq_{k}_{iid}"),
                            "category": c4.selectbox("Category",
                                options=CATEGORIES,
                                index=CATEGORIES.index(item["category"]) if item.get("category") in CATEGORIES else 0,
                                key=f"ec_{k}_{iid}"),
                        }
                    if st.form_submit_button("Save Changes", use_container_width=True):
                        errors_found = False
                        for iid, vals in edits.items():
                            _, ok = api_patch(f"/receipts/{rid}/items/{iid}", json=vals)
                            if not ok:
                                errors_found = True
                        if errors_found:
                            st.error("Some items failed to save.")
                        else:
                            st.session_state[f"show_edit_{k}"] = False
                            st.success("Items updated!")
                            st.rerun()
        else:
            st.caption("No items extracted yet.")

        # ── Action buttons ──
        btn_col1, btn_col2 = st.columns([2, 1])
        with btn_col1:
            if status == "ready" and st.button("Split this receipt", key=f"split_{k}"):
                st.session_state.split_receipt_id = rid
                st.session_state.page = "Splits"
                st.rerun()
        with btn_col2:
            if st.button("🗑️ Delete", key=f"del_{k}", type="secondary"):
                st.session_state[f"confirm_del_{k}"] = True
                st.rerun()

        if st.session_state.get(f"confirm_del_{k}"):
            st.warning("Delete this receipt and all its items?")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete", key=f"yes_del_{k}", type="primary"):
                ok = api_delete(f"/receipts/{rid}")
                st.session_state.pop(f"confirm_del_{k}", None)
                if ok:
                    st.success("Receipt deleted.")
                else:
                    st.error("Delete failed.")
                st.rerun()
            if c2.button("Cancel", key=f"cancel_del_{k}"):
                st.session_state.pop(f"confirm_del_{k}", None)
                st.rerun()


def page_receipts():
    st.markdown("## Receipts")
    st.markdown("---")

    col_upload, col_list = st.columns([1, 2])

    with col_upload:
        st.markdown("### Upload Receipt")
        groups = api_get("/groups/") or []
        group_options = {"None (personal)": None}
        group_options.update({g["name"]: g["id"] for g in groups})

        with st.form("upload_receipt"):
            uploaded_file = st.file_uploader("Receipt image", type=["jpg", "jpeg", "png", "webp"])
            sel_group     = st.selectbox("Assign to Group (optional)", list(group_options.keys()))
            submitted     = st.form_submit_button("Upload & Process", use_container_width=True)

        if submitted and uploaded_file:
            with st.spinner("Uploading..."):
                gid = group_options[sel_group]
                params = f"?group_id={gid}" if gid else ""
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                resp, ok = api_post(f"/receipts/upload{params}", files=files)
            if ok:
                st.success("Uploaded! OCR is processing — auto-refresh will update the list.")
                st.session_state.selected_receipt = resp["id"]
            else:
                st.error(resp.get("detail", "Upload failed"))

    with col_list:
        col_title, col_btn = st.columns([3, 1])
        col_title.markdown("### Your Receipts")
        if col_btn.button("🔄 Refresh", use_container_width=True):
            st.rerun()

        data = api_get("/receipts/") or {}
        all_receipts = data.get("receipts", [])

        # Show a non-blocking notice when receipts are still processing
        processing_count = sum(1 for r in all_receipts if r.get("status") == "processing")
        if processing_count:
            st.info(f"⏳ {processing_count} receipt(s) still processing — click **Refresh** to check for updates.")

        if not all_receipts:
            st.info("No receipts yet — upload one!")
        else:
            tab_all, tab_ready, tab_error, tab_proc = st.tabs([
                f"All ({len(all_receipts)})",
                f"Ready ({sum(1 for r in all_receipts if r.get('status')=='ready')})",
                f"Error ({sum(1 for r in all_receipts if r.get('status')=='error')})",
                f"Processing ({sum(1 for r in all_receipts if r.get('status')=='processing')})",
            ])

            with tab_all:
                for r in all_receipts:
                    _render_receipt_card(r, tab="all")

            with tab_ready:
                ready = [r for r in all_receipts if r.get("status") == "ready"]
                if not ready:
                    st.info("No ready receipts.")
                for r in ready:
                    _render_receipt_card(r, tab="ready")

            with tab_error:
                errors = [r for r in all_receipts if r.get("status") == "error"]
                if errors:
                    if st.button(f"🗑️ Delete all {len(errors)} error receipt(s)", type="primary", key="bulk_del_btn"):
                        st.session_state["confirm_bulk_del"] = True
                        st.rerun()
                    if st.session_state.get("confirm_bulk_del"):
                        st.warning(f"Permanently delete all {len(errors)} error receipts?")
                        bc1, bc2 = st.columns(2)
                        if bc1.button("Yes, delete all", type="primary", key="yes_bulk_del"):
                            for err_r in errors:
                                api_delete(f"/receipts/{err_r['id']}")
                            st.session_state.pop("confirm_bulk_del", None)
                            st.success("All error receipts deleted.")
                            st.rerun()
                        if bc2.button("Cancel", key="cancel_bulk_del"):
                            st.session_state.pop("confirm_bulk_del", None)
                            st.rerun()
                    for r in errors:
                        _render_receipt_card(r, tab="error")
                else:
                    st.success("No error receipts.")

            with tab_proc:
                proc = [r for r in all_receipts if r.get("status") == "processing"]
                if not proc:
                    st.info("No receipts currently processing.")
                else:
                    from datetime import timezone, timedelta
                    now_utc = datetime.now(timezone.utc)
                    stuck = [
                        r for r in proc
                        if not r.get("created_at") or
                        (now_utc - datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))) >= timedelta(minutes=2)
                    ]
                    if stuck:
                        st.warning(f"{len(stuck)} receipt(s) appear stuck (processing for >2 min).")
                        if st.button(f"🗑️ Delete {len(stuck)} stuck receipt(s)", key="del_stuck_btn"):
                            for s in stuck:
                                api_delete(f"/receipts/{s['id']}")
                            st.success("Stuck receipts deleted.")
                            st.rerun()
                    for r in proc:
                        _render_receipt_card(r, tab="proc")

# ── Splits ────────────────────────────────────────────────────────────────────
def page_splits():
    st.markdown("## Split a Receipt")
    st.markdown("---")

    data = api_get("/receipts/") or {}
    receipts = data.get("receipts", [])
    groups   = api_get("/groups/") or []

    if not receipts:
        st.info("No receipts to split — upload one first.")
        return

    receipt_options = {
        f"{r.get('store_name') or 'Unknown'} — {r.get('receipt_date') or 'No date'} — ${r.get('total_amount') or 0:.2f}": r
        for r in receipts if r.get("items")
    }

    if not receipt_options:
        st.info("No receipts with extracted items yet.")
        return

    # Pre-select if coming from receipts page
    default_key = None
    if "split_receipt_id" in st.session_state:
        for k, v in receipt_options.items():
            if v["id"] == st.session_state.split_receipt_id:
                default_key = k
                break

    keys = list(receipt_options.keys())
    sel_key = st.selectbox("Select Receipt", keys, index=keys.index(default_key) if default_key else 0)
    receipt = receipt_options[sel_key]
    items   = receipt.get("items", [])

    group_options = {g["name"]: g for g in groups}
    if not group_options:
        st.warning("Create a group first to split receipts.")
        return

    sel_group_name = st.selectbox("Select Group", list(group_options.keys()))
    sel_group      = group_options[sel_group_name]
    members        = sel_group.get("members", [])

    if not members:
        st.warning("This group has no members.")
        return

    member_options  = {m["username"]: m["user_id"] for m in members}
    uid_to_username = {m["user_id"]: m["username"] for m in members}
    payer_id        = receipt.get("uploaded_by")

    # Warn if the group only has one member (the uploader)
    if len(members) == 1 and members[0]["user_id"] == payer_id:
        st.warning(
            f"You're the only member in **{sel_group_name}**. "
            "Add other people to the group first — settlements only work when items are "
            "assigned to members other than the bill payer."
        )

    st.markdown("### Assign Items to Members")
    st.caption("Personal = one person pays the full item. Equal = divide evenly among selected members. Percentage = custom share per person.")

    member_names = list(member_options.keys())
    assignments = []

    for item in items:
        total_item = round(float(item["price"]) * item["quantity"], 2)
        with st.container(border=True):
            left, right = st.columns([2, 3])
            left.markdown(f"**{item['name']}**")
            left.caption(f"Qty {item['quantity']} × ${item['price']:.2f} = **${total_item:.2f}**")

            with right:
                split_mode = st.radio(
                    "Split type", ["Personal", "Equal", "Percentage"],
                    key=f"mode_{item['id']}", horizontal=True, label_visibility="collapsed"
                )

                if split_mode == "Personal":
                    assigned = st.selectbox(
                        "Assigned to", member_names,
                        key=f"p_{item['id']}", label_visibility="collapsed"
                    )
                    assignments.append({
                        "item_id":    item["id"],
                        "user_id":    member_options[assigned],
                        "split_type": "personal",
                        "share_value": 1.0,
                    })

                elif split_mode == "Equal":
                    selected = st.multiselect("Split among", member_names, key=f"eq_{item['id']}")
                    if not selected:
                        st.caption("Select at least one member.")
                    else:
                        per_person = total_item / len(selected)
                        st.caption(f"${per_person:.2f} each × {len(selected)} people")
                        for uname in selected:
                            assignments.append({
                                "item_id":    item["id"],
                                "user_id":    member_options[uname],
                                "split_type": "equal",
                                "share_value": None,
                            })

                else:  # Percentage
                    selected = st.multiselect("Split among", member_names, key=f"pct_{item['id']}")
                    if not selected:
                        st.caption("Select members to assign percentages.")
                    else:
                        total_pct = 0.0
                        for uname in selected:
                            default_pct = round(100.0 / len(selected), 1)
                            pct = st.number_input(
                                f"{uname} %", min_value=0.0, max_value=100.0,
                                value=default_pct, step=5.0, format="%.1f",
                                key=f"pct_val_{item['id']}_{uname}"
                            )
                            total_pct += pct
                            assignments.append({
                                "item_id":    item["id"],
                                "user_id":    member_options[uname],
                                "split_type": "percentage",
                                "share_value": pct,
                            })
                        ok_pct = abs(total_pct - 100.0) <= 0.5
                        st.caption(f"Total: {total_pct:.1f}% {'✓' if ok_pct else '⚠️ must equal 100%'}")

    # Warn about items with no members selected (equal/pct with empty multiselect)
    assigned_item_ids = {a["item_id"] for a in assignments}
    unassigned = [it for it in items if it["id"] not in assigned_item_ids]
    if unassigned:
        st.warning(f"{len(unassigned)} item(s) have no members selected and will be skipped.")

    # Warn if all assignments go to the payer (no debt created)
    non_payer = [a for a in assignments if a["user_id"] != payer_id]
    if assignments and not non_payer and len(members) > 1:
        st.warning(
            "All items are currently assigned to you (the bill payer). "
            "No settlement debt will be created. Assign at least one item to another member."
        )

    st.markdown("---")
    if st.button("Confirm Split", type="primary", use_container_width=True):
        resp, ok = api_post(
            f"/splits/receipt/{receipt['id']}",
            json={"receipt_id": receipt["id"], "group_id": sel_group["id"], "assignments": assignments},
            expected=200,
        )
        if ok:
            st.success("Split saved!")
            user_totals = resp.get("user_totals", {})
            if user_totals:
                st.markdown("### Summary")
                for uid, amount in user_totals.items():
                    name = uid_to_username.get(uid, uid[:8])
                    st.metric(name, f"${amount:.2f}")
            if not non_payer:
                st.info("No settlement debt was created because all items were assigned to the payer.")
            if "split_receipt_id" in st.session_state:
                del st.session_state.split_receipt_id
        else:
            st.error(resp.get("detail", "Split failed"))

# ── Settlements ───────────────────────────────────────────────────────────────
def page_settlements():
    st.markdown("## Settlements")
    st.markdown("---")

    groups = api_get("/groups/") or []
    if not groups:
        st.info("No groups yet.")
        return

    group_options = {g["name"]: g["id"] for g in groups}
    sel_name = st.selectbox("Select Group", list(group_options.keys()))
    gid      = group_options[sel_name]

    tab_balances, tab_settle, tab_history = st.tabs(["Balances", "Record Payment", "History"])

    with tab_balances:
        data = api_get(f"/settlements/group/{gid}/balances")
        if data:
            total_unsettled = data.get("total_unsettled", 0)
            st.metric("Total Unsettled", f"${total_unsettled:.2f}")
            balances = data.get("balances", [])
            if balances:
                st.markdown("### Who Owes What")
                for b in balances:
                    from_u  = b.get("from_username") or b.get("from_user", "")[:8]
                    to_u    = b.get("to_username")   or b.get("to_user",   "")[:8]
                    amount  = b.get("amount", 0)
                    st.markdown(f"**{from_u}** owes **{to_u}** → `${amount:.2f}`")
            else:
                st.success("All settled up! No outstanding balances.")
        else:
            st.info("No balance data. Split some receipts first.")

    with tab_settle:
        st.markdown("### Record a Settlement Payment")
        sel_group_data = next((g for g in groups if g["id"] == gid), None)
        members        = sel_group_data.get("members", []) if sel_group_data else []
        if len(members) >= 2:
            with st.form("record_settlement"):
                member_opts  = {m["username"]: m["user_id"] for m in members}
                from_user    = st.selectbox("From (payer)", list(member_opts.keys()), key="s_from")
                to_user      = st.selectbox("To (receiver)", list(member_opts.keys()), key="s_to")
                amount       = st.number_input("Amount ($)", min_value=0.01, step=0.01)
                if st.form_submit_button("Record Payment", use_container_width=True):
                    if from_user == to_user:
                        st.error("Payer and receiver must be different.")
                    else:
                        resp, ok = api_post(f"/settlements/group/{gid}/settle", json={
                            "from_user": member_opts[from_user],
                            "to_user":   member_opts[to_user],
                            "amount":    amount,
                        }, expected=200)
                        if ok:
                            st.success(f"Payment of ${amount:.2f} recorded!")
                            st.rerun()
                        else:
                            st.error(resp.get("detail", "Failed"))
        else:
            st.info("Need at least 2 members to record a settlement.")

    with tab_history:
        history = api_get(f"/settlements/group/{gid}/history") or []
        if history:
            rows = []
            for s in history:
                rows.append({
                    "From":   s.get("from_user", "")[:8],
                    "To":     s.get("to_user",   "")[:8],
                    "Amount": f"${s.get('amount', 0):.2f}",
                    "Status": s.get("status", "").capitalize(),
                    "Date":   s.get("settled_at", "")[:10],
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No settlement history yet.")

# ── Analytics ─────────────────────────────────────────────────────────────────
def page_analytics():
    st.markdown("## Analytics & Insights")
    st.markdown("---")

    insights_data = api_get("/analytics/insights") or {}
    cat_spend     = insights_data.get("category_spending", [])
    store_spend   = insights_data.get("store_spending", [])
    trends        = insights_data.get("monthly_trends", [])
    top_items     = insights_data.get("top_items", [])
    month_comp    = insights_data.get("month_comparison", {})
    insight_cards = insights_data.get("insight_cards", [])

    # Insight cards
    if insight_cards:
        st.markdown("### Insights")
        cols = st.columns(min(len(insight_cards), 3))
        for i, card in enumerate(insight_cards):
            with cols[i % 3]:
                st.info(f"{card.get('icon','')} **{card.get('title','')}**\n\n{card.get('detail','')}")
        st.markdown("---")

    # Month comparison
    if month_comp and month_comp.get("previous_month", 0) > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric(month_comp.get("current_label", "This Month"),  f"${month_comp['current_month']:.2f}")
        c2.metric(month_comp.get("previous_label", "Last Month"), f"${month_comp['previous_month']:.2f}")
        delta = month_comp.get("change_pct", 0)
        c3.metric("Change", f"{delta:+.1f}%", delta=f"{delta:.1f}%", delta_color="inverse")
        st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Spending by Category")
        if cat_spend:
            df = pd.DataFrame(cat_spend)
            fig = px.bar(df, x="total", y="category", orientation="h",
                         color="total", color_continuous_scale="Blues",
                         labels={"total": "Amount ($)", "category": ""})
            fig.update_layout(showlegend=False, margin=dict(t=0), height=350, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No category data yet.")

    with col2:
        st.markdown("### Monthly Spending Trend")
        if trends:
            df = pd.DataFrame(trends)
            fig = px.line(df, x="month", y="total", markers=True,
                          labels={"month": "Month", "total": "Amount ($)"},
                          color_discrete_sequence=["#667eea"])
            fig.update_layout(margin=dict(t=0), height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data yet. More receipts needed.")

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("### Top Stores")
        if store_spend:
            df = pd.DataFrame(store_spend[:8])
            fig = px.bar(df, x="store_name", y="total",
                         color="total", color_continuous_scale="Greens",
                         labels={"store_name": "Store", "total": "Amount ($)"})
            fig.update_layout(showlegend=False, margin=dict(t=0), height=300, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No store data yet.")

    with col4:
        st.markdown("### Most Bought Items")
        if top_items:
            rows = [{"Item": i["name"], "Times Bought": i["frequency"],
                     "Total Spent": f"${i['total_spent']:.2f}", "Category": i.get("category", "—")}
                    for i in top_items]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No item data yet.")

# ── Sidebar nav ───────────────────────────────────────────────────────────────
def sidebar():
    user = st.session_state.get("user", {})
    with st.sidebar:
        st.markdown(f"### 🧾 SplitsenseAI")
        st.markdown(f"👤 **{user.get('username', '')}**")
        st.markdown(f"<small>{user.get('email', '')}</small>", unsafe_allow_html=True)
        st.markdown("---")

        pages = ["Overview", "Groups", "Receipts", "Splits", "Settlements", "Analytics"]
        icons = ["🏠", "👥", "🧾", "✂️", "💸", "📊"]

        current = st.session_state.get("page", "Overview")
        for icon, pg in zip(icons, pages):
            active = "background:#667eea; border-radius:8px; padding:4px 8px;" if pg == current else ""
            if st.button(f"{icon}  {pg}", key=f"nav_{pg}", use_container_width=True):
                st.session_state.page = pg
                st.rerun()

        st.markdown("---")
        if st.button("🚪  Logout", use_container_width=True):
            for key in ["token", "user", "page", "split_receipt_id", "selected_receipt"]:
                st.session_state.pop(key, None)
            st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if "token" not in st.session_state:
        page_auth()
        return

    sidebar()

    page = st.session_state.get("page", "Overview")
    {
        "Overview":    page_overview,
        "Groups":      page_groups,
        "Receipts":    page_receipts,
        "Splits":      page_splits,
        "Settlements": page_settlements,
        "Analytics":   page_analytics,
    }.get(page, page_overview)()


if __name__ == "__main__":
    main()
