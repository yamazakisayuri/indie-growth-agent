# Architecture — Indie Growth Agent

Hackathon architecture for **Indie Growth Agent**: three observed sources become one grounded priority list.

**Value:** `3 data sources → grounded analysis → 1 priority list`  
Not a multi-dashboard mashup. The agent applies a Data Contract (periods, populations, missing ≠ zero), then returns **Facts / Speculation** and **prioritized Top 3 Actions**.

## Diagram

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TB
  user([Indie developer])

  subgraph aws ["AWS"]
    amplify["AWS Amplify Hosting<br/>Next.js 16 static export<br/>ja / en UI"]
    ecr["Amazon ECR"]
    ecs["Amazon ECS Express Mode<br/>AWS Fargate + ALB HTTPS<br/>FastAPI"]
    secrets["AWS Secrets Manager"]
    strands["Strands Agents SDK"]
    bedrock["Amazon Bedrock<br/>Claude"]
  end

  subgraph external ["External data sources<br/>separate populations — not one funnel"]
    asc["App Store Connect Analytics"]
    ga4["Google Analytics 4"]
    admob["Google AdMob"]
  end

  github["GitHub"] -.->|deploy UI| amplify
  github -.->|container image| ecr
  ecr -.-> ecs
  secrets -.->|Task Execution Role| ecs

  user -->|Open UI / Analyze| amplify
  amplify -->|"Browser CORS · POST /api/analyze<br/>body: language only"| ecs

  ecs --> asc
  ecs --> ga4
  ecs --> admob

  ecs --> grounding["Data Contract / Grounding<br/>periods · populations · missing ≠ zero"]
  grounding --> strands
  strands -->|ECS Task Role| bedrock
  bedrock --> result["Facts / Speculation<br/>prioritized Top 3 Actions"]
  result -->|JSON response| amplify
```

Source-only Mermaid file: [`architecture.mmd`](architecture.mmd)

## Request flow

1. User opens the Amplify-hosted static Web UI and clicks **Analyze**.
2. Browser calls FastAPI `POST /api/analyze` on the ECS Express Mode HTTPS endpoint (CORS; `{ language }` only).
3. Backend loads secrets via **AWS Secrets Manager** (Task Execution Role) and fetches App Store Connect, GA4, and AdMob.
4. Observed metrics are shaped into a **Data Contract / Grounding** prompt (aligned windows, separate populations, missing ≠ zero).
5. **Strands Agents SDK** invokes **Amazon Bedrock (Claude)** with the ECS **Task Role** (no long-lived AWS access keys in the container).
6. Structured **Facts / Speculation / Top 3 Actions** JSON returns to the browser and renders in the UI.

## Not in this architecture

App Runner, Amplify SSR, Next.js API Route proxy, AgentCore, API Gateway, Cognito, application database, Google Play, RevenueCat, App Store reviews.
