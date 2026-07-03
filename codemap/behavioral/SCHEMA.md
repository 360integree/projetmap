# Behavioral Data Schema (v1)

This is the **contract** between language-specific extractors and the shared Python analyzers.

Any language extractor that produces a JSON file matching this schema gets dead code detection, state flow analysis, and lifecycle health checks for free.

## Top-Level Fields

```json
{
  "call_graph": { ... },
  "state_mutations": [ ... ],
  "widget_lifecycle": [ ... ],
  "providers": [ ... ],
  "entry_points": [ ... ],
  "change_notifiers": [ ... ],
  "file_count": 301
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `call_graph` | `Map<String, CallEntry>` | ✅ | Functions/methods and what they call |
| `state_mutations` | `List<Mutation>` | ✅ | State-changing operations |
| `widget_lifecycle` | `List<LifecycleComponent>` | ✅ | Components with lifecycle hooks |
| `providers` | `List<Provider>` | ✅ | State providers/dependency injection |
| `entry_points` | `List<EntryPoint>` | ✅ | Application entry points |
| `change_notifiers` | `List<StateContainer>` | ✅ | State container classes |
| `file_count` | `int` | ✅ | Number of files analyzed |

---

## `call_graph` — Function Call Relationships

```json
{
  "copilot_orchestrator.dart::conductInterview": {
    "calls": [
      { "target": "generateConversationTurn", "line": 245 },
      { "target": "addSurface", "line": 312 }
    ],
    "called_by": [
      "generative_diagnostic_screen.dart::_startInterview"
    ]
  }
}
```

### `CallEntry`

| Field | Type | Description |
|-------|------|-------------|
| key | `String` | `"file_path::className.methodName"` or `"file_path::functionName"` |
| `calls` | `List<CallTarget>` | What this function calls |
| `called_by` | `List<String>` | Who calls this function (built by Python analyzer) |

### `CallTarget`

| Field | Type | Description |
|-------|------|-------------|
| `target` | `String` | Name of the called function/method |
| `line` | `int` | Line number of the call site |

**Key format:** `"relative/file.dart::ClassName.methodName"` — the `::` separator distinguishes project code from external dependencies.

---

## `state_mutations` — State-Changing Operations

```json
{
  "type": "setState",
  "file": "generative_diagnostic_screen.dart",
  "line": 166,
  "enclosing_method": "_startInterview",
  "enclosing_class": "_GenerativeDiagnosticScreenState",
  "context": "initState"
}
```

### `Mutation`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `String` | ✅ | Mutation type (see below) |
| `file` | `String` | ✅ | Relative file path |
| `line` | `int` | ✅ | Line number |
| `enclosing_method` | `String` | ✅ | Method containing the mutation |
| `enclosing_class` | `String` | | Class containing the mutation |
| `context` | `String` | | Lifecycle context (`initState`, `dispose`, `other`) |

### Mutation Types (Cross-Framework)

| Type | Flutter | React | Vue | Python/Django |
|------|---------|-------|-----|---------------|
| `setState` | `setState((){})` | `setState()` / `useState setter` | `this.x = val` | N/A |
| `notifyListeners` | `notifyListeners()` | N/A | N/A | N/A |
| `setValue` | `dataModel.setValue()` | N/A | N/A | N/A |
| `addListener` | `addListener()` | `useEffect(() => {})` | `watch()` | `connect()` / `subscribe()` |
| `removeListener` | `removeListener()` | cleanup return | N/A | `disconnect()` / `unsubscribe()` |
| `emit` | N/A | `emitter.emit()` | `$emit()` | `signal.send()` |
| `update` | N/A | N/A | N/A | `query.update()` / `save()` |

Extractors should map their framework's primitives to these types.

---

## `widget_lifecycle` — Component Lifecycle Hooks

```json
{
  "widget": "GenerativeDiagnosticScreen",
  "file": "generative_diagnostic_screen.dart",
  "line": 42,
  "extends": "ConsumerStatefulWidget",
  "overrides": ["initState", "dispose", "didChangeDependencies", "build"]
}
```

### `LifecycleComponent`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `widget` | `String` | ✅ | Component/class name |
| `file` | `String` | ✅ | Relative file path |
| `line` | `int` | ✅ | Definition line |
| `extends` | `String` | | Parent class |
| `overrides` | `List<String>` | ✅ | Lifecycle hooks overridden |

### Lifecycle Hook Names (Cross-Framework)

| Category | Flutter | React | Vue | Angular |
|----------|---------|-------|-----|---------|
| init | `initState` | `componentDidMount` / `useEffect` | `mounted` | `ngOnInit` |
| dispose | `dispose` | `componentWillUnmount` / cleanup | `beforeUnmount` | `ngOnDestroy` |
| update | `didUpdateWidget` | `componentDidUpdate` | `updated` | `ngOnChanges` |
| build | `build` | `render` | `render` / `template` | `template` |

---

## `providers` — State Providers / DI

```json
{
  "type": "StateNotifierProvider",
  "file": "copilot_state.dart",
  "line": 45,
  "notifier_class": "CopilotNotifier",
  "state_type": "CopilotPhase",
  "enclosing_class": ""
}
```

### `Provider`

| Field | Type | Description |
|-------|------|-------------|
| `type` | `String` | Provider type (e.g., `StateNotifierProvider`, `Provider`) |
| `file` | `String` | Relative file path |
| `line` | `int` | Declaration line |
| `notifier_class` | `String` | Class that manages this state |
| `state_type` | `String` | Type of state managed |
| `enclosing_class` | `String` | Enclosing class (if method-level) |

---

## `entry_points` — Application Entry Points

```json
{
  "file": "main.dart",
  "line": 1,
  "type": "main"
}
```

### `EntryPoint`

| Field | Type | Description |
|-------|------|-------------|
| `file` | `String` | Relative file path |
| `line` | `int` | Line number |
| `type` | `String` | Entry type (`main`, `handler`, `init`, `route`) |

---

## `change_notifiers` — State Container Classes

```json
{
  "class": "CopilotOrchestrator",
  "file": "copilot_orchestrator.dart",
  "line": 50,
  "extends": "ChangeNotifier",
  "mixins": []
}
```

### `StateContainer`

| Field | Type | Description |
|-------|------|-------------|
| `class` | `String` | Class name |
| `file` | `String` | Relative file path |
| `line` | `int` | Definition line |
| `extends` | `String` | Parent class |
| `mixins` | `List<String>` | Mixed-in classes |

---

## Writing a New Language Extractor

To add support for a new language:

1. **Create the extractor** (e.g., `js_behavioral_extractor.ts`)
2. **Map language concepts to the schema:**
   - Functions/methods → `call_graph` entries
   - State mutations → `state_mutations` with appropriate `type`
   - Components with lifecycle → `widget_lifecycle` (rename field if needed)
   - DI/service providers → `providers`
   - Entry points → `entry_points`
3. **Output `behavioral_data.json`** matching this schema
4. The Python analyzers work automatically — no changes needed

### Minimal Extractor (Pseudocode)

```python
def extract(project_root):
    return {
        "call_graph": build_call_graph(project_root),
        "state_mutations": find_mutations(project_root),
        "widget_lifecycle": find_lifecycle_components(project_root),
        "providers": find_providers(project_root),
        "entry_points": find_entry_points(project_root),
        "change_notifiers": find_state_containers(project_root),
        "file_count": count_files(project_root),
    }
```
