import uuid
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlparse

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from supabase import create_client


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="EcoWatch Pune",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# 2. STYLING
# =========================================================
st.markdown(
    """
    <style>
    /* Consistent black theme with high-contrast readable text */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stHeader"], [data-testid="stToolbar"] {
        background: #000000 !important;
        color: #ffffff !important;
    }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 900px; }

    /* Make normal text, labels, captions and metrics clearly visible */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stMetricLabel"],
    .stApp [data-testid="stMetricValue"],
    .stApp [data-testid="stMetricDelta"] {
        color: #ffffff !important;
        opacity: 1 !important;
    }
    h1, h2, h3, h4, h5, h6,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        color: #ffffff !important;
        opacity: 1 !important;
    }

    /* Dark cards and header blend with the black background */
    .eco-header, .eco-card {
        background: #111111 !important;
        color: #ffffff !important;
        border: 1px solid #454545;
        border-left: 6px solid #18a558;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 18px;
    }
    .eco-title { color: #5be28b !important; font-size: clamp(26px, 5vw, 36px); font-weight: 800; margin: 0; }
    .eco-subtitle { color: #e0e0e0 !important; font-size: 15px; margin-top: 7px; }
    .eco-card * { color: #ffffff !important; opacity: 1 !important; }
    .eco-card h2, .eco-card h3, .eco-card b, .eco-card strong { color: #5be28b !important; }
    .eco-small { color: #eeeeee !important; font-size: 14px; }

    /* Captions and helper text stay bright against black */
    [data-testid="stCaptionContainer"], .stCaption, small {
        color: #e0e0e0 !important; opacity: 1 !important;
    }

    /* Inputs use dark backgrounds and white text */
    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    [data-baseweb="select"] > div, [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div {
        background: #171717 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border-color: #777777 !important;
        opacity: 1 !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #c4c4c4 !important; -webkit-text-fill-color: #c4c4c4 !important; opacity: 1 !important;
    }
    [data-baseweb="select"] *, [role="option"], [role="listbox"] {
        color: #ffffff !important;
        background-color: #171717 !important;
    }
    .stFileUploader, [data-testid="stFileUploader"] {
        color: #ffffff !important; opacity: 1 !important;
    }

    /* Buttons remain readable and prominent */
    div.stButton > button, div.stFormSubmitButton > button,
    [data-testid="stDownloadButton"] button {
        width: 100%; min-height: 60px; border-radius: 12px;
        font-size: 17px; font-weight: 700; white-space: normal;
        border: 1px solid #666666 !important;
        background: #1b1b1b !important; color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        opacity: 1 !important;
    }
    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"],
    [data-testid="stDownloadButton"] button {
        background: #08783e !important; border-color: #18a558 !important;
        color: #ffffff !important; -webkit-text-fill-color: #ffffff !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        border-color: #5be28b !important;
        filter: brightness(1.12);
    }

    /* Messages and data widgets remain legible */
    [data-testid="stAlert"] *, [data-testid="stMetric"] *,
    [data-testid="stDataFrame"] *, [data-testid="stTable"] * {
        opacity: 1 !important;
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        color: #ffffff !important;
    }
    [data-testid="stDataFrame"] *, [data-testid="stTable"] * {
        color: #ffffff !important;
    }

    /* App-like EcoWatch home screen */
    .eco-hero { display:flex; align-items:center; gap:14px; padding:18px 8px 20px; }
    .eco-logo { min-width:66px; height:66px; display:flex; align-items:center; justify-content:center;
        border:2px solid #20a75b; border-radius:18px; background:#06140c; font-size:31px; }
    .eco-hero-title { font-size:clamp(28px, 6vw, 42px); line-height:1.05; font-weight:850; color:#ffffff; }
    .eco-hero-title span { color:#43df7b; }
    .eco-hero-subtitle { margin-top:9px; font-size:11px; letter-spacing:1px; color:#d7e7dc; }
    .eco-banner { background:linear-gradient(135deg,#071b10,#10251a) !important; border:1px solid #1b633b !important; }
    .eco-banner h2 { color:#55e78a !important; }
    .eco-how { border-left-color:#25b963 !important; }
    .eco-muted { color:#c8d5cc !important; font-size:12px; }
    @media (max-width: 520px) {
        .block-container { padding-left:0.8rem; padding-right:0.8rem; }
        .eco-hero { gap:10px; padding-top:10px; }
        .eco-logo { min-width:54px; height:54px; font-size:25px; border-radius:15px; }
        .eco-hero-subtitle { font-size:9px; letter-spacing:.5px; }
        div.stButton > button, div.stFormSubmitButton > button { min-height:72px; font-size:14px; }
    }

    hr { border-color: #555555 !important; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 3. SUPABASE CONNECTION
# =========================================================
try:
    supabase_url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    if supabase_url.endswith("/rest/v1"):
        supabase_url = supabase_url[:-8]

    parsed_url = urlparse(supabase_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or parsed_url.path
        or parsed_url.query
        or parsed_url.fragment
    ):
        st.error("Invalid SUPABASE_URL. Use the project's base URL without /rest/v1.")
        st.stop()

    supabase_key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"].strip()
    if not supabase_key:
        st.error("Supabase service key is missing.")
        st.stop()

    supabase = create_client(supabase_url, supabase_key)
except Exception as exc:
    st.error("Could not initialize EcoWatch. Check your existing Streamlit Secrets.")
    st.caption(f"Configuration error: {exc}")
    st.stop()


# =========================================================
# 4. SESSION STATE
# =========================================================
if "eco_page" not in st.session_state:
    st.session_state["eco_page"] = "Home"
if "gps_latitude" not in st.session_state:
    st.session_state["gps_latitude"] = None
if "gps_longitude" not in st.session_state:
    st.session_state["gps_longitude"] = None
if "gps_ready" not in st.session_state:
    st.session_state["gps_ready"] = False
if "eco_admin_authenticated" not in st.session_state:
    st.session_state["eco_admin_authenticated"] = False


# =========================================================
# 5. DATABASE HELPERS
# =========================================================
def get_reports():
    result = (
        supabase.table("waste_reports")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def upload_photo(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    if extension not in allowed_extensions:
        raise ValueError("Please upload a JPG, JPEG, PNG, or WEBP image.")

    photo_path = f"{datetime.now(timezone.utc):%Y/%m}/{uuid.uuid4().hex}.{extension}"
    content_type = uploaded_file.type or "application/octet-stream"
    (
        supabase.storage.from_("ecowatch-photos").upload(
            photo_path,
            uploaded_file.getvalue(),
            {"content-type": content_type, "upsert": "false"},
        )
    )
    return photo_path


def save_report(latitude, longitude, category, description, uploaded_file):
    latitude = float(latitude)
    longitude = float(longitude)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Invalid GPS coordinates.")
    if latitude == 0 and longitude == 0:
        raise ValueError("GPS location is invalid.")

    photo_path = upload_photo(uploaded_file)
    report_data = {
        "latitude": latitude,
        "longitude": longitude,
        "area_name": None,
        "waste_category": category,
        "description": description.strip(),
        "photo_path": photo_path,
        "status": "Pending",
    }
    supabase.table("waste_reports").insert(report_data).execute()


# =========================================================
# 6. HEADER
# =========================================================
st.markdown(
    """
    <div class="eco-header">
        <div class="eco-title">🌿 EcoWatch Pune</div>
        <div class="eco-subtitle">
            Technology-enabled plastic waste reporting for cleaner public places.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 7. NAVIGATION
# =========================================================
nav_options = ["Home", "Report Plastic Waste", "Pune Waste Map", "Community Photos", "Admin Dashboard"]
if st.session_state.get("eco_page") not in nav_options:
    st.session_state["eco_page"] = "Home"

selected_page = st.session_state["eco_page"]

# On inner pages, show a clear Home button instead of hiding navigation
# behind the Streamlit sidebar/menu.
if selected_page != "Home":
    if st.button("🏠  BACK TO HOME", key="eco_back_home", use_container_width=True):
        st.session_state["eco_page"] = "Home"
        st.rerun()
    st.divider()


# =========================================================
# 8. HOME PAGE
# =========================================================
if selected_page == "Home":
    st.markdown(
        """
        <div class="eco-hero">
            <div class="eco-logo">🌿📍</div>
            <div><div class="eco-hero-title">EcoWatch <span>Pune</span></div>
            <div class="eco-hero-subtitle">CLEANER PLACES&nbsp; | &nbsp;GREENER TOMORROW</div></div>
        </div>
        <div class="eco-card eco-banner">
            <h2>Small actions make a big difference.</h2>
            <p>Help keep Pune clean. Report plastic waste, explore community reports, and see where action is needed.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### What would you like to do?")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("📸\nREPORT WASTE", key="home_report", type="primary", use_container_width=True):
            st.session_state["eco_page"] = "Report Plastic Waste"
            st.rerun()
    with c2:
        if st.button("🗺️\nLIVE WASTE MAP", key="home_map", use_container_width=True):
            st.session_state["eco_page"] = "Pune Waste Map"
            st.rerun()
    c3, c4 = st.columns(2, gap="medium")
    with c3:
        if st.button("🖼️\nCOMMUNITY PHOTOS", key="home_photos", use_container_width=True):
            st.session_state["eco_page"] = "Community Photos"
            st.rerun()
    with c4:
        if st.button("🔐\nADMIN DASHBOARD", key="home_admin", use_container_width=True):
            st.session_state["eco_page"] = "Admin Dashboard"
            st.rerun()

    try:
        home_reports = get_reports()
        total_reports = len(home_reports)
        pending_reports = sum(1 for r in home_reports if str(r.get("status") or "Pending").lower() == "pending")
        photo_reports = sum(1 for r in home_reports if r.get("photo_path"))
        st.markdown("### EcoWatch at a glance")
        m1, m2, m3 = st.columns(3)
        m1.metric("Reports", total_reports)
        m2.metric("Pending", pending_reports)
        m3.metric("Photos", photo_reports)
    except Exception:
        st.info("Report statistics will appear when the database is reachable.")

    st.markdown(
        """
        <div class="eco-card eco-how"><h3>🌱 Take action for a cleaner Pune</h3>
        <p>1. Allow GPS access. &nbsp; 2. Upload a clear photo. &nbsp; 3. Submit your report.</p>
        <p class="eco-muted">Photos submitted to EcoWatch may be visible to other visitors in Community Photos.</p></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("EcoWatch Pune • Plastic Free Public Places Campaign • AI & ML Department • AY 2026–27")


# =========================================================
# 9A. COMMUNITY PHOTO GALLERY
# =========================================================
elif selected_page == "Community Photos":
    st.header("🖼️ Community Photos")
    st.write("Photos shared through EcoWatch Pune reports. Newest reports appear first.")
    st.caption("Please upload only photos you are comfortable sharing publicly. Avoid faces, vehicle number plates, and private information.")
    try:
        photo_reports = [r for r in get_reports() if r.get("photo_path")]
        if not photo_reports:
            st.info("No community photos have been uploaded yet.")
        else:
            filter_options = ["All categories"] + sorted({str(r.get("waste_category") or "Other") for r in photo_reports})
            chosen_category = st.selectbox("Filter by waste type", filter_options, key="eco_gallery_filter")
            if chosen_category != "All categories":
                photo_reports = [r for r in photo_reports if str(r.get("waste_category") or "Other") == chosen_category]
            st.markdown(f"**{len(photo_reports)} photo report(s)**")
            for start in range(0, len(photo_reports), 2):
                cols = st.columns(2, gap="medium")
                for col, report in zip(cols, photo_reports[start:start + 2]):
                    with col:
                        try:
                            signed_result = supabase.storage.from_("ecowatch-photos").create_signed_url(report["photo_path"], 3600)
                            image_url = signed_result.get("signedURL") or signed_result.get("signedUrl") or signed_result.get("signed_url")
                            if image_url and image_url.startswith("/"):
                                image_url = supabase_url + "/storage/v1" + image_url
                            if not image_url:
                                st.warning("This photo link could not be created.")
                                continue
                            st.image(image_url, use_container_width=True)
                            st.markdown(f"**{escape(str(report.get('waste_category') or 'Plastic Waste'))}**")
                            st.caption(f"Status: {escape(str(report.get('status') or 'Pending'))}")
                            description_text = str(report.get("description") or "").strip()
                            if description_text:
                                st.write(description_text[:220])
                            created = str(report.get("created_at") or "")
                            if created:
                                st.caption(f"Reported: {created[:10]}")
                            if st.button("📍 Show this photo on map", key=f"eco_photo_map_{report.get('id', start)}", use_container_width=True):
                                st.session_state["eco_map_target_report_id"] = str(report.get("id", ""))
                                st.session_state["eco_page"] = "Pune Waste Map"
                                st.rerun()
                        except Exception as photo_exc:
                            st.warning("Could not load one of the uploaded photos.")
                            st.caption(f"Photo detail: {photo_exc}")
    except Exception as exc:
        st.error("Community photos could not be loaded.")
        st.caption(f"Technical detail: {exc}")


# =========================================================
# 9. REPORT FORM (GPS ONLY; NO MANUAL AREA FIELD)
# =========================================================
elif selected_page == "Report Plastic Waste":
    st.header("Report Plastic Waste")
    st.write("Detect your current location before submitting. There is no manual area or locality field.")
    st.markdown('<div class="eco-card"><h3>📍 Current GPS Location</h3><p>Use the location control below and allow your browser to access your location.</p></div>', unsafe_allow_html=True)

    try:
        location = streamlit_geolocation()
    except Exception as exc:
        location = None
        st.error("The location control could not start. Check browser location permission and reload the page.")
        st.caption(f"Location detail: {exc}")

    if isinstance(location, dict) and location.get("latitude") is not None and location.get("longitude") is not None:
        try:
            detected_lat = float(location["latitude"])
            detected_lon = float(location["longitude"])
            if (
                -90 <= detected_lat <= 90
                and -180 <= detected_lon <= 180
                and not (detected_lat == 0 and detected_lon == 0)
            ):
                st.session_state["gps_latitude"] = detected_lat
                st.session_state["gps_longitude"] = detected_lon
                st.session_state["gps_ready"] = True
        except (ValueError, TypeError):
            st.session_state["gps_ready"] = False

    if st.session_state["gps_ready"]:
        st.success("GPS coordinates detected.")
        st.code(
            f"Latitude:  {st.session_state['gps_latitude']:.6f}\n"
            f"Longitude: {st.session_state['gps_longitude']:.6f}"
        )
        st.caption("Confirm that these coordinates represent your actual current location.")
    else:
        st.warning("GPS location has not been detected. Allow location permission and use the location control above. Reports cannot be submitted without valid GPS coordinates.")

    st.divider()
    with st.form("eco_report_form"):
        st.subheader("Report Details")
        category = st.selectbox(
            "Type of plastic waste",
            ["Plastic Bottles", "Plastic Bags", "Food Wrappers", "Plastic Packaging", "Mixed Plastic Waste", "Other Plastic Waste"],
        )
        description = st.text_area(
            "Description",
            placeholder="Describe the plastic waste you observed.",
            max_chars=1000,
        )
        uploaded_file = st.file_uploader(
            "Upload a photograph",
            type=["jpg", "jpeg", "png", "webp"],
            help="Upload a clear photograph of the waste.",
        )
        submitted = st.form_submit_button("Submit Waste Report", type="primary", use_container_width=True)

    if submitted:
        if not st.session_state["gps_ready"]:
            st.error("Report not submitted. Detect your current GPS location first.")
        elif uploaded_file is None:
            st.error("Please upload a photograph.")
        elif not description.strip():
            st.error("Please enter a short description.")
        else:
            try:
                with st.spinner("Saving your report..."):
                    save_report(
                        latitude=st.session_state["gps_latitude"],
                        longitude=st.session_state["gps_longitude"],
                        category=category,
                        description=description,
                        uploaded_file=uploaded_file,
                    )
                st.success("Your plastic waste report was submitted!")
                st.session_state["gps_ready"] = False
                st.session_state["gps_latitude"] = None
                st.session_state["gps_longitude"] = None
                st.info("Your report has been saved with GPS coordinates and is awaiting review.")
            except Exception as exc:
                st.error("The report could not be saved. Check your connection and try again.")
                st.caption(f"Technical detail: {exc}")


# =========================================================
# 10. PUNE WASTE MAP
# =========================================================
elif selected_page == "Pune Waste Map":
    st.header("Pune Plastic Waste Map")
    st.write("Map markers use the latitude and longitude saved with each report, not a manually entered area.")

    try:
        reports = get_reports()
        valid_reports = []
        for report in reports:
            try:
                lat = float(report["latitude"])
                lon = float(report["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0):
                    report["_map_lat"] = lat
                    report["_map_lon"] = lon
                    valid_reports.append(report)
            except (KeyError, ValueError, TypeError):
                continue

        st.metric("Reports with valid coordinates", len(valid_reports))
        target_report_id = str(st.session_state.get("eco_map_target_report_id") or "")
        target_report = next((r for r in valid_reports if str(r.get("id", "")) == target_report_id), None)
        if target_report:
            center_lat, center_lon = target_report["_map_lat"], target_report["_map_lon"]
            map_zoom = 16
        elif valid_reports:
            center_lat = sum(report["_map_lat"] for report in valid_reports) / len(valid_reports)
            center_lon = sum(report["_map_lon"] for report in valid_reports) / len(valid_reports)
            map_zoom = 12
        else:
            center_lat, center_lon = 18.5204, 73.8567
            map_zoom = 12

        waste_map = folium.Map(location=[center_lat, center_lon], zoom_start=map_zoom, control_scale=True)
        Fullscreen(position="topright", title="Full screen", title_cancel="Exit full screen").add_to(waste_map)

        for report in valid_reports:
            status = str(report.get("status") or "Pending")
            status_lower = status.lower()
            if status_lower == "resolved":
                marker_color = "green"
            elif status_lower in {"in progress", "in-progress"}:
                marker_color = "orange"
            else:
                marker_color = "red"

            category_text = escape(str(report.get("waste_category") or "Plastic Waste"))
            description_text = escape(str(report.get("description") or "")[:250])
            photo_html = "<p><i>No photo attached to this report.</i></p>"
            photo_path = report.get("photo_path")
            if photo_path:
                try:
                    signed_result = supabase.storage.from_("ecowatch-photos").create_signed_url(photo_path, 3600)
                    image_url = signed_result.get("signedURL") or signed_result.get("signedUrl") or signed_result.get("signed_url")
                    if image_url and image_url.startswith("/"):
                        image_url = supabase_url + "/storage/v1" + image_url
                    if image_url:
                        safe_image_url = escape(str(image_url), quote=True)
                        photo_html = (
                            f"<img src='{safe_image_url}' alt='Community waste report photo' "
                            "style='width:100%;max-width:250px;height:auto;max-height:190px;object-fit:contain;"
                            "border-radius:8px;margin-top:8px;background:#111;' />"
                        )
                    else:
                        photo_html = "<p><i>Photo link is unavailable.</i></p>"
                except Exception:
                    photo_html = "<p><i>Photo could not be loaded.</i></p>"
            popup_html = (
                f"<div style='width:240px;font-family:Arial,sans-serif;color:#111;'>"
                f"<b>{category_text}</b><br>"
                f"<b>Status:</b> {escape(status)}<br>"
                f"<b>GPS:</b> {report['_map_lat']:.6f}, {report['_map_lon']:.6f}"
                f"{photo_html}<p>{description_text}</p></div>"
            )
            should_open = bool(target_report and str(report.get("id", "")) == target_report_id)
            folium.Marker(
                location=[report["_map_lat"], report["_map_lon"]],
                tooltip=f"{category_text} — tap to view photo and details",
                popup=folium.Popup(popup_html, max_width=300, show=should_open),
                icon=folium.Icon(color=marker_color, icon="info-sign"),
            ).add_to(waste_map)

        st_folium(waste_map, use_container_width=True, height=550, returned_objects=[], key="eco_pune_map")
        st.markdown("**Tap any map marker to view its uploaded community photo and report details.**")
        st.markdown("**Map marker colours:** 🔴 Red — Pending or other status · 🟠 Orange — In Progress · 🟢 Green — Resolved")
        if target_report:
            st.success("Showing the selected community photo's location. Tap its map marker to view the photo and report details.")
            if st.button("Clear selected photo", key="eco_clear_map_target"):
                st.session_state.pop("eco_map_target_report_id", None)
                st.rerun()
        if not valid_reports:
            st.info("No reports with valid GPS coordinates are available to display yet.")
    except Exception as exc:
        st.error("The map could not load the saved reports.")
        st.caption(f"Technical detail: {exc}")


# =========================================================
# 11. ADMIN DASHBOARD
# =========================================================
elif selected_page == "Admin Dashboard":
    st.header("Admin Dashboard")
    st.write("Review reports, update their status, and export data.")

    if not st.session_state.get("eco_admin_authenticated", False):
        with st.form("eco_admin_login"):
            admin_password = st.text_input("Administrator password", type="password")
            login_submitted = st.form_submit_button("Unlock Dashboard", type="primary")

        if login_submitted:
            configured_password = st.secrets.get("ADMIN_PASSWORD", "")
            if configured_password and admin_password and admin_password == configured_password:
                st.session_state["eco_admin_authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect administrator password.")

    if st.session_state.get("eco_admin_authenticated", False):
        if st.button("Lock Admin Dashboard"):
            st.session_state["eco_admin_authenticated"] = False
            st.rerun()

        st.divider()
        try:
            reports = get_reports()
            if not reports:
                st.info("No reports have been submitted yet.")
            else:
                df = pd.DataFrame(reports)
                pending_count = 0
                resolved_count = 0
                if "status" in df.columns:
                    statuses = df["status"].fillna("Pending").astype(str).str.lower()
                    pending_count = int((statuses == "pending").sum())
                    resolved_count = int((statuses == "resolved").sum())

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Reports", len(df))
                col2.metric("Pending", pending_count)
                col3.metric("Resolved", resolved_count)

                st.subheader("Submitted Reports")
                display_columns = [
                    column for column in [
                        "id", "created_at", "waste_category", "description",
                        "latitude", "longitude", "status",
                    ] if column in df.columns
                ]
                st.dataframe(df[display_columns], use_container_width=True, hide_index=True)

                st.subheader("Update Report Status")
                report_ids = [str(report["id"]) for report in reports if report.get("id") is not None]
                if report_ids:
                    selected_id = st.selectbox("Select report ID", report_ids)
                    new_status = st.selectbox("New status", ["Pending", "In Progress", "Resolved"])
                    if st.button("Save Status", type="primary"):
                        (
                            supabase.table("waste_reports")
                            .update({"status": new_status})
                            .eq("id", selected_id)
                            .execute()
                        )
                        st.success("Report status updated.")
                        st.rerun()

                st.divider()
                st.subheader("Delete Report")
                st.warning(
                    "Deleting a report is permanent. Select the correct report and confirm below."
                )

                delete_report_lookup = {
                    str(report["id"]): report
                    for report in reports
                    if report.get("id") is not None
                }
                delete_report_ids = list(delete_report_lookup.keys())

                if delete_report_ids:
                    delete_id = st.selectbox(
                        "Select a report to delete",
                        delete_report_ids,
                        format_func=lambda report_id: (
                            f"{delete_report_lookup[report_id].get('waste_category', 'Report')} | "
                            f"{delete_report_lookup[report_id].get('created_at', 'Unknown date')} | "
                            f"ID: {report_id[:8]}"
                        ),
                        key="eco_delete_report_id",
                    )
                    confirm_delete = st.checkbox(
                        "I confirm that I want to permanently delete this report.",
                        key="eco_confirm_delete",
                    )
                    if st.button(
                        "🗑️ Delete Selected Report",
                        type="primary",
                        key="eco_delete_report_button",
                    ):
                        if not confirm_delete:
                            st.error("Tick the confirmation checkbox before deleting.")
                        else:
                            try:
                                report_to_delete = delete_report_lookup[delete_id]
                                # Remove the database row first.
                                (
                                    supabase.table("waste_reports")
                                    .delete()
                                    .eq("id", delete_id)
                                    .execute()
                                )
                                st.success("Report deleted from the database.")

                                # Remove the associated photo from Supabase Storage if present.
                                photo_path = report_to_delete.get("photo_path")
                                if photo_path:
                                    try:
                                        supabase.storage.from_("ecowatch-photos").remove([photo_path])
                                        st.success("Associated photograph removed from storage.")
                                    except Exception as photo_exc:
                                        st.warning(
                                            "The report was deleted, but the stored photo could not be removed."
                                        )
                                        st.caption(f"Photo storage detail: {photo_exc}")

                                st.session_state["eco_confirm_delete"] = False
                                st.rerun()
                            except Exception as exc:
                                st.error("Could not delete the selected report.")
                                st.caption(f"Technical detail: {exc}")
                else:
                    st.info("There are no reports available to delete.")

                st.subheader("Export Reports")
                csv_data = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Download CSV",
                    data=csv_data,
                    file_name="ecowatch_reports.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        except Exception as exc:
            st.error("Could not load the admin dashboard.")
            st.caption(f"Technical detail: {exc}")


# =========================================================
# 12. FOOTER
# =========================================================
st.divider()
st.markdown(
    """
    <div style="text-align:center;color:#647468;font-size:13px">
        <b>EcoWatch Pune</b><br>
        Plastic Free Public Places Campaign<br>
        AI &amp; ML Department • Academic Year 2026–27
    </div>
    """,
    unsafe_allow_html=True,
)
