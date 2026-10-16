# Coding & Debugging

## Problem selection
Pick by level and pattern gap, not at random. Prefer problems with a natural
follow-up that changes the optimal approach (for example, streaming input,
memory cap, concurrent access, or k → general k).

## Pattern coverage list
Track coverage per pattern rather than raw problem counts.

1. Two pointers / sliding window (fixed and variable)
2. Hashing and prefix sums (subarray-sum family)
3. Binary search on answer / monotonic predicate
4. Stack: monotonic stack, parsing, expression evaluation
5. Heap / top-k / k-way merge / scheduling
6. Intervals: sort + sweep, merge, meeting rooms
7. Trees: DFS return-value design, LCA, serialization, BST invariants
8. Graphs: BFS shortest path, topological sort, union-find, Dijkstra, 0-1 BFS
9. Backtracking with pruning
10. DP: 1D/2D, knapsack, interval DP, bitmask DP, DP on trees
11. Greedy with exchange-argument proof
12. Tries and string algorithms (KMP / rolling hash at senior+)
13. Design-a-class: LRU/LFU, rate limiter, iterator, time-based KV store
14. Concurrency (senior+ infra): bounded blocking queue, reader-writer lock, worker pool

## Interviewer script
1. State the problem plus one example. Withhold edge cases unless asked.
2. Let them propose an approach before coding. If they jump straight to code, note it.
3. While they code, stay quiet unless asked; note bugs silently.
4. After "done": "Walk me through this input" (pick one that hits their bug, if any).
5. Follow-up: change one constraint to break their approach.

## Hint ladder (each step costs points)
1. Question nudge: "What's expensive in your current approach?"
2. Direction: "Is there an ordering you could exploit?"
3. Technique: "Consider a monotonic stack."
4. Partial structure: the invariant to maintain.

## Debugging mode
Give 20–60 lines of realistic code with 1–3 bugs from this mix: off-by-one,
mutation aliasing, wrong equality/hash, unhandled empty input, race condition,
integer overflow (in fixed-width languages), resource leak, incorrect async
error handling. Alternatively give a production incident: symptoms, a
dashboard summary, and a log excerpt. Score hypothesis-driven narrowing over
lucky spotting.
