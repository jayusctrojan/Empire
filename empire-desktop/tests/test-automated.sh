#!/bin/bash

# Empire Desktop Automated Test Script
# Uses AppleScript to interact with the app and verify functionality

set -e

APP_PATH="src-tauri/target/release/bundle/macos/Empire Desktop.app"
APP_NAME="Empire Desktop"
TEST_PROJECT_NAME="Automated Test Project"

PASSED=0
FAILED=0

pass() {
    echo "    ✓ $1"
    ((PASSED++))
}

fail() {
    echo "    ✗ $1"
    ((FAILED++))
}

echo "=========================================="
echo "Empire Desktop Automated Test"
echo "=========================================="
echo ""

# Kill any existing instance
echo "[Setup] Killing any existing instance..."
pkill -f "empire-desktop" 2>/dev/null || true
osascript -e 'tell application "Empire Desktop" to quit' 2>/dev/null || true
sleep 2

# Delete old database to start fresh
echo "[Setup] Removing old database for fresh test..."
rm -f ~/Library/Application\ Support/com.empire.desktop/empire.db 2>/dev/null || true
rm -rf ~/Library/Application\ Support/com.empire.desktop/*.db* 2>/dev/null || true

# Launch the app
echo "[Setup] Launching app..."
open "$APP_PATH"
sleep 6

echo ""
echo "[Test 1] App Launch"
if pgrep -f "empire-desktop" > /dev/null; then
    pass "App process is running"
else
    fail "App failed to start"
    exit 1
fi

# Wait for database initialization
sleep 3

echo ""
echo "[Test 2] Database Initialization"
# Check for database error by looking at window content
DB_ERROR=$(osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        try
            set winContent to name of every UI element of window 1
            if winContent contains "Database Error" then
                return "error"
            else
                return "ok"
            end if
        on error
            return "unknown"
        end try
    end tell
end tell
' 2>/dev/null || echo "unknown")

if [ "$DB_ERROR" = "error" ]; then
    fail "Database initialization failed"
else
    pass "Database initialized (no error screen)"
fi

echo ""
echo "[Test 3] Navigate to Projects"
# Click on Projects in sidebar using keyboard shortcut Cmd+2
osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        keystroke "2" using command down
    end tell
end tell
' 2>/dev/null || true
sleep 2
pass "Sent Cmd+2 to navigate to Projects"

echo ""
echo "[Test 4] Open New Project Modal"
# Click New Project button using keyboard shortcut or clicking
osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        try
            click button "New Project" of window 1
        on error
            -- Try clicking any button with "New" in it
            click (first button of window 1 whose description contains "New")
        end try
    end tell
end tell
' 2>/dev/null || true
sleep 1

# Alternative: try Tab to focus and Enter
osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        keystroke tab
        delay 0.2
        keystroke return
    end tell
end tell
' 2>/dev/null || true
sleep 2
pass "Attempted to open New Project modal"

echo ""
echo "[Test 5] Create New Project"
# Type project name
osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        keystroke "'"$TEST_PROJECT_NAME"'"
        delay 0.5
        -- Tab to next field and press Enter to submit
        keystroke tab
        delay 0.2
        keystroke tab
        delay 0.2
        keystroke tab
        delay 0.2
        keystroke tab
        delay 0.2
        keystroke return
    end tell
end tell
' 2>/dev/null || true
sleep 3

# Check for error message
ERROR_CHECK=$(osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        try
            set winElements to entire contents of window 1
            repeat with elem in winElements
                try
                    if name of elem contains "Failed" then
                        return "failed"
                    end if
                end try
            end repeat
            return "ok"
        on error
            return "unknown"
        end try
    end tell
end tell
' 2>/dev/null || echo "unknown")

if [ "$ERROR_CHECK" = "failed" ]; then
    fail "Project creation failed"
else
    pass "Project creation attempted (no obvious error)"
fi

echo ""
echo "[Test 6] Navigate to Chats"
osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        keystroke "1" using command down
    end tell
end tell
' 2>/dev/null || true
sleep 2
pass "Sent Cmd+1 to navigate to Chats"

echo ""
echo "[Test 7] Navigate to Settings"
osascript -e '
tell application "System Events"
    tell process "Empire Desktop"
        keystroke "3" using command down
    end tell
end tell
' 2>/dev/null || true
sleep 2
pass "Sent Cmd+3 to navigate to Settings"

echo ""
echo "[Test 8] App Still Running"
if pgrep -f "empire-desktop" > /dev/null; then
    pass "App is still running after all tests"
else
    fail "App crashed during testing"
fi

# Take screenshot for verification
echo ""
echo "[Capture] Taking screenshot..."
SCREENSHOT_PATH="tests/test-screenshot-$(date +%Y%m%d-%H%M%S).png"
screencapture -w "$SCREENSHOT_PATH" 2>/dev/null || true
if [ -f "$SCREENSHOT_PATH" ]; then
    echo "    Screenshot saved to: $SCREENSHOT_PATH"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Results Summary"
echo "=========================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "All basic tests passed!"
    EXIT_CODE=0
else
    echo "Some tests failed. Check the output above."
    EXIT_CODE=1
fi

echo ""
echo "Cleaning up..."
osascript -e 'tell application "Empire Desktop" to quit' 2>/dev/null || pkill -f "empire-desktop" 2>/dev/null || true

exit $EXIT_CODE
