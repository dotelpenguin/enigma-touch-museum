#!/usr/bin/env python3
"""
Main Enigma device controller
"""

import time
import re
from typing import Optional, Tuple
from .constants import DEFAULT_DEVICE, CONFIG_FILE, CHAR_TIMEOUT
from .config import ConfigManager
from .serial_comm import SerialConnection


class EnigmaController:
    """Handles serial communication with Enigma device"""
    
    def __init__(self, device: str = DEFAULT_DEVICE, preserve_device: bool = False):
        self.device = device
        self.serial_conn = SerialConnection(device)
        self.config_manager = ConfigManager(CONFIG_FILE)
        
        # Default configuration
        default_config = {
            'config': {
                'mode': 'I',
                'rotor_set': 'A III IV I',
                'ring_settings': '01 01 01',
                'ring_position': '20 6 10',
                'pegboard': 'VF PQ'
            },
            'function_mode': 'Interactive',
            'museum_delay': 60,
            'always_send_config': False,
            'word_group_size': 5,
            'character_delay_ms': 0,
            'web_server_enabled': False,
            'web_server_port': 8080,
            'enable_slides': False,
            'lock_model': True,
            'lock_rotor': True,
            'lock_ring': True,
            'disable_power_off': True,
            'use_models_json': False,
            'brightness': 3,
            'volume': 0,
            'screen_saver': 0,
            'timeout_battery': 15,
            'timeout_plugged': 0,
            'timeout_setup_modes': 0,
            'raw_debug_enabled': False,
            'device': device
        }
        
        # Load config
        loaded_config = self.config_manager.load_config(default_config, preserve_device=preserve_device)
        
        # Set attributes from loaded config
        self.config = loaded_config['config']
        self.function_mode = loaded_config['function_mode']
        self.museum_delay = loaded_config['museum_delay']
        self.always_send_config = loaded_config['always_send_config']
        self.word_group_size = loaded_config['word_group_size']
        self.character_delay_ms = loaded_config['character_delay_ms']
        self.web_server_enabled = loaded_config['web_server_enabled']
        self.web_server_port = loaded_config['web_server_port']
        self.web_server_ip: Optional[str] = None
        self.enable_slides = loaded_config['enable_slides']
        self.lock_model = loaded_config['lock_model']
        self.lock_rotor = loaded_config['lock_rotor']
        self.lock_ring = loaded_config['lock_ring']
        self.disable_power_off = loaded_config['disable_power_off']
        self.use_models_json = loaded_config.get('use_models_json', False)
        self.brightness = loaded_config['brightness']
        self.volume = loaded_config['volume']
        self.screen_saver = loaded_config.get('screen_saver', 0)
        self.timeout_battery = loaded_config.get('timeout_battery', 15)
        self.timeout_plugged = loaded_config.get('timeout_plugged', 0)
        self.timeout_setup_modes = loaded_config.get('timeout_setup_modes', 0)
        self.raw_debug_enabled = loaded_config.get('raw_debug_enabled', False)
        self.device = loaded_config['device']
        self.config_file = CONFIG_FILE
        
        # Character tracking
        self.last_char_sent: Optional[str] = None
        self.last_char_received: Optional[str] = None
        self.last_char_original: Optional[str] = None
        
        # Message generation flag (skip delays during message generation)
        self.generating_messages = False
        
        # Monitoring callbacks (for compatibility)
        self.monitoring_debug_callback = None
        self.monitoring_ui_refresh_callback = None
        self.monitoring_keypress_callback = None
    
    def save_config(self, preserve_ring_position=True, preserve_always_send_config=True):
        """Save current configuration to file
        
        Args:
            preserve_ring_position: If True, don't overwrite ring_position from file
            preserve_always_send_config: If True, load always_send_config from file instead of using current value.
                                       Defaults to True to prevent always_send_config from being overwritten.
        """
        # If preserving always_send_config, load it from file (default behavior)
        if preserve_always_send_config:
            saved = self.get_saved_config()
            always_send_config_value = saved.get('always_send_config', self.always_send_config)
        else:
            always_send_config_value = self.always_send_config
        
        config_data = {
            'config': self.config,
            'function_mode': self.function_mode,
            'museum_delay': self.museum_delay,
            'always_send_config': always_send_config_value,
            'word_group_size': self.word_group_size,
            'character_delay_ms': self.character_delay_ms,
            'web_server_enabled': self.web_server_enabled,
            'web_server_port': self.web_server_port,
            'enable_slides': self.enable_slides,
            'lock_model': self.lock_model,
            'lock_rotor': self.lock_rotor,
            'lock_ring': self.lock_ring,
            'disable_power_off': self.disable_power_off,
            'use_models_json': self.use_models_json,
            'brightness': self.brightness,
            'volume': self.volume,
            'screen_saver': self.screen_saver,
            'timeout_battery': getattr(self, 'timeout_battery', 15),
            'timeout_plugged': getattr(self, 'timeout_plugged', 0),
            'timeout_setup_modes': getattr(self, 'timeout_setup_modes', 0),
            'raw_debug_enabled': getattr(self, 'raw_debug_enabled', False),
            'device': self.device
        }
        return self.config_manager.save_config(config_data, preserve_ring_position=preserve_ring_position)
    
    def load_config(self, preserve_device: bool = False, preserve_always_send_config: bool = False, preserve_function_mode: bool = False):
        """Load configuration from file
        
        Args:
            preserve_device: If True, don't overwrite device from config file
            preserve_always_send_config: If True, don't overwrite always_send_config from config file
            preserve_function_mode: If True, don't overwrite function_mode from config file
        """
        default_config = {
            'config': self.config.copy(),
            'function_mode': self.function_mode,
            'museum_delay': self.museum_delay,
            'always_send_config': self.always_send_config,
            'word_group_size': self.word_group_size,
            'character_delay_ms': self.character_delay_ms,
            'web_server_enabled': self.web_server_enabled,
            'web_server_port': self.web_server_port,
            'enable_slides': self.enable_slides,
            'lock_model': self.lock_model,
            'lock_rotor': self.lock_rotor,
            'lock_ring': self.lock_ring,
            'disable_power_off': self.disable_power_off,
            'use_models_json': getattr(self, 'use_models_json', False),
            'brightness': self.brightness,
            'volume': self.volume,
            'screen_saver': self.screen_saver,
            'timeout_battery': getattr(self, 'timeout_battery', 15),
            'timeout_plugged': getattr(self, 'timeout_plugged', 0),
            'timeout_setup_modes': getattr(self, 'timeout_setup_modes', 0),
            'device': self.device
        }
        loaded_config = self.config_manager.load_config(default_config, preserve_device=preserve_device)
        
        # Update attributes
        self.config.update(loaded_config['config'])
        # Preserve function_mode if requested (used when loading config before sending message)
        if not preserve_function_mode:
            self.function_mode = loaded_config['function_mode']
        self.museum_delay = loaded_config['museum_delay']
        # Preserve always_send_config if requested (used when loading config before sending message)
        if not preserve_always_send_config:
            self.always_send_config = loaded_config['always_send_config']
        self.word_group_size = loaded_config['word_group_size']
        self.character_delay_ms = loaded_config['character_delay_ms']
        self.web_server_enabled = loaded_config['web_server_enabled']
        self.web_server_port = loaded_config['web_server_port']
        self.enable_slides = loaded_config['enable_slides']
        self.lock_model = loaded_config['lock_model']
        self.lock_rotor = loaded_config['lock_rotor']
        self.lock_ring = loaded_config['lock_ring']
        self.disable_power_off = loaded_config['disable_power_off']
        self.use_models_json = loaded_config.get('use_models_json', False)
        self.brightness = loaded_config['brightness']
        self.volume = loaded_config['volume']
        self.screen_saver = loaded_config.get('screen_saver', 0)
        self.timeout_battery = loaded_config.get('timeout_battery', 15)
        self.timeout_plugged = loaded_config.get('timeout_plugged', 0)
        self.timeout_setup_modes = loaded_config.get('timeout_setup_modes', 0)
        if not preserve_device:
            self.device = loaded_config['device']
        
        return True
    
    def get_saved_config(self):
        """Get saved configuration from file (without modifying in-memory config)"""
        current_config = {
            'config': self.config,
            'function_mode': self.function_mode,
            'museum_delay': self.museum_delay,
            'always_send_config': self.always_send_config,
            'word_group_size': self.word_group_size,
            'character_delay_ms': self.character_delay_ms,
            'web_server_enabled': self.web_server_enabled,
            'web_server_port': self.web_server_port,
            'enable_slides': self.enable_slides,
            'lock_model': self.lock_model,
            'lock_rotor': self.lock_rotor,
            'lock_ring': self.lock_ring,
            'disable_power_off': self.disable_power_off,
            'use_models_json': getattr(self, 'use_models_json', False),
            'brightness': self.brightness,
            'volume': self.volume,
            'screen_saver': self.screen_saver,
            'timeout_battery': getattr(self, 'timeout_battery', 15),
            'timeout_plugged': getattr(self, 'timeout_plugged', 0),
            'timeout_setup_modes': getattr(self, 'timeout_setup_modes', 0),
            'raw_debug_enabled': getattr(self, 'raw_debug_enabled', False),
            'device': self.device
        }
        return self.config_manager.get_saved_config(current_config)
    
    def connect(self) -> bool:
        """Connect to serial device"""
        return self.serial_conn.connect()
    
    def disconnect(self):
        """Close serial connection"""
        self.serial_conn.disconnect()
    
    def is_connected(self) -> bool:
        """Check if serial connection is open and accessible"""
        return self.serial_conn.is_connected()
    
    def start_monitoring(self):
        """Start background thread to monitor Enigma input (no-op, monitoring was removed)"""
        pass
    
    def stop_monitoring(self):
        """Stop background monitoring thread (no-op, monitoring was removed)"""
        pass
    
    def _has_error_response(self, response: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Check if response contains an error message"""
        return SerialConnection.has_error_response(response)
    
    def send_command(self, command: bytes, timeout: float = None, debug_callback=None):
        """Send a command and return response"""
        if timeout is None:
            from .constants import CMD_TIMEOUT
            timeout = CMD_TIMEOUT
        response = self.serial_conn.send_command(command, timeout=timeout, debug_callback=debug_callback)
        
        # Log raw response if raw debug is enabled
        if debug_callback and self.raw_debug_enabled and response:
            # Get raw bytes from serial connection if available
            # Note: send_command returns decoded string, so we need to capture raw bytes differently
            # For now, we'll log the response string with indication it's from send_command
            if debug_callback:
                debug_callback(f"[RAW] send_command response (decoded): {repr(response)}")
        
        return response
    
    @property
    def ser(self):
        """Property to access serial connection for backward compatibility"""
        return self.serial_conn.ser
    
    def query_mode(self, debug_callback=None) -> Optional[str]:
        """Query Enigma model/mode"""
        response = self.send_command(b'\r\n?MO\r\n', debug_callback=debug_callback)
        if response and 'Enigma' in response:
            lines = response.split('\n')
            for line in lines:
                if 'Enigma' in line:
                    model = line.strip().replace('Enigma', '').strip()
                    return model.split('\x00')[0].strip()
        return None
    
    def query_rotor_set(self, debug_callback=None) -> Optional[str]:
        """Query rotor configuration"""
        response = self.send_command(b'\r\n?RO\r\n', debug_callback=debug_callback)
        if response:
            reflector = ''
            rotors = ''
            for line in response.split('\n'):
                if 'Reflector' in line:
                    reflector = line.replace('Reflector', '').strip()
                elif 'Rotors' in line:
                    rotors = line.replace('Rotors', '').strip()
            if reflector and rotors:
                return f"{reflector} {rotors}"
        return None
    
    def query_ring_settings(self, debug_callback=None) -> Optional[str]:
        """Query ring settings"""
        response = self.send_command(b'\r\n?RI\r\n', debug_callback=debug_callback)
        if response and 'Rings' in response:
            for line in response.split('\n'):
                if 'Rings' in line:
                    rings = line.replace('Rings', '').strip()
                    return rings
        return None
    
    def query_ring_position(self, debug_callback=None) -> Optional[str]:
        """Query ring position"""
        response = self.send_command(b'\r\n?RP\r\n', debug_callback=debug_callback)
        if response and 'Positions' in response:
            for line in response.split('\n'):
                if 'Positions' in line:
                    pos = line.replace('Positions', '').strip()
                    return pos
        return None
    
    def _parse_position_value(self, value: str) -> int:
        """Parse a position value (letter A-Z or number 01-26) to integer 1-26
        
        Args:
            value: Single letter (A-Z) or two-digit number (01-26) as string
            
        Returns:
            Integer value 1-26
            
        Raises:
            ValueError: If value cannot be parsed or is out of range
        """
        value = value.strip().upper()
        
        # Check if it's a letter (A-Z)
        if len(value) == 1 and value.isalpha():
            return ord(value) - ord('A') + 1
        
        # Check if it's a number (01-26)
        try:
            num = int(value)
            if 1 <= num <= 26:
                return num
            raise ValueError(f"Position value {value} out of range (must be 1-26)")
        except ValueError:
            raise ValueError(f"Invalid position value: {value} (must be A-Z or 01-26)")
    
    def _get_rotor_count(self, model: Optional[str] = None) -> int:
        """Get the number of rotors for a given model
        
        Args:
            model: Model name (e.g., 'M4', 'M3', 'I'). If None, uses self.config['mode']
            
        Returns:
            Number of rotors: 4 for M4, 3 for all other models
        """
        if model is None:
            model = self.config.get('mode', 'I')
        
        if model.upper() == 'M4':
            return 4
        return 3
    
    def _parse_positions(self, parts: list, start_idx: int, rotor_count: int) -> Optional[Tuple[int, ...]]:
        """Parse position values from a parts list
        
        Args:
            parts: List of strings from split response
            start_idx: Starting index in parts where positions begin
            rotor_count: Number of rotors (3 or 4)
            
        Returns:
            Tuple of integers representing positions, or None on error
        """
        if start_idx + rotor_count > len(parts):
            return None
        
        try:
            positions = []
            for i in range(rotor_count):
                pos_value = self._parse_position_value(parts[start_idx + i])
                positions.append(pos_value)
            return tuple(positions)
        except (ValueError, IndexError):
            return None
    
    def _format_positions(self, parts: list, start_idx: int, rotor_count: int, positions: Tuple[int, ...]) -> str:
        """Format position values preserving original format (letters or numbers)
        
        Args:
            parts: List of strings from split response (to check original format)
            start_idx: Starting index in parts where positions begin
            rotor_count: Number of rotors (3 or 4)
            positions: Tuple of integer positions (1-26)
            
        Returns:
            Formatted position string preserving original format
        """
        if start_idx + rotor_count > len(parts):
            # Fallback to numbers if we can't check original format
            return ' '.join(f"{p:02d}" for p in positions)
        
        formatted = []
        for i in range(rotor_count):
            original_value = parts[start_idx + i].strip().upper()
            # Check if original was a letter (A-Z)
            if len(original_value) == 1 and original_value.isalpha():
                # Format as letter
                formatted.append(chr(ord('A') + positions[i] - 1))
            else:
                # Format as number - preserve original format exactly
                try:
                    # Try to parse as int to verify it's a valid number
                    original_num = int(original_value)
                    # Verify the parsed value matches what we have
                    if original_num == positions[i]:
                        # Preserve the exact original format
                        formatted.append(original_value)
                    else:
                        # Mismatch - fallback to two-digit format
                        formatted.append(f"{positions[i]:02d}")
                except ValueError:
                    # Not a number, fallback to two-digit format
                    formatted.append(f"{positions[i]:02d}")
        
        return ' '.join(formatted)
    
    def _filter_config_summary(self, response: bytes, debug_callback=None) -> bytes:
        """Filter out config summary lines and return only the last encoding result
        
        When the Enigma device resets or cycles mode, it sends a full config summary
        before the actual encoding result. This function filters out those config lines
        and returns only the last line containing the actual encoding result.
        
        Args:
            response: Raw response bytes from device
            debug_callback: Optional callback for debug messages
            
        Returns:
            Filtered response bytes containing only the last encoding result
        """
        if not response:
            return response
        
        try:
            # Decode response to work with lines
            decoded = response.decode('ascii', errors='replace')
            
            # Split by newlines to preserve line structure
            lines = decoded.split('\n')
            
            # Remove carriage returns and strip whitespace from each line
            cleaned_lines = [line.replace('\r', '').strip() for line in lines if line.strip()]
            
            if not cleaned_lines:
                return response
            
            # Show original response if raw debug enabled
            if debug_callback and self.raw_debug_enabled:
                debug_callback(f"[RAW] Original response before filtering:")
                debug_callback(f"[RAW] {repr(response)}")
                debug_callback(f"[RAW] Decoded lines: {len(cleaned_lines)}")
            
            # Identify config summary lines and encoding result lines
            config_lines = []
            encoding_lines = []
            
            for i, line in enumerate(cleaned_lines):
                line_upper = line.upper()
                parts = line.split()
                
                if not parts:
                    continue
                
                # Check if line matches encoding pattern: two single chars + "Positions"
                # This check must come FIRST to avoid misidentifying encoding lines as config
                is_encoding_line = False
                if len(parts) >= 3:
                    part1 = parts[0]
                    part2 = parts[1]
                    part3 = parts[2]
                    
                    # Pattern: two single alphabetic characters followed by "Positions"
                    if (len(part1) == 1 and part1.isalpha() and
                        len(part2) == 1 and part2.isalpha() and
                        part3.upper() == 'POSITIONS'):
                        is_encoding_line = True
                
                # Check if line is a config summary line (only if not encoding line)
                is_config_line = False
                if not is_encoding_line:
                    if line_upper.startswith('ENIGMA'):
                        is_config_line = True
                    elif line_upper.startswith('REFLECTOR'):
                        is_config_line = True
                    elif line_upper.startswith('ROTORS'):
                        is_config_line = True
                    elif line_upper.startswith('RINGS'):
                        is_config_line = True
                    elif len(parts) >= 1 and parts[0].upper() == 'POSITIONS':
                        # Config line: "Positions D C N G" (Positions is first word)
                        # Encoding line already handled above: "d q   Positions D C N H"
                        is_config_line = True
                
                if is_config_line:
                    config_lines.append((i, line))
                elif is_encoding_line:
                    encoding_lines.append((i, line))
            
            # If we found config lines, filter them out
            if config_lines:
                if debug_callback:
                    debug_callback("Config summary detected in response, filtering...")
                    for idx, config_line in config_lines:
                        debug_callback(f"Ignoring config line: {config_line}")
                    debug_callback(f"Filtered out {len(config_lines)} config summary line(s), using last encoding result")
                
                # If we have encoding lines, use the last one
                if encoding_lines:
                    last_encoding_line = encoding_lines[-1][1]
                    if debug_callback:
                        debug_callback(f"Using encoding result line: {last_encoding_line}")
                    
                    # Return only the last encoding line as bytes
                    filtered_bytes = last_encoding_line.encode('ascii', errors='replace')
                    
                    if debug_callback and self.raw_debug_enabled:
                        raw_hex = ' '.join(f'{b:02x}' for b in filtered_bytes)
                        debug_callback(f"[RAW] Filtered response bytes (hex): {raw_hex}")
                        debug_callback(f"[RAW] Filtered response bytes (repr): {repr(filtered_bytes)}")
                    
                    return filtered_bytes
                else:
                    # No encoding pattern found after filtering
                    if debug_callback:
                        debug_callback("Warning: No encoding pattern found after filtering config summary", color_type=7)
                    # Return original response as fallback
                    return response
            else:
                # No config summary detected, return original response
                return response
                
        except Exception as e:
            # If filtering fails, return original response
            if debug_callback:
                debug_callback(f"Error filtering config summary: {e}, using original response", color_type=7)
            return response
    
    def query_pegboard(self, debug_callback=None) -> Optional[str]:
        """Query pegboard settings"""
        response = self.send_command(b'\r\n?PB\r\n', debug_callback=debug_callback)
        if response and 'Plugboard' in response:
            for line in response.split('\n'):
                if 'Plugboard' in line:
                    pb = line.replace('Plugboard', '').strip()
                    if pb == 'clear':
                        return ''
                    return pb
        return None
    
    def query_lock_model(self, debug_callback=None) -> Optional[bool]:
        """Query lock state for model setup mode
        
        Returns:
            True if locked, False if unlocked, None on error
        """
        response = self.send_command(b'\r\n?LM\r\n', debug_callback=debug_callback)
        if response:
            # Response should contain "1" for locked or "0" for unlocked
            response_lower = response.lower()
            if '1' in response or 'locked' in response_lower:
                return True
            elif '0' in response or 'unlocked' in response_lower:
                return False
            # Try to find a number in the response
            match = re.search(r'\b([01])\b', response)
            if match:
                return match.group(1) == '1'
        return None
    
    def query_lock_rotor(self, debug_callback=None) -> Optional[bool]:
        """Query lock state for rotor (wheel) setup mode
        
        Returns:
            True if locked, False if unlocked, None on error
        """
        response = self.send_command(b'\r\n?LW\r\n', debug_callback=debug_callback)
        if response:
            response_lower = response.lower()
            if '1' in response or 'locked' in response_lower:
                return True
            elif '0' in response or 'unlocked' in response_lower:
                return False
            match = re.search(r'\b([01])\b', response)
            if match:
                return match.group(1) == '1'
        return None
    
    def query_lock_ring(self, debug_callback=None) -> Optional[bool]:
        """Query lock state for ring setup mode
        
        Returns:
            True if locked, False if unlocked, None on error
        """
        response = self.send_command(b'\r\n?LR\r\n', debug_callback=debug_callback)
        if response:
            response_lower = response.lower()
            if '1' in response or 'locked' in response_lower:
                return True
            elif '0' in response or 'unlocked' in response_lower:
                return False
            match = re.search(r'\b([01])\b', response)
            if match:
                return match.group(1) == '1'
        return None
    
    def query_lock_power_off(self, debug_callback=None) -> Optional[bool]:
        """Query lock state for power-off button
        
        Returns:
            True if locked (disabled), False if unlocked (enabled), None on error
        """
        response = self.send_command(b'\r\n?LP\r\n', debug_callback=debug_callback)
        if response:
            response_lower = response.lower()
            if '1' in response or 'locked' in response_lower or 'disabled' in response_lower:
                return True
            elif '0' in response or 'unlocked' in response_lower or 'enabled' in response_lower:
                return False
            import re
            match = re.search(r'\b([01])\b', response)
            if match:
                return match.group(1) == '1'
        return None
    
    def query_brightness(self, debug_callback=None) -> Optional[int]:
        """Query current brightness level
        
        Returns:
            Brightness level (1-5) or None on error
        """
        response = self.send_command(b'\r\n?MB\r\n', debug_callback=debug_callback)
        if response:
            import re
            # Look for a number 1-5 in the response
            match = re.search(r'\b([1-5])\b', response)
            if match:
                return int(match.group(1))
        return None
    
    def query_volume(self, debug_callback=None) -> Optional[int]:
        """Query current volume level
        
        Returns:
            Volume level (0-3) or None on error
        """
        response = self.send_command(b'\r\n?MV\r\n', debug_callback=debug_callback)
        if response:
            # Look for a number 0-3 in the response
            match = re.search(r'\b([0-3])\b', response)
            if match:
                return int(match.group(1))
        return None
    
    def query_logging_format(self, debug_callback=None) -> Optional[int]:
        """Query current logging format
        
        Returns:
            Logging format (1-4) or None on error
        """
        response = self.send_command(b'\r\n?ML\r\n', debug_callback=debug_callback)
        if response:
            import re
            # Look for a number 1-4 in the response
            match = re.search(r'\b([1-4])\b', response)
            if match:
                return int(match.group(1))
        return None
    
    def query_timeout_battery(self, debug_callback=None) -> Optional[int]:
        """Query power-off timeout when battery-operated
        
        Returns:
            Timeout in minutes (0-99) or None on error
        """
        response = self.send_command(b'\r\n?TB\r\n', debug_callback=debug_callback)
        if response:
            # Look for a number 0-99 in the response
            match = re.search(r'\b([0-9]{1,2})\b', response)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 99:
                    return value
        return None
    
    def query_timeout_plugged(self, debug_callback=None) -> Optional[int]:
        """Query power-off timeout when plugged in
        
        Returns:
            Timeout in minutes (0-99) or None on error
        """
        response = self.send_command(b'\r\n?TP\r\n', debug_callback=debug_callback)
        if response:
            # Look for a number 0-99 in the response
            match = re.search(r'\b([0-9]{1,2})\b', response)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 99:
                    return value
        return None
    
    def query_timeout_screen_saver(self, debug_callback=None) -> Optional[int]:
        """Query screen saver timeout
        
        Returns:
            Timeout in minutes (0-99) or None on error
        """
        response = self.send_command(b'\r\n?TS\r\n', debug_callback=debug_callback)
        if response:
            # Look for a number 0-99 in the response
            match = re.search(r'\b([0-9]{1,2})\b', response)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 99:
                    return value
        return None
    
    def query_timeout_setup_modes(self, debug_callback=None) -> Optional[int]:
        """Query setup mode inactivity timeout
        
        Returns:
            Timeout in seconds (0-99) or None on error
        """
        response = self.send_command(b'\r\n?TM\r\n', debug_callback=debug_callback)
        if response:
            # Look for a number 0-99 in the response
            match = re.search(r'\b([0-9]{1,2})\b', response)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 99:
                    return value
        return None

    def get_all_settings(self, debug_callback=None) -> dict:
        """Query all settings"""
        settings = {}
        settings['mode'] = self.query_mode(debug_callback=debug_callback) or self.config['mode']
        time.sleep(0.2)
        settings['rotor_set'] = self.query_rotor_set(debug_callback=debug_callback) or self.config['rotor_set']
        time.sleep(0.2)
        settings['ring_settings'] = self.query_ring_settings(debug_callback=debug_callback) or self.config['ring_settings']
        time.sleep(0.2)
        settings['ring_position'] = self.query_ring_position(debug_callback=debug_callback) or self.config['ring_position']
        time.sleep(0.2)
        settings['pegboard'] = self.query_pegboard(debug_callback=debug_callback) or self.config['pegboard']
        
        # Query lock settings
        time.sleep(0.2)
        lock_model = self.query_lock_model(debug_callback=debug_callback)
        settings['lock_model'] = lock_model if lock_model is not None else self.lock_model
        time.sleep(0.2)
        lock_rotor = self.query_lock_rotor(debug_callback=debug_callback)
        settings['lock_rotor'] = lock_rotor if lock_rotor is not None else self.lock_rotor
        time.sleep(0.2)
        lock_ring = self.query_lock_ring(debug_callback=debug_callback)
        settings['lock_ring'] = lock_ring if lock_ring is not None else self.lock_ring
        time.sleep(0.2)
        lock_power_off = self.query_lock_power_off(debug_callback=debug_callback)
        settings['disable_power_off'] = lock_power_off if lock_power_off is not None else self.disable_power_off
        
        # Query UI settings
        time.sleep(0.2)
        brightness = self.query_brightness(debug_callback=debug_callback)
        settings['brightness'] = brightness if brightness is not None else self.brightness
        time.sleep(0.2)
        volume = self.query_volume(debug_callback=debug_callback)
        settings['volume'] = volume if volume is not None else self.volume
        time.sleep(0.2)
        logging_format = self.query_logging_format(debug_callback=debug_callback)
        settings['logging_format'] = logging_format
        
        # Query timeout settings
        time.sleep(0.2)
        timeout_battery = self.query_timeout_battery(debug_callback=debug_callback)
        settings['timeout_battery'] = timeout_battery if timeout_battery is not None else getattr(self, 'timeout_battery', 15)
        time.sleep(0.2)
        timeout_plugged = self.query_timeout_plugged(debug_callback=debug_callback)
        settings['timeout_plugged'] = timeout_plugged if timeout_plugged is not None else getattr(self, 'timeout_plugged', 0)
        time.sleep(0.2)
        timeout_screen_saver = self.query_timeout_screen_saver(debug_callback=debug_callback)
        settings['screen_saver'] = timeout_screen_saver if timeout_screen_saver is not None else self.screen_saver
        time.sleep(0.2)
        timeout_setup_modes = self.query_timeout_setup_modes(debug_callback=debug_callback)
        settings['timeout_setup_modes'] = timeout_setup_modes if timeout_setup_modes is not None else getattr(self, 'timeout_setup_modes', 0)
        
        return settings
    
    def set_mode(self, mode: str, debug_callback=None) -> bool:
        """Set Enigma model/mode"""
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!MO {mode}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_mode command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_mode full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting mode '{mode}')", color_type=7)
            return False
        if response is None:
            return False
        self.config['mode'] = mode
        return True
    
    def set_rotor_set(self, rotor_set: str, debug_callback=None) -> bool:
        """Set rotor configuration"""
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!RO {rotor_set}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_rotor_set command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_rotor_set full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting rotor set '{rotor_set}')", color_type=7)
            return False
        if response is None:
            return False
        self.config['rotor_set'] = rotor_set
        return True
    
    def set_ring_settings(self, ring_settings: str, debug_callback=None) -> bool:
        """Set ring settings"""
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!RI {ring_settings}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_ring_settings command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_ring_settings full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting ring settings '{ring_settings}')", color_type=7)
            return False
        if response is None:
            return False
        self.config['ring_settings'] = ring_settings
        return True
    
    def set_ring_position(self, ring_position: str, debug_callback=None) -> bool:
        """Set ring position"""
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!RP {ring_position}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_ring_position command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_ring_position full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting ring position '{ring_position}')", color_type=7)
            return False
        if response is None:
            return False
        self.config['ring_position'] = ring_position
        return True
    
    def set_pegboard(self, pegboard: str, debug_callback=None) -> bool:
        """Set pegboard settings
        
        Args:
            pegboard: Pegboard pairs (e.g., "VF PQ") or empty string to clear
        """
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        # To clear pegboard, send !PB with no parameters
        if not pegboard:
            cmd = b'!PB\r\n'
            display_value = 'clear'
        else:
            cmd = f"!PB {pegboard}\r\n".encode('ascii')
            display_value = pegboard
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_pegboard command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_pegboard full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting pegboard '{display_value}')", color_type=7)
            return False
        if response is None:
            return False
        # Store empty string in config when cleared
        self.config['pegboard'] = ''
        if pegboard:
            self.config['pegboard'] = pegboard
        return True
    
    def set_lock_model(self, lock: bool, debug_callback=None) -> bool:
        """Set lock state for model setup mode
        
        Args:
            lock: True to lock, False to unlock
        """
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        value = 1 if lock else 0
        cmd = f"!LM {value}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_lock_model command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_lock_model full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting lock_model to {lock})", color_type=7)
            return False
        if response is None:
            return False
        self.lock_model = lock
        return True
    
    def set_lock_rotor(self, lock: bool, debug_callback=None) -> bool:
        """Set lock state for rotor (wheel) setup mode
        
        Args:
            lock: True to lock, False to unlock
        """
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        value = 1 if lock else 0
        cmd = f"!LW {value}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_lock_rotor command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_lock_rotor full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting lock_rotor to {lock})", color_type=7)
            return False
        if response is None:
            return False
        self.lock_rotor = lock
        return True
    
    def set_lock_ring(self, lock: bool, debug_callback=None) -> bool:
        """Set lock state for ring setup mode
        
        Args:
            lock: True to lock, False to unlock
        """
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        value = 1 if lock else 0
        cmd = f"!LR {value}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_lock_ring command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_lock_ring full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting lock_ring to {lock})", color_type=7)
            return False
        if response is None:
            return False
        self.lock_ring = lock
        return True
    
    def set_lock_power_off(self, lock: bool, debug_callback=None) -> bool:
        """Set lock state for power-off button
        
        Args:
            lock: True to disable power-off button, False to enable
        """
        if not self.ser or not self.ser.is_open:
            return False
        value = 1 if lock else 0
        cmd = f"!LP {value}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_lock_power_off command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_lock_power_off full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting disable_power_off to {lock})", color_type=7)
            return False
        if response is None:
            return False
        self.disable_power_off = lock
        return True
    
    def set_brightness(self, level: int, debug_callback=None) -> bool:
        """Set display brightness
        
        Args:
            level: Brightness level (1-5)
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (1 <= level <= 5):
            if debug_callback:
                debug_callback(f"ERROR: Brightness level must be 1-5 (got {level})", color_type=7)
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!MB {level}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_brightness command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_brightness full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting brightness to {level})", color_type=7)
            return False
        if response is None:
            return False
        self.brightness = level
        return True
    
    def set_volume(self, level: int, debug_callback=None) -> bool:
        """Set volume level
        
        Args:
            level: Volume level (0-3)
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (0 <= level <= 3):
            if debug_callback:
                debug_callback(f"ERROR: Volume level must be 0-3 (got {level})", color_type=7)
            return False
        cmd = f"!MV {level}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_volume command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_volume full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting volume to {level})", color_type=7)
            return False
        if response is None:
            return False
        self.volume = level
        return True
    
    def set_logging_format(self, format: int, debug_callback=None) -> bool:
        """Set logging format
        
        Args:
            format: Logging format (1-4)
                1 = short/5, 2 = short/4, 3 = extended/5, 4 = extended/4
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (1 <= format <= 4):
            if debug_callback:
                debug_callback(f"ERROR: Logging format must be 1-4 (got {format})", color_type=7)
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!ML {format}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_logging_format command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_logging_format full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting logging format to {format})", color_type=7)
            return False
        if response is None:
            return False
        return True
    
    def set_timeout_battery(self, minutes: int, debug_callback=None) -> bool:
        """Set power-off timeout when battery-operated
        
        Args:
            minutes: Timeout in minutes (0-99, 0 = disabled)
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (0 <= minutes <= 99):
            if debug_callback:
                debug_callback(f"ERROR: Timeout must be 0-99 minutes (got {minutes})", color_type=7)
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!TB {minutes}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_timeout_battery command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_timeout_battery full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting timeout_battery to {minutes})", color_type=7)
            return False
        if response is None:
            return False
        self.timeout_battery = minutes
        return True
    
    def set_timeout_plugged(self, minutes: int, debug_callback=None) -> bool:
        """Set power-off timeout when plugged in
        
        Args:
            minutes: Timeout in minutes (0-99, 0 = disabled)
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (0 <= minutes <= 99):
            if debug_callback:
                debug_callback(f"ERROR: Timeout must be 0-99 minutes (got {minutes})", color_type=7)
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!TP {minutes}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_timeout_plugged command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_timeout_plugged full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting timeout_plugged to {minutes})", color_type=7)
            return False
        if response is None:
            return False
        self.timeout_plugged = minutes
        return True
    
    def set_timeout_screen_saver(self, minutes: int, debug_callback=None) -> bool:
        """Set screen saver timeout
        
        Args:
            minutes: Timeout in minutes (0-99, 0 = disabled)
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (0 <= minutes <= 99):
            if debug_callback:
                debug_callback(f"ERROR: Timeout must be 0-99 minutes (got {minutes})", color_type=7)
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!TS {minutes}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_timeout_screen_saver command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_timeout_screen_saver full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting screen_saver timeout to {minutes})", color_type=7)
            return False
        if response is None:
            return False
        self.screen_saver = minutes
        return True
    
    def set_timeout_setup_modes(self, seconds: int, debug_callback=None) -> bool:
        """Set setup mode inactivity timeout
        
        Args:
            seconds: Timeout in seconds (0-99, 0 = disabled)
        """
        if not self.ser or not self.ser.is_open:
            return False
        if not (0 <= seconds <= 99):
            if debug_callback:
                debug_callback(f"ERROR: Timeout must be 0-99 seconds (got {seconds})", color_type=7)
            return False
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!TM {seconds}\r\n".encode('ascii')
        if debug_callback and self.raw_debug_enabled:
            debug_callback(f"[RAW] set_timeout_setup_modes command bytes: {repr(cmd)}")
        response = self.send_command(cmd, debug_callback=debug_callback)
        if debug_callback and self.raw_debug_enabled and response:
            debug_callback(f"[RAW] set_timeout_setup_modes full response: {repr(response)}")
        has_error, error_message = self._has_error_response(response)
        if has_error:
            if debug_callback:
                debug_callback(f"ERROR: {error_message} (setting timeout_setup_modes to {seconds})", color_type=7)
            return False
        if response is None:
            return False
        self.timeout_setup_modes = seconds
        return True
    
    def apply_kiosk_settings(self, debug_callback=None) -> bool:
        """Apply all kiosk/demo mode settings from saved config
        
        This method sends all locking, UI, and timeout settings to the device.
        
        Args:
            debug_callback: Optional callback for debug messages
            
        Returns:
            True if all settings applied successfully, False otherwise
        """
        if not self.ser or not self.ser.is_open:
            if debug_callback:
                debug_callback("ERROR: Not connected to device", color_type=7)
            return False
        
        saved = self.get_saved_config()
        config_errors = []
        
        # Apply lock settings
        if debug_callback:
            debug_callback("Applying lock settings...")
        time.sleep(0.1)
        if not self.set_lock_model(saved.get('lock_model', True), debug_callback=debug_callback):
            config_errors.append("lock_model")
        time.sleep(0.1)
        if not self.set_lock_rotor(saved.get('lock_rotor', True), debug_callback=debug_callback):
            config_errors.append("lock_rotor")
        time.sleep(0.1)
        if not self.set_lock_ring(saved.get('lock_ring', True), debug_callback=debug_callback):
            config_errors.append("lock_ring")
        time.sleep(0.1)
        if not self.set_lock_power_off(saved.get('disable_power_off', True), debug_callback=debug_callback):
            config_errors.append("disable_power_off")
        
        # Apply UI settings
        if debug_callback:
            debug_callback("Applying UI settings...")
        time.sleep(0.1)
        if not self.set_brightness(saved.get('brightness', 3), debug_callback=debug_callback):
            config_errors.append("brightness")
        time.sleep(0.1)
        if not self.set_volume(saved.get('volume', 0), debug_callback=debug_callback):
            config_errors.append("volume")
        time.sleep(0.1)
        # Set logging format based on word_group_size
        # Format 3 = extended/5 chars, Format 4 = extended/4 chars
        word_group_size = saved.get('word_group_size', self.word_group_size)
        if word_group_size == 5:
            desired_logging_format = 3  # extended/5
        elif word_group_size == 4:
            desired_logging_format = 4  # extended/4
        else:
            # Default to extended/5 if word_group_size is not 4 or 5
            desired_logging_format = 3
        
        # Check current logging format before setting
        current_logging_format = self.query_logging_format(debug_callback=debug_callback)
        if current_logging_format != desired_logging_format:
            if debug_callback:
                debug_callback(f"Setting logging format from {current_logging_format} to {desired_logging_format} (word_group_size={word_group_size})")
            if not self.set_logging_format(desired_logging_format, debug_callback=debug_callback):
                config_errors.append("logging_format")
        else:
            if debug_callback:
                debug_callback(f"Logging format already set to {desired_logging_format} (word_group_size={word_group_size})")
        
        # Apply timeout settings
        if debug_callback:
            debug_callback("Applying timeout settings...")
        time.sleep(0.1)
        if not self.set_timeout_battery(saved.get('timeout_battery', 15), debug_callback=debug_callback):
            config_errors.append("timeout_battery")
        time.sleep(0.1)
        if not self.set_timeout_plugged(saved.get('timeout_plugged', 0), debug_callback=debug_callback):
            config_errors.append("timeout_plugged")
        time.sleep(0.1)
        if not self.set_timeout_screen_saver(saved.get('screen_saver', 0), debug_callback=debug_callback):
            config_errors.append("screen_saver")
        time.sleep(0.1)
        if not self.set_timeout_setup_modes(saved.get('timeout_setup_modes', 0), debug_callback=debug_callback):
            config_errors.append("timeout_setup_modes")
        
        if config_errors:
            if debug_callback:
                error_msg = f"Kiosk settings errors: {', '.join(config_errors)}"
                debug_callback(f"ERROR: {error_msg}", color_type=7)
            return False
        
        if debug_callback:
            debug_callback("All kiosk settings applied successfully")
        return True
    
    def wakeup_device(self, debug_callback=None) -> bool:
        """Wake up the device by sending line return, 'A', and line return
        
        This helps ensure the device is ready to receive commands.
        
        Args:
            debug_callback: Optional callback for debug messages
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ser or not self.ser.is_open:
            return False
        
        if debug_callback:
            debug_callback("Waking up device...")
        
        try:
            # Send: \r\n, A, \r\n
            wakeup_parts = [b'\r\n', b'A', b'\r\n']
            
            for i, part in enumerate(wakeup_parts):
                if debug_callback and self.raw_debug_enabled:
                    part_hex = ' '.join(f'{b:02x}' for b in part)
                    debug_callback(f"[RAW] wakeup part {i+1} bytes (hex): {part_hex}")
                    debug_callback(f"[RAW] wakeup part {i+1} bytes (repr): {repr(part)}")
                
                self.ser.write(part)
                self.ser.flush()
                time.sleep(0.1)
            
            # Read any response from device
            time.sleep(0.2)  # Give device time to process
            response = b''
            if self.ser.in_waiting > 0:
                response = self.ser.read(self.ser.in_waiting)
                if debug_callback and self.raw_debug_enabled and response:
                    raw_hex = ' '.join(f'{b:02x}' for b in response)
                    debug_callback(f"[RAW] wakeup response bytes (hex): {raw_hex}")
                    debug_callback(f"[RAW] wakeup response bytes (repr): {repr(response)}")
                    debug_callback(f"[RAW] wakeup response length: {len(response)} bytes")
                    try:
                        decoded = response.decode('ascii', errors='replace')
                        debug_callback(f"[RAW] wakeup response (decoded): {repr(decoded)}")
                    except:
                        pass
            
            if debug_callback:
                if response:
                    debug_callback(f"Device wakeup sent, received {len(response)} bytes")
                else:
                    debug_callback("Device wakeup sent")
            
            return True
        except Exception as e:
            if debug_callback:
                debug_callback(f"Error during wakeup: {e}", color_type=7)
            return False
    
    def return_to_encode_mode(self, debug_callback=None) -> bool:
        """Return to encode mode"""
        response = self.send_command(b'?MO\r\n', timeout=1.0, debug_callback=debug_callback)
        return response is not None
    
    def send_message(self, message: str, callback=None, debug_callback=None, position_update_callback=None, config_error_callback=None, expect_lowercase_response: bool = None, mode_update_callback=None) -> bool:
        """Send message character by character
        
        Args:
            message: Message to send
            callback: Optional callback function for progress updates
            debug_callback: Optional callback for debug messages
            position_update_callback: Optional callback when ring position updates
            config_error_callback: Optional callback for configuration errors
            expect_lowercase_response: If True, expect lowercase responses (for manual messages).
                                     If None, auto-detect based on function_mode.
            mode_update_callback: Optional callback when function_mode changes
        """
        if not self.ser or not self.ser.is_open:
            return False
        
        # Track initial mode to detect changes
        initial_mode = self.function_mode
        
        # Set function mode to Message Interactive if sending manual message and not in museum mode
        if expect_lowercase_response is None:
            # Auto-detect: if not in museum mode, use Message Interactive (lowercase)
            if not (self.function_mode.startswith('Encode') or self.function_mode.startswith('Decode')):
                # Set to Message Interactive mode for manual messages (expects lowercase)
                # This applies even if currently in 'Interactive' mode - we want lowercase for UI messages
                self.function_mode = 'Message Interactive'
        elif expect_lowercase_response:
            # Explicitly set to Message Interactive mode (expects lowercase)
            if not (self.function_mode.startswith('Encode') or self.function_mode.startswith('Decode')):
                self.function_mode = 'Message Interactive'
        
        # Notify UI if mode changed at start
        if self.function_mode != initial_mode and mode_update_callback:
            mode_update_callback()
        
        
        # Send configuration BEFORE any other data if option is enabled
        if self.always_send_config:
            if debug_callback:
                debug_callback("Sending configuration before message...")
            
            # Wake up device first
            self.wakeup_device(debug_callback=debug_callback)
            
            # Load config but preserve always_send_config and function_mode to prevent them from being overwritten
            # We want to keep 'Message Interactive' mode for manual messages
            self.load_config(preserve_device=True, preserve_always_send_config=True, preserve_function_mode=True)
            saved = self.get_saved_config()
            
            # Apply Enigma settings (mode, rotors, rings, pegboard)
            # Note: Kiosk/lock settings are NOT sent automatically - use menu option 6 to set them
            if debug_callback:
                debug_callback("Applying Enigma settings...")
            config_errors = []
            if not self.set_mode(saved['config']['mode'], debug_callback=debug_callback):
                config_errors.append("mode")
            time.sleep(0.2)
            if not self.set_rotor_set(saved['config']['rotor_set'], debug_callback=debug_callback):
                config_errors.append("rotor_set")
            time.sleep(0.2)
            if not self.set_ring_settings(saved['config']['ring_settings'], debug_callback=debug_callback):
                config_errors.append("ring_settings")
            time.sleep(0.2)
            if not self.set_ring_position(saved['config']['ring_position'], debug_callback=debug_callback):
                config_errors.append("ring_position")
            time.sleep(0.2)
            if not self.set_pegboard(saved['config']['pegboard'], debug_callback=debug_callback):
                config_errors.append("pegboard")
            time.sleep(0.2)
            
            if config_errors:
                error_msg = f"Configuration errors detected: {', '.join(config_errors)}"
                if debug_callback:
                    debug_callback(f"ERROR: {error_msg}", color_type=7)
                if config_error_callback:
                    config_error_callback(config_errors)
                return False
            
            self.return_to_encode_mode(debug_callback=debug_callback)
            time.sleep(0.5)
        else:
            # If not sending config first, ensure encode mode before sending message
            self.return_to_encode_mode(debug_callback=debug_callback)
            time.sleep(0.5)
        
        # Filter message to only A-Z characters
        filtered_message = ''.join(c for c in message.upper() if c.isalpha() and c.isupper())
        
        if not filtered_message:
            if debug_callback:
                debug_callback("Warning: No valid A-Z characters in message")
            return False
        
        if debug_callback:
            debug_callback(f"Original message: {message}")
            debug_callback(f"Filtered message (A-Z only): {filtered_message}")
        
        encoded_chars = []
        char_count = 0
        previous_positions = None
        previous_counter = None
        
        def update_ring_position(new_positions, parts=None, start_idx=None):
            """Helper to update ring position in config and notify UI
            
            Args:
                new_positions: Tuple of integer positions
                parts: Optional list of strings from response (to preserve format)
                start_idx: Optional starting index in parts where positions begin
            """
            if new_positions:
                # Format positions preserving original format if parts provided
                if parts is not None and start_idx is not None:
                    rotor_count = len(new_positions)
                    pos_str = self._format_positions(parts, start_idx, rotor_count, new_positions)
                else:
                    # Fallback to numbers if original format not available
                    pos_str = ' '.join(f"{p:02d}" for p in new_positions)
                self.config['ring_position'] = pos_str
                if position_update_callback:
                    position_update_callback()
        
        try:
            for i, char in enumerate(filtered_message):
                char_count += 1
                success = False
                retry_count = 0
                max_retries = 3
                
                while retry_count < max_retries and not success:
                    self.ser.reset_input_buffer()
                    time.sleep(0.1)
                    
                    if debug_callback:
                        debug_callback(f">>> '{char}'")
                    self.last_char_sent = char
                    self.ser.write(char.encode('ascii'))
                    self.ser.flush()
                    
                    response = b''
                    start_time = time.time()
                    found_positions = False
                    last_data_time = None
                    silence_duration = 0.2
                    
                    while time.time() - start_time < CHAR_TIMEOUT:
                        if self.ser.in_waiting > 0:
                            response += self.ser.read(self.ser.in_waiting)
                            last_data_time = time.time()
                            
                            if b'Positions' in response:
                                silence_start = time.time()
                                while time.time() - silence_start < silence_duration:
                                    if self.ser.in_waiting > 0:
                                        response += self.ser.read(self.ser.in_waiting)
                                        silence_start = time.time()
                                    time.sleep(0.01)
                                found_positions = True
                                break
                            time.sleep(0.01)
                        else:
                            if response and b'Positions' in response:
                                if last_data_time:
                                    if time.time() - last_data_time >= silence_duration:
                                        found_positions = True
                                        break
                            elif not response:
                                time.sleep(0.01)
                            else:
                                time.sleep(0.01)
                        time.sleep(0.01)
                    
                    if self.ser.in_waiting > 0:
                        time.sleep(0.1)
                        if self.ser.in_waiting > 0:
                            response += self.ser.read(self.ser.in_waiting)
                    
                    # Log raw payload for debugging (if enabled) - before filtering
                    if debug_callback and response and self.raw_debug_enabled:
                        # Show raw bytes in hex and repr format
                        raw_hex = ' '.join(f'{b:02x}' for b in response)
                        raw_repr = repr(response)
                        debug_callback(f"[RAW] Response bytes (hex): {raw_hex}")
                        debug_callback(f"[RAW] Response bytes (repr): {raw_repr}")
                        # Also show length
                        debug_callback(f"[RAW] Response length: {len(response)} bytes")
                    
                    # Filter out config summary if present
                    if response:
                        response = self._filter_config_summary(response, debug_callback=debug_callback)
                    
                    if response and found_positions:
                        resp_text = None
                        parts = []
                        encoded_char = None
                        # Determine expected case based on function mode:
                        # - Museum modes (Encode/Decode): expect lowercase
                        # - Message Interactive Mode: expect lowercase (manual messages from UI)
                        # - Interactive Mode: expect uppercase (direct device input)
                        is_museum_mode = (self.function_mode.startswith('Encode') or 
                                         self.function_mode.startswith('Decode'))
                        is_message_interactive_mode = (self.function_mode == 'Message Interactive')
                        expect_lowercase = is_museum_mode or is_message_interactive_mode
                        
                        current_positions = None
                        encoded_char_original = None
                        
                        # Get rotor count based on current model (recalculate each time to ensure it's up to date)
                        rotor_count = self._get_rotor_count()
                        if debug_callback:
                            current_model = self.config.get('mode', 'I')
                            debug_callback(f"Using rotor_count: {rotor_count} for model: {current_model}")
                            debug_callback(f"Function mode: {self.function_mode}, expect_lowercase: {expect_lowercase}")
                        
                        try:
                            resp_text = response.decode('ascii', errors='replace')
                            resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                            resp_text = ' '.join(resp_text.split()).strip()
                            
                            if debug_callback:
                                debug_callback(f"<<< {resp_text}")
                            
                            parts = resp_text.split()
                            
                            # Look for pattern: "INPUT ENCODED Positions XX XX XX" (or XX XX XX XX for M4)
                            # Need at least 2 + rotor_count parts after "positions"
                            min_parts_needed = 2 + rotor_count
                            for j in range(len(parts) - min_parts_needed):
                                part1 = parts[j]
                                part2 = parts[j+1]
                                part3 = parts[j+2]
                                
                                if (len(part1) == 1 and part1.isalpha() and
                                    len(part2) == 1 and part2.isalpha() and
                                    part3.lower() == 'positions'):
                                    if expect_lowercase:
                                        # Museum mode or Message Interactive mode: expect lowercase
                                        if part1.islower() and part2.islower():
                                            encoded_char_original = part2
                                            encoded_char = encoded_char_original.upper()
                                        elif part1.isupper() or part2.isupper():
                                            # Uppercase detected - switch to Interactive mode (uppercase)
                                            # When switching to Interactive mode, initialize display values to None
                                            # so they show as "-" until we receive actual Interactive mode input
                                            if debug_callback:
                                                debug_callback(f"Uppercase detected in Message Interactive mode!", color_type=7)
                                                debug_callback(f"  part1: '{part1}' (isupper: {part1.isupper()})", color_type=7)
                                                debug_callback(f"  part2: '{part2}' (isupper: {part2.isupper()})", color_type=7)
                                                debug_callback(f"  part3: '{part3}'", color_type=7)
                                                debug_callback(f"  Full parts list: {parts}", color_type=7)
                                                debug_callback(f"  Raw response was: {repr(response)}", color_type=7)
                                            encoded_char_original = part2  # Use exact value from Enigma
                                            encoded_char = encoded_char_original.upper()  # Ensure uppercase for processing
                                            # Initialize to None so web display shows "-" until we receive Interactive mode input
                                            self.last_char_original = None  # Will be set when Interactive mode input is received
                                            self.last_char_received = None  # Will be set when Interactive mode input is received
                                            self.function_mode = 'Interactive'
                                            self.save_config(preserve_always_send_config=True)
                                            if mode_update_callback:
                                                mode_update_callback()
                                            if debug_callback:
                                                debug_callback(f"Switching to Interactive mode (uppercase)", color_type=7)
                                    else:
                                        # Interactive mode: expect uppercase
                                        if part1.isupper() and part2.isupper():
                                            encoded_char_original = part2
                                            encoded_char = encoded_char_original.upper()
                                            # Ensure uppercase when storing in Interactive mode
                                            self.last_char_original = part1.upper() if part1 else None
                                            self.last_char_received = part2.upper() if part2 else None
                                        else:
                                            continue
                                    
                                    # Parse positions using helper function (handles letters and numbers, 3 or 4 rotors)
                                    # Verify we have enough parts for all positions
                                    if j + 3 + rotor_count > len(parts):
                                        if debug_callback:
                                            debug_callback(f"Warning: Not enough parts for {rotor_count} positions. Have {len(parts)} parts, need at least {j + 3 + rotor_count}. Parts: {parts}")
                                    current_positions = self._parse_positions(parts, j + 3, rotor_count)
                                    
                                    # Check for optional Counter field after positions
                                    # Format: "r y   Positions I M R I   Counter 2092"
                                    counter_value = None
                                    counter_idx = j + 3 + rotor_count
                                    if counter_idx < len(parts) and parts[counter_idx].lower() == 'counter':
                                        # Counter field found, try to parse the counter value
                                        if counter_idx + 1 < len(parts):
                                            try:
                                                counter_value = int(parts[counter_idx + 1])
                                                if debug_callback:
                                                    debug_callback(f"Counter: {counter_value}")
                                            except ValueError:
                                                if debug_callback:
                                                    debug_callback(f"Warning: Could not parse counter value: {parts[counter_idx + 1]}")
                                    
                                    # Store counter_value for later comparison (even if None)
                                    current_counter = counter_value
                                    
                                    if current_positions is None:
                                        if debug_callback:
                                            # Show what we tried to parse for debugging
                                            pos_parts = parts[j + 3:j + 3 + rotor_count] if j + 3 + rotor_count <= len(parts) else parts[j + 3:]
                                            debug_callback(f"Warning: Could not parse positions from response. Parts: {pos_parts}, rotor_count: {rotor_count}, total parts: {len(parts)}")
                                    else:
                                        if debug_callback:
                                            debug_callback(f"Found: {part1} -> {encoded_char} (original case: {encoded_char_original})")
                                            # Format preserving original format (letters or numbers)
                                            pos_str = self._format_positions(parts, j + 3, rotor_count, current_positions)
                                            counter_info = f" Counter {counter_value}" if counter_value is not None else ""
                                            debug_callback(f"Positions: {pos_str}{counter_info} (parsed as: {current_positions}, count: {len(current_positions)}, expected: {rotor_count})")
                                            if len(current_positions) != rotor_count:
                                                debug_callback(f"ERROR: Position count mismatch! Got {len(current_positions)} positions but expected {rotor_count}", color_type=7)
                                    break
                            
                            if encoded_char and current_positions is not None:
                                # Only update last_char if not already set by Interactive mode switch
                                # (Interactive mode switch sets these to uppercase values from LOCAL INPUT above)
                                # LOCAL INPUT FROM ENIGMA TAKES PRIORITY - don't overwrite with message character (char)
                                if self.function_mode != 'Interactive':
                                    # Not in Interactive mode - update normally with message character
                                    self.last_char_original = char
                                    self.last_char_received = encoded_char_original if encoded_char_original else encoded_char
                                elif not (self.last_char_original and self.last_char_original.isupper()):
                                    # In Interactive mode but values not set yet (shouldn't happen, but safety check)
                                    # This should not occur if Interactive mode switch worked correctly
                                    # If it does, preserve any existing uppercase values rather than overwriting with char
                                    if not self.last_char_original or not self.last_char_original.isupper():
                                        # Only set if truly missing - prefer preserving local input
                                        encoded_val = encoded_char_original if encoded_char_original else encoded_char
                                        self.last_char_received = encoded_val.upper() if encoded_val else None
                                    # Note: We don't set last_char_original here because it should have been set
                                    # by the Interactive mode switch above with the LOCAL INPUT (part1)
                                
                                if previous_positions is not None and current_positions is not None:
                                    # Check if positions changed OR counter incremented
                                    positions_changed = current_positions != previous_positions
                                    counter_incremented = False
                                    
                                    # If positions unchanged, check if counter has incremented
                                    if not positions_changed and current_counter is not None and previous_counter is not None:
                                        if current_counter > previous_counter:
                                            counter_incremented = True
                                            if debug_callback:
                                                debug_callback(f"Positions unchanged but counter incremented: {previous_counter} -> {current_counter}, accepting encoding")
                                    
                                    if not positions_changed and not counter_incremented:
                                        if debug_callback:
                                            # Show formatted positions for better debugging
                                            prev_str = self._format_positions(parts, j + 3, rotor_count, previous_positions) if previous_positions else "None"
                                            curr_str = self._format_positions(parts, j + 3, rotor_count, current_positions) if current_positions else "None"
                                            counter_info = ""
                                            if previous_counter is not None:
                                                counter_info = f" (previous counter: {previous_counter}"
                                                if current_counter is not None:
                                                    counter_info += f", current counter: {current_counter})"
                                                else:
                                                    counter_info += ", no counter in current response)"
                                            debug_callback(f"Positions unchanged: {prev_str} == {curr_str} (as tuples: {previous_positions} == {current_positions}){counter_info}, continuing to read for update...")
                                        found_positions = False
                                        additional_wait = 0.3
                                        additional_start = time.time()
                                        while time.time() - additional_start < additional_wait:
                                            if self.ser.in_waiting > 0:
                                                additional_data = self.ser.read(self.ser.in_waiting)
                                                response += additional_data
                                                # Log raw additional data received (if enabled)
                                                if debug_callback and additional_data and self.raw_debug_enabled:
                                                    raw_hex = ' '.join(f'{b:02x}' for b in additional_data)
                                                    debug_callback(f"[RAW] Additional data (hex): {raw_hex}")
                                                    debug_callback(f"[RAW] Additional data (repr): {repr(additional_data)}")
                                                resp_text = response.decode('ascii', errors='replace')
                                                resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                                                resp_text = ' '.join(resp_text.split()).strip()
                                                parts = resp_text.split()
                                                for k in range(len(parts) - 2):
                                                    part_k1 = parts[k]
                                                    part_k2 = parts[k+1]
                                                    part_k3 = parts[k+2]
                                                    
                                                    # Check if we have enough parts for positions (2 + rotor_count)
                                                    if (len(part_k1) == 1 and part_k1.isalpha() and
                                                        len(part_k2) == 1 and part_k2.isalpha() and
                                                        part_k3.lower() == 'positions' and k + 2 + rotor_count <= len(parts)):
                                                        pattern_matches = False
                                                        if expect_lowercase:
                                                            # Museum mode or Message Interactive mode: expect lowercase
                                                            if part_k1.islower() and part_k2.islower():
                                                                pattern_matches = True
                                                            elif part_k1.isupper() or part_k2.isupper():
                                                                # Uppercase detected - switch to Interactive mode (uppercase)
                                                                # Initialize display values to None so they show as "-" until Interactive mode input is received
                                                                if debug_callback:
                                                                    debug_callback(f"Uppercase detected in Message Interactive mode (additional read)!", color_type=7)
                                                                    debug_callback(f"  part_k1: '{part_k1}' (isupper: {part_k1.isupper()})", color_type=7)
                                                                    debug_callback(f"  part_k2: '{part_k2}' (isupper: {part_k2.isupper()})", color_type=7)
                                                                    debug_callback(f"  part_k3: '{part_k3}'", color_type=7)
                                                                    debug_callback(f"  Full parts list: {parts}", color_type=7)
                                                                    debug_callback(f"  Full response: {repr(response)}", color_type=7)
                                                                self.last_char_original = None
                                                                self.last_char_received = None
                                                                self.function_mode = 'Interactive'
                                                                self.save_config(preserve_always_send_config=True)
                                                                if mode_update_callback:
                                                                    mode_update_callback()
                                                                if debug_callback:
                                                                    debug_callback(f"Switching to Interactive mode (uppercase)", color_type=7)
                                                                pattern_matches = True
                                                        else:
                                                            # Interactive mode: expect uppercase
                                                            if part_k1.isupper() and part_k2.isupper():
                                                                pattern_matches = True
                                                        
                                                        if pattern_matches:
                                                            # Parse positions using helper function (handles letters and numbers, 3 or 4 rotors)
                                                            new_positions = self._parse_positions(parts, k + 3, rotor_count)
                                                            
                                                            # Check for counter in additional data
                                                            new_counter = None
                                                            counter_idx = k + 3 + rotor_count
                                                            if counter_idx < len(parts) and parts[counter_idx].lower() == 'counter':
                                                                if counter_idx + 1 < len(parts):
                                                                    try:
                                                                        new_counter = int(parts[counter_idx + 1])
                                                                    except ValueError:
                                                                        pass
                                                            
                                                            # Accept if positions changed OR counter incremented
                                                            positions_changed = new_positions is not None and new_positions != previous_positions
                                                            counter_incremented = False
                                                            if new_counter is not None and previous_counter is not None:
                                                                if new_counter > previous_counter:
                                                                    counter_incremented = True
                                                            
                                                            if positions_changed or counter_incremented:
                                                                if positions_changed:
                                                                    current_positions = new_positions
                                                                encoded_char_original = part_k2
                                                                encoded_char = encoded_char_original.upper()
                                                                if new_counter is not None:
                                                                    current_counter = new_counter
                                                                if debug_callback:
                                                                    if positions_changed:
                                                                        # Format preserving original format (letters or numbers)
                                                                        pos_str_prev = self._format_positions(parts, k + 3, rotor_count, previous_positions) if previous_positions else "None"
                                                                        pos_str_new = self._format_positions(parts, k + 3, rotor_count, new_positions)
                                                                        debug_callback(f"Found updated positions: {pos_str_prev} -> {pos_str_new}")
                                                                    if counter_incremented:
                                                                        debug_callback(f"Found counter increment: {previous_counter} -> {new_counter}")
                                                                break
                                                # Break if positions changed OR counter incremented
                                                if current_positions != previous_positions or (current_counter is not None and previous_counter is not None and current_counter > previous_counter):
                                                    break
                                            time.sleep(0.05)
                                        
                                        # Accept encoding if positions changed OR counter incremented
                                        positions_changed = current_positions != previous_positions
                                        counter_incremented = False
                                        if current_counter is not None and previous_counter is not None:
                                            if current_counter > previous_counter:
                                                counter_incremented = True
                                        
                                        if positions_changed or counter_incremented:
                                            encoded_chars.append(encoded_char)
                                            if positions_changed:
                                                previous_positions = current_positions
                                                # Preserve original format (letters or numbers) when updating
                                                update_ring_position(current_positions, parts, j + 3)
                                            if counter_incremented:
                                                previous_counter = current_counter
                                                if debug_callback:
                                                    debug_callback(f"Accepted encoding due to counter increment: {previous_counter - 1 if previous_counter else 'unknown'} -> {current_counter}")
                                            success = True
                                            if callback:
                                                if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                                    if debug_callback:
                                                        debug_callback("Message sending stopped by callback")
                                                    return False
                                        else:
                                            if debug_callback:
                                                debug_callback(f"Still no position update or counter increment after waiting")
                                            success = False
                                    else:
                                        # Positions changed or counter incremented - accept encoding
                                        if debug_callback:
                                            if current_positions != previous_positions:
                                                debug_callback(f"Positions updated: {previous_positions} -> {current_positions}")
                                            if current_counter is not None and previous_counter is not None and current_counter > previous_counter:
                                                debug_callback(f"Counter incremented: {previous_counter} -> {current_counter}")
                                        encoded_chars.append(encoded_char)
                                        previous_positions = current_positions
                                        previous_counter = current_counter
                                        # Preserve original format (letters or numbers) when updating
                                        update_ring_position(current_positions, parts, j + 3)
                                        success = True
                                        if callback:
                                            if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                                if debug_callback:
                                                    debug_callback("Message sending stopped by callback")
                                                return False
                                elif current_positions is not None:
                                    # First character - just record positions and counter
                                    encoded_chars.append(encoded_char)
                                    previous_positions = current_positions
                                    previous_counter = current_counter
                                    # Preserve original format (letters or numbers) when updating
                                    update_ring_position(current_positions, parts, j + 3)
                                    success = True
                                    if callback:
                                        if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                            if debug_callback:
                                                debug_callback("Message sending stopped by callback")
                                            return False
                                else:
                                    if debug_callback:
                                        debug_callback(f"Warning: Could not extract positions from response")
                                    encoded_chars.append(encoded_char)
                                    success = True
                                    if callback:
                                        if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                            if debug_callback:
                                                debug_callback("Message sending stopped by callback")
                                            return False
                            else:
                                if debug_callback:
                                    debug_callback(f"Warning: Could not parse encoded character")
                                    debug_callback(f"Response: {resp_text}")
                                    debug_callback(f"Parts: {parts}")
                                    debug_callback(f"Expect lowercase: {expect_lowercase}, Function mode: {self.function_mode}")
                        except Exception as e:
                            if debug_callback:
                                debug_callback(f"Error parsing response: {e}", color_type=7)
                                if resp_text:
                                    debug_callback(f"Response text: {resp_text[:100]}")
                                else:
                                    debug_callback(f"Response bytes: {response[:100] if response else 'None'}")
                                debug_callback(f"Parts count: {len(parts) if parts else 0}")
                                import traceback
                                debug_callback(f"Traceback: {traceback.format_exc()}", color_type=7)
                    elif response and not found_positions:
                        if debug_callback:
                            resp_text = response.decode('ascii', errors='replace')
                            debug_callback(f"Warning: Incomplete response (no Positions found): {resp_text[:50]}")
                
                if not success:
                    retry_count += 1
                    if retry_count < max_retries:
                        if debug_callback:
                            debug_callback(f"Retrying character '{char}' (attempt {retry_count + 1}/{max_retries})")
                        self.send_command(b'\r?MO\r\n\r\n', debug_callback=debug_callback)
                        time.sleep(0.5)
                        self.return_to_encode_mode(debug_callback=debug_callback)
                        time.sleep(0.5)
                    else:
                        if debug_callback:
                            debug_callback(f"Failed to encode '{char}' after {max_retries} attempts")
                        char_count -= 1
                
                if success and i < len(filtered_message) - 1:
                    if self.generating_messages:
                        if debug_callback:
                            debug_callback(f"Skipping delay (generating messages)")
                        time.sleep(0.1)
                    else:
                        current_delay = self.character_delay_ms
                        if current_delay > 0:
                            if debug_callback:
                                debug_callback(f"Character delay: {current_delay}ms")
                            time.sleep(current_delay / 1000.0)
                        else:
                            if debug_callback:
                                debug_callback(f"Character delay: 0ms")
                            time.sleep(0.1)
            
            if debug_callback and encoded_chars:
                encoded_result = ''.join(encoded_chars)
                debug_callback(f"Encoded result (ungrouped): {encoded_result}")
                grouped_result = self._group_encoded_text(encoded_result)
                debug_callback(f"Encoded result (grouped): {grouped_result}")
            return True
        except Exception as e:
            if debug_callback:
                debug_callback(f"Error in send_message: {e}")
            return False
    
    def _group_encoded_text(self, text: str) -> str:
        """Group encoded text into groups of configured size with spaces"""
        if not text:
            return ""
        group_size = self.word_group_size
        groups = []
        for i in range(0, len(text), group_size):
            groups.append(text[i:i+group_size])
        return ' '.join(groups)
    
    def format_message_for_display(self, message: str) -> str:
        """Format message for display - group if no spaces, otherwise keep as is"""
        if not message:
            return ""
        if ' ' not in message:
            return self._group_encoded_text(message)
        return message

