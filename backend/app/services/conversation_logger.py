"""
Conversation Logger Service.

Records the complete conversation flow to structured text files for analysis.
Captures all user messages, AI agent outputs, plans, file changes, and responses.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default log directory
DEFAULT_LOG_DIR = "/tmp/conversation_logs"


@dataclass
class ConversationLogEntry:
    """A single entry in the conversation log."""
    timestamp: datetime
    entry_type: str  # user_message, agent_output, response, file_change, plan, event, etc.
    agent_name: Optional[str] = None  # intent_analyzer, context_retriever, planner, executor, validator
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "entry_type": self.entry_type,
            "agent_name": self.agent_name,
            "content": self.content,
            "metadata": self.metadata,
        }


class ConversationLogger:
    """
    Logs the complete conversation flow to structured text files.

    Captures:
    - User messages (first message and all subsequent)
    - AI agent outputs (Intent Analyzer, Context Retriever, Planner, Executor, Validator)
    - All responses and answer chunks
    - All changed files with diffs
    - The complete plan with all steps
    - Events and progress updates
    - Token usage and timing
    """

    def __init__(
        self,
        conversation_id: str,
        project_id: str,
        user_id: str,
        log_dir: str = DEFAULT_LOG_DIR,
    ):
        """
        Initialize the conversation logger.

        Args:
            conversation_id: Unique conversation identifier
            project_id: Project UUID
            user_id: User UUID
            log_dir: Directory to store log files
        """
        self.conversation_id = conversation_id
        self.project_id = project_id
        self.user_id = user_id
        self.log_dir = Path(log_dir)
        self.entries: List[ConversationLogEntry] = []
        self.start_time = datetime.utcnow()

        # Create log directory structure
        self.conversation_dir = self.log_dir / project_id / conversation_id
        self.conversation_dir.mkdir(parents=True, exist_ok=True)

        # Log file paths
        self.main_log_file = self.conversation_dir / "conversation.txt"
        self.json_log_file = self.conversation_dir / "conversation.json"
        self.files_log_file = self.conversation_dir / "file_changes.txt"
        self.agents_log_file = self.conversation_dir / "agents.txt"

        # Initialize main log with header
        self._write_header()

        logger.info(f"[CONV_LOGGER] Initialized for conversation={conversation_id}")

    def _write_header(self):
        """Write the log file header."""
        header = f"""{'='*80}
CONVERSATION LOG
{'='*80}
Conversation ID: {self.conversation_id}
Project ID: {self.project_id}
User ID: {self.user_id}
Started: {self.start_time.isoformat()}
{'='*80}

"""
        self._append_to_file(self.main_log_file, header)

        # Also write agents header
        agents_header = f"""{'='*80}
AGENT OUTPUTS LOG
{'='*80}
Conversation ID: {self.conversation_id}
Started: {self.start_time.isoformat()}
{'='*80}

"""
        self._append_to_file(self.agents_log_file, agents_header)

    def _append_to_file(self, file_path: Path, content: str):
        """Append content to a log file."""
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"[CONV_LOGGER] Failed to write to {file_path}: {e}")

    def _format_timestamp(self, dt: Optional[datetime] = None) -> str:
        """Format timestamp for log entries."""
        ts = dt or datetime.utcnow()
        return ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def _format_divider(self, title: str, char: str = "-") -> str:
        """Format a section divider."""
        return f"\n{char*40}\n{title}\n{char*40}\n"

    def log_user_message(
        self,
        message: str,
        message_number: int = 1,
        conversation_context: Optional[str] = None,
    ):
        """
        Log a user message.

        Args:
            message: The user's message content
            message_number: Sequential message number in conversation
            conversation_context: Formatted conversation history context if any
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="user_message",
            content=message,
            metadata={
                "message_number": message_number,
                "has_context": bool(conversation_context),
            }
        )
        self.entries.append(entry)

        # Format for main log
        log_content = f"""
{self._format_divider(f'USER MESSAGE #{message_number}', '=')}
[{self._format_timestamp(timestamp)}]

{message}

"""
        if conversation_context:
            log_content += f"""
[Conversation Context Included]
{'-'*30}
{conversation_context[:2000]}{'... [truncated]' if len(conversation_context) > 2000 else ''}
{'-'*30}

"""

        self._append_to_file(self.main_log_file, log_content)
        logger.info(f"[CONV_LOGGER] Logged user message #{message_number}")

    def log_intent_analysis(
        self,
        intent_data: Dict[str, Any],
        raw_response: Optional[str] = None,
    ):
        """
        Log intent analyzer output.

        Args:
            intent_data: Parsed intent data dictionary
            raw_response: Raw AI response if available
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="agent_output",
            agent_name="intent_analyzer",
            content=intent_data,
            metadata={"raw_response": raw_response} if raw_response else {},
        )
        self.entries.append(entry)

        # Format for main log
        log_content = f"""
{self._format_divider('INTENT ANALYSIS', '-')}
[{self._format_timestamp(timestamp)}] Agent: Intent Analyzer

Task Type: {intent_data.get('task_type', 'unknown')}
Scope: {intent_data.get('scope', 'unknown')}
Domains: {', '.join(intent_data.get('domains', []))}
Languages: {', '.join(intent_data.get('languages', []))}
Requires Migration: {intent_data.get('requires_migration', False)}
Search Queries: {json.dumps(intent_data.get('search_queries', []), indent=2)}

Full Intent Data:
{json.dumps(intent_data, indent=2, default=str)}

"""
        self._append_to_file(self.main_log_file, log_content)

        # Also log to agents file with more detail
        agents_content = f"""
{'='*60}
INTENT ANALYZER OUTPUT
{'='*60}
[{self._format_timestamp(timestamp)}]

Parsed Intent:
{json.dumps(intent_data, indent=2, default=str)}

"""
        if raw_response:
            agents_content += f"""
Raw AI Response:
{'-'*40}
{raw_response}
{'-'*40}

"""
        self._append_to_file(self.agents_log_file, agents_content)
        logger.info(f"[CONV_LOGGER] Logged intent analysis: {intent_data.get('task_type')}")

    def log_context_retrieval(
        self,
        chunks_count: int,
        chunks: Optional[List[Dict[str, Any]]] = None,
        related_files: Optional[List[str]] = None,
        domain_summaries: Optional[Dict[str, str]] = None,
    ):
        """
        Log context retriever output.

        Args:
            chunks_count: Number of code chunks retrieved
            chunks: List of code chunk data
            related_files: List of related file paths
            domain_summaries: Domain-specific summaries
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="agent_output",
            agent_name="context_retriever",
            content={
                "chunks_count": chunks_count,
                "related_files": related_files,
            },
            metadata={
                "chunks": chunks,
                "domain_summaries": domain_summaries,
            }
        )
        self.entries.append(entry)

        # Format for main log
        log_content = f"""
{self._format_divider('CONTEXT RETRIEVAL', '-')}
[{self._format_timestamp(timestamp)}] Agent: Context Retriever

Chunks Retrieved: {chunks_count}
Related Files: {len(related_files or [])}

"""
        if related_files:
            log_content += "Related Files:\n"
            for f in related_files[:20]:  # Limit to 20 files
                log_content += f"  - {f}\n"
            if len(related_files) > 20:
                log_content += f"  ... and {len(related_files) - 20} more\n"

        log_content += "\n"
        self._append_to_file(self.main_log_file, log_content)

        # Log detailed chunks to agents file
        agents_content = f"""
{'='*60}
CONTEXT RETRIEVER OUTPUT
{'='*60}
[{self._format_timestamp(timestamp)}]

Total Chunks: {chunks_count}
Related Files: {json.dumps(related_files, indent=2) if related_files else '[]'}

"""
        if chunks:
            agents_content += "\nCode Chunks:\n"
            for i, chunk in enumerate(chunks[:10], 1):  # Limit to 10 chunks
                agents_content += f"""
{'-'*40}
Chunk #{i}: {chunk.get('file_path', 'unknown')}
Score: {chunk.get('score', 'N/A')}
{'-'*40}
{chunk.get('content', '')[:1000]}{'... [truncated]' if len(chunk.get('content', '')) > 1000 else ''}

"""

        if domain_summaries:
            agents_content += f"\nDomain Summaries:\n{json.dumps(domain_summaries, indent=2)}\n"

        self._append_to_file(self.agents_log_file, agents_content)
        logger.info(f"[CONV_LOGGER] Logged context retrieval: {chunks_count} chunks")

    def log_plan(
        self,
        plan_data: Dict[str, Any],
        raw_response: Optional[str] = None,
    ):
        """
        Log planner output with complete plan details.

        Args:
            plan_data: Parsed plan data dictionary
            raw_response: Raw AI response if available
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="plan",
            agent_name="planner",
            content=plan_data,
            metadata={"raw_response": raw_response} if raw_response else {},
        )
        self.entries.append(entry)

        steps = plan_data.get("steps", [])

        # Format for main log
        log_content = f"""
{self._format_divider('IMPLEMENTATION PLAN', '=')}
[{self._format_timestamp(timestamp)}] Agent: Planner

Summary: {plan_data.get('summary', 'No summary')}
Total Steps: {len(steps)}

Steps:
"""
        for step in steps:
            log_content += f"""
  Step {step.get('order', '?')}: [{step.get('action', 'unknown')}] {step.get('file', 'unknown')}
    Description: {step.get('description', 'No description')}
"""

        log_content += "\n"
        self._append_to_file(self.main_log_file, log_content)

        # Log full plan to agents file
        agents_content = f"""
{'='*60}
PLANNER OUTPUT
{'='*60}
[{self._format_timestamp(timestamp)}]

Full Plan:
{json.dumps(plan_data, indent=2, default=str)}

"""
        if raw_response:
            agents_content += f"""
Raw AI Response:
{'-'*40}
{raw_response}
{'-'*40}

"""
        self._append_to_file(self.agents_log_file, agents_content)
        logger.info(f"[CONV_LOGGER] Logged plan with {len(steps)} steps")

    def log_execution_step(
        self,
        step_number: int,
        total_steps: int,
        step_data: Dict[str, Any],
        result_data: Dict[str, Any],
        generated_code: Optional[str] = None,
        diff: Optional[str] = None,
    ):
        """
        Log executor output for a single step.

        Args:
            step_number: Current step number
            total_steps: Total number of steps
            step_data: Step configuration data
            result_data: Execution result data
            generated_code: The generated code content
            diff: Diff for modified files
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="execution_step",
            agent_name="executor",
            content={
                "step": step_data,
                "result": result_data,
            },
            metadata={
                "step_number": step_number,
                "total_steps": total_steps,
                "generated_code": generated_code,
                "diff": diff,
            }
        )
        self.entries.append(entry)

        file_path = step_data.get("file", result_data.get("file", "unknown"))
        action = step_data.get("action", result_data.get("action", "unknown"))
        success = result_data.get("success", False)

        # Format for main log
        log_content = f"""
{self._format_divider(f'EXECUTION STEP {step_number}/{total_steps}', '-')}
[{self._format_timestamp(timestamp)}] Agent: Executor

File: {file_path}
Action: {action}
Success: {success}
"""
        if result_data.get("error"):
            log_content += f"Error: {result_data.get('error')}\n"

        if generated_code:
            # Show first 50 lines or 2000 chars
            code_preview = generated_code[:2000]
            if len(generated_code) > 2000:
                code_preview += "\n... [truncated]"
            log_content += f"""
Generated Code Preview:
{'-'*30}
{code_preview}
{'-'*30}
"""

        log_content += "\n"
        self._append_to_file(self.main_log_file, log_content)

        # Log full execution details to agents file
        agents_content = f"""
{'='*60}
EXECUTOR OUTPUT - Step {step_number}/{total_steps}
{'='*60}
[{self._format_timestamp(timestamp)}]

Step Configuration:
{json.dumps(step_data, indent=2, default=str)}

Execution Result:
{json.dumps(result_data, indent=2, default=str)}

"""
        if generated_code:
            agents_content += f"""
Full Generated Code:
{'-'*40}
{generated_code}
{'-'*40}

"""
        if diff:
            agents_content += f"""
Diff:
{'-'*40}
{diff}
{'-'*40}

"""
        self._append_to_file(self.agents_log_file, agents_content)

        # Also log to file changes log
        if generated_code or diff:
            files_content = f"""
{'='*60}
FILE CHANGE: {file_path}
{'='*60}
[{self._format_timestamp(timestamp)}]
Action: {action}
Step: {step_number}/{total_steps}

"""
            if diff:
                files_content += f"Diff:\n{diff}\n\n"
            if generated_code:
                files_content += f"Full Content:\n{generated_code}\n\n"

            self._append_to_file(self.files_log_file, files_content)

        logger.info(f"[CONV_LOGGER] Logged execution step {step_number}/{total_steps}: {file_path}")

    def log_validation(
        self,
        validation_data: Dict[str, Any],
        raw_response: Optional[str] = None,
    ):
        """
        Log validator output.

        Args:
            validation_data: Parsed validation data dictionary
            raw_response: Raw AI response if available
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="validation",
            agent_name="validator",
            content=validation_data,
            metadata={"raw_response": raw_response} if raw_response else {},
        )
        self.entries.append(entry)

        approved = validation_data.get("approved", False)
        score = validation_data.get("score", 0)
        errors = validation_data.get("errors", [])

        # Format for main log
        log_content = f"""
{self._format_divider('VALIDATION RESULT', '-')}
[{self._format_timestamp(timestamp)}] Agent: Validator

Approved: {approved}
Score: {score}/100

"""
        if errors:
            log_content += "Issues Found:\n"
            for i, error in enumerate(errors, 1):
                if isinstance(error, dict):
                    log_content += f"  {i}. [{error.get('file', 'general')}] {error.get('message', str(error))}\n"
                else:
                    log_content += f"  {i}. {error}\n"

        log_content += "\n"
        self._append_to_file(self.main_log_file, log_content)

        # Log full validation to agents file
        agents_content = f"""
{'='*60}
VALIDATOR OUTPUT
{'='*60}
[{self._format_timestamp(timestamp)}]

Validation Result:
{json.dumps(validation_data, indent=2, default=str)}

"""
        if raw_response:
            agents_content += f"""
Raw AI Response:
{'-'*40}
{raw_response}
{'-'*40}

"""
        self._append_to_file(self.agents_log_file, agents_content)
        logger.info(f"[CONV_LOGGER] Logged validation: approved={approved}, score={score}")

    def log_fix_attempt(
        self,
        attempt_number: int,
        max_attempts: int,
        issues: List[str],
        fixed_files: List[str],
    ):
        """
        Log a fix attempt during validation retry loop.

        Args:
            attempt_number: Current attempt number
            max_attempts: Maximum allowed attempts
            issues: List of issues being fixed
            fixed_files: List of files that were fixed
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="fix_attempt",
            agent_name="executor",
            content={
                "attempt": attempt_number,
                "max_attempts": max_attempts,
                "issues": issues,
                "fixed_files": fixed_files,
            }
        )
        self.entries.append(entry)

        # Format for main log
        log_content = f"""
{self._format_divider(f'FIX ATTEMPT {attempt_number}/{max_attempts}', '-')}
[{self._format_timestamp(timestamp)}]

Issues Being Fixed:
"""
        for issue in issues[:10]:
            log_content += f"  - {issue}\n"

        log_content += f"\nFiles Fixed: {', '.join(fixed_files)}\n\n"

        self._append_to_file(self.main_log_file, log_content)
        logger.info(f"[CONV_LOGGER] Logged fix attempt {attempt_number}/{max_attempts}")

    def log_response(
        self,
        response_content: str,
        response_type: str = "assistant",  # assistant, answer_chunk, error
        is_streaming: bool = False,
    ):
        """
        Log AI response content.

        Args:
            response_content: The response text
            response_type: Type of response
            is_streaming: Whether this is a streaming chunk
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="response",
            content=response_content,
            metadata={
                "response_type": response_type,
                "is_streaming": is_streaming,
            }
        )
        self.entries.append(entry)

        # Only log complete responses to main log (not streaming chunks)
        if not is_streaming or response_type == "error":
            log_content = f"""
{self._format_divider('AI RESPONSE', '=')}
[{self._format_timestamp(timestamp)}]
Type: {response_type}

{response_content}

"""
            self._append_to_file(self.main_log_file, log_content)

        logger.info(f"[CONV_LOGGER] Logged response: type={response_type}, streaming={is_streaming}")

    def log_event(
        self,
        event_type: str,
        message: str,
        progress: float,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Log a processing event.

        Args:
            event_type: Type of event (from EventType)
            message: Event message
            progress: Progress value (0-1)
            data: Additional event data
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="event",
            content={
                "event_type": event_type,
                "message": message,
                "progress": progress,
            },
            metadata=data or {},
        )
        self.entries.append(entry)

        # Format for main log (brief)
        log_content = f"[{self._format_timestamp(timestamp)}] EVENT: {event_type} ({progress*100:.0f}%) - {message}\n"
        self._append_to_file(self.main_log_file, log_content)

    def log_error(
        self,
        error_message: str,
        error_type: str = "general",
        stack_trace: Optional[str] = None,
    ):
        """
        Log an error.

        Args:
            error_message: Error message
            error_type: Type of error
            stack_trace: Stack trace if available
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="error",
            content=error_message,
            metadata={
                "error_type": error_type,
                "stack_trace": stack_trace,
            }
        )
        self.entries.append(entry)

        log_content = f"""
{self._format_divider('ERROR', '!')}
[{self._format_timestamp(timestamp)}]
Type: {error_type}

{error_message}

"""
        if stack_trace:
            log_content += f"Stack Trace:\n{stack_trace}\n\n"

        self._append_to_file(self.main_log_file, log_content)
        logger.info(f"[CONV_LOGGER] Logged error: {error_type}")

    def log_token_usage(
        self,
        agent_name: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        latency_ms: Optional[int] = None,
    ):
        """
        Log token usage for an AI call.

        Args:
            agent_name: Name of the agent making the call
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used
            latency_ms: Request latency in milliseconds
        """
        timestamp = datetime.utcnow()

        entry = ConversationLogEntry(
            timestamp=timestamp,
            entry_type="token_usage",
            agent_name=agent_name,
            content={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "model": model,
                "latency_ms": latency_ms,
            }
        )
        self.entries.append(entry)

        log_content = f"[{self._format_timestamp(timestamp)}] TOKENS: {agent_name} - {input_tokens} in / {output_tokens} out ({model})"
        if latency_ms:
            log_content += f" [{latency_ms}ms]"
        log_content += "\n"

        self._append_to_file(self.main_log_file, log_content)

    def finalize(self):
        """
        Finalize the conversation log.

        Writes summary and JSON export.
        """
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        # Calculate summary statistics
        user_messages = [e for e in self.entries if e.entry_type == "user_message"]
        responses = [e for e in self.entries if e.entry_type == "response"]
        execution_steps = [e for e in self.entries if e.entry_type == "execution_step"]
        errors = [e for e in self.entries if e.entry_type == "error"]
        token_entries = [e for e in self.entries if e.entry_type == "token_usage"]

        total_input_tokens = sum(e.content.get("input_tokens", 0) for e in token_entries)
        total_output_tokens = sum(e.content.get("output_tokens", 0) for e in token_entries)

        # Write summary to main log
        summary = f"""
{'='*80}
CONVERSATION SUMMARY
{'='*80}
Conversation ID: {self.conversation_id}
Duration: {duration:.2f} seconds
Started: {self.start_time.isoformat()}
Ended: {end_time.isoformat()}

Statistics:
  - User Messages: {len(user_messages)}
  - AI Responses: {len(responses)}
  - Execution Steps: {len(execution_steps)}
  - Errors: {len(errors)}
  - Total Entries: {len(self.entries)}

Token Usage:
  - Input Tokens: {total_input_tokens:,}
  - Output Tokens: {total_output_tokens:,}
  - Total Tokens: {total_input_tokens + total_output_tokens:,}

{'='*80}
END OF LOG
{'='*80}
"""
        self._append_to_file(self.main_log_file, summary)

        # Write JSON export
        json_data = {
            "conversation_id": self.conversation_id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "summary": {
                "user_messages": len(user_messages),
                "ai_responses": len(responses),
                "execution_steps": len(execution_steps),
                "errors": len(errors),
                "total_entries": len(self.entries),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
            },
            "entries": [e.to_dict() for e in self.entries],
        }

        try:
            with open(self.json_log_file, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"[CONV_LOGGER] Failed to write JSON log: {e}")

        logger.info(f"[CONV_LOGGER] Finalized log with {len(self.entries)} entries")

        return {
            "log_dir": str(self.conversation_dir),
            "main_log": str(self.main_log_file),
            "json_log": str(self.json_log_file),
            "files_log": str(self.files_log_file),
            "agents_log": str(self.agents_log_file),
        }

    def get_log_paths(self) -> Dict[str, str]:
        """Get paths to all log files."""
        return {
            "log_dir": str(self.conversation_dir),
            "main_log": str(self.main_log_file),
            "json_log": str(self.json_log_file),
            "files_log": str(self.files_log_file),
            "agents_log": str(self.agents_log_file),
        }


# Singleton-style factory to get/create logger for a conversation
_conversation_loggers: Dict[str, ConversationLogger] = {}


def get_conversation_logger(
    conversation_id: str,
    project_id: str,
    user_id: str,
    log_dir: str = DEFAULT_LOG_DIR,
) -> ConversationLogger:
    """
    Get or create a conversation logger.

    Args:
        conversation_id: Unique conversation identifier
        project_id: Project UUID
        user_id: User UUID
        log_dir: Directory to store log files

    Returns:
        ConversationLogger instance
    """
    if conversation_id not in _conversation_loggers:
        _conversation_loggers[conversation_id] = ConversationLogger(
            conversation_id=conversation_id,
            project_id=project_id,
            user_id=user_id,
            log_dir=log_dir,
        )
    return _conversation_loggers[conversation_id]


def finalize_conversation_logger(conversation_id: str) -> Optional[Dict[str, str]]:
    """
    Finalize and remove a conversation logger.

    Args:
        conversation_id: The conversation to finalize

    Returns:
        Log file paths or None if not found
    """
    if conversation_id in _conversation_loggers:
        logger_instance = _conversation_loggers.pop(conversation_id)
        return logger_instance.finalize()
    return None
