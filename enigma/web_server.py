#!/usr/bin/env python3
"""
Web server for museum displays
"""

import os
import socket
import threading
import html as html_module
from http.server import HTTPServer, BaseHTTPRequestHandler
from .constants import SCRIPT_DIR, VERSION


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
                    elif self.path == '/message':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        html = self.generate_message_html(data)
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
            <p><a href="/message" style="color: #0ff;">View Kiosk Display</a></p>
            <p>Museum Display {VERSION}</p>
        </div>
    </div>
</body>
</html>"""
                return html
            
            def generate_message_html(self, data):
                """Generate HTML page for museum kiosk display"""
                config = data.get('config', {})
                log_messages = data.get('log_messages', [])
                function_mode = data.get('function_mode', 'N/A')
                is_interactive_mode = (function_mode == 'Interactive')
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
                
                current_message = None
                result_message = None
                
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
                
                # Generate the HTML (abbreviated for brevity - full HTML is in original)
                banner_html = ''
                if device_disconnected_message:
                    banner_html = f'        <div class="disconnected-banner">{html_module.escape(device_disconnected_message)}</div>\n'
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Enigma Museum Kiosk</title>
    <meta http-equiv="refresh" content="{'1' if is_interactive_mode else '2'}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100vw; height: 100vh; overflow: hidden; position: fixed; }}
        body {{ font-family: 'Arial', sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding: 0.8vh 0.8vw; }}
        .kiosk-container {{ width: 100%; max-width: 98vw; text-align: center; display: flex; flex-direction: column; height: 100%; max-height: 98vh; justify-content: space-between; }}
        .logo-section {{ margin-bottom: 1vh; flex-shrink: 0; max-height: 15vh; }}
        .logo-image {{ max-width: min(25vw, 250px); max-height: min(12vh, 120px); width: auto; height: auto; margin-bottom: 0.5vh; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); }}
        .enigma-logo {{ font-size: min(4.5vw, 48px); font-weight: bold; color: #ffd700; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); letter-spacing: 0.3vw; margin-bottom: 0.3vh; }}
        .subtitle {{ font-size: min(1.5vw, 16px); color: #ccc; letter-spacing: 0.15vw; margin-bottom: 0; }}
        .machine-display {{ background: rgba(0, 0, 0, 0.6); border: 2px solid #ffd700; border-radius: 10px; padding: min(1.5vh, 15px); margin: min(1vh, 10px) 0; box-shadow: 0 4px 16px rgba(0,0,0,0.5); flex-shrink: 0; max-height: 25vh; overflow: hidden; }}
        .config-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: min(1vw, 10px); margin: min(1vh, 10px) 0; }}
        .config-item {{ background: rgba(255, 255, 255, 0.1); padding: min(1vh, 10px); border-radius: 6px; border: 1px solid rgba(255, 215, 0, 0.3); }}
        .config-label {{ font-size: min(1.5vw, 15px); color: #ffd700; text-transform: uppercase; letter-spacing: 0.1vw; margin-bottom: min(1vh, 10px); font-weight: bold; }}
        .config-value {{ font-size: min(2vw, 20px); color: #fff; font-weight: bold; font-family: 'Courier New', monospace; }}
        .message-container {{ display: flex; flex-direction: row; gap: min(1vw, 10px); margin: min(1vh, 10px) 0; flex-grow: 1; min-height: 0; max-height: 50vh; }}
        .message-section {{ margin: min(1vh, 10px) 0; padding: min(1.5vh, 15px); background: rgba(0, 0, 0, 0.7); border-radius: 10px; border: 2px solid #0ff; flex-grow: 1; display: flex; flex-direction: column; justify-content: center; min-height: 0; max-height: 50vh; }}
        .message-container .message-section {{ margin: 0; width: 75%; max-height: none; }}
        .slide-section {{ margin: 0; padding: min(1.5vh, 15px); background: rgba(0, 0, 0, 0.7); border-radius: 10px; border: 2px solid #0ff; flex-grow: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 0; width: 25%; }}
        .slide-placeholder {{ background: rgba(255, 255, 255, 0.05); border: 2px dashed rgba(255, 215, 0, 0.5); border-radius: 10px; display: flex; align-items: center; justify-content: center; color: rgba(255, 215, 0, 0.6); font-size: min(2vw, 20px); font-style: italic; width: 100%; height: 100%; min-height: 200px; }}
        .slide-image {{ width: 100%; height: 100%; max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px; display: block; }}
        .slide-section {{ overflow: hidden; }}
        .message-label {{ font-size: min(1.4vw, 14px); color: #0ff; text-transform: uppercase; letter-spacing: 0.2vw; margin-bottom: min(1vh, 10px); flex-shrink: 0; }}
        .message-text {{ font-size: min(2.4vw, 24px); color: #fff; font-family: 'Courier New', monospace; letter-spacing: 0.2vw; word-break: break-word; line-height: 1.4; overflow-y: auto; overflow-x: hidden; flex-grow: 1; min-height: 0; }}
        .char-highlight {{ background-color: #ffd700; color: #000; font-weight: bold; padding: 2px 4px; border-radius: 3px; }}
        .encoded-text {{ font-size: min(2.2vw, 22px); color: #0f0; font-family: 'Courier New', monospace; letter-spacing: 0.2vw; word-break: break-word; margin-top: min(1vh, 10px); padding-top: min(1vh, 10px); border-top: 1px solid rgba(0, 255, 0, 0.3); flex-shrink: 0; overflow-y: auto; overflow-x: hidden; max-height: 20vh; }}
        .rotor-display {{ display: flex; justify-content: center; gap: min(2vw, 30px); margin: min(1vh, 10px) 0; flex-wrap: wrap; }}
        .rotor-box {{ background: rgba(255, 215, 0, 0.2); border: 2px solid #ffd700; border-radius: 6px; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: #ffd700; min-width: 60px; }}
        .model-box {{ background: rgba(128, 100, 128, 0.3); border: 2px solid #806480; border-radius: 6px; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: #c0a0c0; min-width: 60px; }}
        .ring-settings-box {{ background: rgba(100, 120, 150, 0.3); border: 2px solid #647896; border-radius: 6px; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: #90a8c8; min-width: 60px; }}
        .ring-position-box {{ background: rgba(120, 150, 160, 0.3); border: 2px solid #7896a0; border-radius: 6px; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2.2vw, 22px); font-weight: bold; color: #a0c0d0; min-width: 60px; }}
        .plugboard-box {{ background: rgba(150, 100, 120, 0.3); border: 2px solid #966478; border-radius: 6px; padding: min(0.8vh, 8px) min(1.5vw, 15px); font-size: min(2vw, 20px); font-weight: bold; color: #c890a8; min-width: 60px; }}
        .footer {{ margin-top: min(0.5vh, 5px); color: #888; font-size: min(1.1vw, 11px); flex-shrink: 0; }}
        .disconnected-banner {{ background: rgba(255, 0, 0, 0.8); color: #fff; padding: min(1.5vh, 15px); text-align: center; font-size: min(2vw, 20px); font-weight: bold; border: 2px solid #f00; border-radius: 10px; margin-bottom: min(1vh, 10px); }}
        .interactive-container {{ display: flex; flex-direction: row; align-items: center; justify-content: center; gap: min(3vw, 30px); margin: min(2vh, 20px) 0; flex-grow: 1; }}
        .char-box {{ background: rgba(0, 255, 255, 0.2); border: 3px solid #0ff; border-radius: 15px; padding: min(4vh, 40px) min(4vw, 40px); min-width: min(15vw, 150px); min-height: min(15vw, 150px); display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 4px 16px rgba(0, 255, 255, 0.3); }}
        .char-box-label {{ font-size: min(1.2vw, 12px); color: #0ff; text-transform: uppercase; letter-spacing: 0.2vw; margin-bottom: min(1vh, 10px); font-weight: bold; }}
        .char-box-value {{ font-size: min(10vw, 100px); color: #fff; font-weight: bold; font-family: 'Courier New', monospace; line-height: 1; }}
        .char-arrow {{ font-size: min(6vw, 60px); color: #ffd700; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="kiosk-container">
{banner_html}        <div class="logo-section">
            <img src="/enigma.png" alt="Enigma Machine" class="logo-image" onerror="this.style.display='none'; document.querySelector('.enigma-logo').style.display='block';">
            <div class="enigma-logo" style="display: none;">ENIGMA</div>
            <div class="subtitle">Cipher Machine</div>
        </div>
        
        <div class="machine-display">
            <div class="rotor-display">
                <div class="config-section" style="display: flex; flex-direction: column; align-items: center;">
                    <div class="config-label">Model</div>
                    <div class="model-box">{html_module.escape(mode)}</div>
                </div>
                <div class="config-section" style="display: flex; flex-direction: column; align-items: center;">
                    <div class="config-label">Rotors</div>
                    <div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">
"""
                rotor_parts = rotor_display.split()
                for rotor in rotor_parts:
                    html += f'                        <div class="rotor-box">{html_module.escape(rotor)}</div>\n'
                
                html += f"""                    </div>
                </div>
                <div class="config-section" style="display: flex; flex-direction: column; align-items: center;">
                    <div class="config-label">Ring Settings</div>
                    <div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">
"""
                ring_settings_parts = ring_settings.split()
                for setting in ring_settings_parts:
                    html += f'                        <div class="ring-settings-box">{html_module.escape(setting)}</div>\n'
                
                html += f"""                    </div>
                </div>
                <div class="config-section" style="display: flex; flex-direction: column; align-items: center;">
                    <div class="config-label">Ring Position</div>
                    <div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">
"""
                ring_position_parts = ring_position.split()
                for position in ring_position_parts:
                    html += f'                        <div class="ring-position-box">{html_module.escape(position)}</div>\n'
                
                html += f"""                    </div>
                </div>
            </div>
"""
                # Add plugboard display on its own line if configured
                if pegboard and pegboard.strip() and pegboard.lower() != 'clear':
                    html += f"""            <div style="display: flex; flex-direction: column; align-items: center; margin-top: min(1vh, 10px);">
                <div class="config-label">Plugboard</div>
                <div style="display: flex; gap: min(1vw, 10px); flex-wrap: wrap; justify-content: center;">
"""
                    plugboard_parts = pegboard.split()
                    for plug in plugboard_parts:
                        html += f'                    <div class="plugboard-box">{html_module.escape(plug)}</div>\n'
                    html += f"""                </div>
            </div>
"""
                html += f"""        </div>
"""
                if enable_slides:
                    if is_interactive_mode:
                        # Interactive mode: Show large Received -> Encoded boxes
                        html += """        <div class="message-container">
            <div class="message-section" style="display: flex; flex-direction: column; justify-content: center;">
                <div class="interactive-container">
                    <div class="char-box">
                        <div class="char-box-label">Received</div>
                        <div class="char-box-value">"""
                        received_char = last_char_original.upper() if last_char_original else '--'
                        html += html_module.escape(str(received_char))
                        html += """</div>
                    </div>
                    <div class="char-arrow">&rarr;</div>
                    <div class="char-box">
                        <div class="char-box-label">Encoded</div>
                        <div class="char-box-value">"""
                        encoded_char = last_char_received.upper() if last_char_received else '--'
                        html += html_module.escape(str(encoded_char))
                        html += """</div>
                    </div>
                </div>
            </div>
            <div class="slide-section">"""
                    else:
                        html += """        <div class="message-container">
            <div class="message-section">
                <div class="message-label">Current Message</div>
                <div class="message-text">"""
                        
                        if current_message and character_delay_ms >= 2000 and current_char_index > 0:
                            message_no_spaces = current_message.replace(' ', '')
                            if current_char_index <= len(message_no_spaces):
                                char_count = 0
                                highlighted_message = ""
                                for char in current_message:
                                    if char != ' ':
                                        char_count += 1
                                        if char_count == current_char_index:
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
                        result_label = "Encoded" if is_encode_mode else "Decoded"
                        result_label += " Message"
                        if result_message:
                            html += f'                <div class="message-label">{result_label}</div>\n'
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
                    if is_interactive_mode:
                        # Interactive mode: Show large Received -> Encoded boxes
                        html += """        <div class="message-section" style="display: flex; flex-direction: column; justify-content: center;">
            <div class="interactive-container">
                <div class="char-box">
                    <div class="char-box-label">Received</div>
                    <div class="char-box-value">"""
                        received_char = last_char_original if last_char_original else '-'
                        html += html_module.escape(str(received_char))
                        html += """</div>
                </div>
                <div class="char-arrow">&rarr;</div>
                <div class="char-box">
                    <div class="char-box-label">Encoded</div>
                    <div class="char-box-value">"""
                        encoded_char = last_char_received if last_char_received else '-'
                        html += html_module.escape(str(encoded_char))
                        html += """</div>
                </div>
            </div>
        </div>
"""
                    else:
                        html += """        <div class="message-section">
            <div class="message-label">Current Message</div>
            <div class="message-text">"""
                        
                        if current_message and character_delay_ms >= 2000 and current_char_index > 0:
                            message_no_spaces = current_message.replace(' ', '')
                            if current_char_index <= len(message_no_spaces):
                                char_count = 0
                                highlighted_message = ""
                                for char in current_message:
                                    if char != ' ':
                                        char_count += 1
                                        if char_count == current_char_index:
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
                        result_label = "Encoded" if is_encode_mode else "Decoded"
                        result_label += " Message"
                        if result_message:
                            html += f'            <div class="message-label">{result_label}</div>\n'
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

