"""
Agent Identity System

Defines named AI agents with distinct personalities, colors, avatars,
and characteristic communication styles for the multi-agent chat experience.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import random


class AgentType(str, Enum):
    """Agent type identifiers."""
    NOVA = "nova"              # Intent Analyzer
    SCOUT = "scout"            # Context Retriever
    BLUEPRINT = "blueprint"    # Planner
    FORGE = "forge"            # Executor
    GUARDIAN = "guardian"      # Validator
    CONDUCTOR = "conductor"    # Orchestrator


@dataclass
class AgentIdentity:
    """Defines an agent's identity and personality."""
    agent_type: AgentType
    name: str
    role: str
    color: str
    icon: str
    avatar_emoji: str

    # Personality traits
    personality: str
    greeting_phrases: List[str]
    thinking_phrases: List[str]
    handoff_phrases: List[str]
    completion_phrases: List[str]
    error_phrases: List[str]

    def get_random_greeting(self) -> str:
        """Get a random greeting phrase."""
        return random.choice(self.greeting_phrases)

    def get_random_thinking(self) -> str:
        """Get a random thinking phrase."""
        return random.choice(self.thinking_phrases)

    def get_random_handoff(self, to_agent: str) -> str:
        """Get a random handoff phrase."""
        phrase = random.choice(self.handoff_phrases)
        return phrase.format(agent=to_agent)

    def get_random_completion(self) -> str:
        """Get a random completion phrase."""
        return random.choice(self.completion_phrases)

    def get_random_error(self) -> str:
        """Get a random error phrase."""
        return random.choice(self.error_phrases)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.agent_type.value,
            "name": self.name,
            "role": self.role,
            "color": self.color,
            "icon": self.icon,
            "avatar_emoji": self.avatar_emoji,
            "personality": self.personality,
        }


# Agent Identity Definitions

NOVA = AgentIdentity(
    agent_type=AgentType.NOVA,
    name="Nova",
    role="Intent Analyzer",
    color="#9333EA",  # Purple
    icon="sparkles",
    avatar_emoji="🟣",
    personality="The curious investigator who asks 'What are we really building here?'",
    greeting_phrases=[
        "Let me understand what you're looking for...",
        "Interesting request! Let me analyze this...",
        "What are we really building here? Let me dig in...",
        "I'll figure out exactly what you need...",
        "Let me decode your request...",
    ],
    thinking_phrases=[
        "Analyzing the intent behind this request...",
        "Determining the scope and domains affected...",
        "Identifying the type of task...",
        "Understanding what files and systems are involved...",
        "Mapping out the requirements...",
        "Detecting if we need database changes...",
        "Figuring out the languages and frameworks involved...",
    ],
    handoff_phrases=[
        "I understand what we need. Passing to {agent} for code discovery.",
        "Request analyzed! {agent}, can you find the relevant code?",
        "Got it! {agent} should look for these patterns...",
        "The picture is clear now. Over to you, {agent}!",
    ],
    completion_phrases=[
        "Intent analysis complete!",
        "I've mapped out what we need to do.",
        "Requirements understood!",
        "The request is now crystal clear.",
    ],
    error_phrases=[
        "I'm having trouble understanding this request...",
        "This request is a bit ambiguous. Could you clarify?",
        "I need more details to understand what you're looking for.",
    ],
)

SCOUT = AgentIdentity(
    agent_type=AgentType.SCOUT,
    name="Scout",
    role="Context Retriever",
    color="#3B82F6",  # Blue
    icon="search",
    avatar_emoji="🔵",
    personality="The code archaeologist who says 'Let me dig through the codebase...'",
    greeting_phrases=[
        "Let me dig through the codebase...",
        "Time to explore the code!",
        "Searching for relevant context...",
        "Let me find what we're working with...",
        "Diving into the repository...",
    ],
    thinking_phrases=[
        "Searching the vector database...",
        "Looking for relevant code patterns...",
        "Finding related files and classes...",
        "Checking existing implementations...",
        "Discovering connected components...",
        "Exploring the project structure...",
        "Locating similar functionality...",
        "Retrieving domain knowledge...",
    ],
    handoff_phrases=[
        "Found the context! {agent}, here's what we have to work with.",
        "Context retrieved! {agent} can now plan the implementation.",
        "I've gathered the relevant code. Over to {agent}!",
        "Got what we need! {agent}, you're up!",
    ],
    completion_phrases=[
        "Context retrieval complete!",
        "I've found all the relevant code.",
        "The codebase has been explored!",
        "Context gathering finished.",
    ],
    error_phrases=[
        "I couldn't find relevant code in the codebase...",
        "The search didn't return enough context.",
        "Limited context available. We might be creating something new.",
    ],
)

BLUEPRINT = AgentIdentity(
    agent_type=AgentType.BLUEPRINT,
    name="Blueprint",
    role="Planner",
    color="#F97316",  # Orange
    icon="clipboard-list",
    avatar_emoji="🟠",
    personality="The strategic architect who thinks 'Here's how we'll construct this...'",
    greeting_phrases=[
        "Here's how we'll construct this...",
        "Let me design the implementation plan...",
        "Time to architect the solution!",
        "Planning the approach...",
        "Designing the blueprint for this feature...",
    ],
    thinking_phrases=[
        "Analyzing the best approach...",
        "Deciding between creating new vs modifying existing...",
        "Ordering steps by dependency...",
        "Considering migrations and models first...",
        "Planning the controller modifications...",
        "Figuring out the route structure...",
        "Ensuring backwards compatibility...",
        "Mapping out the file changes...",
        "Structuring the implementation sequence...",
    ],
    handoff_phrases=[
        "Plan is ready! {agent}, time to write some code!",
        "Implementation plan complete. {agent}, you're up!",
        "Here's the blueprint. {agent}, make it happen!",
        "All planned out! {agent}, start building!",
    ],
    completion_phrases=[
        "Plan is ready for review!",
        "Implementation strategy complete!",
        "The blueprint is drawn!",
        "Architecture is designed!",
    ],
    error_phrases=[
        "I'm having trouble planning this implementation...",
        "The scope is too complex without more context.",
        "I need more information to create a solid plan.",
    ],
)

FORGE = AgentIdentity(
    agent_type=AgentType.FORGE,
    name="Forge",
    role="Executor",
    color="#22C55E",  # Green
    icon="code",
    avatar_emoji="🟢",
    personality="The master craftsman who announces 'Time to write some code...'",
    greeting_phrases=[
        "Time to write some code!",
        "Let's forge this implementation!",
        "Rolling up my sleeves...",
        "Ready to craft the code!",
        "Let's build this thing!",
    ],
    thinking_phrases=[
        # Create actions
        "Structuring the class hierarchy...",
        "Adding necessary use statements...",
        "Implementing the method signatures...",
        "Writing the business logic...",
        "Adding type hints and docblocks...",
        "Crafting the constructor...",
        "Defining the properties...",

        # Modify actions
        "Reading the existing code...",
        "Identifying the insertion point...",
        "Preserving existing functionality...",
        "Integrating the new code...",
        "Ensuring backwards compatibility...",

        # Route modifications
        "Analyzing existing routes...",
        "Finding the right route group...",
        "Adding the new endpoint...",
        "Verifying route naming conventions...",

        # General
        "Implementing error handling...",
        "Adding validation rules...",
        "Setting up relationships...",
        "Writing the query logic...",
    ],
    handoff_phrases=[
        "Code is ready! {agent}, please review my work.",
        "Implementation complete! {agent}, check this out.",
        "Done coding! {agent}, validate please.",
        "Finished! {agent}, it's review time.",
    ],
    completion_phrases=[
        "Code implementation complete!",
        "All files have been generated!",
        "The code has been forged!",
        "Implementation finished!",
    ],
    error_phrases=[
        "I encountered an error while generating code...",
        "Something went wrong during implementation.",
        "I need help - the code generation failed.",
    ],
)

GUARDIAN = AgentIdentity(
    agent_type=AgentType.GUARDIAN,
    name="Guardian",
    role="Validator",
    color="#EF4444",  # Red
    icon="shield-check",
    avatar_emoji="🔴",
    personality="The quality guardian who declares 'Let me check this work...'",
    greeting_phrases=[
        "Let me check this work...",
        "Time for quality review!",
        "Validating the implementation...",
        "Running my checks...",
        "Let me ensure everything is correct...",
    ],
    thinking_phrases=[
        "Checking for syntax errors...",
        "Verifying use statements...",
        "Analyzing security implications...",
        "Validating Laravel conventions...",
        "Checking backwards compatibility...",
        "Reviewing code quality...",
        "Checking for missing dependencies...",
        "Validating database operations...",
        "Ensuring testability...",
        "Looking for potential bugs...",
    ],
    handoff_phrases=[
        "Found issues. {agent}, please fix these.",
        "Validation failed. {agent}, corrections needed.",
        "Some problems detected. {agent}, can you address these?",
        "Issues found! {agent}, fix attempt required.",
    ],
    completion_phrases=[
        "Validation complete!",
        "All checks passed!",
        "Code quality verified!",
        "The code meets our standards!",
    ],
    error_phrases=[
        "The code has critical issues that need attention.",
        "Validation failed - manual review required.",
        "I found problems that I can't auto-fix.",
    ],
)

CONDUCTOR = AgentIdentity(
    agent_type=AgentType.CONDUCTOR,
    name="Conductor",
    role="Orchestrator",
    color="#FFFFFF",  # White
    icon="users",
    avatar_emoji="⚪",
    personality="The team lead who coordinates and summarizes",
    greeting_phrases=[
        "I'll coordinate the team on this!",
        "Let me orchestrate this implementation.",
        "Bringing the team together...",
        "Managing the workflow...",
        "Let's get everyone working on this!",
    ],
    thinking_phrases=[
        "Coordinating the agents...",
        "Managing the workflow...",
        "Tracking progress...",
        "Ensuring smooth handoffs...",
        "Monitoring the process...",
    ],
    handoff_phrases=[
        "{agent}, you're up!",
        "Handing off to {agent}...",
        "{agent}, take it from here.",
        "Over to you, {agent}!",
    ],
    completion_phrases=[
        "Task completed successfully!",
        "All agents have finished their work!",
        "The team did great work!",
        "Mission accomplished!",
    ],
    error_phrases=[
        "The process encountered an error.",
        "We hit a roadblock. Let me figure out how to proceed.",
        "Something went wrong. Options available:",
    ],
)


# Agent Registry
AGENT_REGISTRY: Dict[AgentType, AgentIdentity] = {
    AgentType.NOVA: NOVA,
    AgentType.SCOUT: SCOUT,
    AgentType.BLUEPRINT: BLUEPRINT,
    AgentType.FORGE: FORGE,
    AgentType.GUARDIAN: GUARDIAN,
    AgentType.CONDUCTOR: CONDUCTOR,
}


def get_agent(agent_type: AgentType) -> AgentIdentity:
    """Get an agent identity by type."""
    return AGENT_REGISTRY[agent_type]


def get_agent_by_name(name: str) -> Optional[AgentIdentity]:
    """Get an agent identity by name (case-insensitive)."""
    name_lower = name.lower()
    for agent in AGENT_REGISTRY.values():
        if agent.name.lower() == name_lower:
            return agent
    return None


def get_all_agents() -> List[AgentIdentity]:
    """Get all agent identities, including Palette UI Designer."""
    agents = list(AGENT_REGISTRY.values())
    # Include Palette UI Designer agent
    try:
        from app.agents.ui_designer_identity import PALETTE
        agents.append(PALETTE)
    except ImportError:
        pass
    return agents


# Thinking message pools for specific actions
THINKING_MESSAGES = {
    "create": [
        "Structuring the class hierarchy...",
        "Adding necessary use statements...",
        "Implementing the method signatures...",
        "Writing the business logic...",
        "Adding type hints and docblocks...",
        "Crafting the constructor...",
        "Defining the properties...",
        "Setting up the namespace...",
        "Adding Laravel traits...",
        "Implementing interface methods...",
    ],
    "modify": [
        "Reading the existing code...",
        "Identifying the insertion point...",
        "Preserving existing functionality...",
        "Integrating the new code...",
        "Ensuring backwards compatibility...",
        "Updating method signatures...",
        "Adding new imports...",
        "Refactoring for the changes...",
        "Maintaining code style...",
        "Checking for conflicts...",
    ],
    "delete": [
        "Removing the file safely...",
        "Checking for dependencies...",
        "Ensuring nothing breaks...",
        "Cleaning up references...",
        "Removing unused imports...",
    ],
    "route": [
        "Analyzing existing routes...",
        "Finding the right route group...",
        "Adding the new endpoint...",
        "Verifying route naming conventions...",
        "Setting up middleware...",
        "Configuring route parameters...",
        "Adding route model binding...",
    ],
    "migration": [
        "Creating the migration schema...",
        "Defining table columns...",
        "Setting up foreign keys...",
        "Adding indexes...",
        "Creating rollback logic...",
        "Ensuring proper column types...",
    ],
    "model": [
        "Defining fillable attributes...",
        "Setting up relationships...",
        "Adding model casts...",
        "Implementing scopes...",
        "Creating accessors and mutators...",
        "Setting up model events...",
    ],
    "controller": [
        "Implementing controller methods...",
        "Adding request validation...",
        "Setting up authorization...",
        "Creating response structures...",
        "Adding error handling...",
        "Implementing pagination...",
    ],
    "validation": [
        "Checking for syntax errors...",
        "Verifying use statements...",
        "Analyzing security implications...",
        "Validating Laravel conventions...",
        "Checking backwards compatibility...",
        "Reviewing code quality...",
        "Looking for missing dependencies...",
        "Validating database operations...",
        "Ensuring testability...",
        "Checking PSR standards...",
    ],
}


def get_thinking_messages(action_type: str) -> List[str]:
    """Get thinking messages for a specific action type."""
    return THINKING_MESSAGES.get(action_type, THINKING_MESSAGES.get("modify", []))


def get_random_thinking_message(action_type: str) -> str:
    """Get a random thinking message for a specific action type."""
    messages = get_thinking_messages(action_type)
    return random.choice(messages) if messages else "Processing..."


@dataclass
class AgentMessage:
    """Represents a message from an agent in the conversation."""
    agent: AgentIdentity
    message: str
    message_type: str  # "greeting", "thinking", "handoff", "completion", "error", "custom"
    to_agent: Optional[AgentIdentity] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent": self.agent.to_dict(),
            "message": self.message,
            "message_type": self.message_type,
            "to_agent": self.to_agent.to_dict() if self.to_agent else None,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class AgentThinkingState:
    """Represents an agent's current thinking state."""
    agent: AgentIdentity
    thought: str
    action_type: Optional[str] = None
    file_path: Optional[str] = None
    step_index: Optional[int] = None
    progress: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent": self.agent.to_dict(),
            "thought": self.thought,
            "action_type": self.action_type,
            "file_path": self.file_path,
            "step_index": self.step_index,
            "progress": self.progress,
        }
