#!/usr/bin/env python3
"""
Claims Processing UI
Streamlit frontend for the Claims Processing REST API
"""

import os
import json
import base64
from urllib.parse import urlparse

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

    /* Policy Evaluation layout */
    .policy-section {
        margin-top: 1.25rem;
        padding: 1.25rem 1.5rem;
        border-radius: 0.75rem;
        border: 1px solid #E5E7EB;
        background-color: #FFFFFF;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    .policy-section-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 0.75rem;
    }

    .policy-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.5rem 1.75rem;
    }

    .policy-item-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6B7280;
        margin-bottom: 0.1rem;
    }

    .policy-item-value {
        font-size: 0.95rem;
        font-weight: 500;
        color: #111827;
    }

    .policy-summary {
        margin-top: 0.75rem;
        font-size: 0.9rem;
        color: #4B5563;
    }

    .claim-valid-wrapper {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .claim-valid-badge {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: 0.08em;
    }

    .claim-valid-badge--yes { color: #059669; }
    .claim-valid-badge--no { color: #DC2626; }

    .claim-valid-meta {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.5rem 1.5rem;
        font-size: 0.9rem;
    }

    .policy-notes {
        margin-top: 0.75rem;
        font-size: 0.9rem;
        color: #374151;
    }
</style>
""",
    unsafe_allow_html=True,
)


def get_api_url():
    if "api_url" not in st.session_state:
        api_url = os.environ.get("API_URL", "")
        st.session_state.api_url = api_url
    return st.session_state.api_url


def infer_upload_mode(api_url: str) -> str:
    """Infer upload mode from API URL.

    - APIM gateway (azure-api.net): use raw binary body ("apim-binary")
    - Container App / direct backend (azurecontainerapps.io or other): multipart
    """

    try:
        host = urlparse(api_url).netloc.lower()
    except Exception:
        host = ""

    if host.endswith("azure-api.net"):
        return "apim-binary"
    # Explicitly treat Container Apps as standard multipart; also default
    if host.endswith("azurecontainerapps.io"):
        return "multipart"
    return "multipart"


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

    Upload mode is inferred from the API URL hostname:
      - *.azure-api.net  → "apim-binary" (raw bytes for APIM policy)
      - *.azurecontainerapps.io or anything else → multipart upload
    """

    upload_mode = infer_upload_mode(api_url)

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

    # Policy Evaluation
    if "policy_evaluation" in data:
        st.subheader("📑 Policy Evaluation")
        pe = data.get("policy_evaluation") or {}

        # Matched Policy
        mp = pe.get("matched_policy") or {}
        if mp:
            score = mp.get("score")
            if isinstance(score, (int, float)):
                score_display = f"{score:.2f}"
            else:
                score_display = score or "N/A"

            matched_policy_html = f"""
            <div class="policy-section">
                <div class="policy-section-title">Matched Policy</div>
                <div class="policy-grid">
                    <div>
                        <div class="policy-item-label">Policy ID</div>
                        <div class="policy-item-value">{mp.get("id", "N/A")}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Title</div>
                        <div class="policy-item-value">{mp.get("title", "N/A")}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Match Score</div>
                        <div class="policy-item-value">{score_display}</div>
                    </div>
                </div>
            """

            summary = mp.get("summary")
            if summary:
                matched_policy_html += f'<div class="policy-summary">{summary}</div>'

            raw_ref = mp.get("raw_document_reference")
            if raw_ref:
                matched_policy_html += (
                    '<div class="policy-summary">'
                    '<span class="policy-item-label">Policy Document</span><br />'
                    f"{raw_ref}</div>"
                )

            matched_policy_html += "</div>"
            st.markdown(matched_policy_html, unsafe_allow_html=True)

        # Coverage Assessment
        ca = pe.get("coverage_assessment") or {}
        if ca:
            applicability_raw = (ca.get("coverage_applicability") or "").replace(
                "_", " "
            )
            applicability_label = (
                applicability_raw.title() if applicability_raw else "Unknown"
            )
            coverage_html = f"""
            <div class="policy-section">
                <div class="policy-section-title">Coverage Assessment</div>
                <div class="policy-grid">
                    <div>
                        <div class="policy-item-label">Coverage</div>
                        <div class="policy-item-value">{applicability_label}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Estimated Company Liability</div>
                        <div class="policy-item-value">${ca.get("estimated_company_liability_amount", 0):,}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Deductible Applies</div>
                        <div class="policy-item-value">{"Yes" if ca.get("deductible_applicable") else "No"}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Deductible Amount</div>
                        <div class="policy-item-value">${ca.get("deductible_amount", 0):,}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Limits May Be Exceeded</div>
                        <div class="policy-item-value">{"Yes" if ca.get("limits_may_be_exceeded") else "No"}</div>
                    </div>
                </div>
            """

            if ca.get("relevant_policy_sections"):
                coverage_html += (
                    '<div class="policy-summary">'
                    '<span class="policy-item-label">Relevant Sections</span><br />'
                    f"{ca.get('relevant_policy_sections')}</div>"
                )

            coverage_html += "</div>"
            st.markdown(coverage_html, unsafe_allow_html=True)

        # Liability Assessment
        la = pe.get("liability_assessment") or {}
        if la:
            at_fault_raw = (la.get("at_fault_party") or "").replace("_", " ")
            at_fault_label = at_fault_raw.title() if at_fault_raw else "Unknown"
            split = la.get("estimated_fault_split") or {}
            key_factors = la.get("key_factors")

            liability_html = f"""
            <div class="policy-section">
                <div class="policy-section-title">Liability Assessment</div>
                <div class="policy-grid">
                    <div>
                        <div class="policy-item-label">At-Fault Party</div>
                        <div class="policy-item-value">{at_fault_label}</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Fault Split</div>
                        <div class="policy-item-value">Policyholder {split.get("policyholder_percent", 0)}% / Third Party {split.get("third_party_percent", 0)}%</div>
                    </div>
                    <div>
                        <div class="policy-item-label">Key Factors Provided</div>
                        <div class="policy-item-value">{"Yes" if bool(key_factors) else "No"}</div>
                    </div>
                </div>
            """

            if key_factors:
                liability_html += (
                    '<div class="policy-summary">'
                    '<span class="policy-item-label">Key Factors</span><br />'
                    f"{key_factors}</div>"
                )

            liability_html += "</div>"
            st.markdown(liability_html, unsafe_allow_html=True)

        # Claim Validity
        cv = pe.get("claim_validity") or {}
        if cv:
            is_valid = bool(cv.get("is_claim_valid"))
            badge_class = (
                "claim-valid-badge claim-valid-badge--yes"
                if is_valid
                else "claim-valid-badge claim-valid-badge--no"
            )
            badge_text = "YES" if is_valid else "NO"

            confidence = cv.get("confidence", "N/A")
            if isinstance(confidence, str):
                confidence_display = confidence.title()
            else:
                confidence_display = confidence

            claim_valid_html = f"""
            <div class="policy-section">
                <div class="policy-section-title">Claim Validity</div>
                <div class="claim-valid-wrapper">
                    <div class="{badge_class}">{badge_text}</div>
                    <div class="claim-valid-meta">
                        <div>
                            <div class="policy-item-label">Primary Reasons</div>
                            <div class="policy-item-value">{cv.get("primary_reasons", "N/A")}</div>
                        </div>
                        <div>
                            <div class="policy-item-label">Assessment Confidence</div>
                            <div class="policy-item-value">{confidence_display}</div>
                        </div>
                    </div>
                </div>
            """

            notes = pe.get("notes")
            if notes:
                claim_valid_html += (
                    '<div class="policy-notes">'
                    '<span class="policy-item-label">Policy Evaluation Notes</span><br />'
                    f"{notes}</div>"
                )

            claim_valid_html += "</div>"
            st.markdown(claim_valid_html, unsafe_allow_html=True)

        elif pe.get("notes"):
            # If there is no structured claim_validity but notes exist, show them in a card
            notes_html = (
                '<div class="policy-section">'
                '<div class="policy-section-title">Policy Evaluation Notes</div>'
                f'<div class="policy-notes">{pe.get("notes")}</div>'
                "</div>"
            )
            st.markdown(notes_html, unsafe_allow_html=True)


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

        if not api_url:
            st.warning(
                "API URL is not set. Set it to enable health checks and claim processing."
            )
        else:
            upload_mode = infer_upload_mode(api_url)
            mode_label = (
                "APIM binary upload (raw body via APIM policy)"
                if upload_mode == "apim-binary"
                else "Multipart form-data upload (direct backend)"
            )
            st.markdown(f"**Upload mode:** {mode_label}")

        if st.button("🏥 Check Health", use_container_width=True, disabled=not api_url):
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
            disabled=(not uploaded) or (not st.session_state.get("api_url")),
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
