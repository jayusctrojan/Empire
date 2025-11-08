"""
Arcade.dev tool integration service for Empire v7.3
Provides access to external tools (Google Search, Slack, GitHub, etc.) via Arcade.dev API
"""
import os
from typing import List, Optional
from arcadepy import Arcade
from langchain_core.tools import Tool
import structlog

logger = structlog.get_logger(__name__)


class ArcadeService:
    """Manages Arcade.dev tool integration for external API access."""

    def __init__(self):
        api_key = os.getenv("ARCADE_API_KEY")
        if not api_key:
            logger.warning("ARCADE_API_KEY not set, Arcade tools disabled")
            self.arcade = None
            self.enabled = False
        else:
            self.arcade = Arcade(api_key=api_key)
            self.enabled = os.getenv("ARCADE_ENABLED", "true").lower() == "true"
            logger.info("Arcade.dev service initialized", enabled=self.enabled)

    def get_available_tools(self) -> List[str]:
        """
        List all available Arcade tools.

        Returns:
            List of tool names (e.g., ["Google.Search", "Slack.SendMessage", ...])
        """
        if not self.enabled or not self.arcade:
            return []

        try:
            tools = self.arcade.list_tools()
            logger.info("Arcade tools listed", count=len(tools))
            return tools
        except Exception as e:
            logger.error("Failed to list Arcade tools", error=str(e))
            return []

    def get_langchain_tools(self, tool_names: Optional[List[str]] = None) -> List[Tool]:
        """
        Get Arcade tools as LangChain-compatible tools.

        These tools can be used in:
        - CrewAI agents (via agent tool configuration)
        - LangGraph workflows (via ToolNode)

        Args:
            tool_names: Specific tools to load (e.g., ["Google.Search", "Slack.SendMessage"])
                       If None, loads default tools from env var ARCADE_DEFAULT_TOOLS.

        Returns:
            List of LangChain Tool objects ready for use in agents or graphs

        Example:
            >>> arcade_tools = arcade_service.get_langchain_tools(["Google.Search"])
            >>> # Use in LangGraph
            >>> from langgraph.prebuilt import ToolNode
            >>> tool_node = ToolNode(arcade_tools)
            >>>
            >>> # Use in CrewAI
            >>> from crewai import Agent
            >>> agent = Agent(role="researcher", tools=arcade_tools)
        """
        if not self.enabled or not self.arcade:
            logger.warning("Arcade tools requested but service is disabled")
            return []

        # Use provided tools or fallback to defaults from environment
        if tool_names is None:
            default_tools = os.getenv("ARCADE_DEFAULT_TOOLS", "")
            tool_names = [t.strip() for t in default_tools.split(",") if t.strip()]

        if not tool_names:
            logger.info("No Arcade tools specified, returning empty list")
            return []

        try:
            tools = self.arcade.get_langchain_tools(tool_names)
            logger.info("Loaded Arcade tools", count=len(tools), tools=tool_names)
            return tools
        except Exception as e:
            logger.error("Failed to load Arcade tools", error=str(e), tools=tool_names)
            return []


# Global singleton instance
arcade_service = ArcadeService()
