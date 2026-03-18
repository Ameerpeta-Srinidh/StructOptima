from typing import List, Dict
import random
import math

class SHMDashboard:
    """
    Visualization logic for Structural Health Monitoring (SHM) data.
    """
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.sensor_data = {}
        
    def generate_heatmap_data(self, elements: List[str], sim_type: str = "Strain") -> Dict[str, float]:
        """
        Simulates sensor readings mapped to element IDs for heatmap coloring.
        Returns {element_id: value (0.0-1.0 normalized)}
        """
        data = {}
        for elem in elements:
            # Simulate hot spots
            if "C1" in elem or "B5" in elem:
                val = random.uniform(0.7, 0.95) # High strain
            else:
                val = random.uniform(0.1, 0.4) # Low strain
            data[elem] = val
        return data

    def calculate_fft_spectrum(self, freq_hz: float) -> Dict[str, List[float]]:
        """
        Simulates Frequency Domain data (Power Spectral Density).
        """
        frequencies = [i*0.1 for i in range(100)] # 0 to 10 Hz
        amplitudes = []
        
        # Create peak around natural frequency
        for f in frequencies:
            # Gaussian peak
            amp = math.exp(-((f - freq_hz)**2) / (2 * (0.2**2)))
            # Add noise
            amp += random.uniform(0, 0.1)
            amplitudes.append(amp)
            
        return {"freq": frequencies, "amp": amplitudes}

    def get_damage_index(self, current_freq: float, baseline_freq: float) -> Dict[str, any]:
        """
        Calculates simple Damage Index (DI).
        DI = 1 - (f_curr / f_base)^2
        """
        ratio = (current_freq / baseline_freq)**2
        di = 1.0 - ratio
        
        status = "Green"
        if di > 0.4: status = "Red"
        elif di > 0.15: status = "Yellow"
        
        return {
            "value": round(di, 3),
            "status": status,
            "message": "Healthy" if status == "Green" else ("Critical Damage" if status == "Red" else "Minor Damage")
        }
