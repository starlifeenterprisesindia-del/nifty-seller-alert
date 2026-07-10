# V22.9 Streamlit PyArrow Fix

## Problem
Streamlit Cloud crashed while rendering a dataframe/table because PyArrow could not serialize a column containing mixed Python values such as lists/dicts/strings.

## Fix
- Added `v229_safe_df()` sanitizer.
- Replaced visible `st.dataframe()` calls with `v229_dataframe()`.
- Replaced `st.table()` calls with `v229_table()`.
- Unsafe object columns are converted to safe strings before display.
- Numeric columns remain numeric where possible.
- Developer error log table is now safe to render.

## Validation
- All Python files compile successfully.
- No raw `st.dataframe()` or `st.table()` calls remain in app.py outside the safe wrapper.

## Trading Logic
No AI decision logic was changed. This is only a display/rendering stability fix.
