#!/usr/bin/env python3
"""
Web server for museum displays
"""

import os
import socket
import threading
import json
import html as html_module
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from .constants import SCRIPT_DIR, VERSION, DEFAULT_LOCALE
from .theme_config import ThemeConfigManager
from .locale_manager import LocaleManager


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
        # Initialize theme and locale managers
        self.theme_manager = ThemeConfigManager()
        self.locale_manager = LocaleManager()
        # Load theme and locale
        self.theme = self.theme_manager.load_theme()
        self.locale = self.locale_manager.load_locale()
    
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def start(self):
        """Start the web server in a separate thread"""
        if not self.enabled:
            return None
        
        self.running = True
        
        # Store callback reference and server instance for handler
        data_callback_ref = self.data_callback
        server_instance = self
        theme_ref = self.theme
        locale_ref = self.locale
        locale_manager_ref = self.locale_manager
        
        class MuseumHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    try:
                        data = data_callback_ref()
                    except Exception as e:
                        data = {
                            'function_mode': 'N/A',
                            'delay': 60,
                            'log_messages': [f'Error getting data: {str(e)}'],
                            'always_send': False,
                            'config': {}
                        }
                    
                    if self.path == '/' or self.path == '/index.html':
                        self.send_response(302)
                        self.send_header('Location', '/status')
                        self.end_headers()
                    elif self.path == '/status':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        html = self.generate_status_html(data)
                        self.wfile.write(html.encode('utf-8'))
                        self.wfile.flush()
                    elif self.path == '/message.json':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        json_data = self.generate_message_json(data)
                        self.wfile.write(json.dumps(json_data).encode('utf-8'))
                        self.wfile.flush()
                    elif self.path.startswith('/kiosk.html'):
                        # Parse URL to get language and debug parameters
                        parsed_url = urlparse(self.path)
                        query_params = parse_qs(parsed_url.query)
                        language = DEFAULT_LOCALE
                        if 'lang' in query_params and query_params['lang']:
                            requested_lang = query_params['lang'][0].strip().lower()
                            # Validate language code (alphanumeric, 2-5 chars for safety)
                            if requested_lang and requested_lang.isalnum() and 2 <= len(requested_lang) <= 5:
                                language = requested_lang
                        
                        # Parse debug parameter
                        debug_mode = False
                        if 'debug' in query_params and query_params['debug']:
                            debug_value = query_params['debug'][0].strip().lower()
                            debug_mode = debug_value in ('true', '1', 'yes', 'on')
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        html = self.generate_kiosk_html(language=language, debug=debug_mode)
                        self.wfile.write(html.encode('utf-8'))
                        self.wfile.flush()
                    elif self.path == '/enigma.png':
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
                        try:
                            slide_file_path = os.path.join(SCRIPT_DIR, self.path.lstrip('/'))
                            if os.path.exists(slide_file_path) and os.path.isfile(slide_file_path):
                                with open(slide_file_path, 'rb') as f:
                                    image_data = f.read()
                                self.send_response(200)
                                self.send_header('Content-type', 'image/png')
                                self.send_header('Cache-Control', 'no-cache')
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
                is_interactive_mode = (function_mode == 'Interactive')
                delay = data.get('delay', 60)
                log_messages = data.get('log_messages', [])
                always_send = data.get('always_send', False)
                config = data.get('config', {})
                device_connected = data.get('device_connected', True)
                device_disconnected_message = data.get('device_disconnected_message', None)
                
                mode = config.get('mode', 'N/A')
                rotors = config.get('rotor_set', 'N/A')
                ring_settings = config.get('ring_settings', 'N/A')
                ring_position = config.get('ring_position', 'N/A')
                pegboard = config.get('pegboard', 'clear')
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Enigma Museum Mode</title>
    <meta http-equiv="refresh" content="{'1' if is_interactive_mode else '2'}">
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
                <div class="setting-item">
                    <span class="setting-label">Device Status:</span>
                    <span class="setting-value" style="color: {'#0f0' if device_connected else '#f00'}">{'Connected' if device_connected else 'Disconnected'}</span>
                </div>
                {('<div class="setting-item"><span class="setting-label">Plugboard:</span><span class="setting-value">' + html_module.escape(pegboard) + '</span></div>') if (pegboard and pegboard.strip() and pegboard.lower() != 'clear') else ''}
            </div>
            {f'<div class="note" style="color: #f00; font-weight: bold;">{html_module.escape(device_disconnected_message)}</div>' if device_disconnected_message else ''}
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
                    <span class="setting-label">Plugboard:</span>
                    <span class="setting-value">{pegboard}</span>
                </div>
            </div>
        </div>
        
        <div class="log">
            <h2>Activity Log</h2>
"""
                if log_messages:
                    for msg in reversed(log_messages[-50:]):
                        escaped_msg = html_module.escape(str(msg))
                        html += f'            <div class="log-entry">{escaped_msg}</div>\n'
                else:
                    html += '            <div class="log-entry">No activity yet...</div>\n'
                
                html += f"""        </div>
        
        <div style="text-align: center; margin-top: 20px; color: #888;">
            <p>Page auto-refreshes every 2 seconds</p>
            <p><a href="/kiosk.html" style="color: #0ff;">View Kiosk Display</a></p>
            <p>Museum Display {VERSION}</p>
        </div>
    </div>
</body>
</html>"""
                return html
            
            def generate_message_json(self, data):
                """Generate JSON data for museum kiosk display"""
                config = data.get('config', {})
                log_messages = data.get('log_messages', [])
                function_mode = data.get('function_mode', 'N/A')
                is_encode_mode = data.get('is_encode_mode', True)
                enable_slides = data.get('enable_slides', False)
                slide_path = data.get('slide_path', None)
                character_delay_ms = data.get('character_delay_ms', 0)
                current_char_index = data.get('current_char_index', 0)
                current_encoded_text = data.get('current_encoded_text', '')
                device_connected = data.get('device_connected', True)
                device_disconnected_message = data.get('device_disconnected_message', None)
                last_char_original = data.get('last_char_original', None)
                last_char_received = data.get('last_char_received', None)
                
                is_interactive_mode = (function_mode == 'Interactive')
                
                current_message = None
                result_message = None
                
                # Extract current_message and result_message from log messages
                if is_encode_mode:
                    if current_encoded_text:
                        result_message = current_encoded_text
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
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('Encoded:'):
                                result_message = msg_str.replace('Encoded:', '').strip()
                                break
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
                    if current_encoded_text:
                        result_message = current_encoded_text
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
                        for msg in reversed(log_messages):
                            msg_str = str(msg)
                            if msg_str.startswith('Decoded:'):
                                result_message = msg_str.replace('Decoded:', '').strip()
                                break
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
                
                mode = config.get('mode', 'N/A')
                rotors = config.get('rotor_set', 'N/A')
                ring_settings = config.get('ring_settings', 'N/A')
                ring_position = config.get('ring_position', 'N/A')
                pegboard = config.get('pegboard', 'clear')
                
                rotor_display = rotors
                if ' ' in rotors:
                    parts = rotors.split()
                    if len(parts) > 1:
                        rotor_display = ' '.join(parts[1:])
                
                # Build highlighted message if needed
                highlighted_message = None
                if current_message and current_char_index > 0:
                    message_no_spaces = current_message.replace(' ', '')
                    if current_char_index <= len(message_no_spaces):
                        char_count = 0
                        highlighted_parts = []
                        for char in current_message:
                            if char != ' ':
                                char_count += 1
                                if char_count == current_char_index:
                                    highlighted_parts.append({'type': 'highlight', 'char': char})
                                else:
                                    highlighted_parts.append({'type': 'normal', 'char': char})
                            else:
                                highlighted_parts.append({'type': 'normal', 'char': char})
                        highlighted_message = highlighted_parts
                
                return {
                    'config': {
                        'mode': mode,
                        'rotors': rotor_display.split() if rotor_display else [],
                        'ring_settings': ring_settings.split() if ring_settings else [],
                        'ring_position': ring_position.split() if ring_position else [],
                        'pegboard': pegboard.split() if (pegboard and pegboard.strip() and pegboard.lower() != 'clear') else []
                    },
                    'messages': {
                        'current_message': current_message,
                        'result_message': result_message,
                        'highlighted_message': highlighted_message,
                        'is_encode_mode': is_encode_mode,
                        'result_label': ('Encoded' if is_encode_mode else 'Decoded') + ' Message'
                    },
                    'interactive': {
                        'is_interactive_mode': is_interactive_mode,
                        'last_char_original': last_char_original.upper() if last_char_original else None,
                        'last_char_received': last_char_received.upper() if last_char_received else None
                    },
                    'display': {
                        'enable_slides': enable_slides,
                        'slide_path': slide_path
                    },
                    'device': {
                        'connected': device_connected,
                        'disconnected_message': device_disconnected_message
                    },
                    'character_highlighting': {
                        'character_delay_ms': character_delay_ms,
                        'current_char_index': current_char_index
                    }
                }
            
            def generate_kiosk_html(self, language: str = None, debug: bool = False):
                """Generate HTML page for JavaScript-powered kiosk display
                
                Args:
                    language: Language code to use (e.g., 'en', 'de'). If None, uses default.
                    debug: If True, display debug information (e.g., screen size) in footer.
                """
                theme = theme_ref
                # Load locale for the requested language
                if language:
                    locale = locale_manager_ref.load_locale(language)
                else:
                    locale = locale_ref
                
                # Helper function to get nested theme value
                def get_theme(path, default=""):
                    keys = path.split('.')
                    value = theme
                    try:
                        for key in keys:
                            value = value[key]
                        return value
                    except (KeyError, TypeError):
                        return default
                
                # Helper function to get nested locale string
                def get_locale(path, default=""):
                    keys = path.split('.')
                    value = locale
                    try:
                        for key in keys:
                            value = value[key]
                        return value
                    except (KeyError, TypeError):
                        return default
                
                # Prepare locale strings for JavaScript (escape script tags)
                locale_js = json.dumps(locale).replace('</script>', '<\\/script>')
                # Prepare debug mode for JavaScript
                debug_js = 'true' if debug else 'false'
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{get_locale('page_title', 'Enigma Museum Kiosk')}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100vw; height: 100vh; overflow: hidden; position: fixed; margin: 0; padding: 0; }}
        body {{ font-family: {get_theme('fonts.primary', "'Arial', sans-serif")}; background: linear-gradient(135deg, {get_theme('background.gradient_start', '#1a1a2e')} 0%, {get_theme('background.gradient_end', '#16213e')} 100%); color: {get_theme('colors.primary_text', '#fff')}; display: flex; flex-direction: column; align-items: stretch; justify-content: flex-start; padding: 0; }}
        .kiosk-container {{ width: 100vw; height: 100vh; text-align: center; display: flex; flex-direction: column; justify-content: flex-start; gap: 10px; flex: 1 1 auto; }}
        .logo-overlay {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 0; pointer-events: none; opacity: {get_theme('logo.opacity', '0.25')}; text-align: center; overflow: hidden; }}
        .logo-overlay .logo-container {{ border: none; padding: min(2vh, 20px) min(2vw, 20px); background: transparent; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
        .logo-overlay .logo-image {{ max-width: min(50vw, 500px); max-height: min(40vh, 400px); width: auto; height: auto; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); margin-bottom: 0.5vh; display: block; }}
        .logo-overlay .enigma-logo {{ font-size: min(8vw, 80px); font-weight: bold; color: {get_theme('logo.text_color', '#ffd700')}; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); letter-spacing: 0.3vw; margin-bottom: 0.3vh; display: block; }}
        .logo-overlay .subtitle {{ font-size: min(2.5vw, 25px); color: {get_theme('logo.subtitle_color', '#ccc')}; letter-spacing: 0.15vw; display: block; }}
        .machine-display {{ background: {get_theme('boxes.machine_display.background', 'rgba(0, 0, 0, 0.6)')}; border: 2px solid {get_theme('boxes.machine_display.border', '#ffd700')}; border-radius: {get_theme('boxes.machine_display.border_radius', '10px')}; padding: min(1vh, 10px); margin: min(1vh, 10px) min(1vw, 10px) 0 min(1vw, 10px); padding-bottom: min(0.5vh, 5px); box-shadow: {get_theme('boxes.machine_display.box_shadow', '0 4px 16px rgba(0,0,0,0.5)')}; flex-shrink: 0; max-height: calc(30vh + 23px); overflow: visible; }}
        .plugboard-unused {{ opacity: {get_theme('boxes.plugboard_unused.opacity', '0.4')}; color: {get_theme('boxes.plugboard_unused.color', '#888')} !important; }}
        .plugboard-unused .config-label {{ color: {get_theme('colors.dark_gray', '#666')} !important; }}
        .plugboard-unused .plugboard-box {{ background: {get_theme('boxes.plugboard_unused.background', 'rgba(100, 100, 100, 0.2)')} !important; border-color: {get_theme('boxes.plugboard_unused.border', '#666')} !important; color: {get_theme('boxes.plugboard_unused.color', '#888')} !important; }}
        .config-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: min(1vw, 10px); margin: min(1vh, 10px) 0; }}
        .config-item {{ background: {get_theme('boxes.config_item.background', 'rgba(255, 255, 255, 0.1)')}; padding: min(1vh, 10px); border-radius: {get_theme('boxes.config_item.border_radius', '6px')}; border: {get_theme('boxes.config_item.border', '1px solid rgba(255, 215, 0, 0.3)')}; }}
        .config-label {{ font-size: min(1.5vw, 15px); color: {get_theme('text.config_label.color', '#ffd700')}; text-transform: uppercase; letter-spacing: 0.1vw; margin-bottom: min(1vh, 10px); font-weight: bold; }}
        .config-value {{ font-size: min(2vw, 20px); color: {get_theme('text.config_value.color', '#fff')}; font-weight: bold; font-family: {get_theme('fonts.monospace', "'Courier New', monospace")}; }}
        .message-container {{ display: flex; flex-direction: row; gap: min(1vw, 10px); margin: 0; margin-top: 0; flex-grow: 1; flex-shrink: 1; min-height: 0; position: relative; }}
        .message-section {{ margin: min(1vh, 10px) min(1vw, 10px) 0 min(1vw, 10px); padding: min(1.5vh, 15px); background: {get_theme('boxes.message_section.background', 'rgba(0, 0, 0, 0.7)')}; border-radius: {get_theme('boxes.message_section.border_radius', '10px')}; border: 2px solid {get_theme('boxes.message_section.border', '#0ff')}; flex-grow: 1; display: flex; flex-direction: column; justify-content: center; min-height: 0; position: relative; overflow: hidden; }}
        .message-container .message-section {{ margin: min(1vh, 10px) min(1vw, 10px) 0 min(1vw, 10px); width: 75%; }}
        #messageContainer > .message-section {{ min-height: 0; }}
        #messageContainer {{ position: relative; margin: 0; padding: 0; flex-grow: 1; flex-shrink: 1; min-height: 0; display: flex; flex-direction: column; }}
        .message-section > *:not(.logo-overlay) {{ position: relative; z-index: 1; }}
        .slide-section {{ margin: min(1vh, 10px) min(1vw, 10px) 0 0; padding: min(1.5vh, 15px); background: {get_theme('boxes.slide_section.background', 'rgba(0, 0, 0, 0.7)')}; border-radius: {get_theme('boxes.slide_section.border_radius', '10px')}; border: 2px solid {get_theme('boxes.slide_section.border', '#0ff')}; flex-grow: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 0; width: 25%; }}
        .slide-placeholder {{ background: {get_theme('boxes.slide_placeholder.background', 'rgba(255, 255, 255, 0.05)')}; border: {get_theme('boxes.slide_placeholder.border', '2px dashed rgba(255, 215, 0, 0.5)')}; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: {get_theme('boxes.slide_placeholder.color', 'rgba(255, 215, 0, 0.6)')}; font-size: min(2vw, 20px); font-style: italic; width: 100%; height: 100%; min-height: 200px; }}
        .slide-image {{ width: 100%; height: 100%; max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px; display: block; transition: opacity 0.6s ease-in-out; }}
        .slide-section {{ overflow: hidden; }}
        .message-label {{ font-size: min(1.848vw, 18.48px); color: {get_theme('text.message_label.color', '#0ff')}; text-transform: uppercase; letter-spacing: 0.2vw; margin-bottom: min(1vh, 10px); flex-shrink: 0; }}
        .message-text {{ font-size: min(3.168vw, 31.68px); color: {get_theme('text.message_text.color', '#fff')}; font-family: {get_theme('fonts.monospace', "'Courier New', monospace")}; letter-spacing: 0.2vw; word-break: break-word; line-height: 1.4; overflow-y: auto; overflow-x: hidden; flex-grow: 1; min-height: 0; }}
        .char-highlight {{ background-color: {get_theme('text.char_highlight.background', '#ffd700')}; color: {get_theme('text.char_highlight.color', '#000')}; font-weight: bold; padding: 2px 4px; border-radius: 3px; }}
        .encoded-text {{ font-size: min(2.904vw, 29.04px); color: {get_theme('text.encoded_text.color', '#00ff80')}; font-family: {get_theme('fonts.monospace', "'Courier New', monospace")}; letter-spacing: 0.2vw; word-break: break-word; margin-top: min(1vh, 10px); padding-top: min(1vh, 10px); border-top: {get_theme('text.encoded_text.border_top', '1px solid rgba(0, 255, 128, 0.3)')}; flex-shrink: 0; overflow-y: auto; overflow-x: hidden; max-height: 20vh; }}
        .rotor-display {{ display: flex; justify-content: center; column-gap: min(2vw, 30px); row-gap: min(0.5vh, 5px); margin: 0; flex-wrap: wrap; }}
        .config-section {{ margin: 0; }}
        .rotor-box {{ background: {get_theme('boxes.rotor_box.background', 'rgba(255, 215, 0, 0.2)')}; border: 2px solid {get_theme('boxes.rotor_box.border', '#ffd700')}; border-radius: {get_theme('boxes.rotor_box.border_radius', '6px')}; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: {get_theme('boxes.rotor_box.color', '#ffd700')}; min-width: 60px; }}
        .model-box {{ background: {get_theme('boxes.model_box.background', 'rgba(128, 100, 128, 0.3)')}; border: 2px solid {get_theme('boxes.model_box.border', '#806480')}; border-radius: {get_theme('boxes.model_box.border_radius', '6px')}; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: {get_theme('boxes.model_box.color', '#c0a0c0')}; min-width: 60px; }}
        .ring-settings-box {{ background: {get_theme('boxes.ring_settings_box.background', 'rgba(100, 120, 150, 0.3)')}; border: 2px solid {get_theme('boxes.ring_settings_box.border', '#647896')}; border-radius: {get_theme('boxes.ring_settings_box.border_radius', '6px')}; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: {get_theme('boxes.ring_settings_box.color', '#90a8c8')}; min-width: 60px; }}
        .ring-position-box {{ background: {get_theme('boxes.ring_position_box.background', 'rgba(120, 150, 160, 0.3)')}; border: 2px solid {get_theme('boxes.ring_position_box.border', '#7896a0')}; border-radius: {get_theme('boxes.ring_position_box.border_radius', '6px')}; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: {get_theme('boxes.ring_position_box.color', '#a0c0d0')}; min-width: 60px; }}
        .plugboard-box {{ background: {get_theme('boxes.plugboard_box.background', 'rgba(150, 100, 120, 0.3)')}; border: 2px solid {get_theme('boxes.plugboard_box.border', '#966478')}; border-radius: {get_theme('boxes.plugboard_box.border_radius', '6px')}; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2vw, 20px); font-weight: bold; color: {get_theme('boxes.plugboard_box.color', '#c890a8')}; min-width: 60px; }}
        .footer {{ margin-top: min(0.2vh, 2px); color: {get_theme('text.footer.color', '#888')}; font-size: min(0.9vw, 9px); flex-shrink: 0; padding: min(1.3vh, 13px) 0; }}
        .disconnected-banner {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: {get_theme('errors.connection_lost.background', 'rgba(255, 0, 0, 0.95)')}; color: {get_theme('errors.connection_lost.color', '#fff')}; padding: min(2vh, 20px) min(4vw, 40px); text-align: center; font-size: min(2vw, 20px); font-weight: bold; border: {get_theme('errors.connection_lost.border', '2px solid #f00')}; border-radius: 10px; box-shadow: {get_theme('errors.connection_lost.box_shadow', '0 4px 20px rgba(255, 0, 0, 0.5), 0 0 20px rgba(255, 0, 0, 0.3)')}; z-index: 10000; opacity: 0; visibility: hidden; transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out; pointer-events: none; max-width: 80vw; min-width: min(40vw, 400px); }}
        .disconnected-banner.show {{ opacity: 1; visibility: visible; }}
        .disconnected-banner .error-title {{ font-size: min(2.2vw, 22px); margin-bottom: min(1vh, 10px); }}
        .disconnected-banner .error-details {{ font-size: min(1.6vw, 16px); font-weight: normal; opacity: 0.9; margin-top: min(0.8vh, 8px); line-height: 1.4; }}
        .device-disconnected-banner {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: {get_theme('errors.device_disconnected.background', 'rgba(255, 140, 0, 0.95)')}; color: {get_theme('errors.device_disconnected.color', '#fff')}; padding: min(2vh, 20px) min(4vw, 40px); text-align: center; font-size: min(2vw, 20px); font-weight: bold; border: {get_theme('errors.device_disconnected.border', '2px solid #ff8c00')}; border-radius: 10px; box-shadow: {get_theme('errors.device_disconnected.box_shadow', '0 4px 20px rgba(255, 140, 0, 0.5), 0 0 20px rgba(255, 140, 0, 0.3)')}; z-index: 10001; opacity: 0; visibility: hidden; transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out, top 0.3s ease-in-out; pointer-events: none; max-width: 80vw; min-width: min(40vw, 400px); }}
        .device-disconnected-banner.show {{ opacity: 1; visibility: visible; }}
        .device-disconnected-banner .error-title {{ font-size: min(2.2vw, 22px); margin-bottom: min(1vh, 10px); }}
        .device-disconnected-banner .error-details {{ font-size: min(1.6vw, 16px); font-weight: normal; opacity: 0.9; margin-top: min(0.8vh, 8px); line-height: 1.4; }}
        .disconnected-banner {{ transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out, top 0.3s ease-in-out; }}
        .interactive-container {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: min(2vh, 20px); margin: min(2vh, 20px) 0; flex-grow: 1; }}
        .interactive-mode-label {{ font-size: min(1.848vw, 18.48px); color: {get_theme('text.message_label.color', '#0ff')}; text-transform: uppercase; letter-spacing: 0.2vw; margin-bottom: min(1vh, 10px); font-weight: bold; flex-shrink: 0; }}
        .interactive-content {{ display: flex; flex-direction: row; align-items: center; justify-content: center; gap: min(3vw, 30px); }}
        .char-box {{ background: {get_theme('boxes.char_box.background', 'rgba(0, 255, 255, 0.2)')}; border: {get_theme('boxes.char_box.border', '3px solid #0ff')}; border-radius: {get_theme('boxes.char_box.border_radius', '15px')}; padding: min(4vh, 40px) min(4vw, 40px); min-width: min(15vw, 150px); min-height: min(15vw, 150px); display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: {get_theme('boxes.char_box.box_shadow', '0 4px 16px rgba(0, 255, 255, 0.3)')}; }}
        .char-box-label {{ font-size: min(1.2vw, 12px); color: {get_theme('text.char_box_label.color', '#0ff')}; text-transform: uppercase; letter-spacing: 0.2vw; margin-bottom: min(1vh, 10px); font-weight: bold; }}
        .char-box-value {{ font-size: min(10vw, 100px); color: {get_theme('text.char_box_value.color', '#fff')}; font-weight: bold; font-family: {get_theme('fonts.monospace', "'Courier New', monospace")}; line-height: 1; }}
        .char-arrow {{ font-size: min(6vw, 60px); color: {get_theme('text.char_arrow.color', '#ffd700')}; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="device-disconnected-banner" id="deviceBanner">
        <div class="error-title">{html_module.escape(get_locale('errors.device_disconnected', 'Enigma Touch Device Disconnected'))}</div>
        <div class="error-details" id="deviceErrorDetails">{html_module.escape(get_locale('errors.device_disconnected_message', 'Please reconnect the Enigma Touch device or turn it back on.'))}</div>
    </div>
    
    <div class="disconnected-banner" id="offlineBanner">
        <div class="error-title">{html_module.escape(get_locale('errors.connection_lost', 'Connection Lost'))}</div>
        <div class="error-details" id="errorDetails">{html_module.escape(get_locale('errors.attempting_reconnect', 'Attempting to reconnect...'))}</div>
    </div>
    
    <div class="kiosk-container">
        <div class="machine-display" id="machineDisplay">
            <div class="rotor-display" id="rotorDisplay"></div>
        </div>
        
        <div id="messageContainer">
            <div class="logo-overlay" id="logoOverlay">
                <img src="/enigma.png" alt="{html_module.escape(get_locale('logo.alt_text', 'Enigma Machine'))}" class="logo-image" id="logoImage" onerror="this.style.display='none'; document.getElementById('enigmaLogo').style.display='block';">
                <div class="enigma-logo" id="enigmaLogo" style="display: none;">{html_module.escape(get_locale('logo.enigma', 'ENIGMA'))}</div>
                <div class="subtitle">{html_module.escape(get_locale('logo.subtitle', 'Cipher Machine'))}</div>
            </div>
        </div>
        
        <div class="footer">
            <p>{html_module.escape(get_locale('footer.text', f'Museum Display {VERSION} - by Andrew Baker (DotelPenguin)').format(VERSION=VERSION))}<span id="debugInfo"></span></p>
        </div>
    </div>
    
    <script>
        (function() {{
            'use strict';
            
            // Locale strings
            const locale = {locale_js};
            
            // Helper function to get locale string
            function getLocale(path, defaultVal) {{
                const keys = path.split('.');
                let value = locale;
                try {{
                    for (const key of keys) {{
                        value = value[key];
                    }}
                    return value || defaultVal || path;
                }} catch (e) {{
                    return defaultVal || path;
                }}
            }}
            
            // State management
            let lastData = null;
            let refreshTimer = null;
            let retryTimer = null;
            let retryDelay = 1000; // Start with 1 second
            const maxRetryDelay = 10000; // Max 10 seconds
            let isOffline = false;
            let imageCache = {{}};
            let consecutiveFailures = 0;
            const failureThreshold = 4; // Show error after 4 consecutive failures (~2 seconds)
            
            // DOM elements
            const offlineBanner = document.getElementById('offlineBanner');
            const deviceBanner = document.getElementById('deviceBanner');
            const machineDisplay = document.getElementById('machineDisplay');
            const rotorDisplay = document.getElementById('rotorDisplay');
            const messageContainer = document.getElementById('messageContainer');
            const logoImage = document.getElementById('logoImage');
            const debugInfo = document.getElementById('debugInfo');
            
            // Debug mode (set from Python)
            const debugMode = {debug_js};
            
            // Update debug info in footer
            function updateDebugInfo() {{
                if (debugMode && debugInfo) {{
                    const width = window.innerWidth;
                    const height = window.innerHeight;
                    debugInfo.textContent = ' | Display: ' + width + ' x ' + height + 'px';
                }}
            }}
            
            // Update debug info on load and resize
            if (debugMode) {{
                updateDebugInfo();
                window.addEventListener('resize', updateDebugInfo);
            }}
            
            // Fetch with timeout
            function fetchWithTimeout(url, timeout = 5000) {{
                return Promise.race([
                    fetch(url),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('Timeout')), timeout)
                    )
                ]);
            }}
            
            // Preload image
            function preloadImage(src) {{
                if (!src || imageCache[src]) {{
                    return Promise.resolve(imageCache[src]);
                }}
                
                return new Promise((resolve, reject) => {{
                    const img = new Image();
                    img.onload = () => {{
                        imageCache[src] = img;
                        resolve(img);
                    }};
                    img.onerror = reject;
                    img.src = src;
                }});
            }}
            
            // Update image with smooth fade animation
            function updateImage(imgElement, newSrc) {{
                if (!newSrc) {{
                    // Fade out and hide
                    imgElement.style.opacity = '0';
                    setTimeout(function() {{
                        imgElement.style.display = 'none';
                    }}, 600);
                    return;
                }}
                
                // Check if already showing this image (compare full URL)
                const currentSrc = imgElement.src;
                const fullNewSrc = window.location.origin + newSrc;
                if (currentSrc === fullNewSrc || currentSrc.endsWith(newSrc)) {{
                    return; // Already showing this image
                }}
                
                // Preload the new image
                preloadImage(newSrc).then(function() {{
                    // Fade out current image
                    imgElement.style.opacity = '0';
                    
                    // After fade out completes, swap image and fade in
                    setTimeout(function() {{
                        imgElement.src = newSrc;
                        imgElement.style.display = 'block';
                        // Force reflow to ensure opacity transition works
                        imgElement.offsetHeight;
                        // Fade in new image
                        imgElement.style.opacity = '1';
                    }}, 600);
                }}).catch(function() {{
                    // If image fails to load, fade out and hide
                    imgElement.style.opacity = '0';
                    setTimeout(function() {{
                        imgElement.style.display = 'none';
                    }}, 600);
                }});
            }}
            
            // Update machine display
            function updateMachineDisplay(config) {{
                let html = '<div class="rotor-display">';
                
                // Model
                html += '<div class="config-section" style="display: flex; flex-direction: column; align-items: center;">';
                html += '<div class="config-label">' + escapeHtml(getLocale('labels.model', 'Model')) + '</div>';
                html += '<div class="model-box">' + escapeHtml(config.mode) + '</div>';
                html += '</div>';
                
                // Rotors
                html += '<div class="config-section" style="display: flex; flex-direction: column; align-items: center;">';
                html += '<div class="config-label">' + escapeHtml(getLocale('labels.rotors', 'Rotors')) + '</div>';
                html += '<div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">';
                config.rotors.forEach(function(rotor) {{
                    html += '<div class="rotor-box">' + escapeHtml(rotor) + '</div>';
                }});
                html += '</div></div>';
                
                // Ring Settings
                html += '<div class="config-section" style="display: flex; flex-direction: column; align-items: center;">';
                html += '<div class="config-label">' + escapeHtml(getLocale('labels.ring_settings', 'Ring Settings')) + '</div>';
                html += '<div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">';
                config.ring_settings.forEach(function(setting) {{
                    html += '<div class="ring-settings-box">' + escapeHtml(setting) + '</div>';
                }});
                html += '</div></div>';
                
                // Ring Position
                html += '<div class="config-section" style="display: flex; flex-direction: column; align-items: center;">';
                html += '<div class="config-label">' + escapeHtml(getLocale('labels.ring_position', 'Ring Position')) + '</div>';
                html += '<div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">';
                config.ring_position.forEach(function(position) {{
                    html += '<div class="ring-position-box">' + escapeHtml(position) + '</div>';
                }});
                html += '</div></div>';
                
                // Plugboard - always show, grey out if unused
                html += '<div class="config-section' + (config.pegboard && config.pegboard.length > 0 ? '' : ' plugboard-unused') + '" style="display: flex; flex-direction: column; align-items: center; margin-top: min(1vh, 10px); margin-bottom: min(1.5vh, 15px); width: 100%;">';
                html += '<div class="config-label">' + escapeHtml(getLocale('labels.plugboard', 'Plugboard')) + '</div>';
                html += '<div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">';
                if (config.pegboard && config.pegboard.length > 0) {{
                    config.pegboard.forEach(function(plug) {{
                        html += '<div class="plugboard-box">' + escapeHtml(plug) + '</div>';
                    }});
                }} else {{
                    html += '<div class="plugboard-box" style="font-style: italic;">' + escapeHtml(getLocale('labels.unused', 'Unused')) + '</div>';
                }}
                html += '</div></div>';
                
                html += '</div>';
                
                rotorDisplay.innerHTML = html;
            }}
            
            // Update message display
            function updateMessageDisplay(data) {{
                const messages = data.messages;
                const interactive = data.interactive;
                const display = data.display;
                const highlighting = data.character_highlighting;
                
                // Check if we need to rebuild the structure
                const hasInteractiveContainer = document.getElementById('interactiveContainer') !== null;
                const hasMessageText = document.getElementById('currentMessageText') !== null;
                const modeChanged = (interactive.is_interactive_mode && !hasInteractiveContainer) ||
                                   (!interactive.is_interactive_mode && !hasMessageText);
                
                const needsRebuild = !messageContainer.hasChildNodes() ||
                    modeChanged ||
                    (display.enable_slides && !document.getElementById('slideImage') && !document.querySelector('.slide-placeholder')) ||
                    (!display.enable_slides && document.getElementById('slideImage'));
                
                if (needsRebuild) {{
                    // Rebuild entire structure
                    let html = '';
                    
                    if (display.enable_slides) {{
                        html += '<div class="message-container">';
                        html += '<div class="message-section" id="messageSection">';
                    }} else {{
                        // When slides are disabled and in interactive mode, add flex styling to center content
                        if (interactive.is_interactive_mode) {{
                            html += '<div class="message-section" id="messageSection" style="display: flex; flex-direction: column; justify-content: center; position: relative;">';
                        }} else {{
                            html += '<div class="message-section" id="messageSection" style="position: relative;">';
                        }}
                    }}
                    
                    if (interactive.is_interactive_mode) {{
                        html += '<div class="interactive-container" id="interactiveContainer">';
                        html += '<div class="interactive-mode-label">' + escapeHtml(getLocale('interactive.mode', 'Interactive Mode')) + '</div>';
                        html += '<div class="interactive-content">';
                        html += '<div class="char-box">';
                        html += '<div class="char-box-label">' + escapeHtml(getLocale('interactive.received', 'Received')) + '</div>';
                        html += '<div class="char-box-value" id="receivedChar">' + escapeHtml(interactive.last_char_original || '--') + '</div>';
                        html += '</div>';
                        html += '<div class="char-arrow">&rarr;</div>';
                        html += '<div class="char-box">';
                        html += '<div class="char-box-label">' + escapeHtml(getLocale('interactive.encoded', 'Encoded')) + '</div>';
                        html += '<div class="char-box-value" id="encodedChar">' + escapeHtml(interactive.last_char_received || '--') + '</div>';
                        html += '</div>';
                        html += '</div>';
                        html += '</div>';
                    }} else {{
                        html += '<div class="message-label">' + escapeHtml(getLocale('messages.current_message', 'Current Message')) + '</div>';
                        html += '<div class="message-text" id="currentMessageText"></div>';
                        html += '<div class="message-label" id="resultLabel" style="display: none;"></div>';
                        html += '<div class="encoded-text" id="resultMessage" style="display: none;"></div>';
                    }}
                    
                    html += '</div>';
                    
                    if (display.enable_slides) {{
                        html += '<div class="slide-section">';
                        if (display.slide_path) {{
                            html += '<img src="/' + escapeHtml(display.slide_path) + '" alt="Slide" class="slide-image" id="slideImage" onerror="this.style.display=\\'none\\'; this.nextElementSibling.style.display=\\'flex\\';">';
                            html += '<div class="slide-placeholder" id="slidePlaceholder" style="display: none;">' + escapeHtml(getLocale('messages.slide_image_placeholder', 'Slide Image Placeholder')) + '</div>';
                        }} else {{
                            html += '<div class="slide-placeholder" id="slidePlaceholder">' + escapeHtml(getLocale('messages.slide_image_placeholder', 'Slide Image Placeholder')) + '</div>';
                        }}
                        html += '</div>';
                        html += '</div>';
                    }}
                    
                    messageContainer.innerHTML = html;
                    
                    // Add logo overlay to the message section (as first child so it's behind everything)
                    const messageSection = document.getElementById('messageSection');
                    if (messageSection) {{
                        const overlay = document.createElement('div');
                        overlay.className = 'logo-overlay';
                        overlay.id = 'logoOverlay';
                        overlay.innerHTML = '<div class="logo-container"><img src="/enigma.png" alt="' + escapeHtml(getLocale('logo.alt_text', 'Enigma Machine')) + '" class="logo-image" id="logoImage" onerror="this.style.display=\\'none\\'; document.getElementById(\\'enigmaLogo\\').style.display=\\'block\\';"><div class="enigma-logo" id="enigmaLogo" style="display: none;">' + escapeHtml(getLocale('logo.enigma', 'ENIGMA')) + '</div><div class="subtitle">' + escapeHtml(getLocale('logo.subtitle', 'Cipher Machine')) + '</div></div>';
                        messageSection.insertBefore(overlay, messageSection.firstChild);
                    }}
                }}
                
                // Update content without rebuilding structure
                if (interactive.is_interactive_mode) {{
                    const receivedChar = document.getElementById('receivedChar');
                    const encodedChar = document.getElementById('encodedChar');
                    if (receivedChar) {{
                        receivedChar.textContent = interactive.last_char_original || '--';
                    }}
                    if (encodedChar) {{
                        encodedChar.textContent = interactive.last_char_received || '--';
                    }}
                }} else {{
                    const currentMessageText = document.getElementById('currentMessageText');
                    const resultLabel = document.getElementById('resultLabel');
                    const resultMessage = document.getElementById('resultMessage');
                    
                    if (currentMessageText) {{
                        if (messages.highlighted_message) {{
                            currentMessageText.innerHTML = '';
                            messages.highlighted_message.forEach(function(part) {{
                                if (part.type === 'highlight') {{
                                    const span = document.createElement('span');
                                    span.className = 'char-highlight';
                                    span.textContent = part.char;
                                    currentMessageText.appendChild(span);
                                }} else {{
                                    currentMessageText.appendChild(document.createTextNode(part.char));
                                }}
                            }});
                        }} else {{
                            currentMessageText.textContent = messages.current_message || getLocale('messages.waiting_for_message', 'Waiting for message...');
                        }}
                    }}
                    
                    if (messages.result_message) {{
                        if (resultLabel) {{
                            resultLabel.textContent = messages.result_label;
                            resultLabel.style.display = 'block';
                        }}
                        if (resultMessage) {{
                            resultMessage.textContent = messages.result_message;
                            resultMessage.style.display = 'block';
                        }}
                    }} else {{
                        if (resultLabel) resultLabel.style.display = 'none';
                        if (resultMessage) resultMessage.style.display = 'none';
                    }}
                }}
                
                // Update slide image if it exists (only update the image, not the container)
                if (display.enable_slides && display.slide_path) {{
                    let slideImg = document.getElementById('slideImage');
                    if (!slideImg) {{
                        // Create image element if it doesn't exist
                        const slideSection = document.querySelector('.slide-section');
                        if (slideSection) {{
                            const placeholder = document.getElementById('slidePlaceholder');
                            if (placeholder) {{
                                placeholder.style.display = 'none';
                            }}
                            slideImg = document.createElement('img');
                            slideImg.src = '/' + display.slide_path;
                            slideImg.alt = 'Slide';
                            slideImg.className = 'slide-image';
                            slideImg.id = 'slideImage';
                            slideImg.onerror = function() {{
                                this.style.display = 'none';
                                const placeholder = document.getElementById('slidePlaceholder');
                                if (placeholder) {{
                                    placeholder.style.display = 'flex';
                                }}
                            }};
                            slideSection.insertBefore(slideImg, slideSection.firstChild);
                        }}
                    }}
                    if (slideImg) {{
                        updateImage(slideImg, '/' + display.slide_path);
                    }}
                }} else if (display.enable_slides && !display.slide_path) {{
                    // Hide image, show placeholder
                    const slideImg = document.getElementById('slideImage');
                    const placeholder = document.getElementById('slidePlaceholder');
                    if (slideImg) {{
                        slideImg.style.display = 'none';
                    }}
                    if (placeholder) {{
                        placeholder.style.display = 'flex';
                    }}
                }}
            }}
            
            // Escape HTML
            function escapeHtml(text) {{
                if (text === null || text === undefined) return '';
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }}
            
            // Check if data changed
            function dataChanged(newData) {{
                if (!lastData) return true;
                return JSON.stringify(newData) !== JSON.stringify(lastData);
            }}
            
            // Update offline status
            function setOfflineStatus(offline, errorDetails) {{
                if (isOffline === offline && !errorDetails) return;
                isOffline = offline;
                const errorDetailsEl = document.getElementById('errorDetails');
                if (offline) {{
                    if (errorDetails) {{
                        let detailsText = '';
                        if (errorDetails.type) {{
                            detailsText = errorDetails.type;
                            if (errorDetails.message) {{
                                detailsText += ': ' + errorDetails.message;
                            }}
                            if (errorDetails.status) {{
                                detailsText += ' (HTTP ' + errorDetails.status + ')';
                            }}
                        }} else if (errorDetails.message) {{
                            detailsText = errorDetails.message;
                        }} else {{
                            detailsText = getLocale('errors.connection_lost', 'Connection lost');
                        }}
                        detailsText += '. ' + getLocale('errors.connection_lost_message', 'Please check the Museum Kiosk Controller. Attempting to reconnect...');
                        errorDetailsEl.textContent = detailsText;
                    }} else {{
                        errorDetailsEl.textContent = getLocale('errors.connection_lost_message', 'Connection lost. Please check the Museum Kiosk Controller. Attempting to reconnect...');
                    }}
                    offlineBanner.classList.add('show');
                    // Adjust positioning if both banners are showing
                    if (deviceBanner.classList.contains('show')) {{
                        deviceBanner.style.top = '40%';
                        offlineBanner.style.top = '60%';
                    }} else {{
                        offlineBanner.style.top = '50%';
                    }}
                }} else {{
                    offlineBanner.classList.remove('show');
                    errorDetailsEl.textContent = getLocale('errors.attempting_reconnect', 'Attempting to reconnect...');
                    retryDelay = 1000; // Reset retry delay on reconnect
                    consecutiveFailures = 0; // Reset failure counter on reconnect
                    // Reset device banner position if connection banner is hidden
                    if (deviceBanner.classList.contains('show')) {{
                        deviceBanner.style.top = '50%';
                    }}
                }}
            }}
            
            // Update device status
            function setDeviceStatus(disconnectedMessage) {{
                const deviceErrorDetailsEl = document.getElementById('deviceErrorDetails');
                if (disconnectedMessage) {{
                    deviceErrorDetailsEl.textContent = getLocale('errors.device_disconnected_message', 'Please reconnect the Enigma Touch device or turn it back on.');
                    deviceBanner.classList.add('show');
                    // Adjust positioning if both banners are showing
                    if (offlineBanner.classList.contains('show')) {{
                        deviceBanner.style.top = '40%';
                        offlineBanner.style.top = '60%';
                    }} else {{
                        deviceBanner.style.top = '50%';
                    }}
                }} else {{
                    deviceBanner.classList.remove('show');
                    // Reset connection banner position if device banner is hidden
                    if (offlineBanner.classList.contains('show')) {{
                        offlineBanner.style.top = '50%';
                    }}
                }}
            }}
            
            // Fetch and update data
            function fetchAndUpdate() {{
                // Clear any existing timers
                if (refreshTimer) {{
                    clearTimeout(refreshTimer);
                    refreshTimer = null;
                }}
                if (retryTimer) {{
                    clearTimeout(retryTimer);
                    retryTimer = null;
                }}
                
                fetchWithTimeout('/message.json')
                    .then(function(response) {{
                        if (!response.ok) {{
                            const error = new Error('HTTP ' + response.status);
                            error.status = response.status;
                            error.type = 'Server Error';
                            throw error;
                        }}
                        return response.json();
                    }})
                    .then(function(data) {{
                        // Reset failure counter on successful fetch
                        consecutiveFailures = 0;
                        setOfflineStatus(false);
                        
                        if (dataChanged(data)) {{
                            // Update machine display
                            updateMachineDisplay(data.config);
                            
                            // Update message display
                            updateMessageDisplay(data);
                            
                            // Update device banner if needed (immediate, no failure threshold)
                            setDeviceStatus(data.device.disconnected_message);
                            
                            lastData = data;
                        }}
                        
                        // Schedule next fetch with adaptive rate
                        const refreshInterval = data.interactive.is_interactive_mode ? 500 : 1000;
                        refreshTimer = setTimeout(fetchAndUpdate, refreshInterval);
                    }})
                    .catch(function(error) {{
                        console.error('Fetch error:', error);
                        
                        // Increment failure counter
                        consecutiveFailures++;
                        
                        // Only show error banner after threshold failures
                        if (consecutiveFailures >= failureThreshold) {{
                            let errorDetails = {{
                                type: getLocale('errors.connection_error', 'Connection Error'),
                                message: getLocale('errors.unable_to_reach_server', 'Unable to reach server')
                            }};
                            
                            if (error.message) {{
                                if (error.message === 'Timeout') {{
                                    errorDetails.type = getLocale('errors.timeout', 'Timeout');
                                    errorDetails.message = getLocale('errors.timeout_message', 'Request timed out after 5 seconds');
                                }} else if (error.message.startsWith('HTTP')) {{
                                    errorDetails.type = getLocale('errors.server_error', 'Server Error');
                                    errorDetails.message = getLocale('errors.server_error_message', 'Server returned an error');
                                    errorDetails.status = error.status;
                                }} else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {{
                                    errorDetails.type = getLocale('errors.network_error', 'Network Error');
                                    errorDetails.message = getLocale('errors.network_error_message', 'Network connection failed');
                                }} else {{
                                    errorDetails.message = error.message;
                                }}
                            }}
                            
                            setOfflineStatus(true, errorDetails);
                        }}
                        
                        // Retry with exponential backoff
                        retryTimer = setTimeout(function() {{
                            fetchAndUpdate();
                            retryDelay = Math.min(retryDelay * 2, maxRetryDelay);
                        }}, retryDelay);
                    }});
            }}
            
            // Start fetching
            fetchAndUpdate();
        }})();
    </script>
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

