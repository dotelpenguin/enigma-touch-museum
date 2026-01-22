#!/usr/bin/env python3
"""
Theme configuration management for Kiosk display
"""

import json
import os
from typing import Dict, Any
from .constants import KIOSK_THEME_FILE


def get_default_theme() -> Dict[str, Any]:
    """Get default theme configuration with current color values"""
    return {
        "background": {
            "gradient_start": "#1a1a2e",
            "gradient_end": "#16213e"
        },
        "colors": {
            "primary_text": "#fff",
            "accent_gold": "#ffd700",
            "accent_cyan": "#0ff",
            "accent_green": "#00ff80",
            "secondary_text": "#ccc",
            "gray_text": "#888",
            "dark_gray": "#666",
            "black": "#000"
        },
        "logo": {
            "opacity": 0.25,
            "text_color": "#ffd700",
            "subtitle_color": "#ccc"
        },
        "boxes": {
            "machine_display": {
                "background": "rgba(0, 0, 0, 0.6)",
                "border": "#ffd700",
                "border_radius": "10px",
                "box_shadow": "0 4px 16px rgba(0,0,0,0.5)"
            },
            "message_section": {
                "background": "rgba(0, 0, 0, 0.7)",
                "border": "#0ff",
                "border_radius": "10px"
            },
            "slide_section": {
                "background": "rgba(0, 0, 0, 0.7)",
                "border": "#0ff",
                "border_radius": "10px"
            },
            "slide_placeholder": {
                "background": "rgba(255, 255, 255, 0.05)",
                "border": "2px dashed rgba(255, 215, 0, 0.5)",
                "color": "rgba(255, 215, 0, 0.6)"
            },
            "config_item": {
                "background": "rgba(255, 255, 255, 0.1)",
                "border": "1px solid rgba(255, 215, 0, 0.3)",
                "border_radius": "6px"
            },
            "rotor_box": {
                "background": "rgba(255, 215, 0, 0.2)",
                "border": "2px solid #ffd700",
                "color": "#ffd700",
                "border_radius": "6px"
            },
            "model_box": {
                "background": "rgba(128, 100, 128, 0.3)",
                "border": "2px solid #806480",
                "color": "#c0a0c0",
                "border_radius": "6px"
            },
            "ring_settings_box": {
                "background": "rgba(100, 120, 150, 0.3)",
                "border": "2px solid #647896",
                "color": "#90a8c8",
                "border_radius": "6px"
            },
            "ring_position_box": {
                "background": "rgba(120, 150, 160, 0.3)",
                "border": "2px solid #7896a0",
                "color": "#a0c0d0",
                "border_radius": "6px"
            },
            "plugboard_box": {
                "background": "rgba(150, 100, 120, 0.3)",
                "border": "2px solid #966478",
                "color": "#c890a8",
                "border_radius": "6px"
            },
            "plugboard_unused": {
                "background": "rgba(100, 100, 100, 0.2)",
                "border": "#666",
                "color": "#888",
                "opacity": 0.4
            },
            "char_box": {
                "background": "rgba(0, 255, 255, 0.2)",
                "border": "3px solid #0ff",
                "border_radius": "15px",
                "box_shadow": "0 4px 16px rgba(0, 255, 255, 0.3)"
            }
        },
        "text": {
            "config_label": {
                "color": "#ffd700"
            },
            "config_value": {
                "color": "#fff"
            },
            "message_label": {
                "color": "#0ff"
            },
            "message_text": {
                "color": "#fff"
            },
            "encoded_text": {
                "color": "#00ff80",
                "border_top": "1px solid rgba(0, 255, 128, 0.3)"
            },
            "char_highlight": {
                "background": "#ffd700",
                "color": "#000"
            },
            "char_box_label": {
                "color": "#0ff"
            },
            "char_box_value": {
                "color": "#fff"
            },
            "char_arrow": {
                "color": "#ffd700"
            },
            "footer": {
                "color": "#888"
            }
        },
        "errors": {
            "connection_lost": {
                "background": "rgba(255, 0, 0, 0.95)",
                "border": "2px solid #f00",
                "color": "#fff",
                "box_shadow": "0 4px 20px rgba(255, 0, 0, 0.5), 0 0 20px rgba(255, 0, 0, 0.3)"
            },
            "device_disconnected": {
                "background": "rgba(255, 140, 0, 0.95)",
                "border": "2px solid #ff8c00",
                "color": "#fff",
                "box_shadow": "0 4px 20px rgba(255, 140, 0, 0.5), 0 0 20px rgba(255, 140, 0, 0.3)"
            }
        },
        "fonts": {
            "primary": "'Arial', sans-serif",
            "monospace": "'Courier New', monospace"
        }
    }


class ThemeConfigManager:
    """Manages theme configuration file load operations"""
    
    def __init__(self, theme_file: str = KIOSK_THEME_FILE):
        self.theme_file = theme_file
        self._theme = None
    
    def load_theme(self) -> Dict[str, Any]:
        """Load theme configuration from file with fallback to defaults
        
        Returns:
            Dictionary with theme configuration values
        """
        if self._theme is not None:
            return self._theme
        
        default_theme = get_default_theme()
        
        try:
            if os.path.exists(self.theme_file):
                with open(self.theme_file, 'r') as f:
                    loaded_theme = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._theme = self._merge_theme(default_theme, loaded_theme)
            else:
                self._theme = default_theme
        except Exception:
            # If file is corrupted or can't be read, use defaults
            self._theme = default_theme
        
        return self._theme
    
    def _merge_theme(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge loaded theme with defaults"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_theme(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_theme(self) -> Dict[str, Any]:
        """Get current theme configuration"""
        if self._theme is None:
            return self.load_theme()
        return self._theme
