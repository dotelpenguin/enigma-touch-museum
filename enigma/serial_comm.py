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
            return False
    
    def disconnect(self):
        """Close serial connection"""
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
                                    if j + 5 < len(parts):
                                        try:
                                            pos1 = int(parts[j+3])
                                            pos2 = int(parts[j+4])
                                            pos3 = int(parts[j+5])
                                            pos_str = f"{pos1:02d} {pos2:02d} {pos3:02d}"
                                            # Update ring position if different
                                            if config.get('ring_position') != pos_str:
                                                config['ring_position'] = pos_str
                                                if self.monitoring_config_update_callback:
                                                    try:
                                                        self.monitoring_config_update_callback()
                                                    except Exception:
                                                        pass
                                        except (ValueError, IndexError):
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

