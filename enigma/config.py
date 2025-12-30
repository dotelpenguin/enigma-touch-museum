#!/usr/bin/env python3
"""
Configuration management for Enigma Museum Controller
"""

import json
import os
from typing import Dict, Any, Optional
from .constants import CONFIG_FILE

# List of all boolean configuration fields
BOOLEAN_FIELDS = [
    'always_send_config',
    'web_server_enabled',
    'enable_slides',
    'lock_model',
    'lock_rotor',
    'lock_ring',
    'disable_power_off',
    'use_models_json'
]


def normalize_boolean(value: Any) -> bool:
    """Normalize a value to a proper boolean (True/False)
    
    Handles:
    - Python booleans (True/False)
    - JSON booleans (true/false) - already converted by json.load
    - Strings ("true", "false", "True", "False", "1", "0", "yes", "no")
    - Integers (1, 0)
    
    Args:
        value: Value to normalize
        
    Returns:
        bool: Normalized boolean value
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    if isinstance(value, (int, float)):
        return bool(value)
    # Default to False for unknown types
    return False


class ConfigManager:
    """Manages configuration file save/load operations"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
    
    def save_config(self, config_data: Dict[str, Any], preserve_ring_position: bool = True, preserve_cipher_config: bool = False) -> bool:
        """Save configuration to file
        
        Args:
            config_data: Dictionary containing all config values
            preserve_ring_position: If True, preserve ring_position from saved config
                                   (prevents encoding updates from being saved).
                                   Set to False when explicitly setting ring position.
            preserve_cipher_config: If True, preserve cipher config (mode, rotor_set, ring_settings, pegboard)
                                   from saved config (prevents museum mode changes from being saved).
                                   Set to False when explicitly setting cipher config.
        
        Returns:
            True if save succeeded, False otherwise
        """
        try:
            config_to_save = config_data['config'].copy()
            
            # If preserving cipher config or ring position, get saved config once
            if preserve_cipher_config or preserve_ring_position:
                saved = self.get_saved_config(config_data)
                saved_config = saved.get('config', {})
                
                # If preserving cipher config, use the saved values instead of current
                # Only preserve cipher settings (mode, rotor_set, ring_settings, pegboard)
                # NOT device, raw_debug_enabled, use_models_json (those should be saved)
                if preserve_cipher_config:
                    if saved_config.get('mode'):
                        config_to_save['mode'] = saved_config['mode']
                    if saved_config.get('rotor_set'):
                        config_to_save['rotor_set'] = saved_config['rotor_set']
                    if saved_config.get('ring_settings'):
                        config_to_save['ring_settings'] = saved_config['ring_settings']
                    if saved_config.get('pegboard') is not None:
                        config_to_save['pegboard'] = saved_config['pegboard']
                
                # If preserving ring position, use the saved value instead of current
                if preserve_ring_position:
                    saved_ring_position = saved_config.get('ring_position')
                    if saved_ring_position:
                        config_to_save['ring_position'] = saved_ring_position
            
            # Build config object with cipher settings and related fields
            config_obj = config_to_save.copy()
            # Add device, raw_debug_enabled, use_models_json to config object
            if 'device' in config_data:
                config_obj['device'] = config_data['device']
            if 'raw_debug_enabled' in config_data:
                config_obj['raw_debug_enabled'] = normalize_boolean(config_data['raw_debug_enabled'])
            if 'use_models_json' in config_data:
                config_obj['use_models_json'] = normalize_boolean(config_data.get('use_models_json', False))
            
            # Build museum_config object
            museum_config = {
                'function_mode': config_data['function_mode'],
                'museum_delay': config_data['museum_delay'],
                'always_send_config': normalize_boolean(config_data['always_send_config']),
                'word_group_size': config_data['word_group_size'],
                'character_delay_ms': config_data['character_delay_ms'],
                'web_server_enabled': normalize_boolean(config_data['web_server_enabled']),
                'web_server_port': config_data['web_server_port'],
                'enable_slides': normalize_boolean(config_data['enable_slides'])
            }
            
            # Build touch_config object
            touch_config = {
                'lock_model': normalize_boolean(config_data['lock_model']),
                'lock_rotor': normalize_boolean(config_data['lock_rotor']),
                'lock_ring': normalize_boolean(config_data['lock_ring']),
                'disable_power_off': normalize_boolean(config_data['disable_power_off']),
                'brightness': config_data['brightness'],
                'volume': config_data['volume'],
                'screen_saver': config_data.get('screen_saver', config_data.get('timeout_screen_saver', 0)),
                'timeout_battery': config_data.get('timeout_battery', 15),
                'timeout_plugged': config_data.get('timeout_plugged', 0),
                'timeout_setup_modes': config_data.get('timeout_setup_modes', 0)
            }
            
            # Build final save structure
            save_data = {
                'config': config_obj,
                'museum_config': museum_config,
                'touch_config': touch_config
            }
            with open(self.config_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            return True
        except Exception:
            return False
    
    def load_config(self, default_config: Dict[str, Any], preserve_device: bool = False) -> Dict[str, Any]:
        """Load configuration from file
        
        Args:
            default_config: Dictionary with default values to use if file doesn't exist
            preserve_device: If True, don't overwrite device from config file
        
        Returns:
            Dictionary with loaded config values
        """
        result = default_config.copy()
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    # Update config if present (cipher settings + device, raw_debug_enabled, use_models_json)
                    if 'config' in config_data:
                        config_obj = config_data['config'].copy()
                        # Extract device, raw_debug_enabled, use_models_json from config object if present
                        if 'device' in config_obj and not preserve_device:
                            result['device'] = config_obj.pop('device')
                        if 'raw_debug_enabled' in config_obj:
                            result['raw_debug_enabled'] = normalize_boolean(config_obj.pop('raw_debug_enabled'))
                        if 'use_models_json' in config_obj:
                            result['use_models_json'] = normalize_boolean(config_obj.pop('use_models_json'))
                        # Update config with remaining cipher settings only
                        result['config'].update(config_obj)
                    
                    # Update museum_config if present
                    if 'museum_config' in config_data:
                        museum_cfg = config_data['museum_config']
                        if 'function_mode' in museum_cfg:
                            result['function_mode'] = museum_cfg['function_mode']
                        if 'museum_delay' in museum_cfg:
                            result['museum_delay'] = museum_cfg['museum_delay']
                        if 'always_send_config' in museum_cfg:
                            result['always_send_config'] = normalize_boolean(museum_cfg['always_send_config'])
                        if 'word_group_size' in museum_cfg:
                            result['word_group_size'] = museum_cfg['word_group_size']
                        if 'character_delay_ms' in museum_cfg:
                            result['character_delay_ms'] = museum_cfg['character_delay_ms']
                        if 'web_server_enabled' in museum_cfg:
                            result['web_server_enabled'] = normalize_boolean(museum_cfg['web_server_enabled'])
                        if 'web_server_port' in museum_cfg:
                            result['web_server_port'] = museum_cfg['web_server_port']
                        if 'enable_slides' in museum_cfg:
                            result['enable_slides'] = normalize_boolean(museum_cfg['enable_slides'])
                    
                    # Update touch_config if present
                    if 'touch_config' in config_data:
                        touch_cfg = config_data['touch_config']
                        if 'lock_model' in touch_cfg:
                            result['lock_model'] = normalize_boolean(touch_cfg['lock_model'])
                        if 'lock_rotor' in touch_cfg:
                            result['lock_rotor'] = normalize_boolean(touch_cfg['lock_rotor'])
                        if 'lock_ring' in touch_cfg:
                            result['lock_ring'] = normalize_boolean(touch_cfg['lock_ring'])
                        if 'disable_power_off' in touch_cfg:
                            result['disable_power_off'] = normalize_boolean(touch_cfg['disable_power_off'])
                        if 'brightness' in touch_cfg:
                            result['brightness'] = touch_cfg['brightness']
                        if 'volume' in touch_cfg:
                            result['volume'] = touch_cfg['volume']
                        if 'screen_saver' in touch_cfg:
                            result['screen_saver'] = touch_cfg['screen_saver']
                        if 'timeout_battery' in touch_cfg:
                            result['timeout_battery'] = touch_cfg['timeout_battery']
                        if 'timeout_plugged' in touch_cfg:
                            result['timeout_plugged'] = touch_cfg['timeout_plugged']
                        if 'timeout_setup_modes' in touch_cfg:
                            result['timeout_setup_modes'] = touch_cfg['timeout_setup_modes']
                    
                    # Backward compatibility: check for old flat structure
                    if 'function_mode' in config_data:
                        result['function_mode'] = config_data['function_mode']
                    if 'museum_delay' in config_data:
                        result['museum_delay'] = config_data['museum_delay']
                    if 'always_send_config' in config_data:
                        result['always_send_config'] = normalize_boolean(config_data['always_send_config'])
                    if 'word_group_size' in config_data:
                        result['word_group_size'] = config_data['word_group_size']
                    if 'character_delay_ms' in config_data:
                        result['character_delay_ms'] = config_data['character_delay_ms']
                    if 'web_server_enabled' in config_data:
                        result['web_server_enabled'] = normalize_boolean(config_data['web_server_enabled'])
                    if 'web_server_port' in config_data:
                        result['web_server_port'] = config_data['web_server_port']
                    if 'enable_slides' in config_data:
                        result['enable_slides'] = normalize_boolean(config_data['enable_slides'])
                    if 'lock_model' in config_data:
                        result['lock_model'] = normalize_boolean(config_data['lock_model'])
                    if 'lock_rotor' in config_data:
                        result['lock_rotor'] = normalize_boolean(config_data['lock_rotor'])
                    if 'lock_ring' in config_data:
                        result['lock_ring'] = normalize_boolean(config_data['lock_ring'])
                    if 'disable_power_off' in config_data:
                        result['disable_power_off'] = normalize_boolean(config_data['disable_power_off'])
                    if 'use_models_json' in config_data:
                        result['use_models_json'] = normalize_boolean(config_data['use_models_json'])
                    if 'brightness' in config_data:
                        result['brightness'] = config_data['brightness']
                    if 'volume' in config_data:
                        result['volume'] = config_data['volume']
                    if 'screen_saver' in config_data:
                        result['screen_saver'] = config_data['screen_saver']
                    if 'timeout_battery' in config_data:
                        result['timeout_battery'] = config_data['timeout_battery']
                    if 'timeout_plugged' in config_data:
                        result['timeout_plugged'] = config_data['timeout_plugged']
                    if 'timeout_setup_modes' in config_data:
                        result['timeout_setup_modes'] = config_data['timeout_setup_modes']
                    if 'device' in config_data and not preserve_device:
                        result['device'] = config_data['device']
                    if 'raw_debug_enabled' in config_data:
                        result['raw_debug_enabled'] = normalize_boolean(config_data['raw_debug_enabled'])
        except Exception:
            # If config file is corrupted or doesn't exist, use defaults
            pass
        return result
    
    def get_saved_config(self, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get saved configuration from file (without modifying in-memory config)
        
        Args:
            current_config: Current in-memory config to use as fallback
        
        Returns:
            Dictionary with saved config values
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    saved_config = {}
                    
                    # Load config object (cipher settings + device, raw_debug_enabled, use_models_json)
                    if 'config' in config_data:
                        config_obj = config_data['config'].copy()
                        # Extract device, raw_debug_enabled, use_models_json from config object
                        if 'device' in config_obj:
                            saved_config['device'] = config_obj.pop('device')
                        if 'raw_debug_enabled' in config_obj:
                            saved_config['raw_debug_enabled'] = normalize_boolean(config_obj.pop('raw_debug_enabled'))
                        if 'use_models_json' in config_obj:
                            saved_config['use_models_json'] = normalize_boolean(config_obj.pop('use_models_json'))
                        # Save remaining cipher settings only
                        saved_config['config'] = config_obj
                    else:
                        saved_config['config'] = current_config['config'].copy()  # Fallback to defaults
                    
                    # Load museum_config
                    if 'museum_config' in config_data:
                        museum_cfg = config_data['museum_config']
                        saved_config['function_mode'] = museum_cfg.get('function_mode', current_config['function_mode'])
                        saved_config['museum_delay'] = museum_cfg.get('museum_delay', current_config['museum_delay'])
                        saved_config['always_send_config'] = normalize_boolean(museum_cfg.get('always_send_config', current_config['always_send_config']))
                        saved_config['word_group_size'] = museum_cfg.get('word_group_size', current_config['word_group_size'])
                        saved_config['character_delay_ms'] = museum_cfg.get('character_delay_ms', current_config['character_delay_ms'])
                        saved_config['web_server_enabled'] = normalize_boolean(museum_cfg.get('web_server_enabled', current_config['web_server_enabled']))
                        saved_config['web_server_port'] = museum_cfg.get('web_server_port', current_config['web_server_port'])
                        saved_config['enable_slides'] = normalize_boolean(museum_cfg.get('enable_slides', current_config['enable_slides']))
                    else:
                        # Fallback to old structure or defaults
                        saved_config['function_mode'] = config_data.get('function_mode', current_config['function_mode'])
                        saved_config['museum_delay'] = config_data.get('museum_delay', current_config['museum_delay'])
                        saved_config['always_send_config'] = normalize_boolean(config_data.get('always_send_config', current_config['always_send_config']))
                        saved_config['word_group_size'] = config_data.get('word_group_size', current_config['word_group_size'])
                        saved_config['character_delay_ms'] = config_data.get('character_delay_ms', current_config['character_delay_ms'])
                        saved_config['web_server_enabled'] = normalize_boolean(config_data.get('web_server_enabled', current_config['web_server_enabled']))
                        saved_config['web_server_port'] = config_data.get('web_server_port', current_config['web_server_port'])
                        saved_config['enable_slides'] = normalize_boolean(config_data.get('enable_slides', current_config['enable_slides']))
                    
                    # Load touch_config
                    if 'touch_config' in config_data:
                        touch_cfg = config_data['touch_config']
                        saved_config['lock_model'] = normalize_boolean(touch_cfg.get('lock_model', current_config['lock_model']))
                        saved_config['lock_rotor'] = normalize_boolean(touch_cfg.get('lock_rotor', current_config['lock_rotor']))
                        saved_config['lock_ring'] = normalize_boolean(touch_cfg.get('lock_ring', current_config['lock_ring']))
                        saved_config['disable_power_off'] = normalize_boolean(touch_cfg.get('disable_power_off', current_config['disable_power_off']))
                        saved_config['brightness'] = touch_cfg.get('brightness', current_config['brightness'])
                        saved_config['volume'] = touch_cfg.get('volume', current_config['volume'])
                        saved_config['screen_saver'] = touch_cfg.get('screen_saver', current_config.get('screen_saver', 0))
                        saved_config['timeout_battery'] = touch_cfg.get('timeout_battery', current_config.get('timeout_battery', 15))
                        saved_config['timeout_plugged'] = touch_cfg.get('timeout_plugged', current_config.get('timeout_plugged', 0))
                        saved_config['timeout_setup_modes'] = touch_cfg.get('timeout_setup_modes', current_config.get('timeout_setup_modes', 0))
                    else:
                        # Fallback to old structure or defaults
                        saved_config['lock_model'] = normalize_boolean(config_data.get('lock_model', current_config['lock_model']))
                        saved_config['lock_rotor'] = normalize_boolean(config_data.get('lock_rotor', current_config['lock_rotor']))
                        saved_config['lock_ring'] = normalize_boolean(config_data.get('lock_ring', current_config['lock_ring']))
                        saved_config['disable_power_off'] = normalize_boolean(config_data.get('disable_power_off', current_config['disable_power_off']))
                        saved_config['brightness'] = config_data.get('brightness', current_config['brightness'])
                        saved_config['volume'] = config_data.get('volume', current_config['volume'])
                        saved_config['screen_saver'] = config_data.get('screen_saver', current_config.get('screen_saver', 0))
                        saved_config['timeout_battery'] = config_data.get('timeout_battery', current_config.get('timeout_battery', 15))
                        saved_config['timeout_plugged'] = config_data.get('timeout_plugged', current_config.get('timeout_plugged', 0))
                        saved_config['timeout_setup_modes'] = config_data.get('timeout_setup_modes', current_config.get('timeout_setup_modes', 0))
                    
                    # Backward compatibility: check for device, raw_debug_enabled, use_models_json at top level
                    if 'device' not in saved_config:
                        saved_config['device'] = config_data.get('device', current_config['device'])
                    if 'raw_debug_enabled' not in saved_config:
                        saved_config['raw_debug_enabled'] = normalize_boolean(config_data.get('raw_debug_enabled', current_config.get('raw_debug_enabled', False)))
                    if 'use_models_json' not in saved_config:
                        saved_config['use_models_json'] = normalize_boolean(config_data.get('use_models_json', current_config.get('use_models_json', False)))
                    
                    return saved_config
        except Exception:
            pass
        # Return defaults if file doesn't exist or is corrupted
        return {
            'config': current_config['config'].copy(),
            'function_mode': current_config['function_mode'],
            'lock_model': current_config['lock_model'],
            'lock_rotor': current_config['lock_rotor'],
            'lock_ring': current_config['lock_ring'],
            'disable_power_off': current_config['disable_power_off'],
            'use_models_json': current_config.get('use_models_json', False),
            'brightness': current_config.get('brightness', 3),
            'volume': current_config.get('volume', 0),
            'screen_saver': current_config.get('screen_saver', 0),
            'timeout_battery': current_config.get('timeout_battery', 15),
            'timeout_plugged': current_config.get('timeout_plugged', 0),
            'timeout_setup_modes': current_config.get('timeout_setup_modes', 0),
            'museum_delay': current_config['museum_delay'],
            'always_send_config': current_config['always_send_config'],
            'word_group_size': current_config['word_group_size'],
            'character_delay_ms': current_config['character_delay_ms'],
            'web_server_enabled': current_config['web_server_enabled'],
            'web_server_port': current_config['web_server_port'],
            'enable_slides': current_config['enable_slides'],
            'device': current_config['device'],
            'raw_debug_enabled': current_config.get('raw_debug_enabled', False)
        }

