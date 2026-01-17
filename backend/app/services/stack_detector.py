"""
Stack Detector Service

Detects project technology stack from configuration files.
Identifies backend/frontend frameworks, databases, caching, queues, etc.
"""
import os
import json
import re
from typing import Dict, Any, Optional
from pathlib import Path


class StackDetector:
    """Detect project stack from files."""

    def __init__(self, project_path: str):
        self.path = project_path

    def detect(self) -> Dict[str, Any]:
        """Run full stack detection."""
        return {
            "backend": self._detect_backend(),
            "frontend": self._detect_frontend(),
            "database": self._detect_database(),
            "cache": self._detect_cache(),
            "queue": self._detect_queue(),
            "realtime": self._detect_realtime(),
            "testing": self._detect_testing(),
            "ci_cd": self._detect_cicd(),
            "deployment": self._detect_deployment(),
        }

    # ========== Backend Detection ==========

    def _detect_backend(self) -> Dict[str, Any]:
        """Detect backend framework and version."""

        # Check for Laravel (PHP)
        composer = self._read_json("composer.json")
        if composer:
            require = composer.get("require", {})
            if "laravel/framework" in str(require):
                return self._detect_laravel(composer)

        # Check for Django (Python)
        if self._file_exists("manage.py") and self._file_exists("requirements.txt"):
            requirements = self._read_file("requirements.txt")
            if requirements and "django" in requirements.lower():
                return self._detect_django()

        # Check for FastAPI (Python)
        requirements = self._read_file("requirements.txt")
        if requirements and "fastapi" in requirements.lower():
            return self._detect_fastapi()

        # Check for Rails (Ruby)
        if self._file_exists("Gemfile"):
            gemfile = self._read_file("Gemfile")
            if gemfile and "rails" in gemfile.lower():
                return self._detect_rails()

        # Check for Node.js backend
        package = self._read_json("package.json")
        if package:
            deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            if "express" in deps:
                return {"framework": "express", "language": "javascript", "runtime": "node"}
            if "nestjs" in str(deps) or "@nestjs/core" in deps:
                return {"framework": "nestjs", "language": "typescript", "runtime": "node"}
            if "fastify" in deps:
                return {"framework": "fastify", "language": "javascript", "runtime": "node"}

        return {"framework": "unknown"}

    def _detect_laravel(self, composer: dict) -> Dict[str, Any]:
        """Extract Laravel details."""
        require = composer.get("require", {})
        require_dev = composer.get("require-dev", {})

        # Laravel version
        laravel_version = require.get("laravel/framework", "unknown")
        laravel_version = re.sub(r"[\^~>=<]", "", laravel_version).split(",")[0].strip()

        # PHP version
        php_version = require.get("php", "unknown")
        php_version = re.sub(r"[\^~>=<|]", "", php_version).split(",")[0].strip()

        # Detect Laravel packages
        all_deps = {**require, **require_dev}
        packages = {
            "octane": "laravel/octane" in all_deps,
            "horizon": "laravel/horizon" in all_deps,
            "reverb": "laravel/reverb" in all_deps,
            "pulse": "laravel/pulse" in all_deps,
            "sanctum": "laravel/sanctum" in all_deps,
            "passport": "laravel/passport" in all_deps,
            "fortify": "laravel/fortify" in all_deps,
            "socialite": "laravel/socialite" in all_deps,
            "cashier": "laravel/cashier" in all_deps or "laravel/cashier-stripe" in all_deps,
            "scout": "laravel/scout" in all_deps,
            "telescope": "laravel/telescope" in all_deps,
            "pennant": "laravel/pennant" in all_deps,
            "pint": "laravel/pint" in all_deps,
            "sail": "laravel/sail" in all_deps,
            "breeze": "laravel/breeze" in all_deps,
            "jetstream": "laravel/jetstream" in all_deps,
            "livewire": "livewire/livewire" in all_deps,
            "inertia": "inertiajs/inertia-laravel" in all_deps,
            "filament": "filament/filament" in all_deps,
        }

        return {
            "framework": "laravel",
            "version": laravel_version,
            "language": "php",
            "php_version": php_version,
            "packages": {k: v for k, v in packages.items() if v},
        }

    def _detect_django(self) -> Dict[str, Any]:
        """Extract Django details."""
        requirements = self._read_file("requirements.txt") or ""

        # Extract version
        version = "unknown"
        for line in requirements.split("\n"):
            if line.lower().startswith("django"):
                version_match = re.search(r"[\d.]+", line)
                if version_match:
                    version = version_match.group()
                break

        return {
            "framework": "django",
            "version": version,
            "language": "python",
            "rest_framework": "djangorestframework" in requirements.lower(),
        }

    def _detect_fastapi(self) -> Dict[str, Any]:
        """Extract FastAPI details."""
        requirements = self._read_file("requirements.txt") or ""

        version = "unknown"
        for line in requirements.split("\n"):
            if line.lower().startswith("fastapi"):
                version_match = re.search(r"[\d.]+", line)
                if version_match:
                    version = version_match.group()
                break

        return {
            "framework": "fastapi",
            "version": version,
            "language": "python",
            "async": True,
        }

    def _detect_rails(self) -> Dict[str, Any]:
        """Extract Rails details."""
        gemfile = self._read_file("Gemfile") or ""

        version = "unknown"
        for line in gemfile.split("\n"):
            if "rails" in line.lower() and "gem" in line:
                version_match = re.search(r"[\d.]+", line)
                if version_match:
                    version = version_match.group()
                break

        return {
            "framework": "rails",
            "version": version,
            "language": "ruby",
        }

    # ========== Frontend Detection ==========

    def _detect_frontend(self) -> Dict[str, Any]:
        """Detect frontend framework."""

        package = self._read_json("package.json")
        if not package:
            # Check for Blade-only Laravel
            if self._dir_exists("resources/views"):
                return {"framework": "blade", "templating": True}
            return {"framework": "none"}

        deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}

        result = {
            "build_tool": self._detect_build_tool(deps),
            "typescript": "typescript" in deps,
            "css_framework": self._detect_css_framework(deps),
        }

        # Vue
        if "vue" in deps:
            vue_version = deps.get("vue", "").replace("^", "").replace("~", "").split(".")[0]
            result.update({
                "framework": "vue",
                "version": deps.get("vue", "").replace("^", "").replace("~", ""),
                "composition_api": vue_version == "3" or vue_version.startswith("3"),
                "inertia": "@inertiajs/vue3" in deps or "@inertiajs/vue2" in deps,
                "router": "vue-router" in deps,
                "state": self._detect_vue_state(deps),
                "ui_library": self._detect_vue_ui(deps),
            })
            return result

        # React
        if "react" in deps:
            react_version = deps.get("react", "").replace("^", "").replace("~", "")
            result.update({
                "framework": "react",
                "version": react_version,
                "nextjs": "next" in deps,
                "remix": "@remix-run/react" in deps,
                "inertia": "@inertiajs/react" in deps,
                "state": self._detect_react_state(deps),
                "ui_library": self._detect_react_ui(deps),
            })
            return result

        # Svelte
        if "svelte" in deps:
            result.update({
                "framework": "svelte",
                "version": deps.get("svelte", "").replace("^", "").replace("~", ""),
                "sveltekit": "@sveltejs/kit" in deps,
                "inertia": "@inertiajs/svelte" in deps,
            })
            return result

        # Alpine.js
        if "alpinejs" in deps:
            result.update({
                "framework": "alpine",
                "version": deps.get("alpinejs", "").replace("^", "").replace("~", ""),
            })
            return result

        # Livewire (check PHP)
        composer = self._read_json("composer.json")
        if composer:
            if "livewire/livewire" in str(composer.get("require", {})):
                result.update({
                    "framework": "livewire",
                    "alpine": "alpinejs" in deps,
                })
                return result

        return result

    def _detect_build_tool(self, deps: dict) -> str:
        """Detect frontend build tool."""
        if "vite" in deps:
            return "vite"
        if "webpack" in deps or "webpack-cli" in deps:
            return "webpack"
        if "esbuild" in deps:
            return "esbuild"
        if "parcel" in deps:
            return "parcel"
        if "rollup" in deps:
            return "rollup"
        if "laravel-mix" in deps:
            return "laravel-mix"
        return "unknown"

    def _detect_css_framework(self, deps: dict) -> Optional[str]:
        """Detect CSS framework."""
        css_frameworks = {
            "tailwindcss": "tailwind",
            "bootstrap": "bootstrap",
            "@mui/material": "material-ui",
            "bulma": "bulma",
            "foundation-sites": "foundation",
            "unocss": "unocss",
        }
        for pkg, name in css_frameworks.items():
            if pkg in deps:
                return name
        return None

    def _detect_vue_ui(self, deps: dict) -> Optional[str]:
        """Detect Vue UI library."""
        ui_libs = {
            "radix-vue": "radix-vue",
            "reka-ui": "reka-ui",
            "@headlessui/vue": "headless-ui",
            "vuetify": "vuetify",
            "primevue": "primevue",
            "element-plus": "element-plus",
            "naive-ui": "naive-ui",
            "quasar": "quasar",
            "@nuxt/ui": "nuxt-ui",
            "vant": "vant",
            "ant-design-vue": "ant-design",
        }
        for pkg, name in ui_libs.items():
            if pkg in deps:
                return name
        return None

    def _detect_vue_state(self, deps: dict) -> Optional[str]:
        """Detect Vue state management."""
        if "pinia" in deps:
            return "pinia"
        if "vuex" in deps:
            return "vuex"
        return None

    def _detect_react_ui(self, deps: dict) -> Optional[str]:
        """Detect React UI library."""
        ui_libs = {
            "@radix-ui/react-dialog": "radix",
            "@headlessui/react": "headless-ui",
            "@mui/material": "material-ui",
            "@chakra-ui/react": "chakra",
            "antd": "ant-design",
            "@mantine/core": "mantine",
            "react-bootstrap": "bootstrap",
            "@nextui-org/react": "nextui",
            "shadcn-ui": "shadcn",
        }
        for pkg, name in ui_libs.items():
            if pkg in deps:
                return name
        return None

    def _detect_react_state(self, deps: dict) -> Optional[str]:
        """Detect React state management."""
        if "zustand" in deps:
            return "zustand"
        if "redux" in deps or "@reduxjs/toolkit" in deps:
            return "redux"
        if "recoil" in deps:
            return "recoil"
        if "jotai" in deps:
            return "jotai"
        if "mobx" in deps:
            return "mobx"
        return None

    # ========== Infrastructure Detection ==========

    def _detect_database(self) -> str:
        """Detect database from config."""

        # Check .env.example
        env = self._read_file(".env.example") or self._read_file(".env")
        if env:
            if "DB_CONNECTION=mysql" in env:
                return "mysql"
            if "DB_CONNECTION=pgsql" in env:
                return "postgresql"
            if "DB_CONNECTION=sqlite" in env:
                return "sqlite"
            if "DB_CONNECTION=mariadb" in env:
                return "mariadb"
            if "DB_CONNECTION=sqlsrv" in env:
                return "sqlserver"
            # PostgreSQL patterns
            if "DATABASE_URL" in env and "postgres" in env:
                return "postgresql"

        # Check config/database.php for Laravel
        db_config = self._read_file("config/database.php")
        if db_config:
            if "'default' => env('DB_CONNECTION', 'mysql')" in db_config:
                return "mysql"
            if "'default' => env('DB_CONNECTION', 'pgsql')" in db_config:
                return "postgresql"

        # Check docker-compose for database services
        docker = self._read_file("docker-compose.yml") or self._read_file("docker-compose.yaml")
        if docker:
            if "mysql:" in docker or "mariadb:" in docker:
                return "mysql"
            if "postgres:" in docker:
                return "postgresql"
            if "mongo:" in docker:
                return "mongodb"

        return "unknown"

    def _detect_cache(self) -> str:
        """Detect cache driver."""
        env = self._read_file(".env.example") or self._read_file(".env")
        if env:
            if "CACHE_DRIVER=redis" in env or "CACHE_STORE=redis" in env:
                return "redis"
            if "CACHE_DRIVER=memcached" in env:
                return "memcached"
            if "CACHE_DRIVER=database" in env:
                return "database"
            if "CACHE_DRIVER=dynamodb" in env:
                return "dynamodb"
        return "file"

    def _detect_queue(self) -> str:
        """Detect queue driver."""
        env = self._read_file(".env.example") or self._read_file(".env")
        if env:
            if "QUEUE_CONNECTION=redis" in env:
                return "redis"
            if "QUEUE_CONNECTION=database" in env:
                return "database"
            if "QUEUE_CONNECTION=sqs" in env:
                return "sqs"
            if "QUEUE_CONNECTION=beanstalkd" in env:
                return "beanstalkd"
            if "QUEUE_CONNECTION=rabbitmq" in env:
                return "rabbitmq"
        return "sync"

    def _detect_realtime(self) -> Optional[str]:
        """Detect realtime/websocket solution."""
        composer = self._read_json("composer.json")
        if composer:
            require = composer.get("require", {})
            if "laravel/reverb" in require:
                return "reverb"
            if "pusher/pusher-php-server" in require:
                return "pusher"
            if "beyondcode/laravel-websockets" in require:
                return "laravel-websockets"

        package = self._read_json("package.json")
        if package:
            deps = package.get("dependencies", {})
            if "socket.io" in deps:
                return "socket.io"
            if "ws" in deps:
                return "ws"
            if "pusher-js" in deps:
                return "pusher"

        return None

    def _detect_testing(self) -> Dict[str, bool]:
        """Detect testing frameworks."""
        composer = self._read_json("composer.json")
        package = self._read_json("package.json")

        result = {
            "phpunit": self._file_exists("phpunit.xml") or self._file_exists("phpunit.xml.dist"),
        }

        if composer:
            require_dev = composer.get("require-dev", {})
            result.update({
                "pest": "pestphp/pest" in require_dev,
                "dusk": "laravel/dusk" in require_dev,
                "mockery": "mockery/mockery" in require_dev,
            })

        if package:
            deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            result.update({
                "vitest": "vitest" in deps,
                "jest": "jest" in deps,
                "cypress": "cypress" in deps,
                "playwright": "@playwright/test" in deps,
                "testing_library": "@testing-library/react" in deps or "@testing-library/vue" in deps,
            })

        return {k: v for k, v in result.items() if v}

    def _detect_cicd(self) -> Dict[str, bool]:
        """Detect CI/CD configurations."""
        return {
            "github_actions": self._dir_exists(".github/workflows"),
            "gitlab_ci": self._file_exists(".gitlab-ci.yml"),
            "jenkins": self._file_exists("Jenkinsfile"),
            "circleci": self._dir_exists(".circleci"),
            "travis": self._file_exists(".travis.yml"),
            "bitbucket": self._file_exists("bitbucket-pipelines.yml"),
        }

    def _detect_deployment(self) -> Dict[str, bool]:
        """Detect deployment configurations."""
        return {
            "docker": self._file_exists("Dockerfile") or self._file_exists("docker-compose.yml"),
            "kubernetes": self._dir_exists("k8s") or self._file_exists("kubernetes.yml"),
            "forge": self._file_exists(".forge") or self._dir_exists(".forge"),
            "vapor": self._file_exists("vapor.yml"),
            "vercel": self._file_exists("vercel.json"),
            "netlify": self._file_exists("netlify.toml"),
            "heroku": self._file_exists("Procfile"),
            "fly": self._file_exists("fly.toml"),
        }

    # ========== Helpers ==========

    def _read_json(self, filename: str) -> Optional[dict]:
        """Read and parse a JSON file."""
        filepath = os.path.join(self.path, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        return None

    def _read_file(self, filename: str) -> Optional[str]:
        """Read a text file."""
        filepath = os.path.join(self.path, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def _file_exists(self, filename: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.path, filename))

    def _dir_exists(self, dirname: str) -> bool:
        """Check if a directory exists."""
        return os.path.isdir(os.path.join(self.path, dirname))
