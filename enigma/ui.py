#!/usr/bin/env python3
"""
Main UI coordinator for Enigma Museum Controller
"""

import curses
import time
import sys
import random
import json
import os
import threading
import socket
import html as html_module
import serial
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple, List

from enigma.constants import VERSION, DEFAULT_DEVICE, BAUD_RATE, CHAR_TIMEOUT, CMD_TIMEOUT, SCRIPT_DIR, CONFIG_FILE, ENGLISH_MSG_FILE, GERMAN_MSG_FILE, MIN_COLS, MIN_LINES
from enigma.messages import ENGLISH_MESSAGES, GERMAN_MESSAGES, load_messages_from_file
from enigma.enigma_controller import EnigmaController
from enigma.web_server import MuseumWebServer
from enigma.base import UIBase


class EnigmaMuseumUI(UIBase):
    """Curses-based UI for Enigma Museum Controller"""
    
    def __init__(self, controller: EnigmaController, simulate_mode: bool = False):
        # Initialize UIBase - stdscr will be set in run() method
        UIBase.__init__(self, controller, None)
        self.controller = controller
        self.stdscr = None  # Will be initialized in run() method
        self.simulate_mode = simulate_mode
        # Note: Most base methods are inherited from UIBase





    def setup_screen(self):
        """Clear screen, draw border, dividers, and create subwindows"""
        if not self.stdscr:
            return
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
        if self.simulate_mode:
            # In simulation mode, only show Museum Mode option
            options = [
                ("4", "Museum Mode"),
                ("8", f"Debug: {'true' if self.debug_enabled else 'false'}"),
                ("Q", "Quit")
            ]
        else:
            options = [
                ("1", "Send Message"),
                ("2", "Configuration"),
                ("3", "Query All Settings"),
                ("4", "Museum Mode"),
                ("5", "Send Enigma Config"),
                ("6", "Send Enigma Lock Config"),
                ("7", "Factory Reset Enigma"),
                ("8", f"Debug: {'true' if self.debug_enabled else 'false'}"),
                ("9", f"Raw Debug: {'ON' if self.controller.raw_debug_enabled else 'OFF'}"),
                ("Q", "Quit")
            ]
        
        selected = 0
        while True:
            # Update debug status in options
            if self.simulate_mode:
                # In simulation mode, only update debug option (index 1)
                options[1] = ("8", f"Debug: {'true' if self.debug_enabled else 'false'}")
            else:
                # In normal mode, update both debug options
                options[7] = ("8", f"Debug: {'true' if self.debug_enabled else 'false'}")
                options[8] = ("9", f"Raw Debug: {'ON' if self.controller.raw_debug_enabled else 'OFF'}")
            menu_title = "Enigma Museum Controller" + (" [SIMULATION MODE]" if self.simulate_mode else "")
            self.show_menu(menu_title, options, selected)
            key = self.stdscr.getch()
            
            if key == ord('q') or key == ord('Q'):
                return 'quit'
            elif key == ord('8'):
                # Toggle debug
                self.debug_enabled = not self.debug_enabled
                if not self.debug_enabled:
                    self.debug_output = []  # Clear debug output when disabled
                self.create_subwindows()  # Recreate subwindows
                self.add_debug_output(f"Debug {'enabled' if self.debug_enabled else 'disabled'}")
                continue
            elif key == ord('9') and not self.simulate_mode:
                # Toggle raw debug (only in normal mode)
                self.controller.raw_debug_enabled = not self.controller.raw_debug_enabled
                self.controller.save_config()
                self.add_debug_output(f"Raw Debug {'enabled' if self.controller.raw_debug_enabled else 'disabled'}")
                continue
            elif key == curses.KEY_UP:
                selected = (selected - 1) % len(options)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(options)
            elif key == ord('\n') or key == ord('\r'):
                if options[selected][0] == 'Q':
                    return 'quit'
                elif options[selected][0] == '8':
                    # Toggle debug
                    self.debug_enabled = not self.debug_enabled
                    if not self.debug_enabled:
                        self.debug_output = []  # Clear debug output when disabled
                    self.create_subwindows()  # Recreate subwindows
                    self.add_debug_output(f"Debug {'enabled' if self.debug_enabled else 'disabled'}")
                    continue
                elif options[selected][0] == '9' and not self.simulate_mode:
                    # Toggle raw debug (only in normal mode)
                    self.controller.raw_debug_enabled = not self.controller.raw_debug_enabled
                    self.controller.save_config()
                    self.add_debug_output(f"Raw Debug {'enabled' if self.controller.raw_debug_enabled else 'disabled'}")
                    continue
                return options[selected][0]
            elif key >= ord('1') and key <= ord('9'):
                return chr(key)
    
    def config_menu(self, exit_after: bool = False):
        """Configuration menu with sections
        
        Args:
            exit_after: If True, exit the application after leaving the menu
        """
        options = [
            ("1", "Enigma Cipher Options"),
            ("2", "WebPage Options"),
            ("3", "Enigma Touch Device Options"),
            ("4", "Utilities"),
            ("B", "Back")
        ]
        
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
                elif options[selected][0] == '1':
                    self.config_menu_enigma()
                elif options[selected][0] == '2':
                    self.config_menu_webpage()
                elif options[selected][0] == '3':
                    self.config_menu_kiosk()
                elif options[selected][0] == '4':
                    self.config_menu_utilities()
            elif key >= ord('1') and key <= ord('4'):
                section = chr(key)
                if section == '1':
                    self.config_menu_enigma()
                elif section == '2':
                    self.config_menu_webpage()
                elif section == '3':
                    self.config_menu_kiosk()
                elif section == '4':
                    self.config_menu_utilities()
    
    def config_menu_enigma(self):
        """Enigma Cipher Options submenu"""
        def get_options():
            saved = self.controller.get_saved_config()
            return [
                ("1", f"Set Device (current: {saved['device']})"),
                ("2", f"Set Mode (current: {saved['config']['mode']})"),
                ("3", f"Set Rotor Set (current: {saved['config']['rotor_set']})"),
                ("4", f"Set Rings (current: {saved['config']['ring_settings']})"),
                ("5", f"Set Ring Position (current: {saved['config']['ring_position']})"),
                ("6", f"Set Plugboard (current: {saved['config']['pegboard']})"),
                ("7", f"Always Send Config Before Message: {str(saved['always_send_config']).lower()}"),
                ("B", "Back")
            ]
        
        options = get_options()
        selected = 0
        while True:
            self.show_menu("Enigma Cipher Options", options, selected)
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
                self.handle_config_option_enigma(options[selected][0])
                options = get_options()
            elif key >= ord('1') and key <= ord('7'):
                self.handle_config_option_enigma(chr(key))
                options = get_options()
    
    def config_menu_webpage(self):
        """WebPage Options submenu"""
        def get_options():
            saved = self.controller.get_saved_config()
            return [
                ("1", f"Set Word Group (current: {saved['word_group_size']})"),
                ("2", f"Set Character Delay (current: {saved.get('character_delay_ms', 0)}ms)"),
                ("3", f"Web Server: {str(saved.get('web_server_enabled', False)).lower()}"),
                ("4", f"Set Web Server Port (current: {saved.get('web_server_port', 8080)})"),
                ("5", f"Enable Slides: {str(saved.get('enable_slides', False)).lower()}"),
                ("B", "Back")
            ]
        
        options = get_options()
        selected = 0
        while True:
            self.show_menu("WebPage Options", options, selected)
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
                self.handle_config_option_webpage(options[selected][0])
                options = get_options()
            elif key >= ord('1') and key <= ord('5'):
                self.handle_config_option_webpage(chr(key))
                options = get_options()
    
    def config_menu_kiosk(self):
        """Enigma Touch Device Options submenu"""
        def get_options():
            saved = self.controller.get_saved_config()
            return [
                ("1", f"Set Museum Delay (current: {saved['museum_delay']}s)"),
                ("2", f"Lock Model: {str(saved.get('lock_model', True)).lower()}"),
                ("3", f"Lock Rotor/Wheel: {str(saved.get('lock_rotor', True)).lower()}"),
                ("4", f"Lock Ring: {str(saved.get('lock_ring', True)).lower()}"),
                ("5", f"Disable Auto-PowerOff: {str(saved.get('disable_power_off', True)).lower()}"),
                ("6", f"Set Brightness (current: {saved.get('brightness', 3)}, range: 1-5)"),
                ("7", f"Set Volume (current: {saved.get('volume', 0)}, range: 0-6)"),
                ("8", f"Set Screen Saver (current: {saved.get('screen_saver', 0)}, range: 0-99)"),
                ("B", "Back")
            ]
        
        options = get_options()
        selected = 0
        while True:
            self.show_menu("Enigma Touch Device Options", options, selected)
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
                self.handle_config_option_kiosk(options[selected][0])
                options = get_options()
            elif key >= ord('1') and key <= ord('8'):
                self.handle_config_option_kiosk(chr(key))
                options = get_options()
    
    def config_menu_utilities(self):
        """Utilities submenu"""
        options = [
            ("1", "Generate Coded Messages - EN"),
            ("2", "Generate Coded Messages - DE"),
            ("3", "Validate Models.json"),
            ("4", ""),  # Will be set in loop
            ("B", "Back")
        ]
        
        selected = 0
        while True:
            # Refresh status from controller's current value (updated immediately after toggle)
            use_models_json_status = str(getattr(self.controller, 'use_models_json', False)).lower()
            options[3] = ("4", f"Use models.json when generating: {use_models_json_status}")
            
            self.show_menu("Utilities", options, selected)
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
                elif options[selected][0] == '1':
                    self.handle_config_option('10')  # Generate EN
                elif options[selected][0] == '2':
                    self.handle_config_option('11')  # Generate DE
                elif options[selected][0] == '3':
                    self.handle_config_option('23')  # Validate Models.json
                elif options[selected][0] == '4':
                    self.handle_config_option('24')  # Toggle Use models.json
            elif key >= ord('1') and key <= ord('4'):
                if chr(key) == '1':
                    self.handle_config_option('10')  # Generate EN
                elif chr(key) == '2':
                    self.handle_config_option('11')  # Generate DE
                elif chr(key) == '3':
                    self.handle_config_option('23')  # Validate Models.json
                elif chr(key) == '4':
                    self.handle_config_option('24')  # Toggle Use models.json
    
    def draw_validation_progress(self, current_idx: int, total: int, name: str, status: str, valid_count: int, invalid_count: int, results: list):
        """Draw validation progress in the left window"""
        if not self.left_win:
            return
        
        try:
            self.left_win.clear()
            max_y, max_x = self.left_win.getmaxyx()
            
            # Title
            title = "Validate Models.json"
            title_x = (max_x - len(title)) // 2
            if title_x >= 0:
                self.left_win.addstr(0, title_x, title, curses.A_BOLD | curses.A_UNDERLINE)
            
            # Progress summary
            progress_line = f"Progress: {current_idx}/{total} ({valid_count} valid, {invalid_count} invalid)"
            y = 2
            if y < max_y:
                self.left_win.addstr(y, 0, progress_line[:max_x], curses.A_BOLD)
            
            # Current test
            y = 4
            if y < max_y:
                current_line = f"Testing [{current_idx}/{total}]: {name[:max_x-20]}"
                self.left_win.addstr(y, 0, current_line[:max_x], curses.A_BOLD)
            
            # Status
            y = 5
            if y < max_y:
                status_attr = curses.A_BOLD
                if status == "VALID":
                    if curses.has_colors():
                        status_attr |= curses.color_pair(self.COLOR_MATCH)
                    status_text = "✓ VALID"
                elif status == "INVALID":
                    if curses.has_colors():
                        status_attr |= curses.color_pair(self.COLOR_MISMATCH)
                    status_text = "✗ INVALID"
                else:
                    status_text = status
                self.left_win.addstr(y, 0, status_text[:max_x], status_attr)
            
            # Results list
            y = 7
            if y < max_y:
                header = "Results:"
                self.left_win.addstr(y, 0, header, curses.A_BOLD)
                y += 1
            
            # Display results (most recent first, scrollable)
            available_lines = max_y - y - 1
            results_to_show = results[-available_lines:] if len(results) > available_lines else results
            
            for result in results_to_show:
                if y >= max_y - 1:
                    break
                idx = result['index']
                name_short = result['name'][:max_x-15]
                is_valid = result['valid']
                
                result_line = f"[{idx:2d}] {name_short}"
                result_attr = curses.A_NORMAL
                if is_valid:
                    if curses.has_colors():
                        result_attr = curses.color_pair(self.COLOR_MATCH) | curses.A_BOLD
                    result_line += " ✓"
                else:
                    if curses.has_colors():
                        result_attr = curses.color_pair(self.COLOR_MISMATCH) | curses.A_BOLD
                    result_line += " ✗"
                
                # Truncate to fit
                result_line = result_line[:max_x]
                self.left_win.addstr(y, 0, result_line, result_attr)
                y += 1
            
            self.left_win.refresh()
        except:
            pass
    
    def prompt_continue_on_error(self, error_msg: str, error_details: str) -> bool:
        """Prompt user to continue or quit when an error is found
        
        Args:
            error_msg: Main error message
            error_details: Detailed error information
            
        Returns:
            True if user wants to continue, False if they want to quit
        """
        if not self.left_win:
            return True  # Default to continue if no window
        
        try:
            max_y, max_x = self.left_win.getmaxyx()
            
            # Clear and show error prompt
            self.left_win.clear()
            
            # Title
            title = "ERROR FOUND"
            title_x = (max_x - len(title)) // 2
            if title_x >= 0:
                title_attr = curses.A_BOLD | curses.A_UNDERLINE
                if curses.has_colors():
                    title_attr |= curses.color_pair(self.COLOR_MISMATCH)
                self.left_win.addstr(0, title_x, title, title_attr)
            
            # Error message
            y = 2
            if y < max_y:
                msg_line = error_msg[:max_x]
                msg_attr = curses.A_BOLD
                if curses.has_colors():
                    msg_attr |= curses.color_pair(self.COLOR_MISMATCH)
                self.left_win.addstr(y, 0, msg_line, msg_attr)
                y += 1
            
            # Error details
            if y < max_y:
                details_line = error_details[:max_x]
                details_attr = curses.A_NORMAL
                if curses.has_colors():
                    details_attr = curses.color_pair(self.COLOR_MISMATCH)
                self.left_win.addstr(y, 0, details_line[:max_x], details_attr)
                y += 2
            
            # Prompt
            if y < max_y:
                prompt = "Continue validation? (C)ontinue / (Q)uit"
                self.left_win.addstr(y, 0, prompt[:max_x], curses.A_BOLD)
                y += 1
            
            # Instructions
            if y < max_y:
                instructions = "Press C to continue, Q to quit"
                self.left_win.addstr(y, 0, instructions[:max_x])
            
            self.left_win.refresh()
            self.draw_debug_panel()
            self.refresh_all_panels()
            
            # Wait for user input
            while True:
                key = self.stdscr.getch()
                if key == ord('c') or key == ord('C'):
                    return True  # Continue
                elif key == ord('q') or key == ord('Q'):
                    return False  # Quit
                elif key == ord('\n') or key == ord('\r'):
                    # Enter key - default to continue
                    return True
                elif key == 27:  # ESC key - quit
                    return False
        
        except:
            # On error, default to continue
            return True
    
    def validate_models_json(self, debug_callback=None):
        """Validate all configurations in models.json by attempting to set them on the Enigma device"""
        models_file = os.path.join(SCRIPT_DIR, 'models.json')
        
        if not os.path.exists(models_file):
            if debug_callback:
                debug_callback(f"ERROR: models.json not found at {models_file}", color_type=7)
            self.show_message(2, 0, f"ERROR: models.json not found!")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            return
        
        # Check if device is connected
        if not self.controller.is_connected():
            if debug_callback:
                debug_callback("ERROR: Device not connected. Please connect to Enigma device first.", color_type=7)
            self.show_message(2, 0, "ERROR: Device not connected!")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            return
        
        # Load models.json
        try:
            with open(models_file, 'r') as f:
                models = json.load(f)
        except json.JSONDecodeError as e:
            if debug_callback:
                debug_callback(f"ERROR: Invalid JSON in models.json: {e}", color_type=7)
            self.show_message(2, 0, f"ERROR: Invalid JSON in models.json!")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            return
        except Exception as e:
            if debug_callback:
                debug_callback(f"ERROR: Failed to read models.json: {e}", color_type=7)
            self.show_message(2, 0, f"ERROR: Failed to read models.json!")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            return
        
        if not isinstance(models, list):
            if debug_callback:
                debug_callback("ERROR: models.json must contain a JSON array", color_type=7)
            self.show_message(2, 0, "ERROR: models.json must be an array!")
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            return
        
        if debug_callback:
            debug_callback(f"Validating {len(models)} configurations from models.json...")
        
        # Setup screen for validation display
        self.setup_screen()
        self.draw_settings_panel()
        
        invalid_configs = []
        valid_count = 0
        results = []  # List of {index, name, valid, errors}
        
        # Test each configuration
        for idx, model_config in enumerate(models, 1):
            name = model_config.get('name', f'Configuration {idx}')
            model = model_config.get('MODEL', '')
            rotor = model_config.get('ROTOR', '')
            ringset = model_config.get('RINGSET', '')
            ringpos = model_config.get('RINGPOS', '')
            plug = model_config.get('PLUG', '')
            
            if debug_callback:
                debug_callback(f"[{idx}/{len(models)}] Testing: {name}")
                debug_callback(f"  MODEL: {model}, ROTOR: {rotor}, RINGSET: {ringset}, RINGPOS: {ringpos}, PLUG: {plug}")
            
            # Update progress display (showing "Testing...")
            self.draw_validation_progress(idx, len(models), name, "Testing...", valid_count, len(invalid_configs), results)
            self.draw_debug_panel()
            self.refresh_all_panels()
            
            errors = []
            
            # Test MODEL
            if model:
                if not self.controller.set_mode(model, debug_callback=debug_callback):
                    errors.append(f"MODEL ({model})")
                time.sleep(0.2)
            
            # Test ROTOR
            if rotor:
                if not self.controller.set_rotor_set(rotor, debug_callback=debug_callback):
                    errors.append(f"ROTOR ({rotor})")
                time.sleep(0.2)
            
            # Test RINGSET
            if ringset:
                if not self.controller.set_ring_settings(ringset, debug_callback=debug_callback):
                    errors.append(f"RINGSET ({ringset})")
                time.sleep(0.2)
            
            # Test RINGPOS
            if ringpos:
                if not self.controller.set_ring_position(ringpos, debug_callback=debug_callback):
                    errors.append(f"RINGPOS ({ringpos})")
                time.sleep(0.2)
            
            # Test PLUG (plugboard)
            if plug is not None:  # Empty string is valid (clears plugboard)
                if not self.controller.set_pegboard(plug, debug_callback=debug_callback):
                    errors.append(f"PLUG ({plug if plug else 'clear'})")
                time.sleep(0.2)
            
            # Record result
            is_valid = len(errors) == 0
            if is_valid:
                valid_count += 1
                if debug_callback:
                    debug_callback(f"  ✓ VALID", color_type=6)
            else:
                invalid_configs.append({
                    'index': idx,
                    'name': name,
                    'errors': errors
                })
                if debug_callback:
                    debug_callback(f"  ❌ INVALID: {', '.join(errors)}", color_type=7)
                
                # Pause and ask user if they want to continue
                error_msg = f"Error found in [{idx}] {name}"
                error_details = f"Errors: {', '.join(errors)}"
                if not self.prompt_continue_on_error(error_msg, error_details):
                    # User chose to quit
                    if debug_callback:
                        debug_callback("Validation cancelled by user")
                    break
            
            results.append({
                'index': idx,
                'name': name,
                'valid': is_valid,
                'errors': errors
            })
            
            # Update progress display with result
            status = "VALID" if is_valid else "INVALID"
            self.draw_validation_progress(idx, len(models), name, status, valid_count, len(invalid_configs), results)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Display final results
        if debug_callback:
            debug_callback("")
            debug_callback("=" * 60)
            if invalid_configs:
                debug_callback("INVALID CONFIGURATIONS:", color_type=7)
                debug_callback("=" * 60)
                for invalid in invalid_configs:
                    error_msg = f"[{invalid['index']}] {invalid['name']}: {', '.join(invalid['errors'])}"
                    debug_callback(error_msg, color_type=7)
            else:
                debug_callback("ALL CONFIGURATIONS VALID!", color_type=6)
                debug_callback("=" * 60)
            debug_callback("")  # Add blank line at end to prevent last item from being cut off
        
        # Final summary in left window
        self.draw_validation_progress(len(models), len(models), "Complete", "", valid_count, len(invalid_configs), results)
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        time.sleep(3)
    
    def handle_config_option_enigma(self, option: str):
        """Handle Enigma Cipher Options section"""
        # Map section options to original option numbers
        option_map = {
            '1': '12',  # Set Device
            '2': '1',   # Set Mode
            '3': '2',   # Set Rotor Set
            '4': '3',   # Set Rings (Ring Settings)
            '5': '4',   # Set Ring Position
            '6': '5',   # Set Pegboard
            '7': '7'    # Always Send Config Before Message
        }
        self.handle_config_option(option_map.get(option, option))
    
    def handle_config_option_webpage(self, option: str):
        """Handle WebPage Options section"""
        # Map section options to original option numbers
        option_map = {
            '1': '8',   # Set Word Group
            '2': '9',   # Set Character Delay
            '3': '14',  # Web Server
            '4': '13',  # Set Web Server Port
            '5': '15'   # Enable Slides
        }
        self.handle_config_option(option_map.get(option, option))
    
    def handle_config_option_kiosk(self, option: str):
        """Handle Enigma Touch Device Options section"""
        # Map section options to original option numbers
        option_map = {
            '1': '6',   # Set Museum Delay
            '2': '16',  # Lock Model
            '3': '17',  # Lock Rotor/Wheel
            '4': '18',  # Lock Ring
            '5': '19',  # Disable Auto-PowerOff
            '6': '20',  # Set Brightness
            '7': '21',  # Set Volume
            '8': '22'   # Set Screen Saver
        }
        self.handle_config_option(option_map.get(option, option))
    
    def handle_config_option(self, option: str):
        """Handle configuration option selection"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Get saved config values from file (not in-memory values)
        saved = self.controller.get_saved_config()
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        if option == '1':
            while True:
                self.show_message(0, 0, "Set Mode (e.g., I, M3, M4):")
                self.draw_debug_panel()
                self.refresh_all_panels()
                value = self.get_input(1, 0, "Mode: ", saved['config']['mode'])
                if not value:
                    break  # User cancelled
                if self.controller.set_mode(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Mode set successfully!")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
                    break  # Success, exit loop
                else:
                    # Error occurred - show message and loop back for retry
                    self.show_message(2, 0, "Error! Please re-enter mode.")
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)  # Show error message longer
        
        elif option == '2':
            while True:
                self.show_message(0, 0, "Set Rotor Set (e.g., A III IV I):")
                self.draw_debug_panel()
                self.refresh_all_panels()
                value = self.get_input(1, 0, "Rotor Set: ", saved['config']['rotor_set'])
                if not value:
                    break  # User cancelled
                if self.controller.set_rotor_set(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Rotor set configured successfully!")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
                    break  # Success, exit loop
                else:
                    # Error occurred - show message and loop back for retry
                    self.show_message(2, 0, "Error! Please re-enter rotor set.")
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)  # Show error message longer
        
        elif option == '3':
            while True:
                self.show_message(0, 0, "Set Ring Settings (e.g., 01 01 01 or A B C):")
                self.draw_debug_panel()
                self.refresh_all_panels()
                value = self.get_input(1, 0, "Ring Settings: ", saved['config']['ring_settings'])
                if not value:
                    break  # User cancelled
                if self.controller.set_ring_settings(value, debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Ring settings configured successfully!")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
                    break  # Success, exit loop
                else:
                    # Error occurred - show message and loop back for retry
                    self.show_message(2, 0, "Error! Please re-enter ring settings.")
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)  # Show error message longer
        
        elif option == '4':
            while True:
                self.show_message(0, 0, "Set Ring Position (e.g., 20 6 10 or A B C):")
                self.draw_debug_panel()
                self.refresh_all_panels()
                value = self.get_input(1, 0, "Ring Position: ", saved['config']['ring_position'])
                if not value:
                    break  # User cancelled
                if self.controller.set_ring_position(value, debug_callback=debug_callback):
                    # Save config with new ring position (don't preserve old value)
                    self.controller.save_config(preserve_ring_position=False)
                    self.show_message(2, 0, "Ring position set successfully!")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
                    break  # Success, exit loop
                else:
                    # Error occurred - show message and loop back for retry
                    self.show_message(2, 0, "Error! Please re-enter ring position.")
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)  # Show error message longer
        
        elif option == '5':
            while True:
                self.show_message(0, 0, "Set Pegboard (e.g., VF PQ or leave empty for clear):")
                self.draw_debug_panel()
                self.refresh_all_panels()
                value = self.get_input(1, 0, "Pegboard: ", saved['config']['pegboard'])
                # Empty value is allowed for pegboard (means 'clear')
                if self.controller.set_pegboard(value if value else '', debug_callback=debug_callback):
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, "Pegboard configured successfully!")
                    self.draw_settings_panel()  # Update settings display
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(1)
                    break  # Success, exit loop
                else:
                    # Error occurred - show message and loop back for retry
                    self.show_message(2, 0, "Error! Please re-enter plugboard.")
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)  # Show error message longer
                    # Continue loop to retry
        
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
            # Save config with preserve_always_send_config=False to save the new value
            self.controller.save_config(preserve_always_send_config=False)  # Save config after change
            status = str(self.controller.always_send_config).lower()
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
                self.show_message(0, 0, "Web server: false", curses.A_BOLD)
                self.draw_settings_panel()  # Update settings display
            else:
                # Currently disabled - enable it
                self.controller.web_server_enabled = True
                self.controller.save_config()
                port = self.controller.web_server_port
                self.show_message(0, 0, f"Web server: true (port {port})", curses.A_BOLD)
                self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '15':
            # Toggle enable_slides
            current_enabled = saved.get('enable_slides', False)
            self.controller.enable_slides = not current_enabled
            self.controller.save_config()  # Save config after change
            status = str(self.controller.enable_slides).lower()
            self.show_message(0, 0, f"Enable Slides: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '16':
            # Toggle lock_model
            current_locked = saved.get('lock_model', True)
            self.controller.lock_model = not current_locked
            self.controller.save_config()  # Save config after change
            status = str(self.controller.lock_model).lower()
            self.show_message(0, 0, f"Lock Model: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '17':
            # Toggle lock_rotor
            current_locked = saved.get('lock_rotor', True)
            self.controller.lock_rotor = not current_locked
            self.controller.save_config()  # Save config after change
            status = str(self.controller.lock_rotor).lower()
            self.show_message(0, 0, f"Lock Rotor/Wheel: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '18':
            # Toggle lock_ring
            current_locked = saved.get('lock_ring', True)
            self.controller.lock_ring = not current_locked
            self.controller.save_config()  # Save config after change
            status = str(self.controller.lock_ring).lower()
            self.show_message(0, 0, f"Lock Ring: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '19':
            # Toggle disable_power_off
            current_disabled = saved.get('disable_power_off', True)
            self.controller.disable_power_off = not current_disabled
            self.controller.save_config()  # Save config after change
            status = str(self.controller.disable_power_off).lower()
            self.show_message(0, 0, f"Disable Power-Off: {status}")
            self.draw_settings_panel()  # Update settings display
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(1)
        
        elif option == '20':
            # Set brightness (1-5)
            self.show_message(0, 0, f"Set Brightness (current: {saved.get('brightness', 3)}, range: 1-5):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Brightness (1-5): ", str(saved.get('brightness', 3)))
            try:
                brightness = int(value)
                if brightness < 1 or brightness > 5:
                    self.show_message(2, 0, "Invalid brightness! Must be 1-5")
                else:
                    self.controller.brightness = brightness
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, f"Brightness set to {brightness}")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            except:
                self.show_message(2, 0, "Invalid brightness value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '21':
            # Set volume (0-6)
            self.show_message(0, 0, f"Set Volume (current: {saved.get('volume', 0)}, range: 0-6):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Volume (0-6): ", str(saved.get('volume', 0)))
            try:
                volume = int(value)
                if volume < 0 or volume > 6:
                    self.show_message(2, 0, "Invalid volume! Must be 0-6")
                else:
                    self.controller.volume = volume
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, f"Volume set to {volume}")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            except:
                self.show_message(2, 0, "Invalid volume value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '22':
            # Set screen_saver (0-99)
            self.show_message(0, 0, f"Set Screen Saver (current: {saved.get('screen_saver', 0)}, range: 0-99):")
            self.draw_debug_panel()
            self.refresh_all_panels()
            value = self.get_input(1, 0, "Screen Saver (0-99): ", str(saved.get('screen_saver', 0)))
            try:
                screen_saver = int(value)
                if screen_saver < 0 or screen_saver > 99:
                    self.show_message(2, 0, "Invalid screen saver! Must be 0-99")
                else:
                    self.controller.screen_saver = screen_saver
                    self.controller.save_config()  # Save config after change
                    self.show_message(2, 0, f"Screen Saver set to {screen_saver}")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
            except:
                self.show_message(2, 0, "Invalid screen saver value!")
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(1)
        
        elif option == '23':
            # Validate Models.json
            self.validate_models_json(debug_callback=debug_callback)
        
        elif option == '24':
            # Toggle use_models_json - use controller's current value
            self.controller.use_models_json = not getattr(self.controller, 'use_models_json', False)
            # Save config after change
            self.controller.save_config()
            status = str(self.controller.use_models_json).lower()
            self.show_message(0, 0, f"Use models.json when generating: {status}")
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
        
        # Check if use_models_json is enabled
        saved = self.controller.get_saved_config()
        use_models_json = saved.get('use_models_json', False)
        models = None
        
        if use_models_json:
            # Load models.json
            models_file = os.path.join(SCRIPT_DIR, 'models.json')
            if not os.path.exists(models_file):
                self.show_message(0, 0, f"Error: models.json not found at {models_file}", curses.A_BOLD)
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(2)
                return
            
            try:
                with open(models_file, 'r', encoding='utf-8') as f:
                    models = json.load(f)
                if not isinstance(models, list) or len(models) == 0:
                    self.show_message(0, 0, "Error: models.json must contain a non-empty array", curses.A_BOLD)
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)
                    return
            except json.JSONDecodeError as e:
                self.show_message(0, 0, f"Error: Invalid JSON in models.json: {e}", curses.A_BOLD)
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(2)
                return
            except Exception as e:
                self.show_message(0, 0, f"Error: Failed to read models.json: {e}", curses.A_BOLD)
                self.draw_debug_panel()
                self.refresh_all_panels()
                time.sleep(2)
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
        # Note: saved was already loaded above
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
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        def position_update_callback():
            """Update settings panel when ring positions change"""
            self.draw_settings_panel()
            self.refresh_all_panels()
        
        # Save original always_send_config value - we'll disable it during message generation
        # to prevent sending default config settings that would overwrite message-specific settings
        original_always_send_config = self.controller.always_send_config
        self.controller.always_send_config = False
        
        # Set flag to skip delays during message generation
        self.controller.generating_messages = True
        if debug_callback:
            debug_callback(f"Message generation mode: delays will be skipped")
        
        # Apply kiosk/lock settings and logging format once at the start
        # This ensures the device is properly configured before generating messages
        if debug_callback:
            debug_callback("Applying kiosk/lock settings and logging format...")
        self.controller.wakeup_device(debug_callback=debug_callback)
        config_errors = []
        if not self.controller.apply_kiosk_settings(debug_callback=debug_callback):
            config_errors.append("kiosk_settings")
        
        if config_errors:
            error_msg = f"Configuration errors detected: {', '.join(config_errors)}"
            if debug_callback:
                debug_callback(f"ERROR: {error_msg}", color_type=7)
            self.setup_screen()
            self.draw_settings_panel()
            self.left_win.clear()
            self.left_win.addstr(0, 0, "Configuration Error!", curses.A_BOLD | curses.A_REVERSE)
            self.left_win.addstr(1, 0, error_msg)
            self.left_win.addstr(2, 0, "")
            self.left_win.addstr(3, 0, "Switching to configuration menu...")
            self.left_win.addstr(4, 0, "Press any key to continue...")
            self.left_win.refresh()
            self.draw_debug_panel()
            self.refresh_all_panels()
            self.stdscr.getch()
            self.config_menu()
            # Clear generation flag before returning
            self.controller.generating_messages = False
            # Restore original always_send_config value
            self.controller.always_send_config = original_always_send_config
            return
        
        # Process each message
        
        for i in range(start_index, message_count):
            message = messages[i]
            
            # If use_models_json is enabled, pick a random model for this message
            message_settings = None
            selected_model = None
            model_index = None
            if use_models_json and models:
                # Pick a random model from models.json
                model_index = random.randint(0, len(models) - 1)
                selected_model = models[model_index]
                message_settings = {
                    'MODEL': selected_model.get('MODEL', ''),
                    'ROTOR': selected_model.get('ROTOR', ''),
                    'RINGSET': selected_model.get('RINGSET', ''),
                    'RINGPOS': selected_model.get('RINGPOS', ''),
                    'PLUG': selected_model.get('PLUG', ''),
                    'GROUP': saved['word_group_size']  # Use saved word_group_size
                }
                if debug_callback:
                    model_name = selected_model.get('name', 'Unknown')
                    model_desc = selected_model.get('description', '')
                    debug_callback(f"Using model {model_index + 1}/{len(models)}: {model_name}")
                    if model_desc:
                        debug_callback(f"  Description: {model_desc}")
                    debug_callback(f"  Configuration: MODEL={message_settings['MODEL']}, ROTOR={message_settings['ROTOR']}, RINGSET={message_settings['RINGSET']}, RINGPOS={message_settings['RINGPOS']}, PLUG={message_settings['PLUG'] if message_settings['PLUG'] else '(none)'}")
            else:
                # Use saved config settings
                message_settings = current_settings.copy()
            
            # Update progress display
            self.left_win.clear()
            max_y, max_x = self.left_win.getmaxyx()
            self.left_win.addstr(0, 0, f"Generating Coded Messages - {language}", curses.A_BOLD)
            self.left_win.addstr(1, 0, f"Progress: {i+1}/{message_count}")
            
            y_pos = 2
            if use_models_json and models and selected_model:
                model_name = selected_model.get('name', 'Unknown')
                model_desc = selected_model.get('description', '')
                # Show model info prominently
                if y_pos < max_y:
                    self.left_win.addstr(y_pos, 0, f"Using Model [{model_index + 1}/{len(models)}]:", curses.A_BOLD)
                    y_pos += 1
                if y_pos < max_y:
                    self.left_win.addstr(y_pos, 0, f"  {model_name[:max_x-2]}")
                    y_pos += 1
                if model_desc and y_pos < max_y:
                    desc_line = f"  {model_desc[:max_x-2]}"
                    self.left_win.addstr(y_pos, 0, desc_line[:max_x], curses.A_DIM)
                    y_pos += 1
                if y_pos < max_y:
                    config_line = f"  MODEL: {message_settings['MODEL']} | ROTOR: {message_settings['ROTOR'][:max_x-30]}"
                    self.left_win.addstr(y_pos, 0, config_line[:max_x])
                    y_pos += 1
                if y_pos < max_y:
                    config_line2 = f"  RINGSET: {message_settings['RINGSET']} | RINGPOS: {message_settings['RINGPOS']}"
                    self.left_win.addstr(y_pos, 0, config_line2[:max_x])
                    y_pos += 1
                if y_pos < max_y:
                    plug_text = message_settings['PLUG'] if message_settings['PLUG'] else '(none)'
                    plug_line = f"  PLUG: {plug_text[:max_x-8]}"
                    self.left_win.addstr(y_pos, 0, plug_line[:max_x])
                    y_pos += 1
                if y_pos < max_y:
                    self.left_win.addstr(y_pos, 0, "-" * max_x)
                    y_pos += 1
                # Show message being processed
                if y_pos < max_y:
                    msg_line = f"Processing message {i+1}: {message[:max_x-25] if len(message) > max_x-25 else message}"
                    self.left_win.addstr(y_pos, 0, msg_line[:max_x])
                    y_pos += 1
                if y_pos < max_y:
                    self.left_win.addstr(y_pos, 0, "-" * max_x)
                    y_pos += 1
                display_start_y = y_pos
            else:
                if y_pos < max_y:
                    self.left_win.addstr(y_pos, 0, f"Processing message {i+1}: {message[:max_x-20] if len(message) > max_x-20 else message}")
                    y_pos += 1
                if y_pos < max_y:
                    self.left_win.addstr(y_pos, 0, "-" * max_x)
                    y_pos += 1
                display_start_y = y_pos
            
            # Show already encoded messages
            if coded_messages:
                self.left_win.addstr(display_start_y, 0, "Encoded so far:")
                display_y = display_start_y + 1
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
            
            # Wake up device first
            self.controller.wakeup_device(debug_callback=debug_callback)
            
            # Apply Enigma settings (mode, rotors, rings, pegboard)
            # Note: Kiosk/lock settings are NOT sent automatically - use menu option 6 to set them
            if debug_callback:
                debug_callback("Applying Enigma settings...")
            config_errors = []
            if not self.controller.set_mode(message_settings['MODEL'], debug_callback=debug_callback):
                config_errors.append("mode")
            time.sleep(0.2)
            
            if not self.controller.set_rotor_set(message_settings['ROTOR'], debug_callback=debug_callback):
                config_errors.append("rotor_set")
            time.sleep(0.2)
            if not self.controller.set_ring_settings(message_settings['RINGSET'], debug_callback=debug_callback):
                config_errors.append("ring_settings")
            time.sleep(0.2)
            if not self.controller.set_ring_position(message_settings['RINGPOS'], debug_callback=debug_callback):
                config_errors.append("ring_position")
            time.sleep(0.2)
            if not self.controller.set_pegboard(message_settings['PLUG'], debug_callback=debug_callback):
                config_errors.append("pegboard")
            time.sleep(0.2)
            
            # If any config errors occurred, notify user and switch to config menu
            if config_errors:
                error_msg = f"Configuration errors detected: {', '.join(config_errors)}"
                if debug_callback:
                    debug_callback(f"ERROR: {error_msg}", color_type=7)  # COLOR_MISMATCH (red)
                self.setup_screen()
                self.draw_settings_panel()
                self.left_win.clear()
                self.left_win.addstr(0, 0, "Configuration Error!", curses.A_BOLD | curses.A_REVERSE)
                self.left_win.addstr(1, 0, error_msg)
                self.left_win.addstr(2, 0, "")
                self.left_win.addstr(3, 0, "Switching to configuration menu...")
                self.left_win.addstr(4, 0, "Press any key to continue...")
                self.left_win.refresh()
                self.draw_debug_panel()
                self.refresh_all_panels()
                self.stdscr.getch()
                self.config_menu()
                # After returning from config menu, stop generation
                # Clear generation flag and restore always_send_config before breaking
                self.controller.generating_messages = False
                self.controller.always_send_config = original_always_send_config
                break
            
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
            # Use Message Interactive mode (expects lowercase) for generating coded files
            success = self.controller.send_message(message, progress_callback, debug_callback, position_update_callback, expect_lowercase_response=True)
            
            if success and encoded_chars:
                encoded_result = ''.join(encoded_chars)
                # Ensure we have a valid string before creating message object
                if encoded_result and isinstance(encoded_result, str):
                    # Use the initial ring position from message_settings (set before encoding started)
                    # This is the starting position used for encoding, not the final position after encoding
                    initial_ring_pos = message_settings['RINGPOS']
                    if debug_callback:
                        debug_callback(f"Using initial ring position: {initial_ring_pos} (from message settings)")
                    
                    # Create message object with all metadata
                    # Use message_settings which contains either the random model settings
                    # or the current_settings depending on use_models_json
                    message_obj = {
                        'MSG': message,
                        'MODEL': message_settings['MODEL'],
                        'ROTOR': message_settings['ROTOR'],
                        'RINGSET': message_settings['RINGSET'],
                        'RINGPOS': initial_ring_pos,  # Use initial position (starting position used for encoding)
                        'PLUG': message_settings['PLUG'],
                        'GROUP': message_settings['GROUP'],
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
        
        # Restore original always_send_config value
        self.controller.always_send_config = original_always_send_config
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
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        def position_update_callback():
            """Update settings panel when ring positions change"""
            self.draw_settings_panel()
            self.refresh_all_panels()
        
        def mode_update_callback():
            """Update settings panel when function mode changes"""
            self.draw_settings_panel()
            self.refresh_all_panels()
        
        config_error_occurred = [False]
        config_error_details = [None]
        
        def config_error_callback(errors):
            """Handle config errors by notifying user and preparing to switch to config menu"""
            config_error_occurred[0] = True
            config_error_details[0] = errors
            error_msg = f"Configuration error detected: {', '.join(errors)}. Please check your settings."
            self.show_message(y + 1, 0, error_msg, curses.A_BOLD | curses.A_REVERSE)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Explicitly use Message Interactive mode (expects lowercase) for manual messages from UI
        success = self.controller.send_message(message, progress_callback, debug_callback, position_update_callback, config_error_callback, expect_lowercase_response=True, mode_update_callback=mode_update_callback)
        
        # Update settings panel after message sending (mode may have changed)
        self.draw_settings_panel()
        self.refresh_all_panels()
        
        # If config error occurred, switch to config menu
        if config_error_occurred[0]:
            self.show_message(y + 2, 0, "Switching to configuration menu...", curses.A_BOLD)
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            self.config_menu()
            return
        
        # Only show results if message was sent successfully
        if not success:
            return
        
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
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        settings = self.controller.get_all_settings(debug_callback=debug_callback)
        
        # Update controller config with queried settings
        self.controller.config.update(settings)
        
        self.setup_screen()
        self.draw_settings_panel()  # Update top panel with new settings
        
        self.show_message(0, 0, "Current Settings:", curses.A_BOLD | curses.A_UNDERLINE)
        
        y = 1
        # Enigma Configuration
        self.show_message(y, 0, "Enigma Configuration:", curses.A_BOLD)
        y += 1
        self.show_message(y, 0, f"  Mode: {settings.get('mode', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"  Rotor Set: {settings.get('rotor_set', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"  Ring Settings: {settings.get('ring_settings', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"  Ring Position: {settings.get('ring_position', 'N/A')}")
        y += 1
        self.show_message(y, 0, f"  Plugboard: {settings.get('pegboard', 'N/A') or 'clear'}")
        y += 1
        
        # Lock Settings
        self.show_message(y, 0, "Lock Settings:", curses.A_BOLD)
        y += 1
        lock_model = settings.get('lock_model', 'N/A')
        lock_model_str = 'locked' if lock_model is True else ('unlocked' if lock_model is False else 'N/A')
        self.show_message(y, 0, f"  Model: {lock_model_str}")
        y += 1
        lock_rotor = settings.get('lock_rotor', 'N/A')
        lock_rotor_str = 'locked' if lock_rotor is True else ('unlocked' if lock_rotor is False else 'N/A')
        self.show_message(y, 0, f"  Rotor/Wheel: {lock_rotor_str}")
        y += 1
        lock_ring = settings.get('lock_ring', 'N/A')
        lock_ring_str = 'locked' if lock_ring is True else ('unlocked' if lock_ring is False else 'N/A')
        self.show_message(y, 0, f"  Ring: {lock_ring_str}")
        y += 1
        lock_power = settings.get('disable_power_off', 'N/A')
        lock_power_str = 'disabled' if lock_power is True else ('enabled' if lock_power is False else 'N/A')
        self.show_message(y, 0, f"  Power-Off Button: {lock_power_str}")
        y += 1
        
        # UI Settings
        self.show_message(y, 0, "UI Settings:", curses.A_BOLD)
        y += 1
        brightness = settings.get('brightness', 'N/A')
        self.show_message(y, 0, f"  Brightness: {brightness if brightness != 'N/A' else 'N/A'} (1-5)")
        y += 1
        volume = settings.get('volume', 'N/A')
        self.show_message(y, 0, f"  Volume: {volume if volume != 'N/A' else 'N/A'} (0-6)")
        y += 1
        logging_format = settings.get('logging_format')
        if logging_format is not None:
            format_desc = {1: 'short/5', 2: 'short/4', 3: 'extended/5', 4: 'extended/4'}.get(logging_format, f'{logging_format}')
            self.show_message(y, 0, f"  Logging Format: {format_desc}")
        else:
            self.show_message(y, 0, "  Logging Format: N/A")
        y += 1
        
        # Timeout Settings
        self.show_message(y, 0, "Timeout Settings:", curses.A_BOLD)
        y += 1
        timeout_battery = settings.get('timeout_battery', 'N/A')
        if timeout_battery == 0:
            timeout_battery_str = 'disabled'
        elif timeout_battery != 'N/A':
            timeout_battery_str = f'{timeout_battery} minutes'
        else:
            timeout_battery_str = 'N/A'
        self.show_message(y, 0, f"  Battery Power-Off: {timeout_battery_str}")
        y += 1
        timeout_plugged = settings.get('timeout_plugged', 'N/A')
        if timeout_plugged == 0:
            timeout_plugged_str = 'disabled'
        elif timeout_plugged != 'N/A':
            timeout_plugged_str = f'{timeout_plugged} minutes'
        else:
            timeout_plugged_str = 'N/A'
        self.show_message(y, 0, f"  Plugged-In Power-Off: {timeout_plugged_str}")
        y += 1
        timeout_screen_saver = settings.get('screen_saver', 'N/A')
        if timeout_screen_saver == 0:
            timeout_screen_saver_str = 'disabled'
        elif timeout_screen_saver != 'N/A':
            timeout_screen_saver_str = f'{timeout_screen_saver} minutes'
        else:
            timeout_screen_saver_str = 'N/A'
        self.show_message(y, 0, f"  Screen Saver: {timeout_screen_saver_str}")
        y += 1
        timeout_setup_modes = settings.get('timeout_setup_modes', 'N/A')
        if timeout_setup_modes == 0:
            timeout_setup_modes_str = 'disabled'
        elif timeout_setup_modes != 'N/A':
            timeout_setup_modes_str = f'{timeout_setup_modes} seconds'
        else:
            timeout_setup_modes_str = 'N/A'
        self.show_message(y, 0, f"  Setup Mode Inactivity: {timeout_setup_modes_str}")
        
        self.draw_debug_panel()
        
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            self.show_message(max_y - 1, 0, "Press any key to continue...")
        
        self.refresh_all_panels()
        self.stdscr.getch()
    
    def set_enigma_config_screen(self):
        """Set Enigma configuration settings from saved config file"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Reload config from file to ensure we use saved defaults, not current state
        # Preserve device to avoid changing it during operation
        self.controller.load_config(preserve_device=True)
        
        self.show_message(0, 0, "Setting Enigma configuration from saved config...", curses.A_BOLD)
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Wake up device first
        self.controller.wakeup_device(debug_callback=debug_callback)
        
        # Get saved config values (from file, not in-memory)
        saved = self.controller.get_saved_config()
        
        config_errors = []
        if not self.controller.set_mode(saved['config']['mode'], debug_callback=debug_callback):
            config_errors.append("mode")
        time.sleep(0.2)
        if not self.controller.set_rotor_set(saved['config']['rotor_set'], debug_callback=debug_callback):
            config_errors.append("rotor_set")
        time.sleep(0.2)
        if not self.controller.set_ring_settings(saved['config']['ring_settings'], debug_callback=debug_callback):
            config_errors.append("ring_settings")
        time.sleep(0.2)
        if not self.controller.set_ring_position(saved['config']['ring_position'], debug_callback=debug_callback):
            config_errors.append("ring_position")
        time.sleep(0.2)
        if not self.controller.set_pegboard(saved['config']['pegboard'], debug_callback=debug_callback):
            config_errors.append("pegboard")
        time.sleep(0.2)
        self.controller.return_to_encode_mode(debug_callback=debug_callback)
        
        self.setup_screen()
        self.draw_settings_panel()  # Update settings display
        
        if config_errors:
            error_msg = f"Configuration errors detected: {', '.join(config_errors)}"
            self.show_message(0, 0, error_msg, curses.A_BOLD | curses.A_REVERSE)
            self.show_message(1, 0, "Switching to configuration menu...", curses.A_BOLD)
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            self.config_menu()
            return
        else:
            self.show_message(0, 0, "Enigma configuration set successfully!", curses.A_BOLD)
        
        self.draw_debug_panel()
        self.refresh_all_panels()
        self.show_message(2, 0, "Press any key to continue...")
        self.refresh_all_panels()
        self.stdscr.getch()
    
    def set_kiosk_lock_config_screen(self):
        """Set Kiosk/Lock configuration settings from saved config file"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Reload config from file to ensure we use saved defaults, not current state
        # Preserve device to avoid changing it during operation
        self.controller.load_config(preserve_device=True)
        
        self.show_message(0, 0, "Setting Kiosk/Lock configuration from saved config...", curses.A_BOLD)
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Wake up device first
        self.controller.wakeup_device(debug_callback=debug_callback)
        
        # Apply kiosk/demo settings (locks, UI, timeouts)
        config_errors = []
        if not self.controller.apply_kiosk_settings(debug_callback=debug_callback):
            config_errors.append("kiosk_settings")
        
        self.setup_screen()
        self.draw_settings_panel()  # Update settings display
        
        if config_errors:
            error_msg = f"Configuration errors detected: {', '.join(config_errors)}"
            self.show_message(0, 0, error_msg, curses.A_BOLD | curses.A_REVERSE)
            self.show_message(1, 0, "Switching to configuration menu...", curses.A_BOLD)
            self.draw_debug_panel()
            self.refresh_all_panels()
            time.sleep(2)
            self.config_menu()
            return
        else:
            self.show_message(0, 0, "Kiosk/Lock configuration set successfully!", curses.A_BOLD)
        
        self.draw_debug_panel()
        
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            self.show_message(max_y - 1, 0, "Press any key to continue...")
        
        self.refresh_all_panels()
        self.stdscr.getch()
    
    def factory_reset_enigma_screen(self):
        """Factory reset the Enigma Touch device"""
        self.setup_screen()
        self.draw_settings_panel()
        
        # Track current Y position for scrolling messages
        current_y = 0
        
        if not self.controller.is_connected():
            self.show_message(current_y, 0, "ERROR: Not connected to device", curses.A_BOLD | curses.color_pair(self.COLOR_MISMATCH))
            current_y += 1
            self.draw_debug_panel()
            self.refresh_all_panels()
            win = self.get_active_window()
            if win:
                max_y, max_x = win.getmaxyx()
                self.show_message(max_y - 1, 0, "Press any key to continue...")
            self.stdscr.getch()
            return
        
        # Confirm factory reset
        self.show_message(current_y, 0, "WARNING: This will factory reset the Enigma Touch device!", curses.A_BOLD | curses.color_pair(self.COLOR_MISMATCH))
        current_y += 1
        self.show_message(current_y, 0, "All settings will be reset to factory defaults.", curses.A_BOLD)
        current_y += 1
        self.show_message(current_y, 0, "Press Y to confirm, any other key to cancel:")
        current_y += 1
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        key = self.stdscr.getch()
        if key != ord('y') and key != ord('Y'):
            # Clear and redraw for cancellation message
            self.setup_screen()
            self.draw_settings_panel()
            current_y = 0
            self.show_message(current_y, 0, "Factory reset cancelled.", curses.A_BOLD)
            current_y += 1
            self.draw_debug_panel()
            self.refresh_all_panels()
            win = self.get_active_window()
            if win:
                max_y, max_x = win.getmaxyx()
                self.show_message(max_y - 1, 0, "Press any key to continue...")
            self.stdscr.getch()
            return
        
        # Clear and redraw for sending command
        self.setup_screen()
        self.draw_settings_panel()
        current_y = 0
        
        def debug_callback(msg, color_type=None):
            self.add_debug_output(msg, color_type=color_type)
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Send factory reset command
        self.show_message(current_y, 0, "Sending factory reset command...", curses.A_BOLD)
        current_y += 1
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        # Send line return, then !RS command with line return
        self.controller.ser.write(b'\r\n')
        self.controller.ser.flush()
        time.sleep(0.1)
        
        response = self.controller.send_command(b'!RS\r\n', debug_callback=debug_callback)
        
        if response is None:
            self.show_message(current_y, 0, "ERROR: No response from device", curses.A_BOLD | curses.color_pair(self.COLOR_MISMATCH))
            current_y += 1
        else:
            has_error, error_message = self.controller._has_error_response(response)
            if has_error:
                self.show_message(current_y, 0, f"ERROR: {error_message}", curses.A_BOLD | curses.color_pair(self.COLOR_MISMATCH))
                current_y += 1
            else:
                self.show_message(current_y, 0, "Factory reset command sent successfully!", curses.A_BOLD)
                current_y += 1
        
        self.draw_debug_panel()
        self.refresh_all_panels()
        
        win = self.get_active_window()
        if win:
            max_y, max_x = win.getmaxyx()
            self.show_message(max_y - 1, 0, "Press any key to continue...")
        
        self.stdscr.getch()
    
    def museum_mode_screen(self):
        """Museum mode selection"""
        options = [
            ("1", "Encode - EN"),
            ("2", "Decode - EN"),
            ("3", "Encode - DE"),
            ("4", "Decode - DE"),
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
            elif key >= ord('1') and key <= ord('4'):
                self.run_museum_mode(chr(key))
    
    def run_museum_mode(self, mode: str):
        """Run museum mode"""
        # Save original always_send_config value - we'll disable it during museum mode
        # since we're setting config from JSON message objects, not from defaults
        original_always_send_config = self.controller.always_send_config
        self.controller.always_send_config = False
        
        # Determine operation mode (encode or decode)
        is_encode = mode in ('1', '3')
        
        if mode == '1':
            mode_name = 'Encode - EN'
            json_file = os.path.join(SCRIPT_DIR, 'english-encoded.json')
        elif mode == '2':
            mode_name = 'Decode - EN'
            json_file = os.path.join(SCRIPT_DIR, 'english-encoded.json')
        elif mode == '3':
            mode_name = 'Encode - DE'
            json_file = os.path.join(SCRIPT_DIR, 'german-encoded.json')
        elif mode == '4':
            mode_name = 'Decode - DE'
            json_file = os.path.join(SCRIPT_DIR, 'german-encoded.json')
        else:
            # Restore original value before returning
            self.controller.always_send_config = original_always_send_config
            return
        
        # Set function mode first so it's displayed in the top panel
        self.controller.function_mode = mode_name
        # Save function mode to config file, but preserve cipher config (museum mode changes cipher settings per message)
        self.controller.save_config(preserve_cipher_config=True)
        
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
            # Restore original always_send_config value before returning
            self.controller.always_send_config = original_always_send_config
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
            # Restore original always_send_config value before returning
            self.controller.always_send_config = original_always_send_config
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
            f"Museum Mode: {self.controller.function_mode}" + (" [SIMULATION]" if self.simulate_mode else ""),
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
        
        # Track disconnection state
        device_disconnected = [False]  # Use list to allow modification in nested functions
        
        # Track slide information
        current_message_index = [None]  # Index of current message in valid_messages
        current_slide_number = [1]  # Current slide number (1.png, 2.png, etc.)
        previous_slide_number = [0]  # Previous slide number to detect changes
        
        def draw_screen():
            """Draw the entire screen with header and log messages"""
            # Use current function_mode (may have changed to 'Interactive' if user input detected)
            # Only set to mode_name if still in museum mode
            if self.controller.function_mode.startswith(('Encode', 'Decode')):
                # Still in museum mode, use mode_name
                self.controller.function_mode = mode_name
            # Otherwise, function_mode is already 'Interactive', keep it
            self.setup_screen()
            self.draw_settings_panel()  # This will display the current function mode
            
            # Get fresh window dimensions after setup_screen() may have recreated windows
            current_win = self.get_active_window()
            if not current_win:
                # Window not ready yet, skip drawing
                return
            try:
                current_max_y, current_max_x = current_win.getmaxyx()
            except Exception:
                # Window might not be fully initialized, skip drawing
                return
            
            # Generate header lines dynamically based on current function mode
            current_header_lines = [
                f"Museum Mode: {self.controller.function_mode}",
                f"Delay: {self.controller.museum_delay} seconds",
                "Press Q to stop"
            ]
            
            # Recalculate log_start_y based on current header height
            current_header_height = len(current_header_lines)
            current_log_start_y = current_header_height
            
            # Draw header lines
            for i, line in enumerate(current_header_lines):
                if i < current_max_y:
                    attr = curses.A_BOLD if i == 0 else curses.A_NORMAL
                    self.show_message(i, 0, line[:current_max_x], attr)
            
            # Draw log messages (scrollable)
            # Show most recent messages that fit
            available_lines = current_max_y - current_log_start_y
            messages_to_show = log_messages[-available_lines:] if len(log_messages) > available_lines else log_messages
            
            for i, log_msg in enumerate(messages_to_show):
                y = current_log_start_y + i
                if y < current_max_y:
                    # Display full message (show_message will handle truncation for display)
                    # Full message is stored in log_messages for web interface
                    self.show_message(y, 0, log_msg)
            
            self.draw_debug_panel()
            self.refresh_all_panels()
        
        # Track if screen is ready for drawing
        screen_ready = [False]
        
        def add_log_message(msg: str, redraw: bool = True):
            """Add a message to the log and optionally redraw"""
            log_messages.append(msg)
            # Keep only last max_log_lines messages
            try:
                if len(log_messages) > max_log_lines:
                    log_messages.pop(0)
            except (NameError, UnboundLocalError):
                # max_log_lines might not be defined yet, just keep all messages for now
                pass
            # Only redraw if screen is ready and redraw is requested
            if redraw and screen_ready[0]:
                try:
                    draw_screen()
                except Exception:
                    # If draw_screen fails, just skip drawing
                    # The message is still added to log_messages
                    pass
        
        # Note: Kiosk/lock settings are NOT applied automatically in museum mode
        # Use menu option 6 "Send Enigma Lock Config" to set them manually
        
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
            # Always check actual connection status, don't rely on flag alone
            try:
                device_connected = self.controller.is_connected()
                # Update flag if connection status changed
                if device_connected and device_disconnected[0]:
                    # Device reconnected - flag will be cleared in main loop
                    pass
                elif not device_connected and not device_disconnected[0]:
                    # Device just disconnected - flag will be set in main loop
                    pass
            except Exception:
                device_connected = False
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
                'slide_path': slide_path,  # Path to current slide image
                'device_connected': device_connected if not self.simulate_mode else True,  # USB connection status (always True in simulation)
                'device_disconnected_message': None if (device_connected or self.simulate_mode) else "Enigma Touch disconnected - museum mode paused",  # Disconnection message
                'last_char_original': self.controller.last_char_original.upper() if self.controller.last_char_original else None,  # Last character received/input (uppercase)
                'last_char_received': self.controller.last_char_received.upper() if self.controller.last_char_received else None,  # Last character encoded/output (uppercase)
                'simulate_mode': self.simulate_mode  # Simulation mode indicator
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
        
        # Mark screen as ready and draw initial screen (will display all log messages)
        screen_ready[0] = True
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
            
            # Check USB connection status
            if device_disconnected[0]:
                # Device is disconnected - attempt to reconnect
                try:
                    # Properly disconnect first to release serial port lock
                    self.controller.disconnect()
                    time.sleep(0.5)  # Brief delay to ensure port is released
                    
                    if self.controller.connect():
                        # Reconnected successfully
                        device_disconnected[0] = False
                        museum_paused[0] = False
                        add_log_message("Device reconnected - restarting museum mode")
                        if debug_callback:
                            debug_callback("USB device reconnected - restarting museum mode", color_type=self.COLOR_MATCH)
                        draw_screen()
                        # Stop web server before restarting to ensure clean state
                        if web_server:
                            web_server.stop()
                            web_server = None
                            self.controller.web_server_ip = None
                            time.sleep(0.5)  # Brief delay to ensure web server fully stops
                        time.sleep(1)  # Brief pause before restart
                        # Restart museum mode by recursively calling with same mode
                        # Restore original always_send_config value before restarting
                        self.controller.always_send_config = original_always_send_config
                        # Recursive call to restart museum mode
                        self.run_museum_mode(mode)
                        # Exit current loop since we've restarted
                        break
                except Exception as e:
                    # Reconnection attempt failed, continue polling
                    if debug_callback:
                        debug_callback(f"Reconnection attempt failed: {e}")
                    # Ensure connection is properly closed on error
                    try:
                        self.controller.disconnect()
                    except Exception:
                        pass
                
                # Still disconnected - wait before next check
                time.sleep(1.5)  # Poll every 1.5 seconds
                continue  # Skip rest of loop iteration
            else:
                # Device should be connected - verify connection status
                try:
                    is_connected = self.controller.is_connected()
                    if not is_connected:
                        # Device just disconnected
                        device_disconnected[0] = True
                        museum_paused[0] = True
                        add_log_message("Enigma Touch disconnected - museum mode paused")
                        if debug_callback:
                            debug_callback("USB device disconnected - pausing museum mode", color_type=self.COLOR_MISMATCH)
                        draw_screen()
                        # Skip rest of loop iteration to enter reconnection polling
                        time.sleep(0.1)
                        continue
                except Exception as e:
                    # Exception checking connection - treat as disconnection
                    device_disconnected[0] = True
                    museum_paused[0] = True
                    add_log_message("Enigma Touch disconnected - museum mode paused")
                    if debug_callback:
                        debug_callback(f"USB connection error: {e} - pausing museum mode", color_type=self.COLOR_MISMATCH)
                    draw_screen()
                    # Skip rest of loop iteration to enter reconnection polling
                    time.sleep(0.1)
                    continue
            
            # Monitor for Interactive mode input from Enigma device
            if self.controller.function_mode == 'Interactive' and not device_disconnected[0]:
                if self.controller.ser and self.controller.ser.is_open:
                    try:
                        if self.controller.ser.in_waiting > 0:
                            # Read available data
                            response = b''
                            start_time = time.time()
                            silence_duration = 0.2
                            last_data_time = None
                            
                            # Read data with timeout
                            while time.time() - start_time < CHAR_TIMEOUT:
                                if self.controller.ser.in_waiting > 0:
                                    response += self.controller.ser.read(self.controller.ser.in_waiting)
                                    last_data_time = time.time()
                                    
                                    if b'Positions' in response:
                                        # Wait for silence to ensure complete response
                                        silence_start = time.time()
                                        while time.time() - silence_start < silence_duration:
                                            if self.controller.ser.in_waiting > 0:
                                                response += self.controller.ser.read(self.controller.ser.in_waiting)
                                                silence_start = time.time()
                                            time.sleep(0.01)
                                        break
                                    time.sleep(0.01)
                                else:
                                    if response and b'Positions' in response:
                                        if last_data_time and time.time() - last_data_time >= silence_duration:
                                            break
                                    time.sleep(0.01)
                            
                            # Final read of any remaining data
                            if self.controller.ser.in_waiting > 0:
                                time.sleep(0.1)
                                if self.controller.ser.in_waiting > 0:
                                    response += self.controller.ser.read(self.controller.ser.in_waiting)
                            
                            # Filter out config summary if present
                            if response:
                                response = self.controller._filter_config_summary(response, debug_callback=debug_callback)
                            
                            # Parse response if we have data
                            if response and b'Positions' in response:
                                try:
                                    resp_text = response.decode('ascii', errors='replace')
                                    resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                                    resp_text = ' '.join(resp_text.split()).strip()
                                    
                                    if debug_callback:
                                        debug_callback(f"<<< {resp_text}")
                                    
                                    parts = resp_text.split()
                                    
                                    # Get rotor count based on current model
                                    rotor_count = self.controller._get_rotor_count()
                                    
                                    # Look for pattern: "INPUT ENCODED Positions XX XX XX" (or XX XX XX XX for M4)
                                    # Need at least 2 + rotor_count parts after "positions"
                                    min_parts_needed = 2 + rotor_count
                                    for j in range(len(parts) - min_parts_needed):
                                        part1 = parts[j]
                                        part2 = parts[j+1]
                                        part3 = parts[j+2]
                                        
                                        if (len(part1) == 1 and part1.isalpha() and part1.isupper() and
                                            len(part2) == 1 and part2.isalpha() and part2.isupper() and
                                            part3.lower() == 'positions'):
                                            # Found Interactive mode input
                                            original_char = part1
                                            encoded_char = part2
                                            
                                            # Update controller's last character info
                                            # Ensure uppercase for Interactive mode display
                                            self.controller.last_char_original = original_char.upper() if original_char else None
                                            self.controller.last_char_received = encoded_char.upper() if encoded_char else None
                                            
                                            # Reset museum delay timer when Interactive mode input is received
                                            last_unexpected_input_time[0] = time.time()
                                            
                                            # Display in debug
                                            if debug_callback:
                                                debug_callback(f"Extra character received from Enigma - resetting museum delay timer")
                                                debug_callback(f">>> '{original_char}'")
                                                pos_info = ""
                                                # Parse positions using helper function (handles letters and numbers, 3 or 4 rotors)
                                                # Check if we have enough parts for positions (2 + rotor_count)
                                                if j + 2 + rotor_count <= len(parts):
                                                    positions = self.controller._parse_positions(parts, j + 3, rotor_count)
                                                    if positions:
                                                        # Format preserving original format (letters or numbers)
                                                        pos_str = self.controller._format_positions(parts, j + 3, rotor_count, positions)
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
                                                        
                                                        # Update ring position
                                                        self.controller.config['ring_position'] = pos_str
                                                debug_callback(f"<<< {original_char} {encoded_char}{pos_info}")
                                            
                                            # Update UI
                                            self.draw_settings_panel()
                                            self.refresh_all_panels()
                                            break
                                except Exception as e:
                                    if debug_callback:
                                        debug_callback(f"Error parsing Interactive mode input: {e}")
                    except Exception as e:
                        # Ignore read errors
                        pass
            
            # Monitor for device input when waiting between messages (not paused, not actively sending)
            # This allows detection of key touches during the waiting period
            if (not museum_paused[0] and 
                self.controller.function_mode.startswith(('Encode', 'Decode')) and 
                not device_disconnected[0] and
                current_time - last_message_time < self.controller.museum_delay):
                # We're in museum mode, waiting between messages - check for device input
                if self.controller.ser and self.controller.ser.is_open:
                    try:
                        if self.controller.ser.in_waiting > 0:
                            # Read available data to check for Interactive mode input
                            response = b''
                            start_time = time.time()
                            silence_duration = 0.2
                            last_data_time = None
                            
                            # Read data with timeout
                            while time.time() - start_time < CHAR_TIMEOUT:
                                if self.controller.ser.in_waiting > 0:
                                    response += self.controller.ser.read(self.controller.ser.in_waiting)
                                    last_data_time = time.time()
                                    
                                    if b'Positions' in response:
                                        # Wait for silence to ensure complete response
                                        silence_start = time.time()
                                        while time.time() - silence_start < silence_duration:
                                            if self.controller.ser.in_waiting > 0:
                                                response += self.controller.ser.read(self.controller.ser.in_waiting)
                                                silence_start = time.time()
                                            time.sleep(0.01)
                                        break
                                    time.sleep(0.01)
                                else:
                                    if response and b'Positions' in response:
                                        if last_data_time and time.time() - last_data_time >= silence_duration:
                                            break
                                    time.sleep(0.01)
                            
                            # Final read of any remaining data
                            if self.controller.ser.in_waiting > 0:
                                time.sleep(0.1)
                                if self.controller.ser.in_waiting > 0:
                                    response += self.controller.ser.read(self.controller.ser.in_waiting)
                            
                            # Filter out config summary if present
                            if response:
                                response = self.controller._filter_config_summary(response, debug_callback=debug_callback)
                            
                            # Parse response if we have data indicating Interactive mode input
                            if response and b'Positions' in response:
                                try:
                                    resp_text = response.decode('ascii', errors='replace')
                                    resp_text = resp_text.replace('\r', ' ').replace('\n', ' ')
                                    resp_text = ' '.join(resp_text.split()).strip()
                                    
                                    if debug_callback:
                                        debug_callback(f"<<< {resp_text}")
                                    
                                    parts = resp_text.split()
                                    
                                    # Get rotor count based on current model
                                    rotor_count = self.controller._get_rotor_count()
                                    
                                    # Look for pattern: "INPUT ENCODED Positions XX XX XX" (or XX XX XX XX for M4)
                                    min_parts_needed = 2 + rotor_count
                                    for j in range(len(parts) - min_parts_needed):
                                        part1 = parts[j]
                                        part2 = parts[j+1]
                                        part3 = parts[j+2]
                                        
                                        if (len(part1) == 1 and part1.isalpha() and part1.isupper() and
                                            len(part2) == 1 and part2.isalpha() and part2.isupper() and
                                            part3.lower() == 'positions'):
                                            # Found Interactive mode input - switch to Interactive mode
                                            original_char = part1
                                            encoded_char = part2
                                            
                                            # Switch to Interactive mode
                                            museum_paused[0] = True
                                            last_unexpected_input_time[0] = time.time()
                                            self.controller.function_mode = 'Interactive'
                                            # Update controller's last character info
                                            self.controller.last_char_original = original_char.upper() if original_char else None
                                            self.controller.last_char_received = encoded_char.upper() if encoded_char else None
                                            # Save the mode change to config file, but preserve cipher config
                                            self.controller.save_config(preserve_cipher_config=True)
                                            
                                            # Update UI to show the mode change
                                            self.draw_settings_panel()
                                            self.refresh_all_panels()
                                            add_log_message(f"Device input detected while waiting - switching to Interactive mode")
                                            if debug_callback:
                                                debug_callback(f"Device input detected while waiting - switching to Interactive mode", color_type=self.COLOR_MISMATCH)
                                            
                                            # Parse positions if available
                                            if j + 2 + rotor_count <= len(parts):
                                                positions = self.controller._parse_positions(parts, j + 3, rotor_count)
                                                if positions:
                                                    pos_str = self.controller._format_positions(parts, j + 3, rotor_count, positions)
                                                    self.controller.config['ring_position'] = pos_str
                                            
                                            break
                                except Exception as e:
                                    if debug_callback:
                                        debug_callback(f"Error parsing device input: {e}")
                    except Exception as e:
                        # Ignore read errors
                        pass
            
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
                    # Restore function mode to museum mode name
                    self.controller.function_mode = mode_name
                    self.controller.save_config(preserve_cipher_config=True)
                    # Update UI to show the function mode change
                    self.draw_settings_panel()
                    self.refresh_all_panels()
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
                
                try:
                    if self.simulate_mode:
                        # In simulation mode, just update config directly (no serial communication)
                        self.controller.config['mode'] = msg_obj.get('MODEL', 'I')
                        self.controller.config['rotor_set'] = msg_obj.get('ROTOR', 'A III IV I')
                        self.controller.config['ring_settings'] = msg_obj.get('RINGSET', '01 01 01')
                        self.controller.config['ring_position'] = msg_obj.get('RINGPOS', '20 6 10')
                        self.controller.config['pegboard'] = msg_obj.get('PLUG', '') if msg_obj.get('PLUG') else ''
                        self.controller.word_group_size = msg_obj.get('GROUP', 5)
                        if debug_callback:
                            debug_callback("Configuration updated for simulation")
                    else:
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
                        # Only return to encode mode if we're in encode mode
                        # In decode mode, the device should already be in the correct mode
                        if is_encode:
                            self.controller.return_to_encode_mode(debug_callback=debug_callback)
                            time.sleep(0.5)
                        else:
                            # For decode mode, ensure we're ready to decode
                            # The device should be in decode mode (set by user or device state)
                            time.sleep(0.5)
                except (serial.SerialException, OSError, AttributeError) as e:
                    if not self.simulate_mode:
                        # Serial operation failed - likely disconnection
                        device_disconnected[0] = True
                        museum_paused[0] = True
                        add_log_message("Enigma Touch disconnected during configuration - museum mode paused")
                        if debug_callback:
                            debug_callback(f"Serial error during configuration: {e} - pausing museum mode", color_type=self.COLOR_MISMATCH)
                        draw_screen()
                        continue  # Skip to next loop iteration to enter reconnection polling
                    else:
                        # In simulation mode, just log the error
                        if debug_callback:
                            debug_callback(f"Error in simulation configuration: {e}", color_type=self.COLOR_MISMATCH)
                
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
                formatted_expected = self.controller.format_message_for_display(expected_result)
                add_log_message(f"{operation}:")
                add_log_message(f"  MSG: {formatted_msg}")
                add_log_message(f"  CODED: {formatted_coded}")
                if is_encode:
                    add_log_message(f"  Expected encoded result: {formatted_expected}")
                else:
                    add_log_message(f"  Expected decoded result: {formatted_expected}")
                
                # Also show in debug callback
                if debug_callback:
                    debug_callback(f"{operation} message:")
                    debug_callback(f"  Sending: {formatted_message}")
                    if is_encode:
                        debug_callback(f"  Expected encoded result: {formatted_expected}")
                    else:
                        debug_callback(f"  Expected decoded result: {formatted_expected}")
                
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
                    
                    # Check if uppercase received in museum mode (indicates direct input from Enigma Touch)
                    # In museum mode, we expect lowercase encoded characters
                    # Note: Mode switch may have already happened in send_message, but check here too as backup
                    if is_encode and self.controller.function_mode.startswith(('Encode', 'Decode')):
                        # Check if received character was originally uppercase (direct input from device)
                        if self.controller.last_char_received and self.controller.last_char_received.isupper():
                            # Uppercase received in museum mode - direct input from Enigma Touch detected
                            if not museum_paused[0]:
                                museum_paused[0] = True
                                last_unexpected_input_time[0] = time.time()
                                self.controller.function_mode = 'Interactive'
                                # Initialize display values to None so they show as "-" until Interactive mode input is received
                                self.controller.last_char_original = None
                                self.controller.last_char_received = None
                                # Save the mode change to config file, but preserve cipher config (museum mode changes are temporary)
                                self.controller.save_config(preserve_cipher_config=True)
                                # Update UI to show the mode change
                                self.draw_settings_panel()
                                self.refresh_all_panels()
                                add_log_message(f"Direct input from Enigma Touch detected - switching to Interactive mode")
                                if debug_callback:
                                    debug_callback(f"Uppercase received in museum mode - direct input from Enigma Touch, switching to Interactive mode", color_type=self.COLOR_MISMATCH)
                                # Return True to stop sending the message
                                return True
                    # Also check if mode was already switched to Interactive (from send_message)
                    elif self.controller.function_mode == 'Interactive' and not museum_paused[0]:
                        # Mode was switched in send_message due to uppercase detection
                        museum_paused[0] = True
                        last_unexpected_input_time[0] = time.time()
                        # Initialize display values to None so they show as "-" until Interactive mode input is received
                        # (send_message may have already set them, but ensure they're None for clean display)
                        self.controller.last_char_original = None
                        self.controller.last_char_received = None
                        # Update UI to show the mode change
                        self.draw_settings_panel()
                        self.refresh_all_panels()
                        add_log_message(f"Switched to Interactive mode due to direct input from Enigma Touch")
                        # Return True to stop sending the message
                        return True
                    
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
                                # Mismatch detected - stop sending message and pause museum mode, switch to Interactive
                                if not museum_paused[0]:
                                    museum_paused[0] = True
                                    last_unexpected_input_time[0] = time.time()
                                    self.controller.function_mode = 'Interactive'
                                    # Initialize display values to None so they show as "-" until Interactive mode input is received
                                    self.controller.last_char_original = None
                                    self.controller.last_char_received = None
                                    # Save the mode change to config file, but preserve cipher config (museum mode changes are temporary)
                                    self.controller.save_config(preserve_cipher_config=True)
                                    # Update UI to show the mode change
                                    self.draw_settings_panel()
                                    self.refresh_all_panels()
                                    add_log_message(f"Encoding interrupted by user input - character mismatch detected, switching to Interactive mode")
                                    # Return True to stop sending the message
                                    return True
                    
                    return False
                
                def position_update_callback():
                    """Update settings panel when ring positions change or characters are sent/received"""
                    self.draw_settings_panel()
                    self.refresh_all_panels()
                
                config_error_occurred = [False]
                
                def config_error_callback(errors):
                    """Handle config errors by notifying user and preparing to switch to config menu"""
                    config_error_occurred[0] = True
                    error_msg = f"Configuration error: {', '.join(errors)}. Switching to config menu..."
                    add_log_message(error_msg)
                    if debug_callback:
                        debug_callback(error_msg, color_type=self.COLOR_MISMATCH)
                
                try:
                    # Determine language for simulation
                    simulation_language = 'EN' if mode in ('1', '2') else 'DE'
                    if self.simulate_mode:
                        message_sent = self.controller.send_message(
                            message_to_send, progress_callback, debug_callback, position_update_callback, 
                            config_error_callback, simulation_language=simulation_language, 
                            simulation_is_encode=is_encode
                        )
                    else:
                        message_sent = self.controller.send_message(
                            message_to_send, progress_callback, debug_callback, position_update_callback, config_error_callback
                        )
                except (serial.SerialException, OSError, AttributeError) as e:
                    if not self.simulate_mode:
                        # Serial operation failed during message sending - likely disconnection
                        device_disconnected[0] = True
                        museum_paused[0] = True
                        add_log_message("Enigma Touch disconnected during message sending - museum mode paused")
                        if debug_callback:
                            debug_callback(f"Serial error during message sending: {e} - pausing museum mode", color_type=self.COLOR_MISMATCH)
                        draw_screen()
                        continue  # Skip to next loop iteration to enter reconnection polling
                    else:
                        # In simulation mode, just log the error
                        if debug_callback:
                            debug_callback(f"Error in simulation: {e}", color_type=self.COLOR_MISMATCH)
                        message_sent = False
                    # Serial operation failed during message sending - likely disconnection
                    device_disconnected[0] = True
                    museum_paused[0] = True
                    add_log_message("Enigma Touch disconnected during message sending - museum mode paused")
                    if debug_callback:
                        debug_callback(f"Serial error during message sending: {e} - pausing museum mode", color_type=self.COLOR_MISMATCH)
                    draw_screen()
                    message_sent = False  # Mark as failed
                
                # If config error occurred, switch to config menu
                if config_error_occurred[0]:
                    add_log_message("Pausing museum mode to fix configuration")
                    museum_paused[0] = True
                    self.show_message(0, 0, "Configuration error detected! Switching to config menu...", curses.A_BOLD | curses.A_REVERSE)
                    self.draw_settings_panel()
                    self.draw_debug_panel()
                    self.refresh_all_panels()
                    time.sleep(2)
                    self.config_menu()
                    # After returning from config menu, resume museum mode
                    museum_paused[0] = False
                    continue  # Skip to next message
                
                # Check if message was interrupted (stopped early due to mismatch or mode switch)
                if museum_paused[0]:
                    # Message was interrupted by mismatch or mode switch - already logged and paused
                    # Update web display to show interruption
                    if current_encoded_text[0]:
                        current_encoded_text[0] = current_encoded_text[0] + " [INTERRUPTED]"
                    else:
                        current_encoded_text[0] = "[INTERRUPTED]"
                    # Force UI update (including function mode change if switched to Interactive)
                    self.draw_settings_panel()
                    self.draw_debug_panel()
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
                                # Update web display with final grouped result
                                current_encoded_text[0] = grouped_result
                            else:
                                # Decode mode: restore spaces and use formatted version
                                # Ensure result has no spaces before restoring (in case device added any)
                                result_no_spaces = result.replace(' ', '').upper()
                                restored_decoded = restore_spaces(result_no_spaces, msg_obj['MSG'])
                                formatted_decoded = self.controller.format_message_for_display(restored_decoded)
                                add_log_message(f"Decoded: {formatted_decoded}")
                                # Update web display with final restored decoded result (with proper spacing)
                                current_encoded_text[0] = restored_decoded
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
        # Restore original always_send_config value
        self.controller.always_send_config = original_always_send_config
        # Clear and redraw screen to prevent flickering
        self.setup_screen()
        self.draw_settings_panel()
        self.draw_debug_panel()
        self.refresh_all_panels()
    
    def run(self, config_only: bool = False, museum_mode: Optional[str] = None, debug_enabled: bool = True, simulate_mode: bool = False):
        """Main UI loop
        
        Args:
            config_only: If True, show only config menu and exit after
            museum_mode: If set, start directly in specified museum mode ('1', '2', '3', or '4')
            debug_enabled: If True, enable debug output panel at startup
            simulate_mode: If True, run in simulation mode (museum menus only)
        """
        # Update simulate_mode if provided
        if simulate_mode:
            self.simulate_mode = True
        # Set debug enabled if requested via command line (before initializing curses)
        if debug_enabled:
            self.debug_enabled = True
        
        # Initialize curses with error handling
        try:
            self.stdscr = curses.initscr()
            # Update UIBase with stdscr
            UIBase.__init__(self, self.controller, self.stdscr)
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
                    self.set_enigma_config_screen()
                elif choice == '6':
                    self.set_kiosk_lock_config_screen()
                elif choice == '7':
                    self.factory_reset_enigma_screen()
        
        finally:
            self.destroy_subwindows()
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()


