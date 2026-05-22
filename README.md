# EAN Reader for Home Assistant

Custom Home Assistant integration for scanning EAN/UPC barcodes and automatically managing your shopping list using the OpenFoodFacts database.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

## Before You Start

### OpenFoodFacts Requirements

This integration uses the [OpenFoodFacts](https://world.openfoodfacts.org/) database. **Before using this integration**, you must:

1. **Read** the [Terms and conditions of use and reuse](https://world.openfoodfacts.org/terms-of-use)
2. **Fill out** the [OpenFoodFacts API usage form](https://docs.google.com/forms/d/e/1FAIpQLSdIE3D8qvjC_zRJw1W8OmuHhsWJ_NSckiiniAHlfaVwUZCziQ/viewform) - This helps OpenFoodFacts understand real-world uses and prioritize improvements

### Legal & Licensing

- **OpenFoodFacts database**: [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1.0/)
- **Database contents**: [Database Contents License (DbCL)](https://opendatacommons.org/licenses/dbcl/1.0/)
- **Product images**: [Creative Commons Attribution ShareAlike (CC BY-SA 3.0)](https://creativecommons.org/licenses/by-sa/3.0/deed.en)
  - May contain graphical elements subject to copyright or other rights
  - May be reproduced under quotation rights or fair use

**Important**: All data is user-contributed and provided "as-is". For critical decisions, verify information independently. This integration is for personal home automation use. For commercial use, review OpenFoodFacts terms thoroughly.

## Features

- 📱 **Barcode Scanning** - Scan with any mobile barcode scanner app
- 🗄️ **Local Product Database** - Build your own mappings over time
- 🛒 **Shopping List Integration** - Auto-add items to Home Assistant shopping list
- 🌍 **OpenFoodFacts API** - Automatic product name lookup for millions of products
- 📊 **Statistics Tracking** - Monitor scan counts, hit rates, and unknown products
- 💰 **Price Tracking** (Optional) - Track price history per product
- 📅 **Expiry Management** (Optional) - Set and track expiry dates
- 🔗 **Webhook Support** (Optional) - Integrate external barcode scanners
- 🌐 **Multi-language** - Prioritize product names by language (sv, en, de, fr, es)
- 🚦 **Rate Limiting** - Built-in compliance with OpenFoodFacts API limits (15 req/min)
- 📈 **Two Sensor Entities** - Statistics and unknown products tracking

**Note**: All product data (names, images, ingredients, etc.) is retrieved from OpenFoodFacts and is user-contributed. This integration does not guarantee accuracy or completeness of product information.

## Installation

### HACS (Recommended)

1. Go to HACS → Integrations
2. Click the three dots menu → Custom repositories
3. Add: `https://github.com/swetoast/ha-ean-reader`
4. Category: Integration
5. Search for "EAN Reader"
6. Click Install
7. Restart Home Assistant
8. **Fill out** the [OpenFoodFacts API usage form](https://docs.google.com/forms/d/e/1FAIpQLSdIE3D8qvjC_zRJw1W8OmuHhsWJ_NSckiiniAHlfaVwUZCziQ/viewform)
9. Go to Settings → Devices & Services → Add Integration
10. Search for "EAN Reader" and configure

### Manual

1. Download the [latest release](https://github.com/swetoast/ha-ean-reader/releases)
2. Copy the `custom_components/ean_reader` folder to your `config/custom_components/` directory
3. Restart Home Assistant
4. **Fill out** the [OpenFoodFacts API usage form](https://docs.google.com/forms/d/e/1FAIpQLSdIE3D8qvjC_zRJw1W8OmuHhsWJ_NSckiiniAHlfaVwUZCziQ/viewform)
5. Go to Settings → Devices & Services → Add Integration
6. Search for "EAN Reader" and configure

## Configuration

### Initial Setup

1. Go to Settings → Devices & Services
2. Click Add Integration
3. Search for "EAN Reader"
4. **Enter your contact email** (required by OpenFoodFacts for API identification)
   - Format: `your-email@example.com`
   - Used in User-Agent: `HomeAssistant-EANReader/1.0.0 (your-email@example.com)`
   - Helps OpenFoodFacts identify your integration
5. Configure optional features:
   - Auto-add to shopping list (default: ON)
   - Show notifications (default: ON)
   - Show product images (default: ON)
   - Track prices (default: OFF)
   - Track expiry dates (default: OFF)
   - Enable webhook (default: OFF)
6. Done - integration is ready to use

### Options

After setup, click Configure on the EAN Reader integration to change:

- **Contact Email** - Your email for OpenFoodFacts API identification
- **Auto-add to Shopping List** - Automatically add recognized products
- **Show Notifications** - Get notified about scans and missing products
- **Show Images** - Display product images from OpenFoodFacts
- **Track Prices** - Enable price history tracking
- **Track Expiry** - Enable expiry date tracking
- **Enable Webhook** - Allow external barcode scanners to connect
- **Language Priority** - Preferred languages for product names (e.g., "sv,en,de")

## Usage

### Scanning with Mobile App

1. Use any barcode scanner app on your phone
2. Scan a product barcode
3. Share the barcode to Home Assistant (using the mobile app)
4. The integration automatically:
   - Looks up the product name in OpenFoodFacts
   - Saves it to your local database
   - Adds it to your shopping list (if enabled)
   - Shows a notification (if enabled)

### Manual Mapping

For products not in OpenFoodFacts or local stores:

```yaml
service: ean_reader.add_last_missing_mapping
data:
  name: "My Local Store Product"
  add_to_shopping_list: true
```

## Entities

### Sensor Entities

- **sensor.ean_reader_statistics**
  - State: Total scan count
  - Attributes:
    - `total_mappings`: Products in local database
    - `unknown_products`: Products needing names
    - `total_scans`: Total scans performed
    - `openfoodfacts_hits`: Successful API lookups
    - `local_hits`: Local database hits
    - `last_scan`: Last scanned EAN
    - `last_scan_time`: Timestamp of last scan

- **sensor.ean_reader_unknown_products**
  - State: Count of unknown products
  - Attributes:
    - `unknowns`: List of unknown products (top 20)
    - `total_unknown`: Total count
    - `last_missing_ean`: Last unknown EAN

### Binary Sensor (Diagnostic)

- **binary_sensor.ean_reader_api_problem**
  - State: ON when API issues detected, OFF when healthy
  - Device Class: Problem
  - Category: Diagnostic
  - Attributes:
    - `error_count`: Total API errors encountered
    - `rate_limited_count`: Number of times rate limited
    - `last_error`: Description of last error
    - `last_error_time`: When the last error occurred
    - `api_available`: Boolean indicating API health

  **Use for:**
  - Monitoring OpenFoodFacts API connectivity
  - Triggering alerts when rate limits are hit
  - Troubleshooting integration issues
  - Automations based on API health

## Services

### ean_reader.add_mapping

Add or update an EAN to product name mapping:

```yaml
service: ean_reader.add_mapping
data:
  ean: "7318690101234"
  name: "Oatly Oat Milk 1L"
  add_to_shopping_list: true
```

### ean_reader.add_last_missing_mapping

Map the last unknown scanned EAN:

```yaml
service: ean_reader.add_last_missing_mapping
data:
  name: "My Product Name"
  add_to_shopping_list: true
```

### ean_reader.remove_mapping

Remove an EAN from the database:

```yaml
service: ean_reader.remove_mapping
data:
  ean: "7318690101234"
```

### ean_reader.lookup_product

Force a lookup in OpenFoodFacts:

```yaml
service: ean_reader.lookup_product
data:
  ean: "3017624010701"
```

### ean_reader.add_scanned_to_shopping_list

Add a scanned EAN to the shopping list:

```yaml
service: ean_reader.add_scanned_to_shopping_list
data:
  ean: "3017624010701"
```

### ean_reader.list_unknowns

Fire an event with all unknown products (fires `ean_reader_unknowns_list` event).

### ean_reader.export_mappings

Export your database to JSON (fires `ean_reader_export_complete` event).

### ean_reader.import_mappings

Import mappings from exported data:

```yaml
service: ean_reader.import_mappings
data:
  data:
    version: 3
    mappings:
      "123456": {"name": "Product"}
  merge: true
```

### ean_reader.add_price

Add a price tracking entry (requires price tracking enabled):

```yaml
service: ean_reader.add_price
data:
  ean: "7318690101234"
  price: 25.90
  currency: "SEK"
```

### ean_reader.set_expiry

Set expiry date for a product (requires expiry tracking enabled):

```yaml
service: ean_reader.set_expiry
data:
  ean: "7318690101234"
  expiry_date: "2025-12-31"
```

## Events

Listen to these events in automations:

- **ean_reader_product_scanned** - Fired on every scan
- **ean_reader_lookup_completed** - Fired after API lookup
- **ean_reader_missing_product** - Fired when product not found
- **ean_reader_mapping_added** - Fired when mapping created
- **ean_reader_mapping_removed** - Fired when mapping deleted
- **ean_reader_stats_updated** - Fired when statistics change
- **ean_reader_unknowns_list** - Response from `list_unknowns` service
- **ean_reader_export_complete** - Response from `export_mappings` service
- **ean_reader_import_complete** - Response from `import_mappings` service

### Example Automation

**Notify on Unknown Product:**
```yaml
automation:
  - alias: "Notify on Unknown Product"
    trigger:
      - platform: event
        event_type: ean_reader_missing_product
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Unknown Product"
          message: "EAN {{ trigger.event.data.ean }} needs a name"
```

**Alert on API Problems:**
```yaml
automation:
  - alias: "Alert on OpenFoodFacts API Issues"
    trigger:
      - platform: state
        entity_id: binary_sensor.ean_reader_api_problem
        to: "on"
    action:
      - service: notify.persistent_notification
        data:
          title: "EAN Reader API Problem"
          message: >
            OpenFoodFacts API issue detected: 
            {{ state_attr('binary_sensor.ean_reader_api_problem', 'last_error') }}
```

## Rate Limiting

OpenFoodFacts enforces these limits to protect their infrastructure:
- **15 requests/minute/IP** for product queries (GET /api/v*/product)
- **10 requests/minute/IP** for search queries
- **HTTP 503** response if global limits exceeded
- **IP ban** possible for repeated violations

**Our Protection:**
- Conservative limit of **12 requests/minute** to stay safe
- Automatic queuing when limit approached
- Logs warnings at 80% capacity (9-10 requests)
- Does NOT cache products as "unknown" if rate limited
- Retries automatically after rate limit window expires

**User Experience:**
- Scans 1-12: Instant response
- Scan 13+: Automatic delay with log message
- No manual intervention needed
- Logs show: "Rate limit reached, waiting X seconds"

**Best Practices:**
- Avoid scanning 15+ products in one minute
- Use local mappings for frequently scanned items
- The integration's 24-hour cache prevents repeated API calls
- If rate limited, the integration handles it automatically

## Data Storage

All data stored in `.storage/ean_reader_mappings`:
- Product mappings (EAN → name)
- Unknown products list
- Statistics (scans, hits)
- Price history (if enabled)
- Expiry dates (if enabled)

**Backup recommended!** This file contains your entire product database.

## Troubleshooting

### Integration won't add

1. Verify internet connectivity
2. Ensure valid email address provided
3. Check you filled out the [API usage form](https://docs.google.com/forms/d/e/1FAIpQLSdIE3D8qvjC_zRJw1W8OmuHhsWJ_NSckiiniAHlfaVwUZCziQ/viewform)
4. Check Home Assistant logs for errors

### Products not being added to shopping list

- Enable Shopping List integration in Home Assistant
- Check "Auto-add to shopping list" is enabled in options
- Verify product was found (check logs or sensor attributes)

### OpenFoodFacts lookups failing

- Check internet connection
- Verify EAN is valid (8-14 digits)
- Some products may not be in OpenFoodFacts database - add manually
- Rate limits: Check logs for "Rate limit" messages
- API may be temporarily down - integration will retry automatically

### Wrong language for product names

- Configure language priority in integration options
- Format: Comma-separated language codes (e.g., "sv,en,de,fr,es")
- Languages are tried in order until a product name is found

### Sensors show "unavailable"

- Normal during initial setup before first scan
- Check if integration is properly configured
- Scan a product to populate sensor data

### Wrong product information

- Remember: All data is user-contributed to OpenFoodFacts
- You can correct it: Visit the product on openfoodfacts.org and edit
- Or: Use local mapping to override with your own name

## Attribution Requirements

When using this integration, you are re-using OpenFoodFacts data. As per the license terms:

**Required Attribution:**
- Mention that data comes from OpenFoodFacts
- Link to https://openfoodfacts.org
- For commercial use: Review [Terms of Use](https://world.openfoodfacts.org/terms-of-use) carefully

**This integration handles attribution in code, but if you:**
- Display product data on a website or app
- Re-distribute product information
- Use data for commercial purposes

Then you must provide proper attribution as specified in the OpenFoodFacts licenses.

## Contributing

Pull requests welcome! For bugs or feature requests, use [GitHub issues](https://github.com/swetoast/ha-ean-reader/issues).

### Development

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with real barcode scans
5. Verify rate limiting behavior
6. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

**This Integration:** MIT License - see [LICENSE](LICENSE) file

**OpenFoodFacts Data:**
- Database: [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1.0/)
- Contents: [Database Contents License (DbCL)](https://opendatacommons.org/licenses/dbcl/1.0/)
- Images: [Creative Commons Attribution ShareAlike (CC BY-SA 3.0)](https://creativecommons.org/licenses/by-sa/3.0/deed.en)

**Third-Party Libraries:**
- [openfoodfacts-python](https://github.com/openfoodfacts/openfoodfacts-python): MIT License

## Credits

- **Product Data**: [OpenFoodFacts](https://world.openfoodfacts.org/) - The free food products database made by everyone, for everyone
- **API Library**: [openfoodfacts-python](https://github.com/openfoodfacts/openfoodfacts-python) - Official Python SDK
- **Data Contributors**: Thousands of OpenFoodFacts contributors worldwide

## Support OpenFoodFacts

OpenFoodFacts is a non-profit project run by volunteers and a small team. If you find this integration useful, consider:

- **Contributing data**: Add products to openfoodfacts.org
- **Donating**: [Support their infrastructure](https://world.openfoodfacts.org/donate)
- **Spreading the word**: Tell others about OpenFoodFacts

## Disclaimer

**Not affiliated with OpenFoodFacts.** This integration retrieves product data from OpenFoodFacts' public API for personal home automation use.

**Data Accuracy**: Product data (names, ingredients, nutrition, images) is user-contributed and provided "as-is" without warranty. OpenFoodFacts does not guarantee accuracy, completeness, or timeliness. For critical decisions (allergies, dietary restrictions, medical purposes), verify information on the actual product packaging.

**Liability**: The integration developer and OpenFoodFacts cannot be held responsible for decisions made based on product data. Use at your own risk.

**Commercial Use**: For commercial use or bulk data access, review [OpenFoodFacts Terms of Use](https://world.openfoodfacts.org/terms-of-use) and consider [hosting your own instance](https://github.com/openfoodfacts/openfoodfacts-server) or using their [bulk data exports](https://world.openfoodfacts.org/data).

**Privacy**: Your contact email is sent in API requests as required by OpenFoodFacts. No other personal data is transmitted. Scanned barcodes are stored locally only.
