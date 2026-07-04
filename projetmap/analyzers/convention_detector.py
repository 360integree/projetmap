"""Convention Detector — Universal detection of codebase conventions.

Works across all languages and frameworks by detecting:
- File naming conventions (snake_case, camelCase, PascalCase, kebab-case)
- Class/type naming conventions
- Directory structure patterns (feature-based, layer-based, flat)
- Import style (relative, absolute, barrel exports)
- Error handling patterns
- Comment/documentation patterns
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConventionReport:
    """Complete convention analysis report."""
    file_naming: dict = field(default_factory=dict)
    class_naming: dict = field(default_factory=dict)
    directory_structure: dict = field(default_factory=dict)
    import_style: dict = field(default_factory=dict)
    error_handling: dict = field(default_factory=dict)
    comment_style: dict = field(default_factory=dict)
    detected_frameworks: list[str] = field(default_factory=list)
    detected_architecture: str | None = None

    def to_dict(self) -> dict:
        return {
            "file_naming": self.file_naming,
            "class_naming": self.class_naming,
            "directory_structure": self.directory_structure,
            "import_style": self.import_style,
            "error_handling": self.error_handling,
            "comment_style": self.comment_style,
            "detected_frameworks": self.detected_frameworks,
            "detected_architecture": self.detected_architecture,
        }


class ConventionDetector:
    """Universal convention detector."""

    # File naming convention patterns
    FILE_NAMING_PATTERNS = {
        "snake_case": re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*\.\w+$"),
        "camelCase": re.compile(r"^[a-z][a-zA-Z0-9]*\.\w+$"),
        "PascalCase": re.compile(r"^[A-Z][a-zA-Z0-9]*\.\w+$"),
        "kebab-case": re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*\.\w+$"),
        "SCREAMING_SNAKE": re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*\.\w+$"),
    }

    # Class/type naming patterns
    CLASS_NAMING_PATTERNS = {
        "PascalCase": re.compile(r"(?:class|struct|enum|interface|type|typedef)\s+([A-Z][a-zA-Z0-9]*)"),
        "snake_case": re.compile(r"(?:class|struct|enum|interface|type|typedef)\s+([a-z][a-z0-9_]*)"),
        "I_Prefix": re.compile(r"(?:class|interface|type)\s+(I[A-Z][a-zA-Z0-9]*)"),
        "_Prefix": re.compile(r"(?:class|struct)\s+(_[A-Z][a-zA-Z0-9]*)"),
    }

    # Import style patterns
    IMPORT_PATTERNS = {
        "relative": {
            "dart": re.compile(r"import\s+['\"](?:\.\./|\./)"),
            "python": re.compile(r"from\s+\."),
            "javascript": re.compile(r"from\s+['\"](?:\.\./|\./)"),
            "typescript": re.compile(r"from\s+['\"](?:\.\./|\./)"),
            "go": re.compile(r"import\s+['\"](?:\.\.?/)"),
        },
        "absolute": {
            "dart": re.compile(r"import\s+['\"](?:package:|/)"),
            "python": re.compile(r"(?:from|import)\s+(?!\.)"),
            "javascript": re.compile(r"from\s+['\"](?:@|/)"),
            "typescript": re.compile(r"from\s+['\"](?:@|/)"),
            "java": re.compile(r"import\s+(?:com\.|org\.|net\.|java\.|javax\.)"),
            "go": re.compile(r"import\s+['\"](?![\. ])"),
        },
        "barrel": {
            "dart": re.compile(r"import\s+['\"](?:.+/)?(?:index| barrel)['\"]"),
            "typescript": re.compile(r"from\s+['\"](?:.+/)?(?:index| barrel)['\"]"),
        },
    }

    # Error handling patterns
    ERROR_HANDLING_PATTERNS = {
        "try_catch": re.compile(r"(?:try|catch|finally|throw|except|raise|panic)"),
        "result_type": re.compile(r"(?:Result|Either|Option|Maybe|Optional)"),
        "error_boundary": re.compile(r"(?:ErrorBoundary|ErrorWidget|componentDidCatch)"),
        "error_callback": re.compile(r"(?:onError|error_handler|errorHandler)"),
        "option_type": re.compile(r"(?:None|Some|Nothing|Unit)"),
    }

    # Comment style patterns
    COMMENT_PATTERNS = {
        "docstrings": re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''),
        "jsdoc": re.compile(r"/\*\*[\s\S]*?\*/"),
        "dartdoc": re.compile(r"///"),
        "block_comments": re.compile(r"/\*[\s\S]*?\*/"),
        "line_comments": re.compile(r"(?://|#|--|%|;)\s*\w"),
        "todo_fixme": re.compile(r"(?:TODO|FIXME|HACK|XXX|OPTIMIZE)"),
    }

    # Architecture detection patterns
    ARCHITECTURE_PATTERNS = {
        "layered": {
            "signals": ["controller", "service", "repository", "model", "view"],
            "dirs": ["controllers", "services", "repositories", "models", "views"],
        },
        "clean_architecture": {
            "signals": ["entities", "use_cases", "interface_adapters", "frameworks", "domain", "data", "presentation"],
            "dirs": ["domain", "data", "presentation", "core"],
        },
        "feature_based": {
            "signals": ["auth", "profile", "settings", "home", "diagnostic"],
            "dirs": ["features", "modules", "screens"],
        },
        "mvc": {
            "signals": ["model", "view", "controller"],
            "dirs": ["models", "views", "controllers"],
        },
        "mvvm": {
            "signals": ["model", "view", "viewmodel"],
            "dirs": ["models", "views", "viewmodels"],
        },
        "microservices": {
            "signals": ["service", "api", "gateway", "docker", "k8s"],
            "dirs": ["services", "api", "gateway", "deploy"],
        },
    }

    # Framework detection patterns
    FRAMEWORK_DETECTION_PATTERNS = {
        "flutter": re.compile(r"(?:import\s+['\"]package:flutter/|Flutter|runApp\s*\()"),
        "react": re.compile(r"(?:import\s+React|from\s+['\"]react['\"]|jsx|JSX)"),
        "nextjs": re.compile(r"(?:import\s+['\"]next/|getServerSideProps|getStaticProps)"),
        "vue": re.compile(r"(?:import\s+Vue|from\s+['\"]vue['\"]|\.vue$)"),
        "angular": re.compile(r"(?:@Component|@Injectable|@NgModule|from\s+['\"]@angular)"),
        "django": re.compile(r"(?:from\s+django|import\s+django|urlpatterns)"),
        "flask": re.compile(r"(?:from\s+flask|import\s+Flask)"),
        "fastapi": re.compile(r"(?:from\s+fastapi|import\s+FastAPI)"),
        "spring": re.compile(r"(?:@SpringBootApplication|@RestController|@Service)"),
        "rails": re.compile(r"(?:Rails\.application|ActiveRecord|ActiveController)"),
        "express": re.compile(r"(?:require\(['\"]express['\"]|from\s+['\"]express)"),
        "gin": re.compile(r"(?:gin\.Default|gin\.New)"),
        "actix": re.compile(r"(?:actix_web|#[actix_web::main])"),
        "laravel": re.compile(r"(?:Laravel|Illuminate|Route::)"),
    }

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

    def detect_all(self, root: Path, files: list[Path]) -> ConventionReport:
        """Detect all conventions in the project."""
        report = ConventionReport()

        # Collect data for analysis
        file_names = []
        class_names = []
        import_styles = Counter()
        error_handling = Counter()
        comment_styles = Counter()
        directory_depth = defaultdict(int)
        frameworks = set()

        for f in files:
            lang = self.EXTENSION_TO_LANG.get(f.suffix.lower())

            # File naming
            file_names.append((f.name, lang))

            # Directory structure
            try:
                rel = f.relative_to(root)
                parts = rel.parts
                if len(parts) > 1:
                    directory_depth[parts[0]] += 1
                    if len(parts) > 2:
                        directory_depth[f"{parts[0]}/{parts[1]}"] += 1
            except ValueError:
                pass

            if not lang:
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Class naming
            for pattern_name, pattern in self.CLASS_NAMING_PATTERNS.items():
                for match in pattern.finditer(content):
                    class_names.append((match.group(1), pattern_name))

            # Import style
            for style, lang_patterns in self.IMPORT_PATTERNS.items():
                if lang in lang_patterns:
                    if lang_patterns[lang].search(content):
                        import_styles[style] += 1

            # Error handling
            for pattern_name, pattern in self.ERROR_HANDLING_PATTERNS.items():
                if pattern.search(content):
                    error_handling[pattern_name] += 1

            # Comment style
            for pattern_name, pattern in self.COMMENT_PATTERNS.items():
                if pattern.search(content):
                    comment_styles[pattern_name] += 1

            # Framework detection
            for framework, pattern in self.FRAMEWORK_DETECTION_PATTERNS.items():
                if pattern.search(content):
                    frameworks.add(framework)

        # Analyze file naming conventions
        report.file_naming = self._analyze_file_naming(file_names)

        # Analyze class naming conventions
        report.class_naming = self._analyze_class_naming(class_names)

        # Analyze directory structure
        report.directory_structure = self._analyze_directory_structure(
            directory_depth, root, files
        )

        # Analyze import style
        report.import_style = dict(import_styles)

        # Analyze error handling
        report.error_handling = dict(error_handling)

        # Analyze comment style
        report.comment_style = dict(comment_styles)

        # Set detected frameworks
        report.detected_frameworks = sorted(frameworks)

        # Detect architecture
        report.detected_architecture = self._detect_architecture(
            directory_depth, class_names, frameworks
        )

        return report

    def _analyze_file_naming(self, file_names: list[tuple]) -> dict:
        """Analyze file naming conventions."""
        counters = {
            "snake_case": 0,
            "camelCase": 0,
            "PascalCase": 0,
            "kebab-case": 0,
            "SCREAMING_SNAKE": 0,
            "other": 0,
        }

        examples = defaultdict(list)

        for filename, lang in file_names:
            matched = False
            for convention, pattern in self.FILE_NAMING_PATTERNS.items():
                if pattern.match(filename):
                    counters[convention] += 1
                    if len(examples[convention]) < 3:
                        examples[convention].append(filename)
                    matched = True
                    break
            if not matched:
                counters["other"] += 1

        # Determine dominant convention
        dominant = max(counters, key=counters.get) if counters else "unknown"

        return {
            "dominant": dominant,
            "counts": counters,
            "examples": dict(examples),
            "total_files": sum(counters.values()),
        }

    def _analyze_class_naming(self, class_names: list[tuple]) -> dict:
        """Analyze class naming conventions."""
        counters = Counter()
        examples = defaultdict(list)

        for name, convention in class_names:
            counters[convention] += 1
            if len(examples[convention]) < 3:
                examples[convention].append(name)

        dominant = counters.most_common(1)[0][0] if counters else "unknown"

        return {
            "dominant": dominant,
            "counts": dict(counters),
            "examples": dict(examples),
            "total_classes": sum(counters.values()),
        }

    def _analyze_directory_structure(
        self, depth_counts: dict, root: Path, files: list[Path],
    ) -> dict:
        """Analyze directory structure patterns."""
        # Get top-level directories
        top_dirs = set()
        for f in files:
            try:
                rel = f.relative_to(root)
                if len(rel.parts) > 1:
                    top_dirs.add(rel.parts[0])
            except ValueError:
                pass

        # Get second-level directories
        second_dirs = defaultdict(int)
        for f in files:
            try:
                rel = f.relative_to(root)
                if len(rel.parts) > 2:
                    key = f"{rel.parts[0]}/{rel.parts[1]}"
                    second_dirs[key] += 1
            except ValueError:
                pass

        # Detect structure pattern
        structure_pattern = "flat"
        top_dirs_lower = {d.lower() for d in top_dirs}

        if top_dirs_lower & {"lib", "src", "app"}:
            structure_pattern = "layered"
        if top_dirs_lower & {"features", "modules", "screens", "pages"}:
            structure_pattern = "feature_based"
        if top_dirs_lower & {"services", "api", "gateway", "deploy"}:
            structure_pattern = "microservices"

        return {
            "pattern": structure_pattern,
            "top_level_dirs": sorted(top_dirs),
            "second_level_dirs": dict(sorted(second_dirs.items(), key=lambda x: -x[1])[:15]),
            "depth_distribution": dict(depth_counts),
        }

    def _detect_architecture(
        self, dir_counts: dict, class_names: list[tuple], frameworks: set[str],
    ) -> str | None:
        """Detect architectural pattern."""
        all_dirs = " ".join(dir_counts.keys()).lower()
        all_classes = " ".join(name for name, _ in class_names).lower()

        for arch_name, arch_info in self.ARCHITECTURE_PATTERNS.items():
            # Check directories
            dir_matches = sum(1 for d in arch_info["dirs"] if d in all_dirs)
            # Check class names
            class_matches = sum(1 for s in arch_info["signals"] if s in all_classes)

            if dir_matches >= 2 or class_matches >= 2:
                return arch_name

        # Framework-specific defaults
        if "flutter" in frameworks:
            return "feature_based"
        if "django" in frameworks:
            return "mvc"
        if "spring" in frameworks:
            return "layered"

        return None
