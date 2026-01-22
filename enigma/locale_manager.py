#!/usr/bin/env python3
"""
Locale/language management for Kiosk display
"""

import json
import os
from typing import Dict, Any, Optional
from .constants import LOCALES_DIR, DEFAULT_LOCALE


def get_default_locale() -> Dict[str, Any]:
    """Get default English locale strings"""
    return {
        "page_title": "Enigma Museum Kiosk",
        "labels": {
            "model": "Model",
            "rotors": "Rotors",
            "ring_settings": "Ring Settings",
            "ring_position": "Ring Position",
            "plugboard": "Plugboard",
            "unused": "Unused"
        },
        "messages": {
            "current_message": "Current Message",
            "encoded_message": "Encoded Message",
            "decoded_message": "Decoded Message",
            "waiting_for_message": "Waiting for message...",
            "slide_image_placeholder": "Slide Image Placeholder"
        },
        "interactive": {
            "received": "Received",
            "encoded": "Encoded"
        },
        "logo": {
            "enigma": "ENIGMA",
            "subtitle": "Cipher Machine",
            "alt_text": "Enigma Machine"
        },
        "errors": {
            "connection_lost": "Connection Lost",
            "device_disconnected": "Enigma Touch Device Disconnected",
            "attempting_reconnect": "Attempting to reconnect...",
            "connection_lost_message": "Connection lost. Please check the Museum Kiosk Controller. Attempting to reconnect...",
            "device_disconnected_message": "Please reconnect the Enigma Touch device or turn it back on.",
            "connection_error": "Connection Error",
            "timeout": "Timeout",
            "timeout_message": "Request timed out after 5 seconds",
            "server_error": "Server Error",
            "server_error_message": "Server returned an error",
            "network_error": "Network Error",
            "network_error_message": "Network connection failed",
            "unable_to_reach_server": "Unable to reach server"
        },
        "footer": {
            "text": "Museum Display {VERSION} - by Andrew Baker (DotelPenguin)"
        }
    }


class LocaleManager:
    """Manages locale/language file load operations"""
    
    def __init__(self, locales_dir: str = LOCALES_DIR, language: str = DEFAULT_LOCALE):
        self.locales_dir = locales_dir
        self.language = language
        self._locale = None
        self._locale_cache = {}  # Cache for multiple languages
    
    def load_locale(self, language: Optional[str] = None) -> Dict[str, Any]:
        """Load locale strings from file with fallback to defaults
        
        Args:
            language: Language code to load (defaults to self.language)
        
        Returns:
            Dictionary with locale strings
        """
        if language is None:
            language = self.language
        
        # Check cache first
        if language in self._locale_cache:
            return self._locale_cache[language]
        
        default_locale = get_default_locale()
        
        try:
            locale_file = os.path.join(self.locales_dir, f"{language}.json")
            if os.path.exists(locale_file):
                with open(locale_file, 'r', encoding='utf-8') as f:
                    loaded_locale = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    merged_locale = self._merge_locale(default_locale, loaded_locale)
                    # Cache the result
                    self._locale_cache[language] = merged_locale
                    return merged_locale
            else:
                # Fallback to English if requested language not found
                if language != DEFAULT_LOCALE:
                    return self.load_locale(DEFAULT_LOCALE)
                # Cache default locale
                self._locale_cache[DEFAULT_LOCALE] = default_locale
                return default_locale
        except Exception:
            # If file is corrupted or can't be read, use defaults
            if language != DEFAULT_LOCALE:
                return self.load_locale(DEFAULT_LOCALE)
            # Cache default locale
            self._locale_cache[DEFAULT_LOCALE] = default_locale
            return default_locale
    
    def _merge_locale(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge loaded locale with defaults"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_locale(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_locale(self) -> Dict[str, Any]:
        """Get current locale strings"""
        if self._locale is None:
            return self.load_locale()
        return self._locale
    
    def get_string(self, key_path: str, default: Optional[str] = None) -> str:
        """Get a localized string by dot-separated key path
        
        Args:
            key_path: Dot-separated path (e.g., "labels.model" or "errors.connection_lost")
            default: Default value if key not found
        
        Returns:
            Localized string or default
        """
        locale = self.get_locale()
        keys = key_path.split('.')
        value = locale
        
        try:
            for key in keys:
                value = value[key]
            return value if isinstance(value, str) else (default or key_path)
        except (KeyError, TypeError):
            return default or key_path
