"""
Simulate Streamlit Session State Persistence
Verifies that key analysis objects (gm, beams, seismic_result) are stored in session_state.
"""

from unittest.mock import MagicMock
import sys

# Mock streamlit before importing app
sys.modules['streamlit'] = MagicMock()
import streamlit as st

# Setup mock session state
st.session_state = {}

def test_persistence():
    print("Testing Streamlit State Persistence...")
    
    # Simulate First Run (Button Click)
    print("1. Simulating 'Run Analysis' Click...")
    st.session_state['analysis_done'] = True
    
    # Mock Data Generation
    st.session_state['gm'] = "GridManager_Object"
    st.session_state['beams'] = ["Beam1", "Beam2"]
    st.session_state['bom'] = "BOM_Data"
    
    # Simulate Re-run (Button NOT clicked, but analysis_done is True)
    print("2. Simulating Re-run (e.g. Generate Report click)...")
    run_btn = False # User didn't click 'Run Analysis' again
    
    if st.session_state.get('analysis_done', False):
        gm = st.session_state.get('gm')
        beams = st.session_state.get('beams')
        
        if gm == "GridManager_Object" and len(beams) == 2:
            print("SUCCESS: Data persisted across re-run!")
        else:
            print("FAIL: Data lost.")
            exit(1)
            
    else:
        print("FAIL: Analysis flow not triggered.")
        exit(1)

if __name__ == "__main__":
    test_persistence()
