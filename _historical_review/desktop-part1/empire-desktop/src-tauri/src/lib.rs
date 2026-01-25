use tauri::{
    Manager,
    menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder, PredefinedMenuItem},
    Emitter,
};
use keyring::Entry;

const KEYCHAIN_SERVICE: &str = "empire-desktop";

/// Simple ping command for testing Rust-TypeScript IPC
#[tauri::command]
fn ping() -> String {
    "pong".to_string()
}

/// Get app version
#[tauri::command]
fn get_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// Store JWT token in system keychain
#[tauri::command]
fn store_jwt(user_id: String, jwt: String) -> Result<(), String> {
    let entry = Entry::new(KEYCHAIN_SERVICE, &user_id)
        .map_err(|e| format!("Failed to create keychain entry: {}", e))?;

    entry
        .set_password(&jwt)
        .map_err(|e| format!("Failed to store JWT in keychain: {}", e))?;

    log::info!("JWT stored in keychain for user: {}", user_id);
    Ok(())
}

/// Retrieve JWT token from system keychain
#[tauri::command]
fn get_jwt(user_id: String) -> Result<Option<String>, String> {
    let entry = Entry::new(KEYCHAIN_SERVICE, &user_id)
        .map_err(|e| format!("Failed to create keychain entry: {}", e))?;

    match entry.get_password() {
        Ok(jwt) => {
            log::info!("JWT retrieved from keychain for user: {}", user_id);
            Ok(Some(jwt))
        }
        Err(keyring::Error::NoEntry) => {
            log::info!("No JWT found in keychain for user: {}", user_id);
            Ok(None)
        }
        Err(e) => Err(format!("Failed to retrieve JWT from keychain: {}", e)),
    }
}

/// Delete JWT token from system keychain
#[tauri::command]
fn delete_jwt(user_id: String) -> Result<(), String> {
    let entry = Entry::new(KEYCHAIN_SERVICE, &user_id)
        .map_err(|e| format!("Failed to create keychain entry: {}", e))?;

    match entry.delete_credential() {
        Ok(()) => {
            log::info!("JWT deleted from keychain for user: {}", user_id);
            Ok(())
        }
        Err(keyring::Error::NoEntry) => {
            log::info!("No JWT to delete for user: {}", user_id);
            Ok(())
        }
        Err(e) => Err(format!("Failed to delete JWT from keychain: {}", e)),
    }
}

/// Check if JWT exists in keychain
#[tauri::command]
fn has_jwt(user_id: String) -> Result<bool, String> {
    let entry = Entry::new(KEYCHAIN_SERVICE, &user_id)
        .map_err(|e| format!("Failed to create keychain entry: {}", e))?;

    match entry.get_password() {
        Ok(_) => Ok(true),
        Err(keyring::Error::NoEntry) => Ok(false),
        Err(e) => Err(format!("Failed to check JWT in keychain: {}", e)),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_window_state::Builder::new().build())
        .plugin(
            tauri_plugin_sql::Builder::default()
                .add_migrations("sqlite:empire.db", include_migrations())
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            ping,
            get_version,
            store_jwt,
            get_jwt,
            delete_jwt,
            has_jwt
        ])
        .setup(|app| {
            // Initialize logging in debug mode
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Set up the macOS menu bar
            #[cfg(target_os = "macos")]
            {
                let handle = app.handle();

                // File menu items
                let new_chat = MenuItemBuilder::with_id("new_chat", "New Chat")
                    .accelerator("CmdOrCtrl+N")
                    .build(handle)?;
                let search = MenuItemBuilder::with_id("search", "Search...")
                    .accelerator("CmdOrCtrl+K")
                    .build(handle)?;
                let close_window = PredefinedMenuItem::close_window(handle, Some("Close Window"))?;

                let file_menu = SubmenuBuilder::new(handle, "File")
                    .item(&new_chat)
                    .separator()
                    .item(&search)
                    .separator()
                    .item(&close_window)
                    .build()?;

                // Edit menu (standard macOS)
                let edit_menu = SubmenuBuilder::new(handle, "Edit")
                    .undo()
                    .redo()
                    .separator()
                    .cut()
                    .copy()
                    .paste()
                    .select_all()
                    .build()?;

                // View menu
                let toggle_sidebar = MenuItemBuilder::with_id("toggle_sidebar", "Toggle Sidebar")
                    .accelerator("CmdOrCtrl+B")
                    .build(handle)?;
                let chats_view = MenuItemBuilder::with_id("chats_view", "Chats")
                    .accelerator("CmdOrCtrl+1")
                    .build(handle)?;
                let projects_view = MenuItemBuilder::with_id("projects_view", "Projects")
                    .accelerator("CmdOrCtrl+2")
                    .build(handle)?;
                let settings_view = MenuItemBuilder::with_id("settings_view", "Settings")
                    .accelerator("CmdOrCtrl+3")
                    .build(handle)?;

                let view_menu = SubmenuBuilder::new(handle, "View")
                    .item(&toggle_sidebar)
                    .separator()
                    .item(&chats_view)
                    .item(&projects_view)
                    .item(&settings_view)
                    .separator()
                    .fullscreen()
                    .build()?;

                // Window menu (standard macOS)
                let window_menu = SubmenuBuilder::new(handle, "Window")
                    .minimize()
                    .separator()
                    .close_window()
                    .build()?;

                // Help menu
                let documentation = MenuItemBuilder::with_id("documentation", "Documentation")
                    .build(handle)?;
                let keyboard_shortcuts = MenuItemBuilder::with_id("keyboard_shortcuts", "Keyboard Shortcuts")
                    .accelerator("CmdOrCtrl+?")
                    .build(handle)?;

                let help_menu = SubmenuBuilder::new(handle, "Help")
                    .item(&documentation)
                    .item(&keyboard_shortcuts)
                    .build()?;

                // Build the complete menu
                let menu = MenuBuilder::new(handle)
                    .item(&file_menu)
                    .item(&edit_menu)
                    .item(&view_menu)
                    .item(&window_menu)
                    .item(&help_menu)
                    .build()?;

                // Set the menu
                app.set_menu(menu)?;

                // Handle menu events
                app.on_menu_event(move |app_handle, event| {
                    let id = event.id().as_ref();
                    log::info!("Menu event: {}", id);

                    // Emit events to the frontend for handling
                    match id {
                        "new_chat" => {
                            let _ = app_handle.emit("menu:new-chat", ());
                        }
                        "search" => {
                            let _ = app_handle.emit("menu:search", ());
                        }
                        "toggle_sidebar" => {
                            let _ = app_handle.emit("menu:toggle-sidebar", ());
                        }
                        "chats_view" => {
                            let _ = app_handle.emit("menu:view-chats", ());
                        }
                        "projects_view" => {
                            let _ = app_handle.emit("menu:view-projects", ());
                        }
                        "settings_view" => {
                            let _ = app_handle.emit("menu:view-settings", ());
                        }
                        "documentation" => {
                            let _ = app_handle.emit("menu:documentation", ());
                        }
                        "keyboard_shortcuts" => {
                            let _ = app_handle.emit("menu:keyboard-shortcuts", ());
                        }
                        _ => {}
                    }
                });

                // Configure the main window
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.set_title("Empire Desktop");
                }
            }

            log::info!("Empire Desktop initialized successfully");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Include database migrations
fn include_migrations() -> Vec<tauri_plugin_sql::Migration> {
    vec![
        tauri_plugin_sql::Migration {
            version: 1,
            description: "Create initial schema per PRD",
            sql: r#"
                -- Enable foreign keys
                PRAGMA foreign_keys = ON;

                -- Users table (cached from Clerk)
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT,
                    avatar_url TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    last_login_at TEXT,
                    synced_at TEXT
                );

                -- Projects table
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    department TEXT,
                    instructions TEXT,
                    memory_context TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    synced_at TEXT
                );

                -- Conversations table
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    message_count INTEGER DEFAULT 0,
                    last_message_at TEXT,
                    synced_at TEXT
                );

                -- Messages table
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    sources TEXT, -- JSON array of sources
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    status TEXT DEFAULT 'complete' CHECK (status IN ('sending', 'streaming', 'complete', 'error')),
                    synced_at TEXT
                );

                -- Project files table
                CREATE TABLE IF NOT EXISTS project_files (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    mime_type TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    synced_at TEXT
                );

                -- Settings table (key-value store)
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id);

                -- Triggers for updated_at timestamps
                CREATE TRIGGER IF NOT EXISTS users_updated_at
                    AFTER UPDATE ON users
                    FOR EACH ROW
                    BEGIN
                        UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id;
                    END;

                CREATE TRIGGER IF NOT EXISTS projects_updated_at
                    AFTER UPDATE ON projects
                    FOR EACH ROW
                    BEGIN
                        UPDATE projects SET updated_at = datetime('now') WHERE id = NEW.id;
                    END;

                CREATE TRIGGER IF NOT EXISTS conversations_updated_at
                    AFTER UPDATE ON conversations
                    FOR EACH ROW
                    BEGIN
                        UPDATE conversations SET updated_at = datetime('now') WHERE id = NEW.id;
                    END;

                CREATE TRIGGER IF NOT EXISTS messages_updated_at
                    AFTER UPDATE ON messages
                    FOR EACH ROW
                    BEGIN
                        UPDATE messages SET updated_at = datetime('now') WHERE id = NEW.id;
                    END;

                CREATE TRIGGER IF NOT EXISTS project_files_updated_at
                    AFTER UPDATE ON project_files
                    FOR EACH ROW
                    BEGIN
                        UPDATE project_files SET updated_at = datetime('now') WHERE id = NEW.id;
                    END;

                CREATE TRIGGER IF NOT EXISTS settings_updated_at
                    AFTER UPDATE ON settings
                    FOR EACH ROW
                    BEGIN
                        UPDATE settings SET updated_at = datetime('now') WHERE key = NEW.key;
                    END;

                -- Trigger to update conversation message_count and last_message_at
                CREATE TRIGGER IF NOT EXISTS messages_insert_update_conversation
                    AFTER INSERT ON messages
                    FOR EACH ROW
                    BEGIN
                        UPDATE conversations
                        SET message_count = message_count + 1,
                            last_message_at = datetime('now'),
                            updated_at = datetime('now')
                        WHERE id = NEW.conversation_id;
                    END;

                -- Insert default settings
                INSERT OR IGNORE INTO settings (key, value) VALUES
                    ('theme', '"dark"'),
                    ('fontSize', '"medium"'),
                    ('keyboardShortcutsEnabled', 'true'),
                    ('apiEndpoint', '"https://jb-empire-api.onrender.com"');
            "#,
            kind: tauri_plugin_sql::MigrationKind::Up,
        },
    ]
}
