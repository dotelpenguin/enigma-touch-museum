# Changelog

All notable changes in the `brainstorm` branch compared to `main` branch.

## [Unreleased] - brainstorm branch

### Added

#### Error Handling & Validation
- **Generalized Error Detection**: Implemented pattern-based error detection for all Enigma device responses
  - Detects errors matching pattern: `^` + line return + `*** ` + error message
  - Automatically catches all error types (Invalid option, Duplicate mapping, Rotor used twice, etc.)
  - Extracts and displays actual error messages from device
- **Config Error Handling**: Enhanced error handling when sending configuration to Enigma device
  - Automatically switches to config menu when config errors are detected
  - Notifies user of specific configuration errors
  - Prevents message sending with invalid configuration
- **Input Validation**: Improved input handling in configuration menu
  - Clears input line before re-entering values on error
  - Requires re-entry of invalid configuration values
  - Better error messages for failed configuration attempts

#### Museum Mode Enhancements
- **Continuous Input Monitoring**: Added real-time monitoring of Enigma device input during museum mode
  - Detects unexpected user input during automated encoding
  - Pauses museum mode when user interacts with device
  - Resumes automatically after timeout period
- **Character Mismatch Detection**: Enhanced museum mode with character verification
  - Compares expected vs actual encoded characters
  - Automatically pauses on mismatch detection
  - Logs interruptions for debugging
- **Pre-coded Message Support**: Added support for pre-encoded messages
  - English and German pre-coded message files
  - JSON format for encoded messages with metadata
  - Automatic generation of coded messages from source files

#### Web Server Features
- **Web Interface**: Added HTTP web server for museum kiosk displays
  - Real-time message display page (`/message`)
  - Status page showing device configuration (`/status`)
  - Auto-refresh every 2 seconds
  - Character highlighting when delay >= 2000ms
- **Web Server Configuration**: Configurable web server settings
  - Enable/disable web server via menu
  - Configurable port (default: 8080)
  - Displays IP address when server starts

#### Slides Feature
- **Slide Support**: Added slideshow functionality for museum displays
  - Image slides change every 10 characters during encoding
  - Support for common slides folder
  - Per-message numbered slide folders
  - Configurable slide paths

#### Configuration Improvements
- **Enhanced Config Menu**: Expanded configuration options
  - Word group size configuration (4 or 5 characters)
  - Character delay configuration (milliseconds)
  - Always send config before message toggle
  - Device path configuration
  - Web server port configuration
- **Config Persistence**: Improved configuration file handling
  - Preserves device path when reloading config
  - Ring position protection (updates during encoding not saved)
  - Better handling of missing config values

#### Debug Features
- **Debug Panel**: Enhanced debugging capabilities
  - Optional debug panel in terminal interface
  - Color-coded debug messages (match/mismatch/error)
  - Real-time serial communication logging
  - Toggle debug mode via menu or command line
- **Debug Output**: Improved debug message handling
  - Color type support for error highlighting
  - Better formatting of serial communication
  - Debug callback support throughout codebase

#### Message Generation
- **Coded Message Generation**: Added tools for generating pre-coded messages
  - Generate English coded messages (`english-encoded.json`)
  - Generate German coded messages (`german-encoded.json`)
  - Preserves original message metadata
  - Batch processing with progress display

#### Platform Support
- **macOS Support**: Added macOS-specific improvements
  - Better device path detection (`/dev/cu.*` vs `/dev/tty.*`)
  - macOS-specific installation instructions
  - USB accessory permission handling

### Changed

#### Code Structure
- **Major Refactoring**: Significant code improvements and organization
  - Better separation of concerns
  - Improved error handling throughout
  - Enhanced type hints and documentation
  - Code cleanup and optimization

#### Error Messages
- **Improved Error Reporting**: Better error messages throughout application
  - More descriptive error messages
  - Context-aware error reporting
  - User-friendly error notifications

#### Configuration Handling
- **Config Loading**: Improved configuration file loading
  - Better default value handling
  - Preserves device settings when appropriate
  - More robust error recovery

### Fixed

#### Bug Fixes
- **Museum Mode Config**: Fixed issue where museum mode wasn't using message array configuration
  - Now properly loads and applies config from message objects
  - Ensures correct settings for each message
- **Debug Log**: Fixed missing last item in debug log display
- **Input Clearing**: Fixed input line not clearing on error (now clears before re-entry)
- **Config Error Handling**: Fixed TypeError when debug callbacks receive color_type parameter
  - All debug callbacks now properly accept color_type parameter
  - Consistent error message formatting

### Documentation

#### Added Documentation
- **Protocol Documentation**: Added `ENIGMA_PROTOCOL_DOCUMENTATION.md`
  - Complete serial communication protocol reference
  - Command and response formats
  - Error message documentation
  - Usage examples

#### Updated Documentation
- **README Updates**: Enhanced README with new features
  - Web server documentation
  - Configuration menu details
  - Troubleshooting section
  - Platform-specific instructions
- **Configuration Summary**: Added `Enigma_Configuration_Summary.csv`
  - Reference for valid configuration values
  - Example configurations

### Files Added
- `english-encoded.json` - Pre-coded English messages
- `german-encoded.json` - Pre-coded German messages
- `ENIGMA_PROTOCOL_DOCUMENTATION.md` - Protocol documentation
- `Enigma_Configuration_Summary.csv` - Configuration reference
- `bugs.md` - Bug tracking
- `facts.md` - Facts file (empty)
- `ATTRIBUTION.md` - Attribution information
- `slides/common/` - Slide images for museum display

### Files Modified
- `enigma-museum.py` - Major enhancements (2338+ lines changed)
- `README.md` - Updated documentation
- `enigma-museum-config.json` - Enhanced configuration format
- `requirements.txt` - Updated dependencies
- `english.msg` - Minor updates

### Technical Details

#### Error Detection Pattern
The new error detection uses regex pattern matching:
- Primary pattern: `^\r\n*** ` or `^\n*** ` followed by error message
- Fallback pattern: `*** ` at start of line for compatibility
- Extracts actual error message text from device response

#### Configuration Error Flow
1. Config sent to device via serial command
2. Response checked for error pattern
3. If error detected:
   - Error message logged to debug output
   - User notified with specific error
   - Application switches to config menu
   - User must fix configuration before continuing

#### Museum Mode Improvements
- Real-time character comparison
- Automatic pause on mismatch
- User input detection
- Configurable pause timeout
- Better logging and debugging

---

## Comparison Summary

**Lines Changed**: ~2,881 insertions, ~601 deletions across 14 files

**Major Feature Additions**:
- Web server with real-time display
- Slideshow support
- Enhanced error handling
- Pre-coded message generation
- macOS support improvements
- Debug panel enhancements

**Key Improvements**:
- Better error detection and handling
- More robust configuration management
- Enhanced museum mode functionality
- Improved user experience
- Better documentation

---

*This changelog compares the `brainstorm` branch to the `main` branch. For specific commit details, see the git log.*
