"""
Prompt Optimization Service

Transforms user UI design requests into optimized Claude prompts
following Claude best practices for better UI code generation.

Best Practices Applied:
- XML tags for structure
- Chain-of-thought instructions
- Positive and negative examples
- Role prompting for design expertise
- Clear, direct, and detailed instructions
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from app.services.frontend_detector import (
    FrontendDetectionResult,
    FrontendFramework,
    ExistingComponent,
)

logger = logging.getLogger(__name__)


@dataclass
class OptimizedPrompt:
    """Result of prompt optimization."""
    optimized_prompt: str
    system_prompt: str
    context_summary: str
    enhancements_applied: List[str] = field(default_factory=list)
    estimated_tokens: int = 0


@dataclass
class UIDesignContext:
    """Context for UI design optimization."""
    user_request: str
    frontend_tech: str
    css_framework: str
    ui_libraries: List[str]
    component_path: str
    style_path: str
    design_tokens: str
    existing_components: List[ExistingComponent]
    uses_typescript: bool = False
    uses_dark_mode: bool = False


class PromptOptimizer:
    """
    Transforms user requests into optimized Claude prompts
    for UI code generation.

    Applies Claude prompt engineering best practices:
    - Uses XML tags to structure prompts
    - Includes positive and negative examples
    - Adds chain-of-thought instructions
    - Uses role prompting for design expertise
    - Adds specific constraints and guidelines
    """

    def optimize(
        self,
        user_request: str,
        detection_result: FrontendDetectionResult,
    ) -> OptimizedPrompt:
        """
        Optimize a user request into a detailed Claude prompt.

        Args:
            user_request: The original user request
            detection_result: Frontend technology detection result

        Returns:
            OptimizedPrompt with optimized prompt and metadata
        """
        logger.info(f"[PROMPT_OPTIMIZER] Optimizing request: {user_request[:100]}...")

        enhancements = []

        # Build context
        context = UIDesignContext(
            user_request=user_request,
            frontend_tech=detection_result.primary_framework.value,
            css_framework=detection_result.css_framework.value,
            ui_libraries=detection_result.ui_libraries,
            component_path=detection_result.component_path,
            style_path=detection_result.style_path,
            design_tokens=detection_result.design_tokens.to_prompt_string(),
            existing_components=detection_result.existing_components,
            uses_typescript=detection_result.uses_typescript,
            uses_dark_mode=self._detect_dark_mode(detection_result),
        )

        # Analyze the request
        request_analysis = self._analyze_request(user_request)
        enhancements.append("request_analysis")

        # Build the optimized prompt
        optimized_prompt = self._build_optimized_prompt(context, request_analysis)
        enhancements.append("xml_structure")
        enhancements.append("chain_of_thought")
        enhancements.append("design_constraints")

        # Build the system prompt
        system_prompt = self._build_system_prompt(context)
        enhancements.append("role_prompting")

        # Add examples if appropriate
        if self._should_add_examples(request_analysis):
            optimized_prompt = self._add_examples(optimized_prompt, context)
            enhancements.append("examples")

        # Estimate tokens
        estimated_tokens = self._estimate_tokens(optimized_prompt + system_prompt)

        # Build context summary
        context_summary = self._build_context_summary(context, request_analysis)

        logger.info(
            f"[PROMPT_OPTIMIZER] Optimization complete: "
            f"enhancements={enhancements}, tokens~{estimated_tokens}"
        )

        return OptimizedPrompt(
            optimized_prompt=optimized_prompt,
            system_prompt=system_prompt,
            context_summary=context_summary,
            enhancements_applied=enhancements,
            estimated_tokens=estimated_tokens,
        )

    def _detect_dark_mode(self, detection: FrontendDetectionResult) -> bool:
        """Detect if project uses dark mode."""
        # Check CSS variables for dark mode
        css_vars = detection.design_tokens.css_variables
        dark_indicators = ["--dark", "dark-mode", "color-scheme"]
        for var in css_vars:
            if any(ind in var.lower() for ind in dark_indicators):
                return True

        # Check tailwind config
        if detection.tailwind_config:
            if "darkMode" in detection.tailwind_config:
                return True

        return False

    def _analyze_request(self, user_request: str) -> Dict[str, Any]:
        """Analyze the user request to understand intent."""
        request_lower = user_request.lower()

        analysis = {
            "type": "component",  # component, page, layout, feature
            "complexity": "simple",  # simple, moderate, complex
            "includes_data": False,
            "includes_forms": False,
            "includes_charts": False,
            "includes_tables": False,
            "includes_navigation": False,
            "includes_modals": False,
            "keywords": [],
        }

        # Detect type
        if any(w in request_lower for w in ["page", "screen", "view"]):
            analysis["type"] = "page"
        elif any(w in request_lower for w in ["layout", "template", "wrapper"]):
            analysis["type"] = "layout"
        elif any(w in request_lower for w in ["dashboard", "feature", "system"]):
            analysis["type"] = "feature"

        # Detect complexity
        complexity_indicators = {
            "simple": ["button", "card", "badge", "avatar", "icon"],
            "moderate": ["form", "list", "table", "menu", "dropdown"],
            "complex": ["dashboard", "wizard", "editor", "builder", "system"],
        }
        for level, keywords in complexity_indicators.items():
            if any(kw in request_lower for kw in keywords):
                analysis["complexity"] = level

        # Detect specific features
        analysis["includes_data"] = any(
            w in request_lower for w in ["data", "fetch", "api", "load", "dynamic"]
        )
        analysis["includes_forms"] = any(
            w in request_lower for w in ["form", "input", "submit", "validation"]
        )
        analysis["includes_charts"] = any(
            w in request_lower for w in ["chart", "graph", "analytics", "visualization"]
        )
        analysis["includes_tables"] = any(
            w in request_lower for w in ["table", "grid", "list", "pagination"]
        )
        analysis["includes_navigation"] = any(
            w in request_lower for w in ["nav", "menu", "sidebar", "header", "footer"]
        )
        analysis["includes_modals"] = any(
            w in request_lower for w in ["modal", "dialog", "popup", "overlay"]
        )

        # Extract keywords
        keywords = re.findall(r'\b(?:with|include|add|create|show|display)\s+(\w+)', request_lower)
        analysis["keywords"] = keywords

        return analysis

    def _build_optimized_prompt(
        self,
        context: UIDesignContext,
        analysis: Dict[str, Any],
    ) -> str:
        """Build the optimized user prompt with XML structure."""

        # Build requirements based on analysis
        requirements = self._generate_requirements(context, analysis)

        # Build constraints
        constraints = self._generate_constraints(context)

        # Build file structure guidance
        file_structure = self._generate_file_structure(context, analysis)

        prompt = f"""<task>
{context.user_request}
</task>

<requirements>
{requirements}
</requirements>

<constraints>
{constraints}
</constraints>

<design_context>
<framework>{context.frontend_tech}</framework>
<css>{context.css_framework}</css>
<libraries>{', '.join(context.ui_libraries) if context.ui_libraries else 'None specified'}</libraries>
<typescript>{context.uses_typescript}</typescript>
<dark_mode>{context.uses_dark_mode}</dark_mode>

<design_tokens>
{context.design_tokens}
</design_tokens>

<existing_components>
{self._format_existing_components(context.existing_components)}
</existing_components>
</design_context>

<file_structure>
{file_structure}
</file_structure>

<thinking_instructions>
Before generating code, think through:
1. What components are needed and how they relate
2. What existing components can be reused
3. What design tokens should be applied
4. How to ensure responsive design
5. What states need to be handled (loading, error, empty)
6. How to match existing code patterns
</thinking_instructions>

<output_requirements>
Generate complete, production-ready code for each file.
Use the exact format:
<file path="path/to/file.{self._get_file_extension(context)}" type="component|style|config">
[complete file content here]
</file>

CRITICAL:
- Include ALL imports
- Include ALL code - no placeholders or "// ... rest of code"
- Follow existing naming conventions from the project
- Use design tokens, NEVER hardcoded colors
- Ensure responsive design for mobile/tablet/desktop
</output_requirements>"""

        return prompt

    def _build_system_prompt(self, context: UIDesignContext) -> str:
        """Build the system prompt with role and guidelines."""
        from app.agents.ui_designer_identity import (
            UI_DESIGNER_SYSTEM_PROMPT,
            get_framework_guidelines,
        )

        return UI_DESIGNER_SYSTEM_PROMPT.format(
            frontend_tech=context.frontend_tech,
            css_framework=context.css_framework,
            ui_libraries=", ".join(context.ui_libraries) if context.ui_libraries else "None",
            component_path=context.component_path,
            style_path=context.style_path,
            design_tokens=context.design_tokens,
            existing_components=self._format_existing_components(context.existing_components),
            framework_guidelines=get_framework_guidelines(context.frontend_tech),
        )

    def _generate_requirements(
        self,
        context: UIDesignContext,
        analysis: Dict[str, Any],
    ) -> str:
        """Generate requirements based on request analysis."""
        requirements = []

        # Base requirements
        requirements.append("1. Create a complete, working implementation")
        requirements.append("2. Follow the project's existing design patterns")
        requirements.append("3. Use responsive design (mobile-first)")

        # Type-specific requirements
        if analysis["type"] == "page":
            requirements.append("4. Include proper page layout and structure")
            requirements.append("5. Add appropriate meta/head elements if needed")
        elif analysis["type"] == "layout":
            requirements.append("4. Include slots/children for content areas")
            requirements.append("5. Handle navigation and routing context")
        elif analysis["type"] == "feature":
            requirements.append("4. Break down into smaller, focused components")
            requirements.append("5. Include all necessary sub-components")

        # Feature-specific requirements
        req_num = len(requirements) + 1
        if analysis["includes_forms"]:
            requirements.append(f"{req_num}. Include form validation and error handling")
            req_num += 1
        if analysis["includes_tables"]:
            requirements.append(f"{req_num}. Include sorting, filtering, and pagination if appropriate")
            req_num += 1
        if analysis["includes_charts"]:
            requirements.append(f"{req_num}. Use the project's charting library if available")
            req_num += 1
        if analysis["includes_modals"]:
            requirements.append(f"{req_num}. Include proper accessibility for modals (focus trap, escape key)")
            req_num += 1

        # Dark mode requirement
        if context.uses_dark_mode:
            requirements.append(f"{req_num}. Support dark mode with appropriate variants")

        return "\n".join(requirements)

    def _generate_constraints(self, context: UIDesignContext) -> str:
        """Generate constraints for the design."""
        constraints = [
            "- Use ONLY design tokens from the project - no hardcoded colors (#hex values)",
            "- Maximum 50 lines per component when possible",
            f"- Place components in: {context.component_path}",
            f"- Use {context.css_framework} for styling",
        ]

        if context.uses_typescript:
            constraints.append("- Include TypeScript types for all props and state")

        if context.ui_libraries:
            constraints.append(f"- Prefer using: {', '.join(context.ui_libraries[:3])}")

        constraints.extend([
            "- Include loading states for async content",
            "- Include error states for potential failures",
            "- Include empty states where appropriate",
            "- Follow existing component patterns from the project",
        ])

        return "\n".join(constraints)

    def _generate_file_structure(
        self,
        context: UIDesignContext,
        analysis: Dict[str, Any],
    ) -> str:
        """Generate suggested file structure."""
        ext = self._get_file_extension(context)

        if analysis["type"] == "page":
            return f"""Suggested structure:
- {context.component_path.replace('Components', 'Pages')}/[PageName].{ext} (main page)
- {context.component_path}/[ComponentName].{ext} (reusable components)"""
        elif analysis["type"] == "feature":
            return f"""Suggested structure:
- {context.component_path}/[FeatureName]/index.{ext} (main component)
- {context.component_path}/[FeatureName]/[SubComponent].{ext} (sub-components)"""
        else:
            return f"""Suggested structure:
- {context.component_path}/[ComponentName].{ext}"""

    def _format_existing_components(
        self, components: List[ExistingComponent]
    ) -> str:
        """Format existing components for prompt."""
        if not components:
            return "No existing components found in the project."

        formatted = []
        for comp in components[:15]:  # Limit to 15 components
            props_str = f" props=[{', '.join(comp.props[:5])}]" if comp.props else ""
            formatted.append(f"- {comp.name} ({comp.component_type}){props_str}")

        return "\n".join(formatted)

    def _get_file_extension(self, context: UIDesignContext) -> str:
        """Get file extension based on framework and TypeScript usage."""
        if context.frontend_tech == FrontendFramework.REACT.value:
            return "tsx" if context.uses_typescript else "jsx"
        elif context.frontend_tech == FrontendFramework.VUE.value:
            return "vue"
        elif context.frontend_tech in [FrontendFramework.BLADE.value, FrontendFramework.LIVEWIRE.value]:
            return "blade.php"
        return "jsx"

    def _should_add_examples(self, analysis: Dict[str, Any]) -> bool:
        """Determine if examples should be added to the prompt."""
        # Add examples for complex requests
        return analysis["complexity"] in ["moderate", "complex"]

    def _add_examples(self, prompt: str, context: UIDesignContext) -> str:
        """Add positive and negative examples to the prompt."""
        examples = self._get_examples(context.frontend_tech)

        example_section = f"""
<examples>
<positive_example>
{examples['positive']}
</positive_example>

<negative_example>
{examples['negative']}
</negative_example>
</examples>
"""
        # Insert before output_requirements
        return prompt.replace("<output_requirements>", example_section + "<output_requirements>")

    def _get_examples(self, frontend_tech: str) -> Dict[str, str]:
        """Get framework-specific examples."""
        if frontend_tech == FrontendFramework.REACT.value:
            return {
                "positive": """// GOOD: Uses design tokens, proper types, accessible
import { cn } from "@/lib/utils";

interface ButtonProps {
  variant?: "primary" | "secondary";
  children: React.ReactNode;
  onClick?: () => void;
}

export function Button({ variant = "primary", children, onClick }: ButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-4 py-2 rounded-md font-medium transition-colors",
        "focus:outline-none focus:ring-2 focus:ring-offset-2",
        variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary/90",
        variant === "secondary" && "bg-secondary text-secondary-foreground hover:bg-secondary/90"
      )}
    >
      {children}
    </button>
  );
}""",
                "negative": """// BAD: Hardcoded colors, no types, not accessible
export default function Button(props) {
  return (
    <button
      onClick={props.onClick}
      style={{ backgroundColor: '#3b82f6', color: 'white', padding: '8px 16px' }}
    >
      {props.children}
    </button>
  );
}""",
            }
        elif frontend_tech == FrontendFramework.VUE.value:
            return {
                "positive": """<!-- GOOD: Uses design tokens, typed props, accessible -->
<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary';
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary'
});
</script>

<template>
  <button
    :class="[
      'px-4 py-2 rounded-md font-medium transition-colors',
      'focus:outline-none focus:ring-2 focus:ring-offset-2',
      variant === 'primary' && 'bg-primary text-primary-foreground hover:bg-primary/90',
      variant === 'secondary' && 'bg-secondary text-secondary-foreground hover:bg-secondary/90'
    ]"
  >
    <slot />
  </button>
</template>""",
                "negative": """<!-- BAD: Hardcoded colors, no types -->
<template>
  <button style="background-color: #3b82f6; color: white; padding: 8px 16px;">
    <slot />
  </button>
</template>""",
            }
        else:  # Blade/Livewire
            return {
                "positive": """{{-- GOOD: Uses Tailwind classes, proper props, accessible --}}
@props([
    'variant' => 'primary',
    'type' => 'button',
])

@php
$classes = match($variant) {
    'primary' => 'bg-primary text-primary-foreground hover:bg-primary/90',
    'secondary' => 'bg-secondary text-secondary-foreground hover:bg-secondary/90',
};
@endphp

<button
    type="{{ $type }}"
    {{ $attributes->merge(['class' => "px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 {$classes}"]) }}
>
    {{ $slot }}
</button>""",
                "negative": """{{-- BAD: Hardcoded colors, inline styles --}}
<button style="background-color: #3b82f6; color: white; padding: 8px 16px;">
    {{ $slot }}
</button>""",
            }

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for the prompt."""
        # Rough estimation: ~4 characters per token
        return len(text) // 4

    def _build_context_summary(
        self,
        context: UIDesignContext,
        analysis: Dict[str, Any],
    ) -> str:
        """Build a human-readable context summary."""
        return (
            f"Request Type: {analysis['type']} ({analysis['complexity']} complexity)\n"
            f"Framework: {context.frontend_tech} with {context.css_framework}\n"
            f"Libraries: {', '.join(context.ui_libraries) if context.ui_libraries else 'None'}\n"
            f"TypeScript: {context.uses_typescript}\n"
            f"Dark Mode: {context.uses_dark_mode}\n"
            f"Existing Components: {len(context.existing_components)}"
        )


def optimize_ui_prompt(
    user_request: str,
    detection_result: FrontendDetectionResult,
) -> OptimizedPrompt:
    """
    Convenience function to optimize a UI design prompt.

    Args:
        user_request: The original user request
        detection_result: Frontend technology detection result

    Returns:
        OptimizedPrompt with optimized prompt and metadata
    """
    optimizer = PromptOptimizer()
    return optimizer.optimize(user_request, detection_result)
