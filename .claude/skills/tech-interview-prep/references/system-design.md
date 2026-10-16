# System Design

## Prompt bank (ordered by difficulty)
- **Core**: URL shortener, paste bin, rate limiter, notification service, news feed, chat (1:1 + group)
- **Intermediate**: distributed cache, typeahead, ride matching, ticket booking with holds, web crawler, metrics/time-series ingestion
- **Advanced**: distributed job scheduler, payments ledger (exactly-once semantics), collaborative editor (CRDT/OT), global KV store with tunable consistency, video streaming + CDN, ad-click aggregation with late data
- **Staff+ twists**: migrate a live system with zero downtime; multi-region active-active with data residency; cut infra cost 40% without SLO regressions

## Expected flow (time for a 45-minute session)
1. Requirements and scope (5–8 min): functional, non-functional (latency, availability, durability, consistency), scale numbers.
2. Estimates (3–5 min): QPS (peak ≈ 2–3× average), storage per year, bandwidth, hot-key skew.
3. API and data model (5–8 min).
4. High-level design (8–10 min).
5. Deep dive (10–15 min): the interviewer picks the riskiest component.
6. Failure modes and evolution (5 min).

## Probes to use
- "What happens when this node dies mid-write?"
- "Your hottest key gets 100× traffic. Now what?"
- "Where exactly does a duplicate get created, and how do you dedupe?"
- "What's your p99, and which hop dominates it?"
- "How do you deploy a schema change here?"
- "What metric pages you at 3 a.m.?"
- "Product wants strong consistency on X. What does it cost?"

## Numbers candidates should know (order of magnitude)
L1 cache ~1 ns · RAM ~100 ns · SSD random read ~100 µs · same-region RTT ~0.5 ms ·
cross-continent RTT ~70–150 ms · a single well-tuned Postgres primary handles
roughly 10k+ simple writes/s · Kafka partition throughput is roughly tens of MB/s ·
1M req/day ≈ 12 req/s average.

## ML / LLM system design section
Prompts: recommendation/ranking feed, fraud detection, search ranking, RAG
assistant over enterprise docs, LLM agent platform with tool use, content
moderation at scale.

Must cover:
- Problem framing: business metric → ML objective → offline proxy; label source and delay.
- Data: collection, leakage risks, feedback loops, freshness, privacy/PII.
- Modeling: baseline first; candidate generation vs. ranking split; fine-tuning vs. prompting vs. RAG trade-offs.
- Evaluation: offline metrics, golden sets, LLM-as-judge pitfalls (bias, self-preference), online A/B tests with guardrail metrics.
- Serving: latency budget per stage, batching, caching (embedding/semantic/prompt caching), GPU cost per 1k requests, fallbacks.
- Safety and reliability: prompt injection, hallucination mitigation, monitoring for drift, human-in-the-loop escalation.
