# Enigma Museum Controller

A Python-based control system for Enigma cipher machines, featuring a curses-based terminal interface and web server for museum displays.

## Features

- **Interactive Terminal Interface**: Full curses-based menu system for controlling Enigma devices
- **Museum Mode**: Automated demonstration modes with configurable delays
- **Web Server**: Real-time web interface for museum kiosk displays
- **Message Encoding**: Send and encode messages character by character
- **Configuration Management**: Persistent settings with JSON configuration file
- **Debug Mode**: Optional serial communication debugging
- **Multiple Museum Modes**: Support for English and German messages, with optional pre-coded messages

## Requirements

- Python 3.x
- pyserial (for serial communication)
- Linux/Unix system (for serial device access)
- Enigma device connected via serial (USB serial adapter)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd enigma-touch-museum
```

2. Install dependencies:
```bash
pip install pyserial
```

3. Ensure you have permission to access the serial device:
```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

## Configuration

The application uses `enigma-museum-config.json` for persistent configuration. You can configure:

- **Device Path**: Serial device path (e.g., `/dev/ttyACM0`)
- **Enigma Settings**: Mode, rotor set, ring settings, ring position, pegboard
- **Museum Delay**: Delay between messages in museum mode (seconds)
- **Character Delay**: Delay between characters during encoding (milliseconds)
- **Word Group Size**: Group size for encoded text display (4 or 5 characters)
- **Web Server**: Enable/disable and port configuration

### Initial Configuration

If the device is not connected, use the `--config` option to configure settings:

```bash
python3 enigma-museum.py --config
```

## Usage

### Basic Usage

```bash
python3 enigma-museum.py [OPTIONS] [DEVICE]
```

### Command-Line Options

- `--config`, `-c`: Open configuration menu without connecting to device
- `--museum-en`: Start directly in Museum EN mode (English messages)
- `--museum-de`: Start directly in Museum DE mode (German messages)
- `--museum-en-coded`: Start in Museum EN mode with pre-coded messages
- `--museum-de-coded`: Start in Museum DE mode with pre-coded messages
- `--debug`: Enable debug output panel (shows serial communication)
- `--help`, `-h`: Show help message and exit

### Examples

```bash
# Start with default device
python3 enigma-museum.py

# Configure settings without connecting
python3 enigma-museum.py --config

# Start directly in Museum EN mode
python3 enigma-museum.py --museum-en

# Start with specific device and debug enabled
python3 enigma-museum.py --debug /dev/ttyACM0

# Start Museum DE mode with pre-coded messages
python3 enigma-museum.py --museum-de-coded
```

## Main Menu Options

1. **Send Message**: Manually send and encode a message
2. **Museum Mode**: Start automated museum demonstration
3. **Configuration**: Access configuration menu
4. **Query Settings**: Query current device settings
5. **Set All Config**: Set all configurations from saved config
6. **Debug**: Toggle debug output panel

## Museum Modes

- **Museum EN**: English messages, encoded on-the-fly
- **Museum DE**: German messages, encoded on-the-fly
- **Museum EN (Coded)**: English messages, using pre-coded messages
- **Museum DE (Coded)**: German messages, using pre-coded messages

## Web Server

The web server provides real-time updates for museum displays:

- **Status Page** (`/status`): Detailed status view with all information
- **Message Page** (`/message`): Kiosk display optimized for 1024x768+ screens
  - Shows current message being encoded
  - Displays encoded text in real-time
  - Highlights current character (when delay >= 2000ms)
  - Updates ring position in real-time
  - Auto-refreshes every 2 seconds

### Enabling Web Server

1. Go to Configuration menu → Option 14: Web Server
2. Enable the web server
3. Configure the port (default: 8080)
4. Access at `http://<your-ip>:<port>/message` for kiosk view

## Configuration Menu

Access via Main Menu → Configuration:

1. Set Mode (I, II, III, M3, M4)
2. Set Rotor Set (e.g., "A III IV I")
3. Set Ring Settings (e.g., "01 01 01")
4. Set Ring Position (e.g., "20 6 10")
5. Set Pegboard (e.g., "VF PQ" or leave empty for clear)
6. Set Museum Delay (seconds between messages)
7. Always Send Config Before Message (toggle)
8. Set Word Group Size (4 or 5 characters)
9. Set Character Delay (milliseconds between characters)
10. Generate Coded Messages - EN
11. Generate Coded Messages - DE
12. Set Device (serial device path)
13. Set Web Server Port
14. Web Server Enable/Disable

## Message Files

- `english.msg`: English messages for museum mode
- `german.msg`: German messages for museum mode
- `english-coded.msg`: Pre-coded English messages (generated)
- `german-coded.msg`: Pre-coded German messages (generated)

## Features

### Character Highlighting

When character delay is 2000ms or greater, the current character being encoded is highlighted in yellow on the web interface.

### Real-Time Updates

- Encoded text updates as each character is encoded
- Ring position updates in real-time during encoding
- Web interface auto-refreshes every 2 seconds

### Ring Position Protection

Ring position updates during encoding are not saved to the config file. Only explicit changes via the configuration menu are persisted.

## Troubleshooting

### Cannot Connect to Device

1. Check device path: `ls -l /dev/ttyACM*` or `ls -l /dev/ttyUSB*`
2. Verify permissions: `groups` (should include `dialout`)
3. Use `--config` to change device path without connecting

### Web Server Not Starting

1. Check if port is already in use: `netstat -tuln | grep <port>`
2. Verify web server is enabled in configuration
3. Check firewall settings

### Messages Not Encoding

1. Enable debug mode (`--debug` or menu option 6)
2. Check serial communication in debug panel
3. Verify device is in encode mode
4. Check message contains only A-Z characters (spaces and special chars are filtered)

## License

See LICENSE file for details.

## Author

Andrew Baker (DotelPenguin)

