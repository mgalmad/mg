# Rubrics

Scores: **1** not demonstrated / incorrect · **2** partially, needed heavy help ·
**3** solid at target level · **4** clearly above target level.

Verdict mapping (average across dimensions, but any single 1 on a must-have
dimension caps the verdict at Lean No Hire):
- ≥3.5 Strong Hire · 3.0–3.4 Hire · 2.6–2.9 Lean Hire · 2.0–2.5 Lean No Hire · <2.0 No Hire
- Each hint taken: −0.25 on Problem Solving (coding) or Design Depth (design).

## Coding
| Dimension | Must-have | 3 looks like |
|---|---|---|
| Problem understanding | yes | Restates the problem, asks about edge cases and input bounds before coding |
| Problem solving | yes | Reaches optimal or near-optimal with justified trade-offs; explores brute force first only briefly |
| Code quality | yes | Correct, idiomatic, readable names, no dead code, handles edges |
| Verification | | Traces an example by hand, identifies own bugs, proposes tests |
| Complexity analysis | | Correct time and space, including hidden costs (slicing, hashing, recursion stack) |
| Communication | | Narrates intent; the interviewer is never guessing |

## System design
| Dimension | Must-have | 3 looks like |
|---|---|---|
| Requirements & scoping | yes | Functional plus non-functional requirements, numeric estimates, explicit out-of-scope |
| High-level architecture | yes | Coherent components, clear data flow, APIs defined |
| Data modeling | | Schema, access patterns drive the store choice, partition key reasoning |
| Scale & performance | | Back-of-envelope numbers drive decisions; identifies the bottleneck |
| Reliability & failure modes | | Replication, retries/idempotency, degradation, blast radius |
| Design depth | yes | One component taken to production depth on request |
| Trade-off articulation | | Names the alternatives and why rejected; consistency vs. availability made explicit |

## Behavioral
| Dimension | Must-have | 3 looks like |
|---|---|---|
| Ownership / scope | yes | Scope matches level (team for senior, multi-team/org for staff+) |
| Specificity | yes | Concrete actions by *them*, real numbers, named trade-offs |
| Judgment under ambiguity | | Explains why that decision, what else they considered |
| Conflict & influence | | Disagrees with substance, influences without authority, preserves relationships |
| Self-awareness | | Real failures, real lessons, evidence the lesson changed later behavior |

## Level expectations (what changes going up)
- **Mid (L4)**: correct, working solutions with modest guidance; design limited to well-known patterns.
- **Senior (L5)**: drives the interview; optimal coding unaided; design covers scale and failure with numbers; team-scope stories.
- **Staff (L6)**: frames the problem and changes it when warranted; design shows operational maturity (migrations, cost, org impact); cross-team influence stories with lasting mechanisms.
- **Principal (L7+)**: multi-year technical direction; designs that anticipate second-order effects (ecosystem, org structure, regulatory); stories about changing how an organization works.
