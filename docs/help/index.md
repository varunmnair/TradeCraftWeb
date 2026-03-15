# TradeCraftX — Help

Welcome to **TradeCraftX**, a web-based assistant for Indian equity traders to **review holdings**, **plan buy entries**, and **manage pending buy orders (GTTs)** in a structured way.

> **Important:** TradeCraftX helps you analyze and execute your plan. You are responsible for decisions and confirming order placement/modification.

---

## What TradeCraftX is for

TradeCraftX is designed to help you:
- **Understand your current portfolio** (what you hold, how it’s performing, opportunity cost)
- **Make entry (buy) decisions** using structured strategies instead of impulse
- **Place buy orders safely** using selection + confirmation
- **Maintain existing pending buy orders** by deleting or adjusting them when needed
- **Ask an AI Analyst** questions about your portfolio and get suggestions (with human confirmation before actions)

---

## Key Concepts (Simple)

### Holdings
Your current positions in your demat account — quantity, average price, current price (CMP), P&L, ROI/day etc.

### Buy / Entries (Buying workspace)
This is where you decide **what to buy today**. It includes:
- **Multi‑Level Entry** (planned buying in levels)
- **Dynamic Averaging** (planned top-ups for existing holdings)

Most users do **Multi‑Level Entry first**, then **Dynamic Averaging**.

### GTT Orders (Good Till Triggered)
Pending conditional buy orders sitting at the broker. They trigger when price reaches a set level.

### Variance (in GTT Orders)
A quick indicator of how far an order’s trigger/price is from CMP. If variance is high, an order may be too far to execute soon.

---

## Typical Daily Workflow (Recommended)

### Step 1 — Review your portfolio
Go to **Holdings**  
1. Click **Refresh / Analyze**  
2. Sort by **ROI/Day** to spot opportunity cost  
3. Apply filters (losers, low ROI/day, etc.)  
4. Export if you want a snapshot

**Outcome:** You understand what is doing well and what is dragging returns.

---

### Step 2 — Plan and place regular buy entries (Multi‑Level Entry)
Go to **Buy / Entries → Multi‑Level Entry**  
1. Click **Generate Candidates**  
2. Review eligible stocks and suggested entry level (E1/E2/E3)  
3. Select only the stocks you want (partial placement is supported)  
4. Click **Place Selected Orders**  
5. Confirm when prompted

**Outcome:** You place only the buy orders you are comfortable with.

---

### Step 3 — (Optional) Apply Risk Adjustments (if enabled)
In **Multi‑Level Entry**, toggle **Apply Risk Adjustments**  
1. Review highlighted changes (price/amount changes)  
2. Select and place based on adjusted plan

**Outcome:** A more conservative plan when market conditions are risky.

---

### Step 4 — Place Dynamic Averaging orders (Top-ups)
Go to **Buy / Entries → Dynamic Averaging**  
1. Click **Generate Averaging Candidates**  
2. Select what you want  
3. Click **Place Selected Orders**  
4. Confirm

**Outcome:** You average into holdings with discipline, not emotion.

---

### Step 5 — Maintain existing pending buy orders (GTT Orders)
Go to **GTT Orders**  
This screen shows what already exists at the broker (independent from today’s plan).

Common actions:
- **Delete Selected:** remove stale/unwanted buy orders
- **Normalize Variance:** adjust selected orders to a target variance (e.g., 2%)

**Outcome:** Your pending orders stay relevant and aligned to market price movement.

---

## Screen Guide

## 1) Holdings

### What you can do
- Refresh/analyze holdings
- Sort by ROI/day or other performance measures
- Filter to focus on underperformers
- Export holdings

### Tips
- Use **ROI/day** to identify opportunity cost (capital stuck in slow movers).
- Export weekly if you want to track improvements over time.

---

## 2) Buy / Entries

### Why both strategies are here
Multi‑Level Entry and Dynamic Averaging are both part of the same activity: **buying**.

### Multi‑Level Entry
Use this for fresh entries in levels (E1/E2/E3).
- Generate candidates
- Select a subset
- Place selected orders with confirmation

### Dynamic Averaging
Use this for planned top-ups into existing holdings.
- Generate averaging candidates
- Select subset
- Place selected orders with confirmation

---

## 3) GTT Orders

### What this screen represents
This is a live view of **existing buy GTT orders** at your broker.

### Typical actions
#### Delete selected orders
1. Filter/search orders
2. Select unwanted orders
3. Click **Delete Selected**
4. Confirm deletion

#### Normalize variance (adjust selected orders)
1. Select orders you want to adjust
2. Enter target variance (example: 2%)
3. Click **Normalize / Adjust**
4. Confirm adjustment

> Tip: Always adjust/delete **selected** orders, not all orders.

---

## 4) AI Analyst

### What it is for
Ask questions and get suggestions. Examples:
- “Which holdings are worst by ROI/day?”
- “Which stocks are dragging performance?”
- “Summarize my pending buy orders risk”

### Safety
AI can suggest actions, but order placement/modification always requires confirmation.

---

## Common Tasks (Quick Help)

### Place orders for only a few stocks
**Buy / Entries → Multi‑Level Entry**
1. Generate candidates
2. Select only what you want
3. Place selected orders
4. Confirm

### Check what orders already exist
**GTT Orders**
1. Refresh
2. Filter/search by symbol
3. Review trigger/price and variance

### Delete stale pending orders
**GTT Orders**
1. Filter/search
2. Select orders
3. Delete selected
4. Confirm

### Adjust orders to target variance (e.g., 2%)
**GTT Orders**
1. Select orders
2. Enter target variance
3. Normalize/Adjust
4. Confirm

---

## Safety & Best Practices

- Always verify symbol, quantity, and trigger/limit prices before confirming
- Start small when testing (place 1–2 orders first)
- After placing orders, review them in **GTT Orders**
- Use selection-based actions to avoid accidental bulk changes

---

## Troubleshooting

### I can’t see updated holdings
- Confirm your session is active
- Click Refresh/Analyze again
- Check Jobs/Status if available

### Orders didn’t place
- Open **GTT Orders** and verify what exists at broker
- Review error message shown during confirmation/apply
- Refresh session and retry

### Broker connection looks connected, but actions fail
- Token may be expired — reconnect broker
- Refresh session
- Try again

### AI Analyst doesn’t respond
- Retry after refreshing session
- Check if AI is enabled/configured in your setup

---

## Where do I go?

- **Portfolio performance now** → Holdings  
- **Buy decisions today** → Buy / Entries  
- **Top-up (averaging) decisions** → Buy / Entries → Dynamic Averaging  
- **Manage pending buy orders** → GTT Orders  
- **Ask questions** → AI Analyst  

---

## About Demo / Safety Mode (if enabled)
If you see “Demo Mode” in the application banner:
- Treat it as a preview environment
- Confirm actions carefully
- Avoid real-money trading unless you fully understand the impact