# ruff: noqa: F821
# executor is a bare name matching the GoroutineSpawn heuristic set
# {"executor", "pool", "futures", "thread_pool"}. Parsed as AST only, never executed.
def f(fn):
    executor.submit(fn)
