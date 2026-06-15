---
tag: quality-pairing-astroid
author: matt-peter
category: gotcha
created_at: 2026-06-15T15:41:05Z
identity: quality-pairing-astroid-20260615T154105-matt-peter
tier: draft
---

When extending test-target pairing in gaze-py's O1 quality pipeline with Astroid (Strategy 3), the most critical correctness detail is BFS graph lookup safety: callee FQNs that were never themselves callers have no key in the adjacency dict, so every BFS lookup must use graph.get(fqn, set()) not graph[fqn]. Without this guard, any function that is called-but-never-calls produces a KeyError that silently aborts the BFS. Additionally, _process_test_func() is the actual pair_to_targets() call site (not assess() directly) — any new parameter like astroid_graph must be threaded through _process_test_func's signature, not just added to assess().
