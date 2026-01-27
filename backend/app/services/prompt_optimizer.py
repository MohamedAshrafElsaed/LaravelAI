"""
Prompt Optimization Service for UI Designer.

Transforms user design requests into optimized Claude prompts
following Claude best practices for code generation.

Features:
- XML tag structuring
- Chain-of-thought instructions
- Design system context injection
- Framework-specific guidelines
- Example-based prompting
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from app.schemas.ui_designer import (
    FrontendTechStack,
    FrontendFramework,
    OptimizedPrompt,
    DesignTokens,
    ExistingComponent,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

SYSTEM_PROMPT_TEMPLATE = """<role>
You are Palette, an expert UI designer and senior frontend developer. You create
beautiful, production-ready UI components that are immediately usable without
any modifications.

Your designs are:
- BEAUTIFUL BY DEFAULT - Modern, clean, visually stunning
- RESPONSIVE - Work perfectly on mobile, tablet, and desktop
- ACCESSIBLE - Include proper ARIA labels, keyboard navigation, contrast
- COMPLETE - No placeholders, TODOs, or incomplete code
</role>

<technology_stack>
{tech_stack_context}
</technology_stack>

<design_system>
{design_system_context}
</design_system>

<critical_rules>
1. **EXACT REQUEST**: Do EXACTLY what the user asks - nothing more, nothing less
2. **NO HARDCODED COLORS**: Always use design tokens, CSS variables, or Tailwind classes
3. **FOLLOW PATTERNS**: Match the existing codebase patterns and conventions
4. **SMALL COMPONENTS**: Create focused components under 100 lines when possible
5. **COMPLETE CODE**: Include ALL imports, exports, and necessary code
6. **TYPE SAFETY**: Use TypeScript types/interfaces if the project uses TypeScript

For each file, output in this EXACT format:
<file path="path/to/file.tsx" type="component">
// Complete file content here
</file>

Include ALL necessary imports and complete implementation.
</critical_rules>

<framework_guidelines>
{framework_guidelines}
</framework_guidelines>

<output_structure>
Generate files in this order:
1. Main component/page
2. Sub-components (if needed)
3. Hooks/utilities (if needed)
4. Styles (if separate CSS needed)

For each file, wrap in <file> tags with path and type attributes.
</output_structure>"""


REACT_GUIDELINES = """
<react_specific>
- Use functional components with hooks
- Use 'use client' directive for client-side components in Next.js
- Prefer composition over inheritance
- Use React.FC<Props> or explicit return types
- Destructure props in function signature
- Use named exports for components
- Organize imports: React, third-party, local components, utils, styles
- Use shadcn/ui components when available: Button, Card, Input, etc.
- Use Radix primitives for complex interactions

Example component structure:
```tsx
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface ComponentNameProps {
  title: string;
  onAction?: () => void;
}

export function ComponentName({ title, onAction }: ComponentNameProps) {
  const [state, setState] = useState(false);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Button onClick={onAction}>Action</Button>
      </CardContent>
    </Card>
  );
}
```
</react_specific>
"""


VUE_GUIDELINES = """
<vue_specific>
- Use Vue 3 Composition API with <script setup>
- Use defineProps and defineEmits for component API
- Prefer ref() for primitives, reactive() for objects
- Use computed() for derived state
- Use Headless UI or PrimeVue components when available
- Single-file components (.vue) with template, script, style order

Example component structure:
```vue
<template>
  <div class="component-name">
    <h2>{{ title }}</h2>
    <button @click="handleAction">Action</button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

interface Props {
  title: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  action: [value: string];
}>();

const state = ref(false);

function handleAction() {
  emit('action', 'value');
}
</script>

<style scoped>
.component-name {
  @apply p-4 rounded-lg bg-background;
}
</style>
```
</vue_specific>
"""


BLADE_GUIDELINES = """
<blade_specific>
- Use Blade component syntax: <x-component-name />
- Extract reusable components to resources/views/components/
- Use Alpine.js for interactivity with x-data, x-show, x-on directives
- Use Tailwind CSS for styling
- Include @props directive for component properties
- Use slots for flexible content

Example component structure:
```blade
{{-- resources/views/components/card.blade.php --}}
@props([
    'title' => '',
    'description' => '',
])

<div {{ $attributes->merge(['class' => 'bg-white rounded-lg shadow p-6']) }}>
    @if($title)
        <h3 class="text-lg font-semibold text-gray-900">{{ $title }}</h3>
    @endif

    @if($description)
        <p class="mt-2 text-gray-600">{{ $description }}</p>
    @endif

    <div class="mt-4">
        {{ $slot }}
    </div>
</div>
```

Usage:
```blade
<x-card title="My Card" description="Card description">
    <button class="btn btn-primary">Action</button>
</x-card>
```
</blade_specific>
"""


LIVEWIRE_GUIDELINES = """
<livewire_specific>
- Create Livewire components with php artisan make:livewire pattern
- Use wire:model for two-way binding
- Use wire:click for actions
- Combine with Alpine.js for client-side interactivity
- Keep component logic in the PHP class, view logic in Blade

Example PHP component:
```php
<?php

namespace App\\Livewire;

use Livewire\\Component;

class ComponentName extends Component
{
    public string $title = '';
    public bool $isOpen = false;

    public function toggle(): void
    {
        $this->isOpen = !$this->isOpen;
    }

    public function render()
    {
        return view('livewire.component-name');
    }
}
```

Example Blade view:
```blade
{{-- resources/views/livewire/component-name.blade.php --}}
<div class="p-4 bg-white rounded-lg shadow">
    <h2 class="text-lg font-semibold">{{ $title }}</h2>

    <button
        wire:click="toggle"
        class="mt-4 px-4 py-2 bg-primary text-white rounded"
    >
        {{ $isOpen ? 'Close' : 'Open' }}
    </button>

    @if($isOpen)
        <div class="mt-4 p-4 bg-gray-50 rounded">
            Content here
        </div>
    @endif
</div>
```
</livewire_specific>
"""


USER_PROMPT_TEMPLATE = """<task>
{user_request}
</task>

<requirements>
{extracted_requirements}
</requirements>

<constraints>
- Use ONLY design tokens from the design system (no hardcoded colors)
- Match existing component patterns in the project
- Maximum {max_files} new files
- Components should be under {max_lines} lines each
- Include loading states and error handling where appropriate
{additional_constraints}
</constraints>

<existing_components>
{existing_components}
</existing_components>

<thinking_instructions>
Before generating code:
1. Analyze what components are needed
2. Identify which existing components to use vs. create new
3. Plan the component hierarchy
4. Consider responsive breakpoints (mobile-first)
5. Think about user interactions and states
6. Ensure accessibility requirements are met

After planning, generate COMPLETE files wrapped in <file> tags.
</thinking_instructions>"""


# =============================================================================
# REQUIREMENTS EXTRACTION
# =============================================================================

@dataclass
class ExtractedRequirements:
    """Requirements extracted from user prompt."""

    component_types: List[str] = field(default_factory=list)
    ui_elements: List[str] = field(default_factory=list)
    interactions: List[str] = field(default_factory=list)
    data_display: List[str] = field(default_factory=list)
    layout_hints: List[str] = field(default_factory=list)
    style_hints: List[str] = field(default_factory=list)
    accessibility_requirements: List[str] = field(default_factory=list)
    estimated_complexity: str = "medium"

    def to_string(self) -> str:
        """Convert to formatted string for prompt."""
        parts = []

        if self.component_types:
            parts.append(f"- Components needed: {', '.join(self.component_types)}")
        if self.ui_elements:
            parts.append(f"- UI elements: {', '.join(self.ui_elements)}")
        if self.interactions:
            parts.append(f"- Interactions: {', '.join(self.interactions)}")
        if self.data_display:
            parts.append(f"- Data display: {', '.join(self.data_display)}")
        if self.layout_hints:
            parts.append(f"- Layout: {', '.join(self.layout_hints)}")
        if self.style_hints:
            parts.append(f"- Style preferences: {', '.join(self.style_hints)}")

        return "\n".join(parts) if parts else "- Generate based on the task description"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component_types": self.component_types,
            "ui_elements": self.ui_elements,
            "interactions": self.interactions,
            "data_display": self.data_display,
            "layout_hints": self.layout_hints,
            "style_hints": self.style_hints,
            "accessibility_requirements": self.accessibility_requirements,
            "estimated_complexity": self.estimated_complexity,
        }


class RequirementsExtractor:
    """Extracts UI requirements from user prompts."""

    # UI element patterns
    COMPONENT_PATTERNS = {
        "dashboard": ["dashboard", "admin panel", "control panel"],
        "form": ["form", "input", "submit", "registration", "login", "signup"],
        "table": ["table", "data grid", "list view", "spreadsheet"],
        "card": ["card", "tile", "panel", "box"],
        "modal": ["modal", "dialog", "popup", "overlay"],
        "navigation": ["navbar", "sidebar", "menu", "navigation", "breadcrumb"],
        "chart": ["chart", "graph", "visualization", "analytics"],
        "profile": ["profile", "user card", "avatar", "account"],
        "settings": ["settings", "preferences", "configuration"],
        "landing": ["landing page", "hero", "homepage"],
    }

    UI_ELEMENT_PATTERNS = {
        "button": ["button", "btn", "click", "action"],
        "input": ["input", "text field", "textarea", "field"],
        "select": ["select", "dropdown", "combobox", "picker"],
        "checkbox": ["checkbox", "toggle", "switch"],
        "badge": ["badge", "tag", "label", "chip"],
        "avatar": ["avatar", "profile picture", "user icon"],
        "icon": ["icon", "symbol"],
        "image": ["image", "photo", "picture", "thumbnail"],
        "progress": ["progress", "loading", "spinner"],
        "tooltip": ["tooltip", "hint", "help text"],
    }

    INTERACTION_PATTERNS = {
        "click": ["click", "tap", "press"],
        "hover": ["hover", "mouse over"],
        "drag": ["drag", "drop", "sortable", "reorder"],
        "scroll": ["scroll", "infinite scroll", "pagination"],
        "filter": ["filter", "search", "sort"],
        "expand": ["expand", "collapse", "accordion", "toggle"],
        "edit": ["edit", "inline edit", "modify"],
        "delete": ["delete", "remove", "clear"],
    }

    LAYOUT_PATTERNS = {
        "grid": ["grid", "columns", "rows"],
        "flex": ["flex", "horizontal", "vertical"],
        "sidebar": ["sidebar layout", "two column", "split"],
        "centered": ["centered", "middle", "center"],
        "full_width": ["full width", "edge to edge", "full screen"],
        "responsive": ["responsive", "mobile", "tablet", "desktop"],
    }

    STYLE_PATTERNS = {
        "modern": ["modern", "sleek", "contemporary"],
        "minimal": ["minimal", "clean", "simple"],
        "colorful": ["colorful", "vibrant", "bright"],
        "dark": ["dark", "dark mode", "night mode"],
        "professional": ["professional", "business", "corporate"],
        "playful": ["playful", "fun", "friendly"],
    }

    def extract(self, prompt: str) -> ExtractedRequirements:
        """Extract requirements from user prompt."""
        prompt_lower = prompt.lower()
        requirements = ExtractedRequirements()

        # Extract component types
        for comp_type, patterns in self.COMPONENT_PATTERNS.items():
            if any(p in prompt_lower for p in patterns):
                requirements.component_types.append(comp_type)

        # Extract UI elements
        for element, patterns in self.UI_ELEMENT_PATTERNS.items():
            if any(p in prompt_lower for p in patterns):
                requirements.ui_elements.append(element)

        # Extract interactions
        for interaction, patterns in self.INTERACTION_PATTERNS.items():
            if any(p in prompt_lower for p in patterns):
                requirements.interactions.append(interaction)

        # Extract layout hints
        for layout, patterns in self.LAYOUT_PATTERNS.items():
            if any(p in prompt_lower for p in patterns):
                requirements.layout_hints.append(layout)

        # Extract style hints
        for style, patterns in self.STYLE_PATTERNS.items():
            if any(p in prompt_lower for p in patterns):
                requirements.style_hints.append(style)

        # Extract data display requirements
        if any(word in prompt_lower for word in ["data", "list", "display", "show", "view"]):
            requirements.data_display.append("data_display")
        if any(word in prompt_lower for word in ["chart", "graph", "stats", "analytics"]):
            requirements.data_display.append("charts")
        if any(word in prompt_lower for word in ["table", "grid", "rows"]):
            requirements.data_display.append("tabular")

        # Estimate complexity
        total_features = (
            len(requirements.component_types) +
            len(requirements.ui_elements) +
            len(requirements.interactions)
        )
        if total_features <= 3:
            requirements.estimated_complexity = "simple"
        elif total_features <= 7:
            requirements.estimated_complexity = "medium"
        else:
            requirements.estimated_complexity = "complex"

        return requirements


# =============================================================================
# PROMPT OPTIMIZER CLASS
# =============================================================================

class PromptOptimizer:
    """
    Optimizes user prompts for UI generation.

    Applies Claude best practices:
    - XML tag structuring
    - Chain-of-thought instructions
    - Context injection
    - Framework-specific guidelines
    """

    def __init__(self):
        self.extractor = RequirementsExtractor()
        logger.info("[PROMPT_OPTIMIZER] Initialized")

    def optimize(
        self,
        user_prompt: str,
        tech_stack: FrontendTechStack,
        design_preferences: Optional[Dict[str, Any]] = None,
    ) -> OptimizedPrompt:
        """
        Optimize a user prompt for UI generation.

        Args:
            user_prompt: Original user request
            tech_stack: Detected frontend technology stack
            design_preferences: Optional user design preferences

        Returns:
            OptimizedPrompt with system and user prompts
        """
        logger.info(f"[PROMPT_OPTIMIZER] Optimizing prompt for {tech_stack.primary_framework}")

        # Extract requirements from prompt
        requirements = self.extractor.extract(user_prompt)

        # Build tech stack context
        tech_stack_context = self._build_tech_stack_context(tech_stack)

        # Build design system context
        design_system_context = self._build_design_system_context(
            tech_stack.design_tokens,
            design_preferences,
        )

        # Get framework-specific guidelines
        framework_guidelines = self._get_framework_guidelines(tech_stack.primary_framework)

        # Build system prompt
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tech_stack_context=tech_stack_context,
            design_system_context=design_system_context,
            framework_guidelines=framework_guidelines,
        )

        # Build existing components context
        existing_components_str = self._format_existing_components(
            tech_stack.existing_components
        )

        # Determine constraints based on complexity
        max_files = 5 if requirements.estimated_complexity == "simple" else 10
        max_lines = 100 if requirements.estimated_complexity == "simple" else 150

        additional_constraints = self._build_additional_constraints(
            requirements, design_preferences
        )

        # Build optimized user prompt
        optimized_user_prompt = USER_PROMPT_TEMPLATE.format(
            user_request=user_prompt,
            extracted_requirements=requirements.to_string(),
            max_files=max_files,
            max_lines=max_lines,
            additional_constraints=additional_constraints,
            existing_components=existing_components_str,
        )

        # Calculate token estimate
        context_tokens = self._estimate_tokens(system_prompt + optimized_user_prompt)

        # Track enhancements applied
        enhancements = [
            "xml_structuring",
            "chain_of_thought",
            "framework_guidelines",
            "design_system_context",
        ]
        if tech_stack.existing_components:
            enhancements.append("existing_components_context")
        if requirements.component_types:
            enhancements.append("requirements_extraction")

        logger.info(
            f"[PROMPT_OPTIMIZER] Optimized: {len(enhancements)} enhancements, "
            f"~{context_tokens} tokens"
        )

        return OptimizedPrompt(
            original_prompt=user_prompt,
            optimized_prompt=optimized_user_prompt,
            system_prompt=system_prompt,
            enhancements_applied=enhancements,
            context_tokens_estimate=context_tokens,
            detected_requirements=requirements.to_dict(),
        )

    def _build_tech_stack_context(self, tech_stack: FrontendTechStack) -> str:
        """Build technology stack context string."""
        parts = [
            f"- Framework: {tech_stack.primary_framework.value}",
            f"- CSS: {tech_stack.css_framework.value}",
            f"- TypeScript: {'Yes' if tech_stack.typescript else 'No'}",
        ]

        if tech_stack.ui_libraries:
            libs = ", ".join(lib.value for lib in tech_stack.ui_libraries)
            parts.append(f"- UI Libraries: {libs}")

        if tech_stack.component_path:
            parts.append(f"- Components directory: {tech_stack.component_path}")

        if tech_stack.dark_mode_supported:
            parts.append("- Dark mode: Supported")

        return "\n".join(parts)

    def _build_design_system_context(
        self,
        tokens: DesignTokens,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build design system context string."""
        parts = []

        # Colors
        if tokens.colors:
            color_lines = [f"  - {name}: {value}" for name, value in tokens.colors.items()]
            parts.append("Colors:\n" + "\n".join(color_lines[:10]))

        # Typography
        if tokens.typography:
            parts.append(f"Typography: {tokens.typography}")

        # Spacing
        if tokens.spacing:
            spacing_str = ", ".join(f"{k}={v}" for k, v in list(tokens.spacing.items())[:5])
            parts.append(f"Spacing scale: {spacing_str}")

        # User preferences
        if preferences:
            pref_str = ", ".join(f"{k}={v}" for k, v in preferences.items())
            parts.append(f"User preferences: {pref_str}")

        return "\n".join(parts) if parts else "Use Tailwind CSS defaults"

    def _get_framework_guidelines(self, framework: FrontendFramework) -> str:
        """Get framework-specific guidelines."""
        guidelines_map = {
            FrontendFramework.REACT: REACT_GUIDELINES,
            FrontendFramework.VUE: VUE_GUIDELINES,
            FrontendFramework.BLADE: BLADE_GUIDELINES,
            FrontendFramework.LIVEWIRE: LIVEWIRE_GUIDELINES,
        }
        return guidelines_map.get(framework, REACT_GUIDELINES)

    def _format_existing_components(
        self,
        components: List[ExistingComponent],
    ) -> str:
        """Format existing components for prompt."""
        if not components:
            return "No existing custom components detected. Use shadcn/ui or create new components."

        lines = ["Available components to use:"]
        for comp in components[:20]:  # Limit to 20 components
            props_str = f"({', '.join(comp.props[:5])})" if comp.props else ""
            lines.append(f"- {comp.name}{props_str}: {comp.path}")

        return "\n".join(lines)

    def _build_additional_constraints(
        self,
        requirements: ExtractedRequirements,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build additional constraints based on requirements."""
        constraints = []

        if "chart" in requirements.component_types or "charts" in requirements.data_display:
            constraints.append("- For charts, use recharts or similar if available")

        if "table" in requirements.component_types or "tabular" in requirements.data_display:
            constraints.append("- For tables, include sorting and filtering if appropriate")

        if "form" in requirements.component_types:
            constraints.append("- Include form validation and error states")

        if "modal" in requirements.component_types:
            constraints.append("- Modals should trap focus and be keyboard accessible")

        if "dark" in requirements.style_hints:
            constraints.append("- Ensure all colors work in dark mode")

        if preferences and preferences.get("animations"):
            constraints.append("- Include subtle animations with Framer Motion")

        return "\n".join(constraints) if constraints else ""

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count (4 chars per token)."""
        return len(text) // 4


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_prompt_optimizer: Optional[PromptOptimizer] = None


def get_prompt_optimizer() -> PromptOptimizer:
    """Get or create the prompt optimizer singleton."""
    global _prompt_optimizer
    if _prompt_optimizer is None:
        _prompt_optimizer = PromptOptimizer()
    return _prompt_optimizer
