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


# =====================================================
# 1. PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="EcoWatch Pune",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =====================================================
# 2. PROFESSIONAL DESIGN
# =====================================================

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
        border: 1px solid #dce8df;
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
        border: 1px solid #dce8df;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 14px;
    }

    .eco-small {
        color: #647468;
        font-size: 13px;
    }

    div.stButton > button {
        border-radius: 8px;
        min-height: 42px;
    }

    div.stButton > button[kind="primary"] {
        background-color: #198754;
        border-color: #198754;
        color: white;
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


# =====================================================
# 3. SUPABASE CONNECTION
# =====================================================

try:
    supabase_url = (
        st.secrets["SUPABASE_URL"]
        .strip()
        .rstrip("/")
    )

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
            "Invalid SUPABASE_URL. Use your project's "
            "base URL without /rest/v1."
        )
        st.stop()

    supabase_key = st.secrets[
        "SUPABASE_SERVICE_ROLE_KEY"
    ].strip()

    if not supabase_key:
        st.error("Supabase service key is missing.")
        st.stop()

    supabase = create_client(
        supabase_url,
        supabase_key,
    )

except Exception as error:
    st.error(
        "Could not initialize EcoWatch. "
        "Check your existing Streamlit Secrets."
    )
    st.caption(f"Technical detail: {error}")
    st.stop()


# =====================================================
# 4. SESSION STATE
# =====================================================

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


# =====================================================
# 5. DATABASE FUNCTIONS
# =====================================================

def get_reports():
    result = (
        supabase
        .table("waste_reports")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []


def upload_photo(uploaded_file):
    extension = uploaded_file.name.rsplit(
        ".", 1
    )[-1].lower()

    allowed_extensions = {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }

    if extension not in allowed_extensions:
        raise ValueError(
            "Upload a JPG, JPEG, PNG, or WEBP image."
        )

    photo_path = (
        f"{datetime.now(timezone.utc):%Y/%m}/"
        f"{uuid.uuid4().hex}.{extension}"
    )

    content_type = (
        uploaded_file.type or "application/octet-stream"
    )

    (
        supabase.storage
        .from_("ecowatch-photos")
        .upload(
            photo_path,
            uploaded_file.getvalue(),
            {
                "content-type": content_type,
                "upsert": "false",
            },
        )
    )

    return photo_path


def save_report(
    latitude,
    longitude,
    category,
    description,
    uploaded_file,
):
    latitude = float(latitude)
    longitude = float(longitude)

    if not (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        raise ValueError("Invalid GPS coordinates.")

    if latitude == 0 and longitude == 0:
        raise ValueError("Invalid GPS location.")

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

    (
        supabase
        .table("waste_reports")
        .insert(report_data)
        .execute()
    )


# =====================================================
# 6. HEADER
# =====================================================

st.markdown(
    """
    <div class="eco-header">
        <div class="eco-title">🌿 EcoWatch Pune</div>
        <div class="eco-subtitle">
            Technology-enabled plastic waste reporting
            for cleaner public places.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =====================================================
# 7. NAVIGATION
# =====================================================

nav_options = [
    "Home",
    "Report Plastic Waste",
    "Pune Waste Map",
    "Admin Dashboard",
]

current_page = st.session_state.get(
    "eco_page",
    "Home",
)

if current_page not in nav_options:
    current_page = "Home"

selected_page = st.radio(
    "Navigation",
    nav_options,
    index=nav_options.index(current_page),
    horizontal=True,
    label_visibility="collapsed",
    key="eco_navigation",
)

st.session_state["eco_page"] = selected_page

st.divider()


# =====================================================
# 8. HOME PAGE
# =====================================================

if selected_page == "Home":

    st.markdown(
        """
        <div class="eco-card">
            <h1>Cleaner Pune Starts With Us</h1>
            <p>
                Help identify plastic waste in public places.
                Submit a photograph and your actual GPS
                location to report a waste hotspot.
            </p>
            <p class="eco-small">
                GPS-based reporting • Community participation
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
                    Allow browser location access to detect
                    your current GPS coordinates.
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
                    and follow their administrative status.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "A submitted report does not automatically mean "
        "that the location has been cleaned."
    )


# =====================================================
# 9. REPORT PLASTIC WASTE
# =====================================================

elif selected_page == "Report Plastic Waste":

    st.header("Report Plastic Waste")

    st.write(
        "Detect your current location before submitting. "
        "There is no manual area or locality field."
    )

    st.markdown(
        """
        <div class="eco-card">
            <h3>📍 Current GPS Location</h3>
            <p>
                Use the location control below and allow
                your browser to access your location.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Browser-based GPS component
    location = streamlit_geolocation()

    if (
        isinstance(location, dict)
        and location.get("latitude") is not None
        and location.get("longitude") is not None
    ):
        try:
            detected_lat = float(
                location["latitude"]
            )

            detected_lon = float(
                location["longitude"]
            )

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

        st.success("GPS coordinates detected.")

        st.code(
            f"Latitude:  "
            f"{st.session_state['gps_latitude']:.6f}\n"
            f"Longitude: "
            f"{st.session_state['gps_longitude']:.6f}"
        )

        st.caption(
            "Confirm that these coordinates represent "
            "your actual current location."
        )

    else:
        st.warning(
            "GPS location has not been detected. "
            "Allow location permission and use the location "
            "control above. Reports cannot be submitted "
            "without valid GPS coordinates."
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
                "Describe the plastic waste you observed."
            ),
            max_chars=1000,
        )

        uploaded_file = st.file_uploader(
            "Upload a photograph",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp",
            ],
            help="Upload a clear photograph of the waste.",
        )

        submitted = st.form_submit_button(
            "Submit Waste Report",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        if not st.session_state["gps_ready"]:

            st.error(
                "Report not submitted. Detect your current "
                "GPS location first."
            )

        elif uploaded_file is None:

            st.error(
                "Please upload a photograph."
            )

        elif not description.strip():

            st.error(
                "Please enter a short description."
            )

        else:

            try:
                with st.spinner("Saving your report..."):

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
                    "Your plastic waste report was submitted!"
                )

                st.session_state["gps_ready"] = False
                st.session_state["gps_latitude"] = None
                st.session_state["gps_longitude"] = None

                st.info(
                    "Your report has been saved with GPS "
                    "coordinates and is awaiting review."
                )

            except Exception as error:
                st.error(
                    "The report could not be saved. "
                    "Check your connection and try again."
                )
                st.caption(
                    f"Technical detail: {error}"
                )


# =====================================================
# 10. PUNE WASTE MAP
# =====================================================

elif selected_page == "Pune Waste Map":

    st.header("Pune Plastic Waste Map")

    st.write(
        "Map markers use the latitude and longitude "
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
                report["_map_lat"]
                for report in valid_reports
            ) / len(valid_reports)

            center_lon = sum(
                report["_map_lon"]
                for report in valid_reports
            ) / len(valid_reports)

        else:
            center_lat = 18.5204
            center_lon = 73.8567

        waste_map = folium.Map(
            location=[
                center_lat,
                center_lon,
            ],
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

            status_lower = status.lower()

            if status_lower == "resolved":
                marker_color = "green"

            elif status_lower in {
                "in progress",
                "in-progress",
            }:
                marker_color = "orange"

            else:
                marker_color = "red"

            category_text = escape(
                str(
                    report.get("waste_category")
                    or "Plastic Waste"
                )
            )

            description_text = escape(
                str(
                    report.get("description") or ""
                )[:250]
            )

            popup_html = (
                f"<div style='width:220px'>"
                f"<b>{category_text}</b><br>"
                f"<b>Status:</b> {escape(status)}<br>"
                f"<b>GPS:</b> "
                f"{report['_map_lat']:.6f}, "
                f"{report['_map_lon']:.6f}"
                f"<p>{description_text}</p>"
                f"</div>"
            )

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

    except Exception as error:
        st.error(
            "The map could not load the saved reports."
        )
        st.caption(
            f"Technical detail: {error}"
        )


# =====================================================
# 11. ADMIN DASHBOARD
# =====================================================

elif selected_page == "Admin Dashboard":

    st.header("Admin Dashboard")

    st.write(
        "Review reports, update their status, "
        "and export report data."
    )

    # Administrator login
    if not st.session_state.get(
        "eco_admin_authenticated",
        False,
    ):

        with st.form("eco_admin_login"):

            admin_password = st.text_input(
                "Administrator password",
                type="password",
            )

            login_submitted = st.form_submit_button(
                "Unlock Dashboard",
                type="primary",
            )

        if login_submitted:

            configured_password = st.secrets.get(
                "ADMIN_PASSWORD",
                "",
            )

            if (
                configured_password
                and admin_password
                and admin_password == configured_password
            ):
                st.session_state[
                    "eco_admin_authenticated"
                ] = True

                st.rerun()

            else:
                st.error(
                    "Incorrect administrator password."
                )

    # Protected dashboard
    if st.session_state.get(
        "eco_admin_authenticated",
        False,
 
