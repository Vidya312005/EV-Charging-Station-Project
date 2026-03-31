# EV CHARGING STATION FINDER - MODIFIED VERSION

**Context-Aware Optimal Resource Scheduling Mechanism of Electric Vehicle Charging Stations using Software Defined Networks**

---

## 🆕 NEW FEATURES IN THIS VERSION

### ✅ **Distance-Based Sorting**
- Stations are **ALWAYS sorted by nearest distance** before applying max distance filter
- Ensures users see closest stations first

### ✅ **Complete Station List Display**
- Shows **ALL stations within max distance** (not just optimal one)
- Each station displays its distance from user
- Click any station to see full details

### ✅ **Color-Coded Map Markers**
- 🟢 **Green**: Nearby stations (0-15 km)
- 🟡 **Yellow**: Medium distance (15-30 km)
- 🔴 **Red**: Far stations (30+ km)
- 🔵 **Blue**: Your current location

### ✅ **Visible Map Legend**
- Clear legend explaining marker colors
- Always visible above the map

### ✅ **Interactive Station Selection**
- Click station in list OR map marker to show details
- Full station information displayed:
  - Station Name
  - Location / District
  - Charging Types (Fast/Medium/Slow ports)
  - Total Ports
  - Available Ports
  - Distance from user

### ✅ **Updated Port Structure**
- Uses `fastPorts`, `mediumPorts`, `slowPorts` instead of single charger type
- Shows available vs total for each port type
- Filter by: **All Types / Fast Ports / Medium Ports / Slow Ports**

### ✅ **Renamed UI Elements**
- "Search Radius" → **"Max Distance (KM)"**
- Port type filter replaces old AC/DC/Fast filter

---

## 📁 PROJECT STRUCTURE

```
EV-CHARGING-STATION-FINDER-MODIFIED/
│
├── app.py                                  # Modified Flask backend
├── requirements.txt                        # Python dependencies
├── .env                                    # Environment variables
├── README.md                               # This file
│
├── algorithms/
│   ├── __init__.py
│   ├── greedy_station_selector.py         # Modified for new port structure
│   └── greedy_future_predictor.py         # Future station prediction
│
├── data/
│   └── kerala_charging_stations.json      # Updated dataset (17 stations)
│
├── static/
│   ├── css/
│   │   └── style.css                      # Updated with legend styling
│   └── js/
│       └── main.js                        # Complete modified JavaScript
│
└── templates/
    └── index.html                         # Updated HTML template
```

---

## 🚀 INSTALLATION & SETUP

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Get Google Maps API Key

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create project
3. Enable **Maps JavaScript API** and **Directions API**
4. Create API Key
5. Copy the key

### Step 3: Configure Environment

Edit `.env` file:

```env
GOOGLE_MAPS_API_KEY=YOUR_ACTUAL_API_KEY_HERE
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

### Step 4: Run Application

```bash
python app.py
```

### Step 5: Open Browser

Navigate to: **http://localhost:5000**

---

## 📖 HOW TO USE THE SYSTEM

### 1. **Location Detection**
- System automatically detects your location when page loads
- Blue marker shows your position on map

### 2. **Set Search Parameters**
- **Max Distance (KM)**: Enter maximum search radius (e.g., 30 km)
- **Preferred Port Type**: Select All Types / Fast / Medium / Slow

### 3. **Find Stations**
- Click **"Find Charging Stations"** button
- System processes your request using modified greedy algorithm

### 4. **View Results**

#### **Nearby Stations Count**
Shows total number of stations found within your max distance

#### **ALL STATIONS List** (Sorted by Distance)
- Lists all stations from nearest to farthest
- Click any station to see full details
- Selected station is highlighted

#### **Station Details Panel**
Displays complete information when you click a station:
- Station Name
- Location / District
- Charging Types with availability (Fast/Medium/Slow)
- Total Ports
- Available Ports
- Distance from your location
- **Navigate to Station** button

### 5. **Navigate to Station**
- Click **"Navigate to Station"** button
- Map switches to Google Maps with driving directions

### 6. **Map Features**

#### **Color-Coded Markers**
- Green markers: Nearby stations (0-15 km)
- Yellow markers: Medium distance (15-30 km)
- Red markers: Far stations (30+ km)
- Blue marker: Your location

#### **Interactive Map Legend**
- Always visible above map
- Explains what each color means
- Helps you quickly identify station distances

---

## 🧠 TECHNICAL IMPLEMENTATION

### Modified Greedy Algorithm for Station Selection

**File**: `algorithms/greedy_station_selector.py`

#### Key Changes:

1. **Distance-First Sorting**
   ```python
   # Step 1: Calculate distance for ALL stations
   # Step 2: Sort ALL stations by distance (ascending)
   # Step 3: Filter by max_distance AFTER sorting
   ```

2. **Port Type Support**
   - Works with `fastPorts`, `mediumPorts`, `slowPorts`
   - Filters based on user's port type preference

3. **Greedy Scoring** (0-100 points)
   - **Distance Score** (40%): Closer stations score higher
   - **Availability Score** (35%): More available ports score higher
   - **Port Type Score** (25%): Matching port type gets bonus

#### Algorithm Flow:

```
1. Calculate distance from user to ALL 17 stations
2. Sort ALL stations by distance (nearest first)
3. Filter: Keep only stations within max_distance
4. Filter: Keep only stations with requested port type
5. Calculate greedy score for each remaining station
6. Select station with HIGHEST score as optimal
7. Return: Optimal station + ALL matching stations
```

### Color-Coded Marker System

**File**: `static/js/main.js`

```javascript
function getMarkerColorByDistance(distance) {
    if (distance <= 15) return '#28a745';     // Green
    else if (distance <= 30) return '#ffc107'; // Yellow
    else return '#dc3545';                     // Red
}
```

### Updated Dataset Structure

**File**: `data/kerala_charging_stations.json`

```json
{
  "id": 1,
  "name": "Station Name",
  "latitude": 8.5241,
  "longitude": 76.9366,
  "district": "District Name",
  "fastPorts": 3,
  "mediumPorts": 3,
  "slowPorts": 2,
  "availableFastPorts": 2,
  "availableMediumPorts": 2,
  "availableSlowPorts": 1,
  "ev_density": 120,
  "charging_demand": "High"
}
```

---

## 🎯 KEY MODIFICATIONS SUMMARY

| Feature | Original | Modified |
|---------|----------|----------|
| **Sorting** | By greedy score only | **By distance FIRST, then score** |
| **Display** | Only optimal station | **ALL stations in range** |
| **Markers** | Availability-based color | **Distance-based color (Green/Yellow/Red)** |
| **Legend** | Not present | **Visible legend with color explanation** |
| **Selection** | Automatic | **Click any station for details** |
| **Port Types** | charger_type (AC/DC/Fast) | **fastPorts, mediumPorts, slowPorts** |
| **Filter** | AC / DC / Fast | **All Types / Fast / Medium / Slow** |
| **Label** | "Search Radius" | **"Max Distance (KM)"** |

---

## 📊 API ENDPOINTS

### 1. Find Stations (Modified)
```
POST /api/find-stations
Content-Type: application/json

{
  "user_latitude": 10.0265,
  "user_longitude": 76.3119,
  "max_distance": 30,
  "port_type": "fast"
}

Response:
{
  "success": true,
  "total_count": 5,
  "optimal_station": {...},
  "all_stations": [...]  // Sorted by distance
}
```

### 2. Get All Stations
```
GET /api/stations
```

### 3. Predict Future Station
```
POST /api/predict-future-station
```

### 4. Health Check
```
GET /api/health
```

---

## 🐛 TROUBLESHOOTING

### Issue: Stations not sorted by distance
**Solution**: Check backend is using modified `greedy_station_selector.py`

### Issue: Map markers all same color
**Solution**: Verify `getMarkerColorByDistance()` function in `main.js`

### Issue: Legend not visible
**Solution**: Check `.map-legend` styling in `style.css`

### Issue: Station details not showing on click
**Solution**: Ensure `showStationDetails()` is called in both marker and list click handlers

### Issue: Port types not displaying correctly
**Solution**: Verify JSON dataset has `fastPorts`, `mediumPorts`, `slowPorts` fields

---

## 🔧 CUSTOMIZATION OPTIONS

### Change Distance Color Thresholds

Edit `main.js`:

```javascript
function getMarkerColorByDistance(distance) {
    if (distance <= 10) return '#28a745';     // Green (0-10 km)
    else if (distance <= 25) return '#ffc107'; // Yellow (10-25 km)
    else return '#dc3545';                     // Red (25+ km)
}
```

### Adjust Greedy Algorithm Weights

Edit `algorithms/greedy_station_selector.py`:

```python
self.DISTANCE_WEIGHT = 50      # Increase distance importance
self.AVAILABILITY_WEIGHT = 30  # Decrease availability importance
self.PORT_TYPE_WEIGHT = 20     # Decrease port type importance
```

### Add More Stations

Edit `data/kerala_charging_stations.json` and add new entries following the structure.

---

## ✅ TESTING CHECKLIST

- [ ] Location detection works
- [ ] Max distance input accepts numbers
- [ ] Port type dropdown shows 4 options
- [ ] "Find Charging Stations" button works
- [ ] Station count displays correctly
- [ ] Station list shows all results sorted by distance
- [ ] Map markers are color-coded by distance
- [ ] Legend is visible and matches marker colors
- [ ] Clicking station in list shows details
- [ ] Clicking map marker shows details
- [ ] Station details show all required fields
- [ ] Port types display with Fast/Medium/Slow badges
- [ ] "Navigate to Station" switches to Google Maps
- [ ] Google Maps shows route from user to station
- [ ] Future station prediction works

---

## 📞 SUPPORT

All code is:
- ✅ Clean and modular
- ✅ Well-commented
- ✅ Ready to run
- ✅ Beginner-friendly

For issues, check:
1. Browser console (F12) for JavaScript errors
2. Terminal for Python errors
3. All files in correct locations
4. Google Maps API key is valid

---

## 📄 LICENSE

Educational project for Software Defined Networks course.

---

**Modified Version 2.0** - Ready to Use! ⚡🚗🗺️