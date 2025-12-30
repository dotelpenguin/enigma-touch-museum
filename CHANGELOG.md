# Changelog

## [Unreleased] - develop-4_21 branch

### Added Features

**Firmware Version Checking**
- Automatic firmware version detection on device connection
- Queries firmware using `?FW` command (firmware 4.21+)
- Falls back to `?LM` command for firmware 4.20 detection
- Displays firmware version in console output and TUI header
- Shows warning if firmware 4.20 detected (4.21 recommended)
- Exits with error if firmware is below 4.20 (minimum required)
- Firmware version stored as float (e.g., 4.21, 4.20)

**Factory Reset Feature**
- New main menu option: "Factory Reset Enigma" (option 7)
- Sends `!RS` command to reset device to factory defaults
- Includes confirmation prompt to prevent accidental resets
- Displays success/error messages with scrolling text display
- Can be used to unlock device if locked out by kiosk settings

### Changed

**Configuration File Structure**
- Reorganized config file into logical sections:
  - `config`: Cipher settings (mode, rotor_set, ring_settings, ring_position, pegboard) + device, raw_debug_enabled, use_models_json
  - `museum_config`: Museum/application settings (function_mode, museum_delay, always_send_config, word_group_size, character_delay_ms, web_server_enabled, web_server_port, enable_slides)
  - `touch_config`: Enigma Touch device settings (lock_model, lock_rotor, lock_ring, disable_power_off, brightness, volume, screen_saver, timeout_battery, timeout_plugged, timeout_setup_modes)
- Maintains backward compatibility with old flat structure
- Removed duplicate values from config file

**Menu Organization**
- Renamed menu options for clarity:
  - "Set Enigma Config" → "Send Enigma Config"
  - "Set Kiosk/Lock Config" → "Send Enigma Lock Config"
  - "Enigma Options" → "Enigma Cipher Options"
  - "Kiosk Options" → "Enigma Touch Device Options"
- Added "Factory Reset Enigma" as main menu option 7
- Debug options renumbered to 8 and 9

**Device Settings**
- Extended volume range from 0-3 to 0-6
- Updated validation, UI prompts, and documentation

**Museum Mode Behavior**
- Museum mode cipher config changes (mode, rotors, rings, pegboard) are now memory-only
- Cipher settings from JSON message objects are not saved to disk
- Only `function_mode` changes are persisted during museum mode
- Added `preserve_cipher_config` parameter to prevent saving temporary cipher config changes

**Application Version**
- Updated to v4.21.beta

### Removed

- Removed CHANGELOG.md file (recreated with new structure)

### Technical Details

**Firmware Detection Flow**
1. Send `\r\n` then `?FW\r\n` command
2. If "Firmware XXX" response: Parse version (e.g., "421" → 4.21)
3. If "*** Invalid command": Fall back to `?LM\r\n`
4. If `?LM` returns "Lock model setup": Set version to 4.20 with warning
5. If `?LM` also returns "Invalid command": Exit with error (firmware too old)

**Config Preservation**
- `preserve_cipher_config=True` prevents museum mode from overwriting saved cipher settings
- `preserve_ring_position=True` prevents encoding updates from overwriting saved ring position
- Both preservation mechanisms work independently

---

**Files Changed**: 5 files modified, 1 file deleted
- `enigma/config.py` - New structure support with backward compatibility
- `enigma/enigma_controller.py` - Firmware checking, factory reset, config structure updates
- `enigma/ui.py` - Menu renames, factory reset UI, museum mode improvements
- `enigma-museum-config.json` - Reorganized structure
- `CHANGELOG.md` - Removed (recreated)

**Backward Compatibility**: All changes maintain backward compatibility with existing config files using the old flat structure.

