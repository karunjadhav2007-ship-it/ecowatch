import uuid
from datetime import datetime, timezone

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from supabase import create_client


# ================================================
# PAGE CONFIGURATION
# ================================================

st.set_page_config(
    page_title="EcoWatch",
    page_icon="♻️",
    layout="wide",
)

TABLE_NAME = "waste_reports"
BUCKET_NAME = "ecowatch-photos"


# ================================================
# SUPABASE CONNECTION
# ================================================

@st.cache_resource
def create_supabase_client(url, key):
    return create_client(url, key)


def get_supabase():
    try:
        url = str(
            st.secrets.get("SUPABASE_URL", "")
        ).strip().rstrip("/")

        key = str(
            st.secrets.get(
                "SUPABASE_SERVICE_ROLE_KEY", ""
            )
        ).strip()

        if url.endswith("/rest/v1"):
            url = url[:-8].rstrip("/")

        if not url.startswith("https://"):
            st.error(
                "Check SUPABASE_URL in Streamlit Secrets."
            )
            return None

        if not key:
            st.error(
                "SUPABASE_SERVICE_ROLE_KEY is missing."
            )
            return None

        return create_supabase_client(url, key)

    except Exception as exc:
        st.error(
            "Supabase connection configuration failed: "
            + str(exc)
        )
        return None


supabase = get_supabase()


# ================================================
# LOAD REPORTS
# ================================================

def load_reports():
    if supabase is None:
        return []

    try:
        result = (
            supabase.table(TABLE_NAME)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    except Exception as exc:
        st.error(
            "Unable to load reports: " + str(exc)
        )
        return []


# ================================================
# PHOTO UPLOAD
# ================================================

def upload_photo(photo):
    if supabase is None:
        raise RuntimeError(
            "Supabase connection is unavailable."
        )

    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    extension = extensions.get(photo.type)

    if extension is None:
        raise ValueError(
            "Upload a JPG, PNG, or WEBP photograph."
        )

    path = (
        datetime.now(timezone.utc).strftime("%Y/%m/")
        + str(uuid.uuid4())
        + "."
        + extension
    )

    supabase.storage.from_(BUCKET_NAME).upload(
        path=path,
        file=photo.getvalue(),
        file_options={
            "content-type": photo.type,
            "upsert": "false",
        },
    )

    return path


# ================================================
# SAVE REPORT
# ================================================

def save_report(
    latitude,
    longitude,
    category,
    description,
    photo,
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
        raise ValueError("Invalid GPS coordinates.")

    photo_path = upload_photo(photo)

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


# ================================================
# DASHBOARD
# ================================================

def show_dashboard():
    st.title("EcoWatch")
    st.subheader("Plastic Waste Monitoring System")

    st.write(
        "Welcome to EcoWatch. Report plastic waste "
        "and explore submitted reports using GPS "
        "coordinates."
    )

    reports = load_reports()

    total = len(reports)

    pending = sum(
        1 for row in reports
        if (row.get("status") or "Pending") == "Pending"
    )

    in_progress = sum(
        1 for row in reports
        if row.get("status") == "In Progress"
    )

    resolved = sum(
        1 for row in reports
        if row.get("status") == "Resolved"
    )

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    col1.metric("Total Reports", total)
    col2.metric("Pending Reports", pending)
    col3.metric("In Progress", in_progress)
    col4.metric("Resolved Reports", resolved)

    st.divider()

    st.subheader("About EcoWatch")

    st.write(
        """
        EcoWatch is a community-oriented plastic waste
        reporting and monitoring project.

        The system allows users to:
        - Submit photographs of plastic waste.
        - Record the actual GPS coordinates.
        - View submitted reports on a map.
        - Track report status through the admin dashboard.
        """
    )


# ================================================
# REPORT PLASTIC WASTE
# ================================================

def show_report_form():
    st.title("Report Plastic Waste")

    st.write(
        "Allow location access to record your "
        "current GPS coordinates."
    )

    try:
        location = streamlit_geolocation()
    except Exception as exc:
        location = None
        st.error(
            "GPS component could not start: " + str(exc)
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
        st.success("GPS location received.")

        st.write("Latitude:", latitude)
        st.write("Longitude:", longitude)
    else:
        st.warning(
            "GPS location is not available yet. "
            "Allow location permission and try again."
        )

    with st.form("report_form"):
        category = st.selectbox(
            "Plastic Waste Category",
            [
                "Plastic Bottles",
                "Plastic Bags",
                "Food Packaging",
                "Mixed Plastic Waste",
                "Other Plastic Waste",
            ],
        )

        description = st.text_area(
            "Description",
            placeholder="Describe the plastic waste...",
        )

        photo = st.file_uploader(
            "Upload Photograph",
            type=["jpg", "jpeg", "png", "webp"],
        )

        consent = st.checkbox(
            "I confirm that this report is genuine."
        )

        submitted = st.form_submit_button(
            "Submit Report",
            type="primary",
        )

    if photo is not None:
        st.image(
            photo,
            caption="Photograph Preview",
            use_container_width=True,
        )

    if submitted:
        latitude = st.session_state.get("eco_latitude")
        longitude = st.session_state.get("eco_longitude")

        if latitude is None or longitude is None:
            st.error(
                "GPS coordinates are required."
            )

        elif photo is None:
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
                    photo,
                )

                st.success(
                    "Report submitted successfully!"
                )

                st.session_state.pop(
                    "eco_latitude", None
                )
                st.session_state.pop(
                    "eco_longitude", None
                )

            except Exception as exc:
                st.error(
                    "Report could not be saved: "
                    + str(exc)
                )


# ================================================
# PUNE WASTE MAP
# ================================================

def show_waste_map():
    st.title("Pune Waste Map")

    st.write(
        "Reports are plotted using the GPS coordinates "
        "saved in the database."
    )

    reports = load_reports()
    valid_reports = []

    for row in reports:
        try:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])

            if (
                -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                item = dict(row)
                item["latitude"] = latitude
                item["longitude"] = longitude
                valid_reports.append(item)

        except (KeyError, TypeError, ValueError):
            continue

    if not valid_reports:
        st.info(
            "No GPS-tagged reports are available yet. "
            "Submit a report to see a map marker."
        )
        return

    center_lat = sum(
        row["latitude"] for row in valid_reports
    ) / len(valid_reports)

    center_lon = sum(
        row["longitude"] for row in valid_reports
    ) / len(valid_reports)

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

    for row in valid_reports:
        category = str(
            row.get("waste_category") or "Plastic Waste"
        )

        description = str(
            row.get("description") or "No description"
        )

        status = str(
            row.get("status") or "Pending"
        )

        popup = folium.Popup(
            (
                "<b>{}</b><br>"
                "Status: {}<br>"
                "{}"
            ).format(
                category,
                status,
                description,
            ),
            max_width=300,
        )

        folium.Marker(
            location=[
                row["latitude"],
                row["longitude"],
            ],
            popup=popup,
            tooltip=category,
            icon=folium.Icon(
                color=colors.get(status, "red"),
                icon="info-sign",
            ),
        ).add_to(map_object)

    st_folium(
        map_object,
        height=550,
        use_container_width=True,
        returned_objects=[],
    )

    st.caption(
        "Red: Pending | Blue: In Progress | Green: Resolved"
    )


# ================================================
# ADMIN DASHBOARD
# ================================================

def show_admin():
    st.title("Admin Dashboard")

    password = str(
        st.secrets.get("ADMIN_PASSWORD", "")
    )

    if not password:
        st.error(
            "ADMIN_PASSWORD is missing from Streamlit Secrets."
        )
        return

    if not st.session_state.get(
        "eco_admin_authenticated", False
    ):
        with st.form("admin_login"):
            entered_password = st.text_input(
                "Admin Password",
                type="password",
            )

            login = st.form_submit_button(
                "Login",
                type="primary",
            )

        if login:
            if entered_password == password:
                st.session_state[
                    "eco_admin_authenticated"
                ] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

        return

    if st.button("Logout"):
        st.session_state[
            "eco_admin_authenticated"
        ] = False
        st.rerun()

    reports = load_reports()

    if not reports:
        st.info("No reports are available.")
        return

    df = pd.DataFrame(reports)

    st.subheader("Submitted Reports")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Update Report Status")

    options = []

    for row in reports:
        report_id = str(row.get("id", ""))

        label = "{} | {}".format(
            row.get("waste_category", "Waste"),
            row.get("status", "Pending"),
        )

        options.append((report_id, label))

    selected_id = st.selectbox(
        "Select Report",
        [item[0] for item in options],
        format_func=lambda value: next(
            (
                label for key, label in options
                if key == value
            ),
            value,
        ),
    )

    selected_row = next(
        (
            row for row in reports
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
        selected_row.get("status") or "Pending"
    )

    if current_status not in statuses:
        current_status = "Pending"

    new_status = st.selectbox(
        "New Status",
        statuses,
        index=statuses.index(current_status),
    )

    if st.button("Save Status", type="primary"):
        try:
            (
                supabase.table(TABLE_NAME)
                .update({"status": new_status})
                .eq("id", selected_id)
                .execute()
            )

            st.success("Status updated successfully.")
            st.rerun()

        except Exception as exc:
            st.error(
                "Could not update status: " + str(exc)
            )

    st.divider()

    csv_data = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download Reports CSV",
        data=csv_data,
        file_name="ecowatch_reports.csv",
        mime="text/csv",
    )


# ================================================
# BASIC SIDEBAR NAVIGATION
# ================================================

st.sidebar.title("EcoWatch")
st.sidebar.caption("Plastic Waste Monitoring")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Report Plastic Waste",
        "Pune Waste Map",
        "Admin Dashboard",
    ],
    key="basic_navigation",
)

st.sidebar.divider()

st.sidebar.caption(
    "Plastic Free Public Places"
)


# ================================================
# PAGE ROUTING
# ================================================

if page == "Dashboard":
    show_dashboard()

elif page == "Report Plastic Waste":
    show_report_form()

elif page == "Pune Waste Map":
    show_waste_map()

elif page == "Admin Dashboard":
    show_admin()
