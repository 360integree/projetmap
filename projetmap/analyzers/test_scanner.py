"""Test Coverage Scanner — Universal detection of test coverage.

Works across all languages and frameworks by detecting:
- Test files and their naming conventions
- Which modules have tests
- Which modules don't (risk assessment)
- Test patterns (mocking, fixtures, assertions)
- Test count per module
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestFile:
    """A detected test file."""
    file: str
    test_framework: str
    test_count: int
    tested_modules: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ModuleCoverage:
    """Coverage information for a source module."""
    source_file: str
    has_test: bool
    test_file: str | None = None
    test_count: int = 0
    coverage_estimate: str = "unknown"  # none, low, medium, high, full
    risk_level: str = "unknown"  # low, medium, high, critical


@dataclass
class TestCoverageReport:
    """Complete test coverage analysis report."""
    test_files: list[TestFile] = field(default_factory=list)
    module_coverage: list[ModuleCoverage] = field(default_factory=list)
    untested_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "test_files": [
                {
                    "file": tf.file,
                    "test_framework": tf.test_framework,
                    "test_count": tf.test_count,
                    "tested_modules": tf.tested_modules,
                    "patterns": tf.patterns,
                }
                for tf in self.test_files
            ],
            "module_coverage": [
                {
                    "source_file": mc.source_file,
                    "has_test": mc.has_test,
                    "test_file": mc.test_file,
                    "test_count": mc.test_count,
                    "coverage_estimate": mc.coverage_estimate,
                    "risk_level": mc.risk_level,
                }
                for mc in self.module_coverage
            ],
            "untested_modules": self.untested_modules,
            "summary": {
                "total_test_files": len(self.test_files),
                "total_test_cases": sum(tf.test_count for tf in self.test_files),
                "total_source_files": len(self.module_coverage),
                "tested_modules": sum(1 for mc in self.module_coverage if mc.has_test),
                "untested_modules": len(self.untested_modules),
                "coverage_percentage": self._calc_coverage_pct(),
                "high_risk_modules": sum(1 for mc in self.module_coverage if mc.risk_level in ("high", "critical")),
            },
        }

    def _calc_coverage_pct(self) -> float:
        if not self.module_coverage:
            return 0.0
        tested = sum(1 for mc in self.module_coverage if mc.has_test)
        return round(tested / len(self.module_coverage) * 100, 1)


class TestCoverageScanner:
    """Universal test coverage scanner."""

    # Test file patterns per language
    TEST_FILE_PATTERNS = {
        "dart": {
            "pattern": re.compile(r"_test\.dart$"),
            "frameworks": {
                "flutter_test": re.compile(r"import\s+['\"]package:flutter_test"),
                "mockito": re.compile(r"import\s+['\"]package:mockito"),
                "mocktail": re.compile(r"import\s+['\"]package:mocktail"),
                "bloc_test": re.compile(r"import\s+['\"]package:bloc_test"),
            },
        },
        "python": {
            "pattern": re.compile(r"(?:test_\w+\.py|_test\.py)$"),
            "frameworks": {
                "pytest": re.compile(r"(?:import\s+pytest|@pytest\.|def\s+test_)"),
                "unittest": re.compile(r"(?:import\s+unittest|class\s+\w+\(unittest\.TestCase)"),
            },
        },
        "javascript": {
            "pattern": re.compile(r"(?:\.test\.|\.spec\.)(?:js|jsx|ts|tsx)$"),
            "frameworks": {
                "jest": re.compile(r"(?:describe|it|test|expect|jest\.)"),
                "mocha": re.compile(r"(?:describe|it|expect|assert)"),
                "vitest": re.compile(r"(?:describe|it|test|expect|vi\.)"),
                "cypress": re.compile(r"(?:cy\.|describe|it|expect)"),
            },
        },
        "typescript": {
            "pattern": re.compile(r"(?:\.test\.|\.spec\.)(?:ts|tsx)$"),
            "frameworks": {
                "jest": re.compile(r"(?:describe|it|test|expect|jest\.)"),
                "vitest": re.compile(r"(?:describe|it|test|expect|vi\.)"),
            },
        },
        "java": {
            "pattern": re.compile(r"(?:Test\.java|Tests\.java)$"),
            "frameworks": {
                "junit4": re.compile(r"(?:@Test|@Before|@After|import\s+org\.junit)"),
                "junit5": re.compile(r"(?:@Test|@BeforeEach|@AfterEach|import\s+org\.junit\.jupiter)"),
                "mockito": re.compile(r"(?:mock\(|when\(|verify\()"),
            },
        },
        "go": {
            "pattern": re.compile(r"_test\.go$"),
            "frameworks": {
                "testing": re.compile(r"import\s+\"testing\""),
                "testify": re.compile(r"(?:assert\.|require\.)"),
            },
        },
        "rust": {
            "pattern": re.compile(r"(?:_test\.rs$|tests/)"),
            "frameworks": {
                "built_in": re.compile(r"#\[test\]"),
                "rstest": re.compile(r"#\[rstest\]"),
            },
        },
        "ruby": {
            "pattern": re.compile(r"_test\.rb$|_spec\.rb$"),
            "frameworks": {
                "minitest": re.compile(r"(?:class\s+\w+<\s*Test::Unit|def\s+test_)"),
                "rspec": re.compile(r"(?:describe|context|it|expect)"),
            },
        },
        "php": {
            "pattern": re.compile(r"Test\.php$"),
            "frameworks": {
                "phpunit": re.compile(r"(?:class\s+\w+Tests?\s+extends|function\s+test)"),
            },
        },
    }

    # Test case counting patterns
    TEST_CASE_PATTERNS = {
        "dart": [
            re.compile(r'test\s*\(["\']'),
            re.compile(r'testWidgets\s*\(["\']'),
        ],
        "python": [
            re.compile(r"def\s+test_\w+"),
            re.compile(r"def\s+test\s*\("),
        ],
        "javascript": [
            re.compile(r'(?:it|test)\s*\(["\']'),
        ],
        "typescript": [
            re.compile(r'(?:it|test)\s*\(["\']'),
        ],
        "java": [
            re.compile(r"@Test"),
        ],
        "go": [
            re.compile(r"func\s+Test\w+"),
        ],
        "rust": [
            re.compile(r"#\[test\]"),
        ],
        "ruby": [
            re.compile(r"def\s+test_\w+"),
            re.compile(r"it\s+['\"]"),
        ],
        "php": [
            re.compile(r"function\s+test\w+"),
        ],
    }

    # Test patterns (mocking, fixtures, etc.)
    TEST_PATTERN_DETECTORS = {
        "mocking": [
            re.compile(r"(?:mock|Mock|Mockito|mocktail|mock\(|when\(|verify\()"),
            re.compile(r"(?:@Mock|@InjectMocks|@Spy)"),
        ],
        "fixtures": [
            re.compile(r"(?:fixture|setUp|setUpAll|tearDown|beforeEach|afterEach)"),
            re.compile(r"(?:@Before|@After|@BeforeEach|@AfterEach)"),
        ],
        "assertions": [
            re.compile(r"(?:expect|assert|assertEquals|assertThat|assertThrows)"),
            re.compile(r"(?:assert\.\w+|require\.\w+)"),
        ],
        "snapshot": [
            re.compile(r"(?:toMatchSnapshot|toMatchInlineSnapshot|expectLater)"),
        ],
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

    def scan_all(self, root: Path, files: list[Path]) -> TestCoverageReport:
        """Scan all files for test coverage."""
        report = TestCoverageReport()

        source_files = []
        test_files_raw = []

        for f in files:
            lang = self.EXTENSION_TO_LANG.get(f.suffix.lower())
            if not lang:
                continue

            test_info = self.TEST_FILE_PATTERNS.get(lang)
            if not test_info:
                continue

            if test_info["pattern"].search(f.name):
                test_files_raw.append((f, lang))
            else:
                source_files.append((f, lang))

        # Process test files
        for f, lang in test_files_raw:
            test_file = self._analyze_test_file(f, lang)
            if test_file:
                report.test_files.append(test_file)

        # Map source files to tests
        source_strs = {str(f): lang for f, lang in source_files}
        test_strs = {tf.file: tf for tf in report.test_files}

        for source_file, lang in source_files:
            coverage = self._map_coverage(source_file, lang, report.test_files, root)
            report.module_coverage.append(coverage)

            if not coverage.has_test:
                report.untested_modules.append(str(source_file))

        return report

    def _analyze_test_file(self, file_path: Path, language: str) -> TestFile | None:
        """Analyze a single test file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        # Detect test framework
        test_info = self.TEST_FILE_PATTERNS.get(language, {})
        frameworks = test_info.get("frameworks", {})
        detected_framework = "unknown"
        for framework, pattern in frameworks.items():
            if pattern.search(content):
                detected_framework = framework
                break

        # Count test cases
        test_count = 0
        patterns = []
        for p in self.TEST_CASE_PATTERNS.get(language, []):
            matches = p.findall(content)
            test_count += len(matches)

        # Detect test patterns
        for pattern_name, pattern_list in self.TEST_PATTERN_DETECTORS.items():
            for p in pattern_list:
                if p.search(content):
                    patterns.append(pattern_name)
                    break

        # Map tested modules (basic heuristic)
        tested_modules = self._find_tested_modules(content, language)

        return TestFile(
            file=str(file_path),
            test_framework=detected_framework,
            test_count=test_count,
            tested_modules=tested_modules,
            patterns=list(set(patterns)),
            metadata={"language": language, "line_count": content.count("\n") + 1},
        )

    def _find_tested_modules(self, content: str, language: str) -> list[str]:
        """Find which modules a test file tests."""
        modules = []

        # Look for imports (most test files import what they test)
        import_patterns = {
            "dart": re.compile(r"import\s+['\"]([^'\"]+)['\"]"),
            "python": re.compile(r"(?:from|import)\s+([\w.]+)"),
            "javascript": re.compile(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]"),
            "typescript": re.compile(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]"),
            "java": re.compile(r"import\s+([\w.]+)"),
            "go": re.compile(r"import\s+['\"]([^'\"]+)['\"]"),
            "rust": re.compile(r"use\s+([\w:]+)"),
            "ruby": re.compile(r"require['\"]([^'\"]+)['\"]"),
            "php": re.compile(r"(?:use|require|include)\s+['\"]([^'\"]+)['\"]"),
        }

        pattern = import_patterns.get(language)
        if pattern:
            for match in pattern.finditer(content):
                import_path = match.group(1)
                # Filter out standard library imports
                if not self._is_stdlib(import_path, language):
                    modules.append(import_path)

        return modules

    def _is_stdlib(self, import_path: str, language: str) -> bool:
        """Check if an import is from the standard library."""
        stdlib_prefixes = {
            "dart": ["dart:", "package:flutter/", "package:collection/", "package:meta/"],
            "python": ["os", "sys", "re", "json", "typing", "pathlib", "collections", "unittest", "pytest"],
            "javascript": ["node:", "fs", "path", "http", "https", "crypto"],
            "typescript": ["node:", "fs", "path", "http", "https", "crypto"],
            "java": ["java.", "javax.", "org.junit"],
            "go": ["fmt", "os", "io", "net", "strings", "testing"],
            "rust": ["std::", "core::", "alloc::"],
            "ruby": ["ruby", "test/unit"],
            "php": ["PHP", "PHPUnit"],
        }

        prefixes = stdlib_prefixes.get(language, [])
        return any(import_path.startswith(p) for p in prefixes)

    def _map_coverage(
        self, source_file: Path, language: str,
        test_files: list[TestFile], root: Path,
    ) -> ModuleCoverage:
        """Map source file to its test coverage."""
        source_name = source_file.stem  # e.g., "user_repository"
        source_str = str(source_file)

        # Look for matching test files
        for tf in test_files:
            tf_path = Path(tf.file)
            # Match by name similarity
            if (source_name in tf_path.stem or
                source_name.replace("_", "") in tf_path.stem.replace("_", "")):
                # Found a matching test file
                return ModuleCoverage(
                    source_file=source_str,
                    has_test=True,
                    test_file=tf.file,
                    test_count=tf.test_count,
                    coverage_estimate=self._estimate_coverage(tf.test_count),
                    risk_level="low" if tf.test_count > 5 else "medium",
                )

        # No test found
        return ModuleCoverage(
            source_file=source_str,
            has_test=False,
            test_count=0,
            coverage_estimate="none",
            risk_level=self._assess_risk(source_file),
        )

    def _estimate_coverage(self, test_count: int) -> str:
        """Estimate coverage level based on test count."""
        if test_count == 0:
            return "none"
        elif test_count <= 2:
            return "low"
        elif test_count <= 5:
            return "medium"
        elif test_count <= 10:
            return "high"
        else:
            return "full"

    def _assess_risk(self, source_file: Path) -> str:
        """Assess risk level for untested modules."""
        # Simple heuristic: critical files are higher risk
        filename = source_file.name.lower()

        critical_patterns = [
            "auth", "user", "payment", "security", "database",
            "repository", "service", "orchestrator", "engine",
        ]

        if any(p in filename for p in critical_patterns):
            return "high"

        medium_patterns = ["provider", "controller", "bloc", "screen", "page"]
        if any(p in filename for p in medium_patterns):
            return "medium"

        return "low"
