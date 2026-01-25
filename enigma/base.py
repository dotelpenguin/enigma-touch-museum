#!/usr/bin/env python3
"""
Base UI functionality for Enigma Museum Controller
"""

import curses
import socket
from typing import Optional
from enigma.constants import VERSION, MIN_COLS, MIN_LINES, COLOR_SENT, COLOR_RECEIVED, COLOR_INFO, COLOR_DELAY, COLOR_MATCH, COLOR_MISMATCH, COLOR_WEB_RUNNING, COLOR_WEB_ENABLED_NOT_RUNNING, COLOR_WEB_DISABLED


class UIBase:
    """Base UI functionality for window management and drawing"""
    
    def __init__(self, controller, stdscr):
        self.controller = controller
        self.stdscr = stdscr
        self.top_win = None
        self.left_win = None
        self.right_win = None
        self.debug_enabled = True
        self.debug_output = []
        self.max_debug_lines = 100
        self.top_height = 6
        
        # Color pair IDs (use constants)
        self.COLOR_SENT = COLOR_SENT
        self.COLOR_RECEIVED = COLOR_RECEIVED
        self.COLOR_INFO = COLOR_INFO
        self.COLOR_DELAY = COLOR_DELAY
        self.COLOR_MATCH = COLOR_MATCH
        self.COLOR_MISMATCH = COLOR_MISMATCH
        self.COLOR_WEB_RUNNING = COLOR_WEB_RUNNING
        self.COLOR_WEB_ENABLED_NOT_RUNNING = COLOR_WEB_ENABLED_NOT_RUNNING
        self.COLOR_WEB_DISABLED = COLOR_WEB_DISABLED
    
    def create_subwindows(self):
        """Create subwindows: top (settings), bottom left (menus), bottom right (debug/logo)"""
        if not self.stdscr:
            return
        
        if curses.COLS < MIN_COLS or curses.LINES < MIN_LINES:
            try:
                self.top_win = None
                self.left_win = self.stdscr.subwin(curses.LINES - 2, curses.COLS - 2, 1, 1)
                self.right_win = None
            except:
                self.top_win = None
                self.left_win = None
                self.right_win = None
            return
        
        self.destroy_subwindows()
        
        try:
            top_y = 1
            top_x = 1
            top_width = curses.COLS - 2
            self.top_win = self.stdscr.subwin(self.top_height, top_width, top_y, top_x)
            
            bottom_y = top_y + self.top_height + 1
            bottom_height = curses.LINES - bottom_y - 1
            left_width = (curses.COLS - 3) // 2
            right_width = curses.COLS - left_width - 3
            
            self.left_win = self.stdscr.subwin(bottom_height, left_width, bottom_y, top_x)
            right_x = top_x + left_width + 1
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
        
        if self.top_win:
            divider_y = 1 + self.top_height
            for x in range(1, curses.COLS - 1):
                try:
                    self.stdscr.addch(divider_y, x, '═')
                except:
                    pass
        
        if self.left_win and self.right_win:
            divider_x = curses.COLS // 2
            bottom_start = 1 + self.top_height + 1
            for y in range(bottom_start, curses.LINES - 1):
                try:
                    self.stdscr.addch(y, divider_x, '║')
                except:
                    pass
        
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
        return curses.COLS - 2
    
    def get_local_ip(self) -> str:
        """Get the local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def draw_settings_panel(self):
        """Display Enigma settings in the top window"""
        if not self.top_win:
            return
        
        try:
            self.top_win.clear()
            max_y, max_x = self.top_win.getmaxyx()
            
            # Build title with firmware version if available
            firmware_info = ""
            if self.controller.firmware_version is not None:
                firmware_info = f"  (FW {self.controller.firmware_version:.2f})"
            title = f"Enigma Museum Controller  {VERSION}{firmware_info}"
            title_x = (max_x - len(title)) // 2
            if title_x >= 0:
                try:
                    self.top_win.addstr(0, max(0, title_x), title, curses.A_BOLD)
                except:
                    pass
            
            config = self.controller.config
            web_port = self.controller.web_server_port
            if self.controller.web_server_ip:
                web_ip = self.controller.web_server_ip
            else:
                web_ip = self.get_local_ip()
            web_url = f"http://{web_ip}:{web_port}"
            web_enabled = self.controller.web_server_enabled
            
            char_delay = f"{self.controller.character_delay_ms}ms" if self.controller.character_delay_ms > 0 else "0ms"
            last_char_info = ""
            if self.controller.last_char_sent:
                if self.controller.last_char_received:
                    last_char_info = f"Last: {self.controller.last_char_sent}→{self.controller.last_char_received}"
                else:
                    last_char_info = f"Last sent: {self.controller.last_char_sent}"
            elif self.controller.last_char_received:
                last_char_info = f"Last received: {self.controller.last_char_original}→{self.controller.last_char_received}"
            else:
                last_char_info = "Last: --"
            
            # Format counter display
            counter_display = "N/A"
            if self.controller.counter is not None:
                counter_display = str(self.controller.counter)
            
            settings_lines = [
                f"Mode: {config.get('mode', 'N/A'):<8}  Rotors: {config.get('rotor_set', 'N/A'):<20}  Ring Settings: {config.get('ring_settings', 'N/A'):<12}",
                f"Ring Position: {config.get('ring_position', 'N/A'):<15}  Plugboard: {config.get('pegboard', 'clear'):<20}  Function Mode: {self.controller.function_mode:<15}",
                f"Counter: {counter_display:<15}",
            ]
            
            start_y = 1 + ((max_y - 1 - (len(settings_lines) + 1)) // 2)
            for i, line in enumerate(settings_lines):
                y = start_y + i
                if y >= max_y:
                    break
                display_line = line[:max_x]
                x = (max_x - len(display_line)) // 2
                if x >= 0:
                    self.top_win.addstr(y, max(0, x), display_line, curses.A_BOLD)
            
            web_line_y = start_y + len(settings_lines)
            if web_line_y < max_y:
                web_prefix = f"Char Delay: {char_delay:<15}  Web Server: "
                web_suffix = f"  {last_char_info}"
                web_line_full = f"{web_prefix}{web_url}{web_suffix}"
                
                web_url_display = web_url
                if len(web_line_full) > max_x:
                    available_for_url = max_x - len(web_prefix) - len(web_suffix)
                    if available_for_url < len(web_url):
                        web_url_display = web_url[:max(0, available_for_url)]
                    web_line_full = f"{web_prefix}{web_url_display}{web_suffix}"[:max_x]
                
                x = (max_x - len(web_line_full)) // 2
                if x >= 0:
                    self.top_win.addstr(web_line_y, max(0, x), web_prefix, curses.A_BOLD)
                    prefix_end = x + len(web_prefix)
                    
                    if not web_enabled:
                        url_color = self.COLOR_WEB_DISABLED
                        if curses.has_colors():
                            url_attr = curses.color_pair(url_color) | curses.A_DIM
                        else:
                            url_attr = curses.A_DIM
                    elif self.controller.web_server_ip:
                        url_color = self.COLOR_WEB_RUNNING
                        if curses.has_colors():
                            url_attr = curses.color_pair(url_color) | curses.A_BOLD
                        else:
                            url_attr = curses.A_BOLD
                    else:
                        url_color = self.COLOR_WEB_ENABLED_NOT_RUNNING
                        if curses.has_colors():
                            url_attr = curses.color_pair(url_color) | curses.A_BOLD
                        else:
                            url_attr = curses.A_BOLD
                    
                    self.top_win.addstr(web_line_y, prefix_end, web_url_display, url_attr)
                    url_end = prefix_end + len(web_url_display)
                    
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
        logo = [
            "╔══════════════════════╗",
            "║   ENIGMA MACHINE     ║",
            "║                      ║",
            "║  ╔═══╗ ╔═══╗ ╔═══╗   ║",
            "║  ║ I ║ ║II ║ ║III║   ║",
            "║  ╚═══╝ ╚═══╝ ╚═══╝   ║",
            "║                      ║",
            "╚══════════════════════╝",
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
            max_logo_width = max(len(line) for line in logo) if logo else 0
            
            if max_logo_width > max_x or len(logo) > max_y:
                msg = "ENIGMA MACHINE"
                y = max_y // 2
                x = (max_x - len(msg)) // 2
                if x >= 0:
                    self.right_win.addstr(y, x, msg, curses.A_BOLD)
            else:
                start_y = (max_y - len(logo)) // 2
                for i, line in enumerate(logo):
                    y = start_y + i
                    if y >= max_y:
                        break
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
        """Add a message to debug output with color coding"""
        if not self.debug_enabled:
            return
        lines = message.split('\n')
        for line in lines:
            line = line.replace('\r', '').strip()
            if line:
                if color_type is None:
                    if line.startswith('>>>'):
                        color_type = self.COLOR_SENT
                    elif line.startswith('<<<'):
                        color_type = self.COLOR_RECEIVED
                    elif 'Character delay' in line or 'Skipping delay' in line:
                        color_type = self.COLOR_DELAY
                    elif 'MATCH' in line:
                        color_type = self.COLOR_MATCH
                    elif 'MISMATCH' in line:
                        color_type = self.COLOR_MISMATCH
                    else:
                        color_type = self.COLOR_INFO
                self.debug_output.append((line, color_type))
        if len(self.debug_output) > self.max_debug_lines:
            self.debug_output = self.debug_output[-self.max_debug_lines:]
    
    def draw_debug_panel(self):
        """Draw debug output or logo in the right panel"""
        if not self.right_win:
            return
        
        if self.debug_enabled:
            try:
                self.right_win.clear()
                max_y, max_x = self.right_win.getmaxyx()
                
                header = " DEBUG OUTPUT "
                header_x = (max_x - len(header)) // 2
                if header_x >= 0 and header_x + len(header) <= max_x:
                    self.right_win.addstr(0, header_x, header, curses.A_BOLD | curses.A_REVERSE)
                
                start_line = 1
                available_lines = max_y - start_line
                debug_lines_to_show = self.debug_output[-available_lines:] if len(self.debug_output) > available_lines else self.debug_output
                
                for i, debug_item in enumerate(debug_lines_to_show):
                    y = start_line + i
                    if y >= max_y:
                        break
                    try:
                        if isinstance(debug_item, tuple):
                            line, color_type = debug_item
                        else:
                            line = debug_item
                            color_type = self.COLOR_INFO
                        
                        display_line = line.replace('\r', '').replace('\n', ' ').strip()
                        if display_line.startswith('>>> '):
                            display_line = display_line[4:]
                        elif display_line.startswith('<<< '):
                            display_line = display_line[4:]
                        display_line = display_line[:max_x]
                        self.right_win.addstr(y, 0, ' ' * max_x)
                        if curses.has_colors():
                            color_attr = curses.color_pair(color_type)
                            if color_type == self.COLOR_RECEIVED or color_type == self.COLOR_MATCH:
                                color_attr |= curses.A_BOLD
                            self.right_win.addstr(y, 0, display_line, color_attr)
                        else:
                            self.right_win.addstr(y, 0, display_line)
                    except:
                        pass
                
                self.right_win.refresh()
            except:
                pass
        else:
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
            input_x = x + len(prompt)
            max_y, max_x = win.getmaxyx()
            for clear_x in range(input_x, max_x):
                try:
                    win.addstr(y, clear_x, ' ')
                except:
                    pass
            win.move(y, input_x)
            win.refresh()
            
            value = win.getstr(y, input_x, 50).decode('utf-8')
            if not value and default:
                return default
            return value
        except:
            return default
        finally:
            curses.noecho()
            curses.curs_set(0)

