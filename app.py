"""
HYBRID REAL-TIME EV CHARGING STATION FINDER
============================================

Features:
1. PRIMARY: Fetch live data from OpenChargeMap API on startup
2. FALLBACK: Use local JSON if API fails
3. CACHE: Store fetched data to avoid repeated API calls
4. REFRESH: Periodic API refresh (every 6 hours)
5. Real-time port availability simulation
6. Automatic data validation and cleaning

Version: 5.0 (Hybrid Live + Fallback)
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
import random
import time
import threading
from datetime import datetime, timedelta
from collections import deque
import requests
from dotenv import load_dotenv

from algorithms.greedy_station_selector import GreedyStationSelector
from algorithms.greedy_future_predictor import GreedyFuturePredictor


# Load environment variables from .env
load_dotenv()

# Get API key
API_KEY = os.getenv("OPENCHARGEMAP_API_KEY")

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-2025')

# Initialize algorithms
station_selector = GreedyStationSelector()
future_predictor = GreedyFuturePredictor()


# ============================================================
# OPENCHARGEMAP LIVE DATA FETCHER
# ============================================================

class OpenChargeMapLiveFetcher:
    """
    Fetches live charging station data from OpenChargeMap API
    with automatic fallback to local JSON
    """
    def __init__(self):
        self.api_url = "https://api.openchargemap.io/v3/poi/"
        self.api_key = os.getenv("OPENCHARGEMAP_API_KEY")
        self.cache_file = os.path.join('data', 'ocm_cache.json')
        self.fallback_file = os.path.join('data', 'kerala_charging_stations.json')
        # Kerala bounding box
        self.kerala_bounds = {
            'min_lat': 8.0,
            'max_lat': 12.8,
            'min_lon': 74.8,
            'max_lon': 77.5
        }
        
        self.kerala_districts = [
            "Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha",
            "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad",
            "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod"
        ]
        
        # District EV density estimates
        self.district_ev_density = {
            "Thiruvananthapuram": 120, "Ernakulam": 140, "Kozhikode": 100,
            "Thrissur": 70, "Kannur": 65, "Kollam": 60, "Palakkad": 50,
            "Kottayam": 55, "Alappuzha": 75, "Malappuram": 45,
            "Kasaragod": 40, "Pathanamthitta": 35, "Idukki": 30, "Wayanad": 25
        }
        
        self.last_fetch_time = None
        self.fetch_interval = timedelta(hours=6)
    
    def fetch_live_stations(self):
        """Fetch live stations from OpenChargeMap API"""
        print("\n🌐 Fetching live data from OpenChargeMap API...")
        
        params = {
            'countrycode': 'IN',
            'maxresults': 500,
            'compact': 'false',
            'verbose': 'false'
        }
        
        headers = {}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
            print(f"✓ Using API Key: {self.api_key[:10]}...")
        
        try:
            response = requests.get(self.api_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            print(f"✓ Fetched {len(data)} stations from India")
            
            kerala_stations = self._filter_kerala_stations(data)
            print(f"✓ Found {len(kerala_stations)} stations in Kerala")
            
            print("\n📍 First 5 Kerala Stations:")
            for i, station in enumerate(kerala_stations[:5], 1):
                print(f"  {i}. {station['name']}")
                print(f"     Coordinates: ({station['latitude']}, {station['longitude']})")
                print(f"     District: {station['district']}")
            
            self._save_to_cache(kerala_stations)
            self.last_fetch_time = datetime.now()
            
            return kerala_stations
        except requests.exceptions.Timeout:
            print("⚠ API request timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"⚠ API request failed: {e}")
            return None
        except json.JSONDecodeError:
            print("⚠ Invalid JSON response from API")
            return None
        except Exception as e:
            print(f"⚠ Unexpected error: {e}")
            return None
    
    def _filter_kerala_stations(self, stations_data):
        """Filter and convert stations for Kerala"""
        kerala_stations = []
        for idx, station in enumerate(stations_data, start=1):
            converted = self._convert_station(station, idx)
            if converted:
                kerala_stations.append(converted)
        return kerala_stations
    
    def _convert_station(self, ocm_station, station_id):
        """Convert OpenChargeMap format to project format"""
        address_info = ocm_station.get('AddressInfo', {})
        lat = address_info.get('Latitude')
        lon = address_info.get('Longitude')
        
        if not lat or not lon:
            return None
        if not self._is_in_kerala(lat, lon):
            return None
        
        district = self._determine_district(lat, lon, address_info)
        name = address_info.get('Title', f'Charging Station {station_id}')
        if not name or name.strip() == '':
            name = f'Station {station_id}'
        
        fast, medium, slow = self._assign_ports(ocm_station)
        ev_density = self.district_ev_density.get(district, 50)
        charging_demand = self._determine_demand(ev_density)
        
        station = {
            "id": station_id,
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "district": district,
            "fastPorts": fast,
            "mediumPorts": medium,
            "slowPorts": slow,
            "availableFastPorts": fast,
            "availableMediumPorts": medium,
            "availableSlowPorts": slow,
            "ev_density": ev_density,
            "charging_demand": charging_demand,
            "source": "OpenChargeMap-Live",
            "ocm_id": ocm_station.get('ID'),
            "operator": ocm_station.get('OperatorInfo', {}).get('Title', 'Unknown'),
            "address": address_info.get('AddressLine1', ''),
            "town": address_info.get('Town', ''),
            "last_verified": ocm_station.get('DateLastVerified', 'Unknown')
        }
        return station
    
    def _is_in_kerala(self, lat, lon):
        return (self.kerala_bounds['min_lat'] <= lat <= self.kerala_bounds['max_lat'] and
                self.kerala_bounds['min_lon'] <= lon <= self.kerala_bounds['max_lon'])
    
    def _determine_district(self, lat, lon, address_info):
        if address_info:
            title = address_info.get('Title', '').lower()
            address_line = address_info.get('AddressLine1', '').lower()
            town = address_info.get('Town', '').lower()
            for district in self.kerala_districts:
                if (district.lower() in title or
                    district.lower() in address_line or
                    district.lower() in town):
                    return district
        if lat >= 11.8:   return "Kasaragod"
        elif lat >= 11.5: return "Kannur"
        elif lat >= 11.0: return "Kozhikode"
        elif lat >= 10.5: return "Thrissur"
        elif lat >= 10.0: return "Ernakulam"
        elif lat >= 9.5:  return "Kottayam"
        elif lat >= 9.0:  return "Alappuzha"
        else:             return "Thiruvananthapuram"
    
    def _assign_ports(self, station_data):
        connections = station_data.get('Connections', [])
        fast_ports = medium_ports = slow_ports = 0
        if not connections:
            return 1, 2, 1
        for conn in connections:
            power_kw = conn.get('PowerKW', 0)
            level = conn.get('Level', {})
            level_title = level.get('Title', '').lower() if level else ''
            if power_kw >= 50 or 'rapid' in level_title or 'dc' in level_title:
                fast_ports += 1
            elif power_kw >= 20 or 'fast' in level_title:
                medium_ports += 1
            else:
                slow_ports += 1
        if fast_ports == 0 and medium_ports == 0 and slow_ports == 0:
            medium_ports = 1
        return fast_ports, medium_ports, slow_ports
    
    def _determine_demand(self, ev_density):
        if ev_density >= 100:  return "High"
        elif ev_density >= 60: return "Medium"
        else:                  return "Low"
    
    def _save_to_cache(self, stations):
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'stations': stations,
                'count': len(stations)
            }
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Cached {len(stations)} stations to {self.cache_file}")
        except Exception as e:
            print(f"⚠ Could not save cache: {e}")
    
    def load_from_cache(self):
        if not os.path.exists(self.cache_file):
            print("⚠ No cache file found")
            return None
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            age = datetime.now() - cache_time
            if age < self.fetch_interval:
                print(f"✓ Using cached data (age: {age.total_seconds()/3600:.1f} hours)")
                self.last_fetch_time = cache_time
                return cache_data['stations']
            else:
                print(f"⚠ Cache expired (age: {age.total_seconds()/3600:.1f} hours)")
                return None
        except Exception as e:
            print(f"⚠ Could not load cache: {e}")
            return None
    
    def load_from_fallback(self):
        if not os.path.exists(self.fallback_file):
            print(f"✗ Fallback file not found: {self.fallback_file}")
            return []
        try:
            with open(self.fallback_file, 'r', encoding='utf-8') as f:
                stations = json.load(f)
            for station in stations:
                if 'source' not in station:
                    station['source'] = 'Local-Fallback'
            print(f"✓ Loaded {len(stations)} stations from fallback file")
            return stations
        except Exception as e:
            print(f"✗ Could not load fallback: {e}")
            return []
    
    def get_stations(self):
        print("\n🔄 Attempting to fetch live data from OpenChargeMap...")
        live_stations = self.fetch_live_stations()
        if live_stations:
            print(f"✅ Using LIVE data: {len(live_stations)} stations")
            return live_stations
        print("⚠ Live fetch failed, trying cache...")
        cached_stations = self.load_from_cache()
        if cached_stations:
            print(f"✅ Using CACHED data: {len(cached_stations)} stations")
            return cached_stations
        print("⚠ Cache invalid/missing, using fallback...")
        fallback_stations = self.load_from_fallback()
        print(f"✅ Using FALLBACK data: {len(fallback_stations)} stations")
        return fallback_stations
    
    def should_refresh(self):
        if self.last_fetch_time is None:
            return True
        return datetime.now() - self.last_fetch_time > self.fetch_interval


# ============================================================
# ENHANCED REAL-TIME SYSTEM WITH LIVE DATA
# ============================================================

class HybridRealTimeSystem:
    def __init__(self):
        self.stations = []
        self.lock = threading.Lock()
        self.running = False
        self.last_update = datetime.now()
        self.min_interval = 15
        self.max_interval = 45
        self.update_history = deque(maxlen=100)
        self.total_updates = 0
        self.fetcher = OpenChargeMapLiveFetcher()
        self.refresh_running = False
    
    def load_stations(self):
        print("\n" + "="*70)
        print("LOADING CHARGING STATION DATA - LIVE MODE")
        print("="*70)
        stations_data = self.fetcher.get_stations()
        if not stations_data:
            print("✗ No stations loaded!")
            return
        with self.lock:
            for station in stations_data:
                if 'total_fastPorts' not in station:
                    station['total_fastPorts'] = station.get('fastPorts', 0)
                    station['total_mediumPorts'] = station.get('mediumPorts', 0)
                    station['total_slowPorts'] = station.get('slowPorts', 0)
                availability_factor = self._get_availability_factor()
                station['availableFastPorts'] = max(0, int(station['total_fastPorts'] * availability_factor))
                station['availableMediumPorts'] = max(0, int(station['total_mediumPorts'] * availability_factor))
                station['availableSlowPorts'] = max(0, int(station['total_slowPorts'] * availability_factor))
                station['last_updated'] = datetime.now().isoformat()
                station['utilization_rate'] = 0.0
            self.stations = stations_data
            print(f"✓ Loaded {len(self.stations)} stations")
            sources = {}
            for s in self.stations:
                source = s.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            print("\n📊 Data Sources:")
            for source, count in sources.items():
                prefix = "🔴" if "Fallback" in source else "🟢"
                print(f"  {prefix} {source}: {count} stations")
            print("="*70 + "\n")
    
    def _get_availability_factor(self):
        current_hour = datetime.now().hour
        if 8 <= current_hour < 10 or 18 <= current_hour < 20:
            return random.uniform(0.60, 0.80)
        elif 10 <= current_hour < 18:
            return random.uniform(0.70, 0.85)
        elif current_hour >= 23 or current_hour < 6:
            return random.uniform(0.90, 1.0)
        else:
            return random.uniform(0.80, 0.95)
    
    def _get_arrival_probability(self):
        current_hour = datetime.now().hour
        if 8 <= current_hour < 10 or 18 <= current_hour < 20: return 0.40
        elif 10 <= current_hour < 18:                          return 0.30
        elif current_hour >= 23 or current_hour < 6:           return 0.10
        else:                                                   return 0.25
    
    def _get_departure_probability(self):
        return 0.35
    
    def simulate_charging_behavior(self):
        with self.lock:
            arrival_prob = self._get_arrival_probability()
            departure_prob = self._get_departure_probability()
            for station in self.stations:
                demand = station.get('charging_demand', 'Medium')
                if demand == 'High':
                    station_arrival = arrival_prob * 1.3
                    station_departure = departure_prob * 0.9
                elif demand == 'Low':
                    station_arrival = arrival_prob * 0.7
                    station_departure = departure_prob * 1.2
                else:
                    station_arrival = arrival_prob
                    station_departure = departure_prob
                self._update_port_availability(station, 'fast', station_arrival, station_departure)
                self._update_port_availability(station, 'medium', station_arrival, station_departure)
                self._update_port_availability(station, 'slow', station_arrival, station_departure)
                self._calculate_utilization(station)
                station['last_updated'] = datetime.now().isoformat()
            self.last_update = datetime.now()
            self.total_updates += 1
            self.update_history.append({
                'timestamp': self.last_update.isoformat(),
                'total_available_ports': self._count_total_available_ports(),
                'avg_utilization': self._calculate_avg_utilization()
            })
    
    def _update_port_availability(self, station, port_type, arrival_prob, departure_prob):
        if port_type == 'fast':
            total_key, available_key = 'total_fastPorts', 'availableFastPorts'
        elif port_type == 'medium':
            total_key, available_key = 'total_mediumPorts', 'availableMediumPorts'
        else:
            total_key, available_key = 'total_slowPorts', 'availableSlowPorts'
        total = station.get(total_key, 0)
        current_available = station.get(available_key, 0)
        if total == 0:
            return
        event = random.random()
        if event < arrival_prob:
            if current_available > 0:
                station[available_key] = current_available - 1
        elif event < (arrival_prob + departure_prob):
            if current_available < total:
                station[available_key] = current_available + 1
    
    def _calculate_utilization(self, station):
        total = (station.get('total_fastPorts', 0) +
                station.get('total_mediumPorts', 0) +
                station.get('total_slowPorts', 0))
        available = (station.get('availableFastPorts', 0) +
                    station.get('availableMediumPorts', 0) +
                    station.get('availableSlowPorts', 0))
        if total == 0:
            station['utilization_rate'] = 0.0
        else:
            station['utilization_rate'] = round(((total - available) / total) * 100, 2)
    
    def _count_total_available_ports(self):
        total = 0
        for station in self.stations:
            total += (station.get('availableFastPorts', 0) +
                     station.get('availableMediumPorts', 0) +
                     station.get('availableSlowPorts', 0))
        return total
    
    def _calculate_avg_utilization(self):
        if not self.stations:
            return 0.0
        total_util = sum(s.get('utilization_rate', 0) for s in self.stations)
        return round(total_util / len(self.stations), 2)
    
    def get_stations(self):
        with self.lock:
            return [s.copy() for s in self.stations]
    
    def get_station_by_id(self, station_id):
        with self.lock:
            for station in self.stations:
                if station['id'] == station_id:
                    return station.copy()
        return None
    
    def get_update_history(self, limit=20):
        with self.lock:
            return list(self.update_history)[-limit:]
    
    def get_system_metrics(self):
        with self.lock:
            total_stations = len(self.stations)
            total_ports = available_ports = stations_with_availability = high_util_stations = 0
            for station in self.stations:
                total = (station.get('total_fastPorts', 0) +
                        station.get('total_mediumPorts', 0) +
                        station.get('total_slowPorts', 0))
                available = (station.get('availableFastPorts', 0) +
                            station.get('availableMediumPorts', 0) +
                            station.get('availableSlowPorts', 0))
                total_ports += total
                available_ports += available
                if available > 0:
                    stations_with_availability += 1
                if station.get('utilization_rate', 0) > 80:
                    high_util_stations += 1
            utilization_rate = 0.0
            if total_ports > 0:
                utilization_rate = round(((total_ports - available_ports) / total_ports) * 100, 2)
            data_source = "Unknown"
            if self.stations:
                data_source = self.stations[0].get('source', 'Unknown')
            last_fetch = "Never"
            if self.fetcher.last_fetch_time:
                last_fetch = self.fetcher.last_fetch_time.strftime("%Y-%m-%d %H:%M:%S")
            return {
                'total_stations': total_stations,
                'stations_with_availability': stations_with_availability,
                'total_ports': total_ports,
                'available_ports': available_ports,
                'occupied_ports': total_ports - available_ports,
                'utilization_rate': utilization_rate,
                'high_utilization_stations': high_util_stations,
                'avg_utilization': self._calculate_avg_utilization(),
                'total_updates': self.total_updates,
                'last_update': self.last_update.isoformat(),
                'update_interval': f'{self.min_interval}-{self.max_interval} seconds',
                'data_source': data_source,
                'last_api_fetch': last_fetch,
                'next_refresh': 'In 6 hours' if self.fetcher.last_fetch_time else 'On next request'
            }
    
    def start_auto_update(self):
        if self.running:
            return
        self.running = True
        def update_loop():
            while self.running:
                sleep_time = random.randint(self.min_interval, self.max_interval)
                time.sleep(sleep_time)
                if self.running:
                    self.simulate_charging_behavior()
                    metrics = self.get_system_metrics()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Update #{self.total_updates} | "
                          f"Available: {metrics['available_ports']}/{metrics['total_ports']} | "
                          f"Utilization: {metrics['utilization_rate']}% | "
                          f"Next: {sleep_time}s")
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
        print(f"✓ Real-time port updates started (every {self.min_interval}-{self.max_interval}s)")
    
    def start_periodic_refresh(self):
        if self.refresh_running:
            return
        self.refresh_running = True
        def refresh_loop():
            while self.refresh_running:
                time.sleep(6 * 3600)
                if self.refresh_running:
                    print("\n🔄 Periodic refresh triggered (6-hour interval)")
                    self.refresh_data()
        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()
        print("✓ Periodic data refresh started (every 6 hours)")
    
    def refresh_data(self):
        print("\n🔄 Refreshing station data from OpenChargeMap...")
        new_stations = self.fetcher.fetch_live_stations()
        if new_stations:
            with self.lock:
                old_availability = {}
                for old_station in self.stations:
                    old_availability[old_station['id']] = {
                        'availableFastPorts': old_station.get('availableFastPorts', 0),
                        'availableMediumPorts': old_station.get('availableMediumPorts', 0),
                        'availableSlowPorts': old_station.get('availableSlowPorts', 0)
                    }
                for station in new_stations:
                    station['total_fastPorts'] = station.get('fastPorts', 0)
                    station['total_mediumPorts'] = station.get('mediumPorts', 0)
                    station['total_slowPorts'] = station.get('slowPorts', 0)
                    if station['id'] in old_availability:
                        avail = old_availability[station['id']]
                        station['availableFastPorts'] = min(avail['availableFastPorts'], station['total_fastPorts'])
                        station['availableMediumPorts'] = min(avail['availableMediumPorts'], station['total_mediumPorts'])
                        station['availableSlowPorts'] = min(avail['availableSlowPorts'], station['total_slowPorts'])
                    else:
                        factor = self._get_availability_factor()
                        station['availableFastPorts'] = int(station['total_fastPorts'] * factor)
                        station['availableMediumPorts'] = int(station['total_mediumPorts'] * factor)
                        station['availableSlowPorts'] = int(station['total_slowPorts'] * factor)
                    station['last_updated'] = datetime.now().isoformat()
                    station['utilization_rate'] = 0.0
                self.stations = new_stations
                print(f"✓ Refreshed: {len(new_stations)} stations loaded")
        else:
            print("⚠ Refresh failed, keeping existing data")
    
    def stop_auto_update(self):
        self.running = False
        self.refresh_running = False


# Initialize system
realtime_system = HybridRealTimeSystem()
realtime_system.load_stations()
realtime_system.start_auto_update()
realtime_system.start_periodic_refresh()


# ============================================================
# FLASK ROUTES
# ============================================================

# ✅ CHANGE 1: / → Dashboard (index.html)
@app.route('/')
def index():
    """Dashboard — default homepage"""
    return render_template('index.html')


# ✅ CHANGE 2: /nearby → Nearby Station page (nearby.html)
@app.route('/nearby')
def nearby():
    """Nearby Station finder page"""
    return render_template('nearby.html')

@app.route('/future')
def future():
    """Future Prediction page"""
    return render_template('future.html')

@app.route('/stations')
def stations():
    """Station Port Manager page"""
    return render_template('stations.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/feature')
def feature():
    return render_template('feature.html')

@app.route('/vehicle')
def vehicle():
    return render_template('vehicle.html')

# ============================================================
# API ROUTES  (all unchanged)
# ============================================================

@app.route('/api/stations', methods=['GET'])
def get_all_stations():
    stations = realtime_system.get_stations()
    metrics = realtime_system.get_system_metrics()
    return jsonify({'success': True, 'count': len(stations), 'stations': stations, 'metrics': metrics})


@app.route('/api/find-stations', methods=['POST'])
def find_stations():
    try:
        data = request.json
        user_lat = float(data.get('user_latitude'))
        user_lon = float(data.get('user_longitude'))
        max_distance = float(data.get('max_distance', 30))
        port_type = data.get('port_type', 'all').lower()
        current_stations = realtime_system.get_stations()
        available_stations = [
            s for s in current_stations
            if (s.get('availableFastPorts', 0) +
                s.get('availableMediumPorts', 0) +
                s.get('availableSlowPorts', 0)) > 0
        ]
        result = station_selector.find_stations_sorted_by_distance(
            available_stations, user_lat, user_lon, port_type, max_distance
        )
        return jsonify({
            'success': True,
            'total_count': result['total_count'],
            'optimal_station': result['optimal_station'],
            'all_stations': result['all_stations_in_range'],
            'metrics': realtime_system.get_system_metrics()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/station/<int:station_id>', methods=['GET'])
def get_station_details(station_id):
    station = realtime_system.get_station_by_id(station_id)
    if not station:
        return jsonify({'success': False, 'error': 'Station not found'}), 404
    return jsonify({'success': True, 'station': station, 'last_update': realtime_system.last_update.isoformat()})


@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    metrics = realtime_system.get_system_metrics()
    history = realtime_system.get_update_history(limit=20)
    return jsonify({'success': True, 'metrics': metrics, 'update_history': history})


@app.route('/api/refresh', methods=['POST'])
def manual_refresh():
    try:
        realtime_system.refresh_data()
        metrics = realtime_system.get_system_metrics()
        return jsonify({'success': True, 'message': 'Data refreshed successfully', 'metrics': metrics})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── In app.py — replace the existing predict_future route ──
@app.route('/api/predict-future-station', methods=['POST'])
def predict_future():
    try:
        stations = realtime_system.get_stations()
        result   = future_predictor.predict_future_station(stations)
        return jsonify({
            'success': True,
            'predicted_location': result['predicted_location'],
            'all_evaluations': result.get('all_evaluations', [])  # ← must be here
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    metrics = realtime_system.get_system_metrics()
    return jsonify({
        'status': 'healthy',
        'service': 'EV Charging Station Finder (Hybrid)',
        'version': '5.0',
        'realtime_status': 'active' if realtime_system.running else 'inactive',
        'stations_loaded': metrics['total_stations'],
        'data_source': metrics['data_source'],
        'last_api_fetch': metrics['last_api_fetch'],
        'total_updates': metrics['total_updates'],
        'last_update': metrics['last_update']
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


def verify_api_connection():
    api_key = os.getenv("OPENCHARGEMAP_API_KEY")
    if not api_key:
        print("⚠️  WARNING: No API key found in .env file!")
        print("   Will use fallback dataset only.")
        return False
    print(f"✓ API Key loaded: {api_key[:10]}...")
    try:
        response = requests.get(
            "https://api.openchargemap.io/v3/poi/",
            params={'countrycode': 'IN', 'maxresults': 1},
            headers={'X-API-Key': api_key},
            timeout=5
        )
        if response.status_code == 200:
            print("✓ OpenChargeMap API connection successful!")
            return True
        else:
            print(f"⚠️  API returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  API connection test failed: {e}")
        return False


if __name__ == '__main__':
    print("=" * 70)
    print("HYBRID EV CHARGING STATION FINDER - VERSION 5.0 (LIVE MODE)")
    print("=" * 70)
    print("Features:")
    print("  ✓ Live OpenChargeMap API integration (PRIMARY)")
    print("  ✓ Automatic fallback to local JSON (BACKUP ONLY)")
    print("  ✓ Smart caching (6-hour validity)")
    print("  ✓ Periodic refresh every 6 hours")
    print("  ✓ Real-time port availability simulation")
    print("  ✓ Time-based usage patterns")
    print("=" * 70)

    print("\n🔍 Verifying API Connection...")
    api_ok = verify_api_connection()
    print()

    realtime_system.load_stations()

    metrics = realtime_system.get_system_metrics()
    print(f"\n📊 System Status:")
    print(f"  Data Source: {metrics['data_source']}")
    print(f"  Stations Loaded: {metrics['total_stations']}")
    print(f"  Last API Fetch: {metrics['last_api_fetch']}")

    if "Fallback" in metrics['data_source']:
        print("\n⚠️  WARNING: Using fallback dataset!")
        print("   Check your API key and internet connection.")
    else:
        print("\n✅ Successfully using LIVE data!")

    print("\n" + "=" * 70)
    print("Starting Flask server on http://localhost:5001")
    print("=" * 70)
    print("\nRoutes:")
    print("  GET  /                      - Dashboard (homepage)")
    print("  GET  /nearby                - Nearby Station finder")
    print("\nAPI Endpoints:")
    print("  GET  /api/stations          - Get all stations")
    print("  POST /api/find-stations     - Find nearby stations")
    print("  GET  /api/metrics           - Get system metrics")
    print("  POST /api/refresh           - Manual data refresh")
    print("  GET  /api/health            - Health check")
    print("=" * 70 + "\n")

    realtime_system.start_auto_update()
    realtime_system.start_periodic_refresh()

    try:
        app.run(
            debug=True,
            host='0.0.0.0',
            port=5001,
            use_reloader=False
        )
    finally:
        realtime_system.stop_auto_update()
        print("\n✓ System stopped")