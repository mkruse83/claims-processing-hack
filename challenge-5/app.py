#!/usr/bin/env python3
"""
Claims Processing UI
Streamlit frontend for the Claims Processing REST API
"""

import os
import json
import base64
import httpx
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/workspaces/claims-processing-hack/.env")

# Page configuration
st.set_page_config(
    page_title="Claims Processing System",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1E3A8A; margin-bottom: 1rem; }
    .status-success { background-color: #D1FAE5; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #10B981; }
    .status-error { background-color: #FEE2E2; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #EF4444; }
</style>
""",
    unsafe_allow_html=True,
)


def get_api_url():
    if "api_url" not in st.session_state:
        api_url = os.environ.get("API_URL")
        if not api_url:
            st.error(
                "API_URL environment variable is not set. Please set API_URL before running the app."
            )
            st.stop()
        st.session_state.api_url = api_url
    return st.session_state.api_url


def check_health(api_url: str) -> dict:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/health")
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


def process_claim(api_url: str, file_content: bytes, filename: str) -> dict:
    """Call claims API, supporting both direct backend and APIM gateway.

    - Direct backend (FastAPI / Container App): expects multipart/form-data
    - APIM with binary-upload policy: expects raw binary body

    Select behavior via API_UPLOAD_MODE env var:
      - "apim-binary": send raw bytes suitable for APIM policy in challenge-4
      - any other value / unset: default multipart upload
    """

    upload_mode = os.environ.get("API_UPLOAD_MODE", "multipart").lower()

    try:
        with httpx.Client(timeout=120.0) as client:
            if upload_mode == "apim-binary":
                # APIM policy in challenge-4 expects raw binary body and
                # re-wraps it as multipart/form-data for the FastAPI backend.
                headers = {"Content-Type": "application/octet-stream"}
                response = client.post(
                    f"{api_url}/process-claim/upload",
                    content=file_content,
                    headers=headers,
                )
            else:
                # Direct call to FastAPI or Container App: send standard multipart upload
                files = {"file": (filename, file_content, "image/jpeg")}
                response = client.post(f"{api_url}/process-claim/upload", files=files)

            return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def display_results(data: dict):
    if not data:
        return
    # Document summary
    st.subheader("📄 Document Summary")
    metadata = data.get("metadata", {}) or {}
    cols = st.columns(3)
    cols[0].metric("Document Type", data.get("document_type", "N/A"))
    cols[1].metric("Confidence", str(data.get("confidence", "N/A")))
    cols[2].metric("Source File", metadata.get("source_file", "N/A"))
    if data.get("notes"):
        st.markdown(f"**Notes:** {data.get('notes')}")

    # Policyholder Information
    if "policyholder_information" in data:
        st.subheader("🙋 Policyholder Information")
        p = data.get("policyholder_information") or {}
        cols = st.columns(2)
        cols[0].markdown(f"**Name:** {p.get('name', 'N/A')}")
        cols[0].markdown(f"**Phone:** {p.get('phone', 'N/A')}")
        cols[0].markdown(f"**Email:** {p.get('email', 'N/A')}")
        cols[1].markdown(f"**Policy Number:** {p.get('policy_number', 'N/A')}")
        cols[1].markdown(f"**Claimant ID:** {p.get('claimant_id', 'N/A') or 'N/A'}")
        st.markdown(f"**Address:** {p.get('address', 'N/A')}")

    # Vehicle Information
    if "vehicle_information" in data:
        st.subheader("🚗 Vehicle Information")
        v = data.get("vehicle_information") or {}
        cols = st.columns(3)
        cols[0].markdown(
            f"**Year/Make/Model:** {v.get('year', 'N/A')} {v.get('make', '')} {v.get('model', '')}"
        )
        cols[1].markdown(f"**Color:** {v.get('color', 'N/A')}")
        cols[2].markdown(f"**VIN:** {v.get('vin', 'N/A')}")
        st.markdown(f"**License Plate:** {v.get('license_plate', 'N/A')}")

    # Accident Information
    if "accident_information" in data:
        st.subheader("📅 Accident Information")
        a = data.get("accident_information") or {}
        cols = st.columns(2)
        cols[0].markdown(f"**Date of Incident:** {a.get('date_of_incident', 'N/A')}")
        cols[0].markdown(f"**Time:** {a.get('time', 'N/A')}")
        cols[1].markdown(
            f"**US Territory:** {'Yes' if a.get('is_us_territory') else 'No'}"
        )
        st.markdown(f"**Location:** {a.get('location', 'N/A')}")

    # Description of Incident
    if "description_of_incident" in data:
        st.subheader("📝 Description of Incident")
        d = data.get("description_of_incident") or {}
        st.markdown(d.get("description", "N/A"))
        cols = st.columns(3)
        cols[0].metric(
            "Date Match",
            "Yes" if d.get("is_date_match") else "No",
        )
        cols[1].metric(
            "Location Match",
            "Yes" if d.get("is_location_match") else "No",
        )
        cols[2].metric(
            "Has Witness",
            "Yes" if d.get("has_witness") else "No",
        )
        cols = st.columns(3)
        cols[0].metric(
            "Own Fault",
            "Yes" if d.get("is_own_fault") else "No",
        )
        cols[1].metric(
            "Third Party Fault",
            "Yes" if d.get("is_third_party_fault") else "No",
        )
        cols[2].metric(
            "Vehicle Moving",
            "Yes" if d.get("vehicle_was_moving") else "No",
        )

    # Description of Damages
    if "description_of_damages" in data:
        st.subheader("🔧 Description of Damages")
        damages = data.get("description_of_damages") or []
        if damages:
            # If items are structured dicts, render nice cards; otherwise fall back to text list
            first_item = damages[0]
            if isinstance(first_item, dict):
                for d in damages:
                    part = d.get("part_name", "Unknown part")
                    desc = d.get("damage_description", "")
                    severity_raw = (d.get("severity") or "").lower()
                    action_raw = (d.get("repair_or_replace") or "").lower()

                    severity_color_map = {
                        "minor": "#10B981",  # green
                        "moderate": "#F59E0B",  # amber
                        "severe": "#EF4444",  # red
                    }
                    severity_color = severity_color_map.get(severity_raw, "#6B7280")

                    severity_label = (
                        severity_raw.capitalize() if severity_raw else "Unknown"
                    )
                    action_label = action_raw.capitalize() if action_raw else "N/A"

                    card_html = f"""
                    <div style="border-radius:0.5rem;border:1px solid #E5E7EB;padding:0.75rem 1rem;margin-bottom:0.75rem;background-color:#F9FAFB;">
                        <div style="font-weight:600;color:#111827;">{part}</div>
                        <div style="font-size:0.9rem;color:#4B5563;margin-top:0.25rem;">{desc}</div>
                        <div style="margin-top:0.5rem;display:flex;gap:0.5rem;flex-wrap:wrap;">
                            <span style="background-color:{severity_color}1A;color:{severity_color};padding:0.15rem 0.5rem;border-radius:999px;font-size:0.75rem;font-weight:500;">Severity: {severity_label}</span>
                            <span style="background-color:#DBEAFE;color:#1D4ED8;padding:0.15rem 0.5rem;border-radius:999px;font-size:0.75rem;font-weight:500;">Action: {action_label}</span>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                for item in damages:
                    st.markdown(f"- {item}")
        else:
            st.markdown("No detailed damages described.")

    # Witness Information
    if "witness_information" in data:
        st.subheader("👁️ Witness Information")
        w = data.get("witness_information") or {}
        cols = st.columns(2)
        cols[0].markdown(f"**Name:** {w.get('name', 'N/A')}")
        cols[0].markdown(f"**Phone:** {w.get('phone', 'N/A')}")
        cols[1].markdown(
            f"**Details Match Statement:** {('Yes' if w.get('is_matching') else 'No') if w.get('is_matching') is not None else 'Unknown'}"
        )

    # Police Report
    if "police_report" in data:
        st.subheader("🚓 Police Report")
        pr = data.get("police_report") or {}
        cols = st.columns(2)
        cols[0].markdown(f"**Report Number:** {pr.get('report_number', 'N/A')}")
        cols[1].markdown(f"**Police Department:** {pr.get('police_department', 'N/A')}")

    # Signature
    if "signature" in data:
        st.subheader("✍️ Signature")
        s = data.get("signature") or {}
        cols = st.columns(3)
        cols[0].metric(
            "Signature Present",
            "Yes" if s.get("is_present") else "No",
        )
        cols[1].markdown(f"**Printed Name:** {s.get('printed_name', 'N/A')}")
        cols[2].markdown(f"**Date:** {s.get('date', 'N/A')}")
        cols = st.columns(2)
        cols[0].metric(
            "Date Within a Week",
            (
                "Yes"
                if s.get("is_date_within_a_week") is True
                else "No"
                if s.get("is_date_within_a_week") is False
                else "Unknown"
            ),
        )
        cols[1].metric(
            "Name Matches Policyholder",
            (
                "Yes"
                if s.get("is_name_matching") is True
                else "No"
                if s.get("is_name_matching") is False
                else "Unknown"
            ),
        )


def main():
    st.markdown(
        '<p class="main-header">🚗 Insurance Claims Processing</p>',
        unsafe_allow_html=True,
    )
    st.markdown("Upload claim images to extract structured data using AI")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_url = st.text_input("API URL", value=get_api_url())
        st.session_state.api_url = api_url

        if st.button("🏥 Check Health", use_container_width=True):
            with st.spinner("Checking..."):
                result = check_health(api_url)
                if result.get("status") == "healthy":
                    st.success(f"✅ API Healthy\n\n{result.get('service', '')}")
                else:
                    st.error(f"❌ {result.get('error', 'Error')}")

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📤 Upload Claim")
        uploaded = st.file_uploader("Choose image", type=["jpg", "jpeg", "png"])
        process_btn = st.button(
            "🚀 Process Claim",
            type="primary",
            use_container_width=True,
            disabled=not uploaded,
        )

    with col2:
        if uploaded:
            st.image(uploaded, caption=uploaded.name, width=200)

    # Process
    if process_btn and uploaded:
        st.divider()
        with st.spinner("🔄 Processing... (30-60 seconds)"):
            result = process_claim(
                st.session_state.api_url, uploaded.getvalue(), uploaded.name
            )

        st.header("📋 Results")

        # Treat presence of an explicit error as failure; otherwise assume success
        if result.get("error") and not result.get("data"):
            st.markdown(
                f'<div class="status-error">❌ Error: {result.get("error", "Unknown")}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-success">✅ Claim processed successfully!</div>',
                unsafe_allow_html=True,
            )
            # Support both wrapped ({"data": {...}}) and direct JSON payloads
            payload = result.get("data", result)
            display_results(payload)
            with st.expander("🔍 Raw JSON"):
                st.json(result)


if __name__ == "__main__":
    main()
