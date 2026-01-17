"""
Structured Outputs Service for Claude API.

Provides JSON Schema-based structured outputs for guaranteed response formats.
Ensures reliable parsing and validation of AI responses.
"""
import json
import logging
import time
from typing import Optional, Any, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ValidationError
from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class OutputFormat(str, Enum):
    """Predefined output formats."""
    INTENT_ANALYSIS = "intent_analysis"
    CODE_PLAN = "code_plan"
    VALIDATION_RESULT = "validation_result"
    CODE_REVIEW = "code_review"
    SECURITY_SCAN = "security_scan"
    ERROR_DIAGNOSIS = "error_diagnosis"


# Predefined JSON Schemas for common use cases
SCHEMAS = {
    OutputFormat.INTENT_ANALYSIS: {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "enum": ["feature", "bugfix", "refactor", "question"],
                "description": "The type of task being requested"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score for the classification"
            },
            "domains_affected": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Laravel domains affected by this request"
            },
            "scope": {
                "type": "string",
                "enum": ["single_file", "feature", "cross_domain"],
                "description": "Scope of changes required"
            },
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Programming languages involved"
            },
            "requires_migration": {
                "type": "boolean",
                "description": "Whether database migration is needed"
            },
            "search_queries": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "description": "Search queries for finding relevant code"
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key entities mentioned in the request"
            }
        },
        "required": ["task_type", "confidence", "domains_affected", "scope", "search_queries"]
    },

    OutputFormat.CODE_PLAN: {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of the implementation plan"
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "order": {"type": "integer"},
                        "action": {"type": "string", "enum": ["create", "modify", "delete"]},
                        "file": {"type": "string"},
                        "description": {"type": "string"},
                        "changes_summary": {"type": "string"},
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "integer"}
                        }
                    },
                    "required": ["order", "action", "file", "description"]
                },
                "description": "Ordered list of implementation steps"
            },
            "estimated_complexity": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Estimated implementation complexity"
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Potential risks or concerns"
            },
            "testing_notes": {
                "type": "string",
                "description": "Notes on how to test the changes"
            }
        },
        "required": ["summary", "steps", "estimated_complexity"]
    },

    OutputFormat.VALIDATION_RESULT: {
        "type": "object",
        "properties": {
            "approved": {
                "type": "boolean",
                "description": "Whether the code passes validation"
            },
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Quality score from 0-100"
            },
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["critical", "error", "warning"]},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "message": {"type": "string"},
                        "suggestion": {"type": "string"}
                    },
                    "required": ["severity", "message"]
                },
                "description": "List of validation errors"
            },
            "warnings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "message": {"type": "string"}
                    },
                    "required": ["message"]
                },
                "description": "List of warnings"
            },
            "improvements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested improvements"
            }
        },
        "required": ["approved", "score", "errors"]
    },

    OutputFormat.CODE_REVIEW: {
        "type": "object",
        "properties": {
            "quality_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
            },
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["critical", "warning", "info"]},
                        "category": {"type": "string"},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "message": {"type": "string"},
                        "suggestion": {"type": "string"}
                    },
                    "required": ["severity", "category", "message"]
                }
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"}
            },
            "best_practices": {
                "type": "object",
                "properties": {
                    "followed": {"type": "array", "items": {"type": "string"}},
                    "violated": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "required": ["quality_score", "summary", "issues"]
    },

    OutputFormat.SECURITY_SCAN: {
        "type": "object",
        "properties": {
            "security_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Security score (100 = most secure)"
            },
            "vulnerabilities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "cwe_id": {"type": "string"},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "description": {"type": "string"},
                        "recommendation": {"type": "string"}
                    },
                    "required": ["type", "severity", "description"]
                }
            },
            "owasp_compliance": {
                "type": "object",
                "additionalProperties": {"type": "boolean"}
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["security_score", "vulnerabilities"]
    },

    OutputFormat.ERROR_DIAGNOSIS: {
        "type": "object",
        "properties": {
            "error_type": {"type": "string"},
            "root_cause": {"type": "string"},
            "affected_files": {
                "type": "array",
                "items": {"type": "string"}
            },
            "fix_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer"},
                        "action": {"type": "string"},
                        "file": {"type": "string"},
                        "code": {"type": "string"}
                    },
                    "required": ["step", "action"]
                }
            },
            "prevention_tips": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["error_type", "root_cause", "fix_steps"]
    }
}


@dataclass
class StructuredResponse(Generic[T]):
    """Response from structured output request."""
    success: bool
    data: Optional[T] = None
    raw_content: Optional[str] = None
    error: Optional[str] = None
    validation_errors: list[str] = field(default_factory=list)
    tokens_used: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data.model_dump() if self.data and hasattr(self.data, 'model_dump') else self.data,
            "raw_content": self.raw_content,
            "error": self.error,
            "validation_errors": self.validation_errors,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }


class StructuredOutputService:
    """
    Service for generating structured outputs from Claude API.

    Uses JSON Schema to guarantee response format and enable reliable parsing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the structured output service.

        Args:
            api_key: Anthropic API key. Uses settings if not provided.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        logger.info("[STRUCTURED_OUTPUTS] Service initialized")

    def _build_schema_prompt(
        self,
        schema: dict,
        include_examples: bool = True,
    ) -> str:
        """Build a prompt section that instructs Claude to follow the schema."""
        schema_str = json.dumps(schema, indent=2)

        prompt = f"""You must respond with a valid JSON object that strictly follows this schema:

```json
{schema_str}
```

Important:
1. Your response must be ONLY the JSON object, no additional text
2. All required fields must be present
3. All values must match their specified types
4. Enum values must be exactly as specified
5. Arrays must contain items of the correct type"""

        return prompt

    async def generate_with_schema(
        self,
        prompt: str,
        schema: dict,
        model: str = "claude-sonnet-4-5-20250929",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> StructuredResponse[dict]:
        """
        Generate a response following a custom JSON schema.

        Args:
            prompt: User prompt
            schema: JSON Schema to follow
            model: Claude model to use
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            StructuredResponse with parsed data
        """
        logger.info(f"[STRUCTURED_OUTPUTS] Generating with custom schema, model={model}")
        start_time = time.time()

        # Build full system prompt
        schema_instructions = self._build_schema_prompt(schema)
        full_system = f"{system_prompt}\n\n{schema_instructions}" if system_prompt else schema_instructions

        try:
            response = await self.async_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=full_system,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            logger.info(f"[STRUCTURED_OUTPUTS] Response received, tokens={tokens_used}, latency={latency_ms}ms")

            # Parse JSON
            try:
                # Clean up response
                content_clean = content.strip()
                if content_clean.startswith("```"):
                    lines = content_clean.split("\n")
                    content_clean = "\n".join(lines[1:-1])

                data = json.loads(content_clean)

                return StructuredResponse(
                    success=True,
                    data=data,
                    raw_content=content,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                )

            except json.JSONDecodeError as e:
                logger.error(f"[STRUCTURED_OUTPUTS] JSON parse error: {e}")
                return StructuredResponse(
                    success=False,
                    raw_content=content,
                    error=f"JSON parse error: {e}",
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                )

        except Exception as e:
            logger.error(f"[STRUCTURED_OUTPUTS] Generation error: {e}")
            return StructuredResponse(
                success=False,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )

    async def generate_with_format(
        self,
        prompt: str,
        output_format: OutputFormat,
        model: str = "claude-sonnet-4-5-20250929",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> StructuredResponse[dict]:
        """
        Generate a response using a predefined output format.

        Args:
            prompt: User prompt
            output_format: Predefined format to use
            model: Claude model to use
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            StructuredResponse with parsed data
        """
        schema = SCHEMAS.get(output_format)
        if not schema:
            return StructuredResponse(
                success=False,
                error=f"Unknown output format: {output_format}",
            )

        logger.info(f"[STRUCTURED_OUTPUTS] Generating with format={output_format.value}")
        return await self.generate_with_schema(
            prompt=prompt,
            schema=schema,
            model=model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_with_pydantic(
        self,
        prompt: str,
        model_class: type[T],
        claude_model: str = "claude-sonnet-4-5-20250929",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> StructuredResponse[T]:
        """
        Generate a response and validate against a Pydantic model.

        Args:
            prompt: User prompt
            model_class: Pydantic model class for validation
            claude_model: Claude model to use
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            StructuredResponse with validated Pydantic model
        """
        logger.info(f"[STRUCTURED_OUTPUTS] Generating with Pydantic model={model_class.__name__}")

        # Get JSON schema from Pydantic model
        schema = model_class.model_json_schema()

        response = await self.generate_with_schema(
            prompt=prompt,
            schema=schema,
            model=claude_model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if not response.success or response.data is None:
            return StructuredResponse(
                success=False,
                raw_content=response.raw_content,
                error=response.error,
                tokens_used=response.tokens_used,
                latency_ms=response.latency_ms,
            )

        # Validate with Pydantic
        try:
            validated_data = model_class.model_validate(response.data)
            logger.info(f"[STRUCTURED_OUTPUTS] Pydantic validation passed for {model_class.__name__}")

            return StructuredResponse(
                success=True,
                data=validated_data,
                raw_content=response.raw_content,
                tokens_used=response.tokens_used,
                latency_ms=response.latency_ms,
            )

        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            logger.error(f"[STRUCTURED_OUTPUTS] Pydantic validation failed: {errors}")

            return StructuredResponse(
                success=False,
                data=response.data,
                raw_content=response.raw_content,
                error="Pydantic validation failed",
                validation_errors=errors,
                tokens_used=response.tokens_used,
                latency_ms=response.latency_ms,
            )

    async def analyze_intent(
        self,
        user_input: str,
        project_context: Optional[str] = None,
    ) -> StructuredResponse[dict]:
        """
        Analyze user intent with structured output.

        Args:
            user_input: User's request text
            project_context: Optional project context

        Returns:
            StructuredResponse with intent analysis
        """
        system = "You are an expert at analyzing developer requests for Laravel applications."
        prompt = f"""Analyze this user request and classify it:

User Request: {user_input}

{"Project Context: " + project_context if project_context else ""}

Provide a structured analysis of what the user wants to accomplish."""

        return await self.generate_with_format(
            prompt=prompt,
            output_format=OutputFormat.INTENT_ANALYSIS,
            model="claude-haiku-4-5-20251001",  # Use Haiku for fast intent analysis
            system_prompt=system,
            temperature=0.3,
        )

    async def create_code_plan(
        self,
        user_request: str,
        context: str,
        project_info: Optional[str] = None,
    ) -> StructuredResponse[dict]:
        """
        Create a structured code implementation plan.

        Args:
            user_request: What the user wants
            context: Retrieved code context
            project_info: Optional project information

        Returns:
            StructuredResponse with implementation plan
        """
        system = "You are an expert Laravel architect who creates detailed implementation plans."
        prompt = f"""Create an implementation plan for this request:

Request: {user_request}

Relevant Code Context:
{context}

{"Project Info: " + project_info if project_info else ""}

Create a step-by-step plan with specific file changes."""

        return await self.generate_with_format(
            prompt=prompt,
            output_format=OutputFormat.CODE_PLAN,
            system_prompt=system,
            temperature=0.5,
        )

    async def validate_code(
        self,
        code: str,
        file_path: str,
        requirements: Optional[str] = None,
    ) -> StructuredResponse[dict]:
        """
        Validate generated code with structured output.

        Args:
            code: Code to validate
            file_path: Path of the file
            requirements: Original requirements

        Returns:
            StructuredResponse with validation result
        """
        system = "You are an expert code reviewer for Laravel applications."
        prompt = f"""Validate this code:

File: {file_path}

```
{code}
```

{"Requirements: " + requirements if requirements else ""}

Check for errors, best practices, and potential issues."""

        return await self.generate_with_format(
            prompt=prompt,
            output_format=OutputFormat.VALIDATION_RESULT,
            system_prompt=system,
            temperature=0.3,
        )

    async def diagnose_error(
        self,
        error_message: str,
        code_context: str,
        stack_trace: Optional[str] = None,
    ) -> StructuredResponse[dict]:
        """
        Diagnose an error with structured output.

        Args:
            error_message: The error message
            code_context: Relevant code
            stack_trace: Optional stack trace

        Returns:
            StructuredResponse with error diagnosis
        """
        system = "You are an expert at debugging Laravel applications."
        prompt = f"""Diagnose this error:

Error: {error_message}

{"Stack Trace:\n" + stack_trace if stack_trace else ""}

Code Context:
{code_context}

Identify the root cause and provide fix steps."""

        return await self.generate_with_format(
            prompt=prompt,
            output_format=OutputFormat.ERROR_DIAGNOSIS,
            system_prompt=system,
            temperature=0.3,
        )


# Factory function
def get_structured_output_service() -> StructuredOutputService:
    """Get a structured output service instance."""
    return StructuredOutputService()
