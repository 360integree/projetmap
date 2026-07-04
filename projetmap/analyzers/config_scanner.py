"""Config Scanner — Universal detection of configuration surfaces.

Works across all languages and frameworks by detecting:
- Environment variables (process.env, Platform.environment, os.environ)
- Config files (.env, config.*, settings.*, appsettings.*)
- Feature flags (boolean toggles, enabled/disabled patterns)
- Hardcoded constants that should be configurable
- API endpoints and base URLs
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConfigItem:
    """A configuration item detected in the codebase."""
    name: str
    type: str  # env_var, config_file, feature_flag, constant, api_url, secret
    file: str
    line: int
    value: str | None = None
    default_value: str | None = None
    used_by: list[str] = field(default_factory=list)
    is_secret: bool = False
    description: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ConfigReport:
    """Complete configuration analysis report."""
    env_vars: list[ConfigItem] = field(default_factory=list)
    config_files: list[ConfigItem] = field(default_factory=list)
    feature_flags: list[ConfigItem] = field(default_factory=list)
    constants: list[ConfigItem] = field(default_factory=list)
    api_urls: list[ConfigItem] = field(default_factory=list)
    secrets: list[ConfigItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "env_vars": [self._item_to_dict(i) for i in self.env_vars],
            "config_files": [self._item_to_dict(i) for i in self.config_files],
            "feature_flags": [self._item_to_dict(i) for i in self.feature_flags],
            "constants": [self._item_to_dict(i) for i in self.constants],
            "api_urls": [self._item_to_dict(i) for i in self.api_urls],
            "secrets": [self._item_to_dict(i) for i in self.secrets],
            "summary": {
                "total_env_vars": len(self.env_vars),
                "total_config_files": len(self.config_files),
                "total_feature_flags": len(self.feature_flags),
                "total_constants": len(self.constants),
                "total_api_urls": len(self.api_urls),
                "total_secrets": len(self.secrets),
            },
        }

    def _item_to_dict(self, item: ConfigItem) -> dict:
        return {
            "name": item.name,
            "type": item.type,
            "file": item.file,
            "line": item.line,
            "value": item.value,
            "default_value": item.default_value,
            "used_by": item.used_by,
            "is_secret": item.is_secret,
            "description": item.description,
        }


class ConfigScanner:
    """Universal configuration surface scanner."""

    # Environment variable patterns (per language)
    ENV_VAR_PATTERNS = {
        "dart": [
            # Platform.environment['VAR_NAME']
            (re.compile(r"Platform\.environment\s*\[['\"](\w+)['\"]\]"), False),
            # String.fromEnvironment('VAR_NAME')
            (re.compile(r"String\.fromEnvironment\s*\(['\"](\w+)['\"]\)"), False),
            # bool.fromEnvironment('VAR_NAME')
            (re.compile(r"bool\.fromEnvironment\s*\(['\"](\w+)['\"]\)"), False),
        ],
        "python": [
            # os.environ['VAR_NAME'] or os.environ.get('VAR_NAME')
            (re.compile(r"os\.environ\s*\[['\"](\w+)['\"]\]"), False),
            (re.compile(r"os\.environ\.get\s*\(['\"](\w+)['\"]"), False),
            # os.getenv('VAR_NAME')
            (re.compile(r"os\.getenv\s*\(['\"](\w+)['\"]"), False),
        ],
        "javascript": [
            # process.env.VAR_NAME or process.env['VAR_NAME']
            (re.compile(r"process\.env\.(\w+)"), False),
            (re.compile(r"process\.env\s*\[['\"](\w+)['\"]\]"), False),
        ],
        "typescript": [
            # process.env.VAR_NAME or process.env['VAR_NAME']
            (re.compile(r"process\.env\.(\w+)"), False),
            (re.compile(r"process\.env\s*\[['\"](\w+)['\"]\]"), False),
        ],
        "java": [
            # System.getenv("VAR_NAME")
            (re.compile(r"System\.getenv\s*\(['\"](\w+)['\"]\)"), False),
            # System.getProperty("VAR_NAME")
            (re.compile(r"System\.getProperty\s*\(['\"](\w+)['\"]\)"), False),
        ],
        "go": [
            # os.Getenv("VAR_NAME")
            (re.compile(r"os\.Getenv\s*\(['\"](\w+)['\"]\)"), False),
            # os.LookupEnv("VAR_NAME")
            (re.compile(r"os\.LookupEnv\s*\(['\"](\w+)['\"]\)"), False),
        ],
        "rust": [
            # std::env::var("VAR_NAME")
            (re.compile(r"std::env::var\s*\(['\"](\w+)['\"]\)"), False),
            # env!("VAR_NAME")
            (re.compile(r"env!\s*\(['\"](\w+)['\"]\)"), True),  # Compile-time
        ],
        "ruby": [
            # ENV['VAR_NAME'] or ENV["VAR_NAME"]
            (re.compile(r"ENV\s*\[['\"](\w+)['\"]\]"), False),
        ],
        "php": [
            # getenv('VAR_NAME')
            (re.compile(r"getenv\s*\(['\"](\w+)['\"]\)"), False),
            # $_ENV['VAR_NAME']
            (re.compile(r"\$_ENV\s*\[['\"](\w+)['\"]\]"), False),
        ],
    }

    # Config file patterns
    CONFIG_FILE_PATTERNS = [
        r"\.env$",
        r"\.env\.\w+$",
        r"config\.\w+$",
        r"settings\.\w+$",
        r"appsettings\.\w+$",
        r"configuration\.\w+$",
        r"properties$",
        r"\.ini$",
        r"\.toml$",
        r"\.yaml$",
        r"\.yml$",
        r"\.json$",
        r"database\.yml$",
        r"credentials\.json$",
    ]

    # Feature flag patterns
    FEATURE_FLAG_PATTERNS = [
        # Boolean variables with ENABLE/DISABLE/DEBUG/FEATURE prefix
        (re.compile(r"(?:const|final|static|let|var)\s+(?:bool\s+)?(ENABLE_\w+|DISABLE_\w+|DEBUG_\w+|FEATURE_\w+|IS_\w+_ENABLED)\s*=\s*(true|false)", re.IGNORECASE), "bool"),
        # Feature flags object/class
        (re.compile(r"(?:FeatureFlags?|FeatureToggles?|FeatureSwitches?)\s*[\.\{]"), "class"),
        # Conditional checks
        (re.compile(r"if\s*\(?\s*(?:isEnabled|isFeatureEnabled|hasFeature|featureEnabled)\s*\("), "check"),
    ]

    # Hardcoded constant patterns
    CONSTANT_PATTERNS = [
        # const/const/final with ALL_CAPS name
        (re.compile(r"(?:const|final|static)\s+(?:String|int|double|num)\s+([A-Z][A-Z0-9_]{2,})\s*=\s*['\"]"), "string"),
        # const/const/final with ALL_CAPS name (numeric)
        (re.compile(r"(?:const|final|static)\s+(?:int|double|num)\s+([A-Z][A-Z0-9_]{2,})\s*=\s*\d+"), "numeric"),
    ]

    # API URL patterns
    API_URL_PATTERNS = [
        # URL strings
        (re.compile(r"(?:base[_]?[Uu]rl|api[_]?[Uu]rl|endpoint|BASE_URL|API_URL)\s*[:=]\s*['\"]?(https?://[^'\"\s]+)['\"]?"), "url"),
        # API endpoints
        (re.compile(r"['\"]/(api|v1|v2|graphql|rest)/[^'\"]*['\"]"), "path"),
    ]

    # Secret detection patterns
    SECRET_PATTERNS = [
        re.compile(r"(?:api[_]?key|secret|password|token|credential|auth)[-_]?(?:key|secret|password|token|credential)?", re.IGNORECASE),
        re.compile(r"(?:private[_]?key|access[_]?key|client[_]?secret)", re.IGNORECASE),
    ]

    # Language detection
    EXTENSION_TO_LANG = {
        ".dart": "dart",
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
    }

    def scan_all(self, root: Path, files: list[Path]) -> ConfigReport:
        """Scan all files for configuration items."""
        report = ConfigReport()

        # Scan config files
        config_files = self._find_config_files(root, files)
        for cf in config_files:
            report.config_files.append(ConfigItem(
                name=cf.name,
                type="config_file",
                file=str(cf),
                line=0,
                metadata={"size": cf.stat().st_size if cf.exists() else 0},
            ))

        # Scan source files for config usage
        for f in files:
            lang = self.EXTENSION_TO_LANG.get(f.suffix.lower())
            if not lang:
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            file_str = str(f)
            items = self._scan_content(content, file_str, lang)
            self._merge_items(report, items)

        return report

    def scan_file(self, file_path: Path) -> list[ConfigItem]:
        """Scan a single file for configuration items."""
        lang = self.EXTENSION_TO_LANG.get(file_path.suffix.lower())
        if not lang:
            return []

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        return self._scan_content(content, str(file_path), lang)

    def _find_config_files(self, root: Path, files: list[Path]) -> list[Path]:
        """Find configuration files in the project."""
        config_files = []

        for f in files:
            filename = f.name.lower()
            for pattern in self.CONFIG_FILE_PATTERNS:
                if re.search(pattern, filename):
                    config_files.append(f)
                    break

        # Also check root for .env files
        for p in root.glob(".env*"):
            if p.is_file() and p not in config_files:
                config_files.append(p)

        return sorted(set(config_files))

    def _scan_content(self, content: str, file_str: str, language: str) -> list[ConfigItem]:
        """Scan file content for configuration items."""
        items = []
        lines = content.split("\n")

        # Scan for environment variables
        env_patterns = self.ENV_VAR_PATTERNS.get(language, [])
        for line_num, line in enumerate(lines, 1):
            for pattern, is_compile_time in env_patterns:
                for match in pattern.finditer(line):
                    name = match.group(1)
                    items.append(ConfigItem(
                        name=name,
                        type="env_var",
                        file=file_str,
                        line=line_num,
                        is_secret=any(sp.search(name) for sp in self.SECRET_PATTERNS),
                        metadata={"is_compile_time": is_compile_time},
                    ))

        # Scan for feature flags
        for line_num, line in enumerate(lines, 1):
            for pattern, flag_type in self.FEATURE_FLAG_PATTERNS:
                match = pattern.search(line)
                if match:
                    name = match.group(1) if match.lastindex else f"feature_flag_{line_num}"
                    # Extract default value if present
                    default = None
                    default_match = re.search(r"=\s*(true|false)", line, re.IGNORECASE)
                    if default_match:
                        default = default_match.group(1).lower()
                    items.append(ConfigItem(
                        name=name,
                        type="feature_flag",
                        file=file_str,
                        line=line_num,
                        default_value=default,
                        metadata={"flag_type": flag_type},
                    ))

        # Scan for hardcoded constants
        for line_num, line in enumerate(lines, 1):
            for pattern, const_type in self.CONSTANT_PATTERNS:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    # Skip common noise constants
                    if name in ("OK", "ERROR", "NULL", "TRUE", "FALSE", "DEBUG"):
                        continue
                    # Extract value
                    value_match = re.search(r"=\s*['\"]?([^'\"]+?)['\"]?\s*;", line)
                    value = value_match.group(1) if value_match else None
                    items.append(ConfigItem(
                        name=name,
                        type="constant",
                        file=file_str,
                        line=line_num,
                        value=value,
                        metadata={"const_type": const_type},
                    ))

        # Scan for API URLs
        for line_num, line in enumerate(lines, 1):
            for pattern, url_type in self.API_URL_PATTERNS:
                match = pattern.search(line)
                if match:
                    url = match.group(1) if match.lastindex else match.group(0)
                    items.append(ConfigItem(
                        name=url[:50],
                        type="api_url",
                        file=file_str,
                        line=line_num,
                        value=url,
                        metadata={"url_type": url_type},
                    ))

        return items

    def _merge_items(self, report: ConfigReport, items: list[ConfigItem]):
        """Merge scanned items into report, avoiding duplicates."""
        seen = set()

        for item in items:
            key = (item.name, item.type, item.file, item.line)
            if key in seen:
                continue
            seen.add(key)

            if item.type == "env_var":
                report.env_vars.append(item)
            elif item.type == "feature_flag":
                report.feature_flags.append(item)
            elif item.type == "constant":
                report.constants.append(item)
            elif item.type == "api_url":
                report.api_urls.append(item)

            if item.is_secret:
                report.secrets.append(item)
