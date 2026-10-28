dashboard fix: Changed OUT path from ROOT/"entrega_v8" to ROOT.parent/"entrega_v8" in dashboard_entrega_v8.py
- The dashboard was looking for data in codigo/entrega_v8/ but data exists at project root entrega_v8/
- Fixed by using ROOT.parent to point to the correct directory
- All existing tests pass
- Dashboard starts successfully