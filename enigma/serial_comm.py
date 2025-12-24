#!/usr/bin/env python3
"""
Serial communication for Enigma Museum Controller
"""

import serial
import time
import threading
import re
from typing import Optional, Tuple, Callable
from .constants import BAUD_RATE, CMD_TIMEOUT


def _parse_position_value(value: str) -> int:
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


def _get_rotor_count(model: str) -> int:
    """Get the number of rotors for a given model
    
    Args:
        model: Model name (e.g., 'M4', 'M3', 'I')
        
    Returns:
        Number of rotors: 4 for M4, 3 for all other models
    """
    if model.upper() == 'M4':
        return 4
    return 3


def _parse_positions(parts: list, start_idx: int, rotor_count: int) -> Optional[Tuple[int, ...]]:
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
            pos_value = _parse_position_value(parts[start_idx + i])
            positions.append(pos_value)
        return tuple(positions)
    except (ValueError, IndexError):
        return None


def _filter_config_summary(response: bytes, debug_callback=None) -> bytes:
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


class SerialConnection:
    """Handles low-level serial communication with Enigma device"""
    
    def __init__(self, device: str):
        self.device = device
        self.ser: Optional[serial.Serial] = None
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_debug_callback: Optional[Callable] = None
        self.monitoring_ui_refresh_callback: Optional[Callable] = None
        self.monitoring_keypress_callback: Optional[Callable] = None
        self.monitoring_config_update_callback: Optional[Callable] = None
    
    def connect(self) -> bool:
        """Connect to serial device"""
        # Ensure any existing connection is properly closed first
        if self.ser:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass
            self.ser = None
        
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
        except serial.SerialException:
            # Ensure ser is None on failure
            self.ser = None
            return False
    
    def disconnect(self):
        """Close serial connection and release port"""
        self.stop_monitoring()
        if self.ser:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass  # Ignore errors during disconnect
            finally:
                # Release reference to allow port to be reused
                self.ser = None
    
    def is_connected(self) -> bool:
        """Check if serial connection is open and accessible"""
        if not self.ser:
            return False
        if not self.ser.is_open:
            return False
        # Try to check if port is still accessible by checking port status
        try:
            # Attempt a simple operation to verify connection
            # Reading port status doesn't send data but checks if port is accessible
            _ = self.ser.in_waiting
            return True
        except (serial.SerialException, OSError, AttributeError):
            return False
    
    def start_monitoring(self):
        """Start background thread to monitor Enigma input (no-op, monitoring was removed)"""
        # Monitoring thread was removed - this method is kept for compatibility
        pass
    
    def stop_monitoring(self):
        """Stop background monitoring thread (no-op, monitoring was removed)"""
        # Monitoring thread was removed - this method is kept for compatibility
        pass
    
    def _monitor_input(self, config: dict, last_char_original_ref: list, last_char_received_ref: list):
        """Background thread to continuously monitor serial input from Enigma
        
        Args:
            config: Dictionary reference to update ring_position
            last_char_original_ref: List reference to update last_char_original
            last_char_received_ref: List reference to update last_char_received
        """
        buffer = b''
        last_data_time = None
        processing_timeout = 0.15  # Wait 150ms of silence before processing
        
        while self.monitoring_active:
            try:
                # Always read data immediately to prevent loss
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
                        # Filter out config summary if present
                        buffer = _filter_config_summary(buffer, debug_callback=self.monitoring_debug_callback)
                        
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
                                    
                                    # Get rotor count from config
                                    model = config.get('mode', 'I')
                                    rotor_count = _get_rotor_count(model)
                                    
                                    # Log keypress to debug output
                                    if self.monitoring_debug_callback:
                                        pos_info = ""
                                        # Parse positions using helper function (handles letters and numbers, 3 or 4 rotors)
                                        positions = _parse_positions(parts, j + 3, rotor_count)
                                        if positions:
                                            pos_str = ' '.join(f"{p:02d}" for p in positions)
                                            pos_info = f" Positions {pos_str}"
                                            
                                            # Check for optional Counter field after positions
                                            counter_idx = j + 3 + rotor_count
                                            if counter_idx < len(parts) and parts[counter_idx].lower() == 'counter':
                                                if counter_idx + 1 < len(parts):
                                                    try:
                                                        counter_value = int(parts[counter_idx + 1])
                                                        pos_info += f" Counter {counter_value}"
                                                    except ValueError:
                                                        pass
                                        
                                        self.monitoring_debug_callback(f">>> '{original_char}'")
                                        self.monitoring_debug_callback(f"<<< {original_char} {encoded_char}{pos_info}")
                                    
                                    # Update last character info
                                    if last_char_original_ref:
                                        last_char_original_ref[0] = original_char
                                    if last_char_received_ref:
                                        last_char_received_ref[0] = encoded_char
                                    
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
                                    # Check if we have enough parts for positions (2 + rotor_count)
                                    if j + 2 + rotor_count <= len(parts):
                                        # Parse positions using helper function (handles letters and numbers, 3 or 4 rotors)
                                        positions = _parse_positions(parts, j + 3, rotor_count)
                                        if positions:
                                            # Format preserving original format (letters or numbers)
                                            # Check if original parts were letters or numbers
                                            pos_str_parts = []
                                            for i in range(rotor_count):
                                                original_value = parts[j + 3 + i].strip().upper()
                                                # Check if original was a letter (A-Z)
                                                if len(original_value) == 1 and original_value.isalpha():
                                                    # Format as letter
                                                    pos_str_parts.append(chr(ord('A') + positions[i] - 1))
                                                else:
                                                    # Format as number - preserve original format exactly
                                                    try:
                                                        # Try to parse as int to verify it's a valid number
                                                        original_num = int(original_value)
                                                        # Verify the parsed value matches what we have
                                                        if original_num == positions[i]:
                                                            # Preserve the exact original format
                                                            pos_str_parts.append(original_value)
                                                        else:
                                                            # Mismatch - fallback to two-digit format
                                                            pos_str_parts.append(f"{positions[i]:02d}")
                                                    except ValueError:
                                                        # Not a number, fallback to two-digit format
                                                        pos_str_parts.append(f"{positions[i]:02d}")
                                            pos_str = ' '.join(pos_str_parts)
                                            # Update ring position if different
                                            if config.get('ring_position') != pos_str:
                                                config['ring_position'] = pos_str
                                                if self.monitoring_config_update_callback:
                                                    try:
                                                        self.monitoring_config_update_callback()
                                                    except Exception:
                                                        pass
                                    
                                    break
                            
                            # Clear buffer after processing
                            buffer = b''
                            last_data_time = None
                        except Exception:
                            # If parsing fails, clear buffer to avoid accumulation
                            if len(buffer) > 500:  # Buffer too large, clear it
                                buffer = b''
                                last_data_time = None
                
                # Sleep briefly to avoid busy-waiting
                time.sleep(0.02)
            except Exception:
                # On any error, sleep and continue
                time.sleep(0.1)
    
    @staticmethod
    def has_error_response(response: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Check if response contains an error message matching pattern: ^ + line return + *** + error message
        
        Pattern: literal '^' character, followed by line return (\r\n or \n), followed by '*** ' and error message
        
        Args:
            response: The response string to check
            
        Returns:
            Tuple of (has_error, error_message) where error_message is the extracted error text or None
        """
        if not response:
            return (False, None)
        
        # Match pattern: ^ followed by line return(s) followed by *** and space, then error message
        pattern = r'\^[\r]*\n\*\*\* (.+)'
        match = re.search(pattern, response)
        if match:
            error_message = match.group(1).strip()
            return (True, error_message)
        
        # Also check for pattern at start of line (in case ^ is missing but *** error is present)
        pattern2 = r'(?:^|\r?\n)\*\*\* (.+)'
        match2 = re.search(pattern2, response)
        if match2:
            error_message = match2.group(1).strip()
            return (True, error_message)
        
        return (False, None)
    
    def send_command(self, command: bytes, timeout: float = CMD_TIMEOUT, debug_callback=None) -> Optional[str]:
        """Send a command and return response"""
        if not self.ser or not self.ser.is_open:
            return None
        
        try:
            # Clear input buffer before sending command to avoid mixing with previous data
            self.ser.reset_input_buffer()
            time.sleep(0.1)  # Small delay after clearing buffer
            
            # Decode command for logging
            try:
                cmd_str = command.decode('ascii', errors='replace')
                cmd_str = cmd_str.replace('\r', '').replace('\n', '').strip()
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
            
            # Final check for any remaining data
            if self.ser.in_waiting > 0:
                time.sleep(0.1)
                if self.ser.in_waiting > 0:
                    response += self.ser.read(self.ser.in_waiting)
            
            # Only clear buffer if there's still data after our final read attempt
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

