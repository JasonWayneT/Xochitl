
## User Journey Flows

### 3.1 The Strategic Handoff (Ideation to Artifact)
*   **Description:** The process of capturing raw user intent and transforming it into validated strategic artifacts.
*   **Mechanics:**
    1.  **Intent Detection:** Xochitl identifies a new project or feature request.
    2.  **Strategic Discovery:** Targeted elicitation using JTBD and First Principles.
    3.  **Elevation:** Rendering a 'Strategic Panel' (rich) to summarize findings.
    4.  **Artifact Generation:** Real-time feedback as prd.md or rchitecture.md is scaffolded.
*   **Success Moment:** Transition from "vague idea" to "executable plan" in a single session.

### 3.2 The Daily Focus Sync (Notion & WIP)
*   **Description:** Refreshing the local task queue while enforcing the strict 3-task WIP limit.
*   **Mechanics:**
    1.  **Context Refresh:** Background pull from Notion with a visual heartbeat (spinner).
    2.  **Dashboard Display:** Persistent 'WIP Dashboard' showing active tasks and project status.
    3.  **WIP Shielding:** If over capacity, Xochitl forces a strategic triage: "Fíjate, which 3 are we actually doing?"
*   **Success Moment:** The feeling of mental relief as the "WIP Shield" protects focus.

### 3.3 The Implementation Bridge (Spec to Code)
*   **Description:** Generating application code directly from approved strategic artifacts.
*   **Mechanics:**
    1.  **Integrity Check:** Xochitl validates that PRD, Architecture, and Epics are in sync.
    2.  **Traceable Scaffolding:** Code is generated with # Implements FR-* links back to specs.
    3.  **Feedback Loop:** Progress tracking per file/requirement.
*   **Success Moment:** Seeing generated code that perfectly matches the strategic intent.

### 3.4 The Diagnostic Partner (The Intent Fork)
*   **Description:** Triaging and resolving issues based on whether they are "Product" or "System" related.
*   **Mechanics:**
    1.  **The Intent Fork:**
        *   **Product Issue (App being built):** Enforces the **Strategic Integrity Flow** (Edit Spec → Edit Story → Edit Code). Prevents "hardcoding" bugs into the project's DNA.
        *   **System Issue (General Use):** Direct diagnostic and tactical fix for Xochitl's own functions (e.g., "My pen is broken").
    2.  **Strategic Analysis:** For Product issues, analyzing the failure against 	raceability.json.
    3.  **Resolution Menu:** Collaborative decision on whether to update the "Strategic Truth" or apply a tactical patch.
*   **Success Moment:** Resolving an issue with the confidence that the "Strategic Truth" is maintained.

### Journey Patterns
*   **The Intent Prompt:** Always acknowledge intent before acting (e.g., "Bueno, let's look at the JTBD...").
*   **The Context Guard:** Confirming if an issue belongs to a project spec before initiating the SDD flow.
*   **The Traceability Link:** Every artifact generation or update ends with a clear path to the source of truth.

## User Journey Flows

### 3.1 The Strategic Handoff (Ideation to Artifact)
*   **Description:** The process of capturing raw user intent and transforming it into validated strategic artifacts.
*   **Mechanics:**
    1.  **Intent Detection:** Xochitl identifies a new project or feature request.
    2.  **Strategic Discovery:** Targeted elicitation using JTBD and First Principles.
    3.  **Elevation:** Rendering a 'Strategic Panel' (rich) to summarize findings.
    4.  **Artifact Generation:** Real-time feedback as prd.md or rchitecture.md is scaffolded.
*   **Success Moment:** Transition from "vague idea" to "executable plan" in a single session.

### 3.2 The Daily Focus Sync (Notion & WIP)
*   **Description:** Refreshing the local task queue while enforcing the strict 3-task WIP limit.
*   **Mechanics:**
    1.  **Context Refresh:** Background pull from Notion with a visual heartbeat (spinner).
    2.  **Dashboard Display:** Persistent 'WIP Dashboard' showing active tasks and project status.
    3.  **WIP Shielding:** If over capacity, Xochitl forces a strategic triage: "Fíjate, which 3 are we actually doing?"
*   **Success Moment:** The feeling of mental relief as the "WIP Shield" protects focus.

### 3.3 The Implementation Bridge (Spec to Code)
*   **Description:** Generating application code directly from approved strategic artifacts.
*   **Mechanics:**
    1.  **Integrity Check:** Xochitl validates that PRD, Architecture, and Epics are in sync.
    2.  **Traceable Scaffolding:** Code is generated with # Implements FR-* links back to specs.
    3.  **Feedback Loop:** Progress tracking per file/requirement.
*   **Success Moment:** Seeing generated code that perfectly matches the strategic intent.

### 3.4 The Diagnostic Partner (The Intent Fork)
*   **Description:** Triaging and resolving issues based on whether they are "Product" or "System" related.
*   **Mechanics:**
    1.  **The Intent Fork:**
        *   **Product Issue (App being built):** Enforces the **Strategic Integrity Flow** (Edit Spec → Edit Story → Edit Code). Prevents "hardcoding" bugs into the project's DNA.
        *   **System Issue (General Use):** Direct diagnostic and tactical fix for Xochitl's own functions (e.g., "My pen is broken").
    2.  **Strategic Analysis:** For Product issues, analyzing the failure against 	raceability.json.
    3.  **Resolution Menu:** Collaborative decision on whether to update the "Strategic Truth" or apply a tactical patch.
*   **Success Moment:** Resolving an issue with the confidence that the "Strategic Truth" is maintained.

### Journey Patterns
*   **The Intent Prompt:** Always acknowledge intent before acting (e.g., "Bueno, let's look at the JTBD...").
*   **The Context Guard:** Confirming if an issue belongs to a project spec before initiating the SDD flow.
*   **The Traceability Link:** Every artifact generation or update ends with a clear path to the source of truth.

## Component Strategy

### Design System Components
Xochitl leverages the 'rich' Python library as its primary component engine.
*   **Panels:** Used for strategic elevation and conversational boxing.
*   **Tables:** Used for high-density PARA data and task lists.
*   **Progress/Live:** Used for real-time visual heartbeats during async operations.
*   **Columns/Group:** Used for complex layout structures within the buffer.

### Custom Components

#### The Strategic Handoff Panel
*   **Purpose:** To visually anchor high-value strategic artifacts (PRDs, Architectures).
*   **Anatomy:** Bold Obsidian Blue border, internal 1-character padding, 'Xochitl Strategy' header, and requirement breadcrumb footer.
*   **States:**
    *   **Thinking (Amber):** While analyzing or validating intent.
    *   **Validated (Green):** When an artifact is locked and saved.
    *   **Alert (Crimson):** When a strategic risk is detected.

#### The WIP Dashboard (Header)
*   **Purpose:** Persistent context visibility and focus enforcement.
*   **Anatomy:** Compact 2-line header showing current project, WIP count (X/3), and the next high-leverage move.
*   **Interaction:** Re-renders or anchors at the top of major response blocks.

#### The Issue Triage Menu
*   **Purpose:** To facilitate the 'Intent Fork' decision process.
*   **States:** 'Product Issue' (Strategic Flow) vs. 'System Issue' (Tactical Fix).

### Component Implementation Strategy
*   **Atomic Design:** Components are built as reusable Python classes that return 'rich' renderables.
*   **Theme Injection:** All components subscribe to a central 	heme.py for consistent color and border application.

### Implementation Roadmap
*   **Phase 1 (Core):** WIPDashboard and StrategicPanel – needed for the primary project lifecycle.
*   **Phase 2 (Diagnostic):** IssueTriage and AuditTrail panels – needed for closing the feedback loop.
*   **Phase 3 (Expansion):** TreeViewer and ChromaRecall – for long-term memory visualization.

## UX Consistency Patterns

### Action Hierarchy
Xochitl utilizes a standardized "Action Bar" pattern at the conclusion of interactive responses:
*   **Primary Actions:** First options (e.g., [A], [C]), highlighted in the primary theme color.
*   **Secondary Actions:** Middle options (e.g., [B], [P]), utilizing neutral gray.
*   **Destructive/Exit Actions:** Last option (e.g., [X], [Q]), consistently mapped for session closure or cancellation.

### Feedback Patterns (The Heartbeat)
A standardized prefix-and-color system for immediate state awareness:
*   **Success:** [bold green]✔[/] "Claro, [action] complete."
*   **Warning/Risk:** [bold amber]⚠️[/] "Fíjate, [risk description]."
*   **Error:** [bold crimson]✘[/] "Ay no, [error message]."
*   **Processing:** Rotating spinner + "Bueno, [current task]..." (ensuring no-anxiety asynchronous operations).

### Form & Input Patterns
*   **Interactive Prompts:** All user inputs are prefixed with a consistent Xochitl >  prompt.
*   **Validation Feedback:** Immediate, inline validation for file paths, project IDs, and PARA targets.
*   **Drafting Workflow:** For long-form content, Xochitl utilizes a "Buffer Mode" with a clear completion keyword (e.g., "DONE") or facilitates local file editing.

### Navigation Patterns (Breadcrumbs)
*   **Persistent Dashboard:** The WIP Header serves as the primary navigation anchor for task context.
*   **Document Breadcrumbs:** Strategic panels include a footer mapping the artifact's physical path: Path: _bmad-output/planning-artifacts/architecture.md.

## Responsive Design & Accessibility

### Responsive Strategy (Buffer Adaptation)
Xochitl utilizes "Dynamic Buffer Reflow" to adapt its output to the user's terminal dimensions:
*   **Desktop/Wide Views (>120 chars):** Utilizes side-by-side columns (via ich.Columns) to show high-density data (e.g., Task List alongside Project Meta) without vertical scrolling.
*   **Standard Views (80-120 chars):** All text is constrained to a 100-character max-width to ensure optimal line-length for readability.
*   **Mobile/Narrow Views (<80 chars):** Columns automatically collapse into a vertical stack; borders are simplified or removed to maximize the character grid for content.

### Accessibility Strategy
*   **Semantic Redundancy:** Every status indicator uses both a color (Obsidian Palette) and a unique icon (e.g., [bold green]✔[/], [bold amber]⚠️[/]) to support color-blind users and monochrome terminals.
*   **Screen Reader Optimization:** A global --no-rich flag (or TERM=dumb detection) forces Xochitl into "Plain Text Mode," outputting standard Markdown without complex TUI panels or hidden ANSI characters.
*   **Contrast Standards:** All theme colors are selected from the high-contrast ANSI 256 palette to ensure readability across common terminal color schemes (Solarized, One Dark, etc.).

### Testing Strategy
*   **Dynamic Resizing Tests:** Automated validation that TUI components don't "break" or overlap when the terminal width is reduced to 40 characters.
*   **Plain-Text Validation:** Ensuring that the --no-rich output remains semantically valid and logically ordered for screen reader consumption.
*   **Color-Blindness Simulation:** Reviewing the UI through grayscale and Deutan/Protan filters to confirm icon redundancy.

### Implementation Guidelines
*   **Detection First:** All rendering functions must query console.size before selecting a layout strategy.
*   **Relative Spacing:** Use percentage-based widths or lex spacing for columns rather than fixed character counts.
*   **ARIA-like Labeling:** Using the persona's voice (e.g., "Bueno, I'm showing your tasks...") to provide spoken-word context before structured data blocks.

