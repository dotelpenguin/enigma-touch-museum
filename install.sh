#!/bin/bash
#
# Installation script for Enigma Museum Controller on Raspberry Pi 2 (Raspbian Lite)
# This script installs required dependencies and optionally sets up auto-start
#
# Usage:
#   ./install.sh          - Install the application
#   ./install.sh --uninstall  - Remove custom changes (bashrc entries, etc.)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Error: Do not run this script as root/sudo${NC}"
   echo "This script will prompt for sudo when needed."
   exit 1
fi

# Check for help flag
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Enigma Museum Controller - Installation Script"
    echo ""
    echo "Usage:"
    echo "  ./install.sh              Install the application and dependencies"
    echo "  ./install.sh --uninstall  Remove custom changes (bashrc entries, etc.)"
    echo "  ./install.sh --help       Show this help message"
    echo ""
    echo "Installation will:"
    echo "  - Check for desktop environment (warns if detected)"
    echo "  - Install Python 3 and pip3 (if needed)"
    echo "  - Install pyserial library"
    echo "  - Add user to dialout group for serial device access"
    echo "  - Create startup script (start-enigma-museum.sh)"
    echo "  - Configure default museum mode (Encode/Decode - EN/DE)"
    echo "  - Optionally enable console auto-login (recommended for kiosk)"
    echo "  - Optionally add auto-start to ~/.bashrc"
    echo ""
    echo "Uninstall will:"
    echo "  - Remove startup script entries from ~/.bashrc"
    echo "  - Optionally remove startup script file"
    echo "  - Optionally disable console auto-login"
    echo "  - Optionally remove user from dialout group"
    echo "  - Optionally uninstall pyserial"
    echo ""
    exit 0
fi

# Check for uninstall flag
if [ "$1" == "--uninstall" ] || [ "$1" == "-u" ]; then
    # Disable exit on error for uninstall (we want to continue even if some steps fail)
    set +e
    
    # Uninstall mode
    echo -e "${YELLOW}Enigma Museum Controller - Uninstall${NC}"
    echo "=========================================="
    echo ""
    
    # Function to remove bashrc entries
    remove_bashrc_entries() {
        if grep -q "Enigma Museum Controller" ~/.bashrc 2>/dev/null; then
            echo -e "${YELLOW}Removing startup script from ~/.bashrc...${NC}"
            sed -i '/# Enigma Museum Controller/,/^fi$/d' ~/.bashrc 2>/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Removed startup script entries from ~/.bashrc${NC}"
            else
                echo -e "${RED}Error: Could not remove entries from ~/.bashrc${NC}"
            fi
        else
            echo "No startup script entries found in ~/.bashrc"
        fi
    }
    
    # Function to remove startup script file
    remove_startup_script() {
        STARTUP_SCRIPT="$SCRIPT_DIR/start-enigma-museum.sh"
        if [ -f "$STARTUP_SCRIPT" ]; then
            echo -e "${YELLOW}Startup script found: $STARTUP_SCRIPT${NC}"
            read -p "Remove startup script file? (y/n): " remove_script
            if [[ "${remove_script,,}" == "y" ]]; then
                rm -f "$STARTUP_SCRIPT"
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}Removed startup script file${NC}"
                else
                    echo -e "${RED}Error: Could not remove startup script file${NC}"
                fi
            else
                echo "Keeping startup script file"
            fi
        else
            echo "Startup script file not found"
        fi
    }
    
    # Function to handle dialout group removal
    handle_dialout_group() {
        if groups | grep -q "\bdialout\b"; then
            echo -e "${YELLOW}User is currently in dialout group${NC}"
            echo -e "${RED}Warning: Removing from dialout group may affect other applications${NC}"
            echo "that need serial port access (e.g., Arduino, other USB serial devices)"
            read -p "Remove user from dialout group? (y/n): " remove_dialout
            if [[ "${remove_dialout,,}" == "y" ]]; then
                # Try gpasswd first, fall back to deluser if needed
                sudo gpasswd -d $USER dialout 2>/dev/null
                if [ $? -ne 0 ]; then
                    # Try alternative method
                    sudo deluser $USER dialout 2>/dev/null
                    if [ $? -eq 0 ]; then
                        echo -e "${GREEN}Removed user from dialout group${NC}"
                        echo -e "${YELLOW}Note: You may need to log out and back in for this to take effect${NC}"
                    else
                        echo -e "${YELLOW}Warning: Could not remove from dialout group${NC}"
                        echo "You may need to manually edit /etc/group"
                    fi
                else
                    echo -e "${GREEN}Removed user from dialout group${NC}"
                    echo -e "${YELLOW}Note: You may need to log out and back in for this to take effect${NC}"
                fi
            else
                echo "Keeping dialout group membership"
            fi
        else
            echo "User is not in dialout group"
        fi
    }
    
    # Function to handle pyserial removal
    handle_pyserial() {
        # Check if installed via apt
        if dpkg -l | grep -q "^ii.*python3-serial"; then
            echo -e "${YELLOW}python3-serial is installed via apt${NC}"
            echo -e "${RED}Warning: Removing pyserial may affect other Python applications${NC}"
            echo "that use serial communication"
            read -p "Uninstall python3-serial? (y/n): " remove_pyserial
            if [[ "${remove_pyserial,,}" == "y" ]]; then
                sudo apt-get remove -y python3-serial 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}Uninstalled python3-serial${NC}"
                else
                    echo -e "${YELLOW}Warning: Could not uninstall python3-serial${NC}"
                fi
            else
                echo "Keeping python3-serial installed"
            fi
        # Check if installed via pip
        elif pip3 show pyserial &>/dev/null; then
            echo -e "${YELLOW}pyserial is installed via pip${NC}"
            echo -e "${RED}Warning: Removing pyserial may affect other Python applications${NC}"
            echo "that use serial communication"
            read -p "Uninstall pyserial? (y/n): " remove_pyserial
            if [[ "${remove_pyserial,,}" == "y" ]]; then
                # Try with --break-system-packages first (if it was installed that way)
                pip3 uninstall -y --break-system-packages pyserial 2>/dev/null || \
                pip3 uninstall -y pyserial 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}Uninstalled pyserial${NC}"
                else
                    echo -e "${YELLOW}Warning: Could not uninstall pyserial${NC}"
                    echo "It may have been installed system-wide or via a different method"
                fi
            else
                echo "Keeping pyserial installed"
            fi
        else
            echo "pyserial/python3-serial is not installed (or not found)"
        fi
    }
    
    # Function to disable console auto-login
    disable_console_autologin() {
        echo -e "${YELLOW}Console Auto-Login Configuration${NC}"
        echo "----------------------------------------"
        
        # Check if auto-login is enabled via raspi-config
        if command -v raspi-config &> /dev/null; then
            # Check current boot behaviour (B2 = console autologin)
            CURRENT_BEHAVIOUR=$(sudo raspi-config nonint get_boot_behaviour 2>/dev/null)
            if [ "$CURRENT_BEHAVIOUR" == "2" ]; then
                echo -e "${YELLOW}Console auto-login is currently enabled${NC}"
                read -p "Disable console auto-login? (y/n): " disable_autologin
                if [[ "${disable_autologin,,}" == "y" ]]; then
                    # B1 = Console require password
                    sudo raspi-config nonint do_boot_behaviour B1
                    if [ $? -eq 0 ]; then
                        echo -e "${GREEN}Console auto-login disabled${NC}"
                        echo -e "${YELLOW}Note: Changes will take effect after reboot${NC}"
                    else
                        echo -e "${YELLOW}Warning: Could not disable auto-login via raspi-config${NC}"
                    fi
                else
                    echo "Keeping console auto-login enabled"
                fi
            else
                echo "Console auto-login is not enabled (or configured differently)"
            fi
        else
            # Check for systemd override file
            AUTOLOGIN_FILE="/etc/systemd/system/getty@tty1.service.d/autologin.conf"
            if [ -f "$AUTOLOGIN_FILE" ]; then
                echo -e "${YELLOW}Console auto-login override file found${NC}"
                read -p "Remove console auto-login configuration? (y/n): " remove_autologin
                if [[ "${remove_autologin,,}" == "y" ]]; then
                    sudo rm -f "$AUTOLOGIN_FILE"
                    if [ $? -eq 0 ]; then
                        sudo systemctl daemon-reload
                        echo -e "${GREEN}Console auto-login configuration removed${NC}"
                        echo -e "${YELLOW}Note: Changes will take effect after reboot${NC}"
                    else
                        echo -e "${YELLOW}Warning: Could not remove auto-login configuration${NC}"
                    fi
                else
                    echo "Keeping console auto-login configuration"
                fi
            else
                echo "No console auto-login configuration found"
            fi
        fi
    }
    
    # Perform uninstall steps
    remove_bashrc_entries
    echo ""
    remove_startup_script
    echo ""
    disable_console_autologin
    echo ""
    handle_dialout_group
    echo ""
    handle_pyserial
    echo ""
    echo -e "${GREEN}=========================================="
    echo "Uninstall complete!"
    echo "==========================================${NC}"
    echo ""
    echo "Note: Application files in $SCRIPT_DIR were not removed"
    echo "To completely remove, delete the directory manually"
    echo ""
    exit 0
fi

# Re-enable exit on error for install mode
set -e

# Install mode (default)
echo -e "${GREEN}Enigma Museum Controller - Installation Script${NC}"
echo "=========================================="
echo ""

# Check for desktop environment
check_desktop_environment() {
    if [ -n "$XDG_CURRENT_DESKTOP" ] || [ -n "$DESKTOP_SESSION" ] || [ -n "$GDMSESSION" ]; then
        echo -e "${YELLOW}=========================================="
        echo "Desktop Environment Detected"
        echo "==========================================${NC}"
        echo -e "${RED}Warning: A desktop environment is running${NC}"
        echo ""
        echo "This application is designed for Raspberry Pi OS Lite (console-only)."
        echo "Running with a desktop environment may:"
        echo "  - Consume unnecessary resources"
        echo "  - Interfere with kiosk mode operation"
        echo "  - Require additional configuration"
        echo ""
        echo -e "${YELLOW}Recommendation: Use Raspberry Pi OS Lite for best results${NC}"
        echo ""
        read -p "Continue installation anyway? (y/n): " continue_install
        if [[ "${continue_install,,}" != "y" ]]; then
            echo "Installation cancelled."
            exit 0
        fi
        echo ""
    else
        echo -e "${GREEN}No desktop environment detected - Raspberry Pi OS Lite confirmed${NC}"
        echo ""
    fi
}

# Function to enable console auto-login
enable_console_autologin() {
    echo -e "${YELLOW}Console Auto-Login Configuration${NC}"
    echo "----------------------------------------"
    echo "For kiosk mode, it's recommended to enable console auto-login"
    echo "so the application starts automatically on boot."
    echo ""
    read -p "Enable console auto-login? (y/n): " enable_autologin
    
    if [[ "${enable_autologin,,}" == "y" ]]; then
        # Check if raspi-config is available (Raspberry Pi OS)
        if command -v raspi-config &> /dev/null; then
            echo -e "${YELLOW}Enabling console auto-login using raspi-config...${NC}"
            # B2 = Console autologin
            sudo raspi-config nonint do_boot_behaviour B2
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Console auto-login enabled${NC}"
                echo -e "${YELLOW}Note: Changes will take effect after reboot${NC}"
            else
                echo -e "${RED}Error: Could not enable auto-login via raspi-config${NC}"
                echo "You may need to configure it manually using: sudo raspi-config"
            fi
        else
            # Manual method using systemd override
            echo -e "${YELLOW}raspi-config not found, using manual systemd configuration...${NC}"
            
            AUTOLOGIN_DIR="/etc/systemd/system/getty@tty1.service.d"
            AUTOLOGIN_FILE="$AUTOLOGIN_DIR/autologin.conf"
            
            # Create directory if it doesn't exist
            sudo mkdir -p "$AUTOLOGIN_DIR"
            
            # Create override file
            echo "[Service]" | sudo tee "$AUTOLOGIN_FILE" > /dev/null
            echo "ExecStart=" | sudo tee -a "$AUTOLOGIN_FILE" > /dev/null
            echo "ExecStart=-/sbin/agetty --autologin $USER --noclear %I \$TERM" | sudo tee -a "$AUTOLOGIN_FILE" > /dev/null
            
            if [ $? -eq 0 ]; then
                # Reload systemd
                sudo systemctl daemon-reload
                echo -e "${GREEN}Console auto-login enabled${NC}"
                echo -e "${YELLOW}Note: Changes will take effect after reboot${NC}"
            else
                echo -e "${RED}Error: Could not create systemd override file${NC}"
                echo "You may need to configure it manually"
            fi
        fi
    else
        echo "Skipping auto-login configuration"
        echo -e "${YELLOW}Note: You will need to log in manually each time${NC}"
    fi
    echo ""
}

# Check desktop environment
check_desktop_environment

# Show installation checklist and get confirmation
show_installation_checklist() {
    echo -e "${GREEN}=========================================="
    echo "Installation Checklist"
    echo "==========================================${NC}"
    echo ""
    echo "The following will be performed:"
    echo ""
    echo -e "${YELLOW}Required Steps:${NC}"
    echo "  [✓] Update package list (apt-get update)"
    echo "  [✓] Install Python 3 and pip3 (if not already installed)"
    echo "  [✓] Install pyserial library (via apt python3-serial or pip3)"
    echo "  [✓] Add user to dialout group (for serial device access)"
    echo "  [✓] Set executable permissions on enigma-museum.py"
    echo "  [✓] Create startup script (start-enigma-museum.sh)"
    echo ""
    echo -e "${YELLOW}Configuration Steps (you will be prompted):${NC}"
    echo "  [ ] Select default museum mode (Encode/Decode - EN/DE)"
    echo "  [ ] Enable console auto-login (recommended for kiosk mode)"
    echo "  [ ] Add startup script to ~/.bashrc (for auto-start on login)"
    echo ""
    echo -e "${YELLOW}What the startup script does:${NC}"
    echo "  - Waits 5 seconds for user input on each start"
    echo "  - If key pressed: offers Config mode, Shell, or Museum mode"
    echo "  - If no input: automatically starts Museum mode (using selected default)"
    echo "  - Auto-restarts if application exits (kiosk mode)"
    echo "  - Supports --debug flag for serial communication debugging"
    echo ""
    echo -e "${YELLOW}System Requirements:${NC}"
    echo "  - Raspberry Pi OS Lite (console-only) recommended"
    echo "  - Python 3.x"
    echo "  - Serial device access (USB serial adapter)"
    echo ""
    echo -e "${YELLOW}Note:${NC}"
    echo "  - Some steps require sudo privileges (you will be prompted)"
    echo "  - You may need to log out/in after dialout group addition"
    echo "  - Auto-login changes require a reboot to take effect"
    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo ""
    read -p "Continue with installation? (y/n): " confirm_install
    
    if [[ "${confirm_install,,}" != "y" ]]; then
        echo ""
        echo "Installation cancelled by user."
        exit 0
    fi
    echo ""
}

# Show checklist and get confirmation
show_installation_checklist

# Update package list
echo -e "${YELLOW}[1/8] Updating package list...${NC}"
sudo apt-get update

# Install Python 3 and pip if not already installed
echo -e "${YELLOW}[2/8] Installing Python 3 and pip...${NC}"
if ! command -v python3 &> /dev/null; then
    sudo apt-get install -y python3
else
    echo "Python 3 already installed: $(python3 --version)"
fi

if ! command -v pip3 &> /dev/null; then
    sudo apt-get install -y python3-pip
else
    echo "pip3 already installed: $(pip3 --version)"
fi

# Install pyserial
echo -e "${YELLOW}[3/8] Installing pyserial...${NC}"
# Try installing via apt first (preferred method for system-wide installation)
if apt-cache show python3-serial &>/dev/null; then
    echo "Installing pyserial via apt (python3-serial)..."
    sudo apt-get install -y python3-serial
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}pyserial installed via apt${NC}"
    else
        echo -e "${YELLOW}apt installation failed, trying pip...${NC}"
        # Fall back to pip with --break-system-packages (acceptable for kiosk systems)
        pip3 install --break-system-packages pyserial
    fi
else
    echo "python3-serial not available in apt, installing via pip..."
    # Use --break-system-packages flag for externally managed environments
    # This is acceptable for kiosk systems where system-wide installation is desired
    pip3 install --break-system-packages pyserial
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Trying with --user flag as fallback...${NC}"
        pip3 install --user pyserial || {
            echo -e "${RED}Error: Could not install pyserial${NC}"
            echo "Please install manually: sudo apt-get install python3-serial"
            echo "or: pip3 install --break-system-packages pyserial"
            exit 1
        }
    fi
fi

# Add user to dialout group for serial device access
echo -e "${YELLOW}[4/8] Adding user to dialout group...${NC}"
if groups | grep -q "\bdialout\b"; then
    echo "User already in dialout group"
else
    sudo usermod -a -G dialout $USER
    echo -e "${GREEN}User added to dialout group${NC}"
    echo -e "${YELLOW}Note: You may need to log out and back in for this to take effect${NC}"
fi

# Function to verify and fix serial device permissions
verify_serial_permissions() {
    # Temporarily disable exit on error for this function
    set +e
    
    echo ""
    echo -e "${YELLOW}Verifying serial device permissions...${NC}"
    
    # Check if user is actually in dialout group in current session
    if id -nG 2>/dev/null | grep -q "\bdialout\b"; then
        echo -e "${GREEN}✓ User is in dialout group (current session)${NC}"
    else
        echo -e "${YELLOW}⚠ User is NOT in dialout group in current session${NC}"
        echo -e "${YELLOW}Note: Group membership was added, but requires logout/login to take effect${NC}"
        echo -e "${YELLOW}You can continue installation, but may need to log out/in later for device access${NC}"
        echo ""
    fi
    
    # Check for common serial devices
    SERIAL_DEVICES=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null)
    if [ -z "$SERIAL_DEVICES" ]; then
        echo -e "${YELLOW}No serial devices found (ttyACM* or ttyUSB*)${NC}"
        echo "Make sure your device is connected"
    else
        echo ""
        echo "Found serial devices:"
        for device in $SERIAL_DEVICES; do
            if [ -e "$device" ]; then
                # Use portable stat command (try GNU format first, fall back to POSIX)
                perms=$(stat -c "%a %U:%G" "$device" 2>/dev/null || stat -f "%OLp %Su:%Sg" "$device" 2>/dev/null || echo "unknown")
                echo "  $device - $perms"
                
                # Check if user can read/write
                if [ -r "$device" ] && [ -w "$device" ]; then
                    echo -e "    ${GREEN}✓ Readable and writable${NC}"
                else
                    echo -e "    ${YELLOW}⚠ Permission denied (this is normal if device just connected)${NC}"
                    echo -e "    ${YELLOW}Attempting to fix permissions...${NC}"
                    sudo chmod 666 "$device" 2>/dev/null
                    if [ $? -eq 0 ]; then
                        echo -e "    ${GREEN}✓ Permissions fixed (temporary)${NC}"
                        echo -e "    ${YELLOW}Note: Permissions may reset after device reconnect${NC}"
                    else
                        echo -e "    ${YELLOW}⚠ Could not fix permissions (may need udev rule)${NC}"
                    fi
                fi
            fi
        done
    fi
    
    # Create udev rule for persistent permissions
    echo ""
    echo -e "${YELLOW}Creating udev rule for persistent serial device permissions...${NC}"
    UDEV_RULE="/etc/udev/rules.d/99-enigma-serial.rules"
    
    if [ -f "$UDEV_RULE" ]; then
        echo "Udev rule already exists: $UDEV_RULE"
        echo -e "${YELLOW}Keeping existing udev rule (use --uninstall to remove)${NC}"
        create_udev="n"
    else
        echo -e "${YELLOW}Create udev rule to set serial device permissions?${NC}"
        echo -e "${YELLOW}This will allow dialout group to access USB serial devices${NC}"
        read -t 10 -p "Create udev rule? (y/n) [default: y]: " create_udev || create_udev="y"
    fi
    
    if [[ "${create_udev:-y}" == "y" ]]; then
        if sudo tee "$UDEV_RULE" > /dev/null << 'UDEV_EOF'
# Enigma Museum Controller - Serial device permissions
# Allow dialout group to access USB serial devices
SUBSYSTEM=="tty", ATTRS{idVendor}=="*", ATTRS{idProduct}=="*", MODE="0666", GROUP="dialout"
UDEV_EOF
        then
            echo -e "${GREEN}Udev rule created${NC}"
            echo "Reloading udev rules..."
            sudo udevadm control --reload-rules 2>/dev/null || true
            sudo udevadm trigger 2>/dev/null || true
            echo -e "${GREEN}Udev rules reloaded${NC}"
            echo -e "${YELLOW}Note: You may need to reconnect the device for changes to take effect${NC}"
        else
            echo -e "${YELLOW}Warning: Could not create udev rule (may need sudo)${NC}"
            echo "You can create it manually later if needed"
        fi
    else
        echo "Skipping udev rule creation"
    fi
    
    # Re-enable exit on error
    set -e
}

# Verify serial permissions
verify_serial_permissions

# Make the main script executable
echo -e "${YELLOW}[5/8] Setting permissions...${NC}"
chmod +x "$SCRIPT_DIR/enigma-museum.py"

# Prompt for default museum mode
echo -e "${YELLOW}[6/8] Configuring default museum mode...${NC}"
echo ""
echo "Select the default museum mode:"
echo "  [1] Encode - EN (English encode mode)"
echo "  [2] Decode - EN (English decode mode)"
echo "  [3] Encode - DE (German encode mode)"
echo "  [4] Decode - DE (German decode mode)"
echo ""
read -p "Enter choice (1-4) [default: 1]: " museum_mode_choice

# Set default museum mode based on choice
case "${museum_mode_choice:-1}" in
    1)
        DEFAULT_MUSEUM_MODE="--museum-en-encode"
        MUSEUM_MODE_NAME="Encode - EN"
        ;;
    2)
        DEFAULT_MUSEUM_MODE="--museum-en-decode"
        MUSEUM_MODE_NAME="Decode - EN"
        ;;
    3)
        DEFAULT_MUSEUM_MODE="--museum-de-encode"
        MUSEUM_MODE_NAME="Encode - DE"
        ;;
    4)
        DEFAULT_MUSEUM_MODE="--museum-de-decode"
        MUSEUM_MODE_NAME="Decode - DE"
        ;;
    *)
        echo -e "${YELLOW}Invalid choice, using default: Encode - EN${NC}"
        DEFAULT_MUSEUM_MODE="--museum-en-encode"
        MUSEUM_MODE_NAME="Encode - EN"
        ;;
esac

echo -e "${GREEN}Default museum mode set to: $MUSEUM_MODE_NAME${NC}"
echo ""

# Create startup script
echo -e "${YELLOW}[7/8] Creating startup script...${NC}"
STARTUP_SCRIPT="$SCRIPT_DIR/start-enigma-museum.sh"
cat > "$STARTUP_SCRIPT" << EOF
#!/bin/bash
#
# Startup script for Enigma Museum Controller
# Waits 5 seconds for input, then starts museum mode or config/shell
#

# Get the directory where this script is located
SCRIPT_DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" && pwd )"
APP_SCRIPT="\$SCRIPT_DIR/enigma-museum.py"
DEFAULT_MODE="$DEFAULT_MUSEUM_MODE"

# Function to wait for input with timeout
# Returns: 0 = continue loop, 1 = exit to shell
wait_for_input() {
    local timeout=5
    local input=""
    
    echo ""
    echo "=========================================="
    echo "Enigma Museum Controller"
    echo "=========================================="
    echo "Press any key within \${timeout} seconds to enter config mode or quit to shell"
    echo "Otherwise, museum mode will start automatically..."
    echo ""
    
    # Use read with timeout (non-blocking)
    # -t timeout, -n 1 means read 1 character, -s silent (don't echo)
    read -t \$timeout -n 1 -s input 2>/dev/null || true
    
    if [ -n "\$input" ]; then
        # User pressed a key - clear the input buffer
        while read -t 0.1 -n 1 -s dummy 2>/dev/null; do :; done
        
        echo ""
        echo "Options:"
        echo "  [C]onfig mode - Open configuration menu"
        echo "  [S]hell - Exit to shell"
        echo "  [M]useum mode - Start museum mode"
        echo "  [D]ebug mode - Start museum mode with debug output"
        echo ""
        read -p "Enter choice (C/S/M/D): " choice
        
        case "\${choice,,}" in
            c)
                echo "Starting config mode..."
                python3 "\$APP_SCRIPT" --config
                return 0  # Continue loop (restart)
                ;;
            s)
                echo "Exiting to shell..."
                return 1  # Exit loop
                ;;
            m)
                echo "Starting museum mode..."
                python3 "\$APP_SCRIPT" \$DEFAULT_MODE
                return 0  # Continue loop (restart)
                ;;
            d)
                echo "Starting museum mode with debug..."
                python3 "\$APP_SCRIPT" \$DEFAULT_MODE --debug
                return 0  # Continue loop (restart)
                ;;
            *)
                echo "Invalid choice, starting museum mode..."
                python3 "\$APP_SCRIPT" \$DEFAULT_MODE
                return 0  # Continue loop (restart)
                ;;
        esac
    else
        # Timeout - start museum mode automatically
        echo ""
        echo "Starting museum mode..."
        python3 "\$APP_SCRIPT" \$DEFAULT_MODE
        return 0  # Continue loop (restart)
    fi
}

# Main loop - restart if app exits (kiosk mode)
while true; do
    if ! wait_for_input; then
        # User chose shell, exit loop
        break
    fi
    
    # App exited, wait a moment before restarting
    echo ""
    echo "Application exited. Restarting in 2 seconds..."
    sleep 2
done
EOF

chmod +x "$STARTUP_SCRIPT"
echo -e "${GREEN}Startup script created: $STARTUP_SCRIPT${NC}"

# Configure console auto-login
echo -e "${YELLOW}[8/8] Configuring console auto-login...${NC}"
enable_console_autologin

# Ask if user wants to add to bash profile
echo ""
echo -e "${YELLOW}Setup auto-start on login?${NC}"
read -p "Add startup script to ~/.bashrc? (y/n): " add_to_bashrc

if [[ "${add_to_bashrc,,}" == "y" ]]; then
    # Check if already added
    if grep -q "Enigma Museum Controller" ~/.bashrc 2>/dev/null; then
        echo -e "${YELLOW}Startup script already found in ~/.bashrc${NC}"
        read -p "Replace existing entry? (y/n): " replace
        if [[ "${replace,,}" == "y" ]]; then
            # Remove old entries (find the block and remove it)
            sed -i '/# Enigma Museum Controller/,/^fi$/d' ~/.bashrc
        else
            echo "Keeping existing entry."
            exit 0
        fi
    fi
    
    # Add new entry to bashrc
    {
        echo ""
        echo "# Enigma Museum Controller - Auto-start"
        echo "if [ -z \"\$SSH_CLIENT\" ] && [ -z \"\$SSH_TTY\" ] && [ -z \"\$ENIGMA_MUSEUM_STARTED\" ]; then"
        echo "    export ENIGMA_MUSEUM_STARTED=1"
        echo "    \"$STARTUP_SCRIPT\""
        echo "fi"
    } >> ~/.bashrc
    
    echo -e "${GREEN}Added startup script to ~/.bashrc${NC}"
    echo -e "${YELLOW}Note: Startup will only occur on local login (not SSH)${NC}"
else
    echo "Skipping bashrc setup. You can manually run: $STARTUP_SCRIPT"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Installation complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. If you were added to dialout group, you MUST log out and back in"
echo "     (or run: newgrp dialout) for group membership to take effect"
if command -v raspi-config &> /dev/null || [ -f "/etc/systemd/system/getty@tty1.service.d/autologin.conf" ]; then
    echo "  2. If auto-login was enabled, reboot for it to take effect: sudo reboot"
    echo "  3. Test the application: python3 $SCRIPT_DIR/enigma-museum.py --config"
    echo "  4. Or run the startup script: $STARTUP_SCRIPT"
else
    echo "  2. Test the application: python3 $SCRIPT_DIR/enigma-museum.py --config"
    echo "  3. Or run the startup script: $STARTUP_SCRIPT"
fi
echo ""
echo -e "${YELLOW}Troubleshooting Serial Device Permissions:${NC}"
echo "  If you get 'Permission denied' accessing /dev/ttyACM0:"
echo "  1. Verify group membership: groups (should show 'dialout')"
echo "  2. If not showing, log out and back in, or run: newgrp dialout"
echo "  3. Check device permissions: ls -l /dev/ttyACM*"
echo "  4. Verify udev rule: cat /etc/udev/rules.d/99-enigma-serial.rules"
echo "  5. If device exists but no permissions: sudo chmod 666 /dev/ttyACM0"
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "  - This application is designed for Raspberry Pi OS Lite (console-only)"
echo "  - For kiosk mode, enable console auto-login and add startup to ~/.bashrc"
echo "  - The application will auto-restart if it exits (kiosk mode)"
echo ""
echo -e "${YELLOW}Command-Line Options:${NC}"
echo "  --config, -c              Open configuration menu without connecting"
echo "  --museum-en-encode        Start in Encode - EN mode (English encode)"
echo "  --museum-en-decode        Start in Decode - EN mode (English decode)"
echo "  --museum-de-encode        Start in Encode - DE mode (German encode)"
echo "  --museum-de-decode        Start in Decode - DE mode (German decode)"
echo "  --debug                   Enable debug output panel"
echo "  DEVICE                    Serial device path (e.g., /dev/ttyACM0)"
echo ""
echo "Examples:"
echo "  python3 enigma-museum.py --config"
echo "  python3 enigma-museum.py --museum-en-encode"
echo "  python3 enigma-museum.py --museum-de-decode /dev/ttyUSB0"
echo "  python3 enigma-museum.py --debug /dev/ttyACM0"
echo ""
echo "To remove auto-start, run: ./install.sh --uninstall"
echo ""

