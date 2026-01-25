"""
Forge Laravel Intelligence Module.

Specialized handlers and utilities for Laravel-specific code generation.
Provides deep Laravel knowledge for Models, Controllers, Migrations, Routes, etc.

This module enhances Forge's code generation with Laravel-specific patterns,
conventions, and best practices.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class LaravelFileType(str, Enum):
    """Types of Laravel files with specialized handling."""
    MODEL = "model"
    CONTROLLER = "controller"
    MIGRATION = "migration"
    ROUTE = "route"
    REQUEST = "request"
    RESOURCE = "resource"
    SERVICE = "service"
    REPOSITORY = "repository"
    POLICY = "policy"
    EVENT = "event"
    LISTENER = "listener"
    JOB = "job"
    MAIL = "mail"
    NOTIFICATION = "notification"
    MIDDLEWARE = "middleware"
    PROVIDER = "provider"
    COMMAND = "command"
    TEST = "test"
    FACTORY = "factory"
    SEEDER = "seeder"
    TRAIT = "trait"
    INTERFACE = "interface"
    UNKNOWN = "unknown"


# Laravel relationship methods
ELOQUENT_RELATIONSHIPS = {
    "hasOne": {"inverse": "belongsTo", "type": "one-to-one"},
    "hasMany": {"inverse": "belongsTo", "type": "one-to-many"},
    "belongsTo": {"inverse": "hasMany", "type": "many-to-one"},
    "belongsToMany": {"inverse": "belongsToMany", "type": "many-to-many"},
    "hasOneThrough": {"inverse": None, "type": "has-one-through"},
    "hasManyThrough": {"inverse": None, "type": "has-many-through"},
    "morphOne": {"inverse": "morphTo", "type": "polymorphic-one"},
    "morphMany": {"inverse": "morphTo", "type": "polymorphic-many"},
    "morphTo": {"inverse": "morphMany", "type": "polymorphic-inverse"},
    "morphToMany": {"inverse": "morphedByMany", "type": "polymorphic-many-to-many"},
    "morphedByMany": {"inverse": "morphToMany", "type": "polymorphic-inverse-many"},
}

# Common model traits
COMMON_MODEL_TRAITS = [
    "HasFactory",
    "SoftDeletes",
    "Notifiable",
    "HasApiTokens",
    "HasRoles",
    "Searchable",
    "Auditable",
]

# Laravel validation rules
VALIDATION_RULES = {
    "string": ["required", "string", "max:255"],
    "email": ["required", "string", "email", "max:255"],
    "password": ["required", "string", "min:8", "confirmed"],
    "integer": ["required", "integer"],
    "boolean": ["sometimes", "boolean"],
    "date": ["required", "date"],
    "file": ["required", "file", "max:10240"],
    "image": ["required", "image", "max:2048"],
    "array": ["sometimes", "array"],
    "uuid": ["required", "uuid"],
    "url": ["sometimes", "url"],
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LaravelFileInfo:
    """Information about a Laravel file."""
    file_type: LaravelFileType
    class_name: str
    namespace: str
    base_class: Optional[str] = None
    traits: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)

    # For models
    table_name: Optional[str] = None
    fillable: List[str] = field(default_factory=list)
    casts: Dict[str, str] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    # For controllers
    model_name: Optional[str] = None
    is_api: bool = False
    is_resource: bool = False

    # For migrations
    migration_action: Optional[str] = None  # create, add, modify, drop
    target_table: Optional[str] = None


@dataclass
class RelationshipInfo:
    """Information about an Eloquent relationship."""
    method_name: str
    relationship_type: str  # hasMany, belongsTo, etc.
    related_model: str
    foreign_key: Optional[str] = None
    local_key: Optional[str] = None
    pivot_table: Optional[str] = None

    def to_code(self) -> str:
        """Generate the relationship method code."""
        args = [f"{self.related_model}::class"]

        if self.foreign_key:
            args.append(f"'{self.foreign_key}'")
        if self.local_key:
            args.append(f"'{self.local_key}'")

        args_str = ", ".join(args)

        return f"""
    /**
     * Get the {self.method_name} relationship.
     *
     * @return \\Illuminate\\Database\\Eloquent\\Relations\\{self.relationship_type.replace('m', 'M').replace('o', 'O').replace('t', 'T')}
     */
    public function {self.method_name}(): {self.relationship_type.replace('m', 'M').replace('o', 'O').replace('t', 'T')}
    {{
        return $this->{self.relationship_type}({args_str});
    }}"""


@dataclass
class MigrationColumn:
    """Information about a migration column."""
    name: str
    type: str  # string, integer, boolean, etc.
    nullable: bool = False
    default: Optional[Any] = None
    unique: bool = False
    index: bool = False
    foreign_table: Optional[str] = None
    foreign_column: Optional[str] = None

    def to_code(self) -> str:
        """Generate the column definition code."""
        parts = [f"$table->{self.type}('{self.name}')"]

        if self.nullable:
            parts.append("->nullable()")
        if self.default is not None:
            if isinstance(self.default, str):
                parts.append(f"->default('{self.default}')")
            elif isinstance(self.default, bool):
                parts.append(f"->default({'true' if self.default else 'false'})")
            else:
                parts.append(f"->default({self.default})")
        if self.unique:
            parts.append("->unique()")
        if self.index:
            parts.append("->index()")

        return "".join(parts) + ";"


@dataclass
class RouteInfo:
    """Information about a Laravel route."""
    method: str  # GET, POST, PUT, DELETE, etc.
    uri: str
    action: str  # Controller@method or closure
    name: Optional[str] = None
    middleware: List[str] = field(default_factory=list)
    prefix: Optional[str] = None

    def to_code(self) -> str:
        """Generate the route definition code."""
        method_lower = self.method.lower()

        # Handle resource routes
        if method_lower == "resource":
            code = f"Route::resource('{self.uri}', {self.action})"
        elif method_lower == "apiresource":
            code = f"Route::apiResource('{self.uri}', {self.action})"
        else:
            code = f"Route::{method_lower}('{self.uri}', [{self.action}])"

        if self.name:
            code += f"->name('{self.name}')"
        if self.middleware:
            middleware_str = ", ".join(f"'{m}'" for m in self.middleware)
            code += f"->middleware([{middleware_str}])"

        return code + ";"


# =============================================================================
# FILE TYPE DETECTION
# =============================================================================

class LaravelFileDetector:
    """Detects Laravel file types from path and content."""

    # Path patterns for file type detection
    PATH_PATTERNS = {
        LaravelFileType.MODEL: [
            r"app/Models/\w+\.php$",
            r"app/\w+\.php$",  # Legacy location
        ],
        LaravelFileType.CONTROLLER: [
            r"app/Http/Controllers/.*Controller\.php$",
        ],
        LaravelFileType.MIGRATION: [
            r"database/migrations/\d{4}_\d{2}_\d{2}_\d{6}_\w+\.php$",
        ],
        LaravelFileType.ROUTE: [
            r"routes/(web|api|channels|console)\.php$",
        ],
        LaravelFileType.REQUEST: [
            r"app/Http/Requests/\w+Request\.php$",
        ],
        LaravelFileType.RESOURCE: [
            r"app/Http/Resources/\w+(Resource|Collection)\.php$",
        ],
        LaravelFileType.SERVICE: [
            r"app/Services/\w+Service\.php$",
        ],
        LaravelFileType.REPOSITORY: [
            r"app/Repositories/\w+Repository\.php$",
        ],
        LaravelFileType.POLICY: [
            r"app/Policies/\w+Policy\.php$",
        ],
        LaravelFileType.EVENT: [
            r"app/Events/\w+\.php$",
        ],
        LaravelFileType.LISTENER: [
            r"app/Listeners/\w+\.php$",
        ],
        LaravelFileType.JOB: [
            r"app/Jobs/\w+\.php$",
        ],
        LaravelFileType.MAIL: [
            r"app/Mail/\w+\.php$",
        ],
        LaravelFileType.NOTIFICATION: [
            r"app/Notifications/\w+\.php$",
        ],
        LaravelFileType.MIDDLEWARE: [
            r"app/Http/Middleware/\w+\.php$",
        ],
        LaravelFileType.PROVIDER: [
            r"app/Providers/\w+Provider\.php$",
        ],
        LaravelFileType.COMMAND: [
            r"app/Console/Commands/\w+\.php$",
        ],
        LaravelFileType.TEST: [
            r"tests/(Unit|Feature)/\w+Test\.php$",
        ],
        LaravelFileType.FACTORY: [
            r"database/factories/\w+Factory\.php$",
        ],
        LaravelFileType.SEEDER: [
            r"database/seeders/\w+Seeder\.php$",
        ],
        LaravelFileType.TRAIT: [
            r"app/Traits/\w+\.php$",
        ],
        LaravelFileType.INTERFACE: [
            r"app/(Contracts|Interfaces)/\w+\.php$",
        ],
    }

    @classmethod
    def detect_from_path(cls, file_path: str) -> LaravelFileType:
        """Detect file type from path."""
        # Normalize path
        file_path = file_path.replace("\\", "/")

        for file_type, patterns in cls.PATH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, file_path):
                    return file_type

        return LaravelFileType.UNKNOWN

    @classmethod
    def detect_from_content(cls, content: str, file_path: str = "") -> LaravelFileType:
        """Detect file type from content analysis."""
        # First try path detection
        if file_path:
            path_type = cls.detect_from_path(file_path)
            if path_type != LaravelFileType.UNKNOWN:
                return path_type

        # Content-based detection
        if "extends Model" in content or "use HasFactory" in content:
            return LaravelFileType.MODEL
        if "extends Controller" in content:
            return LaravelFileType.CONTROLLER
        if "extends Migration" in content or "Schema::create" in content:
            return LaravelFileType.MIGRATION
        if "Route::" in content and "<?php" in content:
            return LaravelFileType.ROUTE
        if "extends FormRequest" in content:
            return LaravelFileType.REQUEST
        if "extends JsonResource" in content:
            return LaravelFileType.RESOURCE
        if "class" in content and "Service" in content:
            return LaravelFileType.SERVICE

        return LaravelFileType.UNKNOWN


# =============================================================================
# LARAVEL CODE ANALYZERS
# =============================================================================

class ModelAnalyzer:
    """Analyzes Laravel Eloquent models."""

    @staticmethod
    def extract_fillable(content: str) -> List[str]:
        """Extract fillable fields from model."""
        match = re.search(
            r"protected\s+\$fillable\s*=\s*\[([\s\S]*?)\]",
            content
        )
        if match:
            fields_str = match.group(1)
            return re.findall(r"['\"](\w+)['\"]", fields_str)
        return []

    @staticmethod
    def extract_casts(content: str) -> Dict[str, str]:
        """Extract casts from model."""
        match = re.search(
            r"protected\s+\$casts\s*=\s*\[([\s\S]*?)\]",
            content
        )
        if match:
            casts_str = match.group(1)
            casts = {}
            for pair in re.findall(r"['\"](\w+)['\"]\s*=>\s*['\"](\w+)['\"]", casts_str):
                casts[pair[0]] = pair[1]
            return casts
        return {}

    @staticmethod
    def extract_relationships(content: str) -> List[Dict[str, Any]]:
        """Extract relationships from model."""
        relationships = []

        for rel_type in ELOQUENT_RELATIONSHIPS.keys():
            pattern = rf"public\s+function\s+(\w+)\([^)]*\)[^{{]*{{\s*return\s+\$this->{rel_type}\(([^)]+)\)"
            matches = re.findall(pattern, content)

            for method_name, args in matches:
                # Parse the arguments
                args_list = [a.strip().strip("'\"") for a in args.split(",")]
                related_model = args_list[0].replace("::class", "") if args_list else ""

                relationships.append({
                    "method": method_name,
                    "type": rel_type,
                    "related_model": related_model,
                    "foreign_key": args_list[1] if len(args_list) > 1 else None,
                    "local_key": args_list[2] if len(args_list) > 2 else None,
                })

        return relationships

    @staticmethod
    def extract_table_name(content: str, class_name: str) -> str:
        """Extract or infer table name."""
        # Explicit table name
        match = re.search(r"protected\s+\$table\s*=\s*['\"](\w+)['\"]", content)
        if match:
            return match.group(1)

        # Convention: snake_case plural
        import re
        # Convert CamelCase to snake_case
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', class_name)
        snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

        # Simple pluralization
        if snake.endswith('y'):
            return snake[:-1] + 'ies'
        elif snake.endswith('s'):
            return snake + 'es'
        else:
            return snake + 's'


class ControllerAnalyzer:
    """Analyzes Laravel controllers."""

    RESOURCE_METHODS = ['index', 'create', 'store', 'show', 'edit', 'update', 'destroy']
    API_RESOURCE_METHODS = ['index', 'store', 'show', 'update', 'destroy']

    @staticmethod
    def extract_methods(content: str) -> List[str]:
        """Extract method names from controller."""
        return re.findall(r"public\s+function\s+(\w+)\s*\(", content)

    @staticmethod
    def is_resource_controller(content: str) -> bool:
        """Check if controller follows resource pattern."""
        methods = ControllerAnalyzer.extract_methods(content)
        resource_count = sum(1 for m in methods if m in ControllerAnalyzer.RESOURCE_METHODS)
        return resource_count >= 4

    @staticmethod
    def is_api_controller(file_path: str, content: str) -> bool:
        """Check if this is an API controller."""
        if "/Api/" in file_path or "/API/" in file_path:
            return True
        if "JsonResponse" in content or "response()->json" in content:
            return True
        return False

    @staticmethod
    def extract_model_name(content: str, class_name: str) -> Optional[str]:
        """Extract the model this controller manages."""
        # From type hints
        match = re.search(r"use\s+App\\Models\\(\w+);", content)
        if match:
            return match.group(1)

        # From controller name (UsersController -> User)
        if class_name.endswith("Controller"):
            name = class_name[:-10]  # Remove "Controller"
            if name.endswith("s"):
                return name[:-1]  # Remove plural 's'
            return name

        return None


class MigrationAnalyzer:
    """Analyzes Laravel migrations."""

    @staticmethod
    def extract_table_name(content: str) -> Optional[str]:
        """Extract the target table name."""
        # Schema::create
        match = re.search(r"Schema::create\(['\"](\w+)['\"]", content)
        if match:
            return match.group(1)

        # Schema::table
        match = re.search(r"Schema::table\(['\"](\w+)['\"]", content)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def extract_columns(content: str) -> List[Dict[str, Any]]:
        """Extract column definitions from migration."""
        columns = []

        # Match column definitions like $table->string('name')
        pattern = r"\$table->(\w+)\(['\"](\w+)['\"]"
        matches = re.findall(pattern, content)

        for col_type, col_name in matches:
            if col_type not in ['foreign', 'index', 'unique', 'primary']:
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "nullable": f"'{col_name}')" in content and "->nullable()" in content,
                })

        return columns

    @staticmethod
    def generate_timestamp() -> str:
        """Generate migration timestamp."""
        return datetime.now().strftime("%Y_%m_%d_%H%M%S")


class RouteAnalyzer:
    """Analyzes Laravel route files."""

    @staticmethod
    def extract_routes(content: str) -> List[Dict[str, Any]]:
        """Extract route definitions."""
        routes = []

        # Simple routes: Route::get('/path', [Controller::class, 'method'])
        pattern = r"Route::(\w+)\(['\"]([^'\"]+)['\"],\s*\[([^\]]+)\]\)"
        for match in re.finditer(pattern, content):
            routes.append({
                "method": match.group(1).upper(),
                "uri": match.group(2),
                "action": match.group(3).strip(),
            })

        # Resource routes
        resource_pattern = r"Route::(api)?[Rr]esource\(['\"]([^'\"]+)['\"],\s*([^)]+)\)"
        for match in re.finditer(resource_pattern, content):
            routes.append({
                "method": "apiResource" if match.group(1) else "resource",
                "uri": match.group(2),
                "action": match.group(3).strip(),
            })

        return routes

    @staticmethod
    def extract_route_groups(content: str) -> List[Dict[str, Any]]:
        """Extract route groups with their middleware/prefix."""
        groups = []

        # Route::middleware(['auth'])->group(function () { ... })
        pattern = r"Route::middleware\(\[([^\]]+)\]\)->group"
        for match in re.finditer(pattern, content):
            middleware = [m.strip().strip("'\"") for m in match.group(1).split(",")]
            groups.append({"type": "middleware", "value": middleware})

        # Route::prefix('admin')->group
        prefix_pattern = r"Route::prefix\(['\"]([^'\"]+)['\"]\)->group"
        for match in re.finditer(prefix_pattern, content):
            groups.append({"type": "prefix", "value": match.group(1)})

        return groups

    @staticmethod
    def find_insertion_point(content: str, route_info: Dict[str, Any]) -> str:
        """Find the best insertion point for a new route."""
        # If there's a matching prefix group, insert there
        if route_info.get("prefix"):
            prefix = route_info["prefix"]
            if f"prefix('{prefix}')" in content or f'prefix("{prefix}")' in content:
                return f"inside the '{prefix}' prefix group"

        # If there's matching middleware, insert there
        if route_info.get("middleware"):
            for mw in route_info["middleware"]:
                if f"'{mw}'" in content or f'"{mw}"' in content:
                    return f"inside the '{mw}' middleware group"

        # Default: end of file before closing
        return "at the end of the route definitions"


# =============================================================================
# LARAVEL CODE GENERATORS
# =============================================================================

class LaravelCodeGenerator:
    """Generates Laravel-specific code snippets."""

    @staticmethod
    def generate_model_relationship(
            method_name: str,
            relationship_type: str,
            related_model: str,
            foreign_key: Optional[str] = None,
            local_key: Optional[str] = None,
    ) -> str:
        """Generate a model relationship method."""
        rel_info = RelationshipInfo(
            method_name=method_name,
            relationship_type=relationship_type,
            related_model=related_model,
            foreign_key=foreign_key,
            local_key=local_key,
        )
        return rel_info.to_code()

    @staticmethod
    def generate_fillable_array(fields: List[str]) -> str:
        """Generate fillable array declaration."""
        fields_str = ",\n        ".join(f"'{f}'" for f in fields)
        return f"""
    /**
     * The attributes that are mass assignable.
     *
     * @var array<int, string>
     */
    protected $fillable = [
        {fields_str},
    ];"""

    @staticmethod
    def generate_casts_array(casts: Dict[str, str]) -> str:
        """Generate casts array declaration."""
        casts_str = ",\n        ".join(f"'{k}' => '{v}'" for k, v in casts.items())
        return f"""
    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        {casts_str},
    ];"""

    @staticmethod
    def generate_migration_column(column: MigrationColumn) -> str:
        """Generate a migration column definition."""
        return column.to_code()

    @staticmethod
    def generate_migration_foreign_key(
            column: str,
            references: str,
            on_table: str,
            on_delete: str = "cascade",
    ) -> str:
        """Generate a foreign key constraint."""
        return f"$table->foreign('{column}')->references('{references}')->on('{on_table}')->onDelete('{on_delete}');"

    @staticmethod
    def generate_validation_rules(fields: Dict[str, str]) -> str:
        """Generate validation rules array."""
        rules = []
        for field_name, field_type in fields.items():
            type_rules = VALIDATION_RULES.get(field_type, ["required"])
            rules.append(f"'{field_name}' => ['" + "', '".join(type_rules) + "']")

        return "[\n            " + ",\n            ".join(rules) + ",\n        ]"

    @staticmethod
    def generate_resource_method(
            method_name: str,
            model_name: str,
            is_api: bool = True,
    ) -> str:
        """Generate a resource controller method."""
        model_var = model_name[0].lower() + model_name[1:]

        methods = {
            "index": f"""
    /**
     * Display a listing of the resource.
     */
    public function index(): {'JsonResponse' if is_api else 'View'}
    {{
        ${model_var}s = {model_name}::paginate(15);

        return {'response()->json($' + model_var + 's)' if is_api else "view('" + model_var + "s.index', compact('" + model_var + "s'))"};
    }}""",
            "store": f"""
    /**
     * Store a newly created resource in storage.
     */
    public function store(Store{model_name}Request $request): {'JsonResponse' if is_api else 'RedirectResponse'}
    {{
        ${model_var} = {model_name}::create($request->validated());

        return {'response()->json($' + model_var + ', 201)' if is_api else "redirect()->route('" + model_var + "s.show', $" + model_var + ")"};
    }}""",
            "show": f"""
    /**
     * Display the specified resource.
     */
    public function show({model_name} ${model_var}): {'JsonResponse' if is_api else 'View'}
    {{
        return {'response()->json($' + model_var + ')' if is_api else "view('" + model_var + "s.show', compact('" + model_var + "'))"};
    }}""",
            "update": f"""
    /**
     * Update the specified resource in storage.
     */
    public function update(Update{model_name}Request $request, {model_name} ${model_var}): {'JsonResponse' if is_api else 'RedirectResponse'}
    {{
        ${model_var}->update($request->validated());

        return {'response()->json($' + model_var + ')' if is_api else "redirect()->route('" + model_var + "s.show', $" + model_var + ")"};
    }}""",
            "destroy": f"""
    /**
     * Remove the specified resource from storage.
     */
    public function destroy({model_name} ${model_var}): {'JsonResponse' if is_api else 'RedirectResponse'}
    {{
        ${model_var}->delete();

        return {'response()->json(null, 204)' if is_api else "redirect()->route('" + model_var + "s.index')"};
    }}""",
        }

        return methods.get(method_name, "")

    @staticmethod
    def generate_route(route_info: RouteInfo) -> str:
        """Generate a route definition."""
        return route_info.to_code()


# =============================================================================
# LARAVEL CONTEXT ENHANCER
# =============================================================================

class LaravelContextEnhancer:
    """
    Enhances execution context with Laravel-specific intelligence.

    This class analyzes the task and context to provide Laravel-specific
    guidance for code generation.
    """

    def __init__(self):
        self.file_detector = LaravelFileDetector()
        self.model_analyzer = ModelAnalyzer()
        self.controller_analyzer = ControllerAnalyzer()
        self.migration_analyzer = MigrationAnalyzer()
        self.route_analyzer = RouteAnalyzer()
        self.code_generator = LaravelCodeGenerator()

    def enhance_context(
            self,
            file_path: str,
            description: str,
            current_content: str = "",
            context_chunks: List[Any] = None,
    ) -> Dict[str, Any]:
        """
        Enhance execution context with Laravel-specific information.

        Returns a dictionary with:
        - file_type: Detected Laravel file type
        - file_info: Analyzed file information
        - suggestions: Laravel-specific suggestions
        - code_snippets: Pre-generated code snippets if applicable
        - conventions: Laravel conventions to follow
        """
        context_chunks = context_chunks or []

        # Detect file type
        file_type = self.file_detector.detect_from_content(current_content, file_path)

        # Build enhanced context
        enhanced = {
            "file_type": file_type.value,
            "file_info": {},
            "suggestions": [],
            "code_snippets": {},
            "conventions": self._get_conventions(file_type),
        }

        # Type-specific enhancement
        if file_type == LaravelFileType.MODEL:
            enhanced.update(self._enhance_model_context(
                file_path, description, current_content, context_chunks
            ))
        elif file_type == LaravelFileType.CONTROLLER:
            enhanced.update(self._enhance_controller_context(
                file_path, description, current_content, context_chunks
            ))
        elif file_type == LaravelFileType.MIGRATION:
            enhanced.update(self._enhance_migration_context(
                file_path, description, current_content, context_chunks
            ))
        elif file_type == LaravelFileType.ROUTE:
            enhanced.update(self._enhance_route_context(
                file_path, description, current_content, context_chunks
            ))
        elif file_type == LaravelFileType.REQUEST:
            enhanced.update(self._enhance_request_context(
                file_path, description, current_content, context_chunks
            ))

        return enhanced

    def _get_conventions(self, file_type: LaravelFileType) -> Dict[str, str]:
        """Get Laravel conventions for file type."""
        conventions = {
            LaravelFileType.MODEL: {
                "namespace": "App\\Models",
                "extends": "Illuminate\\Database\\Eloquent\\Model",
                "naming": "Singular PascalCase (User, OrderItem)",
                "traits": "Use HasFactory for factories",
                "fillable": "Always define $fillable or $guarded",
                "relationships": "Define all relationships with proper return types",
            },
            LaravelFileType.CONTROLLER: {
                "namespace": "App\\Http\\Controllers",
                "extends": "App\\Http\\Controllers\\Controller",
                "naming": "Plural + Controller (UsersController)",
                "methods": "Use resource methods (index, show, store, update, destroy)",
                "injection": "Use constructor injection for dependencies",
                "responses": "Return proper response types (JsonResponse for API)",
            },
            LaravelFileType.MIGRATION: {
                "namespace": "None (anonymous class)",
                "extends": "Illuminate\\Database\\Migrations\\Migration",
                "naming": "Timestamp + descriptive (2024_01_01_000000_create_users_table)",
                "up_down": "Always implement both up() and down()",
                "foreign_keys": "Define foreign keys with proper cascades",
            },
            LaravelFileType.ROUTE: {
                "grouping": "Group routes by middleware and prefix",
                "naming": "Use route names for all routes",
                "controllers": "Use Controller::class syntax",
                "verbs": "Use appropriate HTTP verbs",
            },
            LaravelFileType.REQUEST: {
                "namespace": "App\\Http\\Requests",
                "extends": "Illuminate\\Foundation\\Http\\FormRequest",
                "naming": "Action + Model + Request (StoreUserRequest)",
                "authorize": "Implement authorize() method",
                "rules": "Return validation rules array",
            },
        }

        return conventions.get(file_type, {})

    def _enhance_model_context(
            self,
            file_path: str,
            description: str,
            current_content: str,
            context_chunks: List[Any],
    ) -> Dict[str, Any]:
        """Enhance context for model files."""
        enhanced = {"file_info": {}, "suggestions": [], "code_snippets": {}}

        # Extract class name from path
        class_name = file_path.split("/")[-1].replace(".php", "")

        if current_content:
            # Analyze existing model
            enhanced["file_info"] = {
                "class_name": class_name,
                "table_name": self.model_analyzer.extract_table_name(current_content, class_name),
                "fillable": self.model_analyzer.extract_fillable(current_content),
                "casts": self.model_analyzer.extract_casts(current_content),
                "relationships": self.model_analyzer.extract_relationships(current_content),
            }

        # Detect if adding relationship from description
        if "relationship" in description.lower() or any(
                rel in description.lower() for rel in ELOQUENT_RELATIONSHIPS.keys()
        ):
            # Try to extract relationship details from description
            for rel_type in ELOQUENT_RELATIONSHIPS.keys():
                if rel_type.lower() in description.lower():
                    enhanced["suggestions"].append(
                        f"Use {rel_type}() for this relationship"
                    )
                    # Generate sample code
                    enhanced["code_snippets"]["relationship_sample"] = (
                        self.code_generator.generate_model_relationship(
                            "items",  # placeholder
                            rel_type,
                            "RelatedModel",
                        )
                    )
                    break

        return enhanced

    def _enhance_controller_context(
            self,
            file_path: str,
            description: str,
            current_content: str,
            context_chunks: List[Any],
    ) -> Dict[str, Any]:
        """Enhance context for controller files."""
        enhanced = {"file_info": {}, "suggestions": [], "code_snippets": {}}

        class_name = file_path.split("/")[-1].replace(".php", "")
        is_api = self.controller_analyzer.is_api_controller(file_path, current_content)

        enhanced["file_info"] = {
            "class_name": class_name,
            "is_api": is_api,
            "is_resource": self.controller_analyzer.is_resource_controller(current_content),
            "model_name": self.controller_analyzer.extract_model_name(current_content, class_name),
            "existing_methods": self.controller_analyzer.extract_methods(current_content),
        }

        # Suggest resource methods if applicable
        model_name = enhanced["file_info"]["model_name"]
        if model_name:
            existing = enhanced["file_info"]["existing_methods"]
            missing_resource = [
                m for m in self.controller_analyzer.API_RESOURCE_METHODS
                if m not in existing
            ]

            if missing_resource:
                enhanced["suggestions"].append(
                    f"Missing resource methods: {', '.join(missing_resource)}"
                )

                # Generate sample for first missing method
                if missing_resource:
                    enhanced["code_snippets"]["method_sample"] = (
                        self.code_generator.generate_resource_method(
                            missing_resource[0],
                            model_name,
                            is_api,
                        )
                    )

        return enhanced

    def _enhance_migration_context(
            self,
            file_path: str,
            description: str,
            current_content: str,
            context_chunks: List[Any],
    ) -> Dict[str, Any]:
        """Enhance context for migration files."""
        enhanced = {"file_info": {}, "suggestions": [], "code_snippets": {}}

        if current_content:
            enhanced["file_info"] = {
                "table_name": self.migration_analyzer.extract_table_name(current_content),
                "columns": self.migration_analyzer.extract_columns(current_content),
            }

        # Generate timestamp for new migrations
        if not current_content:
            enhanced["code_snippets"]["timestamp"] = (
                self.migration_analyzer.generate_timestamp()
            )

        # Detect if adding foreign key from description
        if "foreign" in description.lower() or "relationship" in description.lower():
            enhanced["suggestions"].append(
                "Add foreign key with proper cascade rules"
            )
            enhanced["code_snippets"]["foreign_key_sample"] = (
                self.code_generator.generate_migration_foreign_key(
                    "user_id",
                    "id",
                    "users",
                )
            )

        return enhanced

    def _enhance_route_context(
            self,
            file_path: str,
            description: str,
            current_content: str,
            context_chunks: List[Any],
    ) -> Dict[str, Any]:
        """Enhance context for route files."""
        enhanced = {"file_info": {}, "suggestions": [], "code_snippets": {}}

        if current_content:
            enhanced["file_info"] = {
                "existing_routes": self.route_analyzer.extract_routes(current_content),
                "route_groups": self.route_analyzer.extract_route_groups(current_content),
            }

            # Find best insertion point
            enhanced["suggestions"].append(
                f"Insert new route: {self.route_analyzer.find_insertion_point(current_content, {})}"
            )

        # Detect if this is an API route file
        if "api.php" in file_path:
            enhanced["suggestions"].append("Use apiResource for REST endpoints")
            enhanced["suggestions"].append("Apply 'api' middleware group")

        return enhanced

    def _enhance_request_context(
            self,
            file_path: str,
            description: str,
            current_content: str,
            context_chunks: List[Any],
    ) -> Dict[str, Any]:
        """Enhance context for form request files."""
        enhanced = {"file_info": {}, "suggestions": [], "code_snippets": {}}

        class_name = file_path.split("/")[-1].replace(".php", "")

        # Infer model from request name (StoreUserRequest -> User)
        model_match = re.search(r"(Store|Update|Create)(\w+)Request", class_name)
        if model_match:
            model_name = model_match.group(2)
            enhanced["file_info"]["model_name"] = model_name
            enhanced["file_info"]["action"] = model_match.group(1).lower()

        enhanced["suggestions"].append("Implement authorize() to check permissions")
        enhanced["suggestions"].append("Return validation rules in rules() method")

        return enhanced


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

def get_laravel_enhancement(
        file_path: str,
        description: str,
        current_content: str = "",
        context_chunks: List[Any] = None,
) -> Dict[str, Any]:
    """
    Main entry point for Laravel intelligence.

    Usage in Forge executor:
    ```python
    from app.agents.forge_laravel import get_laravel_enhancement

    laravel_context = get_laravel_enhancement(
        step.file,
        step.description,
        current_file_content,
        context.chunks,
    )

    # Include in prompt
    prompt += f"<laravel_context>{json.dumps(laravel_context)}</laravel_context>"
    ```
    """
    enhancer = LaravelContextEnhancer()
    return enhancer.enhance_context(
        file_path,
        description,
        current_content,
        context_chunks or [],
    )
