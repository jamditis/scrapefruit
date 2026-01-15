"""Agent-browser fetcher using Vercel's AI-optimized browser automation CLI."""

import json
import subprocess
import time
import shutil
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import config


@dataclass
class AgentBrowserResult:
    """Result from an Agent-browser fetch operation."""

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "agent_browser"
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None
    # Agent-browser unique features
    accessibility_tree: Optional[Dict[str, Any]] = None
    element_refs: Dict[str, str] = field(default_factory=dict)


class AgentBrowserFetcher:
    """
    Agent-browser CLI wrapper for AI-optimized browser automation.

    Uses Vercel's agent-browser tool which provides:
    - Accessibility tree snapshots with element refs (@e1, @e2, etc.)
    - JSON output mode for programmatic consumption
    - Built-in stealth and anti-bot bypass
    - CDP protocol support

    Requires: npm install -g agent-browser && agent-browser install
    """

    def __init__(self, executable_path: Optional[str] = None):
        self.executable = executable_path or getattr(
            config, "AGENT_BROWSER_PATH", "agent-browser"
        )
        self._available: Optional[bool] = None
        self._session_id: Optional[str] = None

    def is_available(self) -> bool:
        """Check if agent-browser CLI is installed and available."""
        if self._available is not None:
            return self._available

        # Check if executable exists in PATH
        if shutil.which(self.executable):
            try:
                result = subprocess.run(
                    [self.executable, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self._available = result.returncode == 0
            except Exception:
                self._available = False
        else:
            self._available = False

        return self._available

    def _run_command(
        self,
        args: List[str],
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """
        Run an agent-browser command and parse JSON output.

        Args:
            args: Command arguments (after 'agent-browser')
            timeout_seconds: Command timeout

        Returns:
            Parsed JSON response or error dict
        """
        cmd = [self.executable] + args + ["--json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or f"Command failed with code {result.returncode}",
                }

            # Parse JSON output
            if result.stdout.strip():
                return json.loads(result.stdout)

            return {"success": True}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse JSON: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _start_session(self) -> bool:
        """Start a new browser session if not already running."""
        if self._session_id:
            return True

        # Generate unique session ID
        import uuid
        self._session_id = str(uuid.uuid4())[:8]
        return True

    def fetch(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        capture_accessibility: bool = True,
        take_screenshot: bool = False,
    ) -> AgentBrowserResult:
        """
        Fetch a URL using agent-browser CLI.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            capture_accessibility: Whether to capture accessibility tree
            take_screenshot: Whether to capture a screenshot

        Returns:
            AgentBrowserResult with success status and content
        """
        start_time = time.time()

        # Check availability
        if not self.is_available():
            return AgentBrowserResult(
                success=False,
                method="agent_browser",
                error="agent-browser CLI not installed. Run: npm install -g agent-browser && agent-browser install",
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        timeout_seconds = max(timeout // 1000, 10) + 10  # Buffer for CLI overhead

        try:
            # Navigate to URL
            # agent-browser open <url>
            open_result = self._run_command(
                ["open", url, "--timeout", str(timeout)],
                timeout_seconds=timeout_seconds,
            )

            if not open_result.get("success", True) and "error" in open_result:
                response_time = int((time.time() - start_time) * 1000)
                return AgentBrowserResult(
                    success=False,
                    method="agent_browser",
                    error=open_result.get("error"),
                    response_time_ms=response_time,
                )

            # Wait for element if specified
            if wait_for:
                self._run_command(
                    ["wait", wait_for, "--timeout", str(wait_for_timeout)],
                    timeout_seconds=wait_for_timeout // 1000 + 5,
                )

            # Get accessibility snapshot if requested
            accessibility_tree = None
            element_refs = {}

            if capture_accessibility:
                snapshot_result = self._run_command(
                    ["snapshot", "-i"],  # -i for interactive elements only
                    timeout_seconds=30,
                )
                if snapshot_result.get("success", True):
                    accessibility_tree = snapshot_result.get("tree")
                    # Extract element refs from snapshot
                    element_refs = self._extract_refs(snapshot_result)

            # Get HTML content
            # agent-browser html
            html_result = self._run_command(
                ["html"],
                timeout_seconds=30,
            )

            html = ""
            if html_result.get("success", True):
                html = html_result.get("html", html_result.get("content", ""))

            # Get screenshot if requested
            screenshot = None
            if take_screenshot:
                screenshot_result = self._run_command(
                    ["screenshot", "--full-page"],
                    timeout_seconds=30,
                )
                if screenshot_result.get("success", True):
                    # Screenshot might be base64 encoded
                    screenshot_data = screenshot_result.get("data")
                    if screenshot_data:
                        import base64
                        try:
                            screenshot = base64.b64decode(screenshot_data)
                        except Exception:
                            pass

            response_time = int((time.time() - start_time) * 1000)

            # Determine success based on HTML content
            success = len(html) > 0

            return AgentBrowserResult(
                success=success,
                html=html,
                status_code=200 if success else 0,
                method="agent_browser",
                response_time_ms=response_time,
                screenshot=screenshot,
                accessibility_tree=accessibility_tree,
                element_refs=element_refs,
            )

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return AgentBrowserResult(
                success=False,
                method="agent_browser",
                error=str(e),
                response_time_ms=response_time,
            )

    def _extract_refs(self, snapshot_result: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract element refs (@e1, @e2, etc.) from accessibility snapshot.

        Returns:
            Dict mapping ref IDs to element descriptions
        """
        refs = {}

        def traverse(node: Dict[str, Any], path: str = ""):
            if not isinstance(node, dict):
                return

            ref = node.get("ref")
            if ref:
                # Build description from role and name
                role = node.get("role", "")
                name = node.get("name", "")
                description = f"{role}: {name}" if name else role
                refs[ref] = description

            # Traverse children
            children = node.get("children", [])
            for i, child in enumerate(children):
                traverse(child, f"{path}/{i}")

        tree = snapshot_result.get("tree", snapshot_result)
        traverse(tree)

        return refs

    def click(self, ref: str, timeout: int = 5000) -> bool:
        """
        Click an element by its ref ID.

        Args:
            ref: Element ref (e.g., "@e2")
            timeout: Click timeout in milliseconds

        Returns:
            True if click succeeded
        """
        if not self.is_available():
            return False

        result = self._run_command(
            ["click", ref],
            timeout_seconds=timeout // 1000 + 5,
        )
        return result.get("success", False)

    def fill(self, ref: str, text: str, timeout: int = 5000) -> bool:
        """
        Fill a form field by its ref ID.

        Args:
            ref: Element ref (e.g., "@e3")
            text: Text to enter
            timeout: Fill timeout in milliseconds

        Returns:
            True if fill succeeded
        """
        if not self.is_available():
            return False

        result = self._run_command(
            ["fill", ref, text],
            timeout_seconds=timeout // 1000 + 5,
        )
        return result.get("success", False)

    def close(self):
        """Close the browser session."""
        if self.is_available():
            self._run_command(["close"], timeout_seconds=10)
        self._session_id = None
