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


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="EcoWatch Pune",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TABLE_NAME = "waste_reports"
BUCKET_NAME = "ecowatch-photos"

PAGES = [
    "Home",
    "Report Plastic Waste",
    "Pune Waste Map",
    "Admin Dashboard",
]


# ==================================================
# NAVIGATION STATE
# IMPORTANT: Synchronize BEFORE creating the radio.
# ==================================================

if "eco_page" not in st.session_state:
    st.session_state["eco_page"] = "Home"

if st.session_state["eco_page"] not in PAGES:
    st.session_state["eco_page"] = "Home"

# Keep the navigation widget synchronized with the
# destination selected by either homepage button.
st.session_state["eco_navigation"] = (
    st.session_state["eco_page"]
)


# ==================================================
# DESIGN
# ==================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #ffffff;
    }

    .block-container {
        max-width: 1200px;
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    [data-testid="stMetric"] {
        background: #f2f8f3;
        border: 1px solid #dceade;
        padding: 16px;
        border-radius: 12px;
    }

    .eco-hero {
        background: linear-gradient(
            135deg,
            #e7f6eb 0%,
            #ffffff 100%
        );
        padding: 35px 25px;
        border: 1px solid #d6eadb;
        border-radius: 20px;
        margin-bottom: 22px;
    }

    .eco-hero h1 {
        color: #176b3a;
        font-size: 42px;
        margin-bottom: 8px;
    }

    .eco-hero p {
        color: #40564a;
        font-size: 16px;
    }

    .eco-card {
        border: 1px solid #dce8df;
        border-radius: 16px;
        padding: 22px;
        min-height: 175px;
        background: #ffffff;
        margin-bottom: 12px;
    }

    .eco-card h3 {
        color: #176b3a;
    }

    .eco-footer {
        background: #f2f8f3;
        padding: 18px;
        border-radius: 12px;
        text-align: center;
        color: #40564a;
    }

    div.stButton > button[kind="primary"] {
        background-color: #19733f;
        border-color: #19733f;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==================================================
# SUPABASE CONNECTION
# ==================================================

@st.cache_resource
def get_supabase_client(url, key):
    return create_client(url, key)


def get_supabase():
    try:
        raw_url = str(
            st.secrets.get("SUPABASE_URL", "")
        ).strip().rstrip("/")

        key = str(
            st.secrets.get(
                "SUPABASE_SERVICE_ROLE_KEY",
                "",
            )
        ).strip()

        if raw_url.endswith("/rest/v1"):
            raw_url = raw_url[:-8].rstrip("/")

        parsed = urlparse(raw_url)

        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            st.error(
                "Invalid SUPABASE_URL. Use your project's "
                "base HTTPS URL without /rest/v1."
            )
            return None

        if not key:
            st.error(
                "SUPABASE_SERVICE_ROLE_KEY is missing "
                "from Streamlit Secrets."
            )
            return None

        return get_supabase_client(raw_url, key)

    except Exception as exc:
        st.error(
            "Could not configure Supabase: "
            + str(exc)
        )
        return None


supabase = get_supabase()


# ==================================================
# LOAD REPORTS
# ==================================================

def load_reports(show_error=True):
    if supabase is None:
        return []

    try:
        response = (
            supabase.table(TABLE_NAME)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    except Exception as exc:
        if show_error:
            st.error(
                "Could not load reports from the database. "
                + str(exc)
            )

        return []


# ==================================================
# UPLOAD PHOTO TO PRIVATE STORAGE
# ==================================================

def upload_photo(uploaded_file):
    if supabase is None:
        raise RuntimeError(
            "Supabase connection is unavailable."
        )

    allowed_types = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    mime_type = uploaded_file.type

    if mime_type not in allowed_types:
        raise ValueError(
            "Upload a JPG, PNG, or WEBP image."
        )

    extension = allowed_types[mime_type]

    if "." in uploaded_file.name:
        supplied_extension = (
            uploaded_file.name.rsplit(".", 1)[-1]
            .lower()
        )

        if supplied_extension not in {
            "jpg",
            "jpeg",
            "png",
            "webp",
        }:
            raise ValueError(
                "The uploaded file extension is invalid."
            )

    object_path = (
        datetime.now(timezone.utc).strftime("%Y/%m/")
        + str(uuid.uuid4())
        + "."
        + extension
    )

    supabase.storage.from_(BUCKET_NAME).upload(
        path=object_path,
        file=uploaded_file.getvalue(),
        file_options={
            "content-type": mime_type,
            "upsert": "false",
        },
    )

    return object_path


# ==================================================
# SAVE A REPORT
# ==================================================

def save_report(
    latitude,
    longitude,
    category,
    description,
    uploaded_photo,
):
    if supabase is None:
        raise RuntimeError(
            "Supabase connection is unavailable."
        )

    latitude = float(latitude)
    longitude = float(longitude)

    if not (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        raise ValueError(
            "The GPS coordinates are invalid."
        )

    photo_path = upload_photo(uploaded_photo)

    report = {
        "latitude": latitude,
        "longitude": longitude,
        "area_name": None,
        "waste_category": category,
        "description": description.strip(),
        "photo_path": photo_path,
        "status": "Pending",
    }

    try:
        (
            supabase.table(TABLE_NAME)
            .insert(report)
            .execute()
        )

    except Exception:
        try:
            supabase.storage.from_(
                BUCKET_NAME
            ).remove([photo_path])
        except Exception:
            pass

        raise


# ==================================================
# GENERATE A TEMPORARY PRIVATE PHOTO URL
# ==================================================

def get_photo_url(photo_path):
    if not photo_path or supabase is None:
        return None

    try:
        response = (
            supabase.storage.from_(BUCKET_NAME)
            .create_signed_url(photo_path, 300)
        )

        if isinstance(response, dict):
            return (
                response.get("signedURL")
                or response.get("signedUrl")
            )

        return None

    except Exception:
        return None


# ==================================================
# HOMEPAGE
# ==================================================

def show_home():
    st.markdown(
        """
        <div class="eco-hero">
            <div style="font-size:45px;">♻️</div>
            <h1>EcoWatch Pune</h1>
            <p>
                <b>Smart Plastic Waste Reporting and Monitoring</b>
            </p>
            <p>
                Report plastic pollution, explore GPS-mapped
                reports, and support cleaner public spaces.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            """
            <div class="eco-card">
                <div style="font-size:34px;">📸</div>
                <h3>Report Plastic Waste</h3>
                <p>
                    Upload a photograph and record the GPS
                    coordinates of plastic waste.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Report Plastic Waste →",
            key="home_report_button",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["eco_page"] = (
                "Report Plastic Waste"
            )
            st.rerun()

    with right:
        st.markdown(
            """
            <div class="eco-card">
                <div style="font-size:34px;">🗺️</div>
                <h3>Explore Pune Waste Map</h3>
                <p>
                    Explore reports using their saved GPS
                    coordinates and current report status.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Explore Pune Waste Map →",
            key="home_map_button",
            use_container_width=True,
        ):
            st.session_state["eco_page"] = (
                "Pune Waste Map"
            )
            st.rerun()

    st.divider()

    reports = load_reports()

    total = len(reports)

    pending = sum(
        1
        for row in reports
        if (row.get("status") or "Pending") == "Pending"
    )

    resolved = sum(
        1
        for row in reports
        if row.get("status") == "Resolved"
    )

    st.subheader("EcoWatch at a glance")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Reports", total)
    col2.metric("Pending Reports", pending)
    col3.metric("Resolved Reports", resolved)

    st.write("")

    st.markdown(
        """
        <div class="eco-footer">
            <b>Our mission</b><br>
            Using technology and community participation
            to support cleaner public places.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==================================================
# REPORT PLASTIC WASTE
# ==================================================

def show_report_form():
    st.title("📸 Report Plastic Waste")

    st.write(
        "Allow location access to record the actual "
        "GPS coordinates of the report."
    )

    try:
        location = streamlit_geolocation()
    except Exception as exc:
        location = None
        st.warning(
            "The GPS component could not start: "
            + str(exc)
        )

    latitude = None
    longitude = None

    if isinstance(location, dict):
        latitude = location.get("latitude")
        longitude = location.get("longitude")

    if latitude is not None and longitude is not None:
        st.session_state["eco_latitude"] = latitude
        st.session_state["eco_longitude"] = longitude

    latitude = st.session_state.get("eco_latitude")
    longitude = st.session_state.get("eco_longitude")

    if latitude is not None and longitude is not None:
        st.success("GPS coordinates received.")

        st.code(
            "Latitude: {}\nLongitude: {}".format(
                latitude,
                longitude,
            )
        )
    else:
        st.warning(
            "GPS coordinates are not available yet. "
            "Allow location access in your browser and "
            "wait for the coordinates to appear."
        )

    with st.form(
        "eco_report_form",
        clear_on_submit=False,
    ):
        category = st.selectbox(
            "Plastic waste category",
            [
                "Plastic bottles",
                "Plastic bags",
                "Food packaging",
                "Mixed plastic waste",
                "Other plastic waste",
            ],
        )

        description = st.text_area(
            "Description",
            max_chars=1000,
            placeholder=(
                "Describe the waste and any useful "
                "details about the public place."
            ),
        )

        uploaded_photo = st.file_uploader(
            "Upload a photograph",
            type=["jpg", "jpeg", "png", "webp"],
        )

        consent = st.checkbox(
            "I confirm this report is genuine and "
            "the photograph is appropriate to share."
        )

        submitted = st.form_submit_button(
            "Submit Report",
            type="primary",
            use_container_width=True,
        )

    if uploaded_photo is not None:
        st.image(
            uploaded_photo,
            caption="Photo preview",
            use_container_width=True,
        )

    if submitted:
        latitude = st.session_state.get("eco_latitude")
        longitude = st.session_state.get("eco_longitude")

        if latitude is None or longitude is None:
            st.error(
                "GPS is required. Allow location access "
                "and try submitting again."
            )

        elif uploaded_photo is None:
            st.error(
                "Please upload a photograph."
            )

        elif not description.strip():
            st.error(
                "Please enter a description."
            )

        elif not consent:
            st.error(
                "Please confirm that the report is genuine."
            )

        else:
            try:
                save_report(
                    latitude,
                    longitude,
                    category,
                    description,
                    uploaded_photo,
                )

                st.success(
                    "Report submitted successfully!"
                )

                st.session_state.pop(
                    "eco_latitude",
                    None,
                )
                st.session_state.pop(
                    "eco_longitude",
                    None,
                )

                st.session_state["eco_report_submitted"] = True

            except Exception as exc:
                st.error(
                    "Could not save the report. Check the "
                    "Supabase connection, database, and "
                    "private photo bucket. Details: "
                    + str(exc)
                )


# ==================================================
# PUNE WASTE MAP
# ==================================================

def show_map():
    st.title("🗺️ Pune Waste Map")

    st.write(
        "Markers represent saved report GPS coordinates. "
        "The map is centered on the available reports."
    )

    reports = load_reports()

    valid_rows = []

    for row in reports:
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])

            if (
                -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                item = dict(row)
                item["latitude"] = lat
                item["longitude"] = lon
                valid_rows.append(item)

        except (TypeError, ValueError, KeyError):
            continue

    if not valid_rows:
        st.info(
            "No GPS-tagged reports are available yet. "
            "Submit a report first to see a marker."
        )
        return

    center_lat = sum(
        row["latitude"] for row in valid_rows
    ) / len(valid_rows)

    center_lon = sum(
        row["longitude"] for row in valid_rows
    ) / len(valid_rows)

    map_object = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        control_scale=True,
    )

    Fullscreen(
        position="topright"
    ).add_to(map_object)

    marker_colors = {
        "Pending": "red",
        "In Progress": "blue",
        "Resolved": "green",
    }

    for row in valid_rows:
        status = str(
            row.get("status") or "Pending"
        )

        category = escape(
            str(
                row.get("waste_category")
                or "Plastic waste"
            )
        )

        description = escape(
            str(
                row.get("description")
                or "No description"
            )
        )

        created_at = escape(
            str(
                row.get("created_at")
                or "Date unavailable"
            )
        )

        popup_html = (
            "<b>{}</b><br>"
            "Status: {}<br>"
            "{}<br>"
            "<small>{}</small>"
        ).format(
            category,
            escape(status),
            description,
            created_at,
        )

        folium.Marker(
            location=[
                row["latitude"],
                row["longitude"],
            ],
            popup=folium.Popup(
                popup_html,
                max_width=300,
            ),
            tooltip=category,
            icon=folium.Icon(
                color=marker_colors.get(status, "red"),
                icon="info-sign",
            ),
        ).add_to(map_object)

    st_folium(
        map_object,
        height=560,
        use_container_width=True,
        returned_objects=[],
    )

    st.caption(
        "Red: Pending | Blue: In Progress | Green: Resolved"
    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

def show_admin():
    st.title("🔐 Admin Dashboard")

    admin_password = str(
        st.secrets.get("ADMIN_PASSWORD", "")
    )

    if not admin_password:
        st.error(
            "ADMIN_PASSWORD is missing from Streamlit Secrets."
        )
        return

    if not st.session_state.get(
        "eco_admin_authenticated",
        False,
    ):
        with st.form("eco_admin_login_form"):
            entered_password = st.text_input(
                "Admin password",
                type="password",
            )

            login_clicked = st.form_submit_button(
                "Log in",
                type="primary",
            )

        if login_clicked:
            if entered_password == admin_password:
                st.session_state[
                    "eco_admin_authenticated"
                ] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

        return

    if st.button("Log out", key="eco_admin_logout"):
        st.session_state[
            "eco_admin_authenticated"
        ] = False
        st.rerun()

    reports = load_reports()

    if not reports:
        st.info("No reports are available yet.")
        return

    df = pd.DataFrame(reports)

    total = len(df)

    if "status" in df.columns:
        pending = int(
            (df["status"] == "Pending").sum()
        )
        resolved = int(
            (df["status"] == "Resolved").sum()
        )
    else:
        pending = 0
        resolved = 0

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Reports", total)
    col2.metric("Pending", pending)
    col3.metric("Resolved", resolved)

    st.divider()
    st.subheader("Update report status")

    report_options = []

    for row in reports:
        report_id = str(row.get("id", ""))

        label = "{} | {} | {}".format(
            row.get("waste_category", "Waste"),
            row.get("status", "Pending"),
            str(row.get("created_at", ""))[:16],
        )

        report_options.append((report_id, label))

    if report_options:
        selected_id = st.selectbox(
            "Select report",
            [item[0] for item in report_options],
            format_func=lambda value: next(
                (
                    label
                    for key, label in report_options
                    if key == value
                ),
                value,
            ),
        )

        selected_report = next(
            (
                row
                for row in reports
                if str(row.get("id", "")) == selected_id
            ),
            {},
        )

        statuses = [
            "Pending",
            "In Progress",
            "Resolved",
        ]

        current_status = str(
            selected_report.get("status") or "Pending"
        )

        if current_status not in statuses:
            current_status = "Pending"

        chosen_status = st.selectbox(
            "New status",
            statuses,
            index=statuses.index(current_status),
        )

        if st.button(
            "Save status",
            type="primary",
            key="eco_save_status",
        ):
            try:
                (
                    supabase.table(TABLE_NAME)
                    .update({"status": chosen_status})
                    .eq("id", selected_id)
                    .execute()
                )

                st.success("Report status updated.")
                st.rerun()

            except Exception as exc:
                st.error(
                    "Could not update the report: "
                    + str(exc)
                )

        photo_path = selected_report.get("photo_path")

        if photo_path:
            signed_url = get_photo_url(photo_path)

            if signed_url:
                st.image(
                    signed_url,
                    caption="Selected report photograph",
                    use_container_width=True,
                )
            else:
                st.caption(
                    "Photo preview is currently unavailable."
                )

    st.divider()
    st.subheader("All reports")

    preferred_columns = [
        "id",
        "created_at",
        "waste_category",
        "description",
        "latitude",
        "longitude",
        "area_name",
        "status",
        "photo_path",
    ]

    visible_columns = [
        column
        for column in preferred_columns
        if column in df.columns
    ]

    st.dataframe(
        df[visible_columns],
        use_container_width=True,
        hide_index=True,
    )

    csv_data = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name="ecowatch_reports.csv",
        mime="text/csv",
        key="eco_download_csv",
    )


# ==================================================
# NAVIGATION MENU
# ==================================================

selected_page = st.radio(
    "Navigate EcoWatch",
    PAGES,
    horizontal=True,
    key="eco_navigation",
    label_visibility="collapsed",
)

# The navigation menu can also change the page.
st.session_state["eco_page"] = selected_page

st.divider()


# ==================================================
# DISPLAY SELECTED PAGE
# ==================================================

if selected_page == "Home":
    show_home()

elif selected_page == "Report Plastic Waste":
    show_report_form()

elif selected_page == "Pune Waste Map":
    show_map()

elif selected_page == "Admin Dashboard":
    show_admin()


# ==================================================
# FOOTER
# ==================================================

st.write("")

st.markdown(
    """
    <div class="eco-footer">
        <b>EcoWatch Pune</b><br>
        Plastic Waste Reporting and Monitoring<br>
        Community awareness through technology
    </div>
    """,
    unsafe_allow_html=True,
        )
