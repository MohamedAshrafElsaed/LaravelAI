"""
Test scenarios for multi-agent pipeline testing.

Defines comprehensive test scenarios including user input,
expected agent flow, and mock responses for each agent.
"""

from typing import Any, Dict, List, Optional


# =============================================================================
# SUBSCRIPTION MANAGEMENT SCENARIO (Complex Feature)
# =============================================================================

SUBSCRIPTION_SCENARIO = {
    "name": "subscription_management",
    "description": "Full subscription management feature with Stripe integration",

    "user_input": """I need to implement a complete Subscription Management feature:

Backend:
- Migration for subscriptions table (user_id, plan_id, status, starts_at, ends_at, stripe_subscription_id)
- Migration for plans table (name, slug, price, interval, features JSON, is_active)
- Subscription and Plan models with relationships
- SubscriptionController with CRUD operations
- SubscriptionService for business logic
- Form Requests for validation
- API Resources for response formatting
- Stripe webhook handler
- Feature flags middleware

Frontend (React + TypeScript):
- Pricing page component
- Subscription dashboard
- Upgrade/downgrade modal
- Billing history component
- Usage meter component""",

    "project_context": {
        "name": "saas-app",
        "stack": "Laravel + React + TypeScript",
        "existing_models": ["User", "Team", "Project"],
        "has_stripe": False,
        "has_subscriptions": False,
    },

    "expected_flow": {
        "nova": {
            "task_type": "feature",
            "requires_migration": True,
            "requires_frontend": True,
            "min_domains": 4,
            "expected_domains": ["database", "models", "controllers", "services", "api", "frontend"],
        },
        "scout": {
            "min_chunks": 3,
            "expected_files": ["User.php", "routes/api.php"],
        },
        "blueprint": {
            "min_steps": 10,
            "expected_step_types": ["migration", "model", "controller", "service", "frontend"],
        },
        "forge": {
            "min_files": 8,
            "expected_files": [
                "database/migrations/*_create_plans_table.php",
                "database/migrations/*_create_subscriptions_table.php",
                "app/Models/Plan.php",
                "app/Models/Subscription.php",
                "app/Http/Controllers/SubscriptionController.php",
            ],
        },
        "guardian": {
            "min_score": 70,
            "critical_checks": ["migration_syntax", "model_relationships", "controller_methods"],
        },
    },

    "mock_responses": {
        "nova": {
            "intent": """{
                "task_type": "feature",
                "task_type_confidence": 0.92,
                "domains_affected": ["database", "models", "controllers", "services", "api", "routing"],
                "scope": "cross_domain",
                "languages": ["php", "blade"],
                "requires_migration": true,
                "priority": "medium",
                "entities": {
                    "files": [],
                    "classes": ["Subscription", "Plan", "SubscriptionController", "SubscriptionService"],
                    "methods": ["index", "store", "update", "cancel"],
                    "routes": ["/api/subscriptions", "/api/plans"],
                    "tables": ["subscriptions", "plans"]
                },
                "search_queries": ["User model relationships", "existing payment", "Stripe integration", "subscription patterns", "Laravel billing"],
                "reasoning": "Complex feature requiring migrations for plans and subscriptions tables, models with relationships to User, service layer for Stripe integration, and CRUD controller.",
                "overall_confidence": 0.88,
                "needs_clarification": false,
                "clarifying_questions": []
            }""",
        },
        "scout": {
            "context": """Found relevant code:

1. app/Models/User.php (lines 15-45):
   - User model with existing relationships
   - Has team() and projects() relationships
   - Uses HasFactory trait

2. routes/api.php (lines 1-50):
   - Existing API routes structure
   - Auth middleware groups
   - Resource route patterns

3. app/Http/Controllers/Controller.php:
   - Base controller class
   - Common response methods""",
        },
        "blueprint": {
            "plan": """{
                "summary": "Implement subscription management with migrations, models, service layer, and API endpoints",
                "reasoning": {
                    "understanding": "User needs a complete subscription management feature with Stripe integration for a SaaS application.",
                    "approach": "Start with database migrations, then models with relationships, followed by service layer for Stripe logic, and finally controllers with routes.",
                    "dependency_analysis": "Migrations must come first, models depend on migrations, service depends on models, controllers depend on service.",
                    "risks_considered": "Stripe integration complexity, proper relationship setup between User, Plan, and Subscription models."
                },
                "steps": [
                    {
                        "order": 1,
                        "action": "create",
                        "file": "database/migrations/2024_01_01_000001_create_plans_table.php",
                        "category": "migration",
                        "description": "Create plans table with columns: id, name, slug, price (decimal), interval (monthly/yearly), features (JSON), stripe_price_id, is_active, timestamps",
                        "depends_on": [],
                        "estimated_lines": 30
                    },
                    {
                        "order": 2,
                        "action": "create",
                        "file": "database/migrations/2024_01_01_000002_create_subscriptions_table.php",
                        "category": "migration",
                        "description": "Create subscriptions table with columns: id, user_id (foreign), plan_id (foreign), status, stripe_subscription_id, starts_at, ends_at, trial_ends_at, timestamps",
                        "depends_on": [1],
                        "estimated_lines": 35
                    },
                    {
                        "order": 3,
                        "action": "create",
                        "file": "app/Models/Plan.php",
                        "category": "model",
                        "description": "Create Plan model with fillable fields, casts for features JSON, subscriptions() hasMany relationship, isActive() scope",
                        "depends_on": [1],
                        "estimated_lines": 45
                    },
                    {
                        "order": 4,
                        "action": "create",
                        "file": "app/Models/Subscription.php",
                        "category": "model",
                        "description": "Create Subscription model with fillable fields, date casts, user() belongsTo, plan() belongsTo, isActive() method, cancel() method",
                        "depends_on": [2, 3],
                        "estimated_lines": 60
                    },
                    {
                        "order": 5,
                        "action": "create",
                        "file": "app/Services/SubscriptionService.php",
                        "category": "service",
                        "description": "Create SubscriptionService with subscribe(), cancel(), changePlan(), syncFromStripe() methods. Handle Stripe API calls and local database sync.",
                        "depends_on": [3, 4],
                        "estimated_lines": 150
                    },
                    {
                        "order": 6,
                        "action": "create",
                        "file": "app/Http/Requests/SubscriptionRequest.php",
                        "category": "request",
                        "description": "Create form request with validation rules for plan_id, payment_method_id",
                        "depends_on": [],
                        "estimated_lines": 25
                    },
                    {
                        "order": 7,
                        "action": "create",
                        "file": "app/Http/Resources/SubscriptionResource.php",
                        "category": "resource",
                        "description": "Create API resource for subscription with plan relationship, formatted dates, status",
                        "depends_on": [4],
                        "estimated_lines": 30
                    },
                    {
                        "order": 8,
                        "action": "create",
                        "file": "app/Http/Controllers/SubscriptionController.php",
                        "category": "controller",
                        "description": "Create controller with index(), store(), show(), update(), destroy() methods using SubscriptionService",
                        "depends_on": [5, 6, 7],
                        "estimated_lines": 80
                    },
                    {
                        "order": 9,
                        "action": "create",
                        "file": "app/Http/Controllers/WebhookController.php",
                        "category": "controller",
                        "description": "Create Stripe webhook handler for subscription.created, subscription.updated, subscription.deleted events",
                        "depends_on": [5],
                        "estimated_lines": 100
                    },
                    {
                        "order": 10,
                        "action": "modify",
                        "file": "routes/api.php",
                        "category": "route",
                        "description": "Add subscription routes: apiResource for subscriptions, POST /webhooks/stripe for webhook handler",
                        "depends_on": [8, 9],
                        "estimated_lines": 10
                    }
                ],
                "overall_confidence": 0.88,
                "risk_level": "medium",
                "estimated_complexity": 6,
                "needs_clarification": false,
                "clarifying_questions": [],
                "warnings": ["Stripe API keys must be configured in .env", "Webhook endpoint must be registered with Stripe"]
            }""",
        },
        "forge": {
            "execution": """Generated files:

1. database/migrations/2024_01_01_000001_create_plans_table.php
2. database/migrations/2024_01_01_000002_create_subscriptions_table.php
3. app/Models/Plan.php
4. app/Models/Subscription.php
5. app/Services/SubscriptionService.php
6. app/Http/Controllers/SubscriptionController.php
7. app/Http/Requests/SubscriptionRequest.php
8. app/Http/Resources/SubscriptionResource.php
9. app/Http/Controllers/WebhookController.php

All files generated successfully with proper Laravel conventions.""",
        },
        "guardian": {
            "validation": """{
                "score": 85,
                "passed": true,
                "issues": [
                    {
                        "severity": "warning",
                        "file": "app/Http/Controllers/SubscriptionController.php",
                        "line": 45,
                        "message": "Consider adding rate limiting for subscription endpoints",
                        "suggestion": "Add throttle middleware to sensitive endpoints"
                    }
                ],
                "checks_passed": [
                    "migration_syntax",
                    "model_relationships",
                    "controller_methods",
                    "service_injection",
                    "route_definitions"
                ]
            }""",
        },
    },
}


# =============================================================================
# SIMPLE CRUD SCENARIO (Basic Feature)
# =============================================================================

SIMPLE_CRUD_SCENARIO = {
    "name": "simple_crud",
    "description": "Basic CRUD operations for a Tag model",

    "user_input": """Create a Tag model with CRUD operations:
- Migration for tags table (name, slug, color)
- Tag model
- TagController with index, store, update, delete
- API routes""",

    "project_context": {
        "name": "blog-app",
        "stack": "Laravel",
        "existing_models": ["Post", "User"],
    },

    "expected_flow": {
        "nova": {
            "task_type": "feature",
            "requires_migration": True,
            "min_domains": 3,
        },
        "scout": {
            "min_chunks": 2,
        },
        "blueprint": {
            "min_steps": 4,
        },
        "forge": {
            "min_files": 4,
        },
        "guardian": {
            "min_score": 80,
        },
    },

    "mock_responses": {
        "nova": {
            "intent": """{
                "task_type": "feature",
                "task_type_confidence": 0.95,
                "domains_affected": ["database", "models", "controllers", "routing"],
                "scope": "feature",
                "languages": ["php"],
                "requires_migration": true,
                "priority": "medium",
                "entities": {
                    "files": [],
                    "classes": ["Tag", "TagController"],
                    "methods": ["index", "store", "update", "delete"],
                    "routes": ["/api/tags"],
                    "tables": ["tags"]
                },
                "search_queries": ["Tag model", "existing models", "api routes", "CRUD controller"],
                "reasoning": "Simple CRUD feature requiring migration for tags table, Tag model, and TagController with standard REST operations.",
                "overall_confidence": 0.92,
                "needs_clarification": false,
                "clarifying_questions": []
            }""",
        },
        "scout": {
            "context": """Found:
1. app/Models/Post.php - Post model
2. routes/api.php - API routes""",
        },
        "blueprint": {
            "plan": """{
                "summary": "Create Tag model with CRUD operations and API routes",
                "reasoning": {
                    "understanding": "User needs a Tag model with standard CRUD operations for a blog application.",
                    "approach": "Create migration, model, controller, and add routes following Laravel conventions.",
                    "dependency_analysis": "Migration first, then model, then controller, finally routes.",
                    "risks_considered": "Simple feature with low risk. Standard Laravel patterns."
                },
                "steps": [
                    {"order": 1, "action": "create", "file": "database/migrations/create_tags_table.php", "category": "migration", "description": "Create tags table with name, slug, color columns", "depends_on": [], "estimated_lines": 25},
                    {"order": 2, "action": "create", "file": "app/Models/Tag.php", "category": "model", "description": "Create Tag model with fillable fields and posts relationship", "depends_on": [1], "estimated_lines": 30},
                    {"order": 3, "action": "create", "file": "app/Http/Controllers/TagController.php", "category": "controller", "description": "Create TagController with index, store, update, destroy methods", "depends_on": [2], "estimated_lines": 60},
                    {"order": 4, "action": "modify", "file": "routes/api.php", "category": "route", "description": "Add apiResource route for tags", "depends_on": [3], "estimated_lines": 5}
                ],
                "overall_confidence": 0.92,
                "risk_level": "low",
                "estimated_complexity": 2,
                "needs_clarification": false,
                "clarifying_questions": [],
                "warnings": []
            }""",
        },
        "forge": {
            "execution": "Generated 4 files successfully.",
        },
        "guardian": {
            "validation": """{
                "score": 90,
                "passed": true,
                "issues": []
            }""",
        },
    },
}


# =============================================================================
# BUG FIX SCENARIO
# =============================================================================

BUG_FIX_SCENARIO = {
    "name": "bug_fix",
    "description": "Fix authentication bug in login flow",

    "user_input": """Fix the login bug: Users are getting logged out immediately after login.
The issue seems to be in the token refresh logic in AuthController.""",

    "project_context": {
        "name": "api-app",
        "stack": "Laravel",
        "error_message": "Token expired immediately after creation",
    },

    "expected_flow": {
        "nova": {
            "task_type": "bugfix",
            "requires_migration": False,
        },
        "scout": {
            "min_chunks": 2,
            "expected_files": ["AuthController.php"],
        },
        "blueprint": {
            "min_steps": 2,
        },
        "forge": {
            "min_files": 1,
        },
        "guardian": {
            "min_score": 85,
        },
    },

    "mock_responses": {
        "nova": {
            "intent": """{
                "task_type": "bugfix",
                "task_type_confidence": 0.88,
                "domains_affected": ["auth", "controllers"],
                "scope": "single_file",
                "languages": ["php"],
                "requires_migration": false,
                "priority": "high",
                "entities": {
                    "files": ["app/Http/Controllers/AuthController.php"],
                    "classes": ["AuthController"],
                    "methods": ["login"],
                    "routes": ["/api/login"],
                    "tables": []
                },
                "search_queries": ["AuthController login", "token refresh", "JWT token expiry", "authentication"],
                "reasoning": "Bug in token expiration logic causing immediate logout. Need to fix token TTL setting in AuthController login method.",
                "overall_confidence": 0.85,
                "needs_clarification": false,
                "clarifying_questions": []
            }""",
        },
        "scout": {
            "context": """Found relevant code:
1. app/Http/Controllers/AuthController.php (lines 45-80):
   - login() method creates token
   - Issue: token expiry set to 0 instead of config value

2. config/jwt.php:
   - JWT_TTL should be 60 minutes""",
        },
        "blueprint": {
            "plan": """{
                "summary": "Fix token expiration bug in AuthController and add regression test",
                "reasoning": {
                    "understanding": "Token expiry is incorrectly set causing immediate logout after login.",
                    "approach": "Fix the token TTL in AuthController login method to use config value, add test to prevent regression.",
                    "dependency_analysis": "Fix must be applied first, then test added to verify.",
                    "risks_considered": "Need to ensure fix doesn't break other token operations."
                },
                "steps": [
                    {"order": 1, "action": "modify", "file": "app/Http/Controllers/AuthController.php", "category": "controller", "description": "Fix token expiry time to use config JWT_TTL value instead of hardcoded 0", "depends_on": [], "estimated_lines": 10},
                    {"order": 2, "action": "create", "file": "tests/Feature/AuthTest.php", "category": "test", "description": "Add regression test to verify token is valid after login and doesn't expire immediately", "depends_on": [1], "estimated_lines": 40}
                ],
                "overall_confidence": 0.90,
                "risk_level": "low",
                "estimated_complexity": 2,
                "needs_clarification": false,
                "clarifying_questions": [],
                "warnings": []
            }""",
        },
        "forge": {
            "execution": "Fixed AuthController.php, added test.",
        },
        "guardian": {
            "validation": """{
                "score": 92,
                "passed": true,
                "issues": []
            }""",
        },
    },
}


# =============================================================================
# REFACTOR SCENARIO
# =============================================================================

REFACTOR_SCENARIO = {
    "name": "refactor",
    "description": "Refactor OrderController to use service pattern",

    "user_input": """Refactor the OrderController:
- Extract business logic to OrderService
- Keep controller thin with just request handling
- Maintain all existing functionality""",

    "project_context": {
        "name": "ecommerce-app",
        "stack": "Laravel",
        "existing_files": ["OrderController.php"],
    },

    "expected_flow": {
        "nova": {
            "task_type": "refactor",
            "requires_migration": False,
        },
        "scout": {
            "min_chunks": 1,
        },
        "blueprint": {
            "min_steps": 3,
        },
        "forge": {
            "min_files": 2,
        },
        "guardian": {
            "min_score": 80,
        },
    },

    "mock_responses": {
        "nova": {
            "intent": """{
                "task_type": "refactor",
                "task_type_confidence": 0.90,
                "domains_affected": ["controllers", "services"],
                "scope": "feature",
                "languages": ["php"],
                "requires_migration": false,
                "priority": "medium",
                "entities": {
                    "files": ["app/Http/Controllers/OrderController.php"],
                    "classes": ["OrderController", "OrderService"],
                    "methods": [],
                    "routes": [],
                    "tables": []
                },
                "search_queries": ["OrderController", "order business logic", "service pattern", "existing services"],
                "reasoning": "Refactor to extract business logic from OrderController to OrderService following service layer pattern. Controller should only handle HTTP concerns.",
                "overall_confidence": 0.87,
                "needs_clarification": false,
                "clarifying_questions": []
            }""",
        },
        "scout": {
            "context": """Found:
1. app/Http/Controllers/OrderController.php - 500 lines with mixed concerns""",
        },
        "blueprint": {
            "plan": """{
                "summary": "Extract business logic from OrderController to OrderService following service pattern",
                "reasoning": {
                    "understanding": "OrderController has too much business logic and needs to be refactored to follow service pattern.",
                    "approach": "Create OrderService to hold business logic, refactor controller to use service, add unit tests.",
                    "dependency_analysis": "Service must be created first, then controller refactored to use it, finally tests added.",
                    "risks_considered": "Must maintain all existing functionality while extracting logic. Need comprehensive tests."
                },
                "steps": [
                    {"order": 1, "action": "create", "file": "app/Services/OrderService.php", "category": "service", "description": "Create OrderService with methods extracted from OrderController: createOrder, processPayment, updateStatus, calculateTotal", "depends_on": [], "estimated_lines": 150},
                    {"order": 2, "action": "modify", "file": "app/Http/Controllers/OrderController.php", "category": "controller", "description": "Refactor to inject and use OrderService, keep only HTTP request/response handling", "depends_on": [1], "estimated_lines": 80},
                    {"order": 3, "action": "create", "file": "tests/Unit/OrderServiceTest.php", "category": "test", "description": "Add unit tests for OrderService methods to ensure business logic works correctly", "depends_on": [1], "estimated_lines": 100}
                ],
                "overall_confidence": 0.85,
                "risk_level": "medium",
                "estimated_complexity": 5,
                "needs_clarification": false,
                "clarifying_questions": [],
                "warnings": ["Ensure all existing tests still pass after refactor"]
            }""",
        },
        "forge": {
            "execution": "Created OrderService, refactored OrderController.",
        },
        "guardian": {
            "validation": """{
                "score": 88,
                "passed": true,
                "issues": [
                    {"severity": "info", "message": "Consider adding interface for service"}
                ]
            }""",
        },
    },
}


# =============================================================================
# SCENARIO REGISTRY
# =============================================================================

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "subscription_management": SUBSCRIPTION_SCENARIO,
    "simple_crud": SIMPLE_CRUD_SCENARIO,
    "bug_fix": BUG_FIX_SCENARIO,
    "refactor": REFACTOR_SCENARIO,
}


def get_scenario(name: str) -> Dict[str, Any]:
    """
    Get a test scenario by name.

    Args:
        name: Scenario name

    Returns:
        Scenario dictionary

    Raises:
        KeyError: If scenario not found
    """
    if name not in SCENARIOS:
        raise KeyError(f"Scenario '{name}' not found. Available: {list(SCENARIOS.keys())}")
    return SCENARIOS[name]


def get_all_scenarios() -> Dict[str, Dict[str, Any]]:
    """Get all available scenarios."""
    return SCENARIOS


def get_scenario_names() -> List[str]:
    """Get list of all scenario names."""
    return list(SCENARIOS.keys())


def get_mock_response(scenario_name: str, agent: str) -> Optional[Dict[str, str]]:
    """
    Get mock response for a specific agent in a scenario.

    Args:
        scenario_name: Name of the scenario
        agent: Agent name (nova, scout, blueprint, forge, guardian)

    Returns:
        Mock response dictionary or None
    """
    scenario = get_scenario(scenario_name)
    return scenario.get("mock_responses", {}).get(agent.lower())
