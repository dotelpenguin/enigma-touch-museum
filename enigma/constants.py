#!/usr/bin/env python3
"""
Constants for Enigma Museum Controller
"""

import os

# Application Version
VERSION = "v4.21.beta"

# Serial Configuration
DEFAULT_DEVICE = '/dev/ttyACM0'
BAUD_RATE = 9600
CHAR_TIMEOUT = 2.0  # seconds to wait for character response
CMD_TIMEOUT = 3.0   # seconds to wait for command response

# Config file path - in current working directory (where application is run from)
SCRIPT_DIR = os.getcwd()
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'enigma-museum-config.json')
ENGLISH_MSG_FILE = os.path.join(SCRIPT_DIR, 'english.msg')
GERMAN_MSG_FILE = os.path.join(SCRIPT_DIR, 'german.msg')

# Terminal size requirements
MIN_COLS = 100
MIN_LINES = 25

# UI Color pair IDs (for curses)
COLOR_SENT = 1      # Dark green for data sent to Enigma
COLOR_RECEIVED = 2  # Bright green for data received from Enigma
COLOR_INFO = 3      # Yellow for other info
COLOR_DELAY = 5     # Light purple for character delay messages
COLOR_MATCH = 6     # Bright green for matching characters
COLOR_MISMATCH = 7  # Red for mismatching characters
COLOR_WEB_RUNNING = 2  # Green for enabled and running web server
COLOR_WEB_ENABLED_NOT_RUNNING = 3  # Yellow for enabled but not running web server
COLOR_WEB_DISABLED = 4  # Grey for disabled web server

