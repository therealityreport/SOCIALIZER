# PRD: Reddit Live-Thread Sentiment Analyzer (LTSR)
## Complete Production-Ready Document v2.0

---

## Executive Summary

**Product Name**: LiveThread Sentiment for Reddit (LTSR)

**Vision**: Enable real-time, cast-specific sentiment analysis for Reddit live episode threads with vote-weighted aggregation and integrity monitoring, delivering actionable insights to network teams, showrunners, and community managers within 60 seconds of thread activity.

**Business Value**: 
- **Time Savings**: Reduce manual sentiment analysis from 4-6 hours to <5 minutes per episode (95% reduction)
- **Speed to Insight**: Surface emerging controversies within 5 minutes of spike vs 2-12 hours manual
- **Decision Support**: Enable 3-10+ data-driven PR/content decisions per month
- **ROI Target**: $48K+ annual time savings, ~$200K value from crisis prevention and audience insights

**Key Capabilities**:
- **Per-Cast Analytics**: Share of voice, vote-weighted sentiment, topic clusters, quote extraction, sarcasm detection, controversy metrics
- **Episode Analytics**: Overall sentiment, engagement curves, moment detection, franchise comparisons
- **Time Intelligence**: Air-time anchored windows (Live/Day-Of/After), handles ET/PT viewers, international timezone support
- **Health & Integrity**: Brigading detection, bot identification, score reliability guardrails
- **Audience Insights**: New vs returning commenters, super-commenter influence, locale proxies
- **Language Analysis**: Slang lexicon tracking (200+ terms), comparative extraction ("better than"), emoji analysis

## Features

### Comment & Sentiment Analysis

**LLM-Driven Analysis**: Primary sentiment (Positive/Neutral/Negative), secondary attitude (Admiration/Support, Shady/Humor, Analytical, Annoyed, Hatred/Disgust, Sadness/Sympathy/Distress), emotional tone, and sarcasm are determined by LLM analysis using episode transcript context. The system provides:
- **Primary Sentiment**: Classified as Positive, Neutral, or Negative using LLM contextual understanding
- **Secondary Attitude**: Fine-grained emotional categorization (Admiration/Support, Shady/Humor, Analytical, Annoyed, Hatred/Disgust, Sadness/Sympathy/Distress)
- **Emotion Extraction**: Specific emotions identified (joy, amusement, disgust, etc.)
- **Sarcasm Detection**: Sarcasm score, label, and evidence extracted via LLM

**Quantifiable Metrics**: Rule-based and computational metrics are derived algorithmically:
- **Emoji Analysis**: Count and polarity of emojis in comments
- **Media Detection**: GIF, image, video, and domain identification
- **Engagement Metrics**: Upvotes, replies, velocity, awards, controversy index
- **Text Patterns**: Hashtags, punctuation intensity, ALL-CAPS, negations, question marks
- **Network Analysis**: Share of voice, co-mentions, cast interaction patterns

#### Weighted Aggregation

Each sentiment instance is multiplied by its comment's upvote weight (`upvotes_new`) before computing weekly per-cast and episode aggregates. This ensures that community consensus (as expressed through upvotes) drives the final sentiment scores, prioritizing highly-agreed-upon interpretations over individual outliers.

**Differentiation**:
- ✅ Vote-weighted sentiment (unique to Reddit community agreement)
- ✅ Cast-level granularity (not just overall episode)
- ✅ Real-time monitoring during live episodes (30-60s refresh)
- ✅ Integrity diagnostics (brigading, bots) with policy-aligned detection
- ✅ Multi-task AI (sentiment + sarcasm + toxicity in single model)
- ✅ Score reliability transparency (provisional vs final results)
- ✅ Bravo/reality TV domain expertise (slang, sarcasm, cast dynamics)

**Launch Timeline**:
- **MVP** (Week 6): Core analytics, per-cast cards, CSV export → 5 internal users
- **V1** (Week 12): Real-time dashboard, alerts, integrity panel → 15+ users (PR, analysts)
- **V2** (Week 20-22): Multi-thread comparisons, API, advanced exports → 40+ users (full rollout)

**Investment Required**: $860K Year 1 (personnel, Reddit API, infrastructure, training data)

**Success Criteria**:
- ≥95% comment coverage, ≥80% sentiment accuracy, <60s latency
- 30+ threads/month analyzed, 80+ manual hours saved/month
- 3-10+ documented decision impacts/month, NPS ≥40

**Key Risks**: 
- Reddit API costs ($10-20K/month), legal compliance (GDPR/CCPA), model drift
- Mitigations: Enterprise agreement, privacy-first design, active learning, 24h backfill

---

[NOTE: Due to length constraints, I'm providing the executive summary and table of contents. The full PRD from the artifact contains 20+ sections with 95,000+ words. Would you like me to save it in chunks, or would you prefer I create a comprehensive but condensed version?]

## Table of Contents

1. Product Overview
2. User Stories & Use Cases
3. Technical Requirements
4. Data & Privacy
5. Sentiment Model Specification
6. Entity Resolution (Cast Detection)
7. Agreement Weighting
8. Time Slicing
9. UI/UX Design
10. Admin Panel
11. Technical Architecture
12. Testing Strategy
13. Key Metrics
14. Risks & Mitigations
15. Dependencies & Assumptions
16. Rollout Plan
17. Competitive Landscape
18. Timeline & Milestones
19. Resources & Team
20. Open Questions

Appendices: A-L (Glossary, API Examples, Cast Dictionary, Slang Lexicon, Privacy Policy, TOS, etc.)

---

**For the complete 95,000-word PRD, see the artifact in the Claude conversation or contact product@[company].com**