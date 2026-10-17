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


st.set_page_config(
    page_title="EcoWatch Pune",
    page_icon="♻️",
    layout="wide",
)

BUCKET_NAME = "ecowatch-photos"
TABLE_NAME = "waste_reports"


st.markdown(
    """
    <style>
    .stApp {
        background: #ffffff;
    }

    .block-container {
        max-width: 1200px;
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }

    .eco-hero {
        padding: 1.8rem;
        border-radius: 18px;
        background: #eef8f0;
        border: 1px solid #d7eadb;
    }

    .eco-title {
        color: #176b3a;
        font-size: 2.35rem;
        font-weight: 800;
        margin-bottom: 0.4rem;
    }

    .eco-subtitle {
        color: #42564a;
        font-size: 1.05rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SUPABASE CONNECTION
# --------------------------------------------------

def get_supabase():
    """Create a Supabase client using Streamlit Secrets."""

    try:
        raw_url = str(
            st.secrets.get("SUPABASE_URL", "")
        ).strip().rstrip("/")

        key = str(
            st.secrets.get(
                "SUPABASE_SERVICE_ROLE_KEY", ""
            )
        ).strip()

        if raw_url.endswith("/rest/v1"):
            raw_url = raw_url[:-8].rstrip("/")

        parsed = urlparse(raw_url)

        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
        ):
            st.error(
                "SUPABASE_URL must be the base HTTPS "
                "project URL, without /rest/v1."
            )
            return None

        if not key:
            st.error(
                "SUPABASE_SERVICE_ROLE_KEY is missing "
                "from Streamlit Secrets."
            )
            return None

        return create_client(raw_url, key)

    except Exception as exc:
        st.error(
            "Could not configure Supabase: " + str(exc)
        )
        return None


supabase = get_supabase()


# --------------------------------------------------
# LOAD REPORTS
# --------------------------------------------------

def load_reports():
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
        st.error(
            "Could not load reports from Supabase: "
            + str(exc)
        )
        return []


# --------------------------------------------------
# PHOTO UPLOAD
# --------------------------------------------------

def upload_photo(uploaded_file):
    if supabase is None:
        raise RuntimeError(
            "Supabase is not configured."
        )

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if uploaded_file.type not in allowed_types:
        raise ValueError(
            "Please upload a JPG, PNG, or WEBP image."
        )

    if "." in uploaded_file.name:
        extension = (
            uploaded_file.name.rsplit(".", 1)[-1].lower()
        )
    else:
        extension = "jpg"

    if extension not in {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }:
        extension = "jpg"

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
            "content-type": uploaded_file.type,
            "upsert": "false",
        },
    )

    return object_path


# --------------------------------------------------
# SAVE REPORT
# --------------------------------------------------

def save_report(
    latitude,
    longitude,
    category,
    description,
    photo,
):
    if supabase is None:
        raise RuntimeError(
            "Supabase is not configured."
        )

    photo_path = upload_photo(photo)

    payload = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "area_name": None,
        "waste_category": category,
        "description": description.strip(),
        "photo_path": photo_path,
        "status": "Pending",
    }

    try:
        (
            supabase.table(TABLE_NAME)
            .insert(payload)
            .execute()
        )

    except Exception:
        # Attempt to remove the uploaded photo if
        # saving the database record fails.
        try:
            supabase.storage.from_(
                BUCKET_NAME
            ).remove([photo_path])
        except Exception:
            pass

        raise


# --------------------------------------------------
# PRIVATE PHOTO PREVIEW
# --------------------------------------------------

def photo_preview_url(path):
    if not path or supabase is None:
        return None

    try:
        result = (
            supabase.storage.from_(BUCKET_NAME)
            .create_signed_url(path, 300)
        )

        if isinstance(result, dict):
            return (
                result.get("signedURL")
                or result.get("signedUrl")
            )

        return None

    except Exception:
        return None


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

def show_home():
    st.markdown(
        """
        <div class="eco-hero">
            <div class="eco-title">
                ♻️ EcoWatch Pune
            </div>
            <div class="eco-subtitle">
                A community-powered plastic waste
                reporting and monitoring platform.
            </div>
            <p>
                Report plastic waste at a real GPS
                location and help make public places
                cleaner.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    left, right = st.columns(2)

    with left:
        st.subheader("📸 Report plastic waste")

        st.write(
            "Share a photo and your current GPS "
            "coordinates to submit a report."
        )

        if st.button(
            "Report Plastic Waste",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["eco_page"] = (
                "Report Plastic Waste"
            )
            st.rerun()

    with right:
        st.subheader("🗺️ Explore the map")

        st.write(
            "Explore reports saved with their GPS "
            "coordinates in Pune and nearby areas."
        )

        if st.button(
            "Explore Pune Waste Map",
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
        if row.get("status", "Pending") == "Pending"
    )

    resolved = sum(
        1
        for row in reports
        if row.get("status") == "Resolved"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Reports submitted", total)
    col2.metric("Pending", pending)
    col3.metric("Resolved", resolved)

    st.caption(
        "EcoWatch is a student community project. "
        "Reports should be accurate and respectful."
    )


# --------------------------------------------------
# REPORT FORM
# --------------------------------------------------

def show_report_form():
    st.title("📸 Report Plastic Waste")

    st.write(
        "Allow location access so the report is "
        "placed on the map using your device's "
        "GPS coordinates."
    )

    location = streamlit_geolocation()

    latitude = None
    longitude = None

    if isinstance(location, dict):
        latitude = location.get("latitude")
        longitude = location.get("longitude")

    if latitude is not None and longitude is not None:
        st.success("GPS location received.")

        st.code(
            "Latitude: {}\nLongitude: {}".format(
                latitude,
                longitude,
            )
        )

        st.session_state["eco_latitude"] = latitude
        st.session_state["eco_longitude"] = longitude

    else:
        st.warning(
            "GPS location has not been received yet. "
            "Allow location permission in your browser "
            "and try again."
        )

    with st.form(
        "plastic_report_form",
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
                "Describe the plastic waste and nearby "
                "landmark. Do not type a manual map location."
            ),
        )

        photo = st.file_uploader(
            "Upload a photo",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp",
            ],
        )

        consent = st.checkbox(
            "I confirm this photo and report are "
            "genuine and appropriate to share."
        )

        submitted = st.form_submit_button(
            "Submit Report",
            type="primary",
            use_container_width=True,
        )

    if photo is not None:
        st.image(
            photo,
            caption="Photo preview",
            use_container_width=True,
        )

    if submitted:
        lat = st.session_state.get("eco_latitude")
        lon = st.session_state.get("eco_longitude")

        if lat is None or lon is None:
            st.error(
                "GPS coordinates are required. Allow "
                "location access, wait for coordinates, "
                "then submit again."
            )

        elif photo is None:
            st.error(
                "Please upload a photo before submitting."
            )

        elif not description.strip():
            st.error(
                "Please enter a short description."
            )

        elif not consent:
            st.error(
                "Please confirm that the report is genuine."
            )

        else:
            try:
                save_report(
                    lat,
                    lon,
                    category,
                    description,
                    photo,
                )

                st.success(
                    "Your report was submitted successfully. "
                    "Thank you for helping keep Pune clean!"
                )

                st.session_state.pop(
                    "eco_latitude",
                    None,
                )

                st.session_state.pop(
                    "eco_longitude",
                    None,
                )

            except Exception as exc:
                st.error(
                    "The report could not be saved. "
                    "Check the Supabase connection, private "
                    "bucket name, and database permissions. "
                    "Details: " + str(exc)
                )


# --------------------------------------------------
# PUNE WASTE MAP
# --------------------------------------------------

def show_map():
    st.title("🗺️ Pune Waste Map")

    st.write(
        "Map markers use the GPS coordinates saved "
        "when reports were submitted."
    )

    reports = load_reports()
    valid_rows = []

    for row in reports:
        try:
            lat = float(row.get("latitude"))
            lon = float(row.get("longitude"))

            if (
                -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                row_copy = dict(row)
                row_copy["latitude"] = lat
                row_copy["longitude"] = lon
                valid_rows.append(row_copy)

        except (TypeError, ValueError):
            continue

    if not valid_rows:
        st.info(
            "No GPS-tagged reports are available yet."
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

    Fullscreen(position="topright").add_to(map_object)

    colors = {
        "Pending": "red",
        "In Progress": "blue",
        "Resolved": "green",
    }

    for row in valid_rows:
        status = str(
            row.get("status") or "Pending"
        )

        category = escape(
            str(row.get("waste_category") or "Plastic waste")
        )

        description = escape(
            str(row.get("description") or "No description")
        )

        created = escape(
            str(row.get("created_at") or "Date unavailable")
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
            created,
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
                color=colors.get(status, "red"),
                icon="info-sign",
            ),
        ).add_to(map_object)

    st_folium(
        map_object,
        use_container_width=True,
        height=560,
        returned_objects=[],
    )

    st.caption(
        "Red = Pending · Blue = In Progress · "
        "Green = Resolved"
    )


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

def show_admin():
    st.title("🔐 Admin Dashboard")

    password = str(
        st.secrets.get("ADMIN_PASSWORD", "")
    )

    if not password:
        st.error(
            "ADMIN_PASSWORD is missing from "
            "Streamlit Secrets."
        )
        return

    if not st.session_state.get(
        "eco_admin_authenticated",
        False,
    ):
        with st.form("admin_login_form"):
            entered = st.text_input(
                "Admin password",
                type="password",
            )

            login_clicked = st.form_submit_button(
                "Log in",
                type="primary",
            )

        if login_clicked:
            if entered == password:
                st.session_state[
                    "eco_admin_authenticated"
                ] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

        return

    if st.button("Log out"):
        st.session_state[
            "eco_admin_authenticated"
        ] = False
        st.rerun()

    reports = load_reports()

    if not reports:
        st.info(
            "There are no reports to display yet."
        )
        return

    df = pd.DataFrame(reports)

    total = len(df)

    pending = int(
        (
            df.get(
                "status",
                pd.Series(dtype=str),
            ) == "Pending"
        ).sum()
    )

    resolved = int(
        (
            df.get(
                "status",
                pd.Series(dtype=str),
            ) == "Resolved"
        ).sum()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Total reports", total)
    col2.metric("Pending", pending)
    col3.metric("Resolved", resolved)

    st.subheader("Update report status")

    options = []

    for row in reports:
        report_id = str(row.get("id", ""))

        label = "{} | {} | {}".format(
            str(row.get("waste_category", "Waste")),
            str(row.get("status", "Pending")),
            str(row.get("created_at", ""))[:16],
        )

        options.append((report_id, label))

    if options:
        selected_id = st.selectbox(
            "Select a report",
            [item[0] for item in options],
            format_func=lambda value: next(
                (
                    label
                    for key, label in options
                    if key == value
                ),
                value,
            ),
        )

        selected_row = next(
            (
                row
                for row in reports
                if str(row.get("id", "")) == selected_id
            ),
            {},
        )

        current_status = str(
            selected_row.get("status") or "Pending"
        )

        status_choices = [
            "Pending",
            "In Progress",
            "Resolved",
        ]

        if current_status not in status_choices:
            current_status = "Pending"

        chosen_status = st.selectbox(
            "New status",
            status_choices,
            index=status_choices.index(current_status),
        )

        if st.button(
            "Save status",
            type="primary",
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
                    "Could not update status: "
                    + str(exc)
                )

        photo_path = selected_row.get("photo_path")

        if photo_path:
            signed_url = photo_preview_url(photo_path)

            if signed_url:
                st.image(
                    signed_url,
                    caption="Selected report photo",
                    use_container_width=True,
                )

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
        "Download reports as CSV",
        data=csv_data,
        file_name="ecowatch_reports.csv",
        mime="text/csv",
    )


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------
page_options = [
    "Home",
    "Report Plastic Waste",
    "Pune Waste Map",
    "Admin Dashboard",
]

if "eco_page" not in st.session_state:
    st.session_state["eco_page"] = "Home"

current_page = st.session_state.get(
    "eco_page",
    "Home",
)

if current_page not in page_options:
    current_page = "Home"

selected_page = st.radio(
    "Navigation",
    page_options,
    horizontal=True,
    index=page_options.index(current_page),
    label_visibility="collapsed",
    key="eco_navigation",
)

if selected_page != st.session_state.get("eco_page"):
    st.session_state["eco_page"] = selected_page

st.divider()

if selected_page == "Home":
    show_home()

elif selected_page == "Report Plastic Waste":
    show_report_form()

elif selected_page == "Pune Waste Map":
    show_map()

else:
    show_admin()

st.divider()

st.caption(
    "EcoWatch Pune · Plastic waste reporting prototype · "
    "Built for community awareness"
)
page_options = [
    "Home",
    "Report Plastic Waste",
    "Pune Waste Map",
    "Admin Dashboard",
]

   
