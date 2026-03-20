# Green-Tech Inventory Assistant — System Design & Architecture

## 1. Problem & Goal
Small organizations (cafés, laboratories, non-profits) frequently over-order perishable goods resulting in waste, face unexpected stockouts, and lack easily deployable, data-driven tools to make procurement decisions.

**Goal**: Build a lightweight, trustworthy decision-support tool that combines explicit, deterministic mathematical forecasting with an intuitive AI-powered explanation layer. It must be easier to use than a spreadsheet while providing deeper, strictly reliable insights.

---

## 2. Solution Overview
The **Green-Tech Inventory Assistant** is a Streamlit-based web application backed by a zero-configuration SQLite database. It features a predictive reorder engine, a "what-if" scenario simulator, consumption pattern analysis, and integrates Groq's LLM (Llama 3.3) solely for generating human-readable insights from deterministic math.

---

## 3. System Architecture

The application strictly decouples the user interface from business logic, ensuring math calculations and API calls can be executed independently of the Streamlit frontend.

```mermaid
flowchart TD
    %% Define layers
    User[User / Operator]
    
    subgraph UI Layer
        App[app.py (Streamlit Dashboard)]
    end
    
    subgraph Execution & Logic Layer
        Reorder[reorder_engine.py (Core Math)]
        Insights[insights.py (Pattern Detection)]
        Sim[simulator.py (What-If Logic)]
    end
    
    subgraph Explanation Layer
        AI[ai_explainer.py (Groq API)]
        Fallback[fallback_explainer.py (Rule-Based)]
    end
    
    subgraph Data Layer
        DataLoader[data_loader.py (SQLAlchemy CRUD)]
        DB[(inventory.db SQLite)]
    end

    %% Flow connections
    User -->|Interacts| App
    App -->|Requests Analysis| Reorder
    App -->|Requests Insights| Insights
    App -->|Requests Playback| Sim
    
    Reorder -->|Reads/Writes Data| DataLoader
    Insights -->|Reads/Writes Data| DataLoader
    Sim -->|Reuses Core Math| Reorder
    DataLoader <--> DB

    Reorder -->|Passes Decision| AI
    Insights -->|Passes Patterns| AI
    
    AI -->|Returns Natural Text| App
    AI -.->|If API Fails / Disabled| Fallback
    Fallback -->|Returns Template Text| App
```

**Simple Data Flow Diagram**:
```text
User → UI → Reorder Engine ↔ DB  
                  ↓
            Analytics Layer
                  ↓ 
            Explanation Layer (AI)  
                  ↓  
            Fallback Layer (if AI fails)
```

**Data Flow Summary**:
1. **User** interacts with the Streamlit UI.
2. The **UI** delegates math to the **Reorder Engine**, which pulls data via the **Data Layer**.
3. Deterministic output is fed into the **Explanation Layer** (AI or Fallback).
4. Textual insights and interactive charts are returned to the **User**.

---

## 4. Core Features
1. **Predictive Reorder Dashboard**: Automatically flags items needing immediate reorder or approaching thresholds.
2. **What-If Purchase Simulator**: Allows users to dynamically change order quantities and lead times to project stock trajectories on a day-by-day chart.
3. **AI-Powered Explanations**: Translates dry mathematical signals into highly readable, short conversational insights and drafts supplier emails.
4. **Consumption Insights**: Automatically scans usage logs to tag items as fast-movers, slow-movers, or prone to weekend demand spikes.

---

## 5. Reorder Engine Logic (Mathematical Formulas)

The system rejects "black-box" decision making. All purchasing advice is derived explicitly in `reorder_engine.py`.

### Key Formulas:
1. **Average Daily Usage**:
   `avg_usage = SUM(quantity_used over last 7 days) / 7`
2. **Days of Stock Remaining**:
   `stock_days_remaining = current_stock / avg_usage` (If `avg_usage > 0`, else `Infinity`)
3. **Projected Usage Before Expiry**:
   `proj_usage = avg_usage * days_until_expiry`
4. **Suggested Reorder Quantity**:
   `suggested_qty = (avg_usage * lead_time) + safety_stock_buffer`
   *(Strictly capped so `current_stock + suggested_qty <= proj_usage` to prevent ordering perishables that will spoil before consumption).*

### Reorder Condition Rules:
- **`reorder_now`**: IF `stock_days_remaining <= lead_time`
- **`reorder_later`**: IF `stock_days_remaining <= (lead_time + safety_buffer)`
- **`do_not_reorder`**: IF `stock_days_remaining > (lead_time + safety_buffer)` AND `days_until_expiry > 0`

---

## 6. Simulator Design
The "What-If" simulator is **not** an isolated estimation script; it natively executes the exact same core engine logic to guarantee UI consistency.

**How it works (`simulator.py`)**:
1. Modifies the baseline item parameters in memory (applies user's demand multiplier override and custom lead times).
2. Executes a strict 7-day projection loop:
   ```python
   for day in range(7):
       stock_today = stock_yesterday - (avg_usage * demand_multiplier)
       if day == custom_lead_time - 1:
           stock_today += custom_order_quantity
       yield analyze_item(...)  # Re-run core determinism on new state
   ```
3. Returns a day-by-day trajectory array parsed directly by Plotly for graphing.

---

## 7. AI + Fallback Design

### Why AI is used ONLY for explanation:
The AI is strictly firewalled from calculating reorder logic, inventory quantities, or math. 
- **Improves Interpretability**: Translates raw data (e.g., `avg_usage: 4.2`, `stock: 12`) into actionable human insights (`📌 Pattern: Item is running low...`).
- **Avoids Black-Box Decisions**: Purchasing inventory costs real money. Operators must trust the math over LLM hallucinations. The Generative model is anchored securely to deterministic signals.

### Explicit AI vs. Fallback Flow:
```python
if ai_toggle_is_ON and api_key_is_PRESENT:
    try:
        explanation = call_groq_api(structured_math_signals)
        return explanation
    except API_Error:
        return generate_rule_based_template(structured_math_signals)
else:
    return generate_rule_based_template(structured_math_signals)
```
*This ensures 100% offline reliability. If the internet drops, the system instantly degrades gracefully to the Fallback Layer without crashing.*

---

## 8. Data Model

The application uses **SQLite** orchestrated by **SQLAlchemy ORM**.

### Schema Structure:
- `suppliers`: (`supplier_id` PK, `supplier_name`, `avg_lead_days`, `packaging_score`)
- `items`: (`item_id` PK, `item_name`, `quantity`, `expiry_date`, `supplier_id` FK)
- `usage_logs`: (`log_id` PK, `item_id` FK, `usage_date`, `quantity_used`)
- `simulator_runs`: (`scenario_id` PK, `item_id` FK, `parameters_json`)

### ER Relationships:
- **1-to-Many**: `suppliers` → `items` (A supplier provides many items, an item has one primary supplier).
- **1-to-Many**: `items` → `usage_logs` (An item holds daily log entries detailing consumption).
- **1-to-Many**: `items` → `simulator_runs` (An item holds records of past what-if scenarios ran against it).

---

## 9. Edge Cases & Validation

The math engine and UI validation checks gracefully handle extreme states:

1. **Zero Usage History**: 
   - *Logic*: `avg_usage` defaults to 0. `stock_days_remaining` becomes `Infinity`.
   - *Result*: Safe recommendation ("Do not reorder until history is established").
2. **Expired Items**:
   - *Logic*: Checks if `days_until_expiry <= 0` immediately.
   - *Result*: Overrides all reorders. Action explicitly flags "Remove from inventory".
3. **Invalid Inputs**: 
   - *Logic*: `validation.py` traps negative stock quantities, improperly formatted dates, and missing supplier associations before database insertion.
   - *Result*: UI displays standard Streamlit error banners blocking the write.

---

## 10. Testing Strategy

The application includes 19 rigorous `pytest` tests that guarantee mathematical accuracy and safe database interactions.

**Key Testing Areas**:
1. **Mathematical Happy Paths (`test_happy_path.py`)**:
   - *Input*: Item with 10 stock, using 3 a day, lead time 4 days.
   - *Expected Output*: Engine must rigidly return `reorder_decision = reorder_now` and correctly calculate `suggested_qty`.
2. **Edge Case Trapping (`test_edge_case.py`)**:
   - *Input*: Item with 0 usage.
   - *Expected Output*: Engine handles division-by-zero bounds gracefully without crashing python. 
3. **Isolated Database CRUD (`test_database.py`)**:
   - Uses `pytest` monkeypatching to reroute SQLAlchemy to a temporary in-memory/tempfile SQLite DB, asserting foreign key relationships persist safely without corrupting the live `inventory.db` file.

---

## 11. Assumptions
- **Daily Logging**: The accuracy of the reorder engine assumes the operator logs consumption decently consistently (or syncs from a theoretical POS system).
- **Perfect Logistics**: The simulator assumes 100% of an order quantity arrives perfectly upon the designated lead time day, with no partial shipments.
- **Single Warehouse**: Assumes all inventory exists in a singular accessible location.

---

## 12. Limitations
- **Single-User Architecture**: Relying purely on SQLite drastically improves local deployment speed but renders the app fragile under high-concurrency multi-user writes.
- **Aggressive Perishable Capping**: The code rigidly restricts perishable goods orders to *exactly* what can be used before expiry based on past averages. Highly unpredictable demand spikes could trigger stockouts.
- **Fixed Horizons**: Projections are strictly capped at 7 days.

---

## 13. Future Improvements
- **PostgreSQL Migration**: Swap the database layer to permit simultaneous multi-user RBAC (Role-Based Access Control).
- **Barcode / POS Integration**: Introduce physical scanning webhooks to automate `usage_logs` table population, completely removing manual data entry.
- **Multi-Item Scenario Bundling**: Allow the Simulator to project supplier-wide order scenarios, rather than calculating one single item at a time.
