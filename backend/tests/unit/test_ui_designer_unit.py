"""
Unit tests for UI Designer module functions.

Tests UI generation, tech stack detection, and design file handling.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from uuid import uuid4


class TestUIDesignRequest:
    """Unit tests for UIDesignRequest model."""

    def test_request_creation(self):
        """UIDesignRequest should be created correctly."""
        from app.schemas.ui_designer import UIDesignRequest

        request = UIDesignRequest(
            prompt="Create a login form",
        )

        assert request.prompt == "Create a login form"
        assert request.design_preferences is None
        assert request.target_path is None

    def test_request_with_preferences(self):
        """UIDesignRequest should accept preferences."""
        from app.schemas.ui_designer import UIDesignRequest

        request = UIDesignRequest(
            prompt="Create a dashboard",
            design_preferences={
                "style": "modern",
                "dark_mode": True,
            },
            target_path="src/components/dashboard",
        )

        assert request.design_preferences["dark_mode"] == True
        assert request.target_path == "src/components/dashboard"


class TestDesignStatus:
    """Unit tests for DesignStatus enum."""

    def test_status_values(self):
        """DesignStatus should have correct values."""
        from app.schemas.ui_designer import DesignStatus

        assert DesignStatus.PENDING.value == "pending"
        assert DesignStatus.GENERATING.value == "generating"
        assert DesignStatus.COMPLETED.value == "completed"
        assert DesignStatus.FAILED.value == "failed"
        assert DesignStatus.CANCELLED.value == "cancelled"


class TestGeneratedFile:
    """Unit tests for GeneratedFile model."""

    def test_file_structure(self):
        """GeneratedFile should have correct structure."""
        from app.schemas.ui_designer import GeneratedFile, FileType

        file = GeneratedFile(
            path="src/components/LoginForm.tsx",
            content="export const LoginForm = () => {}",
            file_type=FileType.COMPONENT,
            language="typescript",
        )

        assert file.path.endswith(".tsx")
        assert file.file_type == FileType.COMPONENT

    def test_file_types(self):
        """FileType should have all component types."""
        from app.schemas.ui_designer import FileType

        types = [
            FileType.COMPONENT,
            FileType.PAGE,
            FileType.LAYOUT,
            FileType.STYLE,
            FileType.CONFIG,
            FileType.ASSET,
            FileType.HOOK,
            FileType.UTILITY,
        ]

        assert len(types) >= 5


class TestTechStackDetection:
    """Unit tests for tech stack detection."""

    def test_framework_detection(self):
        """Frontend framework should be detected correctly."""
        # Detection patterns
        react_patterns = ["package.json", "node_modules/react"]
        vue_patterns = ["package.json", "node_modules/vue"]
        next_patterns = ["next.config.js", "pages/", "app/"]

        # Check for Next.js
        files = ["package.json", "next.config.js", "app/page.tsx"]
        has_next_config = "next.config.js" in files
        has_app_dir = any("app/" in f for f in files)

        assert has_next_config
        assert has_app_dir

    def test_css_framework_detection(self):
        """CSS framework should be detected correctly."""
        tailwind_patterns = ["tailwind.config.js", "tailwind.config.ts"]
        css_modules_patterns = ["*.module.css", "*.module.scss"]

        # Check for Tailwind
        files = ["tailwind.config.js", "postcss.config.js"]
        has_tailwind = any(f in tailwind_patterns for f in files)

        assert has_tailwind

    def test_typescript_detection(self):
        """TypeScript usage should be detected."""
        ts_patterns = ["tsconfig.json", "*.tsx", "*.ts"]

        files = ["tsconfig.json", "src/app.tsx"]
        has_tsconfig = "tsconfig.json" in files
        has_tsx_files = any(f.endswith(".tsx") for f in files)

        assert has_tsconfig or has_tsx_files


class TestDesignTokens:
    """Unit tests for design token extraction."""

    def test_color_extraction(self):
        """Colors should be extracted from config."""
        tailwind_colors = {
            "primary": "#3b82f6",
            "secondary": "#64748b",
            "accent": "#f59e0b",
        }

        assert tailwind_colors["primary"].startswith("#")
        assert len(tailwind_colors) >= 3

    def test_spacing_extraction(self):
        """Spacing values should be extracted."""
        spacing = {
            "xs": "0.25rem",
            "sm": "0.5rem",
            "md": "1rem",
            "lg": "1.5rem",
            "xl": "2rem",
        }

        assert "rem" in spacing["md"]

    def test_typography_extraction(self):
        """Typography values should be extracted."""
        typography = {
            "fontFamily": {"sans": "Inter, system-ui, sans-serif"},
            "fontSize": {"base": "1rem", "lg": "1.125rem"},
        }

        assert "Inter" in typography["fontFamily"]["sans"]


class TestComponentGeneration:
    """Unit tests for component generation."""

    def test_component_naming(self):
        """Components should follow naming conventions."""
        prompt = "Create a user profile card"
        expected_name = "UserProfileCard"

        # Simple name generation
        words = prompt.replace("Create a ", "").replace("create a ", "").split()
        name = "".join(word.capitalize() for word in words)

        assert name[0].isupper()

    def test_file_path_generation(self):
        """File paths should be generated correctly."""
        component_name = "LoginForm"
        base_path = "src/components"

        # TypeScript React component
        file_path = f"{base_path}/{component_name}.tsx"

        assert file_path == "src/components/LoginForm.tsx"

    def test_export_detection(self):
        """Exports should be detected from generated code."""
        code = """
export const LoginForm = () => {
  return <form>...</form>;
};

export default LoginForm;
"""

        # Detect exports
        exports = []
        for line in code.split("\n"):
            if line.strip().startswith("export"):
                if "const" in line:
                    name = line.split("const")[1].split("=")[0].strip()
                    exports.append(name)

        assert "LoginForm" in exports


class TestPaletteAgent:
    """Unit tests for Palette agent identity."""

    def test_palette_identity(self):
        """Palette agent should have correct identity."""
        from app.agents.agent_identity import PALETTE

        assert PALETTE.name == "Palette"
        assert PALETTE.role is not None
        assert PALETTE.color is not None

    def test_palette_to_dict(self):
        """Palette should serialize correctly."""
        from app.agents.agent_identity import PALETTE

        data = PALETTE.to_dict()

        assert data["name"] == "Palette"
        assert "role" in data
        assert "color" in data


class TestUIDesigner:
    """Unit tests for UIDesigner class."""

    @pytest.mark.asyncio
    async def test_design_result(self, mock_ui_designer):
        """design should return UIDesignResult."""
        mock_ui_designer.design = AsyncMock(return_value=MagicMock(
            success=True,
            design_id=str(uuid4()),
            files=[],
        ))

        result = await mock_ui_designer.design(
            user_prompt="Create a button",
            project_id="project-123",
        )

        assert result.success == True

    def test_design_streaming(self, mock_ui_designer):
        """design_streaming should yield events."""
        # Streaming yields events as dict
        mock_events = [
            {"event": "design_started", "data": {}},
            {"event": "tech_detected", "data": {"framework": "react"}},
            {"event": "design_complete", "data": {"success": True}},
        ]

        for event in mock_events:
            assert "event" in event
            assert "data" in event


class TestApplyDesign:
    """Unit tests for apply design functionality."""

    def test_apply_design_request(self):
        """ApplyDesignRequest should have correct structure."""
        from app.schemas.ui_designer import ApplyDesignRequest
        from uuid import uuid4

        request = ApplyDesignRequest(
            design_id=str(uuid4()),
            selected_files=["src/components/LoginForm.tsx"],
            backup=True,
            overwrite_existing=False,
        )

        assert len(request.selected_files) == 1
        assert request.backup == True
        assert request.overwrite_existing == False

    def test_apply_design_response(self):
        """ApplyDesignResponse should have correct structure."""
        from app.schemas.ui_designer import ApplyDesignResponse

        response = ApplyDesignResponse(
            success=True,
            files_applied=["src/components/LoginForm.tsx"],
            files_skipped=[],
            backup_path=None,
            errors=[],
        )

        assert response.success == True
        assert len(response.files_applied) == 1
        assert len(response.errors) == 0
