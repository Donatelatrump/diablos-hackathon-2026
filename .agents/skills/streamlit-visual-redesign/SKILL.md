---
name: streamlit-visual-redesign
description: Redesign the visuals of an existing Streamlit app while preserving business logic, state, data, and functionality.
---

# Streamlit Visual Redesign

Act as a senior UI/UX designer and Python frontend engineer.

## Inspect first
- Inspect the repository, entry point, every page, shared components, dependencies, theme, and tests.
- Understand session state, widget keys, callbacks, forms, navigation, and data loading.
- Review the Git working tree and establish a baseline before modifying files.

## Design
- Create a consistent, polished design system.
- Improve typography, spacing, layout, navigation, sidebar, cards, metrics, forms, tables, and charts.
- Use cohesive colors, restrained borders, consistent radii, and clear visual hierarchy.
- Make pages responsive and accessible.
- Prefer native Streamlit components and theme settings.
- Use custom CSS or custom components where native widgets are insufficient.

## Preserve functionality
- Do not rewrite the application.
- Preserve calculations, business logic, APIs, database queries, authentication, authorization, and data schemas.
- Preserve widget keys, session state, callbacks, and navigation behavior.
- Do not replace real data with mock data.
- Avoid unnecessary dependencies and unrelated refactoring.

## Workflow
1. Establish a baseline.
2. Define reusable design tokens and theme settings.
3. Redesign one representative page.
4. Run the app and validate the changes.
5. Apply the design consistently to the remaining pages.
6. Test interactions and responsive layouts.
7. Review the Git diff and fix regressions.

## Completion criteria
Report the files changed, tests actually executed, visual checks performed, known limitations, and how to run the app. Never claim a test passed unless it was executed.
