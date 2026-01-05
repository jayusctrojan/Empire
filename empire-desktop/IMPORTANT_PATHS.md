# IMPORTANT: Empire Desktop Build Paths

## Source Code Location (where you edit)
```
/Users/jaybajaj/Library/Mobile Documents/com~apple~CloudDocs/Documents/ai/Empire/empire-desktop
```

## Built App Location (where the .app goes)
```
/Users/jaybajaj/Documents/ai/Empire/empire-desktop/src-tauri/target/release/bundle/macos
```

## Build Process
1. Build the app in the source directory
2. Copy the built `.app` to the macos folder above

## Why Two Locations?
- Source code is in iCloud Documents (synced)
- Built app is in local Documents folder (not synced, for running)

## Quick Command to Copy Built App
```bash
cp -R "src-tauri/target/release/bundle/macos/Empire Desktop.app" "/Users/jaybajaj/Documents/ai/Empire/empire-desktop/src-tauri/target/release/bundle/macos/"
```
