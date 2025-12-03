#!/usr/bin/env python3
"""
Enigma Museum Controller - CLI tool for controlling Enigma device
Duplicates ESP32 controller functionality with curses-based menu interface
"""

# Application Version
VERSION = "v1.05"

import serial
import time
import sys
import curses
import random
import json
import os
import threading
import socket
import html as html_module
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple, List

# Serial Configuration
DEFAULT_DEVICE = '/dev/ttyACM0'
BAUD_RATE = 9600
CHAR_TIMEOUT = 2.0  # seconds to wait for character response
CMD_TIMEOUT = 3.0   # seconds to wait for command response

# Config file path - in same directory as script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'enigma-museum-config.json')
ENGLISH_MSG_FILE = os.path.join(SCRIPT_DIR, 'english.msg')
GERMAN_MSG_FILE = os.path.join(SCRIPT_DIR, 'german.msg')

def load_messages_from_file(filepath: str) -> List[str]:
    """Load messages from a JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                if isinstance(messages, list):
                    return messages
    except Exception:
        pass
    return []

# Load museum messages from files
ENGLISH_MESSAGES = load_messages_from_file(ENGLISH_MSG_FILE)
GERMAN_MESSAGES = load_messages_from_file(GERMAN_MSG_FILE)

# Fallback messages if files are empty or missing
if not ENGLISH_MESSAGES:
    ENGLISH_MESSAGES = ["NO MESSAGES LOADED FROM english.msg FILE"]

if not GERMAN_MESSAGES:
    GERMAN_MESSAGES = ["NO MESSAGES LOADED FROM german.msg FILE"]


class EnigmaController:
    """Handles serial communication with Enigma device"""
    
    def __init__(self, device: str = DEFAULT_DEVICE, preserve_device: bool = False):
        self.device = device
        self.ser: Optional[serial.Serial] = None
        self.config = {
            'mode': 'I',
            'rotor_set': 'A III IV I',
            'ring_settings': '01 01 01',
            'ring_position': '20 6 10',
            'pegboard': 'VF PQ'
        }
        self.function_mode = 'Interactive'
        self.museum_delay = 60
        self.always_send_config = False  # Send config before each message
        self.word_group_size = 5  # Default to 5-character groups
        self.character_delay_ms = 0  # Delay in milliseconds between characters when encoding
        self.generating_messages = False  # Flag to skip delays during message generation
        self.web_server_enabled = False  # Web server enabled/disabled flag
        self.web_server_port = 8080  # Default web server port
        self.web_server_ip: Optional[str] = None  # Web server IP address when running
        self.enable_slides = False  # Enable slides feature
        self.config_file = CONFIG_FILE
        self.last_char_sent: Optional[str] = None  # Last character sent TO Enigma
        self.last_char_received: Optional[str] = None  # Last character received FROM Enigma (encoded)
        self.last_char_original: Optional[str] = None  # Original character that was encoded
        # Load saved config if it exists
        self.load_config(preserve_device=preserve_device)
    
    def save_config(self, preserve_ring_position=True):
        """Save current configuration to file
        
        Args:
            preserve_ring_position: If True, preserve ring_position from saved config
                                   (prevents encoding updates from being saved).
                                   Set to False when explicitly setting ring position.
        """
        try:
            config_to_save = self.config.copy()
            
            # If preserving ring position, use the saved value instead of current (which may be updated during encoding)
            if preserve_ring_position:
                saved = self.get_saved_config()
                saved_ring_position = saved.get('config', {}).get('ring_position')
                if saved_ring_position:
                    config_to_save['ring_position'] = saved_ring_position
            
            config_data = {
                'config': config_to_save,
                'function_mode': self.function_mode,
                'museum_delay': self.museum_delay,
                'always_send_config': self.always_send_config,
                'word_group_size': self.word_group_size,
                'character_delay_ms': self.character_delay_ms,
                'web_server_enabled': self.web_server_enabled,
                'web_server_port': self.web_server_port,
                'enable_slides': self.enable_slides,
                'device': self.device
            }
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            return True
        except Exception as e:
            return False
    
    def load_config(self, preserve_device: bool = False):
        """Load configuration from file
        
        Args:
            preserve_device: If True, don't overwrite self.device with device from config file
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    # Update config if present
                    if 'config' in config_data:
                        self.config.update(config_data['config'])
                    if 'function_mode' in config_data:
                        self.function_mode = config_data['function_mode']
                    if 'museum_delay' in config_data:
                        self.museum_delay = config_data['museum_delay']
                    if 'always_send_config' in config_data:
                        self.always_send_config = config_data['always_send_config']
                    if 'word_group_size' in config_data:
                        self.word_group_size = config_data['word_group_size']
                    if 'character_delay_ms' in config_data:
                        self.character_delay_ms = config_data['character_delay_ms']
                    if 'web_server_enabled' in config_data:
                        self.web_server_enabled = config_data['web_server_enabled']
                    if 'web_server_port' in config_data:
                        self.web_server_port = config_data['web_server_port']
                    if 'enable_slides' in config_data:
                        self.enable_slides = config_data['enable_slides']
                    if 'device' in config_data and not preserve_device:
                        self.device = config_data['device']
                return True
        except Exception:
            # If config file is corrupted or doesn't exist, use defaults
            pass
        return False
    
    def get_saved_config(self):
        """Get saved configuration from file (without modifying in-memory config)"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    saved_config = {}
                    if 'config' in config_data:
                        saved_config['config'] = config_data['config'].copy()
                    else:
                        saved_config['config'] = self.config.copy()  # Fallback to defaults
                    saved_config['function_mode'] = config_data.get('function_mode', self.function_mode)
                    saved_config['museum_delay'] = config_data.get('museum_delay', self.museum_delay)
                    saved_config['always_send_config'] = config_data.get('always_send_config', self.always_send_config)
                    saved_config['word_group_size'] = config_data.get('word_group_size', self.word_group_size)
                    saved_config['character_delay_ms'] = config_data.get('character_delay_ms', self.character_delay_ms)
                    saved_config['web_server_enabled'] = config_data.get('web_server_enabled', self.web_server_enabled)
                    saved_config['web_server_port'] = config_data.get('web_server_port', self.web_server_port)
                    saved_config['enable_slides'] = config_data.get('enable_slides', self.enable_slides)
                    saved_config['device'] = config_data.get('device', self.device)
                    return saved_config
        except Exception:
            pass
        # Return defaults if file doesn't exist or is corrupted
        return {
            'config': self.config.copy(),
            'function_mode': self.function_mode,
            'museum_delay': self.museum_delay,
            'always_send_config': self.always_send_config,
            'word_group_size': self.word_group_size,
            'character_delay_ms': self.character_delay_ms,
            'web_server_enabled': self.web_server_enabled,
            'web_server_port': self.web_server_port,
            'enable_slides': self.enable_slides,
            'device': self.device
        }
        
    def connect(self) -> bool:
        """Connect to serial device"""
        try:
            self.ser = serial.Serial(
                port=self.device,
                baudrate=BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            time.sleep(2)  # Wait for device to be ready
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            return True
        except serial.SerialException as e:
            return False
    
    def disconnect(self):
        """Close serial connection"""
        # Stop background monitoring
        self.stop_monitoring()
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def start_monitoring(self):
        """Start background thread to monitor Enigma input (no-op, monitoring was removed)"""
        # Monitoring thread was removed - this method is kept for compatibility
        pass
    
    def stop_monitoring(self):
        """Stop background monitoring thread (no-op, monitoring was removed)"""
        # Monitoring thread was removed - this method is kept for compatibility
        pass
    
    def _monitor_input(self):
        """Background thread to continuously monitor serial input from Enigma"""
        buffer = b''
        last_data_time = None
        processing_timeout = 0.15  # Wait 150ms of silence before processing (reduced for faster detection)
        
        while self.monitoring_active:
            try:
                # Always read data immediately to prevent loss
                # Read aggressively to catch data before operations clear the buffer
                if self.ser and self.ser.is_open:
                    try:
                        # Read all available data in one go
                        if self.ser.in_waiting > 0:
                            data = self.ser.read(self.ser.in_waiting)
                            if data:
                                buffer += data
                                last_data_time = time.time()
                    except Exception:
                        pass  # Ignore read errors
                
                # Process buffer if we have data and enough time has passed
                if buffer and last_data_time:
                    current_time = time.time()
                    time_since_data = current_time - last_data_time
                    
                    # Process if we've had silence for the timeout period
                    # OR if buffer contains "Positions" (complete response detected)
                    # OR if buffer is getting large (might indicate complete response)
                    buffer_has_positions = b'Positions' in buffer or b'positions' in buffer
                    if time_since_data >= processing_timeout or buffer_has_positions or len(buffer) > 200:
                        # Process buffer regardless of operation status
                        # (we've already read the data, so processing won't interfere)
                        # Try to parse as character encoding response
                        try:
                            resp_text = buffer.decode('ascii', errors='replace')
                            resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                            resp_text = ' '.join(resp_text.split()).strip()
                            
                            # Look for pattern: "INPUT ENCODED Positions XX XX XX"
                            parts = resp_text.split()
                            found_keypress = False
                            for j in range(len(parts) - 2):
                                if (len(parts[j]) == 1 and parts[j].isalpha() and parts[j].isupper() and
                                    len(parts[j+1]) == 1 and parts[j+1].isalpha() and parts[j+1].isupper() and
                                    parts[j+2].lower() == 'positions'):
                                    # Found unexpected character encoding response (keypress detected)
                                    original_char = parts[j]
                                    encoded_char = parts[j+1]
                                    found_keypress = True
                                    
                                    # Log keypress to debug output
                                    if self.monitoring_debug_callback:
                                        pos_info = ""
                                        if j + 5 < len(parts):
                                            try:
                                                pos1 = int(parts[j+3])
                                                pos2 = int(parts[j+4])
                                                pos3 = int(parts[j+5])
                                                pos_info = f" Positions {pos1:02d} {pos2:02d} {pos3:02d}"
                                            except (ValueError, IndexError):
                                                pass
                                        self.monitoring_debug_callback(f">>> '{original_char}'")
                                        self.monitoring_debug_callback(f"<<< {original_char} {encoded_char}{pos_info}")
                                    
                                    # Update last character info
                                    self.last_char_original = original_char
                                    self.last_char_received = encoded_char
                                    
                                    # Trigger UI refresh callback if set
                                    if self.monitoring_ui_refresh_callback:
                                        try:
                                            self.monitoring_ui_refresh_callback()
                                        except Exception:
                                            pass  # Ignore errors in callback
                                    
                                    # Trigger keypress callback if set (for museum mode pause)
                                    if self.monitoring_keypress_callback:
                                        try:
                                            self.monitoring_keypress_callback()
                                        except Exception:
                                            pass  # Ignore errors in callback
                                    
                                    # Extract positions if available
                                    if j + 5 < len(parts):
                                        try:
                                            pos1 = int(parts[j+3])
                                            pos2 = int(parts[j+4])
                                            pos3 = int(parts[j+5])
                                            pos_str = f"{pos1:02d} {pos2:02d} {pos3:02d}"
                                            # Update ring position if different
                                            if self.config.get('ring_position') != pos_str:
                                                self.config['ring_position'] = pos_str
                                        except (ValueError, IndexError):
                                            pass
                                    
                                    break
                            
                            # Clear buffer after processing
                            buffer = b''
                            last_data_time = None
                        except Exception as e:
                            # If parsing fails, clear buffer to avoid accumulation
                            # But keep some data if it might be incomplete
                            if len(buffer) > 500:  # Buffer too large, clear it
                                buffer = b''
                                last_data_time = None
                            # Otherwise keep buffer in case more data arrives
                
                # Sleep briefly to avoid busy-waiting
                time.sleep(0.02)  # Reduced sleep time for more responsive detection
            except Exception:
                # On any error, sleep and continue
                time.sleep(0.1)
    
    def send_command(self, command: bytes, timeout: float = CMD_TIMEOUT, debug_callback=None) -> Optional[str]:
        """Send a command and return response"""
        if not self.ser or not self.ser.is_open:
            return None
        
        try:
            # Clear input buffer before sending command to avoid mixing with previous data
            self.ser.reset_input_buffer()
            time.sleep(0.1)  # Small delay after clearing buffer
            
            # Decode command for logging - ensure we only show the actual command bytes
            # Create a clean string representation directly from the command bytes
            try:
                cmd_str = command.decode('ascii', errors='replace')
                # Remove \r\n and any trailing whitespace for clean display
                cmd_str = cmd_str.replace('\r', '').replace('\n', '').strip()
                # Ensure we're not including any extra data
                if debug_callback:
                    debug_callback(f">>> {cmd_str}")
            except:
                if debug_callback:
                    debug_callback(f">>> {command!r}")  # Show raw bytes if decode fails
            
            # Send the exact command bytes
            self.ser.write(command)
            self.ser.flush()
            
            time.sleep(0.5)  # Initial delay
            response = b''
            start_time = time.time()
            
            # Read response until we get a complete response or timeout
            while time.time() - start_time < timeout:
                if self.ser.in_waiting > 0:
                    response += self.ser.read(self.ser.in_waiting)
                    time.sleep(0.1)
                else:
                    if response:
                        # Wait a bit more to ensure we got the complete response
                        time.sleep(0.2)
                        if self.ser.in_waiting > 0:
                            response += self.ser.read(self.ser.in_waiting)
                        break
                time.sleep(0.01)
            
            # Clear any remaining data in buffer after reading response
            if self.ser.in_waiting > 0:
                self.ser.reset_input_buffer()
            
            if response:
                try:
                    decoded_response = response.decode('ascii', errors='replace')
                    if debug_callback:
                        debug_callback(f"<<< {decoded_response.strip()}")
                    return decoded_response
                except:
                    return None
            return None
        except Exception:
            return None
    
    def query_mode(self, debug_callback=None) -> Optional[str]:
        """Query Enigma model/mode"""
        response = self.send_command(b'\r\n?MO\r\n', debug_callback=debug_callback)
        if response and 'Enigma' in response:
            # Extract model name
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
            # Parse: "Reflector A\nRotors    III II I"
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
        return settings
    
    def set_mode(self, mode: str, debug_callback=None) -> bool:
        """Set Enigma model/mode"""
        if not self.ser or not self.ser.is_open:
            return False
        # Send line return first to ensure clean command
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!MO {mode}\r\n".encode('ascii')
        response = self.send_command(cmd, debug_callback=debug_callback)
        self.config['mode'] = mode
        return response is not None
    
    def set_rotor_set(self, rotor_set: str, debug_callback=None) -> bool:
        """Set rotor configuration"""
        if not self.ser or not self.ser.is_open:
            return False
        # Send line return first to ensure clean command
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!RO {rotor_set}\r\n".encode('ascii')
        response = self.send_command(cmd, debug_callback=debug_callback)
        self.config['rotor_set'] = rotor_set
        return response is not None
    
    def set_ring_settings(self, ring_settings: str, debug_callback=None) -> bool:
        """Set ring settings"""
        if not self.ser or not self.ser.is_open:
            return False
        # Send line return first to ensure clean command
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!RI {ring_settings}\r\n".encode('ascii')
        response = self.send_command(cmd, debug_callback=debug_callback)
        self.config['ring_settings'] = ring_settings
        return response is not None
    
    def set_ring_position(self, ring_position: str, debug_callback=None) -> bool:
        """Set ring position"""
        if not self.ser or not self.ser.is_open:
            return False
        # Send line return first to ensure clean command
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!RP {ring_position}\r\n".encode('ascii')
        response = self.send_command(cmd, debug_callback=debug_callback)
        self.config['ring_position'] = ring_position
        return response is not None
    
    def set_pegboard(self, pegboard: str, debug_callback=None) -> bool:
        """Set pegboard settings"""
        if not self.ser or not self.ser.is_open:
            return False
        if not pegboard:
            pegboard = 'clear'
        # Send line return first to ensure clean command
        self.ser.write(b'\r\n')
        self.ser.flush()
        time.sleep(0.05)
        cmd = f"!PB {pegboard}\r\n".encode('ascii')
        response = self.send_command(cmd, debug_callback=debug_callback)
        self.config['pegboard'] = pegboard if pegboard != 'clear' else ''
        return response is not None
    
    def return_to_encode_mode(self, debug_callback=None) -> bool:
        """Return to encode mode"""
        response = self.send_command(b'?MO\r\n', timeout=1.0, debug_callback=debug_callback)
        return response is not None
    
    def send_message(self, message: str, callback=None, debug_callback=None, position_update_callback=None) -> bool:
        """Send message character by character"""
        if not self.ser or not self.ser.is_open:
            return False
        
        # Ensure encode mode
        self.return_to_encode_mode(debug_callback=debug_callback)
        time.sleep(0.5)
        
        # Send configuration before message if option is enabled
        if self.always_send_config:
            if debug_callback:
                debug_callback("Sending configuration before message...")
            # Reload config from file to ensure we use saved defaults, not current state
            # Preserve device to avoid changing it during operation
            self.load_config(preserve_device=True)
            # Get saved config values (from file, not in-memory)
            saved = self.get_saved_config()
            self.set_mode(saved['config']['mode'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.set_rotor_set(saved['config']['rotor_set'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.set_ring_settings(saved['config']['ring_settings'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.set_ring_position(saved['config']['ring_position'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.set_pegboard(saved['config']['pegboard'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.return_to_encode_mode(debug_callback=debug_callback)
        time.sleep(0.5)
        
        # Filter message to only A-Z characters (remove spaces, numbers, special chars)
        filtered_message = ''.join(c for c in message.upper() if c.isalpha() and c.isupper())
        
        if not filtered_message:
            if debug_callback:
                debug_callback("Warning: No valid A-Z characters in message")
            return False
        
        if debug_callback:
            debug_callback(f"Original message: {message}")
            debug_callback(f"Filtered message (A-Z only): {filtered_message}")
        
        encoded_chars = []
        char_count = 0  # Track actual character number being processed
        previous_positions = None  # Track previous rotor positions to ensure they update
        
        def update_ring_position(new_positions):
            """Helper to update ring position in config and notify UI"""
            if new_positions:
                # Format positions as string (e.g., "20 06 11")
                pos_str = f"{new_positions[0]:02d} {new_positions[1]:02d} {new_positions[2]:02d}"
                self.config['ring_position'] = pos_str
                if position_update_callback:
                    position_update_callback()
        
        try:
            for i, char in enumerate(filtered_message):
                # All characters in filtered_message are already A-Z, so no need to check
                
                char_count += 1  # Increment for each character we attempt to process
                success = False
                
                # Retry loop for this character
                retry_count = 0
                max_retries = 3
                while retry_count < max_retries and not success:
                    # Clear input buffer before sending to ensure we get the right response
                    self.ser.reset_input_buffer()
                    time.sleep(0.1)  # Small delay after clearing
                
                    # Send character
                    if debug_callback:
                        debug_callback(f">>> '{char}'")
                    # Update last character sent
                    self.last_char_sent = char
                    self.ser.write(char.encode('ascii'))
                    self.ser.flush()
                
                    # Wait for complete response - read until we get the encoding response
                    # We need to wait for a period of silence after detecting "Positions" to ensure complete response
                    response = b''
                    start_time = time.time()
                    found_positions = False
                    last_data_time = None
                    silence_duration = 0.2  # Wait 200ms of silence after "Positions" to ensure complete response
                    
                    while time.time() - start_time < CHAR_TIMEOUT:
                            if self.ser.in_waiting > 0:
                                # Read all available data
                                response += self.ser.read(self.ser.in_waiting)
                                last_data_time = time.time()
                                
                                # Check if we have a complete response (contains "Positions")
                                if b'Positions' in response:
                                    # Found "Positions", now wait for silence to ensure we have complete response
                                    silence_start = time.time()
                                    while time.time() - silence_start < silence_duration:
                                        if self.ser.in_waiting > 0:
                                            # More data arrived, read it and reset silence timer
                                            response += self.ser.read(self.ser.in_waiting)
                                            silence_start = time.time()
                                        time.sleep(0.01)
                                    # We've had silence_duration seconds of no new data after "Positions"
                                    found_positions = True
                                    break
                                time.sleep(0.01)
                            else:
                                # No data available
                                if response and b'Positions' in response:
                                    # We have "Positions" but no new data - wait for silence
                                    if last_data_time:
                                        if time.time() - last_data_time >= silence_duration:
                                            found_positions = True
                                            break
                                elif not response:
                                    # No response yet, keep waiting
                                    time.sleep(0.01)
                                else:
                                    # Have some response but no "Positions" yet, keep waiting
                                    time.sleep(0.01)
                            time.sleep(0.01)
                
                    if response and found_positions:
                        try:
                            # Decode and normalize: remove all line returns, carriage returns, and normalize whitespace
                            resp_text = response.decode('ascii', errors='replace')
                            # Remove all line returns and carriage returns
                            resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                            # Normalize multiple spaces to single space
                            resp_text = ' '.join(resp_text.split())
                            resp_text = resp_text.strip()
                            
                            if debug_callback:
                                debug_callback(f"<<< {resp_text}")
                            
                            # Parse response format: "INPUT ENCODED Positions XX XX XX"
                            # Example: "H O Positions 20 06 11"
                            # The encoded character is the 2nd token (the letter after the input letter)
                            parts = resp_text.split()
                            encoded_char = None
                            
                            # Find pattern: two consecutive single uppercase letters followed by "Positions"
                            # This identifies the encoding response: "INPUT ENCODED Positions"
                            current_positions = None
                            for j in range(len(parts) - 2):
                                if (len(parts[j]) == 1 and parts[j].isalpha() and parts[j].isupper() and
                                    len(parts[j+1]) == 1 and parts[j+1].isalpha() and parts[j+1].isupper() and
                                    parts[j+2].lower() == 'positions'):
                                    # Found: letter letter Positions - second letter is encoded
                                    encoded_char = parts[j+1]
                                    
                                    # Extract rotor positions (should be 3 numbers after "Positions")
                                    if j + 5 < len(parts):
                                        try:
                                            pos1 = int(parts[j+3])
                                            pos2 = int(parts[j+4])
                                            pos3 = int(parts[j+5])
                                            current_positions = (pos1, pos2, pos3)
                                        except (ValueError, IndexError):
                                            if debug_callback:
                                                debug_callback(f"Warning: Could not parse positions from response")
                                    
                                    if debug_callback:
                                        debug_callback(f"Found: {parts[j]} -> {encoded_char}")
                                        if current_positions:
                                            debug_callback(f"Positions: {current_positions[0]} {current_positions[1]} {current_positions[2]}")
                                    break
                            
                            if encoded_char:
                                # Update last character info
                                self.last_char_original = char
                                self.last_char_received = encoded_char
                                
                                # Verify that positions have updated (for characters after the first)
                                if previous_positions is not None and current_positions is not None:
                                    if current_positions == previous_positions:
                                        # Positions haven't changed - this might be a duplicate/old response
                                        # Continue reading to get the updated response
                                        if debug_callback:
                                            debug_callback(f"Positions unchanged ({current_positions}), continuing to read for update...")
                                        # Continue the reading loop to get updated positions
                                        # Reset found_positions so we keep reading
                                        found_positions = False
                                        # Read more data if available
                                        additional_wait = 0.3  # Wait up to 300ms more for position update
                                        additional_start = time.time()
                                        while time.time() - additional_start < additional_wait:
                                            if self.ser.in_waiting > 0:
                                                response += self.ser.read(self.ser.in_waiting)
                                                # Re-parse to check for updated positions
                                                resp_text = response.decode('ascii', errors='replace')
                                                resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                                                resp_text = ' '.join(resp_text.split()).strip()
                                                parts = resp_text.split()
                                                # Look for updated positions
                                                for k in range(len(parts) - 2):
                                                    if (len(parts[k]) == 1 and parts[k].isalpha() and parts[k].isupper() and
                                                        len(parts[k+1]) == 1 and parts[k+1].isalpha() and parts[k+1].isupper() and
                                                        parts[k+2].lower() == 'positions' and k + 5 < len(parts)):
                                                        try:
                                                            new_pos1 = int(parts[k+3])
                                                            new_pos2 = int(parts[k+4])
                                                            new_pos3 = int(parts[k+5])
                                                            new_positions = (new_pos1, new_pos2, new_pos3)
                                                            if new_positions != previous_positions:
                                                                # Found updated positions!
                                                                current_positions = new_positions
                                                                encoded_char = parts[k+1]  # Update encoded char in case it's different
                                                                if debug_callback:
                                                                    debug_callback(f"Found updated positions: {previous_positions} -> {current_positions}")
                                                                break
                                                        except (ValueError, IndexError):
                                                            pass
                                                if current_positions != previous_positions:
                                                    break
                                            time.sleep(0.05)
                                        
                                        # Check if we got updated positions
                                        if current_positions != previous_positions:
                                            # Positions updated!
                                            encoded_chars.append(encoded_char)
                                            previous_positions = current_positions
                                            update_ring_position(current_positions)
                                            success = True
                                            if callback:
                                                # Check if callback wants to stop (returns True)
                                                if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                                    # Stop sending message
                                                    if debug_callback:
                                                        debug_callback("Message sending stopped by callback")
                                                    return False
                                        else:
                                            # Still no position update - will retry
                                            if debug_callback:
                                                debug_callback(f"Still no position update after waiting")
                                            success = False
                                    else:
                                        # Positions have changed - good!
                                        if debug_callback:
                                            debug_callback(f"Positions updated: {previous_positions} -> {current_positions}")
                                        encoded_chars.append(encoded_char)
                                        previous_positions = current_positions
                                        update_ring_position(current_positions)
                                        success = True
                                        if callback:
                                            # Use char_count which tracks the actual character being processed
                                            # Check if callback wants to stop (returns True)
                                            if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                                # Stop sending message
                                                if debug_callback:
                                                    debug_callback("Message sending stopped by callback")
                                                return False
                                elif current_positions is not None:
                                    # First character - just record positions
                                    encoded_chars.append(encoded_char)
                                    previous_positions = current_positions
                                    update_ring_position(current_positions)
                                    success = True
                                    if callback:
                                        # Use char_count which tracks the actual character being processed
                                        # Check if callback wants to stop (returns True)
                                        if callback(char_count, len(message), char, encoded_char, resp_text):
                                            # Stop sending message
                                            if debug_callback:
                                                debug_callback("Message sending stopped by callback")
                                            return False
                                else:
                                    # Could not extract positions
                                    if debug_callback:
                                        debug_callback(f"Warning: Could not extract positions from response")
                                    # Still accept the encoded character but warn
                                    encoded_chars.append(encoded_char)
                                    success = True
                                    if callback:
                                        # Check if callback wants to stop (returns True)
                                        if callback(char_count, len(filtered_message), char, encoded_char, resp_text):
                                            # Stop sending message
                                            if debug_callback:
                                                debug_callback("Message sending stopped by callback")
                                            return False
                            else:
                                # Could not find encoded character
                                if debug_callback:
                                    debug_callback(f"Warning: Could not parse encoded character")
                                    debug_callback(f"Response: {resp_text}")
                                    debug_callback(f"Parts: {parts}")
                        except Exception as e:
                            if debug_callback:
                                debug_callback(f"Error parsing response: {e}")
                    elif response and not found_positions:
                        # Got response but it doesn't contain "Positions" - might be incomplete
                        if debug_callback:
                            resp_text = response.decode('ascii', errors='replace')
                            debug_callback(f"Warning: Incomplete response (no Positions found): {resp_text[:50]}")
                
                if not success:
                    retry_count += 1
                    if retry_count < max_retries:
                        if debug_callback:
                            debug_callback(f"Retrying character '{char}' (attempt {retry_count + 1}/{max_retries})")
                        # Reset and retry
                        self.send_command(b'\r?MO\r\n\r\n', debug_callback=debug_callback)
                        time.sleep(0.5)
                        self.return_to_encode_mode(debug_callback=debug_callback)
                        time.sleep(0.5)
                    else:
                        if debug_callback:
                            debug_callback(f"Failed to encode '{char}' after {max_retries} attempts")
                        # Decrement char_count since we didn't successfully process this character
                        char_count -= 1
                
                # Apply delay between characters AFTER successful encoding (outside retry loop)
                # Only delay if character was successfully encoded and there are more characters to process
                if success and i < len(filtered_message) - 1:
                    # Skip delay if generating messages
                    if self.generating_messages:
                        if debug_callback:
                            debug_callback(f"Skipping delay (generating messages)")
                        # Small delay after successful encoding to ensure device is ready for next character
                        time.sleep(0.1)
                    else:
                        # Normal delay handling
                        current_delay = self.character_delay_ms
                        if current_delay > 0:
                            if debug_callback:
                                debug_callback(f"Character delay: {current_delay}ms")
                            time.sleep(current_delay / 1000.0)
                        else:
                            # Small delay after successful encoding to ensure device is ready for next character
                            if debug_callback:
                                debug_callback(f"Character delay: 0ms")
                            time.sleep(0.1)
        
            if debug_callback and encoded_chars:
                encoded_result = ''.join(encoded_chars)
                debug_callback(f"Encoded result (ungrouped): {encoded_result}")
                # Group the encoded result
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
        # If message contains no spaces, group it
        if ' ' not in message:
            return self._group_encoded_text(message)
        # Otherwise, return as-is
        return message


class MuseumWebServer:
    """Web server for displaying museum mode status"""
    
    def __init__(self, enabled: bool, port: int, data_callback):
        """
        Args:
            enabled: Whether web server is enabled
            port: Port to listen on
            data_callback: Function that returns dict with museum mode data
        """
        self.enabled = enabled
        self.port = port
        self.data_callback = data_callback
        self.server = None
        self.server_thread = None
        self.running = False
        # Path to logo image
        self.logo_path = os.path.join(SCRIPT_DIR, 'enigma.png')
    
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            # Connect to a remote address to determine local IP
            # This doesn't actually send data, just determines the route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            # Fallback to localhost
            return "127.0.0.1"
    
    def start(self):
        """Start the web server in a separate thread"""
        if not self.enabled:
            return None
        
        self.running = True
        
        # Store callback reference and server instance for handler
        data_callback_ref = self.data_callback
        server_instance = self  # Reference to server instance for logo path
        
        class MuseumHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    # Get current data using the callback
                    try:
                        data = data_callback_ref()
                    except Exception as e:
                        # Fallback if callback fails
                        data = {
                            'function_mode': 'N/A',
                            'delay': 60,
                            'log_messages': [f'Error getting data: {str(e)}'],
                            'always_send': False,
                            'config': {}
                        }
                    
                    if self.path == '/' or self.path == '/index.html':
                        # Redirect root to /status
                        self.send_response(302)
                        self.send_header('Location', '/status')
                        self.end_headers()
                    elif self.path == '/status':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        
                        # Generate status HTML
                        html = self.generate_status_html(data)
                        self.wfile.write(html.encode('utf-8'))
                        self.wfile.flush()
                    elif self.path == '/message':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        
                        # Generate kiosk HTML
                        html = self.generate_message_html(data)
                        self.wfile.write(html.encode('utf-8'))
                        self.wfile.flush()
                    elif self.path == '/enigma.png':
                        # Serve logo image
                        try:
                            if os.path.exists(server_instance.logo_path):
                                with open(server_instance.logo_path, 'rb') as f:
                                    image_data = f.read()
                                self.send_response(200)
                                self.send_header('Content-type', 'image/png')
                                self.send_header('Cache-Control', 'public, max-age=3600')
                                self.end_headers()
                                self.wfile.write(image_data)
                                self.wfile.flush()
                            else:
                                self.send_response(404)
                                self.end_headers()
                        except Exception:
                            self.send_response(404)
                            self.end_headers()
                    elif self.path.startswith('/slides/'):
                        # Serve slide images
                        try:
                            slide_file_path = os.path.join(SCRIPT_DIR, self.path.lstrip('/'))
                            if os.path.exists(slide_file_path) and os.path.isfile(slide_file_path):
                                with open(slide_file_path, 'rb') as f:
                                    image_data = f.read()
                                self.send_response(200)
                                self.send_header('Content-type', 'image/png')
                                self.send_header('Cache-Control', 'no-cache')  # Don't cache slides as they change
                                self.end_headers()
                                self.wfile.write(image_data)
                                self.wfile.flush()
                            else:
                                self.send_response(404)
                                self.end_headers()
                        except Exception:
                            self.send_response(404)
                            self.end_headers()
                    else:
                        self.send_response(404)
                        self.end_headers()
                except Exception as e:
                    # Send error response
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(f"Error: {str(e)}".encode('utf-8'))
                    except:
                        pass
            
            def generate_status_html(self, data):
                """Generate HTML page with museum mode status information"""
                function_mode = data.get('function_mode', 'N/A')
                delay = data.get('delay', 60)
                log_messages = data.get('log_messages', [])
                always_send = data.get('always_send', False)
                config = data.get('config', {})
                
                # Format config info
                mode = config.get('mode', 'N/A')
                rotors = config.get('rotor_set', 'N/A')
                ring_settings = config.get('ring_settings', 'N/A')
                ring_position = config.get('ring_position', 'N/A')
                pegboard = config.get('pegboard', 'clear')
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Enigma Museum Mode</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body {{
            font-family: 'Courier New', monospace;
            background-color: #000;
            color: #0f0;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #0ff;
            border-bottom: 2px solid #0ff;
            padding-bottom: 10px;
        }}
        .settings {{
            background-color: #111;
            border: 1px solid #0ff;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .settings h2 {{
            color: #0ff;
            margin-top: 0;
        }}
        .settings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 10px;
        }}
        .setting-item {{
            padding: 5px;
        }}
        .setting-label {{
            color: #0f0;
            font-weight: bold;
        }}
        .setting-value {{
            color: #fff;
        }}
        .log {{
            background-color: #111;
            border: 1px solid #0f0;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            max-height: 500px;
            overflow-y: auto;
        }}
        .log h2 {{
            color: #0f0;
            margin-top: 0;
        }}
        .log-entry {{
            padding: 5px;
            border-bottom: 1px solid #333;
            font-size: 14px;
        }}
        .log-entry:last-child {{
            border-bottom: none;
        }}
        .status {{
            background-color: #111;
            border: 1px solid #ff0;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .status h2 {{
            color: #ff0;
            margin-top: 0;
        }}
        .note {{
            color: #888;
            font-style: italic;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Enigma Museum Mode Status</h1>
        
        <div class="status">
            <h2>Status</h2>
            <div class="settings-grid">
                <div class="setting-item">
                    <span class="setting-label">Function Mode:</span>
                    <span class="setting-value">{function_mode}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Delay:</span>
                    <span class="setting-value">{delay} seconds</span>
                </div>
            </div>
            {f'<div class="note">Note: Sending saved configuration before each message...</div>' if always_send else ''}
        </div>
        
        <div class="settings">
            <h2>Enigma Configuration</h2>
            <div class="settings-grid">
                <div class="setting-item">
                    <span class="setting-label">Mode:</span>
                    <span class="setting-value">{mode}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Rotors:</span>
                    <span class="setting-value">{rotors}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Ring Settings:</span>
                    <span class="setting-value">{ring_settings}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Ring Position:</span>
                    <span class="setting-value">{ring_position}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Pegboard:</span>
                    <span class="setting-value">{pegboard}</span>
                </div>
            </div>
        </div>
        
        <div class="log">
            <h2>Activity Log</h2>
"""
                # Add log messages (most recent first)
                # Escape HTML to prevent issues
                if log_messages:
                    for msg in reversed(log_messages[-50:]):  # Show last 50 messages
                        escaped_msg = html_module.escape(str(msg))
                        html += f'            <div class="log-entry">{escaped_msg}</div>\n'
                else:
                    html += '            <div class="log-entry">No activity yet...</div>\n'
                
                html += f"""        </div>
        
        <div style="text-align: center; margin-top: 20px; color: #888;">
            <p>Page auto-refreshes every 2 seconds</p>
            <p><a href="/message" style="color: #0ff;">View Kiosk Display</a></p>
            <p>Museum Display {VERSION}</p>
        </div>
    </div>
</body>
</html>"""
                return html
            
            def generate_message_html(self, data):
                """Generate HTML page for museum kiosk display"""
                # Use current config (updates in real-time)
                config = data.get('config', {})
                log_messages = data.get('log_messages', [])
                
                # Get mode type (encode or decode)
                is_encode_mode = data.get('is_encode_mode', True)
                
                # Get enable_slides setting
                enable_slides = data.get('enable_slides', False)
                
                # Get slide path
                slide_path = data.get('slide_path', None)
                
                # Get character delay and current character index for highlighting
                character_delay_ms = data.get('character_delay_ms', 0)
                current_char_index = data.get('current_char_index', 0)
                
                # Get real-time encoded/decoded text if available
                current_encoded_text = data.get('current_encoded_text', '')
                
                # Extract current message from log based on mode
                current_message = None
                result_message = None
                
                if is_encode_mode:
                    # Encode mode: look for "Encoding:" and "Encoded:" pair
                    if current_encoded_text:
                        result_message = current_encoded_text
                        # Find the corresponding encoding message - look for MSG line after Encoding:
                        # When iterating in reverse, we see MSG before Encoding, so capture MSG first
                        msg_message = None
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('  MSG:'):
                                msg_message = msg_str.replace('  MSG:', '').strip()
                            elif msg_str.startswith('Encoding:'):
                                if msg_message:
                                    current_message = msg_message
                                    break
                    else:
                        # Look for the most recent encoded message first
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('Encoded:'):
                                result_message = msg_str.replace('Encoded:', '').strip()
                                break
                        # Then find the corresponding encoding message - look for MSG line after Encoding:
                        found_encoded = False
                        msg_message = None
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('Encoded:'):
                                found_encoded = True
                            elif found_encoded and msg_str.startswith('  MSG:'):
                                msg_message = msg_str.replace('  MSG:', '').strip()
                            elif found_encoded and msg_str.startswith('Encoding:'):
                                if msg_message:
                                    current_message = msg_message
                                    break
                        # If no encoded message found yet, just get the most recent encoding MSG message
                        if not current_message:
                            msg_message = None
                            for msg in reversed(log_messages):
                                msg_str = str(msg)
                                if msg_str.startswith('  MSG:'):
                                    msg_message = msg_str.replace('  MSG:', '').strip()
                                elif msg_str.startswith('Encoding:'):
                                    if msg_message:
                                        current_message = msg_message
                                        break
                else:
                    # Decode mode: look for "Decoding:" and "Decoded:" pair
                    if current_encoded_text:
                        result_message = current_encoded_text
                        # Find the corresponding decoding message - look for CODED line after Decoding:
                        # When iterating in reverse, we see CODED before Decoding, so capture CODED first
                        coded_message = None
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('  CODED:'):
                                coded_message = msg_str.replace('  CODED:', '').strip()
                            elif msg_str.startswith('Decoding:'):
                                if coded_message:
                                    current_message = coded_message
                                    break
                    else:
                        # Look for the most recent decoded message first
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('Decoded:'):
                                result_message = msg_str.replace('Decoded:', '').strip()
                                break
                        # Then find the corresponding decoding message - look for CODED line after Decoding:
                        found_decoded = False
                        coded_message = None
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('Decoded:'):
                                found_decoded = True
                            elif found_decoded and msg_str.startswith('  CODED:'):
                                coded_message = msg_str.replace('  CODED:', '').strip()
                            elif found_decoded and msg_str.startswith('Decoding:'):
                                if coded_message:
                                    current_message = coded_message
                                    break
                    # If no decoded message found yet, just get the most recent decoding CODED message
                    if not current_message:
                        coded_message = None
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('  CODED:'):
                                coded_message = msg_str.replace('  CODED:', '').strip()
                            elif msg_str.startswith('Decoding:'):
                                if coded_message:
                                    current_message = coded_message
                                    break
                
                # Format config info
                mode = config.get('mode', 'N/A')
                rotors = config.get('rotor_set', 'N/A')
                ring_settings = config.get('ring_settings', 'N/A')
                ring_position = config.get('ring_position', 'N/A')
                
                # Extract rotor numbers from rotor_set (e.g., "A III IV I" -> "III IV I")
                rotor_display = rotors
                if ' ' in rotors:
                    parts = rotors.split()
                    if len(parts) > 1:
                        # Skip reflector (first part) and show rotors
                        rotor_display = ' '.join(parts[1:])
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Enigma Museum Kiosk</title>
    <meta http-equiv="refresh" content="2">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            position: fixed;
        }}
        body {{
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            padding: 0.8vh 0.8vw;
        }}
        .kiosk-container {{
            width: 100%;
            max-width: 98vw;
            text-align: center;
            display: flex;
            flex-direction: column;
            height: 100%;
            max-height: 98vh;
            justify-content: space-between;
        }}
        .logo-section {{
            margin-bottom: 1vh;
            flex-shrink: 0;
            max-height: 15vh;
        }}
        .logo-image {{
            max-width: min(25vw, 250px);
            max-height: min(12vh, 120px);
            width: auto;
            height: auto;
            margin-bottom: 0.5vh;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
        }}
        .enigma-logo {{
            font-size: min(4.5vw, 48px);
            font-weight: bold;
            color: #ffd700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            letter-spacing: 0.3vw;
            margin-bottom: 0.3vh;
        }}
        .subtitle {{
            font-size: min(1.5vw, 16px);
            color: #ccc;
            letter-spacing: 0.15vw;
            margin-bottom: 0;
        }}
        .machine-display {{
            background: rgba(0, 0, 0, 0.6);
            border: 2px solid #ffd700;
            border-radius: 10px;
            padding: min(1.5vh, 15px);
            margin: min(1vh, 10px) 0;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
            flex-shrink: 0;
            max-height: 25vh;
            overflow: hidden;
        }}
        .config-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: min(1vw, 10px);
            margin: min(1vh, 10px) 0;
        }}
        .config-item {{
            background: rgba(255, 255, 255, 0.1);
            padding: min(1vh, 10px);
            border-radius: 6px;
            border: 1px solid rgba(255, 215, 0, 0.3);
        }}
        .config-label {{
            font-size: min(1.1vw, 11px);
            color: #ffd700;
            text-transform: uppercase;
            letter-spacing: 0.1vw;
            margin-bottom: 0.3vh;
            font-weight: bold;
        }}
        .config-value {{
            font-size: min(2vw, 20px);
            color: #fff;
            font-weight: bold;
            font-family: 'Courier New', monospace;
        }}
        .message-container {{
            display: flex;
            flex-direction: row;
            gap: min(1vw, 10px);
            margin: min(1vh, 10px) 0;
            flex-grow: 1;
            min-height: 0;
            max-height: 50vh;
        }}
        .message-section {{
            margin: min(1vh, 10px) 0;
            padding: min(1.5vh, 15px);
            background: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            border: 2px solid #0ff;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 0;
            max-height: 50vh;
        }}
        .message-container .message-section {{
            margin: 0;
            width: 50%;
            max-height: none;
        }}
        .slide-section {{
            margin: 0;
            padding: min(1.5vh, 15px);
            background: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            border: 2px solid #0ff;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 0;
            width: 50%;
        }}
        .slide-placeholder {{
            background: rgba(255, 255, 255, 0.05);
            border: 2px dashed rgba(255, 215, 0, 0.5);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(255, 215, 0, 0.6);
            font-size: min(2vw, 20px);
            font-style: italic;
            width: 100%;
            height: 100%;
            min-height: 200px;
        }}
        .slide-image {{
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border-radius: 8px;
            display: block;
        }}
        .slide-section {{
            overflow: hidden;
        }}
        .message-label {{
            font-size: min(1.4vw, 14px);
            color: #0ff;
            text-transform: uppercase;
            letter-spacing: 0.2vw;
            margin-bottom: min(1vh, 10px);
            flex-shrink: 0;
        }}
        .message-text {{
            font-size: min(2.4vw, 24px);
            color: #fff;
            font-family: 'Courier New', monospace;
            letter-spacing: 0.2vw;
            word-break: break-word;
            line-height: 1.4;
            overflow-y: auto;
            overflow-x: hidden;
            flex-grow: 1;
            min-height: 0;
        }}
        .char-highlight {{
            background-color: #ffd700;
            color: #000;
            font-weight: bold;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        .encoded-text {{
            font-size: min(2.2vw, 22px);
            color: #0f0;
            font-family: 'Courier New', monospace;
            letter-spacing: 0.2vw;
            word-break: break-word;
            margin-top: min(1vh, 10px);
            padding-top: min(1vh, 10px);
            border-top: 1px solid rgba(0, 255, 0, 0.3);
            flex-shrink: 0;
            overflow-y: auto;
            overflow-x: hidden;
            max-height: 20vh;
        }}
        .rotor-display {{
            display: flex;
            justify-content: center;
            gap: min(1vw, 10px);
            margin: min(1vh, 10px) 0;
            flex-wrap: wrap;
        }}
        .rotor-box {{
            background: rgba(255, 215, 0, 0.2);
            border: 2px solid #ffd700;
            border-radius: 6px;
            padding: min(0.8vh, 8px) min(1.5vw, 15px);
            font-size: min(2.2vw, 22px);
            font-weight: bold;
            color: #ffd700;
            min-width: 60px;
        }}
        .footer {{
            margin-top: min(0.5vh, 5px);
            color: #888;
            font-size: min(1.1vw, 11px);
            flex-shrink: 0;
        }}
    </style>
</head>
<body>
    <div class="kiosk-container">
        <div class="logo-section">
            <img src="/enigma.png" alt="Enigma Machine" class="logo-image" onerror="this.style.display='none'; document.querySelector('.enigma-logo').style.display='block';">
            <div class="enigma-logo" style="display: none;">ENIGMA</div>
            <div class="subtitle">Cipher Machine</div>
        </div>
        
        <div class="machine-display">
            <div class="config-label" style="margin-bottom: 10px;">Configuration</div>
            <div class="config-grid">
                <div class="config-item">
                    <div class="config-label">Model</div>
                    <div class="config-value">{mode}</div>
                </div>
                <div class="config-item">
                    <div class="config-label">Ring Settings</div>
                    <div class="config-value">{ring_settings}</div>
                </div>
                <div class="config-item">
                    <div class="config-label">Ring Position</div>
                    <div class="config-value">{ring_position}</div>
                </div>
            </div>
            <div style="margin-top: 12px;">
                <div class="config-label">Rotors</div>
                <div class="rotor-display">
"""
                # Display rotors as individual boxes
                rotor_parts = rotor_display.split()
                for rotor in rotor_parts:
                    html += f'                    <div class="rotor-box">{html_module.escape(rotor)}</div>\n'
                
                html += f"""                </div>
            </div>
        </div>
"""
                # Create layout based on whether slides are enabled
                if enable_slides:
                    # Two separate boxes side by side, each 50% width
                    html += """        <div class="message-container">
            <div class="message-section">
                <div class="message-label">Current Message</div>
                <div class="message-text">"""
                    
                    # Build message with character highlighting if delay >= 2000ms
                    if current_message and character_delay_ms >= 2000 and current_char_index > 0:
                        # Remove spaces for character counting (to match how encoding works)
                        message_no_spaces = current_message.replace(' ', '')
                        if current_char_index <= len(message_no_spaces):
                            # Find the character position in the formatted message (accounting for spaces)
                            char_count = 0
                            highlighted_message = ""
                            for char in current_message:
                                if char != ' ':
                                    char_count += 1
                                    if char_count == current_char_index:
                                        # Highlight this character in yellow
                                        highlighted_message += f'<span class="char-highlight">{html_module.escape(char)}</span>'
                                    else:
                                        highlighted_message += html_module.escape(char)
                                else:
                                    highlighted_message += html_module.escape(char)
                            html += highlighted_message
                        else:
                            html += html_module.escape(current_message)
                    else:
                        html += html_module.escape(current_message) if current_message else 'Waiting for message...'
                    
                    html += """</div>
"""
                    # Display result message (encoded or decoded) with appropriate label
                    result_label = "Encoded" if is_encode_mode else "Decoded"
                    if result_message:
                        html += f'                <div class="message-label">{result_label} Message</div>\n'
                        html += f'                <div class="encoded-text">{html_module.escape(result_message)}</div>\n'
                    
                    html += """            </div>
            <div class="slide-section">"""
                    
                    if slide_path:
                        html += f'                <img src="/{slide_path}" alt="Slide" class="slide-image" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';">'
                        html += """                <div class="slide-placeholder" style="display: none;">
                    Slide Image Placeholder
                </div>"""
                    else:
                        html += """                <div class="slide-placeholder">
                    Slide Image Placeholder
                </div>"""
                    
                    html += """            </div>
        </div>
"""
                else:
                    # Single box (original layout)
                    html += """        <div class="message-section">
            <div class="message-label">Current Message</div>
            <div class="message-text">"""
                    
                    # Build message with character highlighting if delay >= 2000ms
                    if current_message and character_delay_ms >= 2000 and current_char_index > 0:
                        # Remove spaces for character counting (to match how encoding works)
                        message_no_spaces = current_message.replace(' ', '')
                        if current_char_index <= len(message_no_spaces):
                            # Find the character position in the formatted message (accounting for spaces)
                            char_count = 0
                            highlighted_message = ""
                            for char in current_message:
                                if char != ' ':
                                    char_count += 1
                                    if char_count == current_char_index:
                                        # Highlight this character in yellow
                                        highlighted_message += f'<span class="char-highlight">{html_module.escape(char)}</span>'
                                    else:
                                        highlighted_message += html_module.escape(char)
                                else:
                                    highlighted_message += html_module.escape(char)
                            html += highlighted_message
                        else:
                            html += html_module.escape(current_message)
                    else:
                        html += html_module.escape(current_message) if current_message else 'Waiting for message...'
                    
                    html += """</div>
"""
                    # Display result message (encoded or decoded) with appropriate label
                    result_label = "Encoded" if is_encode_mode else "Decoded"
                    if result_message:
                        html += f'            <div class="message-label">{result_label} Message</div>\n'
                        html += f'            <div class="encoded-text">{html_module.escape(result_message)}</div>\n'
                    
                    html += """        </div>
"""
                
                html += f"""        
        <div class="footer">
            <p>Museum Display {VERSION} - Auto-refreshes every 2 seconds</p>
            <p>by Andrew Baker (DotelPenguin)</p>
        </div>
    </div>
</body>
</html>"""
                return html
            
            def log_message(self, format, *args):
                """Suppress server log messages"""
                pass
        
        try:
            self.server = HTTPServer(('', self.port), MuseumHandler)
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            # Return IP address for display
            return self.get_local_ip()
        except Exception as e:
            print(f"Failed to start web server on port {self.port}: {e}")
            return None
    
    def _run_server(self):
        """Run the HTTP server"""
        try:
            self.server.serve_forever()
        except Exception:
            pass
    
    def stop(self):
        """Stop the web server"""
        self.running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass


class EnigmaMuseumUI:
    """Curses-based UI for Enigma Museum Controller"""
    
    def __init__(self, controller: EnigmaController):
        self.controller = controller
        self.stdscr = None
        self.top_win = None  # Top window for settings display
        self.left_win = None  # Bottom left panel window (menus)
        self.right_win = None  # Bottom right panel window (debug/logo)
        self.debug_enabled = False
        self.debug_output = []  # Store debug messages as tuples: (message, color_type)
        self.max_debug_lines = 100  # Limit debug history
        self.top_height = 6  # Height of top settings window
        # Color pair IDs
        self.COLOR_SENT = 1      # Dark green for data sent to Enigma
        self.COLOR_RECEIVED = 2  # Bright green for data received from Enigma
        self.COLOR_INFO = 3      # Yellow for other info
        self.COLOR_DELAY = 5     # Light purple for character delay messages
        self.COLOR_MATCH = 6     # Bright green for matching characters
        self.COLOR_MISMATCH = 7  # Red for mismatching characters
        self.COLOR_WEB_RUNNING = 2  # Green for enabled and running web server
        self.COLOR_WEB_ENABLED_NOT_RUNNING = 3  # Yellow for enabled but not running web server
        self.COLOR_WEB_DISABLED = 4  # Grey for disabled web server
        
    def create_subwindows(self):
        """Create subwindows: top (settings), bottom left (menus), bottom right (debug/logo)"""
        if not self.stdscr:
            return
        
        # Check minimum terminal size
        min_cols = 100
        min_lines = 25
        if curses.COLS < min_cols or curses.LINES < min_lines:
            # Terminal too small - use fallback layout
            try:
                self.top_win = None
                self.left_win = self.stdscr.subwin(curses.LINES - 2, curses.COLS - 2, 1, 1)
                self.right_win = None
            except:
                self.top_win = None
                self.left_win = None
                self.right_win = None
            return
        
        # Destroy existing windows if any
        self.destroy_subwindows()
        
        try:
            # Top window: full width, shows settings
            # Position: (1, 1) with height top_height, width COLS-2
            top_y = 1
            top_x = 1
            top_width = curses.COLS - 2
            self.top_win = self.stdscr.subwin(self.top_height, top_width, top_y, top_x)
            
            # Bottom windows: 50/50 split
            # Bottom starts after top window + divider
            bottom_y = top_y + self.top_height + 1  # +1 for divider line
            bottom_height = curses.LINES - bottom_y - 1  # -1 for bottom border
            left_width = (curses.COLS - 3) // 2  # -3 for borders and divider
            right_width = curses.COLS - left_width - 3  # Remaining width
            
            # Left window: bottom left (menus)
            self.left_win = self.stdscr.subwin(bottom_height, left_width, bottom_y, top_x)
            
            # Right window: bottom right (debug/logo)
            right_x = top_x + left_width + 1  # +1 for divider
            self.right_win = self.stdscr.subwin(bottom_height, right_width, bottom_y, right_x)
        except:
            self.top_win = None
            self.left_win = None
            self.right_win = None
    
    def destroy_subwindows(self):
        """Destroy subwindows"""
        if self.top_win:
            try:
                del self.top_win
            except:
                pass
            self.top_win = None
        if self.left_win:
            try:
                del self.left_win
            except:
                pass
            self.left_win = None
        if self.right_win:
            try:
                del self.right_win
            except:
                pass
            self.right_win = None
    
    def get_active_window(self):
        """Get the active window for drawing (left panel)"""
        return self.left_win if self.left_win else self.stdscr
    
    def refresh_all_panels(self):
        """Refresh all windows"""
        if self.top_win:
            self.top_win.refresh()
        if self.left_win:
            self.left_win.refresh()
        if self.right_win:
            self.right_win.refresh()
        self.stdscr.refresh()
    
    def setup_screen(self):
        """Clear screen, draw border, dividers, and create subwindows"""
        self.stdscr.clear()
        self.stdscr.border()
        self.create_subwindows()
        
        # Draw horizontal divider below top window
        if self.top_win:
            divider_y = 1 + self.top_height
            for x in range(1, curses.COLS - 1):
                try:
                    self.stdscr.addch(divider_y, x, '═')  # ANSI double horizontal line
                except:
                    pass
        
        # Draw vertical divider between left and right bottom windows
        if self.left_win and self.right_win:
            divider_x = curses.COLS // 2
            bottom_start = 1 + self.top_height + 1
            for y in range(bottom_start, curses.LINES - 1):
                try:
                    self.stdscr.addch(y, divider_x, '║')  # ANSI double vertical line
                except:
                    pass
        
        # Clear all windows
        if self.top_win:
            self.top_win.clear()
        if self.left_win:
            self.left_win.clear()
        if self.right_win:
            self.right_win.clear()
    
    def get_left_width(self) -> int:
        """Get width of left panel"""
        if self.left_win:
            return self.left_win.getmaxyx()[1]
        return curses.COLS - 2  # Account for border
    
    def get_local_ip(self) -> str:
        """Get the local IP address"""
        try:
            # Connect to a remote address to determine local IP
            # This doesn't actually send data, just determines the route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            # Fallback to localhost
            return "127.0.0.1"
    
    def draw_settings_panel(self):
        """Display Enigma settings in the top window"""
        if not self.top_win:
            return
        
        try:
            self.top_win.clear()
            max_y, max_x = self.top_win.getmaxyx()
            
            # Title with version at the top
            title = f"Enigma Museum Controller  {VERSION}"
            title_x = (max_x - len(title)) // 2
            if title_x >= 0:
                try:
                    self.top_win.addstr(0, max(0, title_x), title, curses.A_BOLD)
                except:
                    pass
            
            # Get current settings
            config = self.controller.config
            
            # Format settings nicely
            web_port = self.controller.web_server_port
            # Get IP address (use stored IP if available, otherwise get local IP)
            if self.controller.web_server_ip:
                web_ip = self.controller.web_server_ip
            else:
                web_ip = self.get_local_ip()
            web_url = f"http://{web_ip}:{web_port}"
            web_enabled = self.controller.web_server_enabled
            
            char_delay = f"{self.controller.character_delay_ms}ms" if self.controller.character_delay_ms > 0 else "0ms"
            # Format last character info
            last_char_info = ""
            if self.controller.last_char_sent:
                if self.controller.last_char_received:
                    last_char_info = f"Last: {self.controller.last_char_sent}→{self.controller.last_char_received}"
                else:
                    last_char_info = f"Last sent: {self.controller.last_char_sent}"
            elif self.controller.last_char_received:
                # Unexpected input (received without sending)
                last_char_info = f"Last received: {self.controller.last_char_original}→{self.controller.last_char_received}"
            else:
                last_char_info = "Last: --"
            
            # Build settings lines - split web server line to allow color coding
            settings_lines = [
                f"Mode: {config.get('mode', 'N/A'):<8}  Rotors: {config.get('rotor_set', 'N/A'):<20}  Ring Settings: {config.get('ring_settings', 'N/A'):<12}",
                f"Ring Position: {config.get('ring_position', 'N/A'):<15}  Pegboard: {config.get('pegboard', 'clear'):<20}  Function Mode: {self.controller.function_mode:<15}",
            ]
            
            # Center vertically and display (starting from line 1 to leave room for title)
            start_y = 1 + ((max_y - 1 - (len(settings_lines) + 1)) // 2)  # +1 for web server line
            for i, line in enumerate(settings_lines):
                y = start_y + i
                if y >= max_y:
                    break
                # Truncate to fit
                display_line = line[:max_x]
                # Center horizontally
                x = (max_x - len(display_line)) // 2
                if x >= 0:
                    self.top_win.addstr(y, max(0, x), display_line, curses.A_BOLD)
            
            # Draw web server line with color coding
            web_line_y = start_y + len(settings_lines)
            if web_line_y < max_y:
                # Build the line parts
                web_prefix = f"Char Delay: {char_delay:<15}  Web Server: "
                web_suffix = f"  {last_char_info}"
                web_line_full = f"{web_prefix}{web_url}{web_suffix}"
                
                # Initialize web_url_display (will be used for truncation if needed)
                web_url_display = web_url
                
                # Truncate if needed
                if len(web_line_full) > max_x:
                    # Try to fit the URL, truncate suffix if needed
                    available_for_url = max_x - len(web_prefix) - len(web_suffix)
                    if available_for_url < len(web_url):
                        # Truncate URL
                        web_url_display = web_url[:max(0, available_for_url)]
                    web_line_full = f"{web_prefix}{web_url_display}{web_suffix}"[:max_x]
                
                # Center horizontally
                x = (max_x - len(web_line_full)) // 2
                if x >= 0:
                    # Write prefix in normal bold
                    self.top_win.addstr(web_line_y, max(0, x), web_prefix, curses.A_BOLD)
                    prefix_end = x + len(web_prefix)
                    
                    # Write URL in color based on web server state
                    if not web_enabled:
                        # Disabled -> grey (dim)
                        url_color = self.COLOR_WEB_DISABLED
                        if curses.has_colors():
                            url_attr = curses.color_pair(url_color) | curses.A_DIM
                        else:
                            url_attr = curses.A_DIM
                    elif self.controller.web_server_ip:
                        # Enabled and running -> green
                        url_color = self.COLOR_WEB_RUNNING
                        if curses.has_colors():
                            url_attr = curses.color_pair(url_color) | curses.A_BOLD
                        else:
                            url_attr = curses.A_BOLD
                    else:
                        # Enabled but not running -> yellow
                        url_color = self.COLOR_WEB_ENABLED_NOT_RUNNING
                        if curses.has_colors():
                            url_attr = curses.color_pair(url_color) | curses.A_BOLD
                        else:
                            url_attr = curses.A_BOLD
                    
                    # Use web_url_display (which may be truncated)
                    self.top_win.addstr(web_line_y, prefix_end, web_url_display, url_attr)
                    url_end = prefix_end + len(web_url_display)
                    
                    # Write suffix in normal bold
                    suffix_start = url_end
                    suffix_text = web_suffix
                    if suffix_start + len(suffix_text) > max_x:
                        suffix_text = suffix_text[:max(0, max_x - suffix_start)]
                    if suffix_text:
                        self.top_win.addstr(web_line_y, suffix_start, suffix_text, curses.A_BOLD)
            
            self.top_win.refresh()
        except:
            pass
    
    def get_enigma_logo(self):
        """Get ANSI Enigma logo - all lines must be same length"""
        # All lines are exactly 24 characters
        logo = [
            "╔══════════════════════╗",      # 24 chars
            "║   ENIGMA MACHINE     ║",      # 24 chars (added space)
            "║                      ║",      # 24 chars
            "║  ╔═══╗ ╔═══╗ ╔═══╗   ║",     # 24 chars (added space)
            "║  ║ I ║ ║II ║ ║III║   ║",     # 24 chars (added space)
            "║  ╚═══╝ ╚═══╝ ╚═══╝   ║",     # 24 chars (added space)
            "║                      ║",      # 24 chars
            "╚══════════════════════╝",      # 24 chars
        ]
        return logo
    
    def draw_logo_panel(self):
        """Display ANSI Enigma logo in right panel when debug is disabled"""
        if not self.right_win:
            return
        
        try:
            self.right_win.clear()
            max_y, max_x = self.right_win.getmaxyx()
            
            logo = self.get_enigma_logo()
            
            # Find the maximum width of logo lines
            max_logo_width = max(len(line) for line in logo) if logo else 0
            
            # Only draw if we have enough space
            if max_logo_width > max_x or len(logo) > max_y:
                # Logo too big, draw a simple message instead
                msg = "ENIGMA MACHINE"
                y = max_y // 2
                x = (max_x - len(msg)) // 2
                if x >= 0:
                    self.right_win.addstr(y, x, msg, curses.A_BOLD)
            else:
                # Center logo vertically
                start_y = (max_y - len(logo)) // 2
                
                for i, line in enumerate(logo):
                    y = start_y + i
                    if y >= max_y:
                        break
                    # Center horizontally - use actual line length, not truncated
                    x = (max_x - len(line)) // 2
                    if x >= 0 and x + len(line) <= max_x:
                        try:
                            self.right_win.addstr(y, x, line, curses.A_BOLD)
                        except:
                            pass
            
            self.right_win.refresh()
        except:
            pass
    
    def add_debug_output(self, message: str, color_type: Optional[int] = None):
        """Add a message to debug output with color coding
        
        Args:
            message: The debug message to add
            color_type: Optional color type to use. If None, will be determined from message content.
        """
        if not self.debug_enabled:
            return
        # Split multi-line messages into separate lines
        lines = message.split('\n')
        for line in lines:
            # Remove carriage returns and strip whitespace
            line = line.replace('\r', '').strip()
            if line:  # Only add non-empty lines
                # Use provided color_type, or determine from message content
                if color_type is None:
                    if line.startswith('>>>'):
                        # Data sent to Enigma - dark green
                        color_type = self.COLOR_SENT
                    elif line.startswith('<<<'):
                        # Data received from Enigma - bright green
                        color_type = self.COLOR_RECEIVED
                    elif 'Character delay' in line or 'Skipping delay' in line:
                        # Character delay messages - light purple
                        color_type = self.COLOR_DELAY
                    elif 'MATCH' in line:
                        # Matching characters - bright green
                        color_type = self.COLOR_MATCH
                    elif 'MISMATCH' in line:
                        # Mismatching characters - red
                        color_type = self.COLOR_MISMATCH
                    else:
                        # Other info - yellow
                        color_type = self.COLOR_INFO
                # Store as tuple: (message, color_type)
                self.debug_output.append((line, color_type))
        # Keep only last max_debug_lines
        if len(self.debug_output) > self.max_debug_lines:
            self.debug_output = self.debug_output[-self.max_debug_lines:]
    
    
    def draw_debug_panel(self):
        """Draw debug output or logo in the right panel"""
        if not self.right_win:
            return
        
        if self.debug_enabled:
            # Show debug output
            try:
                self.right_win.clear()
                max_y, max_x = self.right_win.getmaxyx()
                
                # Draw debug header
                header = " DEBUG OUTPUT "
                header_x = (max_x - len(header)) // 2
                if header_x >= 0 and header_x + len(header) <= max_x:
                    self.right_win.addstr(0, header_x, header, curses.A_BOLD | curses.A_REVERSE)
                
                # Draw debug messages (scrollable)
                start_line = 1
                available_lines = max_y - start_line
                
                # Show most recent messages
                debug_lines_to_show = self.debug_output[-available_lines:] if len(self.debug_output) > available_lines else self.debug_output
                
                for i, debug_item in enumerate(debug_lines_to_show):
                    y = start_line + i
                    if y >= max_y:
                        break
                    try:
                        # Extract message and color type from tuple
                        if isinstance(debug_item, tuple):
                            line, color_type = debug_item
                        else:
                            # Backward compatibility: if it's just a string, use default color
                            line = debug_item
                            color_type = self.COLOR_INFO
                        
                        # Remove any control characters and truncate to fit window width
                        # Replace any remaining newlines/carriage returns with spaces
                        display_line = line.replace('\r', '').replace('\n', ' ').strip()
                        # Remove the >>> and <<< prefixes from display
                        if display_line.startswith('>>> '):
                            display_line = display_line[4:]  # Remove ">>> "
                        elif display_line.startswith('<<< '):
                            display_line = display_line[4:]  # Remove "<<< "
                        display_line = display_line[:max_x]
                        # Clear the line first to avoid overlap
                        self.right_win.addstr(y, 0, ' ' * max_x)  # Clear line
                        # Apply color based on message type (if colors are supported)
                        if curses.has_colors():
                            color_attr = curses.color_pair(color_type)
                            # Add bold for received messages (bright green) and matching characters
                            if color_type == self.COLOR_RECEIVED or color_type == self.COLOR_MATCH:
                                color_attr |= curses.A_BOLD
                            self.right_win.addstr(y, 0, display_line, color_attr)
                        else:
                            # No color support - just display normally
                            self.right_win.addstr(y, 0, display_line)
                    except:
                        pass
                
                self.right_win.refresh()
            except:
                pass
        else:
            # Show logo when debug is disabled
            self.draw_logo_panel()
        
    def show_message(self, y: int, x: int, text: str, attr=curses.A_NORMAL):
        """Display message at position (left panel when debug enabled)"""
        try:
            win = self.get_active_window()
            if not win:
                return
            max_y, max_x = win.getmaxyx()
            if y >= max_y or x >= max_x:
                return
            max_width = max_x - x
            if max_width <= 0:
                return
            win.addstr(y, x, text[:max_width], attr)
        except:
            pass
    
    def get_input(self, y: int, x: int, prompt: str, default: str = '') -> str:
        """Get text input from user"""
        self.show_message(y, x, prompt)
        win = self.get_active_window()
        if not win:
            return default
        
        curses.echo()
        curses.curs_set(1)
        try:
            win.move(y, x + len(prompt))
            value = win.getstr(y, x + len(prompt), 50).decode('utf-8')
            if not value and default:
                return default
            return value
        except:
            return default
        finally:
            curses.noecho()
            curses.curs_set(0)
    
    def show_menu(self, title: str, options: List[Tuple[str, str]], selected: int = 0) -> int:
        """Display menu and return selected index"""
        self.setup_screen()
        
        # Draw settings in top panel
        self.draw_settings_panel()
        
        # Title in left window
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            title_y = 0
            title_x = (max_x - len(title)) // 2
            try:
                win.addstr(title_y, title_x, title, curses.A_BOLD | curses.A_UNDERLINE)
            except:
                pass
        
        # Options in left window
        start_y = 2
        for i, (key, desc) in enumerate(options):
            y = start_y + i
            attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
            self.show_message(y, 0, f"{key}) {desc}", attr)
        
        # Instructions - dynamic based on available options
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            try:
                # Check if Q is in options
                has_q = any(opt[0].upper() == 'Q' for opt in options)
                has_b = any(opt[0].upper() == 'B' for opt in options)
                
                if has_q:
                    instruction = "Use UP/DOWN arrows, ENTER to select, Q to quit"
                elif has_b:
                    instruction = "Use UP/DOWN arrows, ENTER to select, Q or B to go back"
                else:
                    instruction = "Use UP/DOWN arrows, ENTER to select"
                
                win.addstr(max_y - 1, 0, instruction)
            except:
                pass
        
        # Draw debug panel or logo in right window
        self.draw_debug_panel()
        
        # Refresh all windows
        if self.top_win:
            self.top_win.refresh()
        if self.left_win:
            self.left_win.refresh()
        if self.right_win:
            self.right_win.refresh()
        self.stdscr.refresh()
        return selected
    
    def main_menu(self) -> str:
        """Display main menu"""
        options = [
            ("1", "Send Message"),
            ("2", "Configuration"),
            ("3", "Query All Settings"),
            ("4", "Museum Mode"),
            ("5", "Set All Settings"),
            ("6", f"Debug: {'ON' if self.debug_enabled else 'OFF'}"),
            ("Q", "Quit")
        ]
        
        selected = 0
        while True:
            # Update debug status in options
            options[5] = ("6", f"Debug: {'ON' if self.debug_enabled else 'OFF'}")
            self.show_menu("Enigma Museum Controller", options, selected)
            key = self.stdscr.getch()
            
            if key == ord('q') or key == ord('Q'):
                return 'quit'
            elif key == ord('6'):
                # Toggle debug
                self.debug_enabled = not self.debug_enabled
                if not self.debug_enabled:
                    self.debug_output = []  # Clear debug output when disabled
                self.create_subwindows()  # Recreate subwindows
                self.add_debug_output(f"Debug {'enabled' if self.debug_enabled else 'disabled'}")
                continue
            elif key == curses.KEY_UP:
                selected = (selected - 1) % len(options)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(options)
            elif key == ord('\n') or key == ord('\r'):
                if options[selected][0] == 'Q':
                    return 'quit'
                elif options[selected][0] == '6':
                    # Toggle debug
                    self.debug_enabled = not self.debug_enabled
                    if not self.debug_enabled:
                        self.debug_output = []  # Clear debug output when disabled
                    self.create_subwindows()  # Recreate subwindows
                    self.add_debug_output(f"Debug {'enabled' if self.debug_enabled else 'disabled'}")
                    continue
                return options[selected][0]
            elif key >= ord('1') and key <= ord('5'):
                return chr(key)
    
    def config_menu(self, exit_after: bool = False):
        """Configuration submenu
        
        Args:
            exit_after: If True, exit the application after leaving the menu
        """
        def get_options():
            """Get menu options using saved config values"""
            saved = self.controller.get_saved_config()
            return [
                ("1", f"Set Mode (current: {saved['config']['mode']})"),
                ("2", f"Set Rotor Set (current: {saved['config']['rotor_set']})"),
                ("3", f"Set Ring Settings (current: {saved['config']['ring_settings']})"),
                ("4", f"Set Ring Position (current: {saved['config']['ring_position']})"),
                ("5", f"Set Pegboard (current: {saved['config']['pegboard']})"),
                ("6", f"Set Museum Delay (current: {saved['museum_delay']}s)"),
                ("7", f"Always Send Config Before Message: {'ON' if saved['always_send_config'] else 'OFF'}"),
                ("8", f"Set Word Group Size (current: {saved['word_group_size']})"),
                ("9", f"Set Character Delay (current: {saved.get('character_delay_ms', 0)}ms)"),
                ("10", "Generate Coded Messages - EN"),
                ("11", "Generate Coded Messages - DE"),
                ("12", f"Set Device (current: {saved['device']})"),
                ("13", f"Set Web Server Port (current: {saved.get('web_server_port', 8080)})"),
                ("14", f"Web Server: {'ENABLED' if saved.get('web_server_enabled', False) else 'DISABLED'}"),
                ("15", f"Enable Slides: {'ON' if saved.get('enable_slides', False) else 'OFF'}"),
            ("B", "Back")
        ]
        
        options = get_options()
        selected = 0
        while True:
            self.show_menu("Configuration", options, selected)
            key = self.stdscr.getch()
            
            if key == ord('b') or key == ord('B'):
                if exit_after:
                    return 'exit'
                return
            elif key == ord('q') or key == ord('Q'):
                if exit_after:
                    return 'exit'
                return
            elif key == curses.KEY_UP:
                selected = (selected - 1) % len(options)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(options)
            elif key == ord('\n') or key == ord('\r'):
                if options[selected][0] == 'B':
                    if exit_after:
                        return 'exit'
                    return
                self.handle_config_option(options[selected][0])
                # Refresh menu to show updated values from saved config
                options = get_options()
            elif key >= ord('1') and key <= ord('9'):
                self.handle_config_option(chr(key))
                # Refresh menu to show updated values from saved config
                options = get_options()
            elif key == ord('0'):
                # Handle option 10 (0 key)
                self.handle_config_option('10')
                # Refresh menu to show updated values from saved config
                options = get_options()
            # Note: Options 11, 12, and 13 are handled via menu selection (ENTER key) since they require multiple digits
    
    def handle_config_option(self, option: str):
        """Handle configuration option selection"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Get saved config values from file (not in-memory values)
        saved = self.controller.get_saved_config()
        
        def debug_callback(msg):
            self.add_debug_output(msg)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        if option == '1':
            self.show_message(0, 0, "Set Mode (e.g., I, M3, M4):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Mode: ", saved['config']['mode'])
            if value:
                if self.controller.set_mode(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Mode set successfully!")
                    self.draw_settings_panel()  # Update settings display
                else:
                    self.show_message(2, 0, "Failed to set mode!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '2':
            self.show_message(0, 0, "Set Rotor Set (e.g., A III IV I):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Rotor Set: ", saved['config']['rotor_set'])
            if value:
                if self.controller.set_rotor_set(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Rotor set configured successfully!")
                    self.draw_settings_panel()  # Update settings display
                else:
                    self.show_message(2, 0, "Failed to configure rotor set!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '3':
            self.show_message(0, 0, "Set Ring Settings (e.g., 01 01 01):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Ring Settings: ", saved['config']['ring_settings'])
            if value:
                if self.controller.set_ring_settings(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Ring settings configured successfully!")
                    self.draw_settings_panel()  # Update settings display
                else:
                    self.show_message(2, 0, "Failed to configure ring settings!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '4':
            self.show_message(0, 0, "Set Ring Position (e.g., 20 6 10 or A B C):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Ring Position: ", saved['config']['ring_position'])
            if value:
                if self.controller.set_ring_position(value, debug_callback=debug_callback):
                    # Save config with new ring position (don't preserve old value)
                    self.controller.save_config(preserve_ring_position=False)
                    self.show_message(2, 0, "Ring position set successfully!")
                    self.draw_settings_panel()  # Update settings display
                else:
                    self.show_message(2, 0, "Failed to set ring position!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '5':
            self.show_message(0, 0, "Set Pegboard (e.g., VF PQ or leave empty for clear):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Pegboard: ", saved['config']['pegboard'])
            if value:
                if self.controller.set_pegboard(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Pegboard configured successfully!")
                    self.draw_settings_panel()  # Update settings display
                else:
                    self.show_message(2, 0, "Failed to configure pegboard!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '6':
            self.show_message(0, 0, f"Set Museum Delay (current: {saved['museum_delay']}s):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Delay (seconds): ", str(saved['museum_delay']))
            try:
                self.controller.museum_delay = int(value)
                self.controller.save_config()  # Save config after change
                self.show_message(2, 0, f"Museum delay set to {self.controller.museum_delay}s")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            except:
                self.show_message(2, 0, "Invalid delay value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '7':
            # Toggle always_send_config - use saved value
            self.controller.always_send_config = not saved['always_send_config']
            self.controller.save_config()  # Save config after change
            status = "ON" if self.controller.always_send_config else "OFF"
            self.show_message(0, 0, f"Always Send Config Before Message: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '8':
            # Set word group size
            self.show_message(0, 0, "Enter word group size (4 or 5):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            curses.echo()
            curses.curs_set(1)
            try:
                group_size_str = self.get_input(1, 0, "Group size: ", str(saved['word_group_size']))
                group_size = int(group_size_str.strip())
                if group_size == 4 or group_size == 5:
                    self.controller.word_group_size = group_size
                    self.controller.save_config()  # Save config after change
                    self.show_message(0, 0, f"Word group size set to {group_size}")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
                else:
                    self.show_message(2, 0, "Invalid! Must be 4 or 5")
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
            except:
                self.show_message(2, 0, "Invalid group size value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            finally:
                curses.noecho()
                curses.curs_set(0)
        
        elif option == '9':
            # Set character delay
            self.show_message(0, 0, f"Set Character Delay (current: {saved.get('character_delay_ms', 0)}ms):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            curses.echo()
            curses.curs_set(1)
            try:
                delay_str = self.get_input(1, 0, "Delay (ms): ", str(saved.get('character_delay_ms', 0)))
                delay_ms = int(delay_str.strip())
                if delay_ms < 0:
                    self.show_message(2, 0, "Invalid! Must be >= 0")
                else:
                    self.controller.character_delay_ms = delay_ms
                    self.controller.save_config()  # Save config after change
                    self.show_message(0, 0, f"Character delay set to {delay_ms}ms")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
            except ValueError:
                self.show_message(2, 0, "Invalid delay value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            finally:
                curses.noecho()
                curses.curs_set(0)
        
        elif option == '10':
            # Generate coded messages - English
            self.generate_coded_messages('EN')
        
        elif option == '11':
            # Generate coded messages - German
            self.generate_coded_messages('DE')
        
        elif option == '12':
            # Set device
            self.show_message(0, 0, "Set Device (e.g., /dev/ttyACM0):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            saved = self.controller.get_saved_config()
            value = self.get_input(1, 0, "Device: ", saved['device'])
            if value:
                self.controller.device = value
                self.controller.save_config()  # Save config after change
                self.show_message(2, 0, f"Device set to {value}")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '13':
            # Set web server port
            self.show_message(0, 0, f"Set Web Server Port (current: {saved.get('web_server_port', 8080)}):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Port: ", str(saved.get('web_server_port', 8080)))
            try:
                port = int(value)
                if port < 1 or port > 65535:
                    self.show_message(2, 0, "Invalid port! Must be 1-65535")
                else:
                    self.controller.web_server_port = port
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, f"Web server port set to {port}")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            except:
                self.show_message(2, 0, "Invalid port value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '14':
            # Toggle web server enable/disable
            current_enabled = saved.get('web_server_enabled', False)
            if current_enabled:
                # Currently enabled - disable it
                self.controller.web_server_enabled = False
                self.controller.web_server_ip = None  # Clear IP
                self.controller.save_config()
                self.show_message(0, 0, "Web server DISABLED", curses.A_BOLD)
                self.draw_settings_panel()  # Update settings display
            else:
                # Currently disabled - enable it
                self.controller.web_server_enabled = True
                self.controller.save_config()
                port = self.controller.web_server_port
                self.show_message(0, 0, f"Web server ENABLED on port {port}", curses.A_BOLD)
                self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '15':
            # Toggle enable_slides
            current_enabled = saved.get('enable_slides', False)
            self.controller.enable_slides = not current_enabled
            self.controller.save_config()  # Save config after change
            status = "ON" if self.controller.enable_slides else "OFF"
            self.show_message(0, 0, f"Enable Slides: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
    
    def generate_coded_messages(self, language: str):
        """Generate coded messages from english.msg or german.msg"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Determine file paths
        if language == 'EN':
            input_file = ENGLISH_MSG_FILE
            output_file = os.path.join(SCRIPT_DIR, 'english-encoded.json')
        else:
            input_file = GERMAN_MSG_FILE
            output_file = os.path.join(SCRIPT_DIR, 'german-encoded.json')
        
        # Load messages from file
        messages = load_messages_from_file(input_file)
        
        if not messages:
            self.show_message(0, 0, f"Error: Could not load messages from {os.path.basename(input_file)}", curses.A_BOLD)
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            return
        
        message_count = len(messages)
        
        # Show confirmation screen
        self.show_message(0, 0, f"Generate Coded Messages - {language}", curses.A_BOLD)
        self.show_message(1, 0, f"Found {message_count} messages in {os.path.basename(input_file)}")
        self.show_message(2, 0, f"Output will be saved to {os.path.basename(output_file)}")
        self.show_message(3, 0, "")
        self.show_message(4, 0, "WARNING: This process can take a long time!", curses.A_BOLD | curses.A_BLINK)
        self.show_message(5, 0, "")
        self.show_message(6, 0, "Press Y to continue, any other key to cancel")
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        # Get confirmation
        key = self.stdscr.getch()
        if key != ord('y') and key != ord('Y'):
            return
        
        # Check if output file exists
        file_exists = os.path.exists(output_file)
        coded_messages = []
        start_index = 0
        existing_settings = None
        
        if file_exists:
            # Load existing JSON file
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    coded_messages = json.load(f)
                if not isinstance(coded_messages, list):
                    coded_messages = []
                
                # Extract settings from first message if exists
                if coded_messages and isinstance(coded_messages[0], dict):
                    existing_settings = {
                        'MODEL': coded_messages[0].get('MODEL'),
                        'ROTOR': coded_messages[0].get('ROTOR'),
                        'RINGSET': coded_messages[0].get('RINGSET'),
                        'RINGPOS': coded_messages[0].get('RINGPOS'),
                        'PLUG': coded_messages[0].get('PLUG'),
                        'GROUP': coded_messages[0].get('GROUP')
                    }
                
                start_index = len(coded_messages)
            except (json.JSONDecodeError, IOError) as e:
                # File exists but is invalid - treat as empty
                coded_messages = []
                start_index = 0
        
        # Get saved config values for comparison
        saved = self.controller.get_saved_config()
        saved_config_values = saved['config']
        current_settings = {
            'MODEL': saved_config_values['mode'],
            'ROTOR': saved_config_values['rotor_set'],
            'RINGSET': saved_config_values['ring_settings'],
            'RINGPOS': saved_config_values['ring_position'],
            'PLUG': saved_config_values['pegboard'],
            'GROUP': saved['word_group_size']
        }
        
        # Compare settings if existing file found
        settings_changed = False
        if file_exists and existing_settings:
            settings_changed = (
                existing_settings.get('MODEL') != current_settings['MODEL'] or
                existing_settings.get('ROTOR') != current_settings['ROTOR'] or
                existing_settings.get('RINGSET') != current_settings['RINGSET'] or
                existing_settings.get('RINGPOS') != current_settings['RINGPOS'] or
                existing_settings.get('PLUG') != current_settings['PLUG'] or
                existing_settings.get('GROUP') != current_settings['GROUP']
            )
        
        # Show resume/restart prompt if file exists
        if file_exists and coded_messages:
            self.setup_screen()
            self.draw_settings_panel()
            self.left_win.clear()
            max_y, max_x = self.left_win.getmaxyx()
            
            self.left_win.addstr(0, 0, f"Existing file found: {os.path.basename(output_file)}", curses.A_BOLD)
            self.left_win.addstr(1, 0, f"Found {len(coded_messages)} encoded messages")
            
            if settings_changed:
                self.left_win.addstr(2, 0, "", curses.A_BOLD)
                self.left_win.addstr(3, 0, "WARNING: Enigma settings have changed!", curses.A_BOLD | curses.A_BLINK)
                self.left_win.addstr(4, 0, "You should start over to ensure consistency.")
                self.left_win.addstr(5, 0, "")
                self.left_win.addstr(6, 0, "Current settings:")
                self.left_win.addstr(7, 0, f"  MODEL: {current_settings['MODEL']} (was: {existing_settings.get('MODEL', 'N/A')})")
                self.left_win.addstr(8, 0, f"  ROTOR: {current_settings['ROTOR']} (was: {existing_settings.get('ROTOR', 'N/A')})")
                self.left_win.addstr(9, 0, f"  RINGSET: {current_settings['RINGSET']} (was: {existing_settings.get('RINGSET', 'N/A')})")
                self.left_win.addstr(10, 0, f"  RINGPOS: {current_settings['RINGPOS']} (was: {existing_settings.get('RINGPOS', 'N/A')})")
                self.left_win.addstr(11, 0, f"  PLUG: {current_settings['PLUG']} (was: {existing_settings.get('PLUG', 'N/A')})")
                self.left_win.addstr(12, 0, f"  GROUP: {current_settings['GROUP']} (was: {existing_settings.get('GROUP', 'N/A')})")
            else:
                self.left_win.addstr(2, 0, "Settings match existing file.")
            
            self.left_win.addstr(13, 0, "")
            self.left_win.addstr(14, 0, "Resume from existing file? (Y/N)")
            self.left_win.addstr(15, 0, "If Enigma settings have changed, you should start over.")
            self.left_win.refresh()
            self.draw_debug_panel()
            self.refresh_all_panels()
            
            # Get user choice
            key = self.stdscr.getch()
            if key == ord('y') or key == ord('Y'):
                # Resume - keep existing coded_messages and start_index
                pass
            else:
                # Start over - clear existing file
                coded_messages = []
                start_index = 0
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump([], f, indent=2, ensure_ascii=False)
                except Exception as e:
                    self.show_message(0, 0, f"Error clearing output file: {str(e)}", curses.A_BOLD)
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)
                    return
        elif not file_exists:
            # Create empty file on first run
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.show_message(0, 0, f"Error creating output file: {str(e)}", curses.A_BOLD)
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(2)
                return
        
        # Setup screen for progress display
        self.setup_screen()
        self.draw_settings_panel()
        
        def debug_callback(msg):
            self.add_debug_output(msg)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        def position_update_callback():
            """Update settings panel when ring positions change"""
            self.draw_settings_panel()
            self.refresh_all_panels()
        
        # Set flag to skip delays during message generation
        self.controller.generating_messages = True
        if debug_callback:
            debug_callback(f"Message generation mode: delays will be skipped")
        
        # Process each message
        
        for i in range(start_index, message_count):
            message = messages[i]
            
            # Update progress display
            self.left_win.clear()
            max_y, max_x = self.left_win.getmaxyx()
            self.left_win.addstr(0, 0, f"Generating Coded Messages - {language}", curses.A_BOLD)
            self.left_win.addstr(1, 0, f"Progress: {i+1}/{message_count}")
            self.left_win.addstr(2, 0, f"Processing message {i+1}: {message[:max_x-20] if len(message) > max_x-20 else message}")
            self.left_win.addstr(3, 0, "-" * max_x)
            
            # Show already encoded messages
            if coded_messages:
                self.left_win.addstr(4, 0, "Encoded so far:")
                display_y = 5
                for idx, coded in enumerate(coded_messages[-5:], start=max(0, len(coded_messages)-5)):
                    # Handle both old string format and new object format
                    if isinstance(coded, dict):
                        # New format: extract MSG field for display
                        display_text = coded.get('MSG', '[No MSG field]')
                        display_msg = f"{idx+1}: {display_text[:max_x-10]}"
                    elif isinstance(coded, str):
                        # Old format: backward compatibility
                        display_msg = f"{idx+1}: {coded[:max_x-10]}"
                    else:
                        # Invalid entry
                        display_msg = f"{idx+1}: [Invalid entry]"
                    
                    if len(display_msg) > max_x:
                        display_msg = display_msg[:max_x-3] + "..."
                    self.left_win.addstr(display_y, 0, display_msg)
                    display_y += 1
            
            self.left_win.refresh()
            self.draw_debug_panel()
            self.refresh_all_panels()
            
            # Send configuration before each message
            if debug_callback:
                debug_callback(f"Sending configuration before message {i+1}...")
            
            self.controller.set_mode(saved_config_values['mode'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.controller.set_rotor_set(saved_config_values['rotor_set'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.controller.set_ring_settings(saved_config_values['ring_settings'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.controller.set_ring_position(saved_config_values['ring_position'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.controller.set_pegboard(saved_config_values['pegboard'], debug_callback=debug_callback)
            time.sleep(0.2)
            self.controller.return_to_encode_mode(debug_callback=debug_callback)
            time.sleep(0.5)
            
            # Encode the message
            if debug_callback:
                debug_callback(f"Encoding message {i+1}: {message}")
            
            # Collect encoded characters using callback
            encoded_chars = []
            def progress_callback(index, total, original, encoded, response):
                encoded_chars.append(encoded)
                return False  # Don't cancel
            
            # generating_messages flag is already set, so delays will be skipped
            success = self.controller.send_message(message, progress_callback, debug_callback, position_update_callback)
            
            if success and encoded_chars:
                encoded_result = ''.join(encoded_chars)
                # Ensure we have a valid string before creating message object
                if encoded_result and isinstance(encoded_result, str):
                    # Create message object with all metadata
                    message_obj = {
                        'MSG': message,
                        'MODEL': current_settings['MODEL'],
                        'ROTOR': current_settings['ROTOR'],
                        'RINGSET': current_settings['RINGSET'],
                        'RINGPOS': current_settings['RINGPOS'],
                        'PLUG': current_settings['PLUG'],
                        'GROUP': current_settings['GROUP'],
                        'CODED': encoded_result
                    }
                    coded_messages.append(message_obj)
                    
                    # Save progress after each message
                    try:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(coded_messages, f, indent=2, ensure_ascii=False)
                        if debug_callback:
                            debug_callback(f"Saved {len(coded_messages)}/{message_count} encoded messages")
                    except Exception as e:
                        if debug_callback:
                            debug_callback(f"Error saving file: {str(e)}")
                else:
                    if debug_callback:
                        debug_callback(f"Warning: Invalid encoded result for message {i+1}")
            else:
                if debug_callback:
                    debug_callback(f"Warning: Failed to encode message {i+1}")
        
        # Clear generation flag
        self.controller.generating_messages = False
        if debug_callback:
            debug_callback(f"Message generation complete: delays restored")
        
        # Final summary
        self.setup_screen()
        self.draw_settings_panel()
        self.left_win.clear()
        max_y, max_x = self.left_win.getmaxyx()
        self.left_win.addstr(0, 0, "Generation Complete!", curses.A_BOLD)
        self.left_win.addstr(1, 0, f"Processed {len(coded_messages)}/{message_count} messages")
        self.left_win.addstr(2, 0, f"Output saved to: {os.path.basename(output_file)}")
        self.left_win.addstr(3, 0, "")
        self.left_win.addstr(4, 0, "Press any key to continue...")
        self.left_win.refresh()
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        self.stdscr.getch()
    
    def send_message_screen(self):
        """Screen for sending a message"""
        self.setup_screen()
        self.draw_settings_panel()
        
        self.show_message(0, 0, "Enter message to encode:")
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        curses.echo()
        curses.curs_set(1)
        win = self.get_active_window()
        if win:
            try:
                message = win.getstr(1, 0, 200).decode('utf-8')
            except:
                message = ''
        else:
            message = ''
        curses.noecho()
        curses.curs_set(0)
        
        if not message:
            return
        
        message = message.upper()
        self.setup_screen()
        self.draw_settings_panel()
        
        # Check if always_send_config is enabled (use saved config value)
        saved = self.controller.get_saved_config()
        always_send = saved.get('always_send_config', False)
        
        self.show_message(0, 0, f"Encoding: {message}")
        if always_send:
            self.show_message(1, 0, "Note: Sending saved configuration before encoding...", curses.A_BOLD | curses.A_DIM)
            self.show_message(2, 0, "Press any key to cancel")
            y = 3  # Start progress messages one line lower
        else:
            self.show_message(1, 0, "Press any key to cancel")
            y = 2  # Normal position for progress messages
        
        encoded_result = []
        
        def progress_callback(index, total, original, encoded, response):
            line = f"{index}/{total}: {original} -> {encoded}"
            self.show_message(y + index, 0, line)
            encoded_result.append(encoded)
            self.draw_debug_panel()
            self.refresh_all_panels()
            # Check for cancel
            self.stdscr.nodelay(True)
            if self.stdscr.getch() != -1:
                return True  # Cancel
            self.stdscr.nodelay(False)
            return False
        
        def debug_callback(msg):
            self.add_debug_output(msg)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        def position_update_callback():
            """Update settings panel when ring positions change"""
            self.draw_settings_panel()
            self.refresh_all_panels()
        
        self.controller.send_message(message, progress_callback, debug_callback, position_update_callback)
        
        if encoded_result:
            result = ''.join(encoded_result)
            # Group the result for display
            grouped_result = self.controller._group_encoded_text(result)
            win = self.get_active_window()
            if win:
                max_y, max_x = win.getmaxyx()
                self.show_message(y + len(encoded_result) + 1, 0, f"Encoded: {grouped_result}")
        
        self.draw_debug_panel()
        
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            self.show_message(max_y - 1, 0, "Press any key to continue...")
        
        self.refresh_all_panels()
        self.stdscr.getch()
    
    def query_settings_screen(self):
        """Display all current settings"""
        self.setup_screen()
        
        self.setup_screen()
        self.draw_settings_panel()
        
        self.show_message(0, 0, "Querying settings from device...", curses.A_BOLD)
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        def debug_callback(msg):
            self.add_debug_output(msg)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        settings = self.controller.get_all_settings(debug_callback=debug_callback)
        
        # Update controller config with queried settings
        self.controller.config.update(settings)
        
        self.setup_screen()
        self.draw_settings_panel()  # Update top panel with new settings
        
        self.show_message(0, 0, "Current Settings:", curses.A_BOLD | curses.A_UNDERLINE)
        
        y = 1
        self.show_message(y, 0, f"Mode: {settings.get('mode', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"Rotor Set: {settings.get('rotor_set', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"Ring Settings: {settings.get('ring_settings', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"Ring Position: {settings.get('ring_position', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"Pegboard: {settings.get('pegboard', 'N/A') or 'clear'}")
        
        self.draw_debug_panel()
        
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            self.show_message(max_y - 1, 0, "Press any key to continue...")
        
        self.refresh_all_panels()
        self.stdscr.getch()
    
    def set_all_settings_screen(self):
        """Set all settings from saved config file"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Reload config from file to ensure we use saved defaults, not current state
        # Preserve device to avoid changing it during operation
        self.controller.load_config(preserve_device=True)
        
        self.show_message(0, 0, "Setting all configurations from saved config...", curses.A_BOLD)
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        def debug_callback(msg):
            self.add_debug_output(msg)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Get saved config values (from file, not in-memory)
        saved = self.controller.get_saved_config()
        
        success = True
        if not self.controller.set_mode(saved['config']['mode'], debug_callback=debug_callback):
            success = False
        time.sleep(0.2)
        if not self.controller.set_rotor_set(saved['config']['rotor_set'], debug_callback=debug_callback):
            success = False
        time.sleep(0.2)
        if not self.controller.set_ring_settings(saved['config']['ring_settings'], debug_callback=debug_callback):
            success = False
        time.sleep(0.2)
        if not self.controller.set_ring_position(saved['config']['ring_position'], debug_callback=debug_callback):
            success = False
        time.sleep(0.2)
        if not self.controller.set_pegboard(saved['config']['pegboard'], debug_callback=debug_callback):
            success = False
        time.sleep(0.2)
        self.controller.return_to_encode_mode(debug_callback=debug_callback)
        
        self.setup_screen()
        self.draw_settings_panel()  # Update settings display
        
        if success:
            self.show_message(0, 0, "All settings configured successfully!", curses.A_BOLD)
        else:
            self.show_message(0, 0, "Some settings may have failed to configure.", curses.A_BOLD)
        
        self.draw_debug_panel()
        
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            self.show_message(max_y - 1, 0, "Press any key to continue...")
        
        self.refresh_all_panels()
        self.stdscr.getch()
    
    def museum_mode_screen(self):
        """Museum mode selection"""
        options = [
            ("2", "Encode - EN"),
            ("3", "Decode - EN"),
            ("4", "Encode - DE"),
            ("5", "Decode - DE"),
            ("B", "Back")
        ]
        
        selected = 0
        while True:
            self.show_menu("Museum Mode", options, selected)
            key = self.stdscr.getch()
            
            if key == ord('b') or key == ord('B'):
                return
            elif key == ord('q') or key == ord('Q'):
                return
            elif key == curses.KEY_UP:
                selected = (selected - 1) % len(options)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(options)
            elif key == ord('\n') or key == ord('\r'):
                if options[selected][0] == 'B':
                    return
                self.run_museum_mode(options[selected][0])
            elif key >= ord('2') and key <= ord('5'):
                self.run_museum_mode(chr(key))
    
    def run_museum_mode(self, mode: str):
        """Run museum mode"""
        # Determine operation mode (encode or decode)
        is_encode = mode in ('2', '4')
        
        if mode == '2':
            mode_name = 'Encode - EN'
            json_file = os.path.join(SCRIPT_DIR, 'english-encoded.json')
        elif mode == '3':
            mode_name = 'Decode - EN'
            json_file = os.path.join(SCRIPT_DIR, 'english-encoded.json')
        elif mode == '4':
            mode_name = 'Encode - DE'
            json_file = os.path.join(SCRIPT_DIR, 'german-encoded.json')
        elif mode == '5':
            mode_name = 'Decode - DE'
            json_file = os.path.join(SCRIPT_DIR, 'german-encoded.json')
        else:
            return
        
        # Set function mode first so it's displayed in the top panel
        self.controller.function_mode = mode_name
        # Save function mode to config file
        self.controller.save_config()
        
        # Load JSON file with message objects
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                message_objects = json.load(f)
            if not isinstance(message_objects, list) or len(message_objects) == 0:
                raise ValueError("Invalid or empty JSON file")
        except (IOError, json.JSONDecodeError, ValueError) as e:
            self.setup_screen()
            self.draw_settings_panel()
            self.show_message(0, 0, f"Error: Could not load messages from {os.path.basename(json_file)}", curses.A_BOLD)
            self.show_message(1, 0, "Please generate encoded messages first using the Config menu.")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(3)
            return
        
        # Validate message objects have required fields
        valid_messages = []
        for msg_obj in message_objects:
            if isinstance(msg_obj, dict) and 'MSG' in msg_obj and 'CODED' in msg_obj:
                valid_messages.append(msg_obj)
        
        if not valid_messages:
            self.setup_screen()
            self.draw_settings_panel()
            self.show_message(0, 0, f"Error: No valid messages found in {os.path.basename(json_file)}", curses.A_BOLD)
            self.show_message(1, 0, "Please generate encoded messages first using the Config menu.")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(3)
            return
        
        # Setup screen and ensure function mode is displayed
        self.setup_screen()
        # Ensure function mode is set before drawing
        self.controller.function_mode = mode_name
        self.draw_settings_panel()  # Draw settings panel with updated function mode
        self.draw_debug_panel()  # Draw debug panel
        self.refresh_all_panels()  # Ensure top panel is refreshed
        
        win = self.get_active_window()
        if not win:
            return
        
        max_y, max_x = win.getmaxyx()
        
        # Header lines (fixed at top) - ensure function mode is current
        # Function mode should already be set, but ensure it's current
        self.controller.function_mode = mode_name
        header_lines = [
            f"Museum Mode: {self.controller.function_mode}",
            f"Delay: {self.controller.museum_delay} seconds",
            "Press Q to stop"
        ]
        
        # Calculate available lines for log messages
        header_height = len(header_lines)
        log_start_y = header_height
        max_log_lines = max_y - log_start_y - 1  # Reserve last line for potential overflow
        
        # List to store log messages (scrollable)
        log_messages = []
        
        # Track current character being encoded (for web display highlighting)
        current_char_index = [0]  # Use list to allow modification in nested functions
        
        # Track encoded/decoded text as it's being built (for real-time web display)
        current_encoded_text = [""]  # Use list to allow modification in nested functions
        
        # Track pause state for verification failures
        museum_paused = [False]  # Use list to allow modification in nested functions
        last_unexpected_input_time = [0]  # Use list to allow modification in nested functions
        
        # Track slide information
        current_message_index = [None]  # Index of current message in valid_messages
        current_slide_number = [1]  # Current slide number (1.png, 2.png, etc.)
        previous_slide_number = [0]  # Previous slide number to detect changes
        
        def draw_screen():
            """Draw the entire screen with header and log messages"""
            # Ensure function mode is current before drawing
            self.controller.function_mode = mode_name
            self.setup_screen()
            self.draw_settings_panel()  # This will display the updated function mode
            
            # Draw header lines
            for i, line in enumerate(header_lines):
                if i < max_y:
                    attr = curses.A_BOLD if i == 0 else curses.A_NORMAL
                    self.show_message(i, 0, line[:max_x], attr)
            
            # Draw log messages (scrollable)
            # Show most recent messages that fit
            available_lines = max_y - log_start_y
            messages_to_show = log_messages[-available_lines:] if len(log_messages) > available_lines else log_messages
            
            for i, log_msg in enumerate(messages_to_show):
                y = log_start_y + i
                if y < max_y:
                    # Display full message (show_message will handle truncation for display)
                    # Full message is stored in log_messages for web interface
                    self.show_message(y, 0, log_msg)
            
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        def add_log_message(msg: str):
            """Add a message to the log and redraw"""
            log_messages.append(msg)
            # Keep only last max_log_lines messages
            if len(log_messages) > max_log_lines:
                log_messages.pop(0)
            draw_screen()
        
        # Get saved config for reference
        saved = self.controller.get_saved_config()
        
        # Web server setup (after add_log_message is defined)
        web_server = None
        web_enabled = saved.get('web_server_enabled', False)
        web_port = saved.get('web_server_port', 8080)
        
        def get_slide_path():
            """Determine slide directory and image path"""
            if not self.controller.enable_slides or current_message_index[0] is None:
                return None
            
            slides_dir = os.path.join(SCRIPT_DIR, 'slides')
            message_index_dir = os.path.join(slides_dir, str(current_message_index[0]))
            common_dir = os.path.join(slides_dir, 'common')
            
            # Check if message index directory exists, otherwise use common
            if os.path.isdir(message_index_dir):
                slide_dir = message_index_dir
            elif os.path.isdir(common_dir):
                slide_dir = common_dir
            else:
                return None
            
            # Find available slide images and cycle through them
            slide_files = []
            for i in range(1, 1000):  # Check up to 999.png
                slide_file = os.path.join(slide_dir, f"{i}.png")
                if os.path.exists(slide_file):
                    slide_files.append(f"{i}.png")
                else:
                    break
            
            if not slide_files:
                return None
            
            # Cycle through slides based on current_slide_number (1-based)
            # Subtract 1 to convert to 0-based index, then modulo to cycle
            slide_index = (current_slide_number[0] - 1) % len(slide_files)
            slide_filename = slide_files[slide_index]
            
            # Return relative path from script directory for web server
            return os.path.join('slides', os.path.basename(slide_dir), slide_filename)
        
        # Data callback for web server
        def get_museum_data():
            """Get current museum mode data for web server"""
            slide_path = get_slide_path() if self.controller.enable_slides else None
            return {
                'function_mode': self.controller.function_mode,
                'delay': self.controller.museum_delay,
                'log_messages': log_messages.copy(),
                'is_encode_mode': is_encode,  # Track if encode or decode mode
                'config': self.controller.config.copy(),  # Current config for /status
                'word_group_size': self.controller.word_group_size,  # For message formatting
                'character_delay_ms': self.controller.character_delay_ms,  # Character delay setting
                'current_char_index': current_char_index[0],  # Current character being encoded (1-based)
                'current_encoded_text': current_encoded_text[0],  # Encoded/decoded text being built in real-time
                'enable_slides': self.controller.enable_slides,  # Enable slides feature
                'slide_path': slide_path  # Path to current slide image
            }
        
        # Start web server if enabled
        if web_enabled:
            web_server = MuseumWebServer(web_enabled, web_port, get_museum_data)
            server_ip = web_server.start()
            if server_ip:
                self.controller.web_server_ip = server_ip  # Store IP for display
                add_log_message(f"Web server started: http://{server_ip}:{web_port}")
            else:
                web_server = None
                self.controller.web_server_ip = None  # Clear IP if server failed
                add_log_message(f"Failed to start web server on port {web_port}")
        else:
            self.controller.web_server_ip = None  # Clear IP when disabled
        
        draw_screen()
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Helper function to restore spaces at exact positions from original message
        def restore_spaces(decoded_text: str, original_msg: str) -> str:
            """Restore spaces at exact positions from original message"""
            # Remove any existing spaces from decoded text
            decoded_no_spaces = decoded_text.replace(' ', '')
            result = list(decoded_no_spaces)
            
            # Only restore spaces up to the current decoded length
            current_length = len(decoded_no_spaces)
            if current_length == 0:
                return ''
            
            # Find space positions in original message (as character indices, not counting spaces)
            # Map positions in the original MSG (with spaces) to positions in decoded text (without spaces)
            space_positions = []
            char_index = 0
            for char in original_msg:
                if char == ' ':
                    # This space is at character position char_index in the non-spaced version
                    if char_index < current_length:
                        space_positions.append(char_index)
                else:
                    char_index += 1
            
            # Insert spaces at positions (reverse order to maintain indices)
            for pos in reversed(space_positions):
                if pos < len(result):
                    result.insert(pos, ' ')
            
            return ''.join(result)
        
        # Helper function to normalize text for comparison (remove spaces)
        def normalize_for_comparison(text: str) -> str:
            """Remove spaces for comparison"""
            return text.replace(' ', '').upper()
        
        last_message_time = 0
        
        while True:
            self.stdscr.nodelay(True)
            key = self.stdscr.getch()
            if key == ord('q') or key == ord('Q'):
                break
            
            current_time = time.time()
            
            # Check if paused due to verification failure or mismatch
            if museum_paused[0]:
                # Check for additional input from Enigma while paused
                if self.controller.ser and self.controller.ser.is_open:
                    try:
                        if self.controller.ser.in_waiting > 0:
                            # Additional input detected - read and clear it, then reset timer
                            self.controller.ser.read(self.controller.ser.in_waiting)
                            last_unexpected_input_time[0] = current_time
                            if debug_callback:
                                debug_callback("Additional input detected while paused - resetting timer")
                    except Exception:
                        pass  # Ignore read errors
                
                time_since_last_input = current_time - last_unexpected_input_time[0]
                if time_since_last_input >= self.controller.museum_delay:
                    # Resume museum mode - start over with a new random message immediately
                    museum_paused[0] = False
                    add_log_message("Museum mode resumed - starting new message")
                    # Reset timer to trigger message sending immediately
                    last_message_time = current_time - self.controller.museum_delay
                    # Reset encoded text and character index
                    current_char_index[0] = 0
                    current_encoded_text[0] = ""
                else:
                    # Still paused, skip sending messages
                    time.sleep(0.1)
                    continue
            
            if current_time - last_message_time >= self.controller.museum_delay:
                # Select random message object
                msg_obj = random.choice(valid_messages)
                # Track message index for slide directory lookup
                current_message_index[0] = valid_messages.index(msg_obj)
                # Reset slide number when starting new message
                current_slide_number[0] = 1
                previous_slide_number[0] = 0
                # Log initial slide if slides are enabled
                if self.controller.enable_slides:
                    slide_path = get_slide_path()
                    if slide_path:
                        add_log_message(f"Slide: {slide_path}")
                    else:
                        add_log_message("Slide: No slide image available")
                
                # Apply configuration from JSON message object
                if debug_callback:
                    debug_callback(f"Applying configuration from message...")
                
                self.controller.set_mode(msg_obj.get('MODEL', 'I'), debug_callback=debug_callback)
                time.sleep(0.2)
                self.controller.set_rotor_set(msg_obj.get('ROTOR', 'A III IV I'), debug_callback=debug_callback)
                time.sleep(0.2)
                self.controller.set_ring_settings(msg_obj.get('RINGSET', '01 01 01'), debug_callback=debug_callback)
                time.sleep(0.2)
                self.controller.set_ring_position(msg_obj.get('RINGPOS', '20 6 10'), debug_callback=debug_callback)
                time.sleep(0.2)
                self.controller.set_pegboard(msg_obj.get('PLUG', ''), debug_callback=debug_callback)
                time.sleep(0.2)
                # Set word group size from JSON
                self.controller.word_group_size = msg_obj.get('GROUP', 5)
                self.controller.return_to_encode_mode(debug_callback=debug_callback)
                time.sleep(0.5)
                
                # Determine message to send and expected result
                if is_encode:
                    message_to_send = msg_obj['MSG']
                    expected_result = msg_obj['CODED']
                    operation = "Encoding"
                else:
                    message_to_send = msg_obj['CODED']
                    expected_result = msg_obj['MSG']
                    operation = "Decoding"
                
                # Format message for display
                formatted_message = self.controller.format_message_for_display(message_to_send)
                # Display both MSG and CODED in museum mode
                formatted_msg = self.controller.format_message_for_display(msg_obj['MSG'])
                formatted_coded = self.controller.format_message_for_display(msg_obj['CODED'])
                add_log_message(f"{operation}:")
                add_log_message(f"  MSG: {formatted_msg}")
                add_log_message(f"  CODED: {formatted_coded}")
                
                # Normalize expected result for character-by-character comparison
                expected_normalized = normalize_for_comparison(expected_result)
                
                encoded_result = []
                current_char_index[0] = 0  # Reset current character index
                current_encoded_text[0] = ""  # Reset encoded text
                
                def progress_callback(index, total, original, encoded, response):
                    encoded_result.append(encoded)
                    # Update current character index for web display
                    current_char_index[0] = index
                    # Update encoded text in real-time
                    decoded_text = ''.join(encoded_result)
                    # Format for display based on mode
                    if is_encode:
                        # Encode mode: group the encoded text
                        if decoded_text:
                            current_encoded_text[0] = self.controller._group_encoded_text(decoded_text)
                        else:
                            current_encoded_text[0] = ""
                    else:
                        # Decode mode: restore spaces from MSG in real-time
                        if decoded_text:
                            current_encoded_text[0] = restore_spaces(decoded_text, msg_obj['MSG'])
                        else:
                            current_encoded_text[0] = ""
                    
                    # Update slide number every 10 characters
                    # Characters 1-10: slide 1, 11-20: slide 2, 21-30: slide 3, etc.
                    if self.controller.enable_slides:
                        # Calculate slide number: max(1, (index - 1) // 10 + 1)
                        # This gives: 0 -> 1, 1-10 -> 1, 11-20 -> 2, 21-30 -> 3, etc.
                        new_slide_number = max(1, ((index - 1) // 10) + 1)
                        if new_slide_number != previous_slide_number[0]:
                            current_slide_number[0] = new_slide_number
                            previous_slide_number[0] = new_slide_number
                            # Log slide change with path
                            slide_path = get_slide_path()
                            if slide_path:
                                add_log_message(f"Slide: {slide_path}")
                            else:
                                add_log_message("Slide: No slide image available")
                        else:
                            current_slide_number[0] = new_slide_number
                    
                    # Compare with expected character
                    if index > 0 and index <= len(expected_normalized):
                        expected_char = expected_normalized[index - 1]
                        encoded_upper = encoded.upper() if encoded else ''
                        matches = encoded_upper == expected_char
                        
                        if debug_callback:
                            if matches:
                                debug_callback(f"Expected: {expected_char}, Got: {encoded_upper} ✓ MATCH", color_type=self.COLOR_MATCH)
                            else:
                                debug_callback(f"Expected: {expected_char}, Got: {encoded_upper} ✗ MISMATCH", color_type=self.COLOR_MISMATCH)
                                # Mismatch detected - stop sending message and pause museum mode
                                if not museum_paused[0]:
                                    museum_paused[0] = True
                                    last_unexpected_input_time[0] = time.time()
                                    add_log_message(f"Encoding interrupted by user input - character mismatch detected")
                                    # Return True to stop sending the message
                                    return True
                    
                    return False
                
                def position_update_callback():
                    """Update settings panel when ring positions change or characters are sent/received"""
                    self.draw_settings_panel()
                    self.refresh_all_panels()
                
                message_sent = self.controller.send_message(message_to_send, progress_callback, debug_callback, position_update_callback)
                
                # Check if message was interrupted (stopped early due to mismatch)
                if museum_paused[0]:
                    # Message was interrupted by mismatch - already logged and paused
                    # Update web display to show interruption
                    if current_encoded_text[0]:
                        current_encoded_text[0] = current_encoded_text[0] + " [INTERRUPTED]"
                    else:
                        current_encoded_text[0] = "[INTERRUPTED]"
                    # Force UI update
                    self.draw_settings_panel()
                    self.refresh_all_panels()
                elif not message_sent:
                    # Message sending failed
                    add_log_message(f"{operation} failed or cancelled")
                else:
                    # Message completed - verify result
                    if encoded_result:
                        result = ''.join(encoded_result)
                        # Normalize for comparison (remove spaces)
                        result_normalized = normalize_for_comparison(result)
                        expected_normalized = normalize_for_comparison(expected_result)
                        
                        # Verify result matches expected
                        if result_normalized == expected_normalized:
                            # Success - format and display result
                            if is_encode:
                                grouped_result = self.controller._group_encoded_text(result)
                                add_log_message(f"Encoded: {grouped_result}")
                            else:
                                # Decode mode: use MSG directly since decoded result matches it exactly
                                formatted_decoded = self.controller.format_message_for_display(msg_obj['MSG'])
                                add_log_message(f"Decoded: {formatted_decoded}")
                        else:
                            # Verification failed - pause museum mode
                            add_log_message(f"Verification failed - pausing museum mode (Enigma may have been touched)")
                            museum_paused[0] = True
                            last_unexpected_input_time[0] = current_time
                    else:
                        add_log_message(f"{operation} failed or cancelled")
                
                # Reset current character index and encoded text after encoding completes
                current_char_index[0] = 0
                current_encoded_text[0] = ""
                
                last_message_time = current_time
            
            time.sleep(0.1)
        
        # Stop web server if running
        if web_server:
            web_server.stop()
            self.controller.web_server_ip = None  # Clear IP when stopped
            add_log_message("Web server stopped")
        
        # Restore screen state when exiting museum mode
        self.controller.function_mode = 'Interactive'
        self.stdscr.nodelay(False)  # Restore normal input mode
        # Clear and redraw screen to prevent flickering
        self.setup_screen()
        self.draw_settings_panel()
        self.draw_debug_panel()
        self.refresh_all_panels()
    
    def run(self, config_only: bool = False, museum_mode: Optional[str] = None, debug_enabled: bool = False):
        """Main UI loop
        
        Args:
            config_only: If True, show only config menu and exit after
            museum_mode: If set, start directly in specified museum mode ('2', '3', '4', or '5')
            debug_enabled: If True, enable debug output panel at startup
        """
        # Set debug enabled if requested via command line (before initializing curses)
        if debug_enabled:
            self.debug_enabled = True
        
        # Initialize curses with error handling
        try:
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            curses.curs_set(0)
            self.stdscr.keypad(True)
        except curses.error as e:
            # Clean up if initialization fails
            try:
                curses.endwin()
            except:
                pass
            print(f"ERROR: Failed to initialize curses interface: {e}")
            print("This usually happens when:")
            print("  - The terminal doesn't support curses")
            print("  - Running in a non-interactive environment")
            print("  - The terminal is too small or misconfigured")
            print("\nTry running in a proper terminal emulator (not a non-interactive shell).")
            sys.exit(1)
        
        # Initialize colors if supported
        if curses.has_colors():
            curses.start_color()
            # Cyan for data sent to Enigma
            curses.init_pair(self.COLOR_SENT, curses.COLOR_CYAN, curses.COLOR_BLACK)
            # Bright green for data received from Enigma (we'll add bold when using it)
            curses.init_pair(self.COLOR_RECEIVED, curses.COLOR_GREEN, curses.COLOR_BLACK)
            # Yellow for other info
            curses.init_pair(self.COLOR_INFO, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            # Light purple for character delay messages
            curses.init_pair(self.COLOR_DELAY, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
            # Bright green for matching characters (with bold)
            curses.init_pair(self.COLOR_MATCH, curses.COLOR_GREEN, curses.COLOR_BLACK)
            # Red for mismatching characters
            curses.init_pair(self.COLOR_MISMATCH, curses.COLOR_RED, curses.COLOR_BLACK)
            # Grey for disabled web server
            curses.init_pair(self.COLOR_WEB_DISABLED, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Using white as grey (dim)
        
        # Check terminal size
        min_cols = 100
        min_lines = 25
        if curses.COLS < min_cols or curses.LINES < min_lines:
            self.stdscr.addstr(0, 0, f"Terminal too small! Need at least {min_cols}x{min_lines}, got {curses.COLS}x{curses.LINES}")
            self.stdscr.addstr(1, 0, "Please resize your terminal and restart.")
            self.stdscr.refresh()
            self.stdscr.getch()
            return
        
        try:
            # If config-only mode, go straight to config menu
            if config_only:
                result = self.config_menu(exit_after=True)
                if result == 'exit':
                    return
                # Should not reach here, but just in case
                return
            
            # If museum mode specified, start directly in that mode
            if museum_mode:
                self.run_museum_mode(museum_mode)
                return
            
            while True:
                choice = self.main_menu()
                
                if choice == 'quit' or choice == 'Q':
                    break
                elif choice == '1':
                    self.send_message_screen()
                elif choice == '2':
                    self.config_menu()
                elif choice == '3':
                    self.query_settings_screen()
                elif choice == '4':
                    self.museum_mode_screen()
                elif choice == '5':
                    self.set_all_settings_screen()
        
        finally:
            self.destroy_subwindows()
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()


def print_help():
    """Print help/usage information"""
    script_name = os.path.basename(sys.argv[0])
    help_text = f"""
Enigma Museum Controller - CLI tool for controlling Enigma device

Usage:
    {script_name} [OPTIONS] [DEVICE]

Options:
    --config, -c              Open configuration menu without connecting to device
                              (useful for changing device settings when device is unavailable)
    --museum-en-encode        Start in Encode - EN mode (English encode)
    --museum-en-decode        Start in Decode - EN mode (English decode)
    --museum-de-encode        Start in Encode - DE mode (German encode)
    --museum-de-decode        Start in Decode - DE mode (German decode)
    --debug                   Enable debug output panel (shows serial communication)
    --help, -h                Show this help message and exit

Arguments:
    DEVICE                     Serial device path (default: {DEFAULT_DEVICE})
                              Examples: /dev/ttyACM0, /dev/ttyUSB0 (Linux)
                                        /dev/cu.usbserial-1410 (macOS)

Examples:
    {script_name}                        # Run with default device ({DEFAULT_DEVICE})
    {script_name} /dev/ttyUSB0          # Run with specific device
    {script_name} --config               # Open config menu to change settings
    {script_name} --museum-en-encode    # Start directly in Encode - EN mode
    {script_name} --museum-en-decode /dev/ttyACM0  # Start Decode - EN mode with specific device
    {script_name} --museum-de-encode   # Start Encode - DE mode
    {script_name} --museum-de-decode   # Start Decode - DE mode

Description:
    This tool provides a curses-based menu interface for controlling an Enigma
    device via serial communication. You can send messages, configure settings,
    query device state, and run museum mode demonstrations.

    Museum modes automatically send messages at configured intervals. Encode modes
    send original messages and verify encoded results. Decode modes send coded messages
    and verify decoded results. All modes use JSON files with pre-generated messages.

    If connection fails, use --config to change the device path without
    requiring a connection.
"""
    print(help_text)


def main():
    """Main entry point"""
    device = None  # None means use config file or default
    config_only = False
    museum_mode = None
    debug_enabled = False
    
    # Parse command line arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg in ('--help', '-h'):
            print_help()
            sys.exit(0)
        elif arg in ('--config', '-c'):
            config_only = True
        elif arg == '--museum-en-encode':
            museum_mode = '2'
        elif arg == '--museum-en-decode':
            museum_mode = '3'
        elif arg == '--museum-de-encode':
            museum_mode = '4'
        elif arg == '--museum-de-decode':
            museum_mode = '5'
        elif arg == '--debug':
            debug_enabled = True
        elif arg.startswith('-'):
            # Unknown option
            print(f"Unknown option: {arg}")
            print("Use --help or -h for usage information.")
            sys.exit(1)
        else:
            # This should be the device path
            device = arg
        i += 1
    
    # If no device specified on command line, load from config file
    if device is None:
        # Load config to get device path
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    if 'device' in config_data:
                        device = config_data['device']
        except Exception:
            pass
        # Fall back to default if no device in config
        if device is None:
            device = DEFAULT_DEVICE
        preserve_device = False
    else:
        # Device was explicitly specified on command line, preserve it
        preserve_device = True
    
    controller = EnigmaController(device, preserve_device=preserve_device)
    
    # If config-only mode, skip connection and go straight to config menu
    if config_only:
        try:
            ui = EnigmaMuseumUI(controller)
            ui.run(config_only=True, debug_enabled=debug_enabled)
        except KeyboardInterrupt:
            pass
        finally:
            print("\nGoodbye!")
        return
    
    # Normal mode - try to connect
    # Use controller.device to show the actual device being used
    print(f"Connecting to {controller.device}...")
    if not controller.connect():
        print(f"ERROR: Could not connect to {controller.device}")
        print("Make sure the device is connected and you have permission to access it.")
        print(f"\nTo change the device, run: {sys.argv[0]} --config")
        sys.exit(1)
    
    print("Connected! Starting UI...")
    time.sleep(1)
    
    try:
        ui = EnigmaMuseumUI(controller)
        ui.run(museum_mode=museum_mode, debug_enabled=debug_enabled)
    except KeyboardInterrupt:
        pass
    finally:
        controller.disconnect()
        print("\nDisconnected. Goodbye!")


if __name__ == '__main__':
    main()