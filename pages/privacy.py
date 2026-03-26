import streamlit as st

st.set_page_config(page_title="Privacy Notice — StructOptima", layout="wide")

st.title("Privacy Notice")
st.caption("Last updated: March 2026")

st.markdown("""
## Data Collection

We collect only the information that Razorpay requires for payment processing — specifically 
your **name, email address, and transaction ID**. This data is handled entirely by Razorpay's 
secure payment infrastructure.

## Structural Data

We **do not store** any structural data, drawings, DXF files, or design outputs entered or 
generated during your session. All data exists only in your browser session and is cleared 
when you close the application.

## Third-Party Sharing

We **do not sell, share, or distribute** any personal data to third parties. The only external 
service that receives your information is Razorpay for the sole purpose of processing payments.

---

*For privacy-related inquiries, contact: srinidh.ameerpeta@gmail.com*
""")
