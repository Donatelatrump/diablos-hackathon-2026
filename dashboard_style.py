"""Comprehensive design system for Diablos Stuff+ dashboards."""
import streamlit as st
import base64
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _display_font():
    return base64.b64encode((Path(__file__).parent / 'imgs/fonts/BarlowCondensed-Bold.ttf').read_bytes()).decode('ascii')


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
          --font-display: "Big Shoulders Display", "Arial Narrow", "Segoe UI", sans-serif;
          --color-harp: #cf202e;
          --color-sea: #2E6FA6;
          
          --text-xs: 0.8125rem;
          --text-sm: 0.9375rem;
          --text-base: 1.0625rem;
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
          min-width: 0;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
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

        [data-testid="stForm"] {
          background: var(--bg-surface);
          border-radius: var(--radius-lg);
        }
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button,
        [data-testid="stRadio"] label {
          min-height: 44px;
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

        /* ========================================================================
           DULONGKI-INSPIRED ENHANCEMENTS (AIR & ALTITUDE VISUAL PATTERNS)
           ======================================================================== */

        /* Eyebrow pattern (Dulongski badge over questions/sections) */
        .eyebrow {
          font-family: var(--font-mono);
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--brand-primary);
          margin-bottom: 4px;
          display: inline-block;
        }

        /* Mono numbers & data display (Instrument of measurement concept) */
        .metric-mono, .num-mono {
          font-family: var(--font-mono) !important;
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.02em;
        }

        /* Binary color cues: Red = Harp Helu (altitude), Blue = Sea level */
        .badge-alt, .tag-harp {
          color: #cf202e;
          background: #fdf2f4;
          border: 1px solid #f8d7dc;
          padding: 2px 8px;
          border-radius: 999px;
          font-size: 0.75rem;
          font-weight: 600;
        }
        .badge-sea, .tag-sea {
          color: #2E6FA6;
          background: #edf5fb;
          border: 1px solid #d0e4f5;
          padding: 2px 8px;
          border-radius: 999px;
          font-size: 0.75rem;
          font-weight: 600;
        }

        /* Question cards grid (Dulongski interactive question prompt pattern) */
        .questions-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 14px;
          margin: 18px 0 24px;
        }
        @media (max-width: 900px) {
          .questions-grid { grid-template-columns: 1fr; }
        }
        .question-card {
          background: #ffffff;
          border: 1px solid #e9e6e2;
          border-top: 3px solid #cf202e;
          border-radius: 12px;
          padding: 16px 18px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.03);
          transition: transform 0.15s ease, border-color 0.15s ease;
        }
        .question-card:hover {
          transform: translateY(-2px);
          border-color: #cf202e;
          box-shadow: 0 6px 16px rgba(207,32,46,0.08);
        }
        .question-card .q-ent {
          font-family: var(--font-mono);
          font-size: 0.65rem;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--ink-400);
        }
        .question-card .q-title {
          font-family: var(--font-sans);
          font-weight: 750;
          font-size: 1.05rem;
          line-height: 1.25;
          color: var(--ink-900);
        }
        .question-card .q-desc {
          font-size: 0.86rem;
          color: var(--ink-500);
          line-height: 1.45;
          margin: 0;
          flex: 1;
        }
        .question-card .q-desc b {
          color: #cf202e;
          font-family: var(--font-mono);
        }

        /* Short response callout hero (Respuesta corta) */
        .callout-short-response {
          background: #ffffff;
          border: 1px solid #e8e2dc;
          border-left: 4px solid #cf202e;
          border-radius: 14px;
          padding: 18px 22px;
          margin: 16px 0 20px;
          box-shadow: 0 4px 14px rgba(0,0,0,0.02);
        }
        .callout-short-response .csr-text {
          font-size: 1.02rem;
          color: var(--ink-700);
          line-height: 1.5;
          margin-bottom: 14px;
        }
        .callout-short-response .csr-text b {
          color: var(--ink-900);
        }
        .csr-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 16px;
          padding-top: 12px;
          border-top: 1px solid #f0eae4;
        }
        @media (max-width: 768px) {
          .csr-stats { grid-template-columns: 1fr; }
        }
        .csr-stat {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .csr-stat .stat-num {
          font-family: var(--font-mono);
          font-size: 1.65rem;
          font-weight: 700;
          line-height: 1.1;
          color: #cf202e;
        }
        .csr-stat .stat-num.neutral { color: #2E6FA6; }
        .csr-stat .stat-num.gains { color: #1a7f37; }
        .csr-stat .stat-label {
          font-size: 0.8rem;
          color: var(--ink-500);
          line-height: 1.35;
        }

        /* Current Streamlit layout and the guided landing page. */
        :root {
          --bg-page: #f7f6f3;
          --ink-500: #62636b;
          --font-sans: "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
        }
        .stApp { background: radial-gradient(ellipse at 0% 5%, #fbe9ec 0, transparent 38%), radial-gradient(ellipse at 100% 85%, #e9f1ee 0, transparent 40%), #f7f6f3; }
        [data-testid="stMainBlockContainer"] {
          max-width: 1160px;
          padding: 2.2rem 2rem 4rem;
          margin-left: auto !important;
          margin-right: auto !important;
          width: 100%;
        }
        [data-testid="stSidebar"][aria-expanded="false"] { min-width: 0 !important; }
        [data-testid="stHeader"] {
          background: transparent;
          border-bottom: 0;
          backdrop-filter: none;
        }
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stWidgetLabel"] p,
        input, button, [data-baseweb="select"] {
          font-family: var(--font-sans) !important;
        }
        h1, h2, h3, h4 { font-family: var(--font-sans) !important; }
        .brand-lockup { display: flex; align-items: center; gap: 12px; min-height: 64px; }
        .brand-lockup img { width: 58px; height: 58px; object-fit: contain; }
        .brand-lockup b { display: block; font-size: 20px; letter-spacing: .14em; color: #24252b; }
        .brand-lockup span { display: block; font-size: 9px; font-weight: 700; letter-spacing: .16em; color: #76757c; margin-top: 3px; }
        .start-hero {
          position: relative; overflow: hidden; isolation: isolate; display: flex;
          min-height: 265px; padding: 32px 38px; margin: 12px 0 8px;
          background: radial-gradient(ellipse at 88% 30%, #752338 0, transparent 57%), #241d28;
          border-radius: 22px; box-shadow: 0 12px 30px #38222b12;
        }
        .hero-copy { position: relative; z-index: 2; width: 100%; text-align: center; }
        .hero-eyebrow { font-size: 10px; font-weight: 700; letter-spacing: .19em; color: #e8a6af; }
        .start-hero h1 {
          color: #fff; font-size: clamp(28px, 3.1vw, 42px); font-weight: 750;
          letter-spacing: -.045em; line-height: 1.13; margin: 13px 0 14px; padding: 0;
        }
        .start-hero p { color: #d1c4ce; font-size: 14px; line-height: 1.65; margin: 0 0 19px; }
        .hero-pill { display: inline-flex; align-items: center; gap: 8px; color: #f3dfe5;
          border: 1px solid #ffffff20; background: #ffffff08; border-radius: 30px; padding: 7px 12px; font-size: 11px; }
        .hero-pill > span { width: 6px; height: 6px; background: #e6a9b3; border-radius: 50%; }
        .hero-field { position: absolute; right: -35px; top: 0; width: 330px; height: 100%; opacity: .28; }
        .field-ring { position: absolute; border: 1px solid #ffffff12; border-radius: 50%; }
        .ring-outer { width: 300px; height: 300px; top: -12px; right: -10px; }
        .ring-inner { width: 220px; height: 220px; top: 28px; right: 30px; }
        .field-diamond { position: absolute; width: 102px; height: 102px; border: 1px solid #f4b9c155;
          transform: rotate(45deg); left: 128px; top: 104px; background: #ffffff04; }
        .field-line { position: absolute; width: 166px; height: 1px; background: #ffffff21; top: 227px; left: 179px; transform-origin: left; }
        .line-left { transform: rotate(-135deg); }
        .line-right { transform: rotate(-45deg); }
        .pitch-trail { position: absolute; width: 95px; height: 155px; left: 130px; top: 36px;
          border-right: 2px dashed #ed889770; border-radius: 50%; transform: rotate(35deg); }
        .field-ball { position: absolute; top: 43px; right: 68px; font-size: 62px; transform: rotate(-20deg); filter: drop-shadow(0 12px 20px #0004); }
        .field-label { position: absolute; bottom: 21px; right: 30px; font-size: 8px; letter-spacing: .22em; color: #dc9eaa; }
        .section-intro { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 10px 0 3px; }
        .section-intro h2 { font-size: 21px; margin: 0; padding: 0; letter-spacing: -.03em; }
        .section-intro > span { color: #78757c; font-size: 12px; }
        .st-key-start-pitch-card, [data-testid="stForm"] {
          background: #fff; border: 1px solid #e9e6e2 !important; border-radius: 17px;
          padding: 22px !important; box-shadow: 0 4px 16px #2f263305;
        }
        .st-key-start-pitch-card { min-height: 315px; }
        .st-key-start-pitch-card { border-top: 4px solid #c3263c !important; }
        [data-testid="stForm"] { border-top: 4px solid #36796f !important; }
        [data-testid="stForm"] .step-heading > span { background: #eaf4f0; color: #2c7368; }
        .feature-strip { display: flex; gap: 12px; margin: 2px 0 8px; }
        .feature-strip > div { flex: 1; padding: 14px 18px; border: 1px solid #e8e2dc; border-radius: 12px; background: #fff9; }
        .feature-strip b { display: block; font-size: 12px; color: #9e2338; margin-bottom: 4px; }
        .feature-strip > div:nth-child(2) b { color: #34776e; }
        .feature-strip > div:nth-child(3) b { color: #9c742b; }
        .feature-strip p { color: #746c76; font-size: 11px; margin: 0; }
        .step-heading { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
        .step-heading > span { display: grid; place-items: center; width: 38px; height: 38px;
          border-radius: 11px; background: #fcf0f1; color: #bc2437; font-size: 12px; font-weight: 750; }
        .step-heading h3 { font-size: 19px; margin: 0 0 3px; padding: 0; letter-spacing: -.025em; }
        .step-heading p { color: #87818a; font-size: 12px; margin: 0; }
        [data-testid="stWidgetLabel"] p { font-size: 12px !important; color: #57535c; font-weight: 600; }
        [data-baseweb="select"] > div {
          background: #faf9f7 !important; border: 1px solid #e6e2df !important;
          border-radius: 10px !important; min-height: 46px; color: #29252e;
        }
        [data-baseweb="select"] [role="combobox"] {
          border: 0 !important; background: transparent !important; box-shadow: none !important;
          padding-right: 0; font-size: 14px;
        }
        [data-baseweb="select"] svg { fill: #77717b; }
        [data-baseweb="select"] > div:focus-within { outline: 2px solid #cf202e; outline-offset: 2px; }
        .example-note { margin-top: 9px; padding: 14px 16px; border-radius: 10px; background: #f8f7f4; border-left: 3px solid #d6c8bf; }
        .example-note b { display: block; font-size: 12px; color: #514851; margin-bottom: 5px; }
        .example-note p { font-size: 12px; line-height: 1.6; margin: 0; color: #7a717a; }
        .st-key-start-pitch-card [data-testid="stCaptionContainer"] p,
        [data-testid="stForm"] [data-testid="stCaptionContainer"] p { font-size: 11px; color: #827b84; }
        [data-testid="stForm"] [data-testid="stExpander"] { border: 1px solid #eee9e5; border-radius: 10px; box-shadow: none; }
        [data-testid="stForm"] [data-testid="stExpander"] summary { background: #fff; padding: 10px 12px; }
        [data-testid="stForm"] [data-testid="stExpander"] summary p { font-size: 12px; color: #6e646f; }
        [data-testid="stFormSubmitButton"] button {
          background: #c3263c; color: #fff; border: 0; border-radius: 10px;
          min-height: 48px; box-shadow: 0 4px 9px #c3263c20;
        }
        [data-testid="stFormSubmitButton"] button p { color: #fff; font-size: 14px; font-weight: 650; }
        [data-testid="stFormSubmitButton"] button:hover { background: #a91c31; color: #fff; box-shadow: 0 5px 13px #c3263c30; }
        .st-key-start-result-card { background: #fff; border: 1px solid #e9e6e2; border-top: 3px solid #c3263c; border-radius: 17px; padding: 26px; }
        @media (max-width: 850px) {
          [data-testid="stMainBlockContainer"] { padding: 1.4rem 1.2rem 3rem; }
          .brand-lockup { gap: 8px; }
          .brand-lockup b { font-size: 16px; }
          .brand-lockup img { width: 44px; height: 44px; }
          .start-hero { padding: 28px; }
          .hero-field { right: -60px; opacity: .55; }
        }
        @media (max-width: 640px) {
          .feature-strip { flex-direction: column; gap: 6px; }
          .feature-strip > div { padding: 10px 14px; }
          .hero-copy { max-width: 100%; }
          .start-hero { padding: 24px; min-height: 250px; border-radius: 16px; }
          .start-hero h1 { font-size: 32px; }
          .hero-field { opacity: .15; right: -120px; }
          .hero-copy p { font-size: 13px; }
          .section-intro { display: block; }
          .section-intro h2 { margin-bottom: 6px; }
          .st-key-start-pitch-card { min-height: auto; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.html('<style>@font-face {font-family: "Diablos Display"; src: url(data:font/ttf;base64,' + _display_font() + ') format("truetype"); font-style: normal; font-weight: 700; font-display: swap;}</style>')
    st.html(Path(__file__).parent / 'dashboard_editorial.css')


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
