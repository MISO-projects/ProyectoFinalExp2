import requests
import numpy as np
import time
from typing import List, Tuple, Dict

class TrafficAPIManager:
    def calculate_traffic_matrix(self, coords: List[Tuple[float, float]]) -> Dict:
        print(f"Calculando matriz de tiempos con OSRM")
        
        start_time = time.perf_counter()
        matrix = self._osrm_matrix(coords)
        calc_time = time.perf_counter() - start_time
        
        return {
            'matrix': matrix,
            'provider_used': 'osrm',
            'has_realtime_traffic': False,
            'calculation_time_ms': int(calc_time * 1000),
            'matrix_size': f"{len(coords)}x{len(coords)}"
        }
    
    def _osrm_matrix(self, coords: List[Tuple[float, float]]) -> np.ndarray:
        coords_str = ';'.join([f"{lng},{lat}" for lat, lng in coords])
        
        url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}"
        params = {
            'sources': ';'.join([str(i) for i in range(len(coords))]),
            'destinations': ';'.join([str(i) for i in range(len(coords))])
        }
        
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        
        if data['code'] != 'Ok':
            raise Exception(f"OSRM API error: {data.get('message', 'Unknown error')}")
        
        clean_matrix = []
        for row in data['durations']:
            clean_row = [val if val is not None else 999999 for val in row]
            clean_matrix.append(clean_row)
        
        matrix = np.array(clean_matrix, dtype=np.int32)
        matrix = np.nan_to_num(matrix, nan=999999, posinf=999999, neginf=999999)
        
        return matrix
