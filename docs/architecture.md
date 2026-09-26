# Architecture — Indie Growth Agent

Hackathon architecture for **Indie Growth Agent**: connected Product channels become one grounded priority list.

**Value:** `connected sources → grounded analysis → 1 priority list`  
Not a multi-dashboard mashup. The agent applies a Data Contract (periods, populations, missing ≠ zero, revenue sources not summed), then returns **Facts / Speculation** and **prioritized Top 3 Actions** for the **selected Product**.

## Diagram

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TB
  user([Indie developer])

  subgraph aws ["AWS"]
    amplify["AWS Amplify Hosting<br/>Next.js 16 static export<br/>ja / en UI · Product selector"]
    ecr["Amazon ECR"]
    ecs["Amazon ECS Express Mode<br/>AWS Fargate + ALB HTTPS<br/>FastAPI"]
    strands["Strands Agents SDK"]
    bedrock["Amazon Bedrock<br/>Claude"]
  end

  subgraph external ["External data sources<br/>separate populations — not one funnel"]
    ascAnalytics["App Store Connect Analytics"]
    ascSales["App Store Connect Sales<br/>Developer Proceeds"]
    ga4App["GA4 App"]
    ga4Web["GA4 Web<br/>hostName EXACT"]
    admob["Google AdMob"]
  end

  github["GitHub"] -.->|deploy UI| amplify
  github -.->|container image| ecr
  ecr -.-> ecs

  user -->|Open UI / select Product / Analyze| amplify
  amplify -->|"Browser CORS · POST /api/analyze<br/>body: language + productId"| ecs
  amplify -->|"GET /api/products · POST /api/draft"| ecs

  ecs --> ascAnalytics
  ecs --> ascSales
  ecs --> ga4App
  ecs --> ga4Web
  ecs --> admob

  ecs --> grounding["Data Contract / Grounding<br/>periods · populations · missing ≠ zero<br/>revenue sources not summed"]
  grounding --> strands
  strands -->|ECS Task Role| bedrock
  bedrock --> result["Facts / Speculation<br/>prioritized Top 3 Actions<br/>optional Growth Experiments"]
  result -->|JSON response| amplify
```

Source-only Mermaid file: [`architecture.mmd`](architecture.mmd)

## Request flow

1. User opens the Amplify-hosted static Web UI, selects a **Product**, and sees the **last successful Live Analyze** for that Product from `localStorage` (or an empty shell).
2. Browser may call `GET /api/products` for the catalog. **Analyze** calls FastAPI `POST /api/analyze` on the ECS Express Mode HTTPS endpoint (CORS; body `{ language, productId }`).
3. Backend reads **process environment variables** (`config.py`; locally from `.env`). In ECS deploy, those values may be injected into the task environment from **AWS Secrets Manager**—the application does not call Secrets Manager APIs itself.
4. Backend loads the Product from `products/`, then fetches connected channels: App Store Connect Analytics, optional ASC Sales (Developer Proceeds), GA4 App, GA4 Web (`hostName` EXACT when configured), and AdMob.
5. Observed metrics are shaped into a **Data Contract / Grounding** prompt (aligned windows, separate populations including GA4 Web ≠ GA4 App, missing ≠ zero, AdMob earnings ≠ ASC Proceeds and must not be summed).
6. **Strands Agents SDK** invokes **Amazon Bedrock (Claude)** with the ECS **Task Role** (no long-lived AWS access keys in the container). Optional Planner may attach Growth Experiments.
7. Structured **Facts / Speculation / Top 3 Actions** (and optional experiments) JSON returns to the browser, renders in the UI, and is cached as the last successful report for that Product.
8. Optional **Action Draft**: browser `POST /api/draft` with experiment context (and optional screenshots); secrets still stay server-side.

**Language:** UI chrome switches with the language control immediately. Switching language alone does **not** re-run Analyze or regenerate existing analysis prose; run Analyze again to refresh body text in the new language.

## Not in this architecture

App Runner, Amplify SSR, Next.js API Route proxy, AgentCore, API Gateway, Cognito, application database, **Google Play**, RevenueCat, App Store reviews, cross-Product **portfolio** analysis (the single-Product selector is in scope; portfolio comparison is not).
