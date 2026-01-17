"""
Multilingual Support Service.

Provides language detection, translation, and localized responses
for international Laravel projects with support for 15+ languages.
"""
import logging
import re
import time
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from anthropic import AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class SupportedLanguage(str, Enum):
    """Languages with high-quality Claude support (97%+ relative performance)."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    RUSSIAN = "ru"
    CHINESE_SIMPLIFIED = "zh-CN"
    CHINESE_TRADITIONAL = "zh-TW"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    HINDI = "hi"
    TURKISH = "tr"
    POLISH = "pl"
    UKRAINIAN = "uk"
    VIETNAMESE = "vi"
    THAI = "th"
    INDONESIAN = "id"


# Language display names
LANGUAGE_NAMES = {
    SupportedLanguage.ENGLISH: "English",
    SupportedLanguage.SPANISH: "Espa\u00f1ol",
    SupportedLanguage.FRENCH: "Fran\u00e7ais",
    SupportedLanguage.GERMAN: "Deutsch",
    SupportedLanguage.ITALIAN: "Italiano",
    SupportedLanguage.PORTUGUESE: "Portugu\u00eas",
    SupportedLanguage.DUTCH: "Nederlands",
    SupportedLanguage.RUSSIAN: "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    SupportedLanguage.CHINESE_SIMPLIFIED: "\u7b80\u4f53\u4e2d\u6587",
    SupportedLanguage.CHINESE_TRADITIONAL: "\u7e41\u9ad4\u4e2d\u6587",
    SupportedLanguage.JAPANESE: "\u65e5\u672c\u8a9e",
    SupportedLanguage.KOREAN: "\ud55c\uad6d\uc5b4",
    SupportedLanguage.ARABIC: "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
    SupportedLanguage.HINDI: "\u0939\u093f\u0928\u094d\u0926\u0940",
    SupportedLanguage.TURKISH: "T\u00fcrk\u00e7e",
    SupportedLanguage.POLISH: "Polski",
    SupportedLanguage.UKRAINIAN: "\u0423\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0430",
    SupportedLanguage.VIETNAMESE: "Ti\u1ebfng Vi\u1ec7t",
    SupportedLanguage.THAI: "\u0e44\u0e17\u0e22",
    SupportedLanguage.INDONESIAN: "Bahasa Indonesia",
}

# RTL (Right-to-Left) languages
RTL_LANGUAGES = {SupportedLanguage.ARABIC}

# Common programming terms to preserve during translation
PRESERVE_TERMS = [
    "Laravel", "PHP", "Blade", "Eloquent", "Artisan", "Composer",
    "Vue", "React", "JavaScript", "TypeScript", "Node.js", "npm",
    "MySQL", "PostgreSQL", "Redis", "MongoDB", "SQLite",
    "API", "REST", "GraphQL", "JSON", "XML", "HTML", "CSS",
    "HTTP", "HTTPS", "GET", "POST", "PUT", "DELETE", "PATCH",
    "MVC", "SOLID", "DRY", "CRUD", "ORM",
    "Controller", "Model", "View", "Route", "Middleware",
    "Migration", "Seeder", "Factory", "Observer", "Event", "Listener",
    "Queue", "Job", "Worker", "Scheduler",
    "Auth", "Gate", "Policy", "Guard",
    "Cache", "Session", "Cookie",
    "Storage", "Filesystem",
    "Collection", "Carbon",
]


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""
    language: SupportedLanguage
    confidence: float
    detected_script: Optional[str] = None
    is_rtl: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "language": self.language.value,
            "language_name": LANGUAGE_NAMES.get(self.language, self.language.value),
            "confidence": self.confidence,
            "detected_script": self.detected_script,
            "is_rtl": self.is_rtl,
            "metadata": self.metadata,
        }


@dataclass
class TranslationResult:
    """Result of a translation."""
    original_text: str
    translated_text: str
    source_language: SupportedLanguage
    target_language: SupportedLanguage
    preserved_terms: list[str] = field(default_factory=list)
    tokens_used: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "source_language": self.source_language.value,
            "target_language": self.target_language.value,
            "preserved_terms": self.preserved_terms,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }


@dataclass
class LocalizedResponse:
    """A response with localization info."""
    content: str
    language: SupportedLanguage
    original_language: Optional[SupportedLanguage] = None
    was_translated: bool = False
    formatting_hints: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "language": self.language.value,
            "language_name": LANGUAGE_NAMES.get(self.language, self.language.value),
            "original_language": self.original_language.value if self.original_language else None,
            "was_translated": self.was_translated,
            "formatting_hints": self.formatting_hints,
        }


class MultilingualService:
    """
    Service for multilingual support in AI interactions.

    Provides:
    - Language detection for user input and code comments
    - Translation while preserving technical terms
    - Localized system prompts and responses
    - RTL language support hints
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_language: SupportedLanguage = SupportedLanguage.ENGLISH,
    ):
        """
        Initialize the multilingual service.

        Args:
            api_key: Anthropic API key
            default_language: Default response language
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        self.default_language = default_language

        logger.info(f"[MULTILINGUAL] Service initialized with default language: {default_language.value}")

    def _detect_script(self, text: str) -> Optional[str]:
        """Detect the writing script of text."""
        # Check for specific scripts
        scripts = {
            "latin": re.compile(r'[a-zA-Z]'),
            "cyrillic": re.compile(r'[\u0400-\u04FF]'),
            "chinese": re.compile(r'[\u4e00-\u9fff]'),
            "japanese": re.compile(r'[\u3040-\u309F\u30A0-\u30FF]'),
            "korean": re.compile(r'[\uAC00-\uD7AF]'),
            "arabic": re.compile(r'[\u0600-\u06FF]'),
            "devanagari": re.compile(r'[\u0900-\u097F]'),
            "thai": re.compile(r'[\u0E00-\u0E7F]'),
        }

        counts = {}
        for script_name, pattern in scripts.items():
            matches = pattern.findall(text)
            if matches:
                counts[script_name] = len(matches)

        if not counts:
            return None

        return max(counts.items(), key=lambda x: x[1])[0]

    async def detect_language(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> LanguageDetectionResult:
        """
        Detect the language of text.

        Args:
            text: Text to analyze
            context: Optional context for better detection

        Returns:
            LanguageDetectionResult with detected language
        """
        logger.info(f"[MULTILINGUAL] Detecting language for text ({len(text)} chars)")

        # Quick script-based detection for obvious cases
        script = self._detect_script(text)

        # Script to likely language mapping for quick detection
        script_language_map = {
            "chinese": SupportedLanguage.CHINESE_SIMPLIFIED,
            "japanese": SupportedLanguage.JAPANESE,
            "korean": SupportedLanguage.KOREAN,
            "arabic": SupportedLanguage.ARABIC,
            "devanagari": SupportedLanguage.HINDI,
            "thai": SupportedLanguage.THAI,
            "cyrillic": SupportedLanguage.RUSSIAN,  # Could be Ukrainian, etc.
        }

        # If clear script match, return quickly
        if script in script_language_map:
            language = script_language_map[script]
            return LanguageDetectionResult(
                language=language,
                confidence=0.85,
                detected_script=script,
                is_rtl=language in RTL_LANGUAGES,
            )

        # Use Claude for more nuanced detection
        try:
            prompt = f"""Detect the primary language of the following text.
Respond with ONLY the ISO 639-1 language code (e.g., 'en', 'es', 'fr', 'de', 'zh-CN', 'ja', 'ko').

Text to analyze:
{text[:1000]}

{"Context: " + context[:500] if context else ""}

Language code:"""

            response = await self.async_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )

            detected_code = response.content[0].text.strip().lower()

            # Map to SupportedLanguage
            for lang in SupportedLanguage:
                if lang.value.lower() == detected_code:
                    return LanguageDetectionResult(
                        language=lang,
                        confidence=0.95,
                        detected_script=script,
                        is_rtl=lang in RTL_LANGUAGES,
                    )

            # Default to English if unknown
            return LanguageDetectionResult(
                language=SupportedLanguage.ENGLISH,
                confidence=0.5,
                detected_script=script,
                is_rtl=False,
                metadata={"detected_code": detected_code},
            )

        except Exception as e:
            logger.error(f"[MULTILINGUAL] Language detection error: {e}")
            return LanguageDetectionResult(
                language=self.default_language,
                confidence=0.3,
                detected_script=script,
            )

    async def translate(
        self,
        text: str,
        target_language: SupportedLanguage,
        source_language: Optional[SupportedLanguage] = None,
        preserve_code_blocks: bool = True,
        preserve_technical_terms: bool = True,
    ) -> TranslationResult:
        """
        Translate text while preserving technical terms and code.

        Args:
            text: Text to translate
            target_language: Target language
            source_language: Source language (auto-detected if not provided)
            preserve_code_blocks: Keep code blocks untranslated
            preserve_technical_terms: Keep programming terms in English

        Returns:
            TranslationResult with translated text
        """
        logger.info(f"[MULTILINGUAL] Translating to {target_language.value}")
        start_time = time.time()

        # Detect source language if not provided
        if source_language is None:
            detection = await self.detect_language(text)
            source_language = detection.language

        # If same language, return as-is
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
            )

        # Build preservation instructions
        preserve_instructions = ""
        if preserve_technical_terms:
            terms = ", ".join(PRESERVE_TERMS[:30])
            preserve_instructions += f"\n- Keep these technical terms in English: {terms}"

        if preserve_code_blocks:
            preserve_instructions += "\n- Keep all code blocks (```...```) and inline code (`...`) exactly as-is"

        try:
            prompt = f"""Translate the following text from {LANGUAGE_NAMES.get(source_language, source_language.value)} to {LANGUAGE_NAMES.get(target_language, target_language.value)}.

Important instructions:
{preserve_instructions}
- Maintain the original formatting (headers, lists, etc.)
- Keep variable names, function names, and file paths unchanged
- Translate comments and explanations naturally

Text to translate:
{text}

Translation:"""

            response = await self.async_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=len(text) * 2,  # Allow for expansion
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            translated = response.content[0].text
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Find preserved terms
            preserved = [term for term in PRESERVE_TERMS if term in translated]

            logger.info(f"[MULTILINGUAL] Translation complete, latency={latency_ms}ms")

            return TranslationResult(
                original_text=text,
                translated_text=translated,
                source_language=source_language,
                target_language=target_language,
                preserved_terms=preserved,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"[MULTILINGUAL] Translation error: {e}")
            return TranslationResult(
                original_text=text,
                translated_text=text,  # Return original on error
                source_language=source_language,
                target_language=target_language,
            )

    def get_localized_system_prompt(
        self,
        language: SupportedLanguage,
        base_prompt: str,
    ) -> str:
        """
        Get a system prompt with language-specific instructions.

        Args:
            language: Target language
            base_prompt: Base system prompt

        Returns:
            Localized system prompt
        """
        language_name = LANGUAGE_NAMES.get(language, language.value)

        # Add language instructions
        language_instructions = f"""
## Language Instructions
- Respond in {language_name}
- Keep all code, file paths, and technical terms in their original form
- Translate explanations and descriptions naturally
- Use appropriate technical vocabulary for {language_name}
"""

        # Add RTL hints if needed
        if language in RTL_LANGUAGES:
            language_instructions += """
- This is a right-to-left language; ensure text direction is correct
- Keep code blocks left-to-right
"""

        return base_prompt + "\n" + language_instructions

    async def localize_response(
        self,
        content: str,
        target_language: SupportedLanguage,
        source_language: Optional[SupportedLanguage] = None,
    ) -> LocalizedResponse:
        """
        Localize a response to the target language.

        Args:
            content: Content to localize
            target_language: Target language
            source_language: Source language (auto-detected if not provided)

        Returns:
            LocalizedResponse with localized content
        """
        # Detect source if needed
        if source_language is None:
            detection = await self.detect_language(content)
            source_language = detection.language

        # Same language - no translation needed
        if source_language == target_language:
            return LocalizedResponse(
                content=content,
                language=target_language,
                original_language=source_language,
                was_translated=False,
            )

        # Translate
        translation = await self.translate(
            text=content,
            target_language=target_language,
            source_language=source_language,
        )

        # Build formatting hints
        formatting_hints = {}
        if target_language in RTL_LANGUAGES:
            formatting_hints["direction"] = "rtl"
        else:
            formatting_hints["direction"] = "ltr"

        return LocalizedResponse(
            content=translation.translated_text,
            language=target_language,
            original_language=source_language,
            was_translated=True,
            formatting_hints=formatting_hints,
        )

    async def analyze_code_comments_language(
        self,
        code: str,
    ) -> dict[str, Any]:
        """
        Analyze the languages used in code comments.

        Args:
            code: Source code to analyze

        Returns:
            Dict with language analysis
        """
        logger.info("[MULTILINGUAL] Analyzing code comment languages")

        # Extract comments (simple regex-based extraction)
        # PHP/JS style comments
        single_line = re.findall(r'//\s*(.+?)$', code, re.MULTILINE)
        multi_line = re.findall(r'/\*\s*(.+?)\s*\*/', code, re.DOTALL)
        hash_comments = re.findall(r'#\s*(.+?)$', code, re.MULTILINE)
        blade_comments = re.findall(r'\{\{--\s*(.+?)\s*--\}\}', code, re.DOTALL)

        all_comments = single_line + multi_line + hash_comments + blade_comments

        if not all_comments:
            return {
                "has_comments": False,
                "languages_detected": [],
            }

        # Combine comments for analysis
        combined = " ".join(all_comments)
        detection = await self.detect_language(combined)

        return {
            "has_comments": True,
            "comment_count": len(all_comments),
            "primary_language": detection.to_dict(),
            "languages_detected": [detection.language.value],
        }

    def get_supported_languages(self) -> list[dict]:
        """Get list of supported languages."""
        return [
            {
                "code": lang.value,
                "name": LANGUAGE_NAMES.get(lang, lang.value),
                "is_rtl": lang in RTL_LANGUAGES,
            }
            for lang in SupportedLanguage
        ]

    async def suggest_localization(
        self,
        project_files: list[dict],
    ) -> dict:
        """
        Analyze a project and suggest localization improvements.

        Args:
            project_files: List of {path, content} dicts

        Returns:
            Localization suggestions
        """
        logger.info(f"[MULTILINGUAL] Analyzing {len(project_files)} files for localization")

        suggestions = {
            "hardcoded_strings": [],
            "missing_translations": [],
            "inconsistent_languages": [],
            "recommendations": [],
        }

        # Analyze each file
        for file_info in project_files[:20]:  # Limit analysis
            path = file_info.get("path", "")
            content = file_info.get("content", "")

            # Check for hardcoded strings in Blade templates
            if path.endswith(".blade.php"):
                # Find strings not wrapped in translation helpers
                hardcoded = re.findall(r'>([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)<', content)
                if hardcoded:
                    suggestions["hardcoded_strings"].extend([
                        {"file": path, "string": s}
                        for s in hardcoded[:5]
                    ])

            # Check for hardcoded strings in Vue files
            if path.endswith(".vue"):
                hardcoded = re.findall(r'>\s*([A-Z][^<{]+[a-z])\s*<', content)
                if hardcoded:
                    suggestions["hardcoded_strings"].extend([
                        {"file": path, "string": s.strip()}
                        for s in hardcoded[:5]
                    ])

        # Add recommendations
        if suggestions["hardcoded_strings"]:
            suggestions["recommendations"].append(
                "Consider using Laravel's localization helpers (__(), @lang()) for user-facing strings"
            )
            suggestions["recommendations"].append(
                "Extract hardcoded strings to language files in resources/lang/"
            )

        return suggestions


# Factory function
def get_multilingual_service(
    default_language: SupportedLanguage = SupportedLanguage.ENGLISH,
) -> MultilingualService:
    """Get a multilingual service instance."""
    return MultilingualService(default_language=default_language)
