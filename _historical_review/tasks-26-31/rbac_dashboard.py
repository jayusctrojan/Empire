"""
Empire v7.3 - RBAC Management Dashboard (Gradio)
Provides UI for API key management, role viewing, and audit logs.

Frontend integration for Task 31: RBAC & API Key Management
"""

import os
import gradio as gr
import httpx
import structlog
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger(__name__)

# API base URL
API_BASE_URL = os.getenv("EMPIRE_API_URL", "https://jb-empire-api.onrender.com")


# Helper functions for API calls

async def get_auth_headers(clerk_token: Optional[str] = None) -> dict:
    """Get headers with Clerk JWT token"""
    headers = {"Content-Type": "application/json"}
    if clerk_token:
        headers["Authorization"] = f"Bearer {clerk_token}"
    return headers


async def list_available_roles() -> tuple[str, str]:
    """List all available roles (public endpoint)"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_BASE_URL}/api/rbac/roles")

            if response.status_code == 200:
                roles = response.json()

                # Format as markdown table
                output = "### Available Roles\n\n"
                output += "| Role | Description | Permissions |\n"
                output += "|------|-------------|-------------|\n"

                for role in roles:
                    name = role.get("role_name", "N/A")
                    desc = role.get("description", "N/A")
                    perms = ", ".join(role.get("permissions", [])) or "None"
                    output += f"| {name} | {desc} | {perms} |\n"

                return output, "✅ Success"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to list roles", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


async def create_api_key(
    clerk_token: str,
    key_name: str,
    role_name: str,
    scopes: str,
    expires_days: int
) -> tuple[str, str]:
    """Create a new API key"""
    try:
        if not key_name.strip():
            return "❌ **Error**: Key name is required", "Invalid Input"

        # Parse scopes (comma-separated)
        scopes_list = [s.strip() for s in scopes.split(",") if s.strip()]

        # Calculate expiration date
        expires_at = None
        if expires_days > 0:
            expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat() + "Z"

        headers = await get_auth_headers(clerk_token)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/rbac/keys",
                headers=headers,
                json={
                    "key_name": key_name,
                    "role_name": role_name,
                    "scopes": scopes_list,
                    "expires_at": expires_at
                }
            )

            if response.status_code in [200, 201]:
                data = response.json()
                api_key = data.get("api_key")
                key_id = data.get("key_id")

                output = f"""### ✅ API Key Created Successfully!

**⚠️ IMPORTANT: Save this key now - it will only be shown once!**

```
{api_key}
```

**Key Details:**
- **Key ID**: {key_id}
- **Name**: {key_name}
- **Role**: {role_name}
- **Scopes**: {", ".join(scopes_list) if scopes_list else "All"}
- **Expires**: {expires_at or "Never"}

**Usage Example:**
```bash
curl -X GET {API_BASE_URL}/api/rbac/keys \\
  -H "Authorization: {api_key}"
```
"""
                return output, "✅ Created"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to create API key", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


async def list_user_keys(clerk_token: str) -> tuple[str, str]:
    """List user's API keys"""
    try:
        headers = await get_auth_headers(clerk_token)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/rbac/keys",
                headers=headers
            )

            if response.status_code == 200:
                keys = response.json()

                if not keys:
                    return "ℹ️ **No API keys found**\n\nCreate your first API key using the form above.", "No Keys"

                # Format as markdown
                output = f"### Your API Keys ({len(keys)} total)\n\n"

                for key in keys:
                    key_id = key.get("id", "N/A")
                    name = key.get("key_name", "Unnamed")
                    role = key.get("role", {}).get("role_name", "N/A")
                    scopes = ", ".join(key.get("scopes", [])) or "All"
                    is_active = key.get("is_active", False)
                    created = key.get("created_at", "N/A")
                    expires = key.get("expires_at") or "Never"
                    last_used = key.get("last_used_at") or "Never used"

                    status_emoji = "✅" if is_active else "❌"

                    output += f"""
---

**{name}** {status_emoji}

- **Key ID**: `{key_id}`
- **Role**: {role}
- **Scopes**: {scopes}
- **Created**: {created}
- **Expires**: {expires}
- **Last Used**: {last_used}
"""

                return output, "✅ Success"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to list API keys", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


async def rotate_api_key(clerk_token: str, key_id: str) -> tuple[str, str]:
    """Rotate an API key (invalidate old, create new)"""
    try:
        if not key_id.strip():
            return "❌ **Error**: Key ID is required", "Invalid Input"

        headers = await get_auth_headers(clerk_token)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/rbac/keys/rotate",
                headers=headers,
                json={"key_id": key_id}
            )

            if response.status_code in [200, 201]:
                data = response.json()
                new_key = data.get("new_api_key")
                new_key_id = data.get("new_key_id")
                old_key_id = data.get("old_key_id")

                output = f"""### ✅ API Key Rotated Successfully!

**⚠️ IMPORTANT: Save this new key now - it will only be shown once!**

**New API Key:**
```
{new_key}
```

**Details:**
- **New Key ID**: {new_key_id}
- **Old Key ID**: {old_key_id} (now revoked)

**Action Required:**
Update all services using the old key with this new key.
"""
                return output, "✅ Rotated"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to rotate API key", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


async def revoke_api_key(clerk_token: str, key_id: str) -> tuple[str, str]:
    """Revoke an API key"""
    try:
        if not key_id.strip():
            return "❌ **Error**: Key ID is required", "Invalid Input"

        headers = await get_auth_headers(clerk_token)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/rbac/keys/revoke",
                headers=headers,
                json={"key_id": key_id}
            )

            if response.status_code in [200, 204]:
                return f"### ✅ API Key Revoked\n\nKey ID `{key_id}` has been successfully revoked and can no longer be used.", "✅ Revoked"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to revoke API key", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


async def get_user_roles(clerk_token: str, user_id: Optional[str] = None) -> tuple[str, str]:
    """Get roles for current user or specified user (admin only for other users)"""
    try:
        headers = await get_auth_headers(clerk_token)

        # If no user_id provided, backend will use current user from JWT
        url = f"{API_BASE_URL}/api/rbac/users/{user_id}/roles" if user_id else f"{API_BASE_URL}/api/rbac/users/me/roles"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                roles = response.json()

                if not roles:
                    return "ℹ️ **No roles assigned**\n\nContact an administrator to request role assignment.", "No Roles"

                output = "### Your Roles\n\n"

                for role_assignment in roles:
                    role = role_assignment.get("role", {})
                    role_name = role.get("role_name", "Unknown")
                    role_desc = role.get("description", "N/A")
                    permissions = role.get("permissions", [])
                    granted_by = role_assignment.get("granted_by", "System")
                    granted_at = role_assignment.get("granted_at", "N/A")
                    expires_at = role_assignment.get("expires_at") or "Never"

                    output += f"""
---

**{role_name.upper()}**

- **Description**: {role_desc}
- **Permissions**: {", ".join(permissions) if permissions else "None"}
- **Granted By**: {granted_by}
- **Granted At**: {granted_at}
- **Expires**: {expires_at}
"""

                return output, "✅ Success"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to get user roles", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


async def get_audit_logs(clerk_token: str, event_type: str = "", limit: int = 50) -> tuple[str, str]:
    """Get audit logs (admin only)"""
    try:
        headers = await get_auth_headers(clerk_token)

        params = {"limit": limit}
        if event_type.strip():
            params["event_type"] = event_type.strip()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/rbac/audit-logs",
                headers=headers,
                params=params
            )

            if response.status_code == 200:
                logs = response.json()

                if not logs:
                    return "ℹ️ **No audit logs found**", "No Logs"

                output = f"### Audit Logs ({len(logs)} events)\n\n"

                for log in logs:
                    event_type = log.get("event_type", "unknown")
                    actor = log.get("actor_user_id", "System")
                    target = log.get("target_user_id", "N/A")
                    action = log.get("action", "N/A")
                    result = log.get("result", "N/A")
                    timestamp = log.get("timestamp", "N/A")
                    ip = log.get("ip_address", "N/A")

                    result_emoji = "✅" if result == "success" else "❌"

                    output += f"""
---

**{event_type}** {result_emoji}

- **Action**: {action}
- **Actor**: {actor}
- **Target**: {target}
- **Result**: {result}
- **Timestamp**: {timestamp}
- **IP**: {ip}
"""

                return output, "✅ Success"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return f"❌ **Error**: {error_detail}", f"Status: {response.status_code}"

    except Exception as e:
        logger.error("Failed to get audit logs", error=str(e))
        return f"❌ **Error**: {str(e)}", "Failed"


# Custom CSS
custom_css = """
.gradio-container {
    max-width: 1200px !important;
}

.markdown-text code {
    background-color: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
}

.markdown-text pre {
    background-color: #f8f8f8;
    padding: 12px;
    border-radius: 6px;
    border-left: 4px solid #0066cc;
    overflow-x: auto;
}
"""


# Build Gradio Interface
def build_rbac_dashboard():
    """Build the RBAC management dashboard"""

    with gr.Blocks(theme=gr.themes.Soft(), css=custom_css, title="Empire RBAC Dashboard") as dashboard:
        with gr.Row():
            with gr.Column(scale=4):
                gr.Markdown("# 🔐 Empire RBAC Management Dashboard")
                gr.Markdown("Manage API keys, view roles, and monitor security events.")
            with gr.Column(scale=1):
                chat_btn = gr.Button("💬 Back to Chat", size="sm")

        # Hidden textbox for Clerk token (will be populated by JavaScript)
        clerk_token_input = gr.Textbox(
            label="Clerk Session Token",
            type="password",
            visible=False,
            value=""
        )

        # JavaScript to inject token from localStorage and handle navigation
        gr.HTML("""
        <script>
        window.addEventListener('load', function() {
            const tokenInput = document.querySelector('input[type="password"]');
            const token = localStorage.getItem('clerk_session_token');
            if (token && tokenInput) {
                tokenInput.value = token;
                tokenInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });

        // Handle navigation back to chat
        function goToChat() {
            window.location.href = '/chat';
        }
        </script>
        """)

        # Wire up navigation button
        chat_btn.click(fn=None, js="goToChat()")

        with gr.Tabs():
            # Tab 1: API Key Management
            with gr.Tab("🔑 API Keys"):
                gr.Markdown("## Create New API Key")

                with gr.Row():
                    key_name_input = gr.Textbox(
                        label="Key Name",
                        placeholder="production-service-key",
                        info="Descriptive name for this API key"
                    )
                    role_input = gr.Dropdown(
                        choices=["admin", "editor", "viewer", "guest"],
                        label="Role",
                        value="viewer",
                        info="Role determines permissions"
                    )

                with gr.Row():
                    scopes_input = gr.Textbox(
                        label="Scopes (comma-separated)",
                        placeholder="documents:read, documents:write",
                        value="documents:read",
                        info="Leave empty for all scopes"
                    )
                    expires_input = gr.Number(
                        label="Expires in (days)",
                        value=90,
                        minimum=0,
                        maximum=365,
                        info="0 = never expires"
                    )

                create_btn = gr.Button("🔒 Create API Key", variant="primary")
                create_output = gr.Markdown()
                create_status = gr.Textbox(label="Status", visible=False)

                create_btn.click(
                    fn=create_api_key,
                    inputs=[clerk_token_input, key_name_input, role_input, scopes_input, expires_input],
                    outputs=[create_output, create_status]
                )

                gr.Markdown("---")
                gr.Markdown("## Your API Keys")

                list_btn = gr.Button("📋 List My Keys")
                list_output = gr.Markdown()
                list_status = gr.Textbox(label="Status", visible=False)

                list_btn.click(
                    fn=list_user_keys,
                    inputs=[clerk_token_input],
                    outputs=[list_output, list_status]
                )

                gr.Markdown("---")
                gr.Markdown("## Manage Keys")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 🔄 Rotate Key")
                        rotate_key_id = gr.Textbox(label="Key ID to Rotate", placeholder="key_abc123...")
                        rotate_btn = gr.Button("🔄 Rotate Key")
                        rotate_output = gr.Markdown()
                        rotate_status = gr.Textbox(label="Status", visible=False)

                        rotate_btn.click(
                            fn=rotate_api_key,
                            inputs=[clerk_token_input, rotate_key_id],
                            outputs=[rotate_output, rotate_status]
                        )

                    with gr.Column():
                        gr.Markdown("### ❌ Revoke Key")
                        revoke_key_id = gr.Textbox(label="Key ID to Revoke", placeholder="key_abc123...")
                        revoke_btn = gr.Button("❌ Revoke Key", variant="stop")
                        revoke_output = gr.Markdown()
                        revoke_status = gr.Textbox(label="Status", visible=False)

                        revoke_btn.click(
                            fn=revoke_api_key,
                            inputs=[clerk_token_input, revoke_key_id],
                            outputs=[revoke_output, revoke_status]
                        )

            # Tab 2: Roles
            with gr.Tab("👤 Roles"):
                gr.Markdown("## Available Roles")

                roles_btn = gr.Button("📋 List All Roles")
                roles_output = gr.Markdown()
                roles_status = gr.Textbox(label="Status", visible=False)

                roles_btn.click(
                    fn=list_available_roles,
                    inputs=[],
                    outputs=[roles_output, roles_status]
                )

                gr.Markdown("---")
                gr.Markdown("## Your Roles")

                user_roles_btn = gr.Button("👤 View My Roles")
                user_roles_output = gr.Markdown()
                user_roles_status = gr.Textbox(label="Status", visible=False)

                user_roles_btn.click(
                    fn=get_user_roles,
                    inputs=[clerk_token_input],
                    outputs=[user_roles_output, user_roles_status]
                )

            # Tab 3: Audit Logs (Admin Only)
            with gr.Tab("📊 Audit Logs"):
                gr.Markdown("## Security Events (Admin Only)")

                with gr.Row():
                    event_type_filter = gr.Textbox(
                        label="Event Type Filter (optional)",
                        placeholder="api_key_created, user_role_assigned, etc.",
                        info="Leave empty for all events"
                    )
                    logs_limit = gr.Number(
                        label="Number of Events",
                        value=50,
                        minimum=10,
                        maximum=200
                    )

                logs_btn = gr.Button("📊 View Audit Logs")
                logs_output = gr.Markdown()
                logs_status = gr.Textbox(label="Status", visible=False)

                logs_btn.click(
                    fn=get_audit_logs,
                    inputs=[clerk_token_input, event_type_filter, logs_limit],
                    outputs=[logs_output, logs_status]
                )

        # Footer
        gr.Markdown("""
        ---

        ### ℹ️ Quick Help

        - **API Keys**: Create keys for service-to-service authentication
        - **Roles**: View your assigned roles and permissions
        - **Audit Logs**: Monitor security events (admin only)

        **Documentation**: See `docs/clerk_rbac_integration.md` for integration guide
        """)

    return dashboard


if __name__ == "__main__":
    port = int(os.getenv("RBAC_DASHBOARD_PORT", 7861))
    server_name = os.getenv("RBAC_DASHBOARD_HOST", "0.0.0.0")

    logger.info(
        "Launching RBAC Dashboard",
        host=server_name,
        port=port,
        api_url=API_BASE_URL
    )

    dashboard = build_rbac_dashboard()
    dashboard.launch(
        server_name=server_name,
        server_port=port,
        share=False,
        show_api=False,
        show_error=True
    )
