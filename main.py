#!/usr/bin/env python3
"""
Main entry point for Enigma Museum Controller
"""

import sys
import os
import json
import time
from enigma.constants import DEFAULT_DEVICE, CONFIG_FILE
from enigma.enigma_controller import EnigmaController
from enigma.ui import EnigmaMuseumUI


def print_help():
    """Print help/usage information"""
    script_name = os.path.basename(sys.argv[0])
    help_text = f"""
Enigma Museum Controller - CLI tool for controlling Enigma device

Usage:
    {script_name} [OPTIONS] [DEVICE]

Options:
    --config, -c              Open configuration menu without connecting to device
                              (useful for changing device settings when device is unavailable)
    --museum-en-encode        Start in Encode - EN mode (English encode)
    --museum-en-decode        Start in Decode - EN mode (English decode)
    --museum-de-encode        Start in Encode - DE mode (German encode)
    --museum-de-decode        Start in Decode - DE mode (German decode)
    --debug                   Enable debug output panel (shows serial communication)
    --send-lock-config        Send kiosk/lock settings to device from saved config
                              (⚠️ use with caution - see lockout warning in README)
    --factory-reset           Factory reset the Enigma Touch device
                              (⚠️ resets all settings to factory defaults - requires confirmation)
    --help, -h                Show this help message and exit

Arguments:
    DEVICE                     Serial device path (default: {DEFAULT_DEVICE})
                              Examples: /dev/ttyACM0, /dev/ttyUSB0 (Linux)
                                        /dev/cu.usbserial-1410 (macOS)

Examples:
    {script_name}                        # Run with default device ({DEFAULT_DEVICE})
    {script_name} /dev/ttyUSB0          # Run with specific device
    {script_name} --config               # Open config menu to change settings
    {script_name} --museum-en-encode    # Start directly in Encode - EN mode
    {script_name} --museum-en-decode /dev/ttyACM0  # Start Decode - EN mode with specific device
    {script_name} --museum-de-encode   # Start Encode - DE mode
    {script_name} --museum-de-decode   # Start Decode - DE mode
    {script_name} --send-lock-config   # Send kiosk/lock settings to device
    {script_name} --factory-reset      # Factory reset device (requires confirmation)

Description:
    This tool provides a curses-based menu interface for controlling an Enigma
    device via serial communication. You can send messages, configure settings,
    query device state, and run museum mode demonstrations.

    Museum modes automatically send messages at configured intervals. Encode modes
    send original messages and verify encoded results. Decode modes send coded messages
    and verify decoded results. All modes use JSON files with pre-generated messages.

    If connection fails, use --config to change the device path without
    requiring a connection.
"""
    print(help_text)


def main():
    """Main entry point"""
    device = None
    config_only = False
    museum_mode = None
    debug_enabled = True
    send_lock_config = False
    factory_reset = False
    
    # Parse command line arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg in ('--help', '-h'):
            print_help()
            sys.exit(0)
        elif arg in ('--config', '-c'):
            config_only = True
        elif arg == '--museum-en-encode':
            museum_mode = '1'
        elif arg == '--museum-en-decode':
            museum_mode = '2'
        elif arg == '--museum-de-encode':
            museum_mode = '3'
        elif arg == '--museum-de-decode':
            museum_mode = '4'
        elif arg == '--debug':
            debug_enabled = True
        elif arg == '--send-lock-config':
            send_lock_config = True
        elif arg == '--factory-reset':
            factory_reset = True
        elif arg.startswith('-'):
            print(f"Unknown option: {arg}")
            print("Use --help or -h for usage information.")
            sys.exit(1)
        else:
            device = arg
        i += 1
    
    # If no device specified on command line, load from config file
    if device is None:
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    if 'device' in config_data:
                        device = config_data['device']
        except Exception:
            pass
        if device is None:
            device = DEFAULT_DEVICE
        preserve_device = False
    else:
        preserve_device = True
    
    controller = EnigmaController(device, preserve_device=preserve_device)
    
    # If config-only mode, skip connection and go straight to config menu
    if config_only:
        try:
            ui = EnigmaMuseumUI(controller)
            ui.run(config_only=True, debug_enabled=debug_enabled)
        except KeyboardInterrupt:
            pass
        finally:
            print("\nGoodbye!")
        return
    
    # Normal mode - try to connect
    print(f"Connecting to {controller.device}...")
    if not controller.connect():
        print(f"ERROR: Could not connect to {controller.device}")
        print("Make sure the device is connected and you have permission to access it.")
        print(f"\nTo change the device, run: {sys.argv[0]} --config")
        sys.exit(1)
    
    # Check firmware version
    print("Checking firmware version...")
    if not controller.check_firmware_version():
        print("ERROR: Could not determine firmware version")
        controller.disconnect()
        sys.exit(1)
    
    # Report firmware version
    if controller.firmware_version is not None:
        print(f"Firmware version: {controller.firmware_version:.2f}")
    else:
        print("Firmware version: Unknown")
    
    # Handle --send-lock-config switch
    if send_lock_config:
        print("\nSending kiosk/lock configuration...")
        controller.load_config(preserve_device=True)
        
        def debug_callback(msg, color_type=None):
            print(f"  {msg}")
        
        controller.wakeup_device(debug_callback=debug_callback)
        if controller.apply_kiosk_settings(debug_callback=debug_callback):
            print("✓ Kiosk/lock configuration sent successfully!")
        else:
            print("✗ Error: Failed to apply some kiosk/lock settings")
            controller.disconnect()
            sys.exit(1)
        
        controller.disconnect()
        print("\nDisconnected. Goodbye!")
        return
    
    # Handle --factory-reset switch
    if factory_reset:
        print("\n⚠️  WARNING: This will factory reset the Enigma Touch device!")
        print("All settings will be reset to factory defaults.")
        confirm = input("Continue? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Factory reset cancelled.")
            controller.disconnect()
            sys.exit(0)
        
        print("\nSending factory reset command...")
        
        def debug_callback(msg, color_type=None):
            print(f"  {msg}")
        
        # Send line return, then !RS command with line return
        controller.ser.write(b'\r\n')
        controller.ser.flush()
        time.sleep(0.1)
        
        response = controller.send_command(b'!RS\r\n', debug_callback=debug_callback)
        
        if response is None:
            print("✗ Error: No response from device")
            controller.disconnect()
            sys.exit(1)
        
        has_error, error_message = controller._has_error_response(response)
        if has_error:
            print(f"✗ Error: {error_message}")
            controller.disconnect()
            sys.exit(1)
        else:
            print("✓ Factory reset command sent successfully!")
        
        controller.disconnect()
        print("\nDisconnected. Goodbye!")
        return
    
    print("Connected! Starting UI...")
    time.sleep(1)
    
    try:
        ui = EnigmaMuseumUI(controller)
        ui.run(museum_mode=museum_mode, debug_enabled=debug_enabled)
    except KeyboardInterrupt:
        pass
    finally:
        controller.disconnect()
        print("\nDisconnected. Goodbye!")


if __name__ == '__main__':
    main()

