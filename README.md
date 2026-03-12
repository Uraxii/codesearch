# codesearch

A code search tool with string search and structural AST queries. Uses [tree-sitter](https://tree-sitter.github.io/) to parse source files and supports a human-readable query DSL alongside raw tree-sitter S-expression queries.

## Supported languages

| Language | Extensions |
|---|---|
| Python | `.py` |
| JavaScript | `.js` |
| TypeScript | `.ts`, `.tsx` |
| C# | `.cs` |

## Installation

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo>
cd code-search
uv sync
```

The `codesearch` command is then available via `uv run codesearch`.

## Usage

```
codesearch [--query | --ast | --regex] [--lang LANG] [--ignore-case] [--files-only] <pattern> [path ...]
codesearch --filter-file <file> [--filter-file <file> ...] [--lang LANG] [--files-only] [path ...]
```

If no path is given, the current directory is searched recursively.

---

## Search modes

### String search (default)

Searches file contents line by line for a literal string.

```bash
uv run codesearch "WebRequest" src/
```

### Regex search

```bash
uv run codesearch --regex "new \w+Request\(" src/
```

### DSL query (`--query`)

A human-readable structural query. Searches the parsed AST rather than raw text, so results are always syntactically meaningful.

```bash
uv run codesearch --query 'function where name = "WebRequest"' src/
```

### Raw tree-sitter query (`--ast`)

For advanced use. Pass a tree-sitter [S-expression query](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html) directly.

```bash
uv run codesearch --ast "(function_definition name: (identifier) @name)" src/
```

---

## DSL query syntax

```
<concept> [where <field> <op> "<value>" [and <field> <op> "<value>"] ...]
```

### Concepts

| Concept | What it matches |
|---|---|
| `function` / `method` | Function and method declarations |
| `class` | Class declarations |
| `identifier` | Any identifier (variable, type reference, symbol) |
| `call` | Function or method call expressions |
| `parameter` | Function/method parameters |

### Fields

| Field | Meaning |
|---|---|
| `name` / `text` | The name or text of the node |
| `type` | Type annotation of a parameter |

### Operators

| Operator | Meaning |
|---|---|
| `=` / `is` | Exact match |
| `!=` / `is not` | Not equal |
| `contains` | Substring match |
| `matches` | Regex match |
| `starts_with` | Prefix match |
| `ends_with` | Suffix match |

### Examples

```bash
# Find all places where WebRequest is used (as an identifier)
uv run codesearch --query 'identifier where text = "WebRequest"' src/

# Find methods/functions that accept WebRequest as a parameter type
uv run codesearch --query 'parameter where type = "WebRequest"' src/

# Find methods whose names start with "Process"
uv run codesearch --query 'function where name starts_with "Process"' src/

# Find all classes with "Request" in their name (across all supported languages)
uv run codesearch --query 'class where name contains "Request"' src/

# Find async methods (multi-predicate with and)
uv run codesearch --query 'function where name starts_with "Get" and name ends_with "Async"' src/

# Limit search to C# files only
uv run codesearch --query 'parameter where type = "string"' --lang c_sharp src/
```

---

## Filter files

A filter file is an INI file that bundles multiple named queries into one scan. Each match is tagged with the query name instead of the internal capture label.

```ini
[sql-injection]
type    = regex
pattern = "SELECT |INSERT INTO|UPDATE |DELETE FROM

[weak-hash-md5]
type    = query
pattern = identifier where text = "MD5"
lang    = c_sharp
```

**Fields**

| Field | Required | Description |
|---|---|---|
| `pattern` | yes | The pattern or DSL expression |
| `type` | no | `string` (default), `regex`, `query`, or `ast` |
| `lang` | no | Restrict this query to one language (same values as `--lang`) |
| `captures` | no | `ast` only — comma-separated list of capture names to surface in output. Other captures are used as structural filters but suppressed from results. When omitted, all captures are output. |

**Running a filter file**

```bash
uv run codesearch --filter-file queries.ini src/
```

Multiple `--filter-file` flags are merged into a single scan:

```bash
uv run codesearch --filter-file auth.ini --filter-file network.ini src/
```

Output labels each match with the query name:

```
src/auth.cs:14:12: [weak-hash-md5] MD5
src/auth.cs:23:12: [insecure-random] Random
```

---

## Options

| Flag | Description |
|---|---|
| `--query`, `-q` | Treat pattern as a DSL query |
| `--ast` | Treat pattern as a raw tree-sitter S-expression query |
| `--regex`, `-e` | Treat pattern as a regular expression (string search) |
| `--filter-file FILE` | Run all named queries in FILE (repeatable; cannot combine with `--query`/`--ast`/`--regex`) |
| `--ignore-case`, `-i` | Case-insensitive matching (string search only) |
| `--lang LANG` | Restrict search to one language (`python`, `javascript`, `typescript`, `c_sharp`) |
| `--files-only`, `-l` | Print only filenames of matching files |

## Output format

```
<file>:<line>:<col>: [<capture>] <matched text>
```

For string search, `<capture>` is omitted. For DSL and AST queries, `<capture>` is the concept name (e.g., `function`, `class`, `parameter.type`).

Parse errors are reported on stderr; search results from the partial AST are still returned.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Matches found |
| `1` | No matches |
| `2` | Invalid query or pattern |

---

## Security scanning demo

`demo/csharp/` is a self-contained C# project with intentional security vulnerabilities. Use it to try out codesearch queries for common code smells.

```
demo/csharp/
├── UserController.cs   — SQL injection, XSS, hardcoded credentials
├── AuthService.cs      — weak crypto (MD5/SHA1/DES/RC2), insecure random
├── FileService.cs      — path traversal, command injection, unsafe deserialisation
└── NetworkService.cs   — disabled SSL validation, hardcoded secrets, SSRF
```

### Secrets in GET request parameters

`demo/secrets-in-get.ini` uses a single `type = ast` query with `captures = _param` to find C# action methods that are both decorated with `[HttpGet]` **and** accept parameters with sensitive names (`password`, `secret`, `apiKey`, `token`, `credential`, `key`, `passwd`).

Because it is a structural AST query it avoids false positives: a `[HttpPost]` method with a `password` parameter is correctly ignored, and a `[HttpGet]` method with a non-sensitive parameter is not flagged.

```bash
uv run codesearch --filter-file demo/secrets-in-get.ini <path>
```

Example output against GDVCSharp:

```
app/controllers/HardcodedSecrets.cs:41:54: [secrets-in-get-request] password
app/controllers/HardcodedSecrets.cs:41:72: [secrets-in-get-request] apiKey
```

The `captures = _param` field is what makes this work cleanly: the query captures both `@_attr` (the `HttpGet` attribute, needed only to verify the method's HTTP verb) and `@_param` (the sensitive parameter name). Without `captures`, both would appear in the output. With `captures = _param`, only the parameter result is shown.

---

### GDVCSharp — full app scan

`demo/gdvcsharp-security.ini` targets [GDVCSharp](https://github.com/Uraxii/gdvcsharp), a deliberately vulnerable .NET 8 Web API. Clone the repo and point the filter file at its `app/` directory:

```bash
git clone https://github.com/Uraxii/gdvcsharp
uv run codesearch --filter-file demo/gdvcsharp-security.ini gdvcsharp/app/
```

The filter covers all vulnerability classes in that app:

| Query name | Vulnerability |
|---|---|
| `hardcoded-api-key` | `const string` values starting with `"sk-"` |
| `hardcoded-aws-key` | `const string` values starting with `"AKIA"` |
| `hardcoded-password-constant` | Constants whose name contains PASSWORD/PASS/PWD |
| `hardcoded-secret-constant` | Constants whose name contains SECRET/KEY/TOKEN |
| `hardcoded-key-in-getbytes` | String literals passed to `GetBytes()` (JWT/crypto keys) |
| `auth-bypass-via-header` | `Request.Headers[...]` used for authorization |
| `auth-bypass-via-cookie` | `Request.Cookies[...]` used for authorization |
| `role-as-method-parameter` | Methods with a `role` parameter the caller controls |
| `admin-action-over-get` | Admin routes reachable via HTTP GET |
| `credential-in-log` | Passwords or API keys interpolated into log calls |
| `password-as-method-parameter` | Methods accepting a `password` parameter |
| `secret-as-method-parameter` | Methods accepting a `secret` parameter |
| `apikey-as-method-parameter` | Methods accepting an `apiKey` parameter |
| `xss-html-content-type` | Actions returning `"text/html"` with unsanitised input |
| `xss-innerhtml-assignment` | `innerHTML` writes that may reflect server data |
| `ssrf-http-get` | `HttpClient.GetStringAsync` with user-supplied URL |
| `ssrf-http-post` | `HttpClient.PostAsync` with user-supplied URL |
| `ssrf-webclient-download` | `WebClient.DownloadString` with user-supplied URL |
| `path-traversal-combine` | `Path.Combine` with user-supplied path segment |
| `path-traversal-readalltext` | `File.ReadAllText` with user-controlled path |
| `path-traversal-getfiles` | `Directory.GetFiles` with user-controlled path |
| `path-traversal-getdirectories` | `Directory.GetDirectories` with user-controlled path |
| `regex-constructor-call` | All `Regex` usages — review for user-supplied patterns |
| `redos-nested-quantifier` | Regex literals containing `+)+`, `*)+`, or `+)*` |
| `regex-no-timeout` | `new Regex(...)` without a `TimeSpan` timeout |
| `weak-jwt-issuer-not-validated` | `ValidateIssuer = false` |
| `weak-jwt-audience-not-validated` | `ValidateAudience = false` |
| `weak-jwt-lifetime-not-validated` | `ValidateLifetime = false` |
| `cors-allow-any-origin` | `.AllowAnyOrigin()` on CORS policy |
| `cors-allow-any-method` | `.AllowAnyMethod()` on CORS policy |
| `cors-allow-any-header` | `.AllowAnyHeader()` on CORS policy |
| `exposed-swagger-endpoint` | `UseSwagger()` middleware registered |
| `exposed-swagger-ui` | `UseSwaggerUI()` middleware registered |

---

### Simple demo — `csharp-security.ini`

`demo/csharp-security.ini` bundles all queries into a single filter file. Run all of them in one command:

```bash
uv run codesearch --filter-file demo/csharp-security.ini demo/csharp/
```

Each result is labelled with the query name:

```
demo/csharp/AuthService.cs:16:29: [weak-hash-md5] MD5
demo/csharp/AuthService.cs:24:30: [weak-hash-sha1] SHA1
demo/csharp/AuthService.cs:33:27: [insecure-random] Random
demo/csharp/FileService.cs:32:32: [command-injection] Start
demo/csharp/FileService.cs:54:33: [unsafe-deserialisation] BinaryFormatter
demo/csharp/NetworkService.cs:22:33: [disabled-ssl] ServicePointManager.ServerCertificateValidationCallback =
demo/csharp/UserController.cs:18:28: [sql-injection] string query = "SELECT * FROM ...
...
```

### Running individual queries

All commands below target `demo/csharp/`. Run them from the repo root.

#### 1. Hardcoded secrets in string constants

Finds string constants whose values look like passwords, API keys, or other credentials.

```bash
uv run codesearch --regex 'const string.*=\s*"[A-Za-z0-9!@#$%^&*_\-]{8,}"' demo/csharp/
```

#### 2. SQL injection — raw string concatenation

Finds SQL keyword strings — review each site to check whether user input flows in via concatenation or `string.Format`.

```bash
uv run codesearch --regex '"SELECT |INSERT INTO|UPDATE |DELETE FROM' demo/csharp/
```

#### 3. Weak hash algorithms (MD5 / SHA1)

```bash
uv run codesearch --query 'identifier where text = "MD5"' demo/csharp/
uv run codesearch --query 'identifier where text = "SHA1"' demo/csharp/
```

#### 4. Broken symmetric ciphers (DES / RC2)

```bash
uv run codesearch --query 'identifier where text = "DES"' demo/csharp/
uv run codesearch --query 'identifier where text = "RC2"' demo/csharp/
```

#### 5. Cryptographically insecure random

`System.Random` is not suitable for tokens or codes used in security contexts.

```bash
uv run codesearch --query 'identifier where text = "Random"' --lang c_sharp demo/csharp/
```

#### 6. Disabled SSL/TLS certificate validation

```bash
uv run codesearch --regex 'ServerCertificateValidationCallback' demo/csharp/
uv run codesearch --regex 'ServerCertificateCustomValidationCallback' demo/csharp/
```

#### 7. Unsafe deserialisation (BinaryFormatter)

`BinaryFormatter` can execute arbitrary code when fed attacker-controlled data.

```bash
uv run codesearch --query 'identifier where text = "BinaryFormatter"' demo/csharp/
```

#### 8. Unsafe JSON deserialisation (TypeNameHandling)

`TypeNameHandling.All` or `TypeNameHandling.Objects` allows type-confusion attacks.

```bash
uv run codesearch --query 'identifier where text = "TypeNameHandling"' demo/csharp/
```

#### 9. Command injection — `Process.Start` calls

Find all `Process.Start` call sites and inspect whether the arguments include user-controlled data.

```bash
uv run codesearch --query 'call where name = "Start"' --lang c_sharp demo/csharp/
```

#### 10. Path traversal — file read/write with user-supplied paths

Look for `Path.Combine` and direct `File` calls, then check whether the path argument is validated.

```bash
uv run codesearch --query 'call where name = "Combine"' --lang c_sharp demo/csharp/
uv run codesearch --query 'call where name = "ReadAllText"' --lang c_sharp demo/csharp/
uv run codesearch --query 'call where name = "WriteAllText"' --lang c_sharp demo/csharp/
```

#### 11. SSRF — unvalidated outbound HTTP calls

```bash
uv run codesearch --query 'call where name = "DownloadString"' --lang c_sharp demo/csharp/
```

### Expected output

Each result is printed as `file:line:col: [capture] matched text`. For example:

```
$ uv run codesearch --query 'identifier where text = "MD5"' demo/csharp/
demo/csharp/AuthService.cs:16:29: [identifier] MD5

$ uv run codesearch --regex '"SELECT |INSERT INTO|UPDATE |DELETE FROM' demo/csharp/
demo/csharp/UserController.cs:18:28:             string query = "SELECT * FROM Users WHERE Username = '" + username + "'";
demo/csharp/UserController.cs:29:42:             string query = string.Format("SELECT * FROM Users WHERE Id = {0} ...
```

---

## Development

```bash
uv run pytest        # run tests
```
