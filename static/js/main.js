/**
 * EV CHARGING STATION FINDER - OSRM NAVIGATION
 * 
 * FEATURES:
 * 1. Stations sorted by nearest distance
 * 2. Display all stations within max distance with their distances
 * 3. Color-coded markers based on distance (Green/Yellow/Red)
 * 4. Click on station (list or marker) to show full details
 * 5. OSRM-based routing (no Google Maps API needed)
 * 6. Turn-by-turn navigation using Leaflet Routing Machine
 */

// ========================================
// GLOBAL VARIABLES
// ========================================
let userLatitude = null;
let userLongitude = null;
let map = null;
let currentStations = [];
let stationMarkers = [];
let selectedStationId = null;
let routingControl = null; // For OSRM routing
let userMarker = null;

// ========================================
// INITIALIZATION
// ========================================
window.addEventListener('DOMContentLoaded', function() {
    console.log('EV Charging Station Finder (OSRM) - Initializing...');
    
    // Detect user location automatically
    detectUserLocation();
    
    // Initialize Map
    initializeMap();
    
    console.log('Initialization complete.');
});

// ========================================
// LOCATION DETECTION
// ========================================
function detectUserLocation() {
    const statusElement = document.getElementById('location-status');
    const coordsElement = document.getElementById('location-coords');
    
    statusElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Detecting your location...';
    
    if (!navigator.geolocation) {
        statusElement.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Geolocation not supported';
        statusElement.style.color = 'red';
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
    function(position) {
        userLatitude = position.coords.latitude;
        userLongitude = position.coords.longitude;
        
        statusElement.innerHTML = '<i class="fas fa-check-circle"></i> Location detected successfully!';
        statusElement.style.color = 'green';
        
        coordsElement.innerHTML = `Latitude: ${userLatitude.toFixed(4)}, Longitude: ${userLongitude.toFixed(4)}`;
        
        // Add user marker to map
        if (map) {
            addUserMarkerToMap(userLatitude, userLongitude);
        }
        
        console.log(`User location: ${userLatitude}, ${userLongitude}`);
    },
    function(error) {
        let errorMessage = 'Unable to detect location';
        
        switch(error.code) {
            case error.PERMISSION_DENIED:
                errorMessage = 'Location permission denied. Please enable location access.';
                break;
            case error.POSITION_UNAVAILABLE:
                errorMessage = 'Location information unavailable. Click below to enter manually.';
                break;
            case error.TIMEOUT:
                errorMessage = 'Location request timed out. Click below to enter manually.';
                break;
        }
        
        statusElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${errorMessage}`;
        statusElement.style.color = 'red';
        
        // Add manual location button
        coordsElement.innerHTML = `
            <button onclick="enterManualLocation()" style="
                padding: 8px 16px;
                background: #6c5ce7;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            ">
                <i class="fas fa-map-marker-alt"></i> Enter Location Manually
            </button>
        `;
        
        console.error('Geolocation error:', error);
    },
    {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0
    }
);
}

// ========================================
// MAP FUNCTIONS
// ========================================
function initializeMap() {
    // Create map centered on Kerala
    map = L.map('map').setView([10.8505, 76.2711], 8);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    
    console.log('Map initialized with OpenStreetMap');
}

function addUserMarkerToMap(lat, lng) {
    // Remove existing user marker if any
    if (userMarker) {
        map.removeLayer(userMarker);
    }
    
    // Create custom blue icon for user (matching legend)
    const userIcon = L.divIcon({
        className: 'user-marker',
        html: '<div style="background: #4285F4; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.3);"></div>',
        iconSize: [20, 20]
    });
    
    userMarker = L.marker([lat, lng], { icon: userIcon })
        .addTo(map)
        .bindPopup('<b>Your Location</b>')
        .openPopup();
    
    map.setView([lat, lng], 10);
}

/**
 * Get marker color based on distance
 * Green: 0-15 km (Nearby)
 * Yellow: 15-30 km (Medium)
 * Red: 30+ km (Far)
 */
function getMarkerColorByDistance(distance) {
    if (distance <= 15) {
        return '#28a745'; // Green
    } else if (distance <= 30) {
        return '#ffc107'; // Yellow
    } else {
        return '#dc3545'; // Red
    }
}

/**
 * Add color-coded station markers based on distance
 */
function addStationMarkersToMap(stations) {
    // Clear existing station markers
    stationMarkers.forEach(marker => {
        map.removeLayer(marker);
    });
    stationMarkers = [];
    
    // Add new markers for each station
    stations.forEach(station => {
        // Determine marker color based on distance
        const markerColor = getMarkerColorByDistance(station.distance);
        
        // Create custom colored marker
        const stationIcon = L.divIcon({
            className: 'station-marker',
            html: `<div style="background: ${markerColor}; width: 16px; height: 16px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); cursor: pointer;"></div>`,
            iconSize: [16, 16]
        });
        
        // Add marker to map
        const marker = L.marker([station.latitude, station.longitude], { 
            icon: stationIcon,
            stationId: station.id
        })
            .addTo(map)
            .bindPopup(`
                <div style="min-width: 200px;">
                    <b>${station.name}</b><br>
                    <small>Click marker or list item for details</small><br>
                    Distance: ${station.distance.toFixed(2)} km
                </div>
            `);
        
        // Click marker to show station details
        marker.on('click', function() {
            showStationDetails(station);
        });
        
        stationMarkers.push(marker);
    });
}

// ========================================
// FINDING NEARBY STATIONS
// ========================================
async function findNearbyStations() {
    // Validate user location
    if (!userLatitude || !userLongitude) {
        alert('Please wait for location detection to complete');
        return;
    }
    
    // Get user inputs
    const maxDistance = parseFloat(document.getElementById('max-distance').value);
    const portType = document.getElementById('port-type').value;
    
    // Validate inputs
    if (!maxDistance || maxDistance <= 0) {
        alert('Please enter a valid max distance');
        return;
    }
    
    // Show loading overlay
    showLoading(true);
    
    try {
        // Call backend API
        const response = await fetch('/api/find-stations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_latitude: userLatitude,
                user_longitude: userLongitude,
                max_distance: maxDistance,
                port_type: portType
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            alert(data.message || 'No stations found');
            showLoading(false);
            return;
        }
        
        // Store current stations
        currentStations = data.all_stations;
        
        // Display results
        displayNearbyCount(data.total_count, maxDistance);
        displayStationsList(currentStations);
        
        // Show first station details automatically (optimal station)
        if (data.optimal_station) {
            showStationDetails(data.optimal_station);
        }
        
        // Update map with color-coded markers
        addStationMarkersToMap(currentStations);
        
        // Get future station prediction
        await predictFutureStation();
        
        showLoading(false);
        
    } catch (error) {
        console.error('Error finding stations:', error);
        alert('Error connecting to server');
        showLoading(false);
    }
}

// ========================================
// DISPLAY FUNCTIONS
// ========================================
function displayNearbyCount(count, maxDistance) {
    const box = document.getElementById('nearby-count-box');
    const countElement = document.getElementById('nearby-count');
    const distanceElement = document.getElementById('selected-distance');
    
    countElement.textContent = count;
    distanceElement.textContent = maxDistance;
    box.style.display = 'block';
}

/**
 * Display list of all stations sorted by distance
 */
function displayStationsList(stations) {
    const box = document.getElementById('stations-list-box');
    const listElement = document.getElementById('stations-list');
    
    if (!stations || stations.length === 0) {
        box.style.display = 'none';
        return;
    }
    
    let html = '';
    
    stations.forEach((station, index) => {
        html += `
            <div class="station-list-item" data-station-id="${station.id}" 
                 onclick="selectStationFromList(${station.id})">
                <div class="station-list-name">
                    ${index + 1}. ${station.name}
                </div>
                <div class="station-list-info">
                    <i class="fas fa-map-marker-alt"></i> ${station.district}<br>
                    <span class="station-list-distance">${station.distance.toFixed(2)} km away</span>
                </div>
            </div>
        `;
    });
    
    listElement.innerHTML = html;
    box.style.display = 'block';
}

/**
 * Handle station selection from list
 */
function selectStationFromList(stationId) {
    // Find station in current list
    const station = currentStations.find(s => s.id === stationId);
    
    if (station) {
        // Remove previous selection highlight
        document.querySelectorAll('.station-list-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Highlight selected item
        const selectedItem = document.querySelector(`[data-station-id="${stationId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
        
        // Show station details
        showStationDetails(station);
        
        // Center map on selected station
        map.setView([station.latitude, station.longitude], 13);
    }
}

/**
 * Show full station details when clicked
 */
function showStationDetails(station) {
    const box = document.getElementById('selected-station-box');
    const detailsElement = document.getElementById('selected-station-details');
    
    selectedStationId = station.id;
    
    // Calculate total and available ports
    const totalPorts = station.fastPorts + station.mediumPorts + station.slowPorts;
    const availablePorts = station.availableFastPorts + station.availableMediumPorts + station.availableSlowPorts;
    
    // Build charging type display from port information
    let chargingTypes = '';
    if (station.fastPorts > 0) {
        chargingTypes += `<span class="port-badge fast">Fast: ${station.availableFastPorts}/${station.fastPorts}</span> `;
    }
    if (station.mediumPorts > 0) {
        chargingTypes += `<span class="port-badge medium">Medium: ${station.availableMediumPorts}/${station.mediumPorts}</span> `;
    }
    if (station.slowPorts > 0) {
        chargingTypes += `<span class="port-badge slow">Slow: ${station.availableSlowPorts}/${station.slowPorts}</span>`;
    }
    
    const html = `
        <div class="detail-row">
            <span class="detail-label">Station Name:</span>
            <span class="detail-value highlight">${station.name}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Location / District:</span>
            <span class="detail-value">${station.district}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Charging Types:</span>
            <span class="detail-value">${chargingTypes}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Total Ports:</span>
            <span class="detail-value">${totalPorts}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Available Ports:</span>
            <span class="detail-value highlight">${availablePorts}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Distance from You:</span>
            <span class="detail-value">${station.distance.toFixed(2)} km</span>
        </div>
        <button class="btn-navigate" onclick='navigateToStation(${JSON.stringify(station)})'>
            <i class="fas fa-directions"></i> Navigate to Station
        </button>
    `;
    
    detailsElement.innerHTML = html;
    box.style.display = 'block';
}

// ========================================
// OSRM NAVIGATION FUNCTIONS
// ========================================

/**
 * Navigate to selected station using OSRM
 */
function navigateToStation(station) {
    if (!userLatitude || !userLongitude) {
        alert('User location not available');
        return;
    }
    
    // Clear any existing route
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }
    
    // Update map title
    document.getElementById('map-title').textContent = 'Navigation Active';
    
    // Create routing control with OSRM
    routingControl = L.Routing.control({
        waypoints: [
            L.latLng(userLatitude, userLongitude),
            L.latLng(station.latitude, station.longitude)
        ],
        router: L.Routing.osrmv1({
            serviceUrl: 'https://router.project-osrm.org/route/v1',
            profile: 'driving' // Options: driving, car, bike, foot
        }),
        routeWhileDragging: false,
        addWaypoints: false,
        draggableWaypoints: false,
        fitSelectedRoutes: true,
        showAlternatives: false,
        lineOptions: {
            styles: [
                {color: '#2196F3', opacity: 0.8, weight: 6}
            ]
        },
        createMarker: function(i, waypoint, n) {
            // Custom markers for start and end
            let markerIcon;
            let markerText;
            
            if (i === 0) {
                // Start marker (user location)
                markerIcon = L.divIcon({
                    className: 'route-marker-start',
                    html: '<div style="background: #4285F4; width: 24px; height: 24px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.4);"></div>',
                    iconSize: [24, 24]
                });
                markerText = 'Start: Your Location';
            } else {
                // End marker (station)
                markerIcon = L.divIcon({
                    className: 'route-marker-end',
                    html: '<div style="background: #EA4335; width: 24px; height: 24px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.4);"></div>',
                    iconSize: [24, 24]
                });
                markerText = `Destination: ${station.name}`;
            }
            
            return L.marker(waypoint.latLng, {
                icon: markerIcon
            }).bindPopup(markerText);
        }
    }).addTo(map);
    
    // Listen for route found event
    routingControl.on('routesfound', function(e) {
        const routes = e.routes;
        const summary = routes[0].summary;
        
        // Display route information
        displayRouteInformation({
            distance: (summary.totalDistance / 1000).toFixed(2), // Convert to km
            duration: Math.round(summary.totalTime / 60), // Convert to minutes
            stationName: station.name
        });
    });
    
    // Listen for routing errors
    routingControl.on('routingerror', function(e) {
        console.error('Routing error:', e);
        alert('Unable to find route. Please try again.');
    });
    
    console.log('OSRM navigation started to:', station.name);
}

/**
 * Display route information in the UI
 */
function displayRouteInformation(routeInfo) {
    const box = document.getElementById('route-info-box');
    const detailsElement = document.getElementById('route-details');
    
    const html = `
        <div class="detail-row">
            <span class="detail-label">Destination:</span>
            <span class="detail-value highlight">${routeInfo.stationName}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Route Distance:</span>
            <span class="detail-value">${routeInfo.distance} km</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Estimated Time:</span>
            <span class="detail-value">${routeInfo.duration} minutes</span>
        </div>
        <div class="detail-row" style="border-bottom: none;">
            <span class="detail-label">Route Type:</span>
            <span class="detail-value">Driving (Optimized)</span>
        </div>
        <p style="margin-top: 10px; color: #555; font-size: 0.9em;">
            <i class="fas fa-info-circle"></i> Turn-by-turn directions are shown on the map. 
            The route is calculated using OSRM (Open Source Routing Machine).
        </p>
    `;
    
    detailsElement.innerHTML = html;
    box.style.display = 'block';
}

/**
 * Clear navigation and reset map
 */
function clearNavigation() {
    // Remove routing control
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }
    
    // Hide route info box
    document.getElementById('route-info-box').style.display = 'none';
    
    // Reset map title
    document.getElementById('map-title').textContent = 'Interactive Map';
    
    // Re-center map on user location
    if (userLatitude && userLongitude) {
        map.setView([userLatitude, userLongitude], 10);
    }
    
    console.log('Navigation cleared');
}

// ========================================
// FUTURE STATION PREDICTION
// ========================================
async function predictFutureStation() {
    try {
        const response = await fetch('/api/predict-future-station', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success && data.predicted_location) {
            displayFutureStation(data.predicted_location);
        }
        
    } catch (error) {
        console.error('Error predicting future station:', error);
    }
}

function displayFutureStation(prediction) {
    const box = document.getElementById('future-station-box');
    const detailsElement = document.getElementById('future-station-details');
    
    const html = `
        <div class="detail-row">
            <span class="detail-label">Proposed Location:</span>
            <span class="detail-value highlight">${prediction.district}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Estimated Demand:</span>
            <span class="detail-value">${prediction.estimated_demand}</span>
        </div>
        <div class="detail-row" style="border-bottom: none;">
            <span class="detail-label">Reason:</span>
        </div>
        <p style="margin-top: 10px; color: #555; line-height: 1.8;">
            ${prediction.reason}
        </p>
    `;
    
    detailsElement.innerHTML = html;
    box.style.display = 'block';
}

// ========================================
// UTILITY FUNCTIONS
// ========================================
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}
// ========================================
// MANUAL LOCATION INPUT
// ========================================
function enterManualLocation() {
    const latitude = prompt('Enter your Latitude (e.g., 11.6643 for Salem):');
    const longitude = prompt('Enter your Longitude (e.g., 78.1460 for Salem):');
    
    if (latitude && longitude) {
        const lat = parseFloat(latitude);
        const lng = parseFloat(longitude);
        
        if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
            userLatitude = lat;
            userLongitude = lng;
            
            const statusElement = document.getElementById('location-status');
            const coordsElement = document.getElementById('location-coords');
            
            statusElement.innerHTML = '<i class="fas fa-check-circle"></i> Location set manually!';
            statusElement.style.color = 'green';
            
            coordsElement.innerHTML = `Latitude: ${userLatitude.toFixed(4)}, Longitude: ${userLongitude.toFixed(4)}`;
            
            // Add user marker to map
            if (map) {
                addUserMarkerToMap(userLatitude, userLongitude);
            }
            
            console.log(`Manual location set: ${userLatitude}, ${userLongitude}`);
        } else {
            alert('Invalid coordinates. Please enter valid latitude and longitude.');
        }
    }
}
console.log('OSRM Navigation JavaScript loaded successfully');
console.log('Features: Distance-based sorting, Color-coded markers, OSRM routing');