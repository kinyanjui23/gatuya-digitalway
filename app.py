from __future__ import annotations

import base64
from datetime import date, datetime, time
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (correct_delivery, find_farmer, initialize, query_df,
                      record_delivery, record_labor_shift, record_processing,
                      receive_stock, dispatch_stock, save_farmer, save_laborer,
                      save_feedback, save_meeting, update_farmer_phone,
                      save_message_campaign, save_agrochemical_product,
                      record_agrochemical_transaction, create_agrochemical_loan_request,
                      decide_agrochemical_loan_request, seed_common_agrochemicals,
                      seed_demo_agrochemical_stock,
                      seed_demo_data, seed_demo_labor)
from sms_gateway import normalize_kenyan_phone, send_africas_talking_sms
from receipts import create_receipt_pdf


st.set_page_config(page_title="Gatuya Coffee Society", page_icon="☕", layout="wide")
initialize()


def agrochemical_image_path(formulation: str) -> Path:
    form = (formulation or "").lower()
    if "granule" in form:
        image_name = "granules.jpg"
    elif "powder" in form:
        image_name = "soluble-powder.jpg" if "soluble" in form else "wettable-powder.jpg"
    elif "liquid" in form or "concentrate" in form or form.endswith(" sl") or " ec" in form:
        image_name = "liquid.jpg"
    else:
        image_name = "wettable-powder.jpg"
    return Path(__file__).parent / "assets" / "agrochemicals" / image_name


def agrochemical_catalogue_cards(products: pd.DataFrame, show_availability: bool = False) -> None:
    if products.empty:
        st.info("No active agrochemicals are listed yet.")
        return
    st.caption("Package photos are illustrations for this prototype. Replace them with photos of the actual store items when available.")
    for start in range(0, len(products), 3):
        columns = st.columns(3)
        for column, (_, product) in zip(columns, products.iloc[start:start + 3].iterrows()):
            with column:
                image_path = agrochemical_image_path(str(product.get("formulation", "")))
                if image_path.exists():
                    st.image(str(image_path), use_container_width=True)
                st.markdown(f"**{product['name']}**")
                details = f"{product.get('product_type', 'Other')} · {product.get('formulation', 'Other')} · {product.get('unit', '')}"
                price = product.get("price_per_unit_kes")
                if price is not None and pd.notna(price):
                    details += f" · KES {float(price):,.2f} per {product.get('unit', 'unit')}"
                st.caption(details)
                if show_availability:
                    available = float(product.get("available", 0)) > 0
                    st.success("Available") if available else st.info("Out of stock")


@st.cache_data
def coffee_background_data_uri() -> str:
    image_path = Path(__file__).parent / ".streamlit" / "coffee-beans-bg.png"
    if not image_path.exists():
        return ""
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


coffee_background = coffee_background_data_uri()
if coffee_background:
    st.markdown(f"""
    <style>
    .stApp, [data-testid="stAppViewContainer"] {{
      background-image: linear-gradient(rgba(255,255,255,.22), rgba(255,255,255,.22)), url("{coffee_background}");
      background-size: cover; background-position: center; background-attachment: fixed;
    }}
    section.main [data-testid="stMainBlockContainer"] {{
      background: rgba(255,255,255,.86); border-radius: .75rem; padding: 1rem 1.25rem;
    }}
    </style>
    """, unsafe_allow_html=True)

st.title("☕ Gatuya Coffee Farmers Society")
st.caption("Coffee collection and society operations")

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #111111; }
[data-testid="stSidebar"] * { color: #ffffff; }
[data-testid="stSidebar"] div[role="radiogroup"] { gap: .35rem; }
[data-testid="stSidebar"] div[role="radiogroup"] label {
  background: #1d1d1d; border: 1px solid #3a3a3a; border-radius: .55rem;
  padding: .55rem .75rem; margin: 0;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: #176b3a; border-color: #ed1c24;
}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }
section.main div[data-testid="stRadio"] div[role="radiogroup"] label {
  background: #f1f5f2; border: 1px solid #176b3a; border-radius: .6rem;
  padding: .55rem 1rem; margin-right: .4rem;
}
section.main div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background: #176b3a; border-color: #ed1c24;
}
section.main div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child { display: none; }
section.main div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) * {
  color: #ffffff !important;
}
h1 { border-bottom: 4px solid #ed1c24; padding-bottom: .35rem; }
button[kind="primary"] { background: #176b3a; color: #ffffff !important; }
section.main, section.main [data-testid="stWidgetLabel"], section.main [data-testid="stMarkdownContainer"],
section.main label, section.main [data-baseweb="select"] span {
  color: #111111 !important;
}
section.main input, section.main textarea {
  background: #ffffff !important; color: #111111 !important;
}
section.main [data-baseweb="select"] div, section.main [data-baseweb="input"] div {
  color: #111111 !important;
}
</style>
""", unsafe_allow_html=True)

requested_portal = st.query_params.get("portal", "management")
portal_options = ["Management dashboard", "Farmer portal"]
portal_index = 1 if requested_portal == "farmer" else 0
portal = st.radio("Choose your dashboard", portal_options, index=portal_index,
                  horizontal=True, label_visibility="collapsed", key="portal_mode")
portal_value = "farmer" if portal == "Farmer portal" else "management"
if st.query_params.get("portal") != portal_value:
    st.query_params["portal"] = portal_value

management_pages = ["Overview", "Farmers", "Record delivery", "Processing / washing", "Store / stock",
                    "Agrochemicals & loans", "Labour", "Meetings & messages", "Delivery history",
                    "Manager corrections", "Feedback inbox", "Data & next steps"]
if portal == "Management dashboard":
    requested_page = st.query_params.get("page", "Overview")
    page_index = management_pages.index(requested_page) if requested_page in management_pages else 0
    page = st.sidebar.radio("Management sections", management_pages, index=page_index,
                            label_visibility="collapsed", key="management_section")
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
else:
    page = "Farmer portal"
    st.sidebar.info("Farmer self-service")


def require_admin() -> bool:
    try:
        expected_pin = st.secrets["admin_pin"]
    except Exception:
        expected_pin = None
    if not expected_pin:
        st.error("Authorized access is not configured yet. Follow the README to set an admin PIN in .streamlit/secrets.toml.")
        return False
    if st.session_state.get("admin_authorized"):
        st.sidebar.success("Authorized session")
        if st.sidebar.button("Lock authorized pages"):
            st.session_state["admin_authorized"] = False
            st.rerun()
        return True
    with st.form("admin_login"):
        pin = st.text_input("Authorized personnel PIN", type="password")
        login = st.form_submit_button("Unlock this page")
    if login:
        if pin == str(expected_pin):
            st.session_state["admin_authorized"] = True
            st.rerun()
        else:
            st.error("PIN not accepted.")
    return False


def overview() -> None:
    selected_day = st.date_input("Daily collection date", value=date.today())
    today = selected_day.isoformat()
    totals = query_df(
        "SELECT COUNT(*) AS deliveries, COALESCE(SUM(kg), 0) AS kg "
        "FROM deliveries WHERE delivery_date = ?",
        (today,),
    ).iloc[0]
    farmer_count = query_df("SELECT COUNT(*) AS n FROM farmers").iloc[0]["n"]
    left, middle, right = st.columns(3)
    left.metric("Deliveries today", int(totals["deliveries"]))
    middle.metric("Kilograms today", f"{totals['kg']:,.1f}")
    right.metric("Registered farmers", int(farmer_count))
    week_start = selected_day - pd.Timedelta(days=(selected_day.weekday() - 1) % 7).to_pytimedelta()
    week_end = week_start + pd.Timedelta(days=3).to_pytimedelta()
    week_total = query_df(
        "SELECT COALESCE(SUM(kg), 0) AS kg FROM deliveries WHERE delivery_date BETWEEN ? AND ?",
        (week_start.isoformat(), week_end.isoformat()),
    ).iloc[0]["kg"] / 1000
    st.metric(f"Collection this delivery week ({week_start:%d %b}–{week_end:%d %b})", f"{week_total:,.2f} / 100 tonnes")
    st.progress(min(float(week_total) / 100, 1.0), text="100 tonnes is the society's peak-week reference")
    st.caption("Expected delivery days: Tuesday–Friday. Cherry peak: late October through November, with some deliveries into December/January. Mbuni commonly arrives from February after drying.")

    st.subheader(f"Deliveries on {selected_day:%d %B %Y}")
    recent = query_df(
        "SELECT d.delivery_date AS Date, d.weighed_at AS 'Weighed at', "
        "f.share_number AS 'Share number', f.name AS Farmer, d.coffee_type AS Type, d.kg AS Kg "
        "FROM deliveries d JOIN farmers f ON f.id=d.farmer_id WHERE d.delivery_date=? "
        "ORDER BY d.weighed_at", (today,)
    )
    st.dataframe(recent, use_container_width=True, hide_index=True)

    if not recent.empty:
        st.subheader("Collection loaded as farmers deliver")
        recent["Cumulative tonnes"] = recent["Kg"].cumsum() / 1000
        chart = recent[["Weighed at", "Cumulative tonnes"]].set_index("Weighed at")
        st.line_chart(chart)
        st.metric("Total loaded that day", f"{recent['Kg'].sum() / 1000:,.2f} tonnes")
    else:
        st.info("No deliveries recorded for this date yet.")


def farmers() -> None:
    st.subheader("Register a farmer")
    with st.form("farmer_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        share = c1.text_input("Share number (unique)").strip()
        name = c2.text_input("Farmer name").strip()
        c3, c4 = st.columns(2)
        national_id = c3.text_input("National ID (optional)").strip() or None
        account = c4.text_input("Account number (optional)").strip() or None
        zone = st.text_input("Zone / village (optional)").strip() or None
        phone = st.text_input("Phone number for farmer updates (optional)").strip() or None
        submitted = st.form_submit_button("Save farmer", type="primary")
    if submitted:
        if not share or not name:
            st.error("Share number and farmer name are required.")
        else:
            try:
                save_farmer(share, name, national_id, account, zone, phone)
                st.success(f"Saved farmer {share} — {name}.")
            except Exception as exc:
                st.error(f"Could not save farmer: {exc}")
    st.subheader("Farmer register")
    st.dataframe(query_df(
        "SELECT share_number AS 'Share number', name AS Name, national_id AS 'National ID', "
        "account_number AS 'Account number', phone_number AS Phone, zone AS Zone FROM farmers ORDER BY share_number"
    ), use_container_width=True, hide_index=True)
    st.subheader("Update a farmer's phone number")
    contact_rows = query_df("SELECT id, share_number, name, phone_number FROM farmers ORDER BY share_number")
    if not contact_rows.empty:
        contact_options = {f"{r.share_number} — {r.name}": (int(r.id), r.phone_number or "")
                           for r in contact_rows.itertuples()}
        selected_contact = st.selectbox("Farmer", list(contact_options), key="phone_farmer")
        new_phone = st.text_input("Phone number", value=contact_options[selected_contact][1], key="phone_edit").strip()
        if st.button("Save phone number"):
            update_farmer_phone(contact_options[selected_contact][0], new_phone or None)
            st.success("Farmer phone number updated.")


def delivery() -> None:
    st.subheader("Record a farmer delivery")
    st.info("Each share number can have only one delivery per calendar day, across both coffee types.")
    if query_df("SELECT COUNT(*) AS n FROM farmers").iloc[0]["n"] == 0:
        st.warning("Register farmers before recording deliveries.")
        return
    share_number = st.text_input("Enter the farmer's share number", key="delivery_share").strip()
    farmer = find_farmer(share_number) if share_number else None
    if share_number and farmer is None:
        st.warning("No farmer found with that share number. Check the number or register the farmer.")
        return
    if not share_number:
        st.caption("The registered farmer name will appear here after the share number is entered.")
        return
    st.markdown(f"**Farmer found:** {farmer['name']}  ·  **Share number:** {farmer['share_number']}")
    confirmed = st.checkbox("Yes, this is the farmer's name", key="delivery_name_confirm")
    if not confirmed:
        st.caption("If the name is wrong, change the share number above and check again.")
        return
    with st.form("delivery_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        delivery_date = c1.date_input("Delivery date", value=date.today())
        weighed_time = c2.time_input("Exact weighing time", value=datetime.now().time().replace(microsecond=0))
        c3, c4 = st.columns(2)
        coffee_type = c3.selectbox("Coffee type", ["Cherry", "Mbuni"])
        kg = c4.number_input("Weight (kg)", min_value=0.1, step=0.1, format="%.1f")
        reference = st.text_input("Receipt / scale ticket number (optional)").strip() or None
        submitted = st.form_submit_button("Record delivery", type="primary")
    if submitted:
        try:
            if delivery_date.weekday() not in (1, 2, 3, 4):
                raise ValueError("Deliveries are scheduled Tuesday through Friday. Ask a manager before recording an exception.")
            receipt_number = reference or f"GAT-{delivery_date:%y%m%d}-{datetime.now():%H%M%S}-{farmer['share_number']}"
            delivery_id = record_delivery(int(farmer["id"]), delivery_date, weighed_time,
                                          coffee_type, kg, receipt_number)
            st.success(f"Recorded {kg:,.1f} kg of {coffee_type.lower()} for {farmer['share_number']} — {farmer['name']}.")
            receipt_pdf = create_receipt_pdf("COFFEE DELIVERY RECEIPT", [
                ("Receipt number", receipt_number),
                ("Farmer", farmer["name"]),
                ("Share number", farmer["share_number"]),
                ("Delivery date", delivery_date.strftime("%d %B %Y")),
                ("Weighing time", weighed_time.strftime("%H:%M:%S")),
                ("Coffee type", coffee_type),
                ("Weight", f"{kg:,.1f} kg"),
            ])
            st.download_button("Download / print delivery receipt (PDF)", receipt_pdf,
                               file_name=f"{receipt_number}.pdf", mime="application/pdf",
                               key=f"delivery_receipt_{delivery_id}")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Could not record delivery: {exc}")


def history() -> None:
    st.subheader("Delivery history")
    c1, c2 = st.columns(2)
    start = c1.date_input("From", value=date.today().replace(day=1), key="from")
    end = c2.date_input("To", value=date.today(), key="to")
    if start > end:
        st.error("The start date must be on or before the end date.")
        return
    rows = query_df(
        "SELECT d.delivery_date AS Date, d.weighed_at AS 'Weighed at', "
        "f.share_number AS 'Share number', f.name AS Farmer, d.coffee_type AS Type, "
        "d.kg AS Kg, d.receipt_number AS Receipt FROM deliveries d "
        "JOIN farmers f ON f.id=d.farmer_id WHERE d.delivery_date BETWEEN ? AND ? "
        "ORDER BY d.weighed_at DESC", (start.isoformat(), end.isoformat())
    )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if not rows.empty:
        st.download_button("Download CSV", rows.to_csv(index=False).encode("utf-8"),
                           "gatuya_deliveries.csv", "text/csv")
        st.subheader("Collection over time")
        period = st.selectbox("Group totals by", ["Week", "Month", "Year"])
        dated = rows.copy()
        dated["Date"] = pd.to_datetime(dated["Date"])
        if period == "Week":
            dated["Period"] = dated["Date"].dt.to_period("W").astype(str)
        elif period == "Month":
            dated["Period"] = dated["Date"].dt.to_period("M").astype(str)
        else:
            dated["Period"] = dated["Date"].dt.year.astype(str)
        summary = dated.groupby(["Period", "Type"], as_index=False)["Kg"].sum()
        chart_data = summary.pivot(index="Period", columns="Type", values="Kg").fillna(0)
        st.bar_chart(chart_data)


def farmer_dashboard() -> None:
    st.subheader("Farmer portal")
    st.write("View your kilograms, agrochemical loans and society meeting notifications, or send feedback.")
    with st.form("farmer_self_service"):
        share = st.text_input("Share number").strip()
        phone = st.text_input("Registered phone number", type="password").strip()
        view = st.form_submit_button("Open my farmer account", type="primary")
    if view:
        match = query_df(
            "SELECT id FROM farmers WHERE share_number=? AND phone_number=?",
            (share, phone),
        ) if share and phone else pd.DataFrame()
        if match.empty:
            st.session_state.pop("farmer_dashboard_id", None)
            st.error("Those details did not match a farmer record. Ask the society to check your share number and phone number.")
        else:
            st.session_state["farmer_dashboard_id"] = int(match.iloc[0]["id"])
    farmer_id = st.session_state.get("farmer_dashboard_id")
    farmer = query_df("SELECT share_number, name FROM farmers WHERE id=?", (farmer_id,)) if farmer_id else pd.DataFrame()
    if farmer_id and not farmer.empty:
        st.success(f"Signed in as {farmer.iloc[0]['name']} · share {farmer.iloc[0]['share_number']}")
        if st.button("Sign out of farmer account"):
            st.session_state.pop("farmer_dashboard_id", None)
            st.rerun()
    coffee_tab, loan_tab, notice_tab, feedback_tab = st.tabs(
        ["My kilograms", "Agrochemical loans", "Notifications", "Give feedback"]
    )
    with coffee_tab:
        if not farmer_id:
            st.info("Enter your share number and registered phone above to see your coffee history.")
        else:
            c1, c2 = st.columns(2)
            start = c1.date_input("From", value=date.today() - pd.Timedelta(days=365).to_pytimedelta(), key="farmer_from")
            end = c2.date_input("To", value=date.today(), key="farmer_to")
            if start <= end:
                rows = query_df(
                    "SELECT delivery_date AS Date, weighed_at AS 'Weighed at', coffee_type AS Type, kg AS Kg "
                    "FROM deliveries WHERE farmer_id=? AND delivery_date BETWEEN ? AND ? ORDER BY weighed_at",
                    (farmer_id, start.isoformat(), end.isoformat()),
                )
                total = float(rows["Kg"].sum()) if not rows.empty else 0.0
                cherry = float(rows.loc[rows["Type"] == "Cherry", "Kg"].sum()) if not rows.empty else 0.0
                mbuni = float(rows.loc[rows["Type"] == "Mbuni", "Kg"].sum()) if not rows.empty else 0.0
                m1, m2, m3 = st.columns(3)
                m1.metric("Total delivered", f"{total:,.1f} kg")
                m2.metric("Cherry", f"{cherry:,.1f} kg")
                m3.metric("Mbuni", f"{mbuni:,.1f} kg")
                if not rows.empty:
                    rows["Date"] = pd.to_datetime(rows["Date"])
                    rows["Period"] = rows["Date"].dt.to_period("M").astype(str)
                    monthly = rows.groupby(["Period", "Type"], as_index=False)["Kg"].sum()
                    st.subheader("Your production over time")
                    st.bar_chart(monthly.pivot(index="Period", columns="Type", values="Kg").fillna(0))
                    st.dataframe(rows.drop(columns=["Period"]), use_container_width=True, hide_index=True)
                else:
                    st.info("No deliveries found in that date range.")
            else:
                st.error("The start date must be on or before the end date.")
    with loan_tab:
        if not farmer_id:
            st.info("Sign in above to view your agrochemical loans.")
        else:
            loan_total = query_df(
                "SELECT COALESCE(SUM(CASE WHEN transaction_type='LOAN' THEN amount_kes "
                "WHEN transaction_type='REPAYMENT' THEN -amount_kes ELSE 0 END), 0) AS balance "
                "FROM agrochemical_transactions WHERE farmer_id=?", (farmer_id,)
            ).iloc[0]["balance"]
            st.metric("Outstanding agrochemical loan", f"KES {loan_total:,.2f}")
            loan_rows = query_df(
                "SELECT t.transacted_at AS 'Date', a.name AS Agrochemical, t.transaction_type AS Type, "
                "t.quantity AS Quantity, a.unit AS Unit, t.amount_kes AS 'KES amount', t.reference AS Reference "
                "FROM agrochemical_transactions t LEFT JOIN agrochemical_products a ON a.id=t.product_id "
                "WHERE t.farmer_id=? ORDER BY t.transacted_at DESC", (farmer_id,)
            )
            st.dataframe(loan_rows, use_container_width=True, hide_index=True)
            st.subheader("Agrochemicals available from the society store")
            available = query_df(
                "SELECT p.id, p.name, p.product_type, p.formulation, p.unit, p.registration_reference, "
                "p.price_per_unit_kes, COALESCE(SUM(CASE WHEN t.transaction_type='RECEIPT' THEN t.quantity "
                "WHEN t.transaction_type='LOAN' THEN -t.quantity ELSE 0 END), 0) - "
                "(SELECT COALESCE(SUM(r.requested_quantity), 0) FROM agrochemical_loan_requests r "
                "WHERE r.product_id=p.id AND r.status='APPROVED') AS available "
                "FROM agrochemical_products p LEFT JOIN agrochemical_transactions t ON t.product_id=p.id "
                "WHERE p.active=1 GROUP BY p.id ORDER BY p.name"
            )
            agrochemical_catalogue_cards(available, show_availability=True)
            available_products = available.loc[available["available"] > 0].copy() if not available.empty else available
            if available_products.empty:
                st.info("No products are currently available to request. The office can update stock when new items arrive.")
            else:
                product_options = {
                    f"{r.name} ({r.unit})": {
                        "id": int(r.id), "available": float(r.available), "unit": r.unit,
                    }
                    for r in available_products.itertuples()
                }
                selected_product = st.selectbox("Choose an agrochemical to request", list(product_options), key="farmer_loan_product")
                selected = product_options[selected_product]
                with st.form("farmer_loan_request_form", clear_on_submit=True):
                    requested_qty = st.number_input(
                        f"Quantity requested ({selected['unit']})", min_value=0.01,
                        max_value=selected["available"], step=min(1.0, selected["available"]),
                    )
                    farmer_notes = st.text_input("Optional note for the office").strip() or None
                    request_submit = st.form_submit_button("Apply for agrochemical loan", type="primary")
                if request_submit:
                    try:
                        request_id = create_agrochemical_loan_request(
                            farmer_id, selected["id"], requested_qty, farmer_notes)
                        st.success(f"Request #{request_id} sent to the society office. It is pending review; this does not issue the product yet.")
                    except ValueError as exc:
                        st.error(str(exc))
            st.subheader("Your agrochemical loan requests")
            requests = query_df(
                "SELECT r.id AS 'Request #', r.requested_at AS 'Requested at', p.name AS Agrochemical, "
                "r.requested_quantity AS Quantity, p.unit AS Unit, r.status AS Status, "
                "r.manager_notes AS 'Office response', r.issued_transaction_id AS 'Issue transaction' "
                "FROM agrochemical_loan_requests r JOIN agrochemical_products p ON p.id=r.product_id "
                "WHERE r.farmer_id=? ORDER BY r.requested_at DESC", (farmer_id,)
            )
            st.dataframe(requests, use_container_width=True, hide_index=True)
    with notice_tab:
        notices = query_df(
            "SELECT title AS Meeting, meeting_at AS 'Date and time', location AS Location, message AS Details "
            "FROM meeting_notices WHERE meeting_at >= datetime('now', 'localtime') ORDER BY meeting_at"
        )
        if notices.empty:
            st.info("There are no upcoming meeting notices right now.")
        else:
            st.dataframe(notices, use_container_width=True, hide_index=True)
    with feedback_tab:
        share_thoughts()
    st.caption("This prototype matches share number and registered phone. Add verified one-time SMS codes before publishing personal histories to the public internet.")


def meetings_messages() -> None:
    st.subheader("Meetings and farmer messages")
    with st.form("meeting_form", clear_on_submit=True):
        title = st.text_input("Meeting title").strip()
        a, b = st.columns(2)
        meeting_date = a.date_input("Meeting date", value=date.today())
        meeting_time = b.time_input("Meeting time", value=time(10, 0))
        location = st.text_input("Meeting location").strip()
        body = st.text_area("Message details (agenda or instructions)").strip()
        save = st.form_submit_button("Save meeting notice", type="primary")
    if save:
        if not title or not location:
            st.error("Meeting title and location are required.")
        else:
            save_meeting(title, f"{meeting_date.isoformat()} {meeting_time.strftime('%H:%M:%S')}",
                         location, body or "Please attend.")
            st.success("Meeting notice saved.")
    notices = query_df(
        "SELECT id, title, meeting_at, location, message FROM meeting_notices ORDER BY meeting_at DESC"
    )
    if notices.empty:
        st.info("Save a meeting notice to prepare a message.")
        return
    st.subheader("Prepare a message for all farmers")
    notice_options = {f"{r.meeting_at} — {r.title}": int(r.id) for r in notices.itertuples()}
    chosen = st.selectbox("Meeting notice", list(notice_options))
    notice = notices.loc[notices["id"] == notice_options[chosen]].iloc[0]
    recipient_rows = query_df(
        "SELECT share_number, name, phone_number FROM farmers WHERE phone_number IS NOT NULL AND phone_number<>'' ORDER BY share_number"
    )
    total = int(query_df("SELECT COUNT(*) AS n FROM farmers").iloc[0]["n"])
    recipient_numbers = []
    for number in recipient_rows["phone_number"].tolist():
        normalized = normalize_kenyan_phone(str(number))
        if normalized:
            recipient_numbers.append(normalized)
    recipient_numbers = sorted(set(recipient_numbers))
    st.metric("Valid, unique SMS recipients", f"{len(recipient_numbers)} / {total} farmers")
    invalid_count = len(recipient_rows) - len(recipient_numbers)
    if invalid_count:
        st.warning(f"{invalid_count} saved phone number(s) are invalid or duplicated and will not receive this message.")
    message_text = (f"Gatuya Coffee Society meeting: {notice['title']} on {notice['meeting_at']} "
                    f"at {notice['location']}. {notice['message']}")
    edited_message = st.text_area("SMS message draft", value=message_text, height=110,
                                  key=f"sms_draft_{notice_options[chosen]}")
    if not recipient_rows.empty:
        st.download_button("Download recipient phone list (CSV)",
                           recipient_rows[["share_number", "phone_number"]].to_csv(index=False).encode("utf-8"),
                           "gatuya_meeting_recipients.csv", "text/csv")
    try:
        sms_username = str(st.secrets["sms_username"])
        sms_api_key = str(st.secrets["sms_api_key"])
        sms_sender_id = str(st.secrets["sms_sender_id"])
    except Exception:
        sms_username = sms_api_key = sms_sender_id = ""
    if not (sms_username and sms_api_key and sms_sender_id):
        st.info("To enable sending, add Africa's Talking username, API key and approved sender ID to .streamlit/secrets.toml. Until then, this page only prepares the message and phone list.")
    else:
        st.warning(f"Sending submits this message to {len(recipient_numbers)} farmers through Africa's Talking and may incur SMS charges. Review the text and recipient count first.")
        confirm_send = st.checkbox(
            f"I reviewed the message and confirm sending it to {len(recipient_numbers)} unique phone numbers.",
            key=f"confirm_sms_{notice_options[chosen]}"
        )
        send_clicked = st.button("Send meeting SMS now", type="primary",
                                 disabled=(not confirm_send or not recipient_numbers or not edited_message.strip()))
        if send_clicked:
            try:
                with st.spinner("Submitting SMS campaign…"):
                    response = send_africas_talking_sms(sms_username, sms_api_key, sms_sender_id,
                                                        edited_message.strip(), recipient_numbers)
                response_json = json.dumps(response, ensure_ascii=False, default=str)
                save_message_campaign(notice_options[chosen], edited_message.strip(),
                                      len(recipient_numbers), "submitted", response_json)
                st.success("Campaign submitted to Africa's Talking. This confirms API submission, not delivery to every phone.")
                st.json(response)
            except Exception as exc:
                save_message_campaign(notice_options[chosen], edited_message.strip(),
                                      len(recipient_numbers), "failed", str(exc))
                st.error(f"SMS campaign failed: {exc}")
    st.subheader("Saved meeting notices")
    st.dataframe(notices.rename(columns={"meeting_at": "Meeting time", "location": "Location", "message": "Details"}),
                 use_container_width=True, hide_index=True)
    campaigns = query_df(
        "SELECT attempted_at AS 'Attempted at', recipient_count AS Recipients, status AS Status, "
        "message AS Message FROM message_campaigns ORDER BY attempted_at DESC LIMIT 50"
    )
    st.subheader("SMS campaign history")
    st.dataframe(campaigns, use_container_width=True, hide_index=True)


def share_thoughts() -> None:
    st.subheader("Share your thoughts with Gatuya Society")
    st.write("Suggestions, questions and concerns are welcome. You may leave your feedback anonymously.")
    with st.form("public_feedback", clear_on_submit=True):
        category = st.selectbox("Topic", ["Coffee collection", "Washing / quality", "Payments", "Agrochemicals", "Meetings", "Other"])
        message = st.text_area("Your thoughts", max_chars=3000)
        contact = st.text_input("Name or contact (optional)").strip() or None
        submit = st.form_submit_button("Send feedback", type="primary")
    if submit:
        if not message.strip():
            st.error("Please write a message before submitting.")
        else:
            save_feedback(category, message, contact)
            st.success("Thank you. Your feedback has been saved for the society.")
    st.caption("For people outside your network to use this form, the app must be deployed to a public URL. Share the URL while this page is selected.")


def feedback_inbox() -> None:
    st.subheader("Feedback inbox")
    inbox = query_df(
        "SELECT submitted_at AS 'Submitted at', category AS Topic, message AS Feedback, contact AS Contact "
        "FROM feedback_submissions ORDER BY submitted_at DESC"
    )
    st.dataframe(inbox, use_container_width=True, hide_index=True)


def manager_corrections() -> None:
    st.subheader("Manager: correct a delivery")
    rows = query_df(
        "SELECT d.id, d.delivery_date AS Date, d.weighed_at AS 'Weighed at', "
        "f.share_number AS 'Share number', f.name AS Farmer, d.coffee_type AS Type, d.kg AS Kg "
        "FROM deliveries d JOIN farmers f ON f.id=d.farmer_id ORDER BY d.weighed_at DESC LIMIT 200"
    )
    if rows.empty:
        st.info("There are no deliveries to correct yet.")
        return
    options = {
        f"#{int(r['id'])} · {r['Date']} · {r['Share number']} — {r['Farmer']} · {r['Kg']:g} kg": int(r['id'])
        for _, r in rows.iterrows()
    }
    label = st.selectbox("Choose the delivery", list(options))
    delivery_id = options[label]
    current = query_df("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).iloc[0]
    farmers_df = query_df("SELECT id, share_number, name FROM farmers ORDER BY share_number")
    farmer_map = {f"{r.share_number} — {r.name}": int(r.id) for r in farmers_df.itertuples()}
    current_label = next((label for label, fid in farmer_map.items() if fid == int(current["farmer_id"])), None)
    with st.form("correction_form"):
        corrected_farmer = st.selectbox("Correct farmer", list(farmer_map),
                                         index=list(farmer_map).index(current_label) if current_label else 0)
        d1, d2 = st.columns(2)
        corrected_date = d1.date_input("Correct date", value=date.fromisoformat(current["delivery_date"]))
        corrected_time = d2.time_input("Correct weighing time", value=time.fromisoformat(current["weighed_at"].split()[1]))
        d3, d4 = st.columns(2)
        corrected_type = d3.selectbox("Correct type", ["Cherry", "Mbuni"],
                                      index=["Cherry", "Mbuni"].index(current["coffee_type"]))
        corrected_kg = d4.number_input("Correct kilograms", min_value=0.1, value=float(current["kg"]), step=0.1)
        reason = st.text_input("Reason for correction (required)")
        submit = st.form_submit_button("Save correction", type="primary")
    if submit:
        if not reason.strip():
            st.error("Enter a reason so the audit trail explains the change.")
        else:
            try:
                correct_delivery(delivery_id, farmer_map[corrected_farmer], corrected_date,
                                 corrected_time, corrected_type, corrected_kg, reason)
                st.success("Correction saved and recorded in the audit trail.")
            except ValueError as exc:
                st.error(str(exc))
    st.subheader("Correction audit trail")
    st.dataframe(query_df(
        "SELECT delivery_id AS 'Delivery ID', action AS Action, reason AS Reason, "
        "changed_at AS 'Changed at', before_json AS Before, after_json AS After "
        "FROM delivery_audit ORDER BY changed_at DESC LIMIT 100"
    ), use_container_width=True, hide_index=True)


def processing() -> None:
    st.subheader("Cherry washing and grading")
    st.caption("Record the date and time a cherry batch is washed, its input weight, and the graded output weights.")
    with st.form("processing_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        processed_date = c1.date_input("Washed on", value=date.today())
        processed_time = c2.time_input("Time", value=datetime.now().time().replace(microsecond=0))
        input_kg = st.number_input("Cherry input (kg)", min_value=0.1, step=1.0)
        g1, g2, g3, g4 = st.columns(4)
        pp1 = g1.number_input("PP1 (kg)", min_value=0.0, step=1.0)
        pp2 = g2.number_input("PP2 (kg)", min_value=0.0, step=1.0)
        third = g3.number_input("Third grade (kg)", min_value=0.0, step=1.0)
        light = g4.number_input("Light (kg)", min_value=0.0, step=1.0)
        notes = st.text_input("Batch / operator notes").strip() or None
        submit = st.form_submit_button("Save washing batch", type="primary")
    if submit:
        try:
            batch_id = record_processing(f"{processed_date.isoformat()} {processed_time.strftime('%H:%M:%S')}",
                                          input_kg, pp1, pp2, third, light, notes)
            st.success(f"Washing batch #{batch_id} saved. Grade outputs were added to stock automatically.")
        except ValueError as exc:
            st.error(str(exc))
    st.subheader("Washing history")
    batches = query_df(
        "SELECT processed_at AS 'Washed at', input_cherry_kg AS 'Cherry input kg', pp1_kg AS 'PP1 kg', "
        "pp2_kg AS 'PP2 kg', third_kg AS 'Third kg', light_kg AS 'Light kg', notes AS Notes "
        "FROM processing_batches ORDER BY processed_at DESC LIMIT 300"
    )
    st.dataframe(batches, use_container_width=True, hide_index=True)
    if not batches.empty:
        st.subheader("Graded coffee totals in store from washing records")
        grades = batches[["PP1 kg", "PP2 kg", "Third kg", "Light kg"]].sum()
        st.bar_chart(grades)
        st.caption("This table shows produced quantities. For current balances after dispatches, open Store / stock.")


def store_stock() -> None:
    st.subheader("Coffee store balances")
    grades = ["PP1", "PP2", "Third grade", "Light", "Mbuni"]
    balance_rows = query_df(
        "SELECT grade, SUM(CASE WHEN direction='IN' THEN kg ELSE -kg END) AS kg "
        "FROM stock_movements GROUP BY grade"
    )
    balances = {r["grade"]: float(r["kg"] or 0) for _, r in balance_rows.iterrows()}
    balance_view = pd.DataFrame({"Grade": grades, "On hand (kg)": [balances.get(g, 0.0) for g in grades]})
    st.dataframe(balance_view, use_container_width=True, hide_index=True)
    st.bar_chart(balance_view.set_index("Grade"))

    receipt_tab, dispatch_tab = st.tabs(["Receive into store", "Dispatch from store"])
    with receipt_tab:
        st.caption("Use this for dried mbuni, opening balances, or other coffee stock brought into the store. Washing batches add graded outputs automatically.")
        with st.form("stock_receipt_form", clear_on_submit=True):
            grade = st.selectbox("Grade received", grades, key="receipt_grade")
            c1, c2 = st.columns(2)
            receipt_date = c1.date_input("Receipt date", value=date.today(), key="receipt_date")
            receipt_time = c2.time_input("Receipt time", value=datetime.now().time().replace(microsecond=0), key="receipt_time")
            receipt_kg = st.number_input("Kilograms received", min_value=0.1, step=1.0, key="receipt_kg")
            reference = st.text_input("Batch / store receipt number", key="receipt_ref").strip()
            receipt_notes = st.text_input("Notes (e.g. dried mbuni from farmer collection)", key="receipt_notes").strip() or None
            save_receipt = st.form_submit_button("Record store receipt", type="primary")
        if save_receipt:
            if not reference:
                st.error("Enter a batch or receipt number for traceability.")
            else:
                try:
                    receive_stock(f"{receipt_date.isoformat()} {receipt_time.strftime('%H:%M:%S')}",
                                  grade, receipt_kg, reference, receipt_notes)
                    st.success(f"Received {receipt_kg:,.1f} kg of {grade} into store.")
                except Exception as exc:
                    st.error(f"Could not record receipt: {exc}")
    with dispatch_tab:
        with st.form("stock_dispatch_form", clear_on_submit=True):
            out_grade = st.selectbox("Grade dispatched", grades, key="dispatch_grade")
            st.caption(f"Available now: {balances.get(out_grade, 0.0):,.1f} kg")
            d1, d2 = st.columns(2)
            dispatch_date = d1.date_input("Dispatch date", value=date.today(), key="dispatch_date")
            dispatch_time = d2.time_input("Dispatch time", value=datetime.now().time().replace(microsecond=0), key="dispatch_time")
            dispatch_kg = st.number_input("Kilograms leaving store", min_value=0.1, step=1.0, key="dispatch_kg")
            dispatch_ref = st.text_input("Dispatch / vehicle / waybill reference", key="dispatch_ref").strip()
            dispatch_notes = st.text_input("Destination or notes", key="dispatch_notes").strip() or None
            save_dispatch = st.form_submit_button("Record dispatch", type="primary")
        if save_dispatch:
            if not dispatch_ref:
                st.error("Enter a dispatch, vehicle or waybill reference.")
            else:
                try:
                    remaining = dispatch_stock(
                        f"{dispatch_date.isoformat()} {dispatch_time.strftime('%H:%M:%S')}",
                        out_grade, dispatch_kg, dispatch_ref, dispatch_notes)
                    st.success(f"Dispatch recorded. {remaining:,.1f} kg of {out_grade} remains in stock.")
                except ValueError as exc:
                    st.error(str(exc))
    st.subheader("Stock movement ledger")
    ledger = query_df(
        "SELECT movement_at AS 'Moved at', grade AS Grade, direction AS Direction, kg AS Kg, "
        "movement_kind AS Movement, reference AS Reference, notes AS Notes "
        "FROM stock_movements ORDER BY movement_at DESC, id DESC LIMIT 500"
    )
    st.dataframe(ledger, use_container_width=True, hide_index=True)


def agrochemicals_loans() -> None:
    st.subheader("Agrochemical store and farmer loans")
    st.caption("Catalogue examples are for inventory tracking. Confirm current Kenyan registration, coffee use, label and supplier before purchasing or issuing any crop-protection product.")
    if st.button("Load fictional demo agrochemical catalogue and stock"):
        added, stocked = seed_demo_agrochemical_stock()
        st.success(f"Added {added} catalogue items and loaded demo stock for {stocked} items. This stock is fictional; replace it with a physical count before real use.")
        st.rerun()
    products = query_df(
        "SELECT id, name, product_type, formulation, unit, price_per_unit_kes, registration_reference "
        "FROM agrochemical_products WHERE active=1 ORDER BY name"
    )
    st.subheader("Agrochemical catalogue")
    agrochemical_catalogue_cards(products)
    farmers_df = query_df("SELECT id, share_number, name FROM farmers ORDER BY share_number")
    create_tab, receive_tab, issue_tab, repayment_tab, requests_tab = st.tabs(
        ["Add product", "Receive stock", "Issue farmer loan", "Record repayment", "Farmer requests"]
    )
    with create_tab:
        with st.form("agro_product_form", clear_on_submit=True):
            product_name = st.text_input("Agrochemical name").strip()
            product_type = st.selectbox("Type", ["Fungicide", "Insect control", "Biopesticide", "Herbicide",
                                                  "Foliar fertilizer", "Granular fertilizer", "Micronutrient fertilizer",
                                                  "Soil amendment", "Adjuvant", "Other"])
            formulation = st.selectbox("Formulation / form", ["Liquid", "Emulsifiable concentrate", "Soluble concentrate",
                                                               "Suspension concentrate", "Wettable powder", "Soluble powder",
                                                               "Granules", "Water-dispersible granules", "Biological product", "Other"])
            unit = st.selectbox("Store unit", ["litre", "ml", "kg", "gram", "bag", "packet", "bottle", "pack", "other"])
            default_price = st.number_input("Default loan price per unit (KES)", min_value=0.0, step=10.0)
            registration = st.text_input("PCPB registration / supplier reference (optional)").strip() or None
            save_product = st.form_submit_button("Add agrochemical")
        if save_product:
            if not product_name:
                st.error("Enter the agrochemical name.")
            else:
                try:
                    save_agrochemical_product(product_name, product_type, formulation, unit,
                                              default_price, registration)
                    st.success(f"Added {product_name}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not add product: {exc}")
    product_map = {f"{r.name} ({r.formulation}, {r.unit})":
                   (int(r.id), r.product_type, r.formulation, r.unit,
                    float(r.price_per_unit_kes), r.registration_reference)
                   for r in products.itertuples()}
    farmer_map = {f"{r.share_number} — {r.name}": (int(r.id), r.share_number, r.name)
                  for r in farmers_df.itertuples()}
    with receive_tab:
        if not product_map:
            st.info("Add an agrochemical product first.")
        else:
            with st.form("agro_receipt_form", clear_on_submit=True):
                selected_product = st.selectbox("Product received", list(product_map))
                qty = st.number_input("Quantity received", min_value=0.01, step=1.0)
                ref = st.text_input("Supplier / purchase reference").strip()
                dt = st.date_input("Receipt date", value=date.today())
                tm = st.time_input("Receipt time", value=datetime.now().time().replace(microsecond=0))
                notes = st.text_input("Notes").strip() or None
                submit_receipt = st.form_submit_button("Record stock receipt", type="primary")
            if submit_receipt:
                if not ref:
                    st.error("Enter a supplier or receipt reference.")
                else:
                    try:
                        record_agrochemical_transaction(
                            f"{dt.isoformat()} {tm.strftime('%H:%M:%S')}", "RECEIPT",
                            product_map[selected_product][0], None, qty, 0, 0, ref, notes)
                        st.success("Agrochemical stock received.")
                    except Exception as exc:
                        st.error(f"Could not record receipt: {exc}")
    with issue_tab:
        if not product_map or not farmer_map:
            st.info("Register farmers and add agrochemical products first.")
        else:
            with st.form("agro_loan_form", clear_on_submit=True):
                selected_product = st.selectbox("Agrochemical", list(product_map), key="loan_product")
                selected_farmer = st.selectbox("Farmer", list(farmer_map), key="loan_farmer")
                qty = st.number_input("Quantity issued", min_value=0.01, step=1.0, key="loan_qty")
                st.caption(f"Type: {product_map[selected_product][1]} · Form: {product_map[selected_product][2]} · Default rate: KES {product_map[selected_product][4]:,.2f} per {product_map[selected_product][3]}")
                price = st.number_input("Loan rate per unit (KES)", min_value=0.0,
                                        value=product_map[selected_product][4], step=10.0, key="loan_price")
                ref = st.text_input("Loan voucher / issue reference (optional)", key="loan_ref").strip()
                dt = st.date_input("Issue date", value=date.today(), key="loan_date")
                tm = st.time_input("Issue time", value=datetime.now().time().replace(microsecond=0), key="loan_time")
                notes = st.text_input("Notes", key="loan_notes").strip() or None
                submit_loan = st.form_submit_button("Issue as farmer loan", type="primary")
            if submit_loan:
                try:
                    loan_ref = ref or f"AGL-{dt:%y%m%d}-{datetime.now():%H%M%S}"
                    transaction_id = record_agrochemical_transaction(
                        f"{dt.isoformat()} {tm.strftime('%H:%M:%S')}", "LOAN",
                        product_map[selected_product][0], farmer_map[selected_farmer][0],
                        qty, price, 0, loan_ref, notes)
                    balance = query_df(
                        "SELECT COALESCE(SUM(CASE WHEN transaction_type='LOAN' THEN amount_kes "
                        "WHEN transaction_type='REPAYMENT' THEN -amount_kes ELSE 0 END), 0) AS balance "
                        "FROM agrochemical_transactions WHERE farmer_id=?", (farmer_map[selected_farmer][0],)
                    ).iloc[0]["balance"]
                    st.success(f"Loan issued. Value added to farmer balance: KES {qty * price:,.2f}.")
                    pdf = create_receipt_pdf("AGROCHEMICAL LOAN RECEIPT", [
                        ("Receipt number", loan_ref),
                        ("Farmer", farmer_map[selected_farmer][2]),
                        ("Share number", farmer_map[selected_farmer][1]),
                        ("Issue date", dt.strftime("%d %B %Y")),
                        ("Issue time", tm.strftime("%H:%M:%S")),
                        ("Agrochemical", selected_product),
                        ("Type / formulation", f"{product_map[selected_product][1]} / {product_map[selected_product][2]}"),
                        ("Quantity issued", f"{qty:g} {product_map[selected_product][3]}"),
                        ("Loan rate", f"KES {price:,.2f} per {product_map[selected_product][3]}"),
                        ("Loan value", f"KES {qty * price:,.2f}"),
                        ("Outstanding after issue", f"KES {balance:,.2f}"),
                        ("Reference", loan_ref),
                    ])
                    st.download_button("Download / print agrochemical loan receipt (PDF)", pdf,
                                       file_name=f"{loan_ref}.pdf", mime="application/pdf",
                                       key=f"agro_receipt_{transaction_id}")
                except ValueError as exc:
                    st.error(str(exc))
        approved_requests = query_df(
            "SELECT r.id, r.farmer_id, r.product_id, r.requested_quantity, r.farmer_notes, "
            "f.share_number, f.name AS farmer_name, p.name AS product_name, p.product_type, "
            "p.formulation, p.unit, p.price_per_unit_kes "
            "FROM agrochemical_loan_requests r JOIN farmers f ON f.id=r.farmer_id "
            "JOIN agrochemical_products p ON p.id=r.product_id "
            "WHERE r.status='APPROVED' ORDER BY r.requested_at"
        )
        st.subheader("Fulfil an approved farmer request")
        if approved_requests.empty:
            st.info("No approved requests are waiting for store issue.")
        else:
            approved_map = {
                f"#{int(r.id)} · {r.share_number} {r.farmer_name} · {r.product_name} · {r.requested_quantity:g} {r.unit}": int(r.id)
                for r in approved_requests.itertuples()
            }
            approved_label = st.selectbox("Approved request", list(approved_map), key="approved_loan_request")
            approved = approved_requests.loc[approved_requests["id"] == approved_map[approved_label]].iloc[0]
            st.caption(f"Issue exactly {approved['requested_quantity']:g} {approved['unit']} of {approved['product_name']} to {approved['farmer_name']} (share {approved['share_number']}). The office receipt is generated after recording the issue.")
            with st.form("approved_loan_issue_form", clear_on_submit=True):
                approved_price = st.number_input(
                    "Loan rate per unit (KES)", min_value=0.0,
                    value=float(approved["price_per_unit_kes"]), step=10.0,
                    key=f"approved_price_{int(approved['id'])}",
                )
                approved_ref = st.text_input("Issue voucher / reference (optional)", key="approved_issue_ref").strip()
                approved_date = st.date_input("Store issue date", value=date.today(), key="approved_issue_date")
                approved_time = st.time_input("Store issue time", value=datetime.now().time().replace(microsecond=0), key="approved_issue_time")
                approved_notes = st.text_input("Office notes", key="approved_issue_notes").strip() or None
                fulfill = st.form_submit_button("Issue product and print receipt", type="primary")
            if fulfill:
                try:
                    approved_receipt = approved_ref or f"AGL-{approved_date:%y%m%d}-{datetime.now():%H%M%S}"
                    transaction_id = record_agrochemical_transaction(
                        f"{approved_date.isoformat()} {approved_time.strftime('%H:%M:%S')}", "LOAN",
                        int(approved["product_id"]), int(approved["farmer_id"]),
                        float(approved["requested_quantity"]), approved_price, 0,
                        approved_receipt, approved_notes, loan_request_id=int(approved["id"]),
                    )
                    balance = query_df(
                        "SELECT COALESCE(SUM(CASE WHEN transaction_type='LOAN' THEN amount_kes "
                        "WHEN transaction_type='REPAYMENT' THEN -amount_kes ELSE 0 END), 0) AS balance "
                        "FROM agrochemical_transactions WHERE farmer_id=?", (int(approved["farmer_id"]),)
                    ).iloc[0]["balance"]
                    receipt_pdf = create_receipt_pdf("AGROCHEMICAL LOAN RECEIPT", [
                        ("Receipt number", approved_receipt),
                        ("Farmer", approved["farmer_name"]),
                        ("Share number", approved["share_number"]),
                        ("Issue date", approved_date.strftime("%d %B %Y")),
                        ("Issue time", approved_time.strftime("%H:%M:%S")),
                        ("Agrochemical", approved["product_name"]),
                        ("Type / formulation", f"{approved['product_type']} / {approved['formulation']}"),
                        ("Quantity issued", f"{approved['requested_quantity']:g} {approved['unit']}"),
                        ("Loan rate", f"KES {approved_price:,.2f} per {approved['unit']}"),
                        ("Loan value", f"KES {float(approved['requested_quantity']) * approved_price:,.2f}"),
                        ("Outstanding after issue", f"KES {balance:,.2f}"),
                        ("Request #", int(approved["id"])),
                    ])
                    st.success("Request fulfilled. The office receipt is ready to print.")
                    st.download_button("Download / print office loan receipt (PDF)", receipt_pdf,
                                       file_name=f"{approved_receipt}.pdf", mime="application/pdf",
                                       key=f"approved_agro_receipt_{transaction_id}")
                except ValueError as exc:
                    st.error(str(exc))
    with repayment_tab:
        if not farmer_map:
            st.info("Register farmers first.")
        else:
            with st.form("agro_repayment_form", clear_on_submit=True):
                selected_farmer = st.selectbox("Farmer repaying", list(farmer_map), key="repay_farmer")
                amount = st.number_input("Repayment / deduction (KES)", min_value=0.01, step=50.0)
                ref = st.text_input("Payment / deduction reference").strip()
                dt = st.date_input("Repayment date", value=date.today(), key="repayment_date")
                tm = st.time_input("Repayment time", value=datetime.now().time().replace(microsecond=0), key="repayment_time")
                notes = st.text_input("Notes", key="repayment_notes").strip() or None
                submit_repayment = st.form_submit_button("Record repayment")
            if submit_repayment:
                if not ref:
                    st.error("Enter a payment or deduction reference.")
                else:
                    try:
                        record_agrochemical_transaction(
                            f"{dt.isoformat()} {tm.strftime('%H:%M:%S')}", "REPAYMENT",
                            None, farmer_map[selected_farmer][0], 0, 0, amount, ref, notes)
                        st.success("Repayment recorded.")
                    except ValueError as exc:
                        st.error(str(exc))
    stock = query_df(
        "SELECT p.name AS Agrochemical, p.product_type AS Type, p.formulation AS Formulation, "
        "p.unit AS Unit, p.registration_reference AS 'Registration / reference', "
        "COALESCE(SUM(CASE WHEN t.transaction_type='RECEIPT' THEN t.quantity "
        "WHEN t.transaction_type='LOAN' THEN -t.quantity ELSE 0 END), 0) AS 'On hand' "
        "FROM agrochemical_products p LEFT JOIN agrochemical_transactions t ON t.product_id=p.id "
        "GROUP BY p.id ORDER BY p.name"
    )
    st.subheader("Agrochemical stock on hand")
    st.dataframe(stock, use_container_width=True, hide_index=True)
    outstanding = query_df(
        "SELECT f.share_number AS 'Share number', f.name AS Farmer, "
        "SUM(CASE WHEN t.transaction_type='LOAN' THEN t.amount_kes "
        "WHEN t.transaction_type='REPAYMENT' THEN -t.amount_kes ELSE 0 END) AS 'Outstanding KES' "
        "FROM farmers f JOIN agrochemical_transactions t ON t.farmer_id=f.id "
        "GROUP BY f.id HAVING SUM(CASE WHEN t.transaction_type='LOAN' THEN t.amount_kes "
        "WHEN t.transaction_type='REPAYMENT' THEN -t.amount_kes ELSE 0 END) > 0 ORDER BY f.share_number"
    )
    st.subheader("Outstanding farmer loans")
    st.dataframe(outstanding, use_container_width=True, hide_index=True)
    ledger = query_df(
        "SELECT t.transacted_at AS 'Date', t.transaction_type AS Type, p.name AS Agrochemical, "
        "f.share_number AS 'Share number', f.name AS Farmer, t.quantity AS Quantity, "
        "t.unit_price_kes AS 'Rate KES', t.amount_kes AS 'Amount KES', t.reference AS Reference "
        "FROM agrochemical_transactions t LEFT JOIN agrochemical_products p ON p.id=t.product_id "
        "LEFT JOIN farmers f ON f.id=t.farmer_id ORDER BY t.transacted_at DESC LIMIT 500"
    )
    st.subheader("Agrochemical movement ledger")
    st.dataframe(ledger, use_container_width=True, hide_index=True)
    with requests_tab:
        st.subheader("Review farmer loan requests")
        request_rows = query_df(
            "SELECT r.id AS id, r.requested_at AS 'Requested at', f.share_number AS 'Share number', "
            "f.name AS Farmer, p.name AS Agrochemical, r.requested_quantity AS Quantity, p.unit AS Unit, "
            "r.farmer_notes AS 'Farmer note', r.status AS Status, r.manager_notes AS 'Office note' "
            "FROM agrochemical_loan_requests r JOIN farmers f ON f.id=r.farmer_id "
            "JOIN agrochemical_products p ON p.id=r.product_id ORDER BY r.requested_at DESC"
        )
        pending = request_rows[request_rows["Status"] == "PENDING"] if not request_rows.empty else request_rows
        if pending.empty:
            st.info("There are no pending farmer requests.")
        else:
            request_options = {
                f"#{int(r['id'])} · {r['Share number']} {r['Farmer']} · {r['Agrochemical']} · {r['Quantity']:g} {r['Unit']}": int(r["id"])
                for _, r in pending.iterrows()
            }
            selected_request = st.selectbox("Pending request", list(request_options), key="pending_loan_request")
            with st.form("review_farmer_loan_request"):
                decision = st.selectbox("Decision", ["Approve", "Reject"])
                manager_note = st.text_input("Optional response to farmer").strip() or None
                review_submit = st.form_submit_button("Save decision", type="primary")
            if review_submit:
                try:
                    decision_status = "APPROVED" if decision == "Approve" else "REJECTED"
                    decide_agrochemical_loan_request(request_options[selected_request], decision_status, manager_note)
                    st.success(f"Request {decision.lower()}d. The farmer will see the status in their portal.")
                except ValueError as exc:
                    st.error(str(exc))
        st.subheader("All farmer loan requests")
        st.dataframe(request_rows.drop(columns=["id"]) if not request_rows.empty else request_rows,
                     use_container_width=True, hide_index=True)


def labour() -> None:
    st.subheader("Labour and overtime")
    st.caption("Pay rule used: KES 400 for up to 8 paid hours; deduct the recorded break, then pay KES 50 for each extra hour.")
    with st.expander("Add a labourer"):
        with st.form("laborer_form", clear_on_submit=True):
            name = st.text_input("Labourer name").strip()
            add = st.form_submit_button("Save labourer")
        if add:
            if name:
                save_laborer(name)
                st.success(f"Added {name}.")
            else:
                st.error("Enter a name.")
    laborers_df = query_df("SELECT id, name FROM laborers WHERE active=1 ORDER BY name")
    if laborers_df.empty:
        st.info("Add labourers before entering shifts.")
    else:
        laborer_map = {r.name: int(r.id) for r in laborers_df.itertuples()}
        with st.form("shift_form", clear_on_submit=True):
            selected = st.selectbox("Labourer", list(laborer_map))
            a, b = st.columns(2)
            start_date = a.date_input("Shift start date", value=date.today())
            start_time = a.time_input("Started at", value=time(8, 0))
            end_date = b.date_input("Shift end date", value=date.today())
            end_time = b.time_input("Ended at", value=time(17, 0))
            break_minutes = st.number_input("Break minutes", min_value=0, value=60, step=15)
            notes = st.text_input("Work / overtime notes (e.g. night cover removal)").strip() or None
            submit = st.form_submit_button("Record shift", type="primary")
        if submit:
            started = datetime.combine(start_date, start_time).isoformat(sep=" ")
            ended = datetime.combine(end_date, end_time).isoformat(sep=" ")
            try:
                paid, overtime, pay = record_labor_shift(laborer_map[selected], started, ended,
                                                         int(break_minutes), notes)
                st.success(f"Shift saved · {paid:g} paid hours · {overtime:g} overtime hours · KES {pay:,.2f}")
            except Exception as exc:
                st.error(f"Could not save shift: {exc}")
    st.subheader("Recorded shifts and pay")
    shifts = query_df(
        "SELECT l.name AS Labourer, s.started_at AS Started, s.ended_at AS Ended, "
        "s.break_minutes AS 'Break min', s.paid_hours AS 'Paid hours', "
        "s.overtime_hours AS 'Overtime hours', s.pay_kes AS 'Pay KES', s.notes AS Notes "
        "FROM labor_shifts s JOIN laborers l ON l.id=s.laborer_id ORDER BY s.started_at DESC LIMIT 500"
    )
    st.dataframe(shifts, use_container_width=True, hide_index=True)
    if not shifts.empty:
        st.metric("Total recorded labour pay", f"KES {shifts['Pay KES'].sum():,.2f}")


if portal == "Farmer portal":
    farmer_dashboard()
elif require_admin():
    if page == "Overview":
        overview()
    elif page == "Farmers":
        farmers()
    elif page == "Record delivery":
        delivery()
    elif page == "Processing / washing":
        processing()
    elif page == "Store / stock":
        store_stock()
    elif page == "Agrochemicals & loans":
        agrochemicals_loans()
    elif page == "Labour":
        labour()
    elif page == "Meetings & messages":
        meetings_messages()
    elif page == "Delivery history":
        history()
    elif page == "Manager corrections":
        manager_corrections()
    elif page == "Feedback inbox":
        feedback_inbox()
    else:
        st.subheader("Data & next steps")
        if st.button("Add fictional demo farmers and two years of sample deliveries"):
            count = seed_demo_data()
            st.success(f"Demo data is ready. Added {count:,} simulated deliveries. Names and weights are fictional.")
        demo_farmers = query_df("SELECT share_number AS 'Share number', name AS Farmer, "
                                "national_id AS 'Demo ID', phone_number AS 'Demo phone', "
                                "account_number AS 'Demo account', zone AS Zone FROM farmers "
                                "WHERE share_number LIKE 'DEMO-%' ORDER BY share_number")
        if not demo_farmers.empty:
            st.caption("Farmer portal demo: enter a Demo share number and its matching Demo phone. These phone values are deliberately non-routable, so they cannot receive SMS.")
            st.dataframe(demo_farmers,
                         use_container_width=True, hide_index=True)
        if st.button("Add example labour shifts"):
            count = seed_demo_labor()
            if count:
                st.success(f"Added {count} fictional labour shifts. Open Labour to see regular, overtime and overnight examples.")
            else:
                st.info("Fictional labour shifts have already been added; open Labour to view them.")
        st.markdown(
            "The prototype covers management operations and farmer self-service. "
            "The current SQLite database is local to this computer and is not ready for multiple office computers."
        )
        st.markdown("""
        **Remaining modules**
        - Transit location updates and public bidding / sale-income reporting.
        - Multi-office hosting with a central PostgreSQL database and separate staff accounts.
        - Forecasting after enough reliable season history exists.
        """)
        st.info("Delivery history can be filtered by dates and grouped by week, month or year. Existing records can be migrated after we know their file format.")
