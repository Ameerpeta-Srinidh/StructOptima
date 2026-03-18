"""
Simple session-based authentication for Structural Design Platform.

This module provides basic authentication for the Streamlit app using
password hashing and session state management.

Features:
- Password hashing with hashlib (can be upgraded to bcrypt)
- Session-based authentication
- Support for environment-variable or file-based credentials
- Simple decorator for protecting routes/functions

Usage:
    from src.auth import authenticate_user, check_authentication, logout_user
    
    # In Streamlit app:
    if not check_authentication():
        authenticate_user()  # Shows login form
        st.stop()
    
    # User is authenticated, show main content
    st.write("Welcome!")
    
    # Logout button
    if st.button("Logout"):
        logout_user()
"""

import os
import hashlib
import secrets
from typing import Optional, Dict, Tuple
from functools import wraps
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


# Default admin credentials (should be changed in production)
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD_HASH = hashlib.sha256("structural2024".encode()).hexdigest()

# Environment variable names for credentials
ENV_USERNAME = "STRUCT_APP_USERNAME"
ENV_PASSWORD_HASH = "STRUCT_APP_PASSWORD_HASH"


def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256.
    
    For production, consider using bcrypt:
        pip install bcrypt
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.
    """
    return hash_password(password) == password_hash


def get_credentials() -> Tuple[str, str]:
    """
    Get credentials from environment variables or use defaults.
    
    Returns:
        Tuple of (username, password_hash)
    """
    username = os.environ.get(ENV_USERNAME, DEFAULT_USERNAME)
    password_hash = os.environ.get(ENV_PASSWORD_HASH, DEFAULT_PASSWORD_HASH)
    return username, password_hash


def check_authentication() -> bool:
    """
    Check if the current session is authenticated.
    
    Returns:
        True if authenticated, False otherwise.
    """
    if not STREAMLIT_AVAILABLE:
        return True  # No Streamlit, assume CLI usage
    
    return st.session_state.get("authenticated", False)


def authenticate_user() -> bool:
    """
    Display login form and authenticate user.
    
    Returns:
        True if authentication successful, False otherwise.
    """
    if not STREAMLIT_AVAILABLE:
        return True
    
    if check_authentication():
        return True
    
    st.markdown("### 🔐 Login Required")
    st.markdown("Please enter your credentials to access the Structural Design Platform.")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            expected_username, expected_password_hash = get_credentials()
            
            if username == expected_username and verify_password(password, expected_password_hash):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["session_token"] = secrets.token_hex(16)
                st.success("✅ Login successful!")
                st.rerun()
                return True
            else:
                st.error("❌ Invalid username or password.")
                return False
    
    return False


def logout_user() -> None:
    """
    Log out the current user and clear session state.
    """
    if not STREAMLIT_AVAILABLE:
        return
    
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.session_state.pop("session_token", None)
    st.rerun()


def get_current_user() -> Optional[str]:
    """
    Get the currently logged-in username.
    
    Returns:
        Username if authenticated, None otherwise.
    """
    if not STREAMLIT_AVAILABLE:
        return "cli_user"
    
    if check_authentication():
        return st.session_state.get("username")
    return None


def require_auth(func):
    """
    Decorator to require authentication for a function.
    
    Usage:
        @require_auth
        def protected_function():
            # This only runs if authenticated
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not check_authentication():
            if STREAMLIT_AVAILABLE:
                st.error("🔒 Authentication required. Please log in.")
                authenticate_user()
                st.stop()
            else:
                raise PermissionError("Authentication required")
        return func(*args, **kwargs)
    return wrapper


def show_login_sidebar() -> None:
    """
    Display a compact login/logout widget in the sidebar.
    """
    if not STREAMLIT_AVAILABLE:
        return
    
    with st.sidebar:
        if check_authentication():
            st.markdown(f"**Logged in as:** {get_current_user()}")
            if st.button("🚪 Logout", key="sidebar_logout"):
                logout_user()
        else:
            st.markdown("**Not logged in**")


# --- Password Management Utilities ---

def generate_password_hash(password: str) -> str:
    """
    Generate a password hash for setting up new credentials.
    
    Usage:
        python -c "from src.auth import generate_password_hash; print(generate_password_hash('mypassword'))"
    """
    return hash_password(password)


def setup_credentials_instructions() -> str:
    """
    Return instructions for setting up custom credentials.
    """
    return """
    To set custom credentials, set environment variables:
    
    Windows (PowerShell):
        $env:STRUCT_APP_USERNAME = "your_username"
        $env:STRUCT_APP_PASSWORD_HASH = "<hash_from_generate_password_hash>"
    
    Linux/Mac:
        export STRUCT_APP_USERNAME="your_username"
        export STRUCT_APP_PASSWORD_HASH="<hash_from_generate_password_hash>"
    
    To generate a password hash:
        python -c "from src.auth import generate_password_hash; print(generate_password_hash('your_password'))"
    """
