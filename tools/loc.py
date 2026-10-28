"""Count lines of code for the paper (device library, camera header, backend).

Rule. A line is counted when, after removing comments, something other than
whitespace is left on it:

- Blank lines are not counted.
- C++: `//` and `/* ... */` comments (also multi-line ones) are removed first;
  comment markers inside string literals are not comments. A line holding only
  a comment is not counted; a line with code and a trailing comment is counted.
- Python: `#` comments are removed (with the tokenizer, so `#` inside a string
  is not a comment). A string continued over several lines counts each of its
  non-blank lines.

Two columns:
- "code": the rule above. C++ preprocessor lines (#include, #pragma, #if, #define...)
  and Python docstrings are counted.
- "strict": also leaves out C++ preprocessor lines and Python docstrings (the first
  string statement of a module, class or function).
"physical" is every line of the file (or class), blank lines and comments included.

The paper's numbers (2026-10) come from:
- device library 527 = "strict" of BeyondBoard.h + Cloud.cpp + LocalCloud.cpp +
  BeyondBoardAws.h (the root certificate in AwsCloudCA.h is not counted)
- camera header 104 = "strict" of BeyondBoardCamera.h
- shared core 226 = "strict" of backend/runtime/core.py
- AWS adapter 170 and local adapter 152 = "strict" lines of the AwsAdapter and
  LocalAdapter classes (docstrings excluded, as for the others)

Usage: python3 tools/loc.py
"""
import ast
import io
import os
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "arduino/BeyondBoard/src/"

# (group, [(file, class or None)]). A class entry counts only the lines of that class.
GROUPS = [
    ("device library", [(SRC + f, None) for f in ["BeyondBoard.h", "Cloud.cpp", "LocalCloud.cpp", "BeyondBoardAws.h"]]),
    ("root certificate (not in the paper's count)", [(SRC + "AwsCloudCA.h", None)]),
    ("camera header", [(SRC + "BeyondBoardCamera.h", None)]),
    ("shared core", [("backend/runtime/core.py", None)]),
    ("AWS adapter, whole files", [("backend/runtime/handler.py", None), ("backend/runtime/shim.py", None)]),
    ("AWS adapter, class only", [("backend/runtime/handler.py", "AwsAdapter")]),
    ("local adapter, whole file", [("local/cloud_local.py", None)]),
    ("local adapter, class only", [("local/cloud_local.py", "LocalAdapter")]),
]


def cpp_lines(text):
    """Returns the code left on each line after removing C++ comments."""
    out, line = [], []
    i, n = 0, len(text)
    in_block = False
    quote = None
    while i < n:
        c = text[i]
        if c == "\n":
            out.append("".join(line))
            line = []
            i += 1
            continue
        if in_block:
            if text.startswith("*/", i):
                in_block = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            line.append(c)
            if c == "\\" and i + 1 < n and text[i + 1] != "\n":
                line.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if text.startswith('R"', i) and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
            # raw string literal R"delim( ... )delim"
            open_paren = text.index("(", i)
            end = ")" + text[i + 2:open_paren] + '"'
            close = text.index(end, open_paren) + len(end)
            for ch in text[i:close]:
                if ch == "\n":
                    out.append("".join(line))
                    line = []
                else:
                    line.append(ch)
            i = close
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            in_block = True
            i += 2
            continue
        if c in "\"'":
            quote = c
        line.append(c)
        i += 1
    if line:
        out.append("".join(line))
    return out


def count_cpp(text):
    """Returns (code, strict) as sets of line numbers."""
    code, strict, cont = set(), set(), False
    for no, s in enumerate(cpp_lines(text), 1):
        s = s.strip()
        if not s:
            continue
        code.add(no)
        if cont or s.startswith("#"):
            cont = s.endswith("\\")
        else:
            strict.add(no)
    return code, strict


def count_py(text):
    """Returns (code, strict) as sets of line numbers."""
    docs = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docs.update(range(body[0].lineno, body[0].end_lineno + 1))
    code = set()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                        tokenize.DEDENT, tokenize.ENDMARKER):
            continue
        code.update(range(tok.start[0], tok.end[0] + 1))
    code -= {no for no, line in enumerate(text.splitlines(), 1) if not line.strip()}  # blank lines in strings
    return code, code - docs


def class_lines(text, name):
    for node in ast.parse(text).body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return range(node.lineno - len(node.decorator_list), node.end_lineno + 1)
    raise SystemExit(f"class {name} not found")


def count(rel, cls):
    """Returns (code, strict, physical) for a file or one class in it."""
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        text = f.read()
    code, strict = count_py(text) if rel.endswith(".py") else count_cpp(text)
    lines = class_lines(text, cls) if cls else range(1, len(text.splitlines()) + 1)
    keep = set(lines)
    return len(code & keep), len(strict & keep), len(keep)


def main():
    print(f"{'group / file':52}{'code':>7}{'strict':>8}{'physical':>10}")
    for name, entries in GROUPS:
        total = [0, 0, 0]
        for rel, cls in entries:
            n = count(rel, cls)
            if len(entries) > 1:
                print(f"  {rel + (' ' + cls if cls else ''):50}{n[0]:7}{n[1]:8}{n[2]:10}")
            total = [t + x for t, x in zip(total, n)]
        print(f"{name:52}{total[0]:7}{total[1]:8}{total[2]:10}")


if __name__ == "__main__":
    main()
