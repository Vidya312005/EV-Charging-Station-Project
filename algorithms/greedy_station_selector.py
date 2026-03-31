"""
MODIFIED GREEDY ALGORITHM FOR OPTIMAL CHARGING STATION SELECTION

Changes from original:
1. Works with fastPorts, mediumPorts, slowPorts instead of charger_type
2. Supports filtering by port type (All/Fast/Medium/Slow)
3. Stations are ALWAYS sorted by distance BEFORE filtering by max distance
4. Returns ALL stations within max distance with their distances
"""

import math

class GreedyStationSelector:
    
    def __init__(self):
        """
        Initialize the greedy station selector with updated weights
        """
        # Weight factors for greedy scoring
        self.DISTANCE_WEIGHT = 40  # 40% importance
        self.AVAILABILITY_WEIGHT = 35  # 35% importance
        self.PORT_TYPE_WEIGHT = 25  # 25% importance
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two points using Haversine formula
        
        Args:
            lat1, lon1: User's latitude and longitude
            lat2, lon2: Station's latitude and longitude
            
        Returns:
            Distance in kilometers
        """
        R = 6371.0  # Earth's radius in kilometers
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return round(distance, 2)
    
    def get_total_ports(self, station):
        """
        Calculate total ports for a station
        
        Args:
            station: Station dictionary
            
        Returns:
            Total number of ports
        """
        return station['fastPorts'] + station['mediumPorts'] + station['slowPorts']
    
    def get_available_ports(self, station):
        """
        Calculate total available ports for a station
        
        Args:
            station: Station dictionary
            
        Returns:
            Total available ports
        """
        return (station['availableFastPorts'] + 
                station['availableMediumPorts'] + 
                station['availableSlowPorts'])
    
    def has_port_type(self, station, port_type):
        """
        Check if station has the requested port type with availability
        
        Args:
            station: Station dictionary
            port_type: 'fast', 'medium', 'slow', or 'all'
            
        Returns:
            True if station has available ports of requested type
        """
        if port_type == 'all':
            return True
        
        if port_type == 'fast':
            return station['fastPorts'] > 0
        elif port_type == 'medium':
            return station['mediumPorts'] > 0
        elif port_type == 'slow':
            return station['slowPorts'] > 0
        
        return False
    
    def calculate_greedy_score(self, station, user_lat, user_lon, preferred_port_type):
        """
        MODIFIED GREEDY ALGORITHM: Calculate score for a station
        
        Scoring criteria (updated for new port structure):
        1. Distance Score: Closer stations get higher scores
        2. Availability Score: More available ports = higher score
        3. Port Type Score: Having requested port type = bonus points
        
        Args:
            station: Station dictionary with fastPorts, mediumPorts, slowPorts
            user_lat, user_lon: User's location
            preferred_port_type: 'fast', 'medium', 'slow', or 'all'
            
        Returns:
            Dictionary with score details
        """
        # Calculate distance (already calculated, but include for scoring)
        distance = station['distance']
        
        # 1. DISTANCE SCORE (0-40 points)
        # Closer stations get more points
        # Maximum distance considered is 50 km
        distance_score = max(0, self.DISTANCE_WEIGHT * (1 - distance / 50))
        
        # 2. AVAILABILITY SCORE (0-35 points)
        total_ports = self.get_total_ports(station)
        available_ports = self.get_available_ports(station)
        
        availability_ratio = available_ports / total_ports if total_ports > 0 else 0
        availability_score = self.AVAILABILITY_WEIGHT * availability_ratio
        
        # 3. PORT TYPE SCORE (0-25 points)
        port_score = 0
        if preferred_port_type == 'all':
            # If all types, give score based on variety
            port_score = self.PORT_TYPE_WEIGHT
        elif preferred_port_type == 'fast' and station['fastPorts'] > 0:
            # Bonus for having fast ports
            port_score = self.PORT_TYPE_WEIGHT
        elif preferred_port_type == 'medium' and station['mediumPorts'] > 0:
            port_score = self.PORT_TYPE_WEIGHT
        elif preferred_port_type == 'slow' and station['slowPorts'] > 0:
            port_score = self.PORT_TYPE_WEIGHT
        
        # TOTAL GREEDY SCORE
        total_score = distance_score + availability_score + port_score
        
        return {
            'total_score': round(total_score, 2),
            'distance': distance,
            'distance_score': round(distance_score, 2),
            'availability_score': round(availability_score, 2),
            'port_score': round(port_score, 2)
        }
    
    def find_stations_sorted_by_distance(self, stations, user_lat, user_lon, 
                                        preferred_port_type, max_distance):
        """
        MODIFIED ALGORITHM: Find stations sorted by distance, then filter by max distance
        
        Key Changes:
        1. Calculate distance for ALL stations first
        2. Sort ALL stations by distance (ascending)
        3. Filter by max_distance AFTER sorting
        4. Apply port type filter
        5. Return ALL matching stations with distances
        
        Args:
            stations: List of all charging stations
            user_lat, user_lon: User's current location
            preferred_port_type: 'fast', 'medium', 'slow', or 'all'
            max_distance: Maximum distance in km
            
        Returns:
            Dictionary with all matching stations sorted by distance
        """
        # STEP 1: Calculate distance for ALL stations
        stations_with_distance = []
        
        for station in stations:
            distance = self.calculate_distance(
                user_lat, user_lon,
                station['latitude'], station['longitude']
            )
            
            # Create a copy with distance added
            station_copy = station.copy()
            station_copy['distance'] = distance
            stations_with_distance.append(station_copy)
        
        # STEP 2: Sort ALL stations by distance (NEAREST FIRST)
        stations_with_distance.sort(key=lambda x: x['distance'])
        
        # STEP 3: Filter by max_distance
        filtered_stations = [
            s for s in stations_with_distance 
            if s['distance'] <= max_distance
        ]
        
        # STEP 4: Apply port type filter
        if preferred_port_type != 'all':
            filtered_stations = [
                s for s in filtered_stations
                if self.has_port_type(s, preferred_port_type)
            ]
        
        # STEP 5: Calculate greedy scores for each station
        for station in filtered_stations:
            score_data = self.calculate_greedy_score(
                station, user_lat, user_lon, preferred_port_type
            )
            station['score_details'] = score_data
        
        # STEP 6: Find optimal station (highest greedy score)
        optimal_station = None
        if filtered_stations:
            optimal_station = max(filtered_stations, 
                                 key=lambda x: x['score_details']['total_score'])
        
        return {
            'optimal_station': optimal_station,
            'all_stations_in_range': filtered_stations,
            'total_count': len(filtered_stations)
        }