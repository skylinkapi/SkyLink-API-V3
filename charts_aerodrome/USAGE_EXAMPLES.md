# Usage Examples for Aerodrome Charts CLI Tool

## Installation

```bash
# Install required dependencies
pip install -r requirements.txt
```

## Basic Usage

### Get charts for a specific airport

```bash
python aerodrome_charts_cli.py KJFK
```

### Use verbose mode for debugging

```bash
python aerodrome_charts_cli.py KJFK --verbose
```

## Example Outputs

### Example 1: JFK Airport (KJFK)
```bash
python aerodrome_charts_cli.py KJFK
```

Output shows:
- **GEN**: 2 charts (Alternate Minimums, Takeoff Minimums)
- **SID**: 6 departure procedures
- **STAR**: 6 arrival procedures  
- **APP**: 25 approach procedures

### Example 2: Los Angeles (KLAX)
```bash
python aerodrome_charts_cli.py KLAX
```

Output shows:
- **GEN**: 2 charts
- **SID**: 40 departure procedures
- **STAR**: 34 arrival procedures
- **APP**: 26 approach procedures

### Example 3: San Francisco (KSFO)
```bash
python aerodrome_charts_cli.py KSFO
```

Output shows:
- **GEN**: 3 charts
- **SID**: 12 departure procedures
- **STAR**: 14 arrival procedures
- **APP**: 21 approach procedures

## Common US Airport Codes

- **KJFK** - John F. Kennedy International (New York)
- **KLAX** - Los Angeles International
- **KORD** - Chicago O'Hare
- **KATL** - Atlanta Hartsfield-Jackson
- **KDFW** - Dallas/Fort Worth
- **KDEN** - Denver International
- **KSFO** - San Francisco International
- **KSEA** - Seattle-Tacoma
- **KLAS** - Las Vegas McCarran
- **KMCO** - Orlando International
- **KMIA** - Miami International
- **KBOS** - Boston Logan
- **KPHX** - Phoenix Sky Harbor
- **KIAH** - Houston Intercontinental

## Chart Categories Explained

### GEN (General)
- Airport minimums
- Takeoff minimums
- Alternate minimums
- Diverse vector areas
- General information charts

### GND (Ground)
- Airport diagrams (layout)
- Taxi diagrams
- Hot spots
- LAHSO (Land and Hold Short Operations)

### SID (Standard Instrument Departure)
- Named departure procedures
- DP (Departure Procedure) charts
- RNAV SIDs
- Conventional SIDs

### STAR (Standard Terminal Arrival)
- Named arrival procedures
- RNAV STARs
- Conventional STARs

### APP (Approach)
- ILS (Instrument Landing System)
- LOC (Localizer)
- RNAV (Area Navigation)
- GPS approaches
- VOR approaches
- Visual approaches
- Category II/III approaches

## Troubleshooting

### Airport not found
```bash
python aerodrome_charts_cli.py XXXX
```
**Error**: `Airport XXXX not found in FAA database`

**Solution**: 
- Verify the ICAO code is correct
- FAA database only contains US airports
- Try with the K prefix for US airports (e.g., KJFK instead of JFK)

### No charts found
If no charts are returned, the airport might not have published instrument procedures.

### Network errors
If you get connection errors:
- Check your internet connection
- The FAA website might be temporarily unavailable
- Try again later

## Advanced Usage

### Redirect output to file
```bash
python aerodrome_charts_cli.py KJFK > kjfk_charts.txt
```

### Get charts for multiple airports
```bash
for code in KJFK KLAX KSFO; do python aerodrome_charts_cli.py $code; done
```

## Integration with Other Tools

The tool outputs clean text that can be:
- Piped to other commands
- Redirected to files
- Parsed by scripts
- Used in automation workflows

## Future Enhancements

Planned features:
- Direct PDF download capability
- Export to JSON/CSV format
- Support for EASA and other aviation authorities
- Batch processing for multiple airports
- Chart update notifications
