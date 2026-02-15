# SkyLink API

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)]()


**Professional aviation data service providing comprehensive real-time aircraft tracking, airport information, and weather services.**

## 🚀 Features

### ✈️ Real-Time Aircraft Tracking
- **Live ADS-B Data**: Real-time aircraft positions from global ADS-B network  
- **Enriched Information**: 615,000+ aircraft database with registrations, types, and operators  
- **Airline Identification**: Automatic airline detection from flight callsigns  
- **Advanced Filtering**: Search by location, altitude, speed, airline, registration  

### 🌍 Global Aviation Data
- **Airport Information**: Comprehensive database of worldwide airports  
- **Airline Details**: Complete airline information with ICAO/IATA codes  
- **Weather Services**: Current METAR and TAF weather reports  
- **Flight Schedules**: Real-time arrival and departure information  

### 🔧 Technical Features
- **High Performance**: Optimized for production workloads  
- **RESTful API**: Clean, intuitive endpoints with comprehensive documentation  
- **Real-time Updates**: Live data streaming and processing  

## 📋 API Endpoints

### Aircraft Tracking
```

GET /v2/adsb/aircraft                     # All tracked aircraft
GET /v2/adsb/aircraft?icao24=ABC123       # Filter by aircraft identifier
GET /v2/adsb/aircraft?registration=N123AB # Filter by registration
GET /v2/adsb/aircraft?airline=Delta       # Filter by airline
GET /v2/adsb/aircraft?lat=40.7&lon=-74&radius=50 # Geographic search

```

### Airport Services
```

GET /v2/airports/search?icao=KJFK       # Search by ICAO code
GET /v2/airports/search?iata=JFK        # Search by IATA code

```

### Weather Services
```

GET /v2/weather/metar/KJFK              # Current weather
GET /v2/weather/taf/KJFK                # Weather forecast

```

### Flight Information
```

GET /v2/airlines/search?icao=BAW        # Airline information
GET /v2/flight_status/BAW123            # Live flight tracking
GET /v2/schedules/arrivals?icao=KJFK    # Airport schedules

````

## 🔐 Authentication

SkyLink API requires an API key for authentication.  
Include your key in the request header:


## 📊 Response Examples

### Aircraft Tracking Response

```json
{
  "aircraft": [
    {
      "icao24": "A12345",
      "callsign": "BAW123",
      "registration": "G-ABCD",
      "latitude": 51.4706,
      "longitude": -0.4619,
      "altitude": 35000.0,
      "ground_speed": 450.5,
      "track": 089.2,
      "is_on_ground": false,
      "aircraft_type": "Boeing 777-300ER",
      "airline": "British Airways",
      "last_seen": "2025-09-27T12:00:00Z"
    }
  ],
  "total_count": 4691,
  "timestamp": "2025-09-27T12:00:00Z"
}
```


## 📈 Performance

* **Aircraft Tracking**: Processes 15M+ messages per day
* **Response Time**: < 100ms average for aircraft queries
* **Concurrent Users**: Designed for high-traffic production use
* **Database**: 615K+ enriched aircraft records


## 🆔 Version History

* **v2.0.0**: Production-ready release with enhanced authentication and performance
* **v1.0.0**: Initial release with core aviation data features

---

**SkyLink API** - Professional aviation data at your fingertips ✈️



**Built with ❤️ for the aviation community**