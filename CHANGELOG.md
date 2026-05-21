# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-XX

### Added
- Initial release of EAN Reader integration
- OpenFoodFacts API integration using official openfoodfacts-python library
- Barcode scanning via mobile_app.share events
- Local product database with manual mappings
- Shopping list auto-add functionality
- Two sensor entities: statistics and unknown products
- Rate limiting (12 req/min) to comply with OpenFoodFacts API limits
- Configurable contact email for User-Agent compliance
- Multi-language product name support (sv, en, de, fr, es)
- Optional price tracking feature
- Optional expiry date tracking feature
- Optional webhook support for external scanners
- Config flow with options for all features
- 10 services for product management
- 9 events for automation triggers
- Comprehensive error handling and logging
- HTTP 503 rate limit detection
- 24-hour caching of unknown products
- Export/import functionality for backups

### Services
- `add_mapping` - Add or update EAN to product name mapping
- `add_last_missing_mapping` - Map the last unknown scanned EAN
- `remove_mapping` - Remove an EAN from the database
- `lookup_product` - Force a lookup in OpenFoodFacts
- `add_scanned_to_shopping_list` - Add scanned EAN to shopping list
- `list_unknowns` - List all unknown products
- `export_mappings` - Export database to JSON
- `import_mappings` - Import mappings from JSON
- `add_price` - Add price tracking entry
- `set_expiry` - Set expiry date for product

### Events
- `ean_reader_product_scanned` - Fired on every scan
- `ean_reader_lookup_completed` - Fired after API lookup
- `ean_reader_missing_product` - Fired when product not found
- `ean_reader_mapping_added` - Fired when mapping created
- `ean_reader_mapping_removed` - Fired when mapping deleted
- `ean_reader_stats_updated` - Fired when statistics change
- `ean_reader_unknowns_list` - Response from list_unknowns service
- `ean_reader_export_complete` - Response from export_mappings service
- `ean_reader_import_complete` - Response from import_mappings service

### Technical
- Synchronous openfoodfacts library wrapped in executor jobs
- Conservative rate limiting to prevent IP bans
- Proper User-Agent format: `HomeAssistant-EANReader/1.0.0 (email)`
- Storage migration support from older versions
- Robust error handling for network issues
- Input sanitization for security
- Field selection for efficient API calls

### Documentation
- Comprehensive README with OpenFoodFacts legal requirements
- CONTRIBUTING.md with development guidelines
- LICENSE file with third-party license information
- GitHub issue templates for bugs and feature requests
- Pull request template
- HACS integration support

### Requirements
- Home Assistant 2024.1.0+
- openfoodfacts>=0.2.0 library
- Shopping List integration (optional)
