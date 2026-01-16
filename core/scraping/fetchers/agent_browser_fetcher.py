"""Agent-browser fetcher using Vercel's AI-optimized browser automation CLI.

This fetcher wraps the agent-browser CLI tool from:
https://github.com/vercel-labs/agent-browser

The tool provides accessibility tree snapshots with element refs (@e1, @e2, etc.)
which are useful for AI-driven browser automation.

Installation:
    npm install -g agent-browser
    agent-browser install  # Download Chromium
"""

import json
import subprocess
import time
import shutil
import base64
import tempfile
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


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
    accessibility_tree: Optional[str] = None
    element_refs: Dict[str, str] = field(default_factory=dict)


class AgentBrowserFetcher:
    """
    Agent-browser CLI wrapper for AI-optimized browser automation.

    Uses Vercel's agent-browser tool which provides:
    - Accessibility tree snapshots with element refs (@e1, @e2, etc.)
    - Semantic locators (role, label, text, placeholder)
    - Multi-session support for isolated contexts
    - Network interception and mocking

    Requires: npm install -g agent-browser && agent-browser install
    """

    def __init__(self, executable_path: Optional[str] = None, session_name: Optional[str] = None):
        self.executable = executable_path or shutil.which("agent-browser") or "agent-browser"
        self.session_name = session_name  # Optional session isolation
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if agent-browser CLI is installed and available."""
        if self._available is not None:
            return self._available

        # Check if executable exists in PATH
        exe_path = shutil.which(self.executable)
        if exe_path:
            try:
                result = subprocess.run(
                    [exe_path, "--version"],
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

    def _build_command(self, args: List[str]) -> List[str]:
        """Build command with optional session flag."""
        cmd = [self.executable] + args
        if self.session_name:
            cmd.extend(["--session", self.session_name])
        return cmd

    def _run_command(
        self,
        args: List[str],
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """
        Run an agent-browser command and return output.

        Args:
            args: Command arguments (after 'agent-browser')
            timeout_seconds: Command timeout

        Returns:
            Dict with stdout, stderr, success
        """
        cmd = self._build_command(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out", "stdout": "", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}

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
            # Step 1: Navigate to URL
            # Command: agent-browser open <url>
            open_result = self._run_command(
                ["open", url],
                timeout_seconds=timeout_seconds,
            )

            if not open_result.get("success"):
                error = open_result.get("stderr") or open_result.get("error", "Navigation failed")
                return AgentBrowserResult(
                    success=False,
                    method="agent_browser",
                    error=error,
                    response_time_ms=int((time.time() - start_time) * 1000),
                )

            # Step 2: Wait for element if specified
            if wait_for:
                self._run_command(
                    ["wait", wait_for],
                    timeout_seconds=wait_for_timeout // 1000 + 5,
                )

            # Step 3: Get accessibility snapshot if requested
            accessibility_tree = None
            element_refs = {}

            if capture_accessibility:
                # Command: agent-browser snapshot
                snapshot_result = self._run_command(
                    ["snapshot"],
                    timeout_seconds=30,
                )
                if snapshot_result.get("success"):
                    accessibility_tree = snapshot_result.get("stdout", "")
                    # Extract element refs from snapshot output
                    element_refs = self._extract_refs(accessibility_tree)

            # Step 4: Get HTML content
            # Command: agent-browser get html body (or specific selector)
            html_result = self._run_command(
                ["get", "html", "body"],
                timeout_seconds=30,
            )

            html = ""
            if html_result.get("success"):
                html = html_result.get("stdout", "").strip()

            # If body didn't work, try getting text as fallback
            if not html or len(html) < 100:
                text_result = self._run_command(
                    ["get", "text", "body"],
                    timeout_seconds=30,
                )
                if text_result.get("success") and text_result.get("stdout"):
                    # Wrap text in minimal HTML
                    text = text_result.get("stdout", "").strip()
                    html = f"<html><body>{text}</body></html>"

            # Step 5: Get screenshot if requested
            screenshot = None
            if take_screenshot:
                # Create temp file for screenshot
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name

                try:
                    # Command: agent-browser screenshot <path>
                    screenshot_result = self._run_command(
                        ["screenshot", tmp_path],
                        timeout_seconds=30,
                    )
                    if screenshot_result.get("success") and os.path.exists(tmp_path):
                        with open(tmp_path, "rb") as f:
                            screenshot = f.read()
                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            response_time = int((time.time() - start_time) * 1000)

            # Determine success based on HTML content
            success = len(html) > 100

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

    def _extract_refs(self, snapshot_output: str) -> Dict[str, str]:
        """
        Extract element refs (@e1, @e2, etc.) from accessibility snapshot.

        The snapshot output contains lines like:
        @e1 button "Submit"
        @e2 textbox "Email"

        Returns:
            Dict mapping ref IDs to element descriptions
        """
        refs = {}
        if not snapshot_output:
            return refs

        import re
        # Match patterns like: @e1 role "name" or @e1 [role] name
        # Allow optional leading whitespace
        ref_pattern = re.compile(r'^\s*(@e\d+)\s+(.+)$', re.MULTILINE)

        for match in ref_pattern.finditer(snapshot_output):
            ref_id = match.group(1)
            description = match.group(2).strip()
            refs[ref_id] = description

        return refs

    def click(self, selector: str, timeout: int = 5000) -> bool:
        """
        Click an element by selector or ref ID.

        Args:
            selector: CSS selector, ref (@e2), or semantic locator
            timeout: Click timeout in milliseconds

        Returns:
            True if click succeeded
        """
        if not self.is_available():
            return False

        result = self._run_command(
            ["click", selector],
            timeout_seconds=timeout // 1000 + 5,
        )
        return result.get("success", False)

    def fill(self, selector: str, text: str, timeout: int = 5000) -> bool:
        """
        Fill a form field (clears first).

        Args:
            selector: CSS selector, ref (@e3), or semantic locator
            text: Text to enter
            timeout: Fill timeout in milliseconds

        Returns:
            True if fill succeeded
        """
        if not self.is_available():
            return False

        result = self._run_command(
            ["fill", selector, text],
            timeout_seconds=timeout // 1000 + 5,
        )
        return result.get("success", False)

    def type_text(self, selector: str, text: str, timeout: int = 5000) -> bool:
        """
        Type text into an element (doesn't clear first).

        Args:
            selector: CSS selector, ref, or semantic locator
            text: Text to type
            timeout: Type timeout in milliseconds

        Returns:
            True if typing succeeded
        """
        if not self.is_available():
            return False

        result = self._run_command(
            ["type", selector, text],
            timeout_seconds=timeout // 1000 + 5,
        )
        return result.get("success", False)

    def get_snapshot(self, interactive_only: bool = True) -> Optional[str]:
        """
        Get accessibility tree snapshot.

        Args:
            interactive_only: If True, only include interactive elements

        Returns:
            Snapshot text with element refs, or None if failed
        """
        if not self.is_available():
            return None

        args = ["snapshot"]
        if interactive_only:
            args.append("-i")  # Interactive elements only

        result = self._run_command(args, timeout_seconds=30)
        if result.get("success"):
            return result.get("stdout", "")
        return None

    def close(self):
        """Close the browser session."""
        if self.is_available():
            self._run_command(["close"], timeout_seconds=10)
