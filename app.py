import streamlit as st
import pandas as pd
import folium
import uuid
from datetime import datetime, timezone
from supabase import create_client
from streamlit_folium import st_folium

st.set_page_config(
    page_title="EcoWatch",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ EcoWatch")
st.subheader("Plastic Free Public Places")
st.write("Help make Pune cleaner by reporting plastic waste.")

try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    supabase = create_client(url, key)
except Exception:
    st.error("EcoWatch setup is incomplete. Hosting secrets are required.")
    st.stop()

page = st.sidebar.radio(
    "Navigate",
    ["Report Plastic Waste", "Pune Waste Map", "Admin Dashboard"]
)

if page == "Report Plastic Waste":
    st.header("Report Plastic Waste")

    with st.form("report_form"):
        photo = st.file_uploader(
            "Upload a photo of plastic waste",
            type=["jpg", "jpeg", "png"]
        )

        category = st.selectbox(
            "Waste category",
            ["Plastic bottles", "Plastic bags", "Food packaging",
             "Plastic cups", "Mixed plastic", "Other"]
        )

        area = st.text_input("Area or locality in Pune")
        description = st.text_area("Describe the problem")

        location_method = st.radio(
            "Choose location method",
            ["Enter coordinates manually", "Use current location"]
        )

        latitude = None
        longitude = None

        if location_method == "Enter coordinates manually":
            latitude = st.number_input(
                "Latitude", min_value=-90.0, max_value=90.0,
                value=18.5204, format="%.6f"
            )
            longitude = st.number_input(
                "Longitude", min_value=-180.0, max_value=180.0,
                value=73.8567, format="%.6f"
            )
        else:
            st.info(
                "Your browser's location permission will be needed. "
                "Use manual coordinates for now."
            )

        submitted = st.form_submit_button("Submit Report")

    if submitted:
        if photo is None:
            st.error("Please upload a photo.")
        elif not area.strip():
            st.error("Please enter the area or locality.")
        elif location_method == "Use current location":
            st.warning(
                "Current GPS reporting is not enabled yet. "
                "Please select manual coordinates."
            )
        else:
            try:
                report_id = str(uuid.uuid4())
                extension = photo.name.rsplit(".", 1)[-1].lower()
                photo_path = f"{report_id}.{extension}"

                supabase.storage.from_("ecowatch-photos").upload(
                    photo_path,
                    photo.getvalue(),
                    {"content-type": photo.type}
                )

                report = {
                    "id": report_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "area_name": area.strip(),
                    "waste_category": category,
                    "description": description.strip(),
                    "photo_path": photo_path,
                    "status": "Pending",
                    "created_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }

                supabase.table("waste_reports").insert(
                    report
                ).execute()

                st.success("Report submitted successfully!")
                st.info(f"Report ID: {report_id}")

            except Exception:
                st.error(
                    "Submission failed. Please check the app "
                    "configuration and try again."
                )

elif page == "Pune Waste Map":
    st.header("Pune Plastic Waste Map")

    try:
        result = (
            supabase.table("waste_reports")
            .select("*")
            .execute()
        )
        reports = result.data or []

        map_view = folium.Map(
            location=[18.5204, 73.8567],
            zoom_start=12
        )

        for report in reports:
            popup_text = (
                f"Area: {report.get('area_name', '')}<br>"
                f"Category: {report.get('waste_category', '')}<br>"
                f"Status: {report.get('status', 'Pending')}"
            )

            folium.Marker(
                location=[
                    report["latitude"],
                    report["longitude"]
                ],
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=report.get("area_name", "Waste report"),
                icon=folium.Icon(
                    color="red"
                    if report.get("status") == "Pending"
                    else "green"
                )
            ).add_to(map_view)

        st_folium(map_view, width=None, height=500)

        st.caption(f"Total reports: {len(reports)}")

        except Exception as e:
        st.error(f"Map error: {e}")

elif page == "Admin Dashboard":
    st.header("Administrator Login")

    if not st.session_state.get("admin_ok", False):
        with st.form("admin_login"):
            password = st.text_input(
                "Admin password", type="password"
            )
            login = st.form_submit_button("Login")

        if login:
            if password == st.secrets.get("ADMIN_PASSWORD", ""):
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    if st.session_state.get("admin_ok", False):
        st.success("Administrator authenticated.")

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
            st.metric("Total reports", len(reports))

            if reports:
                df = pd.DataFrame(reports)
                st.dataframe(df, use_container_width=True)

                st.subheader("Update report status")
                report_ids = [
                    r["id"] for r in reports
                ]

                selected_id = st.selectbox(
                    "Select report ID", report_ids
                )

                new_status = st.selectbox(
                    "New status",
                    ["Pending", "Reviewed", "Resolved"]
                )

                if st.button("Update status"):
                    supabase.table("waste_reports").update(
                        {"status": new_status}
                    ).eq("id", selected_id).execute()

                    st.success("Status updated.")
                    st.rerun()

                st.download_button(
                    "Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "ecowatch_reports.csv",
                    "text/csv"
                )

        except Exception:
            st.error("Could not load the reports.")

        if st.button("Logout"):
            st.session_state.admin_ok = False
            st.rerun()
