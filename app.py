import streamlit as st
import pandas as pd
import folium
import uuid

from datetime import datetime, timezone
from urllib.parse import urlparse
from supabase import create_client
from streamlit_folium import st_folium


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="EcoWatch | Pune",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ EcoWatch")
st.subheader("Plastic Free Public Places")
st.write(
    "Report plastic waste, view reported locations, "
    "and help make Pune cleaner."
)


# =========================================================
# 2. SUPABASE CONNECTION
# =========================================================

try:
    supabase_url = (
        st.secrets["SUPABASE_URL"]
        .strip()
        .rstrip("/")
    )

    # Normalize an accidentally included REST API suffix.
    if supabase_url.endswith("/rest/v1"):
        supabase_url = supabase_url[:-len("/rest/v1")]

    parsed_url = urlparse(supabase_url)

    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or parsed_url.path
        or parsed_url.query
        or parsed_url.fragment
    ):
        st.error(
            "Invalid SUPABASE_URL. Use the project URL "
            "ending in .supabase.co without /rest/v1."
        )
        st.stop()

    supabase_key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

    if not supabase_key:
        st.error("The Supabase key is missing.")
        st.stop()

    supabase = create_client(
        supabase_url,
        supabase_key
    )

except Exception as e:
    st.error(
        "EcoWatch could not initialize its database connection."
    )
    st.code(f"{type(e).__name__}: {e}")
    st.stop()


# =========================================================
# 3. VISIBLE NAVIGATION
# =========================================================

page = st.radio(
    "Choose an option",
    [
        "Report Plastic Waste",
        "Pune Waste Map",
        "Admin Dashboard"
    ],
    horizontal=True,
    label_visibility="collapsed",
    key="main_navigation"
)


# =========================================================
# 4. PUBLIC REPORTING FORM
# =========================================================

if page == "Report Plastic Waste":

    st.header("📸 Report Plastic Waste")

    st.info(
        "Help keep public places clean. Upload a photograph "
        "and enter the location of the plastic waste."
    )

    with st.form("report_form"):

        photo = st.file_uploader(
            "Photograph of plastic waste",
            type=["jpg", "jpeg", "png"]
        )

        category = st.selectbox(
            "Waste category",
            [
                "Plastic bottles",
                "Plastic bags",
                "Food packaging",
                "Plastic cups",
                "Mixed plastic",
                "Other"
            ]
        )

        area = st.text_input(
            "Area or locality in Pune"
        )

        description = st.text_area(
            "Describe the plastic waste"
        )

        st.subheader("📍 Waste Location")

        st.caption(
            "Enter the coordinates of the waste location. "
            "The default coordinates point to Pune city. "
            "These defaults do not represent your exact location."
        )

        latitude = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=18.5204,
            format="%.6f"
        )

        longitude = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=73.8567,
            format="%.6f"
        )

        submitted = st.form_submit_button(
            "📤 Submit Plastic Waste Report",
            use_container_width=True
        )

    if submitted:

        if photo is None:
            st.error("Please upload a photograph.")

        elif not area.strip():
            st.error("Please enter the area or locality.")

        else:

            try:
                report_id = str(uuid.uuid4())

                extension = (
                    photo.name.rsplit(".", 1)[-1].lower()
                )

                photo_path = f"{report_id}.{extension}"

                # Upload the photograph to the existing
                # private Supabase Storage bucket.
                supabase.storage.from_(
                    "ecowatch-photos"
                ).upload(
                    photo_path,
                    photo.getvalue(),
                    {
                        "content-type": photo.type
                    }
                )

                report = {
                    "id": report_id,
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "area_name": area.strip(),
                    "waste_category": category,
                    "description": description.strip(),
                    "photo_path": photo_path,
                    "status": "Pending",
                    "created_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }

                # Save the report in the existing database table.
                supabase.table(
                    "waste_reports"
                ).insert(
                    report
                ).execute()

                st.success(
                    "Your plastic waste report was submitted successfully!"
                )

                st.write("Report ID:", report_id)

                st.info(
                    "Your report is marked Pending until "
                    "an administrator reviews it."
                )

            except Exception as e:
                st.error(
                    "The report could not be submitted."
                )
                st.code(
                    f"{type(e).__name__}: {e}"
                )


# =========================================================
# 5. PUNE WASTE MAP
# =========================================================

elif page == "Pune Waste Map":

    st.header("🗺️ Pune Plastic Waste Map")

    try:
        result = (
            supabase.table("waste_reports")
            .select(
                "id, latitude, longitude, area_name, "
                "waste_category, description, status, created_at"
            )
            .execute()
        )

        reports = result.data or []

        map_view = folium.Map(
            location=[18.5204, 73.8567],
            zoom_start=12,
            control_scale=True
        )

        valid_reports = 0

        for report in reports:

            try:
                lat = float(report["latitude"])
                lon = float(report["longitude"])

                if not (
                    -90 <= lat <= 90
                    and -180 <= lon <= 180
                ):
                    continue

                area_name = (
                    report.get("area_name") or "Unknown area"
                )

                category = (
                    report.get("waste_category") or "Unknown"
                )

                status = (
                    report.get("status") or "Pending"
                )

                popup_html = (
                    f"<b>Area:</b> {area_name}<br>"
                    f"<b>Category:</b> {category}<br>"
                    f"<b>Status:</b> {status}"
                )

                if status == "Pending":
                    marker_color = "red"
                elif status == "Resolved":
                    marker_color = "green"
                else:
                    marker_color = "blue"

                folium.Marker(
                    location=[lat, lon],
                    tooltip=area_name,
                    popup=folium.Popup(
                        popup_html,
                        max_width=300
                    ),
                    icon=folium.Icon(
                        color=marker_color,
                        icon="info-sign"
                    )
                ).add_to(map_view)

                valid_reports += 1

            except (KeyError, TypeError, ValueError):
                continue

        st_folium(
            map_view,
            width=None,
            height=500,
            key="ecowatch_pune_map"
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Total reports retrieved",
                len(reports)
            )

        with col2:
            st.metric(
                "Locations displayed",
                valid_reports
            )

        if not reports:
            st.info(
                "No reports have been submitted yet. "
                "The map is centered on Pune."
            )

        elif valid_reports == 0:
            st.warning(
                "Reports were retrieved, but none had "
                "valid coordinates for map markers."
            )

    except Exception as e:
        st.error(
            "The map or database request failed."
        )
        st.code(
            f"{type(e).__name__}: {e}"
        )


# =========================================================
# 6. ADMIN DASHBOARD
# =========================================================

elif page == "Admin Dashboard":

    st.header("🔐 Administrator Dashboard")

    if not st.session_state.get("admin_ok", False):

        with st.form("admin_login"):

            password = st.text_input(
                "Admin password",
                type="password"
            )

            login = st.form_submit_button("Login")

        if login:

            correct_password = st.secrets.get(
                "ADMIN_PASSWORD", ""
            )

            if correct_password and password == correct_password:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error(
                    "Incorrect password or admin password "
                    "not configured."
                )

    if st.session_state.get("admin_ok", False):

        st.success("Administrator logged in.")

        if st.button("Refresh reports"):
            st.rerun()

        try:
            result = (
                supabase.table("waste_reports")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )

            reports = result.data or []

            st.metric(
                "Total plastic waste reports",
                len(reports)
            )

            if reports:

                df = pd.DataFrame(reports)

                st.subheader("All Reports")

                st.dataframe(
                    df,
                    use_container_width=True
                )

                st.subheader("Update Report Status")

                report_ids = [
                    report["id"]
                    for report in reports
                ]

                selected_id = st.selectbox(
                    "Select report",
                    report_ids
                )

                new_status = st.selectbox(
                    "Choose status",
                    [
                        "Pending",
                        "Reviewed",
                        "Resolved"
                    ]
                )

                if st.button("Save Status"):

                    (
                        supabase.table("waste_reports")
                        .update({"status": new_status})
                        .eq("id", selected_id)
                        .execute()
                    )

                    st.success(
                        "Report status updated successfully."
                    )

                    st.rerun()

                st.download_button(
                    label="Download Reports as CSV",
                    data=df.to_csv(
                        index=False
                    ).encode("utf-8"),
                    file_name="ecowatch_reports.csv",
                    mime="text/csv"
                )

            else:
                st.info(
                    "No reports have been submitted yet."
                )

        except Exception as e:
            st.error(
                "The administrator could not retrieve reports."
            )
            st.code(
                f"{type(e).__name__}: {e}"
            )

        if st.button("Logout"):
            st.session_state.admin_ok = False
            st.rerun()
