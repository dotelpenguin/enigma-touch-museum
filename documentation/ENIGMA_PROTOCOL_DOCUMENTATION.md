# Enigma Serial Communication Protocol Documentation

## Serial Configuration

- **Baud Rate**: 9600
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Flow Control**: None

## Command Format

All commands must follow this format:
```
\r\n[COMMAND]\r\n
```

**Important**: Commands must start with a carriage return + line feed (`\r\n`), followed by the command, then end with `\r\n`.

## Query Commands (Get Configuration)

### ?MO - Query Mode/Model
**Command**: `\r\n?MO\r\n`

**Response Format**:
```
\r\n?MO\r\nEnigma    I\x00\r\n
```

**Response Content**: Returns the Enigma model (e.g., "Enigma    I")

**Notes**: 
- The `?MO` command appears to return the model information, not the current mode
- To return to encode mode, simply send `?MO\r\n` (without the leading `\r\n`)

---

### ?RO - Query Rotor Set
**Command**: `\r\n?RO\r\n`

**Response Format**:
```
\r\n?RO\r\nReflector A\r\nRotors    III II I\r\n
```

**Response Content**: 
- Reflector type (e.g., "A", "B", "C")
- Rotor configuration (e.g., "III II I")

**Example Response**:
```
?RO
Reflector A
Rotors    III II I
```

---

### ?RI - Query Ring Settings
**Command**: `\r\n?RI\r\n`

**Response Format**:
```
\r\n?RI\r\nRings     01 01 01\r\n
```

**Response Content**: Ring settings as three two-digit numbers (01-26)

**Example Response**:
```
?RI
Rings     01 01 01
```

---

### ?RP - Query Ring Position
**Command**: `\r\n?RP\r\n`

**Response Format**:
```
\r\n?RP\r\nPositions 01 01 10\r\n
```

**Response Content**: Current rotor positions as three two-digit numbers (01-26)

**Example Response**:
```
?RP
Positions 01 01 10
```

---

### ?PB - Query Pegboard Settings
**Command**: `\r\n?PB\r\n`

**Response Format**:
```
\r\n?PB\r\nPlugboard clear\r\n
```
or
```
\r\n?PB\r\nPlugboard AB CD EF \r\n
```

**Response Content**: 
- "Plugboard clear" if no connections
- "Plugboard [pairs]" if connections exist (space-separated pairs like "AB CD EF")

**Example Responses**:
```
?PB
Plugboard clear
```
```
?PB
Plugboard AB CD EF 
```

---

## Set Commands (Configure Device)

### !MO - Set Model
**Command**: `\r\n!MO [MODEL]\r\n`

**Accepted Values**: 
- Model name (e.g., "I", "M3", "M4")
- **Note**: This sets the Enigma model type, not the operating mode

**Example**:
```
\r\n!MO I\r\n
```

**Error Responses**:
- `*** Space expected` - Missing space between command and value
- `*** Unknown model` - Invalid model name

---

### !RO - Set Rotor Set
**Command**: `\r\n!RO [CONFIGURATION]\r\n`

**Accepted Values**: 
- Rotor configuration format needs further investigation
- Current format appears to be: `[Reflector] [Rotor3] [Rotor2] [Rotor1]`
- Example: `A III II I` (Reflector A, Rotors III, II, I)

**Error Responses**:
- `*** Invalid option` - Invalid rotor configuration

**Note**: Exact format requires more testing

---

### !RI - Set Ring Settings
**Command**: `\r\n!RI [RING1] [RING2] [RING3]\r\n`

**Accepted Values**: 
- Three two-digit numbers (01-26) separated by spaces
- Each number represents the ring setting for each rotor

**Examples**:
```
\r\n!RI 01 01 01\r\n    # All rings at position 01
\r\n!RI 05 10 15\r\n    # Rings at 05, 10, 15
\r\n!RI 26 26 26\r\n    # All rings at position 26
```

**Response**: Echoes the command and returns current ring settings

---

### !RP - Set Ring Position
**Command**: `\r\n!RP [POS1] [POS2] [POS3]\r\n`

**Accepted Values**: 
- **Letters**: Single letters A-Z (converted to 01-26)
- **Numbers**: Two-digit numbers 01-26
- Can mix letters and numbers

**Examples**:
```
\r\n!RP A A A\r\n       # Sets positions to 01 01 01
\r\n!RP A B C\r\n       # Sets positions to 01 02 03
\r\n!RP 01 02 03\r\n    # Sets positions to 01 02 03
\r\n!RP 05 10 15\r\n    # Sets positions to 05 10 15
```

**Response**: Echoes the command and returns current positions

---

### !PB - Set Pegboard Settings
**Command**: `\r\n!PB [PAIRS]\r\n`

**Accepted Values**: 
- Space-separated letter pairs (e.g., "AB CD EF")
- **No dashes**: Use spaces, not dashes (e.g., "AB CD" not "A-B C-D")
- **No "clear"**: Cannot use "clear" as a parameter
- Each pair connects two letters (e.g., "AB" connects A and B)

**Examples**:
```
\r\n!PB AB CD EF\r\n    # Connects A-B, C-D, E-F
\r\n!PB AB CD\r\n       # Connects A-B, C-D
```

**Error Responses**:
- `*** Too few parameters` - Missing pairs or invalid format
- `*** Letter expected` - Invalid character in pair

**Response**: Echoes the command and returns current pegboard settings

---

## Version 4.20 Commands (Demo/Kiosk Mode)

### Locking Setup Modes and Power-Off Button

The setup modes for Model selection and replica settings, Rotor (= Wheel) selection, and Ring settings can be locked. The modes will still be accessible via the front panel buttons to view the current settings, but will not respond to the sliders. A lock icon in the upper left display window indicates when a mode is locked.

#### !LM - Lock/Unlock Model Setup Mode
**Command**: `\r\n!LM [VALUE]\r\n`

**Accepted Values**:
- `1` - Locks access via the front panel button
- `0` - Unlocks access

**Query Command**: `\r\n?LM\r\n` - Prints access status

**Notes**:
- `!LM` also controls access to the Reflector D re-wiring (long press of Modell button) and Diagnostic Mode (very long press)
- When locked, the mode is still viewable but sliders won't respond

**Examples**:
```
\r\n!LM 1\r\n    # Lock model setup mode
\r\n!LM 0\r\n    # Unlock model setup mode
\r\n?LM\r\n      # Query lock status
```

---

#### !LW - Lock/Unlock Rotor (Wheel) Setup Mode
**Command**: `\r\n!LW [VALUE]\r\n`

**Accepted Values**:
- `1` - Locks access via the front panel button
- `0` - Unlocks access

**Query Command**: `\r\n?LW\r\n` - Prints access status

**Notes**:
- The long-press function of the Rotor button remains available even if the setup mode is locked

**Examples**:
```
\r\n!LW 1\r\n    # Lock rotor setup mode
\r\n!LW 0\r\n    # Unlock rotor setup mode
\r\n?LW\r\n      # Query lock status
```

---

#### !LR - Lock/Unlock Ring Setup Mode
**Command**: `\r\n!LR [VALUE]\r\n`

**Accepted Values**:
- `1` - Locks access via the front panel button
- `0` - Unlocks access

**Query Command**: `\r\n?LR\r\n` - Prints access status

**Notes**:
- The long-press function of the Ring button remains available even if the setup mode is locked

**Examples**:
```
\r\n!LR 1\r\n    # Lock ring setup mode
\r\n!LR 0\r\n    # Unlock ring setup mode
\r\n?LR\r\n      # Query lock status
```

---

#### !LP - Lock/Unlock Power-Off Button
**Command**: `\r\n!LP [VALUE]\r\n`

**Accepted Values**:
- `1` - Disables the power-off functionality of the power button
- `0` - Re-enables power-off functionality

**Query Command**: `\r\n?LP\r\n` - Prints lock status

**Notes**:
- When the power-off button is locked, the Enigma touch can only be powered off by:
  - (a) Removing external power (if no battery installed)
  - (b) An inactivity timeout
  - (c) The USB command `!PO`
- The power button will still be used to turn the power ON

**Examples**:
```
\r\n!LP 1\r\n    # Disable power-off button
\r\n!LP 0\r\n    # Enable power-off button
\r\n?LP\r\n      # Query lock status
```

---

### Control User Interface Settings

The following commands control the UI settings. They are mainly meant for use with an external "museum mode controller". As usual, `?Mx` can be used to view the current setting.

#### !MB - Set Brightness
**Command**: `\r\n!MB [LEVEL]\r\n`

**Accepted Values**:
- `1` through `5` - Brightness level (1 = dimmest, 5 = brightest)

**Query Command**: `\r\n?MB\r\n` - Returns current brightness level

**Examples**:
```
\r\n!MB 3\r\n    # Set brightness to level 3
\r\n!MB 5\r\n    # Set brightness to maximum
\r\n?MB\r\n      # Query current brightness
```

---

#### !MV - Set Volume
**Command**: `\r\n!MV [LEVEL]\r\n`

**Accepted Values**:
- `0` through `6` - Volume level (0 = silent, 6 = maximum)

**Query Command**: `\r\n?MV\r\n` - Returns current volume level

**Examples**:
```
\r\n!MV 0\r\n    # Set volume to silent
\r\n!MV 3\r\n    # Set volume to level 3
\r\n!MV 6\r\n    # Set volume to maximum
\r\n?MV\r\n      # Query current volume
```

---

#### !ML - Set Logging Format
**Command**: `\r\n!ML [FORMAT]\r\n`

**Accepted Values**:
- `1` - Short format, 5 characters per group
- `2` - Short format, 4 characters per group
- `3` - Extended format, 5 characters per group
- `4` - Extended format, 4 characters per group

**Query Command**: `\r\n?ML\r\n` - Returns current logging format

**Notes**:
- `!ML` only supports those settings which keep the USB serial connection active
- Keyboard mode or completely disabled USB can only be selected from the front panel
- This prevents locking yourself out of USB communication

**Examples**:
```
\r\n!ML 1\r\n    # Set to short format, 5 chars per group
\r\n!ML 3\r\n    # Set to extended format, 5 chars per group
\r\n?ML\r\n      # Query current logging format
```

---

### Timeout Control

Earlier firmware versions had a fixed inactivity timeout (automatic power-off) of 15 minutes in battery-operated mode, and no timeout when operated on an external 5V supply. Version 4.20 gives you control over these timeouts and adds an optional screen saver.

All times are given in minutes, with valid values from 1..99. Value 0 disables the respective automatic timeout.

#### !TB - Set Battery Power-Off Timeout
**Command**: `\r\n!TB [MINUTES]\r\n`

**Accepted Values**:
- `0` - Disables automatic power-off timeout
- `1` through `99` - Timeout in minutes

**Query Command**: `\r\n?TB\r\n` - Returns current timeout setting

**Default**: 15 minutes

**Examples**:
```
\r\n!TB 15\r\n   # Set timeout to 15 minutes (default)
\r\n!TB 30\r\n   # Set timeout to 30 minutes
\r\n!TB 0\r\n    # Disable timeout
\r\n?TB\r\n      # Query current timeout
```

---

#### !TP - Set Plugged-In Power-Off Timeout
**Command**: `\r\n!TP [MINUTES]\r\n`

**Accepted Values**:
- `0` - Disables automatic power-off timeout (default)
- `1` through `99` - Timeout in minutes

**Query Command**: `\r\n?TP\r\n` - Returns current timeout setting

**Default**: 0 (disabled)

**Examples**:
```
\r\n!TP 0\r\n    # Disable timeout (default)
\r\n!TP 60\r\n    # Set timeout to 60 minutes when plugged in
\r\n?TP\r\n      # Query current timeout
```

---

#### !TS - Set Screen Saver Timeout
**Command**: `\r\n!TS [MINUTES]\r\n`

**Accepted Values**:
- `0` - Disables screen saver
- `1` through `99` - Timeout in minutes before screen saver activates

**Query Command**: `\r\n?TS\r\n` - Returns current screen saver timeout

**Default**: 10 minutes

**Examples**:
```
\r\n!TS 10\r\n   # Set screen saver to 10 minutes (default)
\r\n!TS 5\r\n    # Set screen saver to 5 minutes
\r\n!TS 0\r\n    # Disable screen saver
\r\n?TS\r\n      # Query current screen saver timeout
```

---

#### !TM - Set Setup Mode Inactivity Timeout
**Command**: `\r\n!TM [SECONDS]\r\n`

**Accepted Values**:
- `0` - Disables automatic timeout (default)
- `1` through `99` - Timeout in seconds

**Query Command**: `\r\n?TM\r\n` - Returns current timeout setting

**Notes**:
- After a specified inactivity period, the Enigma touch can revert to its regular encryption mode
- Unlike other timeout commands, this timeout is specified in **seconds** rather than minutes

**Default**: 0 (disabled)

**Examples**:
```
\r\n!TM 0\r\n    # Disable setup mode timeout (default)
\r\n!TM 30\r\n   # Close setup modes after 30 seconds of inactivity
\r\n!TM 60\r\n   # Close setup modes after 60 seconds of inactivity
\r\n?TM\r\n      # Query current timeout
```

---

## Character Encoding

### Format
When sending a single ASCII character (no line return), the device responds with:

```
[Original] [Encoded]   Positions [rotor1] [rotor2] [rotor3]\r\n
```

**Example Responses**:
```
H G   Positions 01 01 06\r\n
E W   Positions 01 01 07\r\n
L E   Positions 01 01 08\r\n
```

**Format Details**:
- Original character (what was sent)
- Encoded character (Enigma output)
- Three spaces
- "Positions"
- Three two-digit numbers representing rotor positions

**Notes**:
- Only printable ASCII characters (0x20-0x7E) are encoded
- Numbers and spaces may return minimal or no response
- Each character must be sent individually
- Wait for response before sending next character

---

## Reset Sequence

### Reset to Get Model Information
**Command**: `\r?MO\r\n\r\n`

**Response Format**:
```
\r\n?MO\r\nEnigma    I\x00\r\n\r\n
```

**Purpose**: Resets the device and returns model information. Useful for recovery if device stops responding.

**Usage**: Send this sequence if no response is received after sending a character.

---

## Error Messages

Common error messages:
- `*** Space expected` - Missing space in command
- `*** Unknown model` - Invalid model name
- `*** Invalid option` - Invalid configuration value
- `*** Too few parameters` - Missing required parameters
- `*** Letter expected` - Invalid character in command

---

## Protocol Summary

### Command Structure
1. **Query Commands**: Start with `?` (e.g., `?MO`, `?RO`, `?RI`, `?RP`, `?PB`, `?LM`, `?LW`, `?LR`, `?LP`, `?MB`, `?MV`, `?ML`, `?TB`, `?TP`, `?TS`, `?TM`)
2. **Set Commands**: Start with `!` (e.g., `!MO`, `!RO`, `!RI`, `!RP`, `!PB`, `!LM`, `!LW`, `!LR`, `!LP`, `!MB`, `!MV`, `!ML`, `!TB`, `!TP`, `!TS`, `!TM`)
3. **All commands**: Must be prefixed with `\r\n` and suffixed with `\r\n`

### Character Encoding Protocol
1. Send one character at a time (no line return)
2. Wait for response before sending next character
3. Response includes: original char, encoded char, and rotor positions
4. If no response within timeout, send reset: `\r?MO\r\n\r\n`

### Configuration Workflow
1. Enter configuration mode: Send `\r\n` (blank line)
2. Send configuration command: `\r\n![COMMAND] [VALUE]\r\n`
3. Query to verify: `\r\n?[COMMAND]\r\n`
4. Return to encode mode: Send `?MO\r\n` (without leading `\r\n`)

---

## Testing Notes

- Device responds immediately to most commands
- Configuration changes take effect immediately
- Character encoding is real-time
- Rotor positions advance with each character encoded
- Model information is static (Enigma I in tested device)

---

## Example Usage

### Query All Configuration
```python
# Query mode/model
ser.write(b'\r\n?MO\r\n')

# Query rotor set
ser.write(b'\r\n?RO\r\n')

# Query ring settings
ser.write(b'\r\n?RI\r\n')

# Query ring position
ser.write(b'\r\n?RP\r\n')

# Query pegboard
ser.write(b'\r\n?PB\r\n')
```

### Set Configuration
```python
# Set ring positions to A B C
ser.write(b'\r\n!RP A B C\r\n')

# Set ring settings
ser.write(b'\r\n!RI 05 10 15\r\n')

# Set pegboard
ser.write(b'\r\n!PB AB CD EF\r\n')
```

### Encode Message
```python
message = "HELLO"
for char in message:
    ser.write(char.encode('ascii'))
    ser.flush()
    # Wait for response
    response = ser.read_until(b'\r\n')
    print(response)
```

---

## References

- Test scripts: `test_enigma_protocol.py`, `test_config_commands.py`, `test_set_commands.py`
- ESPHome configuration: `enigma-controler-v3.yaml`

