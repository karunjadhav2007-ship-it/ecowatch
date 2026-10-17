import io
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
import folium

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
# 2. PROFESSIONAL DESIGN
# =========================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f7faf7;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    .eco-header {
        background: #ffffff;
        border: 1px solid #e0e9e1;
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 18px;
    }

    .eco-title {
        color: #176b3a;
        font-size: 34px;
        font-weight: 750;
        margin: 0;
    }

    .eco-subtitle {
        color: #53675a;
        font-size: 15px;
        margin-top: 8px;
    }

    .eco-card {
        background: #ffffff;
        border: 1px solid #e0e9e1;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 14px;
    }

    .eco-small {
        color: #647468;
        font-size: 13px;
    }

    div.stButton > button[kind="primary"] {
        background-color: #198754;
        border-color: #198754;
        border-radius: 8px;
        min-height: 44px;
        font-weight: 600;
    }

    div.stButton > button {
        border-radius: 8px;
        min-height: 40px;
    }

    h1, h2, h3 {
        color: #183d28;
    }

    footer {
        visibility: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 3. SUPABASE CONNECTION
# =========================================================

try:
    supabase_url = (
        st.secrets["SUPABASE_URL"]
        .strip()
        .rstrip("/")
    )

    # Correct a URL accidentally saved with /rest/v1.
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
        st.error(
            "Invalid SUPABASE_URL. "
            "Use your project's base URL without /rest/v1."
        )
        st.stop()

    supabase_key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

    if not supabase_key.strip():
        st.error("Supabase service key is missing.")
        st.stop()

    supabase = create_client(
        supabase_url,
        supabase_key,
    )

except Exception:
    st.error(
        "EcoWatch could not connect to its configuration. "
        "Check the existing Streamlit Secrets settings."
    )
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


# =========================================================
# 5. DATABASE HELPERS
# =========================================================

def get_reports():
    """Retrieve reports from the existing Supabase table."""
    result = (
        supabase.table("waste_reports")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []


def upload_photo(uploaded_file):
    """Upload a report photo to the existing private bucket."""
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    allowed_extensions = {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }

    if extension not in allowed_extensions:
        raise ValueError(
            "Please upload a JPG, JPEG, PNG, or WEBP image."
        )

    photo_path = (
        f"{datetime.now(timezone.utc):%Y/%m}/"
        f"{uuid.uuid4().hex}.{extension}"
    )

    content_type = uploaded_file.type or "image/jpeg"

    supabase.storage.from_("ecowatch-photos").upload(
        photo_path,
        uploaded_file.getvalue(),
        {
            "content-type": content_type,
            "upsert": "false",
        },
    )

    return photo_path


def save_report(
    latitude,
    longitude,
    category,
    description,
    uploaded_file,
):
    """Save a report using GPS coordinates only."""

    photo_path = None

    if uploaded_file is not None:
        photo_path = upload_photo(uploaded_file)

    report_data = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "area_name": None,
        "waste_category": category,
        "description": description.strip(),
        "photo_path": photo_path,
        "status": "Pending",
    }

    supabase.table("waste_reports").insert(
        report_data
    ).execute()


# =========================================================
# 6. HEADER
# =========================================================

st.markdown(
    """
    <div class="eco-header">
        <div class="eco-title">🌿 EcoWatch Pune</div>
        <div class="eco-subtitle">
            A technology-enabled initiative for cleaner
            public places and responsible plastic waste reporting.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 7. VISIBLE NAVIGATION
# =========================================================

navigation_options = [
    "Home",
    "Report Plastic Waste",
    "Pune Waste Map",
    "Admin Dashboard",
]

current_page = st.session_state["eco_page"]

if current_page not in navigation_options:
    current_page = "Home"

selected_page = st.radio(
    "Navigation",
    navigation_options,
    index=navigation_options.index(current_page),
    horizontal=True,
    label_visibility="collapsed",
    key="eco_navigation",
)

st.session_state["eco_page"] = selected_page

st.divider()


# =========================================================
# 8. HOME PAGE
# =========================================================

if selected_page == "Home":

    st.markdown(
        """
        <div class="eco-card">
            <h1>Cleaner Pune Starts With Us</h1>

            <p>
                Help identify plastic waste in public places.
                Submit a report with a photograph and your
                actual GPS location so the reported spot
                can appear on the EcoWatch map.
            </p>

            <p class="eco-small">
                Community participation • GPS-based reporting
                • Environmental awareness
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "📍 Report Plastic Waste",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["eco_page"] = (
                "Report Plastic Waste"
            )
            st.rerun()

    with col2:
        if st.button(
            "🗺️ Explore Pune Waste Map",
            use_container_width=True,
        ):
            st.session_state["eco_page"] = (
                "Pune Waste Map"
            )
            st.rerun()

    st.markdown("### How EcoWatch Works")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="eco-card">
                <h3>01. Locate</h3>
                <p>
                    Allow location access to detect the
                    device's current GPS coordinates.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="eco-card">
                <h3>02. Report</h3>
                <p>
                    Upload a photograph and describe
                    the plastic waste you observe.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="eco-card">
                <h3>03. View</h3>
                <p>
                    View submitted reports on the map
                    and track their administrative status.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "EcoWatch supports environmental reporting. "
        "A submitted report does not automatically mean "
        "that the location has been cleaned."
    )


# =========================================================
# 9. REPORT PLASTIC WASTE
# =========================================================

elif selected_page == "Report Plastic Waste":

    st.header("Report Plastic Waste")

    st.write(
        "Detect your current location before submitting "
        "a report. There is no manual area or locality field."
    )

    st.markdown(
        """
        <div class="eco-card">
            <h3>📍 Current GPS Location</h3>
            <p>
                Tap the location control below and allow
                your browser to access your location.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    location = streamlit_geolocation()

    if (
        isinstance(location, dict)
        and location.get("latitude") is not None
        and location.get("longitude") is not None
    ):
        try:
            detected_lat = float(location["latitude"])
            detected_lon = float(location["longitude"])

            if (
                -90 <= detected_lat <= 90
                and -180 <= detected_lon <= 180
                and not (
                    detected_lat == 0
                    and detected_lon == 0
                )
            ):
                st.session_state["gps_latitude"] = (
                    detected_lat
                )
                st.session_state["gps_longitude"] = (
                    detected_lon
                )
                st.session_state["gps_ready"] = True

        except (ValueError, TypeError):
            st.session_state["gps_ready"] = False

    if st.session_state["gps_ready"]:
        latitude = st.session_state["gps_latitude"]
        longitude = st.session_state["gps_longitude"]

        st.success("GPS coordinates detected.")

        st.code(
            f"Latitude:  {latitude:.6f}\n"
            f"Longitude: {longitude:.6f}"
        )

        st.caption(
            "Check that this is your actual current location "
            "before submitting the report."
        )

    else:
        st.warning(
            "Location has not been detected yet. "
            "Allow location permission and use the location "
            "control above. You cannot submit a report "
            "until valid GPS coordinates are available."
        )

    st.divider()

    with st.form("eco_report_form"):

        st.subheader("Report Details")

        category = st.selectbox(
            "Type of plastic waste",
            [
                "Plastic Bottles",
                "Plastic Bags",
                "Food Wrappers",
                "Plastic Packaging",
                "Mixed Plastic Waste",
                "Other Plastic Waste",
            ],
        )

        description = st.text_area(
            "Description",
            placeholder=(
                "Describe the plastic waste and "
                "the public place where you observed it."
            ),
            max_chars=1000,
        )

        uploaded_file = st.file_uploader(
            "Upload a photograph",
            type=["jpg", "jpeg", "png", "webp"],
            help=(
                "Upload a clear photograph of the "
                "plastic waste. Do not include "
                "unnecessary personal information."
            ),
        )

        submitted = st.form_submit_button(
            "Submit Waste Report",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        if not st.session_state["gps_ready"]:
            st.error(
                "Report not submitted. Detect your "
                "current GPS location first."
            )

        elif uploaded_file is None:
            st.error(
                "Please upload a photograph before submitting."
            )

        elif not description.strip():
            st.error(
                "Please enter a short description."
            )

        else:
            try:
                with st.spinner(
                    "Saving your report securely..."
                ):
                    save_report(
                        latitude=st.session_state[
                            "gps_latitude"
                        ],
                        longitude=st.session_state[
                            "gps_longitude"
                        ],
                        category=category,
                        description=description,
                        uploaded_file=uploaded_file,
                    )

                st.success(
                    "Your plastic waste report was submitted "
                    "successfully!"
                )

                st.session_state["gps_ready"] = False
                st.session_state["gps_latitude"] = None
                st.session_state["gps_longitude"] = None

                st.info(
                    "Your report has been saved with GPS "
                    "coordinates and is awaiting review."
                )

            except Exception:
                st.error(
                    "The report could not be saved. "
                    "Please check your connection and try again. "
                    "If the problem continues, contact the "
                    "project administrator."
                )


# =========================================================
# 10. PUNE WASTE MAP
# =========================================================

elif selected_page == "Pune Waste Map":

    st.header("Pune Plastic Waste Map")

    st.write(
        "Markers are positioned using the GPS coordinates "
        "saved with each report, not a manually entered area."
    )

    try:
        reports = get_reports()

        valid_reports = []

        for report in reports:
            try:
                lat = float(report["latitude"])
                lon = float(report["longitude"])

                if (
                    -90 <= lat <= 90
                    and -180 <= lon <= 180
                    and not (lat == 0 and lon == 0)
                ):
                    report["_map_lat"] = lat
                    report["_map_lon"] = lon
                    valid_reports.append(report)

            except (KeyError, ValueError, TypeError):
                continue

        st.metric(
            "Reports with valid coordinates",
            len(valid_reports),
        )

        if valid_reports:
            center_lat = sum(
                r["_map_lat"] for r in valid_reports
            ) / len(valid_reports)

            center_lon = sum(
                r["_map_lon"] for r in valid_reports
            ) / len(valid_reports)

        else:
            center_lat = 18.5204
            center_lon = 73.8567

        waste_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            control_scale=True,
        )

        Fullscreen(
            position="topright",
            title="Full screen",
            title_cancel="Exit full screen",
        ).add_to(waste_map)

        for report in valid_reports:

            status = str(
                report.get("status") or "Pending"
            )

            if status.lower() == "resolved":
                marker_color = "green"
            elif status.lower() in {
                "in progress",
                "in-progress",
            }:
                marker_color = "orange"
            else:
                marker_color = "red"

            category_text = str(
                report.get("waste_category")
                or "Plastic Waste"
            )

            description_text = str(
                report.get("description") or ""
            )

            popup_html = f"""
            <div style="width:220px">
                <b>{category_text}</b><br>
                <b>Status:</b> {status}<br>
                <b>GPS:</b>
                {report["_map_lat"]:.6f},
                {report["_map_lon"]:.6f}<br>
                <p>{description_text[:250]}</p>
            </div>
            """

            folium.Marker(
                location=[
                    report["_map_lat"],
                    report["_map_lon"],
                ],
                tooltip=category_text,
                popup=folium.Popup(
                    popup_html,
                    max_width=280,
                ),
                icon=folium.Icon(
                    color=marker_color,
                    icon="info-sign",
                ),
            ).add_to(waste_map)

        st_folium(
            waste_map,
            use_container_width=True,
            height=550,
            returned_objects=[],
            key="eco_pune_map",
        )

        st.markdown(
            """
            **Map marker colours**

            - 🔴 Red — Pending or other status
            - 🟠 Orange — In Progress
            - 🟢 Green — Resolved
            """
        )

        if not valid_reports:
            st.info(
                "No reports with valid GPS coordinates "
                "are available to display yet."
            )

    except Exception:
        st.error(
            "The map could not load the saved reports. "
            "Please try again later."
        )


# =========================================================
# 11. ADMIN DASHBOARD
# =========================================================

elif selected_page == "Admin Dashboard":

    st.header("Admin Dashboard")

    st.write(
        "Authorized administrators can review reports, "
        "update their status, and export report data."
    )

    admin_password = st.text_input(
        "Administrator password",
        type="password",
    )

    try:
        configured_password = st.secrets[
            "ADMIN_PASSWORD"
        ]

    except Exception:
        configured_password = None

    if st.button(
        "Unlock Dashboard",
        type="primary",
    ):

        if (
            configured_password
            and admin_password
            and admin_password == configured_password
        ):
            st.session_state["eco_admin_authenticated"] = True
            st.success("Administrator access granted.")

        else:
            st.session_state["eco_admin_authenticated"] = False
            st.error("Incorrect administrator password.")

    if st.session_state.get(
        "eco_admin_authenticated",
        False,
    ):

        st.divider()

        try:
            reports = get_reports()

            if not reports:
                st.info("No reports have been submitted yet.")

            else:
                df = pd.DataFrame(reports)

                total_reports = len(df)

                pending_count = (
                    df["status"].fillna("Pending")
                    .str.lower()
          
