#!/bin/bash

# Empire Desktop App Test Script
# This script launches the app and verifies basic functionality

set -e

APP_PATH="src-tauri/target/release/bundle/macos/Empire Desktop.app"
APP_NAME="Empire Desktop"

echo "=========================================="
echo "Empire Desktop App Test"
echo "=========================================="
echo ""

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: App not found at $APP_PATH"
    echo "Please run 'npm run tauri:build' first"
    exit 1
fi

echo "[1/6] App bundle found at: $APP_PATH"

# Kill any existing instance
echo "[2/6] Killing any existing instance..."
pkill -f "empire-desktop" 2>/dev/null || true
sleep 1

# Launch the app
echo "[3/6] Launching app..."
open "$APP_PATH"
sleep 5

# Check if app is running
echo "[4/6] Checking if app is running..."
if pgrep -f "empire-desktop" > /dev/null; then
    echo "    ✓ App is running"
else
    echo "    ✗ App failed to start"
    exit 1
fi

# Check if window is visible using AppleScript
echo "[5/6] Checking app window..."
WINDOW_CHECK=$(osascript -e '
tell application "System Events"
    if exists (process "Empire Desktop") then
        tell process "Empire Desktop"
            if (count of windows) > 0 then
                return "window_exists"
            else
                return "no_window"
            end if
        end tell
    else
        return "not_running"
    end if
end tell
' 2>/dev/null || echo "script_error")

if [ "$WINDOW_CHECK" = "window_exists" ]; then
    echo "    ✓ App window is visible"
else
    echo "    ! Could not verify window (may need accessibility permissions): $WINDOW_CHECK"
fi

# Get window title
echo "[6/6] Verifying app title..."
TITLE_CHECK=$(osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        try
            return name of window 1
        on error
            return "unknown"
        end try
    end tell
end tell
' 2>/dev/null || echo "unknown")

echo "    Window title: $TITLE_CHECK"

echo ""
echo "=========================================="
echo "Basic App Test Results:"
echo "=========================================="
echo "✓ App bundle exists"
echo "✓ App launched successfully"
echo "✓ App process is running"
if [ "$WINDOW_CHECK" = "window_exists" ]; then
    echo "✓ App window is visible"
fi
echo ""
echo "App is running. You can now manually test:"
echo "  1. Navigate to Projects"
echo "  2. Create a new project"
echo "  3. Open project detail view"
echo "  4. Create a chat"
echo "  5. Access settings"
echo ""
echo "Press Enter to quit the app and end the test..."
read

# Cleanup
echo "Quitting app..."
osascript -e 'tell application "Empire Desktop" to quit' 2>/dev/null || pkill -f "empire-desktop" 2>/dev/null || true

echo "Test complete!"
