import streamlit as st


def inject_css():
    css = """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&display=swap" rel="stylesheet">
        <style>
        :root {
            --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            --font-reading: "Source Serif 4", Georgia, "Times New Roman", serif;
            --color-bg: #f6f4ef;
            --color-bg-alt: #efece5;
            --color-text: #1f2d3d;
            --color-text-soft: #5e6e80;
            --color-text-muted: #7f8a99;
            --color-heading: #122236;
            --color-card: rgba(255, 255, 255, 0.92);
            --color-card-soft: rgba(247, 250, 253, 0.95);
            --color-border: rgba(18, 34, 54, 0.08);
            --color-border-strong: rgba(18, 34, 54, 0.14);
            --color-shadow: 0 8px 24px rgba(18, 34, 54, 0.07);
            --color-shadow-strong: 0 14px 32px rgba(18, 34, 54, 0.12);
            --color-primary: #1d5ea8;
            --color-primary-strong: #154884;
            --color-primary-soft: rgba(29, 94, 168, 0.10);
            --color-secondary: #c98014;
            --color-secondary-soft: rgba(201, 128, 20, 0.14);
            --color-success: #3f7b11;
            --color-success-strong: #175f13;
            --color-success-soft: rgba(63, 123, 17, 0.12);
            --color-warn: #8a5208;
            --color-warn-soft: rgba(200, 128, 21, 0.16);
            --color-danger: #b43232;
            --color-danger-soft: rgba(180, 50, 50, 0.12);
            --color-info: #2f6f8f;
            --color-info-soft: rgba(47, 111, 143, 0.12);
            --color-target: #5b8e1f;
            --color-target-strong: #145e0f;
            --color-neutral: #6d6a63;
            --color-neutral-miss: #2f6f8f;
            --color-bomb: #b43232;
            --color-hidden-from: #2b68d8;
            --color-hidden-to: #2f80ed;
            --radius-sm: 10px;
            --radius-md: 14px;
            --radius-lg: 18px;
            --radius-xl: 22px;
            --radius-pill: 999px;
            --space-1: 0.35rem;
            --space-2: 0.6rem;
            --space-3: 0.85rem;
            --space-4: 1.1rem;
            --space-5: 1.5rem;
        }

        html, body, [class*="css"], .stApp {
            font-family: var(--font-sans);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(208, 223, 255, 0.42), transparent 23%),
                linear-gradient(180deg, var(--color-bg) 0%, var(--color-bg-alt) 100%);
            color: var(--color-text);
        }

        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        [data-testid="stSidebar"] {
            display: none;
        }

        h1, h2, h3, h4 {
            font-family: var(--font-sans);
            letter-spacing: -0.02em;
            color: var(--color-heading);
        }

        /* Hero */
        .hero {
            position: relative;
            overflow: hidden;
            background:
                radial-gradient(circle at 12% 18%, rgba(255,255,255,0.38), transparent 24%),
                linear-gradient(135deg, #163a5b 0%, #245f91 55%, #d09a2d 100%);
            border: 1px solid rgba(22, 58, 91, 0.08);
            border-radius: 28px;
            padding: 1.35rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--color-shadow-strong);
        }
        .hero-title {
            font-size: clamp(1.5rem, 2.2vw + 0.6rem, 2.1rem);
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.3rem;
            color: #fffdf8;
            letter-spacing: -0.02em;
        }
        .hero-subtitle {
            font-size: clamp(0.92rem, 0.4vw + 0.7rem, 1.02rem);
            color: rgba(255, 249, 239, 0.92);
            margin: 0;
            line-height: 1.45;
        }
        .hero-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 0.95rem;
        }
        .hero-badge {
            border-radius: var(--radius-pill);
            padding: 0.42rem 0.85rem;
            font-size: 0.8rem;
            font-weight: 700;
            color: #fff8e6;
            background: rgba(255, 255, 255, 0.16);
            border: 1px solid rgba(255, 255, 255, 0.22);
            backdrop-filter: blur(2px);
        }

        /* Cards */
        .glass-card,
        .board-wrap {
            background: var(--color-card);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-xl);
            padding: 1rem 1.05rem;
            box-shadow: var(--color-shadow);
        }
        .compact-card {
            padding-top: 0.8rem;
            padding-bottom: 0.8rem;
        }
        .panel-title {
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: var(--color-text-muted);
            margin-bottom: 0.5rem;
            font-weight: 700;
        }

        /* Top status pills */
        .top-status-shell {
            background: rgba(245, 238, 225, 0.92);
            border: 1px solid rgba(212, 198, 171, 0.58);
            border-radius: var(--radius-xl);
            padding: 0.95rem;
            margin-top: 0.85rem;
            margin-bottom: 1rem;
            box-shadow: 0 8px 24px rgba(115, 102, 75, 0.06);
        }
        .top-status {
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 0.7rem;
            align-items: stretch;
        }
        .status-pill {
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            padding: 0.7rem 0.85rem;
            box-shadow: 0 6px 16px rgba(29, 53, 87, 0.05);
            min-height: 74px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .status-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--color-text-muted);
            margin-bottom: 0.28rem;
            font-weight: 700;
            line-height: 1.1;
        }
        .status-value {
            font-size: 1rem;
            font-weight: 800;
            color: var(--color-heading);
            line-height: 1.2;
        }

        .round-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.65rem 1rem;
            border-radius: var(--radius-pill);
            background: var(--color-primary-soft);
            color: var(--color-primary);
            border: 1px solid rgba(29, 94, 168, 0.12);
            font-size: 0.92rem;
            font-weight: 800;
            margin-bottom: 0.95rem;
            letter-spacing: 0.02em;
        }

        /* Word board cards */
        .word-card {
            box-sizing: border-box;
            border-radius: var(--radius-md);
            padding: 0.9rem 0.7rem;
            text-align: center;
            font-size: 0.98rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            margin-bottom: 0.7rem;
            border: 1px solid transparent;
            height: 72px;
            min-height: 72px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 0.22rem;
            font-family: var(--font-sans);
        }
        .board-wrap [data-testid="stButton"],
        .board-wrap .element-container {
            margin-bottom: 0.7rem;
        }
        .board-wrap .word-card {
            margin-bottom: 0;
        }
        .word-hidden {
            background: linear-gradient(135deg, var(--color-hidden-from), var(--color-hidden-to));
            color: #eff6ff;
            border-color: rgba(255, 255, 255, 0.25);
        }
        .word-target {
            background: var(--color-target);
            color: #f7fff1;
        }
        .word-found {
            background: var(--color-target-strong);
            color: #f5fff0;
            border-color: rgba(7, 55, 10, 0.35);
            box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.18), 0 10px 22px rgba(23, 95, 19, 0.18);
        }
        .word-neutral {
            background: var(--color-neutral);
            color: #f9f8f6;
        }
        .word-neutral-miss {
            background: var(--color-neutral-miss);
            color: #f0fbff;
        }
        .word-bomb {
            background: var(--color-bomb);
            color: #fff5f5;
        }
        .card-mark {
            font-size: 0.82rem;
            line-height: 1;
            opacity: 0.95;
        }
        .word-selected {
            outline: 3px solid var(--color-heading);
            outline-offset: -4px;
            box-shadow: inset 0 0 0 3px rgba(255, 255, 255, 0.82);
        }

        /* Legend */
        .legend {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.75rem;
        }
        .legend-pill {
            border-radius: var(--radius-pill);
            padding: 0.32rem 0.7rem;
            font-size: 0.8rem;
            font-weight: 700;
            background: #fff;
            border: 1px solid var(--color-border);
        }
        .legend-target {
            color: #2f6e10;
            border-color: rgba(63, 123, 17, 0.20);
            background: var(--color-success-soft);
        }
        .legend-neutral {
            color: #5c5a55;
            border-color: rgba(109, 106, 99, 0.22);
            background: rgba(109, 106, 99, 0.08);
        }
        .legend-neutral-miss {
            color: #245f7c;
            border-color: rgba(47, 111, 143, 0.22);
            background: var(--color-info-soft);
        }
        .legend-bomb {
            color: #a12727;
            border-color: rgba(180, 50, 50, 0.20);
            background: var(--color-danger-soft);
        }

        /* Hint card (no explanation shown) */
        .hint-card {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: center;
            gap: 0.75rem;
            background: linear-gradient(135deg, #f3f8ff, #dcecff);
            border: 1px solid rgba(29, 94, 168, 0.22);
            border-radius: var(--radius-xl);
            padding: 0.82rem 1rem;
            box-shadow: 0 10px 24px rgba(29, 94, 168, 0.10);
            margin: 0.6rem 0 0.55rem 0;
        }
        .hint-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #315f91;
            font-weight: 800;
        }
        .hint-main {
            font-size: clamp(1.45rem, 2vw + 0.35rem, 2.05rem);
            line-height: 1.05;
            margin: 0.2rem 0 0 0;
            font-weight: 900;
            color: #0b4a8b;
            letter-spacing: 0.03em;
            word-break: break-word;
        }
        .hint-chip-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            justify-content: flex-end;
        }
        .hint-chip {
            border-radius: var(--radius-pill);
            padding: 0.34rem 0.72rem;
            background: #0b4a8b;
            color: #ffffff;
            font-weight: 800;
            font-size: 0.8rem;
            white-space: nowrap;
        }
        .guess-rationale-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 0.75rem;
            margin: 0.35rem 0 0.35rem 0;
        }
        .guess-rationale-head .panel-title {
            margin-bottom: 0;
        }
        .guess-rationale-rule {
            color: var(--color-text-muted);
            font-size: 0.82rem;
            font-weight: 700;
            text-align: right;
        }
        div[class*="st-key-guess_rationale_"] .stTextArea textarea {
            min-height: 88px;
            height: 88px;
            padding: 0.68rem 0.82rem;
            line-height: 1.35;
            background: #f6f8fb;
        }
        .guess-rationale-status {
            margin: 0.2rem 0 0.45rem 0;
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--color-text-muted);
        }
        .guess-rationale-status.ok {
            color: #207344;
        }
        .guess-rationale-status.pending {
            color: #9b4d11;
        }

        /* Guide / welcome screens */
        .welcome-grid {
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 0.9rem;
            margin-bottom: 0.9rem;
        }
        .guide-shell {
            display: grid;
            gap: 0.9rem;
            margin-bottom: 0.9rem;
        }
        .guide-intro .subtle-text {
            margin-bottom: 0;
            font-size: 1rem;
        }
        .guide-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
        }
        .guide-card {
            border-radius: var(--radius-lg);
            padding: 1rem 1.05rem;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid var(--color-border);
            color: var(--color-text-soft);
            line-height: 1.48;
        }
        .guide-card h3 {
            margin: 0 0 0.55rem 0;
            font-size: 1.05rem;
            font-weight: 800;
        }
        .guide-card p {
            margin: 0 0 0.55rem 0;
        }
        .guide-card ul,
        .guide-card ol {
            margin: 0.35rem 0 0 1.15rem;
            padding: 0;
        }
        .guide-card li {
            margin-bottom: 0.38rem;
        }
        .guide-example {
            border-radius: var(--radius-md);
            padding: 0.62rem 0.72rem;
            background: var(--color-primary-soft);
            color: var(--color-primary);
            font-weight: 700;
        }
        .guide-goal {
            background: rgba(63, 123, 17, 0.08);
            border-color: rgba(63, 123, 17, 0.16);
        }
        .guide-medals {
            background: rgba(200, 128, 21, 0.10);
            border-color: rgba(200, 128, 21, 0.18);
        }
        .guide-research {
            background: var(--color-info-soft);
            border-color: rgba(47, 111, 143, 0.18);
        }

        /* Research documents */
        .st-key-consent_document,
        .st-key-debriefing_document {
            max-width: 1120px;
            margin: 0 auto 1.1rem auto;
            padding: clamp(1.25rem, 3vw, 2.6rem) clamp(1.15rem, 4vw, 3.4rem);
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(18, 34, 54, 0.10);
            border-radius: 22px;
            box-shadow: 0 18px 48px rgba(18, 34, 54, 0.10);
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"],
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] {
            font-family: var(--font-reading);
            color: #26384a;
            font-size: 1.05rem;
            line-height: 1.78;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] > h1,
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] > h1 {
            font-family: var(--font-sans);
            font-size: clamp(1.55rem, 2.5vw, 2.05rem);
            line-height: 1.22;
            letter-spacing: -0.035em;
            margin: 0 auto 0.85rem auto;
            color: #12395f;
            text-align: center;
            text-wrap: balance;
        }
        .st-key-consent_logos {
            margin: 0 auto 1.25rem auto;
            padding-bottom: 1.15rem;
            border-bottom: 1px solid rgba(29, 94, 168, 0.14);
        }
        .st-key-consent_logos [data-testid="stImage"] {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 112px;
        }
        .st-key-consent_logos img {
            max-width: 100%;
            height: auto;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] > h2,
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] > h2 {
            font-family: var(--font-sans);
            font-size: 1.22rem;
            line-height: 1.35;
            margin: 2rem 0 0.8rem 0;
            color: #174f80;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] > h3,
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] > h3 {
            font-family: var(--font-sans);
            font-size: 1.04rem;
            line-height: 1.4;
            margin: 1.65rem 0 0.5rem 0;
            color: #183b5a;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] p,
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] p {
            margin: 0 0 1rem 0;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] > h2:first-of-type + p {
            text-align: center;
            line-height: 1.65;
            margin-left: auto;
            margin-right: auto;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] li,
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] li {
            margin-bottom: 0.48rem;
            padding-left: 0.2rem;
        }
        .st-key-consent_document [data-testid="stMarkdownContainer"] hr,
        .st-key-debriefing_document [data-testid="stMarkdownContainer"] hr {
            margin: 2.35rem 0;
            border-color: rgba(29, 94, 168, 0.18);
        }
        .st-key-consent_action_panel,
        .st-key-debriefing_action_panel {
            max-width: 1120px;
            margin: 0 auto;
        }
        .st-key-consent_action_panel [data-testid="stVerticalBlockBorderWrapper"],
        .st-key-debriefing_action_panel [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 1.05rem 1.15rem;
            background: rgba(238, 246, 255, 0.94);
            border: 1px solid rgba(29, 94, 168, 0.18);
            border-radius: 16px;
            box-shadow: 0 8px 24px rgba(18, 34, 54, 0.06);
        }
        .st-key-consent_action_panel .stCheckbox label,
        .st-key-debriefing_action_panel .stCheckbox label {
            font-weight: 650;
            color: var(--color-heading);
        }

        /* Summary stats and history */
        .summary-stat {
            border-radius: var(--radius-md);
            padding: 0.8rem 0.95rem;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid var(--color-border);
            margin-bottom: 0.7rem;
        }
        .summary-stat strong {
            color: var(--color-heading);
        }
        .history-panel {
            border-radius: var(--radius-lg);
            padding: 0.95rem;
            background: var(--color-card-soft);
            border: 1px solid var(--color-border);
            margin-top: 0.85rem;
            margin-bottom: 0.85rem;
        }
        .history-row {
            display: grid;
            grid-template-columns: 38px minmax(0, 1fr) auto;
            gap: 0.75rem;
            align-items: start;
            padding: 0.78rem;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            background: rgba(255, 255, 255, 0.92);
            margin-top: 0.55rem;
            color: var(--color-text-soft);
            font-size: 0.9rem;
            line-height: 1.4;
        }
        .history-index {
            width: 30px;
            height: 30px;
            border-radius: var(--radius-pill);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: var(--color-heading);
            color: #fffdf8;
            font-weight: 800;
        }
        .history-body {
            min-width: 0;
        }
        .history-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.38rem;
            margin-bottom: 0.3rem;
        }
        .history-meta span,
        .history-outcome {
            border-radius: var(--radius-pill);
            padding: 0.22rem 0.56rem;
            background: var(--color-primary-soft);
            color: var(--color-primary);
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .history-hint-line {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            margin-bottom: 0.46rem;
            flex-wrap: wrap;
        }
        .history-hint {
            color: var(--color-heading);
            font-size: 1.05rem;
            font-weight: 900;
            letter-spacing: 0.02em;
        }
        .history-detail {
            display: grid;
            grid-template-columns: 96px minmax(0, 1fr);
            gap: 0.45rem;
            align-items: start;
            margin-top: 0.28rem;
        }
        .history-detail-label {
            color: var(--color-heading);
            font-weight: 800;
            font-size: 0.76rem;
        }
        .history-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
            min-width: 0;
        }
        .history-number {
            border-radius: var(--radius-pill);
            padding: 0.18rem 0.5rem;
            background: rgba(29, 94, 168, 0.12);
            color: var(--color-primary);
            font-weight: 800;
            font-size: 0.78rem;
        }
        .history-chip {
            border-radius: var(--radius-pill);
            padding: 0.2rem 0.5rem;
            background: rgba(18, 34, 54, 0.07);
            color: #34495f;
            font-size: 0.78rem;
            font-weight: 700;
            overflow-wrap: anywhere;
        }
        .history-chip.correct {
            background: var(--color-success-soft);
            color: var(--color-success-strong);
        }
        .history-chip.neutral {
            background: var(--color-info-soft);
            color: #245f7c;
        }
        .history-chip.bomb {
            background: var(--color-danger-soft);
            color: #a12727;
        }
        .history-chip.muted {
            color: #7b8b9a;
            background: rgba(18, 34, 54, 0.05);
        }
        .history-outcome {
            justify-self: end;
            white-space: nowrap;
        }
        .history-outcome-correct {
            background: var(--color-success-soft);
            color: var(--color-success-strong);
        }
        .history-outcome-wrong {
            background: var(--color-info-soft);
            color: #245f7c;
        }
        .history-outcome-bomb {
            background: var(--color-danger-soft);
            color: #a12727;
        }
        .history-outcome-skip {
            background: var(--color-warn-soft);
            color: var(--color-warn);
        }
        .history-skip-note {
            margin-top: 0.45rem;
            color: var(--color-warn);
            font-weight: 700;
            font-size: 0.82rem;
        }
        .history-empty {
            color: var(--color-text-muted);
            font-weight: 600;
        }

        /* Medals */
        .medal-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        .medal {
            display: inline-flex;
            align-items: center;
            border-radius: var(--radius-pill);
            padding: 0.34rem 0.55rem;
            font-size: 1rem;
            font-weight: 900;
            line-height: 1;
            border: 1px solid var(--color-border);
        }
        .medal.gold {
            background: rgba(200, 128, 21, 0.22);
            color: #704400;
        }
        .medal.silver {
            background: rgba(109, 106, 99, 0.20);
            color: #403f3b;
        }
        .medal.bronze {
            background: rgba(142, 84, 38, 0.22);
            color: #5f3415;
        }
        .final-score {
            display: inline-flex;
            margin-top: 0.9rem;
            border-radius: var(--radius-md);
            padding: 0.7rem 0.95rem;
            background: var(--color-primary-soft);
            color: var(--color-heading);
            font-weight: 900;
            font-size: 1.05rem;
        }
        .score-tiers {
            margin-top: 0.55rem;
            color: var(--color-text-muted);
            font-size: 0.9rem;
            font-weight: 700;
        }
        .locked-board {
            filter: blur(2.2px);
            opacity: 0.48;
        }
        .section-gap {
            margin-top: 1rem;
        }
        .subtle-text {
            color: var(--color-text-muted);
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .center-actions {
            max-width: 420px;
            margin: 0.95rem auto 0 auto;
        }

        /* Reflection / explanation panel */
        .st-key-reflection_panel,
        .st-key-reflection_panel [data-testid="stVerticalBlockBorderWrapper"] {
            background: #F8F8F8 !important;
            border: 1px solid #E5E5E5 !important;
            border-radius: 12px !important;
            box-shadow: 0 8px 18px rgba(18, 34, 54, 0.06) !important;
        }
        .st-key-reflection_panel {
            padding: 0 !important;
        }
        .st-key-reflection_panel [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 1rem 1.05rem !important;
        }
        .st-key-reflection_panel [data-testid="stVerticalBlock"] {
            gap: 0.55rem !important;
        }
        .reflection-header {
            margin-bottom: 0.2rem;
        }
        .reflection-title {
            color: var(--color-heading);
            font-size: 1.02rem;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 0.22rem;
        }
        .reflection-subtitle {
            color: var(--color-text-soft);
            font-size: 0.9rem;
            line-height: 1.35;
        }
        .st-key-reflection_panel .subtle-text,
        .st-key-reflection_panel [data-testid="stCaptionContainer"],
        .st-key-reflection_panel [data-testid="stMarkdownContainer"] p {
            color: var(--color-text-soft) !important;
        }
        .st-key-reflection_panel label,
        .st-key-reflection_panel .stRadio label,
        .st-key-reflection_panel [data-testid="stWidgetLabel"],
        .st-key-reflection_panel [data-testid="stWidgetLabel"] p {
            color: var(--color-heading) !important;
            font-weight: 650;
        }
        .st-key-reflection_panel .reflection-ai-explanation {
            background: #FFFFFF !important;
            border: 1px solid #E5E5E5 !important;
            border-radius: 12px !important;
            padding: 0.62rem 0.78rem !important;
            box-shadow: 0 4px 12px rgba(18, 34, 54, 0.05) !important;
        }
        .st-key-reflection_panel .reflection-compact-head {
            margin-bottom: 0.1rem !important;
        }
        .st-key-reflection_panel .reflection-compact-head .panel-title {
            margin-bottom: 0.22rem;
        }
        .st-key-reflection_panel .reflection-compact-head .subtle-text {
            font-size: 0.86rem;
            line-height: 1.28;
        }
        .st-key-reflection_panel .reflection-ai-explanation .panel-title {
            color: var(--color-text-muted);
        }
        .st-key-reflection_panel .stRadio [role="radiogroup"] {
            margin-top: 0.28rem;
        }
        .st-key-reflection_panel .stRadio label {
            background: #FFFFFF !important;
            border: 1px solid #E5E5E5 !important;
            color: var(--color-heading) !important;
            min-height: 42px;
            padding: 0.35rem 0.5rem;
        }
        .st-key-reflection_panel .stRadio label:hover {
            border-color: rgba(29, 94, 168, 0.32) !important;
            background: #F3F7FC !important;
        }
        .st-key-reflection_panel .stSelectbox [data-baseweb="select"] > div {
            background: #FFFFFF !important;
            color: var(--color-heading) !important;
            border: 1px solid #E0E0E0 !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }
        .st-key-reflection_panel .stTextArea textarea {
            background: #EEF0F3 !important;
            color: #111827 !important;
            border: 1px solid #D5DAE1 !important;
            border-radius: 10px !important;
            min-height: 78px;
            height: 78px;
            padding: 0.65rem 0.78rem;
            box-shadow: none !important;
        }
        .st-key-reflection_panel .stTextArea textarea::placeholder {
            color: #6B7280 !important;
        }
        .st-key-reflection_panel .stTextArea textarea:focus {
            border-color: rgba(29, 94, 168, 0.42) !important;
            box-shadow: 0 0 0 3px rgba(29, 94, 168, 0.14) !important;
            background: #EEF0F3 !important;
            color: #111827 !important;
        }
        .st-key-reflection_panel .stSelectbox [data-baseweb="select"] > div:focus-within {
            border-color: rgba(29, 94, 168, 0.34) !important;
            box-shadow: 0 0 0 3px rgba(29, 94, 168, 0.12) !important;
            background: #FFFFFF !important;
        }
        .st-key-reflection_panel .stSelectbox [data-baseweb="select"] * {
            color: var(--color-heading) !important;
        }
        div[data-baseweb="popover"] [role="listbox"] {
            background: #FFFFFF !important;
            border: 1px solid #E0E0E0 !important;
            color: var(--color-heading) !important;
        }
        div[data-baseweb="popover"] [role="option"] {
            background: #FFFFFF !important;
            color: var(--color-heading) !important;
        }
        div[data-baseweb="popover"] [role="option"]:hover {
            background: #F3F7FC !important;
        }

        /* Inputs */
        .stTextInput input,
        .stSelectbox [data-baseweb="select"] > div,
        .stTextArea textarea {
            border-radius: var(--radius-md);
            background: #EEF0F3;
            color: #111827;
            border: 1px solid #D5DAE1;
            font-family: var(--font-sans);
        }
        .stTextArea textarea {
            min-height: 140px;
            line-height: 1.45;
            padding: 0.85rem 1rem;
        }
        .compact-field .stTextInput input {
            min-height: 58px;
            font-size: 1.05rem;
            padding: 0.85rem 1rem;
        }
        .name-card {
            max-width: 420px;
            margin: 0 auto 0.35rem auto;
        }
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: #6B7280;
        }
        .stTextInput input:focus,
        .stTextArea textarea:focus {
            color: #111827;
            background: #EEF0F3;
            border-color: rgba(29, 94, 168, 0.42);
            box-shadow: 0 0 0 3px rgba(29, 94, 168, 0.14);
            outline: none;
        }
        .stSelectbox [data-baseweb="select"] * {
            color: #111827;
        }
        .stSelectbox [data-baseweb="select"] {
            min-width: 110px;
        }

        /* Buttons */
        .stButton > button,
        .stButton button,
        [data-testid="stButton"] > button,
        [data-testid="stButton"] button,
        button[data-baseweb="button"] {
            border-radius: var(--radius-md);
            border: 1px solid rgba(18, 34, 54, 0.08);
            padding: 0.72rem 1rem;
            font-weight: 700;
            font-size: 0.96rem;
            background: linear-gradient(135deg, var(--color-primary-strong), var(--color-primary));
            color: #FFFFFF !important;
            box-shadow: 0 8px 18px rgba(29, 94, 168, 0.14);
            transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
            font-family: var(--font-sans);
            letter-spacing: 0.01em;
        }
        .stButton > button *,
        .stButton button *,
        [data-testid="stButton"] > button *,
        [data-testid="stButton"] button *,
        button[data-baseweb="button"] * {
            color: #FFFFFF !important;
        }
        .stButton > button:hover,
        .stButton button:hover,
        [data-testid="stButton"] > button:hover,
        [data-testid="stButton"] button:hover,
        button[data-baseweb="button"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(29, 94, 168, 0.18);
            filter: brightness(1.05);
        }
        .stButton > button:focus,
        .stButton button:focus,
        [data-testid="stButton"] > button:focus,
        [data-testid="stButton"] button:focus,
        button[data-baseweb="button"]:focus {
            box-shadow: 0 0 0 3px rgba(45, 111, 180, 0.28);
            outline: none;
        }
        .stButton > button:disabled,
        .stButton button:disabled,
        [data-testid="stButton"] > button:disabled,
        [data-testid="stButton"] button:disabled,
        button[data-baseweb="button"]:disabled {
            opacity: 0.55;
            cursor: not-allowed;
            transform: none;
            filter: grayscale(0.2);
        }
        .let-ai-guess-marker + div [data-testid="stButton"] > button,
        .let-ai-guess-marker + div button {
            background: linear-gradient(135deg, #9b4d11, var(--color-secondary));
            border-color: rgba(155, 77, 17, 0.28);
            box-shadow: 0 10px 22px rgba(155, 77, 17, 0.18);
        }
        .let-ai-guess-marker + div [data-testid="stButton"] > button:hover,
        .let-ai-guess-marker + div button:hover {
            box-shadow: 0 12px 26px rgba(155, 77, 17, 0.22);
        }
        .st-key-before_ai_guess_panel,
        .st-key-before_ai_guess_panel [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--color-card) !important;
            border-color: var(--color-border) !important;
            border-radius: var(--radius-xl) !important;
            box-shadow: var(--color-shadow) !important;
        }
        .st-key-before_ai_guess_panel {
            margin-top: 1rem;
        }
        .st-key-before_ai_guess_panel [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.72rem 0.9rem !important;
        }
        .st-key-before_ai_guess_panel [data-testid="stVerticalBlock"] {
            gap: 0.2rem !important;
        }
        .st-key-before_ai_guess_panel .before-ai-question {
            margin: 0 !important;
            line-height: 1.25;
        }
        .st-key-before_ai_guess_panel .stRadio [role="radiogroup"] {
            margin-top: 0;
            grid-template-columns: repeat(5, minmax(42px, 1fr));
            gap: 0.38rem;
        }
        .st-key-before_ai_guess_panel .stRadio label {
            min-height: 42px;
            padding: 0.32rem 0.45rem;
        }
        .st-key-post_game_questionnaire_panel,
        .st-key-post_game_questionnaire_panel [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--color-card) !important;
            border-color: var(--color-border) !important;
            border-radius: var(--radius-xl) !important;
            box-shadow: var(--color-shadow) !important;
        }
        .st-key-post_game_questionnaire_panel {
            margin-top: 1rem;
        }
        .st-key-post_game_questionnaire_panel [data-testid="stVerticalBlock"] {
            gap: 0.55rem !important;
        }
        .st-key-post_game_questionnaire_panel .stRadio {
            padding: 0.55rem 0;
            border-top: 1px solid rgba(18, 34, 54, 0.08);
        }
        .st-key-post_game_questionnaire_panel .stRadio [role="radiogroup"] {
            grid-template-columns: repeat(5, minmax(42px, 1fr));
            max-width: 360px;
            margin-top: 0.32rem;
        }
        .st-key-post_game_questionnaire_panel .stRadio label {
            min-height: 40px;
            padding: 0.32rem 0.48rem;
        }
        .st-key-post_game_questionnaire_panel [data-testid="stWidgetLabel"] p {
            color: var(--color-heading) !important;
            font-weight: 700;
            line-height: 1.25;
        }
        .st-key-participant_profile_panel,
        .st-key-participant_profile_panel [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--color-card) !important;
            border-color: var(--color-border) !important;
            border-radius: var(--radius-xl) !important;
            box-shadow: var(--color-shadow) !important;
        }
        .st-key-participant_profile_panel {
            margin: 0 auto;
            max-width: 960px;
        }
        .st-key-participant_profile_panel [data-testid="stVerticalBlock"] {
            gap: 0.6rem !important;
        }
        .st-key-participant_profile_panel .stRadio {
            padding-top: 0.35rem;
        }
        .st-key-participant_profile_panel .stRadio [role="radiogroup"] {
            display: flex !important;
            flex-wrap: wrap;
            gap: 0.45rem;
            width: 100%;
        }
        .st-key-participant_profile_panel .stRadio label {
            width: auto;
            min-height: 42px;
            min-width: 0;
            padding: 0.42rem 0.68rem;
            justify-content: flex-start;
            white-space: nowrap;
        }
        .st-key-participant_profile_panel .stRadio label > div {
            justify-content: flex-start;
        }
        .st-key-participant_profile_panel [data-testid="stWidgetLabel"] p {
            color: var(--color-heading) !important;
            font-weight: 750;
            line-height: 1.25;
        }
        .stButton > button[kind="secondary"],
        .stButton button[kind="secondary"],
        .stButton [data-testid="stBaseButton-secondary"],
        [data-testid="stButton"] button[kind="secondary"] {
            height: 72px;
            min-height: 72px;
            max-height: 72px;
            overflow: hidden;
            border-radius: var(--radius-md);
            padding: 0.9rem 0.7rem;
            text-align: center;
            font-size: 0.98rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            margin-bottom: 0.7rem;
            background: linear-gradient(135deg, var(--color-hidden-from), var(--color-hidden-to));
            color: #eff6ff;
            border: 1px solid rgba(255, 255, 255, 0.24);
            box-shadow: none;
        }
        .stButton > button[kind="secondary"]:hover,
        .stButton button[kind="secondary"]:hover,
        .stButton [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stButton"] button[kind="secondary"]:hover {
            box-shadow: none;
        }
        .board-wrap .stButton > button,
        .board-wrap .stButton button,
        .board-wrap [data-testid="stButton"] > button,
        .board-wrap [data-testid="stButton"] button {
            height: 72px;
            min-height: 72px;
            max-height: 72px;
            overflow: hidden;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, var(--color-hidden-from), var(--color-hidden-to));
            color: #eff6ff;
            border: 1px solid rgba(255, 255, 255, 0.24);
            box-shadow: none;
        }
        .board-wrap .stButton > button:hover,
        .board-wrap .stButton button:hover,
        .board-wrap [data-testid="stButton"] > button:hover,
        .board-wrap [data-testid="stButton"] button:hover {
            box-shadow: none;
        }

        /* Radio (rating) groups */
        .stRadio > div {
            gap: 0.45rem;
        }
        .stRadio [role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(5, minmax(44px, 1fr));
            gap: 0.45rem;
            width: 100%;
        }
        .stRadio label {
            border-radius: var(--radius-md);
            padding: 0.45rem 0.6rem;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid var(--color-border);
            min-width: 0;
            width: 100%;
            min-height: 46px;
            justify-content: center;
            margin: 0;
            transition: border-color 0.15s ease, background 0.15s ease;
        }
        .stRadio label:hover {
            border-color: var(--color-primary);
        }
        .stRadio label > div {
            justify-content: center;
        }

        /* Game-over card */
        .game-over-card {
            margin-bottom: 1rem;
        }
        .celebration-card {
            position: relative;
            overflow: hidden;
            border-color: rgba(200, 128, 21, 0.28);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(255, 248, 232, 0.94));
        }
        .celebration-medals {
            display: flex;
            gap: 0.55rem;
            font-size: 2.4rem;
            margin-bottom: 0.75rem;
            filter: drop-shadow(0 8px 12px rgba(115, 78, 16, 0.18));
        }

        /* Streamlit "info / warning" alerts use the theme too */
        div[data-testid="stAlert"] {
            border-radius: var(--radius-md);
            border: 1px solid var(--color-border-strong);
            font-family: var(--font-sans);
        }

        /* Tablet */
        @media (max-width: 900px) {
            .block-container {
                padding-top: 1.4rem;
                padding-bottom: 1.6rem;
            }
            .top-status {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .welcome-grid,
            .guide-grid {
                grid-template-columns: 1fr;
            }
            .hint-main {
                font-size: 1.65rem;
            }
            .status-pill {
                min-height: 68px;
                padding: 0.6rem 0.7rem;
            }
            .word-card,
            .stButton > button[kind="secondary"],
            .stButton [data-testid="stBaseButton-secondary"],
            .board-wrap .stButton > button {
                height: 64px;
                min-height: 64px;
                max-height: 64px;
                font-size: 0.9rem;
            }
            .history-detail {
                grid-template-columns: 84px 1fr;
            }
        }

        /* Phone */
        @media (max-width: 640px) {
            .block-container {
                padding: 0.9rem 0.65rem 1.6rem 0.65rem;
            }
            .hero {
                border-radius: var(--radius-lg);
                padding: 0.95rem;
            }
            .hero-title {
                font-size: 1.3rem;
                line-height: 1.15;
            }
            .hero-subtitle {
                font-size: 0.88rem;
            }
            .hero-badge {
                font-size: 0.7rem;
                padding: 0.3rem 0.55rem;
            }
            .top-status-shell {
                border-radius: var(--radius-lg);
                padding: 0.6rem;
                margin-bottom: 0.7rem;
            }
            .top-status {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.5rem;
            }
            .status-pill {
                border-radius: var(--radius-sm);
                padding: 0.55rem 0.6rem;
                min-height: 58px;
            }
            .status-label {
                font-size: 0.6rem;
                letter-spacing: 0.08em;
            }
            .status-value {
                font-size: 0.88rem;
                overflow-wrap: anywhere;
            }
            .medal-row {
                gap: 0.28rem;
            }
            .medal {
                padding: 0.26rem 0.42rem;
                font-size: 0.88rem;
            }
            .guide-card,
            .glass-card {
                border-radius: var(--radius-md);
                padding: 0.85rem;
            }
            .guide-card {
                font-size: 0.9rem;
            }
            .guide-card h3 {
                font-size: 0.98rem;
            }
            .st-key-consent_document,
            .st-key-debriefing_document {
                border-radius: 15px;
                padding: 1.15rem 1rem;
            }
            .st-key-consent_document [data-testid="stMarkdownContainer"],
            .st-key-debriefing_document [data-testid="stMarkdownContainer"] {
                font-size: 0.98rem;
                line-height: 1.7;
            }
            .legend {
                gap: 0.32rem;
            }
            .legend-pill {
                font-size: 0.7rem;
                padding: 0.26rem 0.46rem;
            }
            div[data-testid="column"] {
                min-width: 0;
            }
            /* Board grid: 3 columns on phones for better tap targets */
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(5)) {
                display: grid !important;
                grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
                gap: 0.4rem !important;
            }
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(5)) > div[data-testid="column"] {
                width: 100% !important;
                min-width: 0 !important;
                flex: unset !important;
            }
            /* 4-column blocks (hint target selector etc.) get 2 columns on phone */
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)):not(:has(> div[data-testid="column"]:nth-child(5))) {
                display: grid !important;
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                gap: 0.4rem !important;
            }
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)):not(:has(> div[data-testid="column"]:nth-child(5))) > div[data-testid="column"] {
                width: 100% !important;
                min-width: 0 !important;
                flex: unset !important;
            }
            .word-card,
            .stButton > button[kind="secondary"],
            .stButton [data-testid="stBaseButton-secondary"],
            .board-wrap .stButton > button {
                height: 56px;
                min-height: 56px;
                max-height: 56px;
                border-radius: var(--radius-sm);
                padding: 0.5rem 0.35rem;
                font-size: 0.78rem;
                overflow-wrap: anywhere;
                line-height: 1.1;
            }
            .hint-card {
                grid-template-columns: 1fr;
                gap: 0.55rem;
                border-radius: var(--radius-md);
                padding: 0.78rem;
            }
            .hint-main {
                font-size: 1.35rem;
            }
            .hint-chip-row {
                justify-content: flex-start;
            }
            .guess-rationale-head {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.18rem;
            }
            .guess-rationale-rule {
                text-align: left;
            }
            div[class*="st-key-guess_rationale_"] .stTextArea textarea {
                min-height: 82px;
                height: 82px;
            }
            .st-key-reflection_panel .stTextArea textarea {
                min-height: 72px;
                height: 72px;
            }
            .history-row {
                grid-template-columns: 26px 1fr;
                gap: 0.45rem;
                font-size: 0.82rem;
                padding: 0.62rem;
            }
            .history-outcome {
                grid-column: 2;
                justify-self: start;
            }
            .history-detail {
                grid-template-columns: 1fr;
                gap: 0.18rem;
            }
            .history-hint {
                font-size: 0.98rem;
            }
            .summary-stat {
                border-radius: var(--radius-sm);
                padding: 0.6rem 0.7rem;
                font-size: 0.9rem;
            }
            .stRadio [role="radiogroup"] {
                grid-template-columns: repeat(5, minmax(36px, 1fr));
                gap: 0.28rem;
            }
            .stRadio label {
                min-height: 42px;
                padding: 0.32rem 0.2rem;
                border-radius: var(--radius-sm);
                font-size: 0.78rem;
            }
            .compact-field .stTextInput input {
                min-height: 58px;
            }
            .stTextInput input,
            .stSelectbox [data-baseweb="select"] > div {
                min-height: 50px;
                font-size: 0.95rem;
            }
            .stButton > button {
                padding: 0.7rem 0.85rem;
                font-size: 0.92rem;
            }
            .final-score {
                font-size: 0.95rem;
                padding: 0.6rem 0.8rem;
            }
            .celebration-medals {
                font-size: 1.9rem;
            }
        }

        /* Very narrow phones */
        @media (max-width: 380px) {
            .top-status {
                grid-template-columns: 1fr;
            }
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(5)) {
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            }
        }
        </style>
        """
    if hasattr(st, "html"):
        st.html(css)
    else:
        st.markdown(css, unsafe_allow_html=True)
