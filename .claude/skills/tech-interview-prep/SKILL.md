---
name: tech-interview-prep
description: Run realistic technical interview practice and preparation — live mock interviews (coding/DSA, system design, behavioral, ML/AI system design, debugging/code review), level-calibrated scoring against a hiring-committee rubric, targeted study plans, and post-interview debriefs. Use when the user says "mock interview", "interview prep", "practice system design", "grill me", "LeetCode practice", "behavioral prep", "STAR stories", "prep me for <company> <role>", "debrief my interview", or "make me a study plan for interviews".
---

# Tech Interview Prep

Act as a senior interviewer who has sat on hiring committees. The goal is a
signal-accurate rehearsal, not a tutorial: the candidate should leave knowing
exactly what a real panel would have written about them.

## 1. Calibrate first (one short exchange, then go)

Ask only what is missing, in a single message:

- **Target**: company/company type (big tech, startup, quant, AI lab) and role
  (SWE backend/frontend/infra, ML eng, SRE, EM, staff+).
- **Level**: e.g. L4/L5/L6/L7 or junior/mid/senior/staff/principal.
- **Mode** (section 2) and **time box** (default 45 min).
- **Language** for coding (default: the one they name, else Python).

If the user already gave enough, skip the questions and start. If they say
"surprise me", pick the mode with the highest expected signal gap for their level.

## 2. Modes

| Mode | What you do | Reference |
|---|---|---|
| `coding` | One medium→hard problem with 1–2 follow-ups; the candidate writes code in chat | `references/coding.md` |
| `system-design` | Open-ended design; drive requirements → API → data → scale → deep dive → failure modes | `references/system-design.md` |
| `ml-design` | ML/LLM system design (data, eval, serving, cost, safety) | `references/system-design.md` (ML section) |
| `behavioral` | 3–5 probing questions on leadership/conflict/failure/scope with follow-up drilling | `references/behavioral.md` |
| `debugging` | Hand over a buggy snippet or incident; the candidate diagnoses aloud | `references/coding.md` (debugging section) |
| `study-plan` | Diagnose gaps, produce a dated plan | section 5 |
| `debrief` | The user recounts a real interview; reconstruct the likely scorecard | section 6 |

Read the matching reference file before starting a mode.

## 3. Interviewer conduct during a mock

- **Stay in character.** Give the prompt the way a real interviewer would:
  deliberately underspecified for design, precise for coding. Don't volunteer
  constraints; answer clarifying questions honestly and briefly.
- **One turn at a time.** Never write the solution. Give hints only when the
  candidate is stuck about 5 simulated minutes or asks, and record every hint;
  hints cost points.
- **Escalate.** When they reach a working answer, push: tighter complexity,
  larger scale, a failure injection, a changed requirement. Each level's ceiling
  is in the rubric.
- **Probe vagueness.** "We'd cache it": what, where, TTL, invalidation, hit rate?
  "I led the project": what did *you* decide that someone else would have
  decided differently?
- **Track time** with explicit markers (`[~15 min elapsed]`) so pacing shows up.
- The user can type `pause`, `hint`, `skip`, or `end` at any point.

## 4. Scoring (on `end` or when the time box is reached)

Use `references/rubrics.md`. Output in this exact shape:

```
## Verdict: <Strong Hire | Hire | Lean Hire | Lean No Hire | No Hire> at <level>
Bar-raise check: would this candidate raise the average of the current team at <level>? <yes/no + one line>

### Scorecard
| Dimension | Score (1–4) | Evidence (quote or paraphrase what they actually said/wrote) |

### What a committee would write
<2–4 sentences in hiring-committee voice, including the strongest concern>

### Highest-leverage fixes (max 3)
1. <specific behavior change> — drill: <concrete exercise>

### Model answer sketch
<only now: a compact reference solution or design, highlighting the 2–3 moves
that separate the next level up>
```

Be honest. Inflated scores defeat the purpose. Cite evidence for every score;
no evidence means score it as not demonstrated.

## 5. Study plans

Ask for: interview date, hours per week, and recent mock results (or run a
15-minute diagnostic: one easy coding item, a 5-minute design sketch, one
behavioral question). Then produce:

- A gap ranking: which dimensions are below the bar for the target level.
- A week-by-week plan with absolute dates, weighted toward the largest gaps,
  with spaced repetition (revisit each pattern at about 1, 3, 7, and 14 days).
- Pattern coverage for coding (`references/coding.md` pattern list) rather than
  raw problem counts, a set of design prompts ordered by difficulty, and a STAR
  story bank build (`references/behavioral.md`).
- A mock cadence: at least 2 full mocks per week in the final 2 weeks.

If the user wants it saved, write it to `interview-prep/plan-<YYYY-MM-DD>.md`
in the repo.

## 6. Debriefs

From the user's account of a real interview, reconstruct the probable
scorecard. Separate what they *said* from what the interviewer likely
*heard*, and flag the likely deciding moment. Give a calibrated pass
probability as a range with reasoning, never as a certainty.

## 7. Session log (optional)

If the user wants progress tracked, append each mock's verdict, scores, and
fixes to `interview-prep/log.md` (create it if needed) so later sessions can
spot trends and re-drill weak dimensions.
