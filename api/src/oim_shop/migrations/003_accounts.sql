-- v3: people sign in with GitHub and become sales reps.

-- One row per GitHub account that has signed in. Only GitHub's numeric id is kept: never the
-- username, the email or the name. employee_id is the employees row the person enters orders
-- as; on public pages it reads "Sales rep <employee_id>". display_name is the name the person
-- chose, shown only to them and to managers. role comes from the allowlist at each sign-in.
CREATE TABLE accounts (
    github_id    INTEGER PRIMARY KEY,
    employee_id  INTEGER NOT NULL UNIQUE REFERENCES employees,
    display_name TEXT CHECK (length(display_name) BETWEEN 1 AND 40),
    role         TEXT NOT NULL CHECK (role IN ('rep', 'manager')),
    created_at   TEXT NOT NULL
) STRICT;

-- A signed-in browser. The cookie holds a random token; only its SHA-256 is stored, so the
-- database alone cannot be used to sign in. csrf_token must come back with every write.
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    github_id  INTEGER NOT NULL REFERENCES accounts ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at TEXT NOT NULL
) STRICT;
