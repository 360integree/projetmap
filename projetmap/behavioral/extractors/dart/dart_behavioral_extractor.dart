/// Graphify Behavioral Extractor — AST-based analysis for Dart codebases.
///
/// Usage:
///   dart run dart_behavioral_extractor.dart <project_root> [output_path]
///
/// Extracts: call graph, state mutations, widget lifecycle, providers, entry points.
/// Output: JSON file consumed by Python behavioral analyzers.

import 'dart:convert';
import 'dart:io';

import 'package:analyzer/dart/analysis/analysis_context_collection.dart';
import 'package:analyzer/dart/analysis/results.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/visitor.dart';
import 'package:path/path.dart' as p;

void main(List<String> args) {
  if (args.isEmpty) {
    stderr.writeln(
      'Usage: dart run dart_behavioral_extractor.dart <project_root> [output_path]',
    );
    exit(1);
  }

  final projectRoot = args[0];
  final outputPath = args.length > 1 ? args[1] : 'behavioral_data.json';

  stdout.writeln('🔍 Scanning $projectRoot ...');

  final extractor = BehavioralExtractor(projectRoot);
  final data = extractor.extract();

  final jsonStr = const JsonEncoder.withIndent('  ').convert(data);
  File(outputPath).writeAsStringSync(jsonStr);

  stdout.writeln(
    '✅ Extracted behavioral data for ${data['file_count']} files → $outputPath',
  );
}

// ---------------------------------------------------------------------------
// Main extractor
// ---------------------------------------------------------------------------

class BehavioralExtractor {
  final String projectRoot;

  BehavioralExtractor(this.projectRoot);

  Map<String, dynamic> extract() {
    final collection = AnalysisContextCollection(
      includedPaths: [projectRoot],
    );

    final callGraph = <String, dynamic>{};
    final stateMutations = <Map<String, dynamic>>[];
    final widgetLifecycle = <Map<String, dynamic>>[];
    final providers = <Map<String, dynamic>>[];
    final entryPoints = <Map<String, dynamic>>[];
    final changeNotifiers = <Map<String, dynamic>>[];
    var fileCount = 0;

    for (final context in collection.contexts) {
      // Scan all .dart files under the context root
      final rootDir = Directory(context.contextRoot.root.path);
      if (!rootDir.existsSync()) continue;

      final dartFiles = rootDir
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))
          .where((f) => !f.path.contains('.g.dart'))
          .where((f) => !f.path.contains('.freezed.dart'))
          .where((f) => !f.path.contains('.part.dart'));

      for (final file in dartFiles) {
        final filePath = file.path;
        if (!context.contextRoot.isAnalyzed(filePath)) continue;

        try {
          final parsed = context.currentSession.getParsedUnit(filePath);
          if (parsed case ParsedUnitResult()) {
            final cu = parsed.unit;
            fileCount++;

            final visitor = _BehavioralVisitor(
              filePath: p.relative(filePath, from: projectRoot),
            );
            cu.accept(visitor);

            // Merge results
            for (final entry in visitor.callGraph.entries) {
              final key = entry.key;
              final value = entry.value;
              if (callGraph.containsKey(key)) {
                final existing = callGraph[key] as Map<String, dynamic>;
                final existingCalls =
                    (existing['calls'] as List).cast<Map<String, dynamic>>();
                final newCalls =
                    (value['calls'] as List).cast<Map<String, dynamic>>();
                for (final c in newCalls) {
                  if (!existingCalls
                      .any((e) => e['target'] == c['target'])) {
                    existingCalls.add(c);
                  }
                }
              } else {
                callGraph[key] = value;
              }
            }

            stateMutations.addAll(visitor.stateMutations);
            widgetLifecycle.addAll(visitor.widgetLifecycle);
            providers.addAll(visitor.providers);
            entryPoints.addAll(visitor.entryPoints);
            changeNotifiers.addAll(visitor.changeNotifiers);
          }
        } catch (e) {
          stderr.writeln('⚠️  Skipping ${p.basename(filePath)}: $e');
        }
      }
    }

    // Build reverse call graph (called_by)
    _buildReverseCallGraph(callGraph);

    collection.dispose();

    return {
      'call_graph': callGraph,
      'state_mutations': stateMutations,
      'widget_lifecycle': widgetLifecycle,
      'providers': providers,
      'entry_points': entryPoints,
      'change_notifiers': changeNotifiers,
      'file_count': fileCount,
    };
  }

  void _buildReverseCallGraph(Map<String, dynamic> callGraph) {
    // Collect all reverse edges first, then apply (avoid concurrent modification)
    final reverseEdges = <String, List<String>>{};

    for (final entry in callGraph.entries) {
      final caller = entry.key;
      final data = entry.value as Map<String, dynamic>;
      final calls = (data['calls'] as List).cast<Map<String, dynamic>>();

      for (final call in calls) {
        final target = call['target'] as String;
        reverseEdges.putIfAbsent(target, () => []).add(caller);
      }
    }

    // Apply reverse edges
    for (final entry in reverseEdges.entries) {
      final target = entry.key;
      final callers = entry.value;
      if (!callGraph.containsKey(target)) {
        callGraph[target] = {'calls': <Map<String, dynamic>>[], 'called_by': <String>[]};
      }
      final targetData = callGraph[target] as Map<String, dynamic>;
      final calledBy = (targetData['called_by'] as List).cast<String>();
      for (final caller in callers) {
        if (!calledBy.contains(caller)) {
          calledBy.add(caller);
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// AST visitor
// ---------------------------------------------------------------------------

class _BehavioralVisitor extends RecursiveAstVisitor<void> {
  final String filePath;

  final Map<String, dynamic> callGraph = {};
  final List<Map<String, dynamic>> stateMutations = [];
  final List<Map<String, dynamic>> widgetLifecycle = [];
  final List<Map<String, dynamic>> providers = [];
  final List<Map<String, dynamic>> entryPoints = [];
  final List<Map<String, dynamic>> changeNotifiers = [];

  String _currentClass = '';
  String _currentMethod = '';
  bool _isInInitState = false;
  bool _isInDispose = false;

  _BehavioralVisitor({required this.filePath});

  String _methodKey() {
    final classPrefix = _currentClass.isNotEmpty ? '$_currentClass.' : '';
    return '$filePath::$classPrefix$_currentMethod';
  }

  void _ensureCallGraphEntry() {
    final key = _methodKey();
    if (!callGraph.containsKey(key)) {
      callGraph[key] = {
        'calls': <Map<String, dynamic>>[],
        'called_by': <String>[],
      };
    }
  }

  // ── Class declarations ──────────────────────────────────────────────

  @override
  void visitClassDeclaration(ClassDeclaration node) {
    final className = node.name.lexeme;
    final superclass = node.extendsClause?.superclass.name2.lexeme;
    final mixins = node.withClause?.mixinTypes
            .map((m) => m.name2.lexeme)
            .toList() ??
        [];

    _currentClass = className;

    // Detect ChangeNotifier subclasses
    final isChangeNotifier = superclass == 'ChangeNotifier' ||
        superclass == 'StateNotifier' ||
        mixins.contains('ChangeNotifier');
    if (isChangeNotifier) {
      changeNotifiers.add({
        'class': className,
        'file': filePath,
        'line': node.name.offset,
        'extends': superclass,
        'mixins': mixins,
      });
    }

    // Detect Flutter widgets
    const widgetSuperclasses = {
      'StatefulWidget',
      'ConsumerStatefulWidget',
      'ConsumerWidget',
      'StatelessWidget',
      'State',
    };
    final isWidget = widgetSuperclasses.contains(superclass);

    if (isWidget) {
      final overrides = <String>[];
      for (final member in node.members) {
        if (member is MethodDeclaration) {
          final name = member.name.lexeme;
          const lifecycle = {
            'initState',
            'dispose',
            'didChangeDependencies',
            'build',
            'didUpdateWidget',
          };
          if (lifecycle.contains(name)) {
            overrides.add(name);
          }
        }
      }

      widgetLifecycle.add({
        'widget': className,
        'file': filePath,
        'line': node.name.offset,
        'extends': superclass,
        'overrides': overrides,
      });
    }

    super.visitClassDeclaration(node);
    _currentClass = '';
  }

  // ── Method declarations ─────────────────────────────────────────────

  @override
  void visitMethodDeclaration(MethodDeclaration node) {
    _currentMethod = node.name.lexeme;
    _ensureCallGraphEntry();

    if (_currentMethod == 'initState') _isInInitState = true;
    if (_currentMethod == 'dispose') _isInDispose = true;

    super.visitMethodDeclaration(node);

    _isInInitState = false;
    _isInDispose = false;
    _currentMethod = '';
  }

  // ── Top-level function declarations ─────────────────────────────────

  @override
  void visitFunctionDeclaration(FunctionDeclaration node) {
    _currentMethod = node.name.lexeme;
    _currentClass = '';
    _ensureCallGraphEntry();

    if (_currentMethod == 'main') {
      entryPoints.add({
        'file': filePath,
        'line': node.name.offset,
        'type': 'main',
      });
    }

    super.visitFunctionDeclaration(node);
    _currentMethod = '';
  }

  // ── Function/method invocations ─────────────────────────────────────

  @override
  void visitMethodInvocation(MethodInvocation node) {
    _recordCall(node.methodName.name, node.offset);
    _detectStateMutation(node);
    super.visitMethodInvocation(node);
  }

  @override
  void visitInstanceCreationExpression(InstanceCreationExpression node) {
    final typeName = node.constructorName.type.name2.lexeme;
    _recordCall(typeName, node.offset);

    // Detect provider-like constructors
    if (_isProviderType(typeName)) {
      _extractProvider(node);
    }

    super.visitInstanceCreationExpression(node);
  }

  void _recordCall(String targetName, int offset) {
    if (_currentMethod.isEmpty) return;
    _ensureCallGraphEntry();

    final calls =
        (callGraph[_methodKey()]!['calls'] as List).cast<Map<String, dynamic>>();

    // Deduplicate by target+line
    final alreadyExists =
        calls.any((c) => c['target'] == targetName && c['line'] == offset);
    if (!alreadyExists) {
      calls.add({'target': targetName, 'line': offset});
    }
  }

  // ── State mutation detection ────────────────────────────────────────

  void _detectStateMutation(MethodInvocation node) {
    final name = node.methodName.name;

    const mutationTypes = {
      'setState',
      'notifyListeners',
      'setValue',
      'addListener',
      'removeListener',
    };
    if (!mutationTypes.contains(name)) return;

    final mutation = <String, dynamic>{
      'type': name,
      'file': filePath,
      'line': node.offset,
      'enclosing_method': _currentMethod,
      'enclosing_class': _currentClass,
    };

    // Add lifecycle context for listeners
    if (name == 'addListener' || name == 'removeListener') {
      mutation['context'] = _isInInitState
          ? 'initState'
          : (_isInDispose ? 'dispose' : 'other');
    }

    stateMutations.add(mutation);
  }

  // ── Provider detection ──────────────────────────────────────────────

  bool _isProviderType(String typeName) {
    return typeName.contains('Provider') || typeName.contains('Notifier');
  }

  void _extractProvider(InstanceCreationExpression node) {
    final typeArgs = node.constructorName.type.typeArguments;
    String notifierClass = '';
    String stateType = '';

    if (typeArgs != null && typeArgs.arguments.isNotEmpty) {
      final firstArg = typeArgs.arguments.first;
      if (firstArg case NamedType namedType) {
        notifierClass = namedType.name2.lexeme;
      }
      if (typeArgs.arguments.length > 1) {
        final secondArg = typeArgs.arguments[1];
        if (secondArg case NamedType namedType) {
          stateType = namedType.name2.lexeme;
        }
      }
    }

    providers.add({
      'type': node.constructorName.type.name2.lexeme,
      'file': filePath,
      'line': node.offset,
      'notifier_class': notifierClass,
      'state_type': stateType,
      'enclosing_class': _currentClass,
    });
  }
}
