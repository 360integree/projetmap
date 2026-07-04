"""Entry Point Detector — Universal detection of application entry points.

Works across all languages and frameworks by detecting:
- main() functions (any language)
- Application initialization (app startup, server listen)
- Route/screen initialization (what the user sees first)
- Service initialization (what gets started at boot)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Initialization:
    """A service/component initialized at startup."""
    name: str
    line: int
    type: str  # database, auth, provider, router, logger, cache, etc.
    config_refs: list[str] = field(default_factory=list)
    is_async: bool = False


@dataclass
class EntryPoint:
    """An application entry point."""
    file: str
    line: int
    language: str
    entry_type: str  # main, server, app, cli, test, worker
    initializations: list[Initialization] = field(default_factory=list)
    initial_route: str | None = None
    home_screen: str | None = None
    exports: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class EntryDetector:
    """Detect application entry points across languages and frameworks."""

    # Language-specific entry point patterns
    ENTRY_PATTERNS = {
        "dart": [
            # Flutter app entry
            (re.compile(r"void\s+main\s*\(\s*\)"), "app", "Flutter/Dart app"),
            (re.compile(r"void\s+main\s*\(\s*\)\s*(?:async|=>)"), "app", "Async Flutter/Dart app"),
            (re.compile(r"runApp\s*\("), "app", "Flutter runApp call"),
            (re.compile(r"GetMaterialApp\s*\(|MaterialApp\s*\(|CupertinoApp\s*\("), "app", "Flutter app widget"),
        ],
        "python": [
            # Python entry
            (re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]"), "main", "Python main guard"),
            (re.compile(r"app\s*=\s*(?:Flask|FastAPI|Django)\s*\("), "server", "Python web server"),
            (re.compile(r"def\s+main\s*\("), "main", "Python main function"),
            (re.compile(r"manage\.py", re.IGNORECASE), "cli", "Django management"),
        ],
        "javascript": [
            # JS/Node entry
            (re.compile(r"app\.listen\s*\("), "server", "Node.js HTTP server"),
            (re.compile(r"createServer\s*\("), "server", "Node.js server creation"),
            (re.compile(r"express\s*\("), "server", "Express app"),
            (re.compile(r"next\s*\("), "server", "Next.js entry"),
            (re.compile(r"export\s+default\s+function"), "export", "Default export"),
        ],
        "typescript": [
            # TS entry (same as JS)
            (re.compile(r"app\.listen\s*\("), "server", "Node.js HTTP server"),
            (re.compile(r"createServer\s*\("), "server", "Node.js server creation"),
            (re.compile(r"express\s*\("), "server", "Express app"),
            (re.compile(r"next\s*\("), "server", "Next.js entry"),
            (re.compile(r"export\s+default\s+function"), "export", "Default export"),
        ],
        "java": [
            # Java entry
            (re.compile(r"public\s+static\s+void\s+main\s*\("), "main", "Java main method"),
            (re.compile(r"@SpringBootApplication"), "server", "Spring Boot app"),
            (re.compile(r"public\s+static\s+void\s+main\s*\(\s*String\s*\["), "main", "Java main with args"),
        ],
        "go": [
            # Go entry
            (re.compile(r"func\s+main\s*\("), "main", "Go main function"),
            (re.compile(r"package\s+main"), "package", "Go main package"),
            (re.compile(r"http\.ListenAndServe\s*\("), "server", "Go HTTP server"),
            (re.compile(r"gin\.Default\s*\(\)|echo\.New\s*\(\)"), "server", "Go web framework"),
        ],
        "rust": [
            # Rust entry
            (re.compile(r"fn\s+main\s*\("), "main", "Rust main function"),
            (re.compile(r"#\[tokio::main\]"), "async_main", "Async Rust main"),
            (re.compile(r"actix_web|axum|warp"), "server", "Rust web framework"),
        ],
        "ruby": [
            # Ruby entry
            (re.compile(r"Rails\.application\.run"), "server", "Rails server"),
            (re.compile(r"Sinatra::Application"), "server", "Sinatra app"),
            (re.compile(r"if\s+__FILE__\s*==\s*__FILE__"), "main", "Ruby main guard"),
        ],
        "php": [
            # PHP entry
            (re.compile(r"public\s+function\s+index\s*\("), "controller", "PHP controller"),
            (re.compile(r"Route::|->get\(|->post\("), "route", "PHP route definition"),
            (re.compile(r"Laravel|Symfony"), "framework", "PHP framework"),
        ],
    }

    # File patterns that are typically entry points
    ENTRY_FILE_PATTERNS = {
        "dart": ["main.dart", "app.dart"],
        "python": ["main.py", "app.py", "manage.py", "__main__.py", "wsgi.py", "asgi.py"],
        "javascript": ["index.js", "server.js", "app.js", "main.js"],
        "typescript": ["index.ts", "server.ts", "app.ts", "main.ts"],
        "java": ["Main.java", "Application.java", "App.java"],
        "go": ["main.go"],
        "rust": ["main.rs", "lib.rs"],
        "ruby": ["config.ru", "application.rb"],
        "php": ["index.php", "public/index.php"],
    }

    # Initialization patterns (what gets started at boot)
    INIT_PATTERNS = [
        # Databases
        (re.compile(r"(?:Supabase|Firebase|MongoDB|PostgreSQL|MySQL|SQLite)\s*\.?\s*(?:initialize|init|configure|client)"), "database"),
        (re.compile(r"(?:Drift|Hive|SharedPreferences|GetStorage)\s*\.?\s*(?:open|init)"), "local_storage"),
        # Auth
        (re.compile(r"(?:Auth|Authentication|Login|Session)\s*\.?\s*(?:initialize|init|configure)"), "auth"),
        # State management
        (re.compile(r"(?:ProviderScope|MultiProvider|BlocProvider|GetBuilder|ChangeNotifierProvider)"), "state_management"),
        # Router
        (re.compile(r"(?:GoRouter|GoRoute|AutoRoute|Navigator|Router)\s*\("), "router"),
        (re.compile(r"(?:routes|router)\s*[:=]"), "router"),
        # Logging
        (re.compile(r"(?:Logger|Log|logging)\s*\.?\s*(?:init|configure|setup)"), "logger"),
        # Cache
        (re.compile(r"(?:Cache|CacheManager|Redis)\s*\.?\s*(?:init|configure)"), "cache"),
        # API
        (re.compile(r"(?:api|API|baseUrl|base_url)\s*[:=]"), "api"),
        # HTTP client
        (re.compile(r"(?:HttpClient|Dio|axios|fetch|http\.Client)"), "http_client"),
        # WebSocket
        (re.compile(r"(?:WebSocket|Socket|socket\.io)"), "websocket"),
        # Background tasks
        (re.compile(r"(?:Background|Worker|Job|Queue)\s*\.?\s*(?:start|init)"), "background"),
    ]

    # Framework initialization patterns
    FRAMEWORK_INIT_PATTERNS = {
        "flutter": [
            (re.compile(r"WidgetsFlutterBinding\s*\.?\s*ensureInitialized"), "flutter_binding"),
            (re.compile(r"SystemChrome\s*\."), "system_ui"),
            (re.compile(r"FlutterError\s*\.?\s*onError"), "error_handler"),
        ],
        "react": [
            (re.compile(r"ReactDOM\s*\.?\s*render|createRoot"), "react_root"),
            (re.compile(r"StrictMode"), "strict_mode"),
        ],
        "django": [
            (re.compile(r"django\.setup\s*\("), "django_setup"),
            (re.compile(r"WSGI_APPLICATION|ASGI_APPLICATION"), "wsgi"),
        ],
        "spring": [
            (re.compile(r"@SpringBootApplication|@EnableAutoConfiguration"), "spring_boot"),
            (re.compile(r"SpringApplication\s*\.?\s*run"), "spring_run"),
        ],
    }

    # Language detection from file extension
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

    def detect_all(self, root: Path, files: list[Path]) -> list[EntryPoint]:
        """Detect all entry points in the project."""
        entry_points = []

        for f in files:
            lang = self._detect_language(f)
            if not lang:
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Check if file is a known entry file
            is_entry_file = self._is_entry_file(f, lang)

            # Check content for entry patterns
            points = self._scan_content(content, f, lang, is_entry_file)
            entry_points.extend(points)

        return entry_points

    def detect_file(self, file_path: Path) -> EntryPoint | None:
        """Detect entry point in a single file."""
        lang = self._detect_language(file_path)
        if not lang:
            return None

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        is_entry_file = self._is_entry_file(file_path, lang)
        points = self._scan_content(content, file_path, lang, is_entry_file)
        return points[0] if points else None

    def _detect_language(self, file_path: Path) -> str | None:
        """Detect language from file extension."""
        return self.EXTENSION_TO_LANG.get(file_path.suffix.lower())

    def _is_entry_file(self, file_path: Path, language: str) -> bool:
        """Check if file matches known entry point patterns."""
        filename = file_path.name.lower()
        patterns = self.ENTRY_FILE_PATTERNS.get(language, [])
        return any(filename == p.lower() for p in patterns)

    def _scan_content(
        self, content: str, file_path: Path, language: str, is_entry_file: bool,
    ) -> list[EntryPoint]:
        """Scan file content for entry point patterns."""
        entry_points = []
        patterns = self.ENTRY_PATTERNS.get(language, [])

        lines = content.split("\n")
        file_str = str(file_path)

        for line_num, line in enumerate(lines, 1):
            for pattern, entry_type, description in patterns:
                if pattern.search(line):
                    # Found an entry point
                    inits = self._find_initializations(lines, line_num)

                    entry = EntryPoint(
                        file=file_str,
                        line=line_num,
                        language=language,
                        entry_type=entry_type,
                        initializations=inits,
                        metadata={
                            "description": description,
                            "is_entry_file": is_entry_file,
                            "line_content": line.strip()[:100],
                        },
                    )

                    # Check for framework-specific initialization
                    framework_inits = self._find_framework_inits(lines, line_num)
                    entry.initializations.extend(framework_inits)

                    # Check for route/screen initialization
                    route_info = self._find_initial_route(lines, line_num)
                    if route_info:
                        entry.initial_route = route_info.get("route")
                        entry.home_screen = route_info.get("screen")

                    entry_points.append(entry)
                    break  # One entry point per line

        return entry_points

    def _find_initializations(self, lines: list[str], start_line: int) -> list[Initialization]:
        """Find service initializations near an entry point."""
        inits = []
        # Look within 50 lines after entry point
        search_range = min(start_line + 50, len(lines))

        for i in range(start_line - 1, search_range):
            line = lines[i]
            for pattern, init_type in self.INIT_PATTERNS:
                if pattern.search(line):
                    # Extract the initialization name
                    init_name = self._extract_init_name(line, init_type)
                    if init_name:
                        inits.append(Initialization(
                            name=init_name,
                            line=i + 1,
                            type=init_type,
                            config_refs=self._extract_config_refs(line),
                            is_async="async" in line or "await" in line,
                        ))

        return inits

    def _find_framework_inits(self, lines: list[str], start_line: int) -> list[Initialization]:
        """Find framework-specific initializations."""
        inits = []
        search_range = min(start_line + 30, len(lines))

        for i in range(start_line - 1, search_range):
            line = lines[i]
            for framework, patterns in self.FRAMEWORK_INIT_PATTERNS.items():
                for pattern, init_type in patterns:
                    if pattern.search(line):
                        inits.append(Initialization(
                            name=init_type,
                            line=i + 1,
                            type=f"framework_{framework}",
                            is_async=False,
                        ))

        return inits

    def _find_initial_route(self, lines: list[str], start_line: int) -> dict | None:
        """Find initial route/home screen declaration."""
        search_range = min(start_line + 40, len(lines))

        for i in range(start_line - 1, search_range):
            line = lines[i]

            # Flutter: initialRoute: '/path'
            m = re.search(r"initialRoute\s*:\s*['\"]([^'\"]+)['\"]", line)
            if m:
                return {"route": m.group(1)}

            # Flutter: home: ScreenName()
            m = re.search(r"home\s*:\s*(\w+)\s*\(", line)
            if m:
                return {"screen": m.group(1)}

            # React: <Route path="/" element={<Home />} />
            m = re.search(r"path\s*=\s*['\"]([^'\"]+)['\"]", line)
            if m and m.group(1) == "/":
                # Look for component
                m2 = re.search(r"element\s*=\s*\{?<(\w+)", line)
                if m2:
                    return {"route": "/", "screen": m2.group(1)}

        return None

    def _extract_init_name(self, line: str, init_type: str) -> str | None:
        """Extract the name of what's being initialized."""
        # Try to extract class/variable name
        patterns = [
            r"(\w+)\s*\.?\s*(?:initialize|init|configure|setup)",
            r"(?:var|final|const|let)\s+(\w+)\s*=",
            r"(\w+)\s*\(",
        ]
        for p in patterns:
            m = re.search(p, line)
            if m:
                return m.group(1)
        return init_type

    def _extract_config_refs(self, line: str) -> list[str]:
        """Extract configuration references from a line."""
        refs = []
        # Look for env vars
        env_refs = re.findall(r"(?:Platform\.environment|process\.env|os\.environ)\[['\"](\w+)['\"]\]", line)
        refs.extend(env_refs)
        # Look for config references
        config_refs = re.findall(r"(?:config|Config|CONFIG)\s*\.?\s*(\w+)", line)
        refs.extend(config_refs)
        return refs

    def to_dict(self, entry_points: list[EntryPoint]) -> dict:
        """Serialize entry points to dict."""
        return {
            "entry_points": [
                {
                    "file": ep.file,
                    "line": ep.line,
                    "language": ep.language,
                    "entry_type": ep.entry_type,
                    "initializations": [
                        {
                            "name": init.name,
                            "line": init.line,
                            "type": init.type,
                            "config_refs": init.config_refs,
                            "is_async": init.is_async,
                        }
                        for init in ep.initializations
                    ],
                    "initial_route": ep.initial_route,
                    "home_screen": ep.home_screen,
                    "metadata": ep.metadata,
                }
                for ep in entry_points
            ],
            "summary": {
                "total_entry_points": len(entry_points),
                "by_type": self._count_by_type(entry_points),
                "by_language": self._count_by_language(entry_points),
            },
        }

    def _count_by_type(self, entry_points: list[EntryPoint]) -> dict[str, int]:
        counts = {}
        for ep in entry_points:
            counts[ep.entry_type] = counts.get(ep.entry_type, 0) + 1
        return counts

    def _count_by_language(self, entry_points: list[EntryPoint]) -> dict[str, int]:
        counts = {}
        for ep in entry_points:
            counts[ep.language] = counts.get(ep.language, 0) + 1
        return counts
