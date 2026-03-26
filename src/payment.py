"""
Razorpay Payment Integration for StructOptima.

Handles pay-per-report flow with graceful fallback when keys are not configured.
"""
import os
import hashlib
import hmac
import streamlit as st
from typing import Optional, Dict, Any

# Default price: ₹49 (4900 paise)
DEFAULT_PRICE_PAISE = int(os.environ.get("REPORT_PRICE_PAISE", "4900"))


def _get_razorpay_keys() -> tuple:
    """Get Razorpay API keys from Streamlit secrets or environment variables."""
    key_id = None
    key_secret = None
    
    # Try Streamlit secrets first
    try:
        key_id = st.secrets.get("RAZORPAY_KEY_ID", None)
        key_secret = st.secrets.get("RAZORPAY_KEY_SECRET", None)
    except Exception:
        pass
    
    # Fall back to environment variables
    if not key_id:
        key_id = os.environ.get("RAZORPAY_KEY_ID", None)
    if not key_secret:
        key_secret = os.environ.get("RAZORPAY_KEY_SECRET", None)
    
    return key_id, key_secret


def is_payment_enabled() -> bool:
    """Check if Razorpay keys are configured."""
    key_id, key_secret = _get_razorpay_keys()
    return bool(key_id and key_secret)


def get_price_display() -> str:
    """Return formatted price string."""
    rupees = DEFAULT_PRICE_PAISE / 100
    return f"₹{rupees:.0f}"


def create_razorpay_order(amount_paise: int = None, receipt: str = "report_order") -> Optional[Dict[str, Any]]:
    """
    Create a Razorpay order for payment.
    
    Returns order dict with 'id', 'amount', 'currency' or None if payment is not enabled.
    """
    if not is_payment_enabled():
        return None
    
    if amount_paise is None:
        amount_paise = DEFAULT_PRICE_PAISE
    
    try:
        import razorpay
        key_id, key_secret = _get_razorpay_keys()
        client = razorpay.Client(auth=(key_id, key_secret))
        
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "product": "StructOptima Structural Design Report",
                "type": "pay-per-report"
            }
        }
        
        order = client.order.create(data=order_data)
        return order
    except Exception as e:
        st.error(f"Payment service error: {e}")
        return None


def verify_payment(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verify Razorpay payment signature.
    
    Returns True if payment is verified, False otherwise.
    """
    if not is_payment_enabled():
        return True  # If payment not enabled, always pass
    
    try:
        key_id, key_secret = _get_razorpay_keys()
        
        # Verify signature: HMAC SHA256 of order_id|payment_id
        message = f"{order_id}|{payment_id}"
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(generated_signature, signature)
    except Exception:
        return False


def render_payment_button(pdf_data: bytes, filename: str = "Structural_Report.pdf") -> None:
    """
    Render payment gate or direct download based on payment configuration.
    
    If Razorpay is configured: shows payment info + download after conceptual payment
    If not configured: shows direct download (free mode)
    """
    if is_payment_enabled():
        price = get_price_display()
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0;">
            <h3 style="color: white; margin: 0 0 10px 0;">📄 Download Your Design Report</h3>
            <p style="color: rgba(255,255,255,0.9); margin: 0 0 15px 0;">
                Complete structural design package • IS 456 compliant • Professional PDF
            </p>
            <p style="color: white; font-size: 1.5em; font-weight: bold; margin: 0;">
                {price} per report
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.info(
            "💡 **How it works:** Click below to generate your report. "
            "Payment is processed securely via Razorpay (UPI, Cards, Net Banking)."
        )
        
        # For now, show a payment initiation button
        # Full Razorpay checkout requires JavaScript integration
        # In Streamlit, we use a simplified flow
        if 'payment_verified' not in st.session_state:
            st.session_state['payment_verified'] = False
        
        if not st.session_state['payment_verified']:
            if st.button("💳 Pay & Download Report", type="primary", key="pay_download_btn"):
                order = create_razorpay_order()
                if order:
                    st.session_state['current_order_id'] = order['id']
                    st.info(
                        f"🔗 **Order Created:** {order['id']}\n\n"
                        f"Complete payment at Razorpay checkout. "
                        f"Once payment is confirmed, your report will be available for download."
                    )
                    # In production, you'd redirect to Razorpay checkout
                    # For Streamlit, display payment ID field for manual verification
                    payment_id = st.text_input("Enter Payment ID (after completing payment):", key="payment_id_input")
                    signature = st.text_input("Enter Payment Signature:", key="payment_sig_input")
                    
                    if payment_id and signature:
                        if verify_payment(order['id'], payment_id, signature):
                            st.session_state['payment_verified'] = True
                            st.success("✅ Payment verified! Downloading report...")
                            st.rerun()
                        else:
                            st.error("❌ Payment verification failed. Please try again.")
        
        if st.session_state.get('payment_verified', False):
            st.download_button(
                label="📄 Download Your Report (PDF)",
                data=pdf_data,
                file_name=filename,
                mime="application/pdf",
                type="primary",
                key="paid_download_btn"
            )
    else:
        # Free mode — direct download
        st.download_button(
            label="📄 Download Complete Design Report (PDF)",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="primary",
            key="free_download_btn"
        )
