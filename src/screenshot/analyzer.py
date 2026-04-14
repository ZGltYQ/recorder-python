"""Screenshot analyzer with AI integration for task detection and auto-solve."""

import base64
import json
import re
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal

from ..utils.logger import get_logger
from ..utils.config import get_config
from ..ai.openrouter import OpenRouterClient, Message

logger = get_logger(__name__)


# AI prompts for screenshot analysis
TASK_DETECTION_PROMPT = """You are analyzing a screenshot for actionable tasks.
Identify any: TODOs, questions asked, action items, decisions made, 
or items requiring follow-up.

Return a JSON list with this format:
[
  {
    "task": "description of the task",
    "priority": "high|medium|low",
    "context": "relevant context from screenshot"
  }
]

If no tasks found, return: []"""

TASK_AUTO_SOLVE_PROMPT = """A screenshot analysis found this actionable task:
{task_description}

Based on the screenshot context:
{screenshot_context}

Provide a solution or recommendation for completing this task.
Be specific and actionable."""


class ScreenshotAnalyzer(QObject):
    """Analyzes screenshots using AI to detect actionable tasks and auto-solve them.

    Screenshots are analyzed to identify TODOs, questions, action items, and
    decisions. Detected tasks are then auto-solved using AI to provide
    actionable recommendations.

    Signals:
        tasks_found: Emitted with list of {task, solution, priority} dicts
        error: Emitted with error message string
    """

    tasks_found = Signal(list)  # List of {task, solution, priority}
    error = Signal(str)

    def __init__(self, ai_generator=None, parent=None):
        """Initialize screenshot analyzer.

        Args:
            ai_generator: AISuggestionGenerator instance for AI communication
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._ai_generator = ai_generator
        self._provider = "openrouter"

        # Load config for provider
        config = get_config()
        self._provider = config.get("provider", "openrouter")

        # Initialize client based on provider
        self._init_client()

    def _init_client(self):
        """Initialize the AI client based on current provider."""
        if self._provider == "local":
            from ..ai.local_llm import LocalLLMClient

            self._client = LocalLLMClient()
        else:
            self._client = OpenRouterClient()

    def set_provider(self, provider: str) -> None:
        """Switch AI provider.

        Args:
            provider: "openrouter" or "local"
        """
        if provider not in ("openrouter", "local"):
            raise ValueError(f"Invalid provider: {provider}")

        if self._provider != provider:
            self._provider = provider
            self._init_client()
            logger.info("ScreenshotAnalyzer provider switched", provider=provider)

    def analyze_screenshot(self, image_path: str) -> List[Dict[str, Any]]:
        """Analyze a screenshot for actionable tasks.

        Args:
            image_path: Path to the screenshot image file

        Returns:
            List of dicts with {task, priority, context} keys
        """
        try:
            # Load and encode image
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Determine image format from extension
            ext = Path(image_path).suffix.lower()
            mime_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(ext, "image/png")

            # Build messages with image
            messages = self._build_vision_messages(image_base64, mime_type, TASK_DETECTION_PROMPT)

            # Send to AI
            response = self._send_to_ai(messages)

            # Parse JSON response
            tasks = self._parse_tasks_response(response)

            logger.info("Screenshot analyzed", path=image_path, tasks_found=len(tasks))
            return tasks

        except Exception as e:
            logger.error("Screenshot analysis failed", path=image_path, error=str(e))
            self.error.emit(f"Analysis failed: {e}")
            return []

    def solve_task(self, task_description: str, screenshot_context: str) -> str:
        """Generate a solution for an actionable task.

        Args:
            task_description: Description of the task
            screenshot_context: Context from the screenshot

        Returns:
            Solution or recommendation text
        """
        try:
            # Build prompt
            prompt = TASK_AUTO_SOLVE_PROMPT.format(
                task_description=task_description, screenshot_context=screenshot_context
            )

            # Send to AI
            messages = [Message(role="user", content=prompt)]
            response = self._send_to_ai(messages)

            logger.info("Task solved", task=task_description[:50])
            return response.strip() if response else "No solution generated."

        except Exception as e:
            logger.error("Task solving failed", error=str(e))
            self.error.emit(f"Solve failed: {e}")
            return "Failed to generate solution."

    def process_screenshot(self, image_path: str) -> None:
        """Process a screenshot: detect tasks and auto-solve them.

        This method runs asynchronously and emits tasks_found signal when complete.

        Args:
            image_path: Path to the screenshot image file
        """
        # Run in background thread to avoid blocking
        thread = threading.Thread(
            target=self._process_screenshot_thread, args=(image_path,), daemon=True
        )
        thread.start()

    def _process_screenshot_thread(self, image_path: str) -> None:
        """Background processing of screenshot.

        Args:
            image_path: Path to the screenshot image file
        """
        try:
            # Step 1: Analyze for tasks
            tasks = self.analyze_screenshot(image_path)

            if not tasks:
                logger.debug("No tasks found in screenshot", path=image_path)
                self.tasks_found.emit([])
                return

            # Step 2: Auto-solve each task
            results = []
            for task_info in tasks:
                task = task_info.get("task", "")
                priority = task_info.get("priority", "medium")
                context = task_info.get("context", "")

                if task:
                    solution = self.solve_task(task, context)
                    results.append({"task": task, "solution": solution, "priority": priority})

            logger.info("Screenshot processed", tasks=len(results))
            self.tasks_found.emit(results)

        except Exception as e:
            logger.error("Screenshot processing failed", error=str(e))
            self.error.emit(str(e))

    def _build_vision_messages(
        self, image_base64: str, mime_type: str, prompt: str
    ) -> List[Message]:
        """Build messages for vision-capable AI model.

        Args:
            image_base64: Base64-encoded image data
            mime_type: MIME type of the image
            prompt: Text prompt to send with image

        Returns:
            List of Message objects
        """
        if self._provider == "local":
            # Local LLM uses dict format
            return [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                }
            ]
        else:
            # OpenRouter uses Message dataclass with content blocks
            return [
                Message(
                    role="user",
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                )
            ]

    def _send_to_ai(self, messages) -> str:
        """Send messages to AI and get response.

        Args:
            messages: List of Message objects or dicts

        Returns:
            Response content string
        """
        if self._provider == "local":
            # Local LLM
            response = self._client.chat_sync(messages)
            return response.content
        else:
            # OpenRouter
            response = self._client.chat_sync(messages)
            return response.content

    def _parse_tasks_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response to extract tasks.

        Args:
            response: Raw AI response text

        Returns:
            List of task dicts
        """
        if not response:
            return []

        # Try to extract JSON from response
        # Handle cases where AI wraps JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r"(\[[\s\S]*\])", response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()

        try:
            tasks = json.loads(json_str)
            if isinstance(tasks, list):
                # Validate and normalize each task
                valid_tasks = []
                for task in tasks:
                    if isinstance(task, dict) and "task" in task:
                        valid_tasks.append(
                            {
                                "task": str(task.get("task", "")),
                                "priority": str(task.get("priority", "medium")),
                                "context": str(task.get("context", "")),
                            }
                        )
                return valid_tasks
            return []
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse tasks JSON", error=str(e), response=response[:200])
            return []
