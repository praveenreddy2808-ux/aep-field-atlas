#!/usr/bin/env python3
# app_dynamic_generic.py
"""
Streamlit app - dynamic scanner that discovers nested fields under any chosen root column.

Usage:
  pip install streamlit pandas psycopg2-binary
  streamlit run app_dynamic_generic.py
"""

import streamlit as st
import pandas as pd
import psycopg2
import json
import re
from typing import Any, List

st.set_page_config(page_title="AEP Field Finder (Generic)", layout="wide")
st.title("AEP - Generic Field Finder (dynamic loader)")

st.markdown(
    """
This app will query your AEP Query Service (Postgres) to discover datasets that contain
a chosen top-level column (root) and extract nested paths under that root up to 4 levels.

**Fill DB connection and root column**, then click **Load from DB**.
"""
)

# ------------------------
# Connection & root inputs
# ------------------------
with st.expander("Connection and scan settings"):
    HOST = st.text_input("Host", value="<your_host>")
    PORT = st.number_input("Port", value=80, step=1)
    DATABASE = st.text_input("Database", value="<your_database>")
    USER = st.text_input("User", value="<your_user>")
    PASSWORD = st.text_input("Password", type="password")
    SSL_MODE = st.selectbox("sslmode", options=["require", "disable"], index=0)

    st.markdown("---")
    root_field = st.text_input("Root column to inspect (top-level)", value="_luma",
                               help="Top-level column name to scan (e.g. _luma or payload). If you include dots, only the first segment is used to find Datasets.")
    sample_limit = st.number_input("Sample rows per dataset (LIMIT)", value=1, min_value=1, step=1,
                                   help="How many sample rows to inspect per dataset. Larger values increase cost.")
    st.markdown("**Search options**: once data is loaded, use the Find box to search exact/contains/regex against discovered paths.")

# ------------------------
# SQL template with placeholders {table}, {root_dot}, {root}
# ------------------------
PER_TABLE_TEMPLATE = r"""
WITH sample AS (
  SELECT to_json(struct(*)) AS js
  FROM {table}
  LIMIT {limit}
),
root_json AS (
  SELECT get_json_object(js, '$.{root}') AS r0
  FROM sample
),
lvl1_prep AS (
  SELECT explode(split(regexp_replace(r0, '^[{]|[}]$', ''), ',')) AS kv, r0
  FROM root_json
  WHERE r0 IS NOT NULL
),
lvl1 AS (
  SELECT DISTINCT regexp_extract(kv, '"([^"]+)":', 1) AS k1,
         get_json_object(r0, concat('$.', regexp_extract(kv, '"([^"]+)":', 1))) AS v1
  FROM lvl1_prep
  WHERE kv IS NOT NULL
),

-- LEVEL 2
lvl2_prep AS (
  SELECT DISTINCT l1.k1,
         CASE WHEN trim(l1.v1) LIKE '[%' THEN get_json_object(l1.v1,'$[0]') ELSE l1.v1 END AS v2
  FROM lvl1 l1
  WHERE l1.v1 IS NOT NULL
),
lvl2_expl AS (
  SELECT k1, v2, explode(split(regexp_replace(v2, '^[{]|[}]$', ''), ',')) AS kv2
  FROM lvl2_prep
  WHERE v2 IS NOT NULL
),
lvl2 AS (
  SELECT DISTINCT k1,
         regexp_extract(kv2, '"([^"]+)":', 1) AS k2,
         CASE
           WHEN trim(kv2) IS NULL THEN NULL
           ELSE
             CASE
               WHEN trim(
                 get_json_object(
                   CASE WHEN trim(v2) LIKE '[%' THEN get_json_object(v2,'$[0]') ELSE v2 END,
                   concat('$.', regexp_extract(kv2, '"([^"]+)":', 1))
                 )
               ) LIKE '[%' THEN get_json_object(
                 get_json_object(
                   CASE WHEN trim(v2) LIKE '[%' THEN get_json_object(v2,'$[0]') ELSE v2 END,
                   concat('$.', regexp_extract(kv2, '"([^"]+)":', 1))
                 ), '$[0]')
               ELSE get_json_object(
                 CASE WHEN trim(v2) LIKE '[%' THEN get_json_object(v2,'$[0]') ELSE v2 END,
                 concat('$.', regexp_extract(kv2, '"([^"]+)":', 1))
               )
             END
         END AS v2_child
  FROM lvl2_expl
),

-- LEVEL 3
lvl3_prep AS (
  SELECT DISTINCT k1, k2,
         CASE WHEN v2_child IS NULL THEN NULL
              WHEN trim(v2_child) LIKE '[%' THEN get_json_object(v2_child,'$[0]') ELSE v2_child
         END AS v3
  FROM lvl2
  WHERE v2_child IS NOT NULL
),
lvl3_expl AS (
  SELECT k1, k2, v3, explode(split(regexp_replace(v3, '^[{]|[}]$', ''), ',')) AS kv3
  FROM lvl3_prep
  WHERE v3 IS NOT NULL
),
lvl3 AS (
  SELECT DISTINCT k1, k2,
         regexp_extract(kv3, '"([^"]+)":', 1) AS k3,
         CASE
           WHEN trim(kv3) IS NULL THEN NULL
           ELSE
             CASE
               WHEN trim(
                 get_json_object(
                   CASE WHEN trim(v3) LIKE '[%' THEN get_json_object(v3,'$[0]') ELSE v3 END,
                   concat('$.', regexp_extract(kv3, '"([^"]+)":', 1))
                 )
               ) LIKE '[%' THEN get_json_object(
                 get_json_object(
                   CASE WHEN trim(v3) LIKE '[%' THEN get_json_object(v3,'$[0]') ELSE v3 END,
                   concat('$.', regexp_extract(kv3, '"([^"]+)":', 1))
                 ), '$[0]')
               ELSE get_json_object(
                 CASE WHEN trim(v3) LIKE '[%' THEN get_json_object(v3,'$[0]') ELSE v3 END,
                 concat('$.', regexp_extract(kv3, '"([^"]+)":', 1))
               )
             END
         END AS v3_child
  FROM lvl3_expl
),

-- LEVEL 4
lvl4_prep AS (
  SELECT DISTINCT k1, k2, k3,
         CASE WHEN v3_child IS NULL THEN NULL
              WHEN trim(v3_child) LIKE '[%' THEN get_json_object(v3_child,'$[0]') ELSE v3_child
         END AS v4
  FROM lvl3
  WHERE v3_child IS NOT NULL
),
lvl4_expl AS (
  SELECT k1, k2, k3, v4, explode(split(regexp_replace(v4, '^[{]|[}]$', ''), ',')) AS kv4
  FROM lvl4_prep
  WHERE v4 IS NOT NULL
),
lvl4 AS (
  SELECT DISTINCT k1, k2, k3,
         regexp_extract(kv4, '"([^"]+)":', 1) AS k4
  FROM lvl4_expl
  WHERE kv4 IS NOT NULL
),

final_paths AS (
  SELECT DISTINCT concat('{root_dot}', k1) AS path FROM lvl1 WHERE k1 IS NOT NULL
  UNION
  SELECT DISTINCT concat('{root_dot}', k1, '.', k2) FROM lvl2 WHERE k1 IS NOT NULL AND k2 IS NOT NULL
  UNION
  SELECT DISTINCT concat('{root_dot}', k1, '.', k2, '.', k3) FROM lvl3 WHERE k1 IS NOT NULL AND k2 IS NOT NULL AND k3 IS NOT NULL
  UNION
  SELECT DISTINCT concat('{root_dot}', k1, '.', k2, '.', k3, '.', k4) FROM lvl4 WHERE k1 IS NOT NULL AND k2 IS NOT NULL AND k3 IS NOT NULL AND k4 IS NOT NULL
)
SELECT '{table}' AS table_name, collect_list(path) AS columns
FROM final_paths;
"""

# ------------------------
# Helpers: normalize various returned shapes into list[str]
# ------------------------
def parse_postgres_array(s: str) -> List[str]:
    inner = s[1:-1]
    parts = []
    cur = ""
    in_quote = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == '"' and (i == 0 or inner[i-1] != '\\'):
            in_quote = not in_quote
            i += 1
            continue
        if ch == ',' and not in_quote:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    if cur != "":
        parts.append(cur)
    return [p.strip().strip('"') for p in parts if p.strip()]

def normalize_columns_field(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, (tuple, set)):
        return [str(x) for x in raw]
    if isinstance(raw, dict):
        return [str(k) for k in raw.keys()]
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        s = raw.strip()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
            if isinstance(parsed, dict):
                return [str(k) for k in parsed.keys()]
            return [str(parsed)]
        except Exception:
            if s.startswith("{") and s.endswith("}"):
                return parse_postgres_array(s)
            if "," in s:
                return [p.strip() for p in s.split(",") if p.strip()]
            if s == "":
                return []
            return [s]
    return [str(raw)]

# ------------------------
# DB helpers
# ------------------------
def run_query_raw(conn, sql: str):
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    return cur, rows

def discover_tables(conn, root_col_name: str):
    q = f"""
    SELECT DISTINCT table_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND column_name = '{root_col_name}'
    ORDER BY table_name;
    """
    with conn.cursor() as cur:
        cur.execute(q)
        rows = cur.fetchall()
        return [r[0] for r in rows]

# ------------------------
# Cached loader (scans all datasets) - caches results for speed
# ------------------------
@st.cache_data(show_spinner=False)
def load_all_tables_from_db(host, port, dbname, user, password, sslmode, root_col_name, limit):
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, sslmode=sslmode)
    try:
        tables = discover_tables(conn, root_col_name)
        results = []
        for tbl in tables:
            q = PER_TABLE_TEMPLATE.replace("{table}", tbl).replace("{root}", root_col_name).replace("{root_dot}", root_field + ".").replace("{limit}", str(limit))
            try:
                cur, rows = run_query_raw(conn, q)
                if not rows:
                    results.append({"table_name": tbl, "columns": []})
                    continue
                row0 = rows[0]
                mapped = {}
                if isinstance(row0, dict):
                    mapped = row0
                elif isinstance(row0, (list, tuple)) and cur.description:
                    colnames = [d[0] for d in cur.description]
                    mapped = {colnames[i]: (row0[i] if i < len(row0) else None) for i in range(len(colnames))}
                else:
                    mapped = {cur.description[0][0] if cur.description else "value": row0}
                # choose candidate
                candidate = None
                for key in ("columns", "collect_list(path)", "js", root_col_name, "value"):
                    if key in mapped and mapped[key] is not None:
                        candidate = mapped[key]; break
                if candidate is None:
                    for k,v in mapped.items():
                        if k.lower() == "table_name": continue
                        candidate = v; break
                cols = normalize_columns_field(candidate)
                results.append({"table_name": mapped.get("table_name", tbl), "columns": cols})
            except Exception as e:
                results.append({"table_name": tbl, "columns": [], "error": str(e)})
        return results
    finally:
        conn.close()

# ------------------------
# UI: load actions
# ------------------------
col1, col2 = st.columns([3,1])
with col1:
    load_action = st.button("Load from DB")
with col2:
    clear_cache = st.button("Clear cache")

if clear_cache:
    st.cache_data.clear()
    st.success("Cache cleared.")

if "scanner_data" not in st.session_state:
    st.session_state["scanner_data"] = None
    st.session_state["loaded"] = False

if load_action:
    if not HOST or not DATABASE or not USER or not PASSWORD:
        st.error("Fill host, database, user, and password before loading.")
    else:
        with st.spinner("Scanning - this may take some time depending on no of datasets..."):
            try:
                # discover uses only the first segment of root_field to find table column names
                root_col_name = root_field.split(".")[0]
                data = load_all_tables_from_db(HOST, PORT, DATABASE, USER, PASSWORD, SSL_MODE, root_col_name, sample_limit)
                st.session_state["scanner_data"] = data
                st.session_state["loaded"] = True
                st.success(f"Loaded {len(data)} datasets.")
            except Exception as e:
                st.error(f"Failed to load: {e}")

# ------------------------
# Search UI
# ------------------------
if st.session_state.get("loaded"):
    data = st.session_state["scanner_data"]
    st.sidebar.header("Loaded summary")
    df_meta = pd.DataFrame([{"table_name": r["table_name"], "col_count": len(r.get("columns") or [])} for r in data])
    st.sidebar.write(f"Datasets loaded: {len(df_meta)}")
    st.sidebar.dataframe(df_meta.sort_values("col_count", ascending=False).head(50), use_container_width=True)

    st.header("Search field path")
    col_a, col_b = st.columns([3,1])
    with col_a:
        field_path = st.text_input("Field path to find (example)", value=f"{root_field}.userIdentifiers.contactId")
    with col_b:
        match_mode = st.selectbox("Match mode", ["exact", "contains", "regex"])
    if st.button("Find"):
        results = []
        try:
            re_obj = re.compile(field_path) if match_mode == "regex" else None
            for row in data:
                matches = []
                for c in row.get("columns", []):
                    if match_mode == "exact" and c == field_path:
                        matches.append(c)
                    elif match_mode == "contains" and field_path.lower() in c.lower():
                        matches.append(c)
                    elif match_mode == "regex" and re_obj.search(c):
                        matches.append(c)
                if matches:
                    results.append({"table_name": row["table_name"], "matches": matches})
            st.success(f"Found {len(results)} Datasets.")
            if results:
                df_out = pd.DataFrame([{"table_name": r["table_name"], "match_count": len(r["matches"]), "preview": "; ".join(r["matches"][:5])} for r in results])
                st.dataframe(df_out, use_container_width=True)
                for r in results:
                    with st.expander(f"{r['table_name']} - {len(r['matches'])} match(es)"):
                        st.write("\n".join(r["matches"]))
                out_df = pd.DataFrame([{"table_name": r["table_name"], "matches": json.dumps(r["matches"])} for r in results])
                st.download_button("Download matches CSV", out_df.to_csv(index=False).encode("utf-8"), file_name="field_matches.csv")
            else:
                st.info("No matches found.")
        except re.error as e:
            st.error(f"Invalid regex: {e}")
else:
    st.header("Search field path")
    st.text_input("Field path (load data first)", value=f"{root_field}.userIdentifiers.contactId", disabled=True)
    st.selectbox("Match mode", ["exact", "contains", "regex"], disabled=True)
    st.button("Find", disabled=True)
    st.info("Load scanner data from DB to enable searching.")

st.markdown("---")
st.caption("Notes: scans sample rows (LIMIT). Increase sample size to discover fields present only in other rows (cost increases).")
