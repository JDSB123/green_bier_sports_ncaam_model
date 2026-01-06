# Long-Term Integration Architecture
**Last Updated:** January 2026  
**Status:** Proposed Architecture

---

## Overview

This document outlines the sustainable, production-ready architecture for:
1. **Teams Integration** - Getting picks in Microsoft Teams
2. **Website Integration** - Displaying picks on greenbiersportsventures.com

---

## Current State (Problems)

### Teams Webhook
| Issue | Root Cause |
|-------|------------|
| "Run already in progress" errors | Advisory locks stuck from crashed processes |
| Incoming webhooks deprecated | Microsoft retiring incoming webhooks in 2026 |
| Outgoing webhook complexity | Requires HMAC validation, specific response format |

### Website Integration  
| Issue | Root Cause |
|-------|------------|
| No weekly lineup page | Frontend is static placeholder HTML |
| No automatic updates | Picks must be manually triggered |
| No public API | All endpoints require internal access |

---

## Long-Term Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PREDICTION ENGINE                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐  │
│  │ run_today.py│───▶│  PostgreSQL │◀───│ predictions + betting_recs     │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
│  FastAPI (prediction-service-python)                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GET  /api/picks/{date}      → JSON picks (for website)              │    │
│  │ GET  /api/picks/weekly      → 7-day picks rollup (for website)      │    │
│  │ POST /api/run/{date}        → Trigger + return picks                │    │
│  │ GET  /health                → Service health                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                               │
                    ▼                               ▼
┌────────────────────────────┐    ┌────────────────────────────────────────────┐
│      TEAMS INTEGRATION     │    │         WEBSITE INTEGRATION                 │
│                            │    │                                            │
│  Option A: Power Automate  │    │  greenbiersportsventures.com               │
│  ─────────────────────────│    │  ┌──────────────────────────────────────┐  │
│  • Scheduled flow (daily)  │    │  │ React/Vue SPA or Static Site Gen   │  │
│  • Calls POST /api/run     │    │  │ • Fetches /api/picks/weekly        │  │
│  • Posts to Teams channel  │    │  │ • Renders picks table              │  │
│  • No webhook needed       │    │  │ • Auto-refreshes every hour        │  │
│                            │    │  └──────────────────────────────────────┘  │
│  Option B: Teams Bot       │    │                                            │
│  ─────────────────────────│    │  Alternative: Server-Side Rendering       │
│  • Azure Bot Service       │    │  • Next.js/Nuxt on Azure Static Web Apps │
│  • Responds to commands    │    │  • SSR with caching                       │
│  • Proactive notifications │    │  • SEO-friendly                           │
│                            │    │                                            │
└────────────────────────────┘    └────────────────────────────────────────────┘
```

---

## Recommended Solutions

### 1. Teams Integration: Power Automate Flow

**Why Power Automate instead of webhooks:**
- ✅ Microsoft's official replacement for incoming webhooks
- ✅ No code to maintain - visual workflow
- ✅ Built-in retry/error handling
- ✅ Can be triggered by schedule OR manually
- ✅ Logs and audit trail in M365

**Setup Steps:**
1. Create a Power Automate flow in your M365 tenant
2. Trigger: Recurrence (daily at 8 AM CT) or Manual
3. Action: HTTP → `POST https://your-app.azurecontainerapps.io/api/run/today`
4. Action: Parse JSON response
5. Action: Post Adaptive Card to Teams channel

**Adaptive Card Template:**
```json
{
  "type": "AdaptiveCard",
  "body": [
    {"type": "TextBlock", "text": "🏀 NCAAM Picks - @{formatDateTime(utcNow(), 'MMMM d')}", "weight": "Bolder", "size": "Large"},
    {"type": "FactSet", "facts": "@{body('Parse_JSON')?['picks']}"}
  ],
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "version": "1.4"
}
```

### 2. Website Integration: Weekly Lineup Page

**Option A: Static Site with Client-Side Fetch (Simplest)**

Add to `services/web-frontend/site/weekly.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Weekly Lineup | Green Bier Sports</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100">
  <div id="app" class="max-w-6xl mx-auto px-6 py-10">
    <h1 class="text-3xl font-bold mb-6">Weekly NCAAM Picks</h1>
    <div id="picks-container">Loading...</div>
  </div>
  <script>
    const API_BASE = 'https://your-app.azurecontainerapps.io';
    
    async function loadPicks() {
      try {
        const res = await fetch(`${API_BASE}/api/picks/weekly`);
        const data = await res.json();
        renderPicks(data);
      } catch (e) {
        document.getElementById('picks-container').innerHTML = 
          '<p class="text-red-400">Failed to load picks</p>';
      }
    }
    
    function renderPicks(data) {
      // Render table with picks grouped by date
    }
    
    loadPicks();
    setInterval(loadPicks, 3600000); // Refresh hourly
  </script>
</body>
</html>
```

**Option B: Next.js on Azure Static Web Apps (Production-Grade)**
- Server-side rendering for SEO
- ISR (Incremental Static Regeneration) for caching
- Edge caching for performance

---

## New API Endpoints Needed

### `/api/picks/weekly`
Returns 7-day picks rollup for website:

```python
@app.get("/api/picks/weekly")
@limiter.limit("60/minute")
async def get_weekly_picks(request: Request):
    """
    Fetch picks for the next 7 days (for website weekly lineup).
    """
    engine = _get_db_engine()
    if not engine:
        return {"error": "Database not configured", "days": []}
    
    today = date.today()
    days = []
    
    for offset in range(7):
        target_date = today + timedelta(days=offset)
        picks = _fetch_persisted_picks(engine, target_date)
        if picks:
            days.append({
                "date": target_date.isoformat(),
                "day_name": target_date.strftime("%A"),
                "picks": picks,
                "total": len(picks),
            })
    
    return {
        "generated_at": datetime.now(CST).isoformat(),
        "model_version": _model_version_tag(),
        "days": days,
        "total_picks": sum(d["total"] for d in days),
    }
```

### `/api/picks/latest`
Returns most recent picks regardless of date:

```python
@app.get("/api/picks/latest")
async def get_latest_picks(request: Request, limit: int = 50):
    """Latest picks across all dates (for dashboard/widget)."""
    # Query betting_recommendations ORDER BY created_at DESC LIMIT {limit}
```

---

## CORS Configuration

For website integration, add CORS to FastAPI:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://greenbiersportsventures.com",
        "https://www.greenbiersportsventures.com",
        "http://localhost:3000",  # Dev
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## Scheduler Options

### Azure Container Apps Job (Recommended)
```yaml
# azure/scheduler-job.yaml
apiVersion: apps.containerapps.azure.com/v1
kind: ContainerAppJob
metadata:
  name: ncaam-daily-run
spec:
  schedule: "0 8 * * *"  # 8 AM UTC
  template:
    containers:
      - name: runner
        image: ${ACR}/prediction-service:latest
        command: ["python", "run_today.py"]
```

### Azure Logic Apps
- Visual workflow designer
- Integrates with Teams, Email, Slack
- No code changes needed

### Cron in Container (Current)
- Works but less observable
- No retry/alerting built-in

---

## Implementation Roadmap

### Phase 1: Fix Immediate Issues (This Week)
- [x] Add stale lock detection
- [x] Add emergency lock release endpoint
- [ ] Add `/api/picks/weekly` endpoint
- [ ] Add CORS for greenbiersportsventures.com

### Phase 2: Teams Power Automate (Next Week)
- [ ] Create Power Automate flow
- [ ] Test daily schedule
- [ ] Remove outgoing webhook complexity
- [ ] Archive webhook secret/validation code

### Phase 3: Website Frontend (2 Weeks)
- [ ] Create `weekly.html` with picks display
- [ ] Deploy to Azure Static Web Apps
- [ ] Configure custom domain
- [ ] Add caching/CDN

### Phase 4: Polish (Ongoing)
- [ ] Add settlement results display
- [ ] Historical performance charts
- [ ] Email digest option

---

## Summary: What to Do Now

| Component | Current | Long-Term Fix |
|-----------|---------|---------------|
| **Teams** | Outgoing webhook with HMAC | **Power Automate flow** (scheduled, calls API) |
| **Website** | Static placeholder | **Client-side fetch** of `/api/picks/weekly` |
| **Scheduler** | Manual trigger | **Azure Container Apps Job** (cron) |
| **Locking** | Advisory lock (fixed) | Keep, but add job queue (optional) |

**Immediate Next Steps:**
1. Add `/api/picks/weekly` endpoint
2. Add CORS headers
3. Create Power Automate flow in M365 admin
4. Update `weekly.html` to fetch and display picks
