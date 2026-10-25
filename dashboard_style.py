"""Comprehensive design system for Diablos Stuff+ dashboards."""
import streamlit as st


def apply_dashboard_style():
    st.markdown(
        """
        <style>
        /* ========================================================================
           DESIGN TOKENS — Diablos Rojos del México
           ======================================================================== */
        :root {
          /* Brand */
          --brand-primary: #cf202e;
          --brand-primary-hover: #ad1830;
          --brand-primary-light: #fff1f3;
          --brand-primary-muted: #fef2f4;
          
          /* Neutral Scale */
          --ink-900: #111317;
          --ink-700: #2a2e35;
          --ink-500: #565d6a;
          --ink-400: #717a8a;
          --ink-300: #9aa3af;
          --ink-200: #c8ced6;
          --ink-100: #e8ebef;
          --ink-50: #f5f6f8;
          --white: #ffffff;
          
          /* Semantic */
          --text-primary: var(--ink-900);
          --text-secondary: var(--ink-500);
          --text-muted: var(--ink-400);
          --text-inverse: var(--white);
          --text-link: var(--brand-primary);
          
          --bg-page: var(--ink-50);
          --bg-surface: var(--white);
          --bg-surface-hover: var(--ink-50);
          --bg-elevated: var(--white);
          
          --border-subtle: var(--ink-100);
          --border-default: var(--ink-200);
          --border-strong: var(--ink-300);
          --border-focus: var(--brand-primary);
          
          /* Status */
          --success: #1a7f37;
          --success-bg: #eef7f0;
          --success-border: #c8e6d1;
          --warning: #b86b00;
          --warning-bg: #fff8e1;
          --warning-border: #ffe08a;
          --error: #c0392b;
          --error-bg: #fdf2f2;
          --error-border: #f5c6c6;
          --info: #1d6ec7;
          --info-bg: #eef3fa;
          --info-border: #c5dbf5;
          
          /* Spacing Scale (base 4px) */
          --space-0: 0;
          --space-1: 0.25rem;   /* 4px */
          --space-2: 0.5rem;    /* 8px */
          --space-3: 0.75rem;   /* 12px */
          --space-4: 1rem;      /* 16px */
          --space-5: 1.25rem;   /* 20px */
          --space-6: 1.5rem;    /* 24px */
          --space-8: 2rem;      /* 32px */
          --space-10: 2.5rem;   /* 40px */
          --space-12: 3rem;     /* 48px */
          --space-16: 4rem;     /* 64px */
          
          /* Border Radius */
          --radius-sm: 6px;
          --radius-md: 8px;
          --radius-lg: 12px;
          --radius-xl: 16px;
          --radius-full: 9999px;
          
          /* Shadows */
          --shadow-xs: 0 1px 2px rgba(17, 19, 23, 0.04);
          --shadow-sm: 0 1px 3px rgba(17, 19, 23, 0.06), 0 1px 2px rgba(17, 19, 23, 0.04);
          --shadow-md: 0 4px 8px rgba(17, 19, 23, 0.06), 0 2px 4px rgba(17, 19, 23, 0.04);
          --shadow-lg: 0 12px 24px rgba(17, 19, 23, 0.08), 0 4px 8px rgba(17, 19, 23, 0.04);
          --shadow-xl: 0 20px 40px rgba(17, 19, 23, 0.1), 0 8px 16px rgba(17, 19, 23, 0.06);
          
          /* Transitions */
          --transition-fast: 120ms ease;
          --transition-base: 200ms ease;
          --transition-slow: 300ms ease;
          
          /* Typography */
          --font-sans: "Inter", "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          --font-mono: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
          
          --text-xs: 0.7rem;
          --text-sm: 0.8125rem;
          --text-base: 0.9375rem;
          --text-lg: 1.0625rem;
          --text-xl: 1.25rem;
          --text-2xl: 1.5rem;
          --text-3xl: 1.875rem;
          --text-4xl: 2.25rem;
          
          --leading-tight: 1.15;
          --leading-snug: 1.35;
          --leading-normal: 1.55;
          --leading-relaxed: 1.65;
          
          /* Layout */
          --container-max: 1320px;
          --sidebar-width: 280px;
          --header-height: 56px;
        }
        
        /* ========================================================================
           BASE & RESET
           ======================================================================== */
        .stApp {
          background: var(--bg-page);
          color: var(--text-primary);
          font-family: var(--font-sans);
        }
        
        [data-testid="stAppViewContainer"] > .main .block-container {
          max-width: var(--container-max);
          padding: var(--space-6) var(--space-6) var(--space-10);
        }
        
        @media (max-width: 768px) {
          [data-testid="stAppViewContainer"] > .main .block-container {
            padding: var(--space-4) var(--space-4) var(--space-8);
          }
        }
        
        /* Hide default Streamlit header bar */
        [data-testid="stHeader"] {
          background: rgba(245, 246, 248, 0.92);
          backdrop-filter: blur(8px);
          border-bottom: 1px solid var(--border-subtle);
        }
        
        /* ========================================================================
           TYPOGRAPHY
           ======================================================================== */
        h1, h2, h3, h4, h5, h6 {
          color: var(--ink-900);
          letter-spacing: -0.02em;
          line-height: var(--leading-tight);
          font-weight: 700;
        }
        
        h1 {
          font-size: clamp(var(--text-2xl), 3.5vw, var(--text-4xl));
          margin-bottom: var(--space-2);
        }
        
        h2 {
          font-size: clamp(var(--text-xl), 2.5vw, var(--text-2xl));
          margin-top: var(--space-6);
          margin-bottom: var(--space-3);
        }
        
        h3 {
          font-size: var(--text-lg);
          margin-top: var(--space-5);
          margin-bottom: var(--space-2);
          font-weight: 650;
        }
        
        h4 {
          font-size: var(--text-base);
          margin-top: var(--space-4);
          margin-bottom: var(--space-2);
          font-weight: 650;
        }
        
        p, li, label, [data-testid="stCaptionContainer"] {
          color: var(--ink-500);
          line-height: var(--leading-normal);
          font-size: var(--text-base);
        }
        
        .stMarkdown p:last-child {
          margin-bottom: 0;
        }
        
        strong, b {
          color: var(--ink-700);
          font-weight: 650;
        }
        
        code, [data-testid="stCode"] {
          font-family: var(--font-mono);
          font-size: 0.85em;
          background: var(--ink-100);
          padding: 0.15em 0.4em;
          border-radius: var(--radius-sm);
        }
        
        pre {
          background: var(--ink-900);
          color: var(--ink-100);
          border-radius: var(--radius-lg);
          padding: var(--space-4);
          overflow-x: auto;
        }
        
        pre code {
          background: transparent;
          padding: 0;
          color: inherit;
        }
        
        a {
          color: var(--brand-primary);
          text-decoration: none;
          font-weight: 500;
        }
        
        a:hover {
          text-decoration: underline;
        }
        
        /* ========================================================================
           SIDEBAR
           ======================================================================== */
        [data-testid="stSidebar"] {
          background: var(--bg-surface);
          border-right: 1px solid var(--border-subtle);
          min-width: var(--sidebar-width);
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
          color: var(--ink-500);
        }
        
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
          color: var(--ink-900);
        }
        
        [data-testid="stSidebar"] [role="radiogroup"] label {
          padding: var(--space-2) var(--space-3);
          border-radius: var(--radius-md);
          margin: var(--space-1) 0;
          transition: all var(--transition-fast);
          font-weight: 500;
        }
        
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
          background: var(--bg-surface-hover);
        }
        
        [data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
          color: var(--brand-primary);
          background: var(--brand-primary-light);
          font-weight: 600;
        }
        
        [data-testid="stSidebar"] [data-testid="stSelectbox"] {
          margin-top: var(--space-3);
        }
        
        /* Sidebar section headers */
        .sidebar-section {
          padding: var(--space-3) var(--space-3) var(--space-1);
          font-size: var(--text-xs);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--ink-400);
        }
        
        /* ========================================================================
           TABS
           ======================================================================== */
        [data-testid="stTabs"] [role="tablist"] {
          border-bottom: 1px solid var(--border-subtle);
          gap: var(--space-1);
          padding-bottom: 1px;
        }
        
        [data-testid="stTabs"] button[role="tab"] {
          padding: var(--space-3) var(--space-4);
          color: var(--ink-500);
          font-weight: 600;
          font-size: var(--text-sm);
          border-radius: var(--radius-md) var(--radius-md) 0 0;
          background: transparent;
          border: none;
          border-bottom: 2px solid transparent;
          transition: all var(--transition-fast);
        }
        
        [data-testid="stTabs"] button[role="tab"]:hover {
          color: var(--ink-700);
          background: var(--bg-surface-hover);
        }
        
        [data-testid="stTabs"] button[aria-selected="true"] {
          color: var(--brand-primary);
          border-bottom-color: var(--brand-primary);
          background: var(--brand-primary-muted);
        }
        
        [data-testid="stTabs"] [role="tabpanel"] {
          padding-top: var(--space-5);
        }
        
        /* ========================================================================
           METRICS
           ======================================================================== */
        [data-testid="stMetric"] {
          background: var(--bg-surface);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          padding: var(--space-4) var(--space-5);
          min-height: 104px;
          box-shadow: var(--shadow-xs);
          transition: all var(--transition-fast);
        }
        
        [data-testid="stMetric"]:hover {
          border-color: var(--border-default);
          box-shadow: var(--shadow-sm);
        }
        
        [data-testid="stMetricLabel"] {
          color: var(--ink-500);
          font-size: var(--text-sm);
          font-weight: 500;
          letter-spacing: 0.01em;
        }
        
        [data-testid="stMetricValue"] {
          color: var(--ink-900);
          font-weight: 700;
          font-size: clamp(var(--text-2xl), 3vw, var(--text-3xl));
          line-height: var(--leading-tight);
        }
        
        [data-testid="stMetricDelta"] {
          font-size: var(--text-sm);
          font-weight: 500;
        }
        
        [data-testid="stMetricDelta"] [style*="color: rgb(0, 128, 0)"] {
          color: var(--success) !important;
        }
        
        [data-testid="stMetricDelta"] [style*="color: rgb(255, 0, 0)"] {
          color: var(--error) !important;
        }
        
        /* ========================================================================
           BUTTONS
           ======================================================================== */
        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button {
          border-radius: var(--radius-md);
          padding: var(--space-2) var(--space-4);
          font-weight: 600;
          font-size: var(--text-sm);
          min-height: 40px;
          transition: all var(--transition-fast);
          border: 1px solid transparent;
        }
        
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stDownloadButton"] button[kind="primary"] {
          background: var(--brand-primary);
          border-color: var(--brand-primary);
          color: var(--white);
        }
        
        [data-testid="stButton"] button[kind="primary"]:hover,
        [data-testid="stDownloadButton"] button[kind="primary"]:hover {
          background: var(--brand-primary-hover);
          border-color: var(--brand-primary-hover);
        }
        
        [data-testid="stButton"] button[kind="secondary"],
        [data-testid="stDownloadButton"] button[kind="secondary"] {
          background: var(--bg-surface);
          border-color: var(--border-default);
          color: var(--ink-700);
        }
        
        [data-testid="stButton"] button[kind="secondary"]:hover,
        [data-testid="stDownloadButton"] button[kind="secondary"]:hover {
          background: var(--bg-surface-hover);
          border-color: var(--border-strong);
        }
        
        [data-testid="stButton"] button:disabled,
        [data-testid="stDownloadButton"] button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        /* ========================================================================
           INPUTS
           ======================================================================== */
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stMultiSelect"] [role="combobox"],
        [data-testid="stDateInput"] input {
          border-radius: var(--radius-md);
          border: 1px solid var(--border-default);
          background: var(--bg-surface);
          color: var(--ink-900);
          font-size: var(--text-base);
          transition: all var(--transition-fast);
        }
        
        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stSelectbox"] [role="combobox"]:focus,
        [data-testid="stMultiSelect"] [role="combobox"]:focus {
          border-color: var(--border-focus);
          box-shadow: 0 0 0 3px var(--brand-primary-light);
          outline: none;
        }
        
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stMultiSelect"] [role="combobox"] {
          padding-right: var(--space-8);
        }
        
        [data-testid="stNumberInput"] input {
          padding-right: var(--space-8);
        }
        
        [data-testid="stNumberInput"] button {
          border-radius: 0 var(--radius-md) var(--radius-md) 0;
          background: var(--ink-100);
          border-left: 1px solid var(--border-default);
        }
        
        [data-testid="stNumberInput"] button:hover {
          background: var(--ink-200);
        }
        
        /* Slider */
        [data-testid="stSlider"] [role="slider"] {
          background: var(--brand-primary);
        }
        
        [data-testid="stSlider"] [data-testid="stThumbValue"] {
          background: var(--brand-primary);
          color: var(--white);
          border-radius: var(--radius-sm);
          padding: 2px 6px;
          font-size: var(--text-xs);
          font-weight: 600;
        }
        
        /* Checkbox & Radio */
        [data-testid="stCheckbox"] input,
        [data-testid="stRadio"] input {
          accent-color: var(--brand-primary);
        }
        
        /* ========================================================================
           EXPANDER
           ======================================================================== */
        [data-testid="stExpander"] {
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          background: var(--bg-surface);
          overflow: hidden;
        }
        
        [data-testid="stExpander"] summary {
          padding: var(--space-3) var(--space-4);
          font-weight: 600;
          color: var(--ink-700);
          background: var(--bg-surface);
          border-bottom: 1px solid var(--border-subtle);
        }
        
        [data-testid="stExpander"] summary:hover {
          background: var(--bg-surface-hover);
        }
        
        [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
          padding: var(--space-4);
        }
        
        /* ========================================================================
           ALERTS / INFO BOXES
           ======================================================================== */
        [data-testid="stAlert"] {
          border-radius: var(--radius-lg);
          border: 1px solid;
          padding: var(--space-3) var(--space-4);
          font-size: var(--text-sm);
          line-height: var(--leading-relaxed);
        }
        
        [data-testid="stAlert"][kind="info"] {
          background: var(--info-bg);
          border-color: var(--info-border);
          color: var(--info);
        }
        
        [data-testid="stAlert"][kind="success"] {
          background: var(--success-bg);
          border-color: var(--success-border);
          color: var(--success);
        }
        
        [data-testid="stAlert"][kind="warning"] {
          background: var(--warning-bg);
          border-color: var(--warning-border);
          color: var(--warning);
        }
        
        [data-testid="stAlert"][kind="error"] {
          background: var(--error-bg);
          border-color: var(--error-border);
          color: var(--error);
        }
        
        /* ========================================================================
           DATAFRAME / TABLES
           ======================================================================== */
        [data-testid="stDataFrame"] {
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          overflow: hidden;
          background: var(--bg-surface);
        }
        
        [data-testid="stDataFrame"] table {
          font-size: var(--text-sm);
        }
        
        [data-testid="stDataFrame"] th {
          background: var(--ink-50);
          color: var(--ink-700);
          font-weight: 600;
          font-size: var(--text-xs);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: var(--space-2) var(--space-3);
          border-bottom: 1px solid var(--border-subtle);
        }
        
        [data-testid="stDataFrame"] td {
          padding: var(--space-2) var(--space-3);
          border-bottom: 1px solid var(--border-subtle);
          color: var(--ink-700);
        }
        
        [data-testid="stDataFrame"] tr:last-child td {
          border-bottom: none;
        }
        
        [data-testid="stDataFrame"] tr:hover td {
          background: var(--ink-50);
        }
        
        /* ========================================================================
           CHARTS (Altair/Plotly/Vega)
           ======================================================================== */
        [data-testid="stPlotlyChart"],
        [data-testid="stVegaLiteChart"],
        [data-testid="stPyplotChart"] {
          background: var(--bg-surface);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          padding: var(--space-3);
          box-shadow: var(--shadow-xs);
        }
        
        /* ========================================================================
           CONTAINERS & CARDS
           ======================================================================== */
        .stContainer {
          background: var(--bg-surface);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          padding: var(--space-4);
          box-shadow: var(--shadow-xs);
        }
        
        /* Guide cards */
        .st-key-guide-stuff,
        .st-key-guide-location,
        .st-key-guide-pitching {
          min-height: 160px;
          padding: var(--space-4) var(--space-5);
          background: var(--bg-surface);
          border: 1px solid var(--border-subtle);
          border-top: 3px solid var(--brand-primary);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-xs);
          transition: all var(--transition-base);
        }
        
        .st-key-guide-stuff:hover,
        .st-key-guide-location:hover,
        .st-key-guide-pitching:hover {
          border-color: var(--border-default);
          box-shadow: var(--shadow-md);
          transform: translateY(-2px);
        }
        
        .st-key-guide-stuff h4,
        .st-key-guide-location h4,
        .st-key-guide-pitching h4 {
          margin-top: var(--space-1);
          margin-bottom: var(--space-2);
          color: var(--brand-primary);
          font-size: var(--text-lg);
        }
        
        /* Tour highlight containers */
        .st-key-tour-profile,
        .st-key-tour-measurements,
        .st-key-tour-advanced,
        .st-key-tour-results {
          border-radius: var(--radius-lg);
          transition: all var(--transition-base);
        }
        
        /* ========================================================================
           SEGMENTED CONTROL
           ======================================================================== */
        [data-testid="stSegmentedControl"] {
          background: var(--ink-100);
          border-radius: var(--radius-full);
          padding: var(--space-1);
          display: inline-flex;
          gap: var(--space-1);
        }
        
        [data-testid="stSegmentedControl"] button {
          border-radius: var(--radius-full);
          padding: var(--space-2) var(--space-4);
          font-weight: 500;
          font-size: var(--text-sm);
          color: var(--ink-500);
          background: transparent;
          border: none;
          transition: all var(--transition-fast);
        }
        
        [data-testid="stSegmentedControl"] button:hover {
          color: var(--ink-700);
        }
        
        [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
          background: var(--white);
          color: var(--brand-primary);
          box-shadow: var(--shadow-sm);
          font-weight: 600;
        }
        
        /* ========================================================================
           PROGRESS / SPINNER
           ======================================================================== */
        [data-testid="stProgress"] > div > div {
          background: var(--brand-primary);
          border-radius: var(--radius-full);
        }
        
        [data-testid="stSpinner"] > div {
          border-top-color: var(--brand-primary) !important;
        }
        
        /* ========================================================================
           DIVIDER / HR
           ======================================================================== */
        hr {
          border: none;
          border-top: 1px solid var(--border-subtle);
          margin: var(--space-6) 0;
        }
        
        /* ========================================================================
           FOCUS VISIBLE (Accessibility)
           ======================================================================== */
        :focus-visible {
          outline: 2px solid var(--border-focus);
          outline-offset: 2px;
        }
        
        /* ========================================================================
           REDUCED MOTION
           ======================================================================== */
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            transition: none !important;
            animation: none !important;
            scroll-behavior: auto !important;
          }
        }
        
        /* ========================================================================
           RESPONSIVE
           ======================================================================== */
        @media (max-width: 768px) {
          :root {
            --sidebar-width: 100%;
          }
          
          [data-testid="stMetric"] {
            min-height: auto;
            padding: var(--space-3) var(--space-4);
          }
          
          [data-testid="stTabs"] [role="tablist"] {
            overflow-x: auto;
            flex-wrap: nowrap;
            -webkit-overflow-scrolling: touch;
          }
          
          [data-testid="stTabs"] button[role="tab"] {
            white-space: nowrap;
            padding: var(--space-2) var(--space-3);
          }
          
          .st-key-guide-stuff,
          .st-key-guide-location,
          .st-key-guide-pitching {
            min-height: auto;
          }
        }
        
        @media (max-width: 480px) {
          [data-testid="stAppViewContainer"] > .main .block-container {
            padding: var(--space-3) var(--space-3) var(--space-6);
          }
          
          h1 { font-size: var(--text-2xl); }
          h2 { font-size: var(--text-xl); }
        }
        
        /* ========================================================================
           PRINT
           ======================================================================== */
        @media print {
          [data-testid="stSidebar"],
          [data-testid="stHeader"],
          [data-testid="stButton"],
          [data-testid="stDownloadButton"] {
            display: none !important;
          }
          
          [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: none;
            padding: 0;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def highlight_tutorial_target(target):
    """Subtly outline the simulator area selected by the in-page tour."""
    selectors = {
        "profile": ".st-key-tour-profile",
        "measurements": ".st-key-tour-measurements",
        "advanced": ".st-key-tour-advanced",
        "results": ".st-key-tour-results",
        "analysis": '[data-testid="stTabs"] [role="tablist"]',
    }
    selector = selectors.get(target)
    if selector:
        st.markdown(
            f"""
            <style>
            {selector} {{
              outline: 2px solid var(--brand-primary);
              outline-offset: 4px;
              border-radius: var(--radius-lg);
              background-color: var(--brand-primary-muted);
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )