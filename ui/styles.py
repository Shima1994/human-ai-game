import streamlit as st


def inject_css():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(208, 223, 255, 0.42), transparent 23%),
                linear-gradient(180deg, #f7f5f1 0%, #f3f0eb 100%);
            color: #243b53;
        }
        .block-container {
            max-width: 1120px;
            padding-top: 2.35rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebar"] {
            display: none;
        }
        h1, h2, h3, h4 {
            letter-spacing: -0.02em;
            color: #17324d;
        }
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
            box-shadow: 0 18px 44px rgba(20, 45, 68, 0.16);
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
            color: #fffdf8;
        }
        .hero-subtitle {
            font-size: 1rem;
            color: rgba(255, 249, 239, 0.92);
            margin-bottom: 0;
        }
        .hero-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 0.95rem;
        }
        .hero-badge {
            border-radius: 999px;
            padding: 0.42rem 0.8rem;
            font-size: 0.8rem;
            font-weight: 700;
            color: #fff8e6;
            background: rgba(255,255,255,0.14);
            border: 1px solid rgba(255,255,255,0.18);
        }
        .glass-card,
        .board-wrap {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(23, 50, 77, 0.10);
            border-radius: 22px;
            padding: 1rem 1.05rem;
            box-shadow: 0 8px 22px rgba(29, 53, 87, 0.06);
        }
        .compact-card {
            padding-top: 0.8rem;
            padding-bottom: 0.8rem;
        }
        .panel-title {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #73879b;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }
        .top-status-shell {
            background: rgba(245, 238, 225, 0.92);
            border: 1px solid rgba(212, 198, 171, 0.58);
            border-radius: 22px;
            padding: 0.95rem;
            margin-top: 0.85rem;
            margin-bottom: 1rem;
            box-shadow: 0 8px 24px rgba(115, 102, 75, 0.06);
        }
        .top-status {
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 0.75rem;
            margin-bottom: 0;
            align-items: stretch;
        }
        .status-pill {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(23, 50, 77, 0.10);
            border-radius: 16px;
            padding: 0.72rem 0.95rem 0.8rem 0.95rem;
            box-shadow: 0 6px 18px rgba(29, 53, 87, 0.05);
            min-height: 76px;
        }
        .status-label {
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #6f8599;
            margin-bottom: 0.28rem;
            font-weight: 800;
            line-height: 1.1;
            display: block;
        }
        .status-value {
            font-size: 1rem;
            font-weight: 800;
            color: #17324d;
            line-height: 1.2;
        }
        .round-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.7rem 1rem;
            border-radius: 999px;
            background: #e8f1fb;
            color: #1d5ea8;
            border: 1px solid rgba(29, 94, 168, 0.08);
            font-size: 0.95rem;
            font-weight: 800;
            margin-bottom: 0.95rem;
        }
        .word-card {
            box-sizing: border-box;
            border-radius: 16px;
            padding: 0.9rem 0.7rem;
            text-align: center;
            font-size: 0.98rem;
            font-weight: 800;
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
        }
        .word-hidden {
            background: linear-gradient(135deg, #2b68d8, #2f80ed);
            color: #eff6ff;
            border-color: rgba(255,255,255,0.25);
        }
        .word-target {
            background: #6b9f2a;
            color: #f7fff1;
        }
        .word-found {
            background: #175f13;
            color: #f5fff0;
            border-color: rgba(7, 55, 10, 0.35);
            box-shadow: inset 0 0 0 2px rgba(255,255,255,0.18), 0 10px 22px rgba(23, 95, 19, 0.18);
        }
        .word-neutral {
            background: #6d6a63;
            color: #f9f8f6;
        }
        .word-neutral-miss {
            background: #2f6f8f;
            color: #f0fbff;
        }
        .word-bomb {
            background: #b43232;
            color: #fff5f5;
        }
        .card-mark {
            font-size: 0.82rem;
            line-height: 1;
            opacity: 0.95;
        }
        .word-selected {
            outline: 4px solid #17324d;
            outline-offset: 2px;
            box-shadow: 0 0 0 6px rgba(255,255,255,0.75);
        }
        .legend {
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
            margin-top: 0.75rem;
        }
        .legend-pill {
            border-radius: 999px;
            padding: 0.34rem 0.72rem;
            font-size: 0.82rem;
            font-weight: 700;
            background: #fff;
            border: 1px solid rgba(23, 50, 77, 0.08);
        }
        .legend-target {
            color: #2f6e10;
            border-color: rgba(63, 123, 17, 0.20);
            background: rgba(63, 123, 17, 0.06);
        }
        .legend-neutral {
            color: #5c5a55;
            border-color: rgba(109, 106, 99, 0.22);
            background: rgba(109, 106, 99, 0.08);
        }
        .legend-neutral-miss {
            color: #245f7c;
            border-color: rgba(47, 111, 143, 0.22);
            background: rgba(47, 111, 143, 0.08);
        }
        .legend-bomb {
            color: #a12727;
            border-color: rgba(180, 50, 50, 0.20);
            background: rgba(180, 50, 50, 0.08);
        }
        .hint-card {
            background: linear-gradient(180deg, #f9fbff, #eef4fb);
            border: 1px solid rgba(29, 94, 168, 0.12);
            border-radius: 22px;
            padding: 0.95rem 1rem;
            box-shadow: 0 8px 18px rgba(29, 94, 168, 0.06);
            margin-bottom: 0.8rem;
        }
        .hint-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #6d85a0;
            font-weight: 800;
        }
        .hint-main {
            font-size: 2rem;
            line-height: 1;
            margin: 0.38rem 0 0.55rem 0;
            font-weight: 900;
            color: #17324d;
            letter-spacing: 0.05em;
        }
        .hint-chip-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        .hint-chip {
            border-radius: 999px;
            padding: 0.36rem 0.7rem;
            background: rgba(29, 94, 168, 0.08);
            color: #275b8c;
            font-weight: 700;
            font-size: 0.8rem;
        }
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
            border-radius: 18px;
            padding: 1rem 1.05rem;
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(23, 50, 77, 0.08);
            color: #4f6275;
            line-height: 1.48;
        }
        .guide-card h3 {
            margin: 0 0 0.55rem 0;
            font-size: 1.05rem;
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
            border-radius: 14px;
            padding: 0.62rem 0.72rem;
            background: rgba(29, 94, 168, 0.07);
            color: #275b8c;
            font-weight: 750;
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
            background: rgba(47, 111, 143, 0.08);
            border-color: rgba(47, 111, 143, 0.16);
        }
        .feature-list {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
            margin-top: 0.75rem;
        }
        .feature-item {
            border-radius: 18px;
            padding: 0.85rem 0.9rem;
            background: rgba(247, 250, 253, 0.9);
            border: 1px solid rgba(23, 50, 77, 0.08);
            color: #4f6275;
            line-height: 1.45;
        }
        .feature-item strong {
            display: block;
            color: #17324d;
            margin-bottom: 0.18rem;
        }
        .feature-target {
            background: rgba(63, 123, 17, 0.10);
            border-color: rgba(63, 123, 17, 0.18);
        }
        .feature-bomb {
            background: rgba(180, 50, 50, 0.10);
            border-color: rgba(180, 50, 50, 0.18);
        }
        .feature-neutral {
            background: rgba(109, 106, 99, 0.09);
            border-color: rgba(109, 106, 99, 0.16);
        }
        .choice-row {
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
        }
        .choice-pill {
            border-radius: 999px;
            padding: 0.42rem 0.76rem;
            background: rgba(29, 94, 168, 0.06);
            border: 1px solid rgba(29, 94, 168, 0.08);
            color: #275b8c;
            font-weight: 700;
            font-size: 0.82rem;
        }
        .mini-steps {
            display: grid;
            gap: 0.45rem;
            margin-top: 0.9rem;
        }
        .mini-step {
            border-radius: 14px;
            padding: 0.68rem 0.8rem;
            background: rgba(247, 250, 253, 0.9);
            border: 1px solid rgba(23, 50, 77, 0.08);
            color: #53677a;
            font-weight: 600;
        }
        .summary-stat {
            border-radius: 16px;
            padding: 0.82rem 0.95rem;
            background: rgba(255,255,255,0.88);
            border: 1px solid rgba(23, 50, 77, 0.08);
            margin-bottom: 0.7rem;
        }
        .summary-stat strong {
            color: #17324d;
        }
        .history-panel {
            border-radius: 18px;
            padding: 0.95rem;
            background: rgba(247,250,253,0.92);
            border: 1px solid rgba(23, 50, 77, 0.10);
            margin-top: 0.85rem;
            margin-bottom: 0.85rem;
        }
        .history-row {
            display: grid;
            grid-template-columns: 38px minmax(0, 1fr) auto;
            gap: 0.75rem;
            align-items: start;
            padding: 0.78rem;
            border: 1px solid rgba(23, 50, 77, 0.08);
            border-radius: 16px;
            background: rgba(255,255,255,0.86);
            margin-top: 0.58rem;
            color: #40566a;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        .history-index {
            width: 30px;
            height: 30px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #17324d;
            color: #fffdf8;
            font-weight: 900;
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
            border-radius: 999px;
            padding: 0.22rem 0.52rem;
            background: rgba(29, 94, 168, 0.08);
            color: #275b8c;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .history-hint-line {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            margin-bottom: 0.46rem;
        }
        .history-hint {
            color: #17324d;
            font-size: 1.08rem;
            font-weight: 950;
        }
        .history-detail {
            display: grid;
            grid-template-columns: 96px minmax(0, 1fr);
            gap: 0.45rem;
            align-items: start;
            margin-top: 0.28rem;
        }
        .history-detail-label {
            color: #17324d;
            font-weight: 850;
            font-size: 0.78rem;
        }
        .history-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
            min-width: 0;
        }
        .history-number {
            border-radius: 999px;
            padding: 0.18rem 0.46rem;
            background: rgba(29, 94, 168, 0.10);
            color: #1d5ea8;
            font-weight: 900;
            font-size: 0.78rem;
        }
        .history-chip {
            border-radius: 999px;
            padding: 0.2rem 0.48rem;
            background: rgba(23, 50, 77, 0.07);
            color: #34495f;
            font-size: 0.78rem;
            font-weight: 750;
            overflow-wrap: anywhere;
        }
        .history-chip.correct {
            background: rgba(23, 95, 19, 0.14);
            color: #175f13;
        }
        .history-chip.neutral {
            background: rgba(47, 111, 143, 0.12);
            color: #245f7c;
        }
        .history-chip.bomb {
            background: rgba(180, 50, 50, 0.14);
            color: #a12727;
        }
        .history-chip.muted {
            color: #7b8b9a;
            background: rgba(23, 50, 77, 0.04);
        }
        .history-outcome {
            justify-self: end;
            white-space: nowrap;
        }
        .history-outcome-correct {
            background: rgba(23, 95, 19, 0.12);
            color: #175f13;
        }
        .history-outcome-wrong {
            background: rgba(47, 111, 143, 0.10);
            color: #245f7c;
        }
        .history-outcome-bomb {
            background: rgba(180, 50, 50, 0.12);
            color: #a12727;
        }
        .history-outcome-skip {
            background: rgba(200, 128, 21, 0.14);
            color: #8a5208;
        }
        .history-skip-note {
            margin-top: 0.45rem;
            color: #8a5208;
            font-weight: 750;
            font-size: 0.82rem;
        }
        .history-empty {
            color: #66788a;
            font-weight: 700;
        }
        .medal-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }
        .medal {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.38rem 0.58rem;
            font-size: 1.05rem;
            font-weight: 950;
            line-height: 1;
            border: 1px solid rgba(23, 50, 77, 0.08);
        }
        .medal.gold {
            background: rgba(200, 128, 21, 0.24);
            color: #704400;
        }
        .medal.silver {
            background: rgba(109, 106, 99, 0.20);
            color: #403f3b;
        }
        .medal.bronze {
            background: rgba(142, 84, 38, 0.23);
            color: #5f3415;
        }
        .final-score {
            display: inline-flex;
            margin-top: 0.9rem;
            border-radius: 16px;
            padding: 0.7rem 0.95rem;
            background: rgba(29, 94, 168, 0.08);
            color: #17324d;
            font-weight: 950;
            font-size: 1.05rem;
        }
        .score-tiers {
            margin-top: 0.55rem;
            color: #66788a;
            font-size: 0.9rem;
            font-weight: 800;
        }
        .locked-board {
            filter: blur(2.2px);
            opacity: 0.48;
        }
        .section-gap {
            margin-top: 1rem;
        }
        .subtle-text {
            color: #66788a;
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .center-actions {
            max-width: 420px;
            margin: 0.95rem auto 0 auto;
        }
        .compact-field [data-baseweb="input"] input,
        .stTextInput input,
        .stSelectbox [data-baseweb="select"] > div {
            border-radius: 16px;
            background: #17324d;
            color: #fffdf8;
            border: 1px solid rgba(23, 50, 77, 0.10);
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
        .stTextInput input::placeholder {
            color: rgba(255, 253, 248, 0.62);
        }
        .stTextInput input:focus {
            color: #fffdf8;
            background: #17324d;
        }
        .stSelectbox [data-baseweb="select"] * {
            color: #fffdf8;
        }
        .stSelectbox [data-baseweb="select"] {
            min-width: 110px;
        }
        .stButton > button {
            border-radius: 16px;
            border: 1px solid rgba(23, 50, 77, 0.08);
            padding: 0.72rem 1rem;
            font-weight: 800;
            font-size: 0.96rem;
            background: linear-gradient(135deg, #1f5fa5, #2d6fb4);
            color: #fff;
            box-shadow: 0 8px 20px rgba(29, 94, 168, 0.14);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(29, 94, 168, 0.16);
        }
        .let-ai-guess-marker + div [data-testid="stButton"] > button,
        .let-ai-guess-marker + div button {
            background: linear-gradient(135deg, #9b4d11, #c88015);
            border-color: rgba(155, 77, 17, 0.28);
            box-shadow: 0 10px 24px rgba(155, 77, 17, 0.18);
        }
        .let-ai-guess-marker + div [data-testid="stButton"] > button:hover,
        .let-ai-guess-marker + div button:hover {
            box-shadow: 0 12px 26px rgba(155, 77, 17, 0.22);
        }
        .stButton > button[kind="secondary"],
        .stButton [data-testid="stBaseButton-secondary"] {
            height: 72px;
            min-height: 72px;
            max-height: 72px;
            overflow: hidden;
            border-radius: 16px;
            padding: 0.9rem 0.7rem;
            text-align: center;
            font-size: 0.98rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            margin-bottom: 0.7rem;
            background: linear-gradient(135deg, #2b68d8, #2f80ed);
            color: #eff6ff;
            border: 1px solid rgba(255,255,255,0.24);
            box-shadow: none;
        }
        .stButton > button[kind="secondary"]:hover,
        .stButton [data-testid="stBaseButton-secondary"]:hover {
            box-shadow: none;
        }
        .board-wrap .stButton > button {
            height: 72px;
            min-height: 72px;
            max-height: 72px;
            overflow: hidden;
            border-radius: 16px;
            background: linear-gradient(135deg, #2b68d8, #2f80ed);
            color: #eff6ff;
            border: 1px solid rgba(255,255,255,0.24);
            box-shadow: none;
        }
        .board-wrap .stButton > button:hover {
            box-shadow: none;
        }
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
            border-radius: 14px;
            padding: 0.45rem 0.6rem;
            background: rgba(255,255,255,0.85);
            border: 1px solid rgba(23, 50, 77, 0.08);
            min-width: 0;
            width: 100%;
            min-height: 46px;
            justify-content: center;
            margin: 0;
        }
        .stRadio label > div {
            justify-content: center;
        }
        .game-over-card {
            margin-bottom: 1rem;
        }
        .celebration-card {
            position: relative;
            overflow: hidden;
            border-color: rgba(200, 128, 21, 0.28);
            background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(255,248,232,0.92));
        }
        .celebration-medals {
            display: flex;
            gap: 0.55rem;
            font-size: 2.4rem;
            margin-bottom: 0.75rem;
            filter: drop-shadow(0 8px 12px rgba(115, 78, 16, 0.18));
        }
        @media (max-width: 900px) {
            .top-status-shell,
            .top-status,
            .welcome-grid,
            .guide-grid,
            .feature-list {
                grid-template-columns: 1fr;
            }
            .hero-title {
                font-size: 1.65rem;
            }
            .hint-main {
                font-size: 1.65rem;
            }
            .status-pill {
                min-height: auto;
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
        }
        @media (max-width: 640px) {
            .block-container {
                padding: 1rem 0.7rem 1.6rem 0.7rem;
            }
            .hero {
                border-radius: 18px;
                padding: 1rem;
            }
            .hero-title {
                font-size: 1.35rem;
                line-height: 1.12;
            }
            .hero-subtitle {
                font-size: 0.9rem;
            }
            .hero-badge {
                font-size: 0.74rem;
                padding: 0.34rem 0.58rem;
            }
            .top-status-shell {
                border-radius: 16px;
                padding: 0.65rem;
                margin-bottom: 0.75rem;
            }
            .top-status {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.55rem;
            }
            .status-pill {
                border-radius: 12px;
                padding: 0.58rem 0.62rem;
            }
            .status-label {
                font-size: 0.62rem;
                letter-spacing: 0.06em;
            }
            .status-value {
                font-size: 0.9rem;
                overflow-wrap: anywhere;
            }
            .guide-card,
            .glass-card {
                border-radius: 16px;
                padding: 0.85rem;
            }
            .guide-card {
                font-size: 0.9rem;
            }
            .guide-card h3 {
                font-size: 0.98rem;
            }
            .legend {
                gap: 0.38rem;
            }
            .legend-pill {
                font-size: 0.72rem;
                padding: 0.28rem 0.48rem;
            }
            div[data-testid="column"] {
                min-width: 0;
            }
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)) {
                display: flex;
                flex-wrap: wrap;
                gap: 0.35rem;
            }
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)) > div[data-testid="column"] {
                flex: 1 1 calc(33.333% - 0.35rem) !important;
                min-width: calc(33.333% - 0.35rem) !important;
                width: calc(33.333% - 0.35rem) !important;
            }
            .word-card,
            .stButton > button[kind="secondary"],
            .stButton [data-testid="stBaseButton-secondary"],
            .board-wrap .stButton > button {
                height: 58px;
                min-height: 58px;
                max-height: 58px;
                border-radius: 12px;
                padding: 0.55rem 0.35rem;
                font-size: 0.78rem;
                overflow-wrap: anywhere;
            }
            .hint-card {
                border-radius: 16px;
                padding: 0.8rem;
            }
            .hint-main {
                font-size: 1.35rem;
            }
            .history-row {
                grid-template-columns: 26px 1fr;
                gap: 0.48rem;
                font-size: 0.78rem;
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
                border-radius: 12px;
                padding: 0.68rem 0.75rem;
                font-size: 0.9rem;
            }
            .stRadio [role="radiogroup"] {
                grid-template-columns: repeat(5, minmax(38px, 1fr));
                gap: 0.32rem;
            }
            .stRadio label {
                min-height: 44px;
                padding: 0.35rem 0.25rem;
                border-radius: 12px;
            }
            .compact-field .stTextInput input {
                min-height: 62px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
