"""Code metrics for the five sample applications built three ways (E7).

Everything here is computed from the files; nothing is judged by hand except the
fixed tables below (which file plays which role, and which names belong to a
platform). Both tables are printed so that they can be checked.

Approaches and files (evaluation/baselines/, arduino/BeyondBoard/examples/, backend/):
- raw_aws: sketch + secrets.h (user), Lambda code (user, apps 2-5), the app's
  IoT Rule SQL (typed into the console; kept in raw_aws/cloud/iot_rules.sql).
- arduino_cloud: sketch (user, starting from the generated skeleton),
  arduino_secrets.h (made by Arduino Cloud, user fills the values),
  thingProperties.h (generated, "DO NOT EDIT"), cloud function (user, app 3: a Lambda
  function URL the sketch calls). Apps 4-5 call Bedrock from the sketch, so no cloud code.
- beyondboard: sketch (user), aws_config.h (made by `npm run deploy`, user fills
  the Wi-Fi lines; rebuilt here from the template in backend/scripts/devices.mjs
  with placeholders, so no real token is read), backend/functions/*.py (app 3).
Data files (backend/files/config.json, an S3 object for raw_aws) and settings
done in a web console (IoT/IAM policies, function URLs, variables) are not files the
user writes code in and are not counted (E1 counts them as steps).

Rules
- LOC: tools/loc.py "code" (non-blank, non-comment; preprocessor lines counted).
  SQL: lines left after removing `--` comments.
- Tokens: lexical tokens with comments removed. C++: identifiers, numbers,
  string/char literals (a raw string R"x(...)x" is one token), header names
  (<...> after #include), operators and punctuation (longest match), `#`.
  Python: the tokenize module, without COMMENT/NL/NEWLINE/INDENT/DEDENT/ENDMARKER.
  SQL: words, quoted strings, numbers, symbols.
- Functions: C++ function definitions at file scope (`name(...) {`); Python `def`.
  Callbacks = functions the platform calls rather than the user: setup/loop
  (Arduino), lambda_handler (Lambda), run (BeyondBoard function), and any
  function whose name is passed as a value (followed by `)` or `,`, e.g.
  client.onMessage(messageHandler), addProperty(..., onResultChange)).
- Cyclomatic complexity per function: 1 + (if, for, while, case, catch, &&, ||, ?)
  in C++; 1 + (if, elif, for, while, except, and, or) in Python. If `lizard`
  can be imported, its numbers are computed too and compared.
- Platform API identifiers: names in user-written code that are declared by a
  platform or a third-party library, not by the language, its standard library,
  or the Arduino core (Serial, delay, millis, random, String, PROGMEM ...).
  C++: members used on an object of a platform type or a platform global
  (`client.publish` -> MQTTClient.publish), subscripts of a JsonDocument,
  `.as<>()` on a JSON value, and free names in PLATFORM_FREE (functions,
  types, constants, generated names). Python: boto3.client and each service
  name, methods called on a boto3 client, `.read()` on a response value, and
  platform URLs (Arduino Cloud REST). SQL: the keywords of the IoT Rule.
  Separately, "schema keys": keyword arguments and string keys whose names are
  fixed by a platform's request/response/event format (PLATFORM_KEYS); other
  string keys are the user's own (they must match between device and cloud).
- Credential lines (device side): lines inside a PEM block (BEGIN..END) and
  string definitions whose name contains PASS, PASSWORD, KEY or TOKEN.
  "expected" replaces an elided PEM block by the size given in the comment
  above it ("about N lines"). Identity lines: SSID, Wi-Fi name, endpoint, URL,
  thing or login name.
- Couplings: names that must be spelled the same on the device and in the
  cloud: string literals / identifiers of device files that appear as string
  literals, string keys, SQL strings or file names of the cloud-side files.
- Change size: unified diff (no context) between two versions, counting added
  and removed lines; "code" diffs the LOC lines (comments and blank lines
  removed, spaces trimmed), "physical" diffs the files as they are.

Usage: python3 tools/code_metrics.py   (prints tables, writes evaluation/e7_code_metrics.csv)
"""
import ast
import csv
import difflib
import io
import os
import re
import sys
import tokenize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loc import count_cpp, count_py, cpp_lines  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "evaluation/baselines/"
EXAMPLES = "arduino/BeyondBoard/examples/"
OUT_CSV = "evaluation/e7_code_metrics.csv"

APPS = ["app1_save", "app2_load", "app3_run", "app4_ask", "app5_classify"]
OURS = {"app1_save": "01_SaveSensor", "app2_load": "02_LoadConfig", "app3_run": "03_RunFunction",
        "app4_ask": "04_AskExplain", "app5_classify": "05_AskClassify"}
RAW_LAMBDA = {"app2_load": "app2_config_lambda.py", "app3_run": "app3_anomaly_lambda.py",
              "app4_ask": "app4_ask_lambda.py", "app5_classify": "app5_classify_lambda.py"}
OURS_FUNCTION = {"app3_run": "backend/functions/detectAnomaly.py"}
APPROACHES = ["raw_aws", "arduino_cloud", "beyondboard"]

# ---- platform names -------------------------------------------------------------------------

# C++ types declared by a platform library (a variable of this type makes its members platform API).
PLATFORM_TYPES = {
    "WiFiClientSecure": "ESP32 core NetworkClientSecure",
    "MQTTClient": "arduino-mqtt (256dpi)",
    "JsonDocument": "ArduinoJson 7",
    "WiFiConnectionHandler": "Arduino_ConnectionHandler",
    "HTTPClient": "ESP32 core HTTPClient",
}
# Global objects of a platform library.
PLATFORM_OBJECTS = {"WiFi": "ESP32 core WiFi", "ArduinoCloud": "ArduinoIoTCloud",
                    "aws": "BeyondBoard", "local": "BeyondBoard"}
# Free functions, constants and generated names.
PLATFORM_FREE = {
    "serializeJson": "ArduinoJson 7", "deserializeJson": "ArduinoJson 7",
    "WIFI_STA": "ESP32 core WiFi", "WL_CONNECTED": "ESP32 core WiFi",
    "setDebugMessageLevel": "Arduino_DebugUtils (ArduinoIoTCloud)",
    "READ": "ArduinoIoTCloud", "READWRITE": "ArduinoIoTCloud", "ON_CHANGE": "ArduinoIoTCloud",
    "initProperties": "Arduino Cloud generated", "ArduinoIoTPreferredConnection": "Arduino Cloud generated",
}
BOTO3_SERVICES = {"s3": "S3", "iot-data": "IoTDataPlane", "bedrock-runtime": "BedrockRuntime"}
PLATFORM_URL = re.compile(r"https://api2\.arduino\.cc")
# Names fixed by a platform's request, response or event format, per platform. An approach
# checks only the formats it uses (raw_aws: AWS; arduino_cloud: all three), so that a key the
# user chose (e.g. event["name"] in a raw_aws Lambda) is not taken for a platform name.
PLATFORM_KEYS = {
    # boto3 S3 / IoT data plane / Bedrock Converse
    "aws": {"Bucket", "Key", "Body", "topic", "qos", "payload", "modelId", "messages", "inferenceConfig",
            "role", "content", "text", "maxTokens", "output", "message"},
    # Lambda function URL event and response
    "lambda_url": {"body", "statusCode"},
    # Arduino Cloud webhook payload and REST API (OAuth client credentials)
    "arduino_cloud": {"values", "name", "value", "thing_id", "grant_type", "client_id", "client_secret",
                      "audience", "access_token"},
}
KEYS_BY_APPROACH = {"raw_aws": PLATFORM_KEYS["aws"], "beyondboard": set(),
                    "arduino_cloud": set().union(*PLATFORM_KEYS.values())}
# Generic HTTP names (not platform-specific): reported as neither.
HTTP_KEYS = {"Authorization", "Content-Type"}
CALLBACK_NAMES = {"setup", "loop", "lambda_handler", "run"}
CORE_HEADERS = {"pgmspace.h", "Arduino.h"}

# Skeleton that Arduino Cloud writes into a new sketch (code lines, spaces trimmed).
# Lines of an arduino_cloud sketch equal to one of these are counted as "skeleton".
AC_SKELETON = ['#include "arduino_secrets.h"', '#include "thingProperties.h"', "void setup() {",
               "Serial.begin(9600);", "delay(1500);", "initProperties();",
               "ArduinoCloud.begin(ArduinoIoTPreferredConnection);", "setDebugMessageLevel(2);",
               "ArduinoCloud.printDebugInfo();", "}", "void loop() {", "ArduinoCloud.update();"]  # + "}"
AC_CALLBACK_SKELETON = re.compile(r"^void on\w+Change\(\) \{$")

# ---- files ------------------------------------------------------------------------------------


class Artifact:
    """One file (or one part of a file) the user deals with."""

    def __init__(self, approach, label, side, role, lang, path=None, text=None, fills=None, kind=None):
        self.approach = approach
        self.label, self.side, self.role, self.lang, self.path = label, side, role, lang, path
        self.kind = kind or label  # matches the same file across versions in a diff
        self.fills = fills  # regex of the names whose values the user writes (role "user_values")
        if text is None:
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                text = f.read()
        self.text = text


def sql_sections():
    """Splits iot_rules.sql into the rule of each app ("-- App N" headers)."""
    with open(os.path.join(ROOT, BASE, "raw_aws/cloud/iot_rules.sql"), encoding="utf-8") as f:
        text = f.read()
    sections, current = {}, None
    for line in text.splitlines(keepends=True):
        m = re.match(r"--\s*App (\d)", line)
        if m:
            current = APPS[int(m.group(1)) - 1]
        if current:
            sections[current] = sections.get(current, "") + line
    return sections


def aws_config_template():
    """aws_config.h as `npm run deploy` writes it, with placeholders for the values."""
    with open(os.path.join(ROOT, "backend/scripts/devices.mjs"), encoding="utf-8") as f:
        src = f.read()
    body = re.search(r"`(// Made by .*?)`,\n", src, re.S).group(1).replace("\\`", "`")
    values = {"device": "device-1", "wifi.name": "wifi-name", "wifi.password": "wifi-password",
              "apiUrl": "https://xxxxxxxx.lambda-url.ap-northeast-1.on.aws", "token": "xxxxxxxxxxxxxxxx"}
    return re.sub(r"\$\{([^}]*)\}", lambda m: values.get(m.group(1), "0"), body)


SQL = sql_sections()
AWS_CONFIG = aws_config_template()


def artifacts(approach, app):
    a = []
    if approach == "raw_aws":
        d = BASE + "raw_aws/" + app + "/"
        a.append(Artifact(approach, "sketch", "device", "user", "C++", d + app + ".ino"))
        a.append(Artifact(approach, "secrets.h", "device", "user", "C++", d + "secrets.h"))
        if app in RAW_LAMBDA:
            a.append(Artifact(approach, "lambda", "cloud", "user", "Python", BASE + "raw_aws/cloud/" + RAW_LAMBDA[app]))
        a.append(Artifact(approach, "rule SQL", "cloud", "user", "SQL", BASE + "raw_aws/cloud/iot_rules.sql#" + app,
                          text=SQL[app]))
    elif approach == "arduino_cloud":
        d = BASE + "arduino_cloud/" + app + "/"
        a.append(Artifact(approach, "sketch", "device", "user", "C++", d + app + ".ino"))
        a.append(Artifact(approach, "arduino_secrets.h", "device", "user_values", "C++", d + "arduino_secrets.h",
                          fills=r"SECRET_\w+"))
        a.append(Artifact(approach, "thingProperties.h", "device", "generated", "C++", d + "thingProperties.h"))
        function = BASE + "arduino_cloud/cloud/" + app.split("_")[0] + "_function.py"
        if os.path.exists(os.path.join(ROOT, function)):
            a.append(Artifact(approach, "function", "cloud", "user", "Python", function))
    else:
        d = EXAMPLES + OURS[app] + "/"
        a.append(Artifact(approach, "sketch", "device", "user", "C++", d + OURS[app] + ".ino"))
        a.append(Artifact(approach, "aws_config.h", "device", "user_values", "C++",
                          "backend/out/device-1/aws_config.h (template)", text=AWS_CONFIG,
                          fills=r"AWS_WIFI_\w+"))
        if app in OURS_FUNCTION:
            a.append(Artifact(approach, "function", "cloud", "user", "Python", OURS_FUNCTION[app]))
    return a


# ---- lexers -----------------------------------------------------------------------------------

CPP_OPS = sorted("""<<= >>= -> ++ -- << >> <= >= == != && || += -= *= /= %= &= |= ^= :: ...
+ - * / % < > = ! ~ & | ^ ? : ; , . ( ) [ ] { } #""".split(), key=len, reverse=True)
CPP_TOKEN = re.compile(
    r'(?P<raw>R"(?P<delim>[^(\s]*)\(.*?\)(?P=delim)")'
    r'|(?P<str>"(?:\\.|[^"\\\n])*")'
    r"|(?P<chr>'(?:\\.|[^'\\\n])*')"
    r"|(?P<num>\.?\d(?:[\w.]|[eEpP][+-])*)"
    r"|(?P<id>[A-Za-z_]\w*)"
    r"|(?P<op>" + "|".join(re.escape(o) for o in CPP_OPS) + ")",
    re.S,
)


def strip_cpp_comments(text):
    return "\n".join(cpp_lines(text))


def cpp_tokens(text):
    """Returns [(kind, value, line)] for C++ source; comments removed."""
    src = strip_cpp_comments(text)
    out, i, line = [], 0, 1
    while i < len(src):
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        if out and out[-1][1] == "include" and c == "<":
            j = src.index(">", i)
            out.append(("header", src[i + 1:j], line))
            i = j + 1
            continue
        m = CPP_TOKEN.match(src, i)
        if not m:
            raise ValueError(f"cannot read C++ at line {line}: {src[i:i + 20]!r}")
        kind = m.lastgroup if m.lastgroup != "delim" else "raw"
        kind = "str" if kind == "raw" else kind
        value = m.group(0)
        if kind == "str" and out and out[-1][1] == "include":
            kind, value = "header", value.strip('"')
        out.append((kind, value, line))
        line += value.count("\n")
        i = m.end()
    return out


def str_value(tok):
    """Contents of a C++ string literal token."""
    v = tok[1]
    m = re.match(r'R"([^(]*)\((.*)\)\1"$', v, re.S)
    return m.group(2) if m else v[1:-1]


PY_SKIP = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
           tokenize.ENDMARKER, tokenize.ENCODING}


def py_tokens(text):
    return [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type not in PY_SKIP]


def sql_strip(text):
    return [re.sub(r"--.*", "", line).strip() for line in text.splitlines()]


def sql_tokens(text):
    return re.findall(r"'[^']*'|\w+|[^\s\w]", "\n".join(sql_strip(text)))


# ---- per-file metrics -------------------------------------------------------------------------


def code_lines(art):
    """The LOC lines of a file, comments removed and spaces trimmed (used for LOC and diffs)."""
    if art.lang == "SQL":
        return [s for s in sql_strip(art.text) if s]
    if art.lang == "Python":
        code, _ = count_py(art.text)
        lines = art.text.splitlines()
        for tok in tokenize.generate_tokens(io.StringIO(art.text).readline):
            if tok.type == tokenize.COMMENT:
                no, col = tok.start
                lines[no - 1] = lines[no - 1][:col]
        return [lines[no - 1].strip() for no in sorted(code)]
    code, _ = count_cpp(art.text)
    stripped = cpp_lines(art.text)
    return [stripped[no - 1].strip() for no in sorted(code)]


def cpp_functions(toks):
    """[(name, first_token, last_token)] for function definitions at file scope."""
    funcs, depth, i = [], 0, 0
    while i < len(toks):
        v = toks[i][1]
        if v == "{":
            if depth == 0 and i > 0 and toks[i - 1][1] == ")":
                j, paren = i - 1, 0
                while True:
                    paren += {")": 1, "(": -1}.get(toks[j][1], 0)
                    if paren == 0:
                        break
                    j -= 1
                name = toks[j - 1][1]
                k, d = i, 0
                while True:
                    d += {"{": 1, "}": -1}.get(toks[k][1], 0)
                    if d == 0:
                        break
                    k += 1
                funcs.append((name, i, k))
                i = k + 1
                continue
            depth += 1
        elif v == "}":
            depth -= 1
        i += 1
    return funcs


CPP_DECISIONS = {"if", "for", "while", "case", "catch", "&&", "||", "?"}
PY_DECISIONS = {"if", "elif", "for", "while", "except", "and", "or"}


def functions(art):
    """[(name, ccn)] of the functions defined in a file."""
    if art.lang == "C++":
        toks = cpp_tokens(art.text)
        return [(name, 1 + sum(t[1] in CPP_DECISIONS and t[0] in ("id", "op") for t in toks[a:b]))
                for name, a, b in cpp_functions(toks)]
    if art.lang == "Python":
        toks = py_tokens(art.text)
        out = []
        for node in ast.walk(ast.parse(art.text)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = [t for t in toks if node.lineno <= t.start[0] <= node.end_lineno]
                out.append((node.name, 1 + sum(t.type == tokenize.NAME and t.string in PY_DECISIONS
                                               for t in body)))
        return out
    return []


def lizard_functions(art):
    try:
        import lizard
    except ImportError:
        return None
    if art.lang == "SQL":
        return []
    name = "x.cpp" if art.lang == "C++" else "x.py"
    info = lizard.analyze_file.analyze_source_code(name, art.text)
    return [(f.name.split("::")[-1], f.cyclomatic_complexity) for f in info.function_list]


def cpp_api(toks):
    """Platform API names, user string keys, and included library headers in C++ tokens."""
    typed = {}
    for i, (k, v, _) in enumerate(toks):
        if k == "id" and v in PLATFORM_TYPES:
            j = i + 1
            while j < len(toks) and toks[j][1] in ("&", "*"):
                j += 1
            if j < len(toks) and toks[j][0] == "id":
                typed[toks[j][1]] = v
    api, keys, headers = set(), set(), set()
    for i, (k, v, _) in enumerate(toks):
        prev = toks[i - 1][1] if i else ""
        nxt = toks[i + 1][1] if i + 1 < len(toks) else ""
        if k == "header":
            headers.add(v)
        elif k == "id" and prev != ".":
            if v in PLATFORM_TYPES or v in PLATFORM_FREE:
                api.add(v)
            owner = typed.get(v) or (v if v in PLATFORM_OBJECTS else None)
            if owner and nxt == "." and i + 2 < len(toks):
                api.add(f"{owner}.{toks[i + 2][1]}")
            if typed.get(v) == "JsonDocument" and nxt == "[":
                api.add("JsonDocument[]")
                # every string subscript in the chain: d["a"][0]["b"] -> a, b
                j = i + 1
                while j + 2 < len(toks) and toks[j][1] == "[" and toks[j + 2][1] == "]":
                    if toks[j + 1][0] == "str":
                        keys.add(str_value(toks[j + 1]))
                    j += 3
        elif k == "id" and prev == "." and v == "as" and i >= 2 and toks[i - 2][1] == "]":
            api.add("JsonVariant.as")
    return api, keys, headers


def py_api(text, platform_keys):
    """Platform API names, schema keys, user keys, and imported modules in Python code."""
    tree = ast.parse(text)
    clients, results = {}, set()
    api, schema, user, mods = set(), set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module.split(".")[0])
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "boto3":
                service = node.value.args[0].value
                for t in node.targets:
                    clients[t.id] = BOTO3_SERVICES.get(service, service)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in clients:
                results.update(t.id for t in node.targets if isinstance(t, ast.Name))
    fstring_parts = {id(p) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for p in n.values}
    for node in ast.walk(tree):
        if id(node) in fstring_parts:
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            f = node.func
            if isinstance(f.value, ast.Name) and f.value.id == "boto3":
                api.add(f"boto3.{f.attr}")
                api.update(f"service:{a.value}" for a in node.args if isinstance(a, ast.Constant))
            elif isinstance(f.value, ast.Name) and f.value.id in clients:
                api.add(f"{clients[f.value.id]}.{f.attr}")
                schema.update(kw.arg for kw in node.keywords)
            elif isinstance(f.value, ast.Subscript) and isinstance(f.value.value, ast.Name) \
                    and f.value.value.id in results:
                api.add(f"response.{f.attr}()")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and PLATFORM_URL.match(node.value):
            api.add("URL " + node.value)
        elif isinstance(node, ast.JoinedStr):
            s = "".join(p.value if isinstance(p, ast.Constant) else "{}" for p in node.values)
            if PLATFORM_URL.match(s):
                api.add("URL " + s)
        names = []
        if isinstance(node, ast.Dict):
            names = [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str):
            names = [node.slice.value]
        for n in names:
            if n in platform_keys:
                schema.add(n)
            elif n not in HTTP_KEYS:
                user.add(n)
    return api, schema, user, mods


def string_names(art):
    """Strings (and identifiers, for C++) that can tie this file to another one."""
    if art.lang == "C++":
        toks = cpp_tokens(art.text)
        names = {str_value(t) for t in toks if t[0] == "str"}
        if art.role == "generated":  # Arduino Cloud variables are declared here
            names |= {toks[i + 1][1] for i, t in enumerate(toks[:-2])
                      if t[1] in ("float", "int", "bool", "String") and toks[i + 2][1] == ";"}
        return names
    if art.lang == "Python":
        return {n.value for n in ast.walk(ast.parse(art.text))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return {s.strip("'") for s in sql_tokens(art.text) if s.startswith("'")}


SECRET_NAME = re.compile(r"(PASS|PASSWORD|KEY|TOKEN)\b")
IDENTITY_NAME = re.compile(r"(SSID|WIFI_NAME|ENDPOINT|URL|THINGNAME|LOGIN_NAME)\b")
DEFINE = re.compile(r'^\s*(?:#define\s+(\w+)|(?:static\s+)?const\s+char\s*\*?\s*(\w+)\s*\[?\]?.*?=)\s*.*"')


def credentials(art):
    """(credential lines, expected credential lines, typed by the user, identity lines)."""
    lines = art.text.splitlines()
    cred = exp = hand = ident = 0
    in_pem, block, block_expected = False, 0, None
    for no, line in enumerate(lines):
        if "-----BEGIN" in line:
            in_pem, block = True, 0
            block_expected = None
            for back in range(no - 1, max(no - 4, -1), -1):
                m = re.search(r"about (\d+) lines", lines[back])
                if m:
                    block_expected = int(m.group(1))
                    break
        if in_pem:
            block += 1
            if "-----END" in line:
                in_pem = False
                cred += block
                n = block_expected or block
                exp += n
                hand += n if art.role == "user" else 0
            continue
        m = DEFINE.match(line)
        name = m and (m.group(1) or m.group(2))
        if not name:
            continue
        user_fills = art.role == "user" or (art.fills and re.fullmatch(art.fills, name))
        if SECRET_NAME.search(name):
            cred += 1
            exp += 1
            hand += 1 if user_fills else 0
        elif IDENTITY_NAME.search(name):
            ident += 1
    return cred, exp, hand, ident


def measure(art):
    m = {"loc": len(code_lines(art)), "physical": len(art.text.splitlines())}
    if art.lang == "C++":
        toks = cpp_tokens(art.text)
        m["tokens"] = len(toks)
        api, keys, headers = cpp_api(toks)
        # A JSON key in device code is a platform name when the device itself speaks a
        # platform's format (Arduino Cloud apps 4-5 call Bedrock from the sketch).
        platform = KEYS_BY_APPROACH[art.approach] if art.approach == "arduino_cloud" else set()
        m["api"], m["schema"], m["user_keys"] = api, keys & platform, keys - platform - HTTP_KEYS
        m["headers"] = {h for h in headers if h not in CORE_HEADERS}
    elif art.lang == "Python":
        m["tokens"] = len(py_tokens(art.text))
        api, schema, user, mods = py_api(art.text, KEYS_BY_APPROACH[art.approach])
        m["api"], m["schema"], m["user_keys"] = api, schema, user
        m["headers"] = {x for x in mods if x not in sys.stdlib_module_names}
    else:
        toks = sql_tokens(art.text)
        m["tokens"] = len(toks)
        m["api"] = {"IoT Rules SQL " + t.upper() for t in toks if t.upper() in ("SELECT", "FROM", "WHERE")}
        m["schema"], m["user_keys"], m["headers"] = set(), set(), set()
    m["functions"] = functions(art)
    m["lizard"] = lizard_functions(art)
    m["cred"] = credentials(art) if art.side == "device" else (0, 0, 0, 0)
    return m


# ---- per app ----------------------------------------------------------------------------------


def callbacks(arts, funcs):
    """Names of the functions the platform calls (see the rule in the module docstring)."""
    passed = set()
    for a in arts:
        if a.lang != "C++":
            continue
        toks = cpp_tokens(a.text)
        for i in range(1, len(toks) - 1):
            if toks[i][0] == "id" and toks[i - 1][1] in ("(", ",") and toks[i + 1][1] in (")", ","):
                passed.add(toks[i][1])
    return {name for name in funcs if name in CALLBACK_NAMES or name in passed}


def skeleton_lines(art):
    """Lines of an Arduino Cloud sketch that the generated skeleton already holds.

    The skeleton is AC_SKELETON plus an empty `void onXChange() {` ... `}` for each
    variable callback in the sketch; matched in order (longest common subsequence).
    """
    lines = code_lines(art)
    skeleton = list(AC_SKELETON) + ["}"]
    for line in lines:
        if AC_CALLBACK_SKELETON.match(line):
            skeleton += [line, "}"]
    prev = [0] * (len(skeleton) + 1)
    for x in lines:
        cur = [0]
        for j, y in enumerate(skeleton):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def summarize(arts, side):
    """One CSV row for the artifacts of one side ("device", "cloud" or "all")."""
    sel = [a for a in arts if side == "all" or a.side == side]
    user = [a for a in sel if a.role == "user"]
    gen = [a for a in sel if a.role != "user"]
    ms = {id(a): measure(a) for a in sel}
    um = [ms[id(a)] for a in user]
    funcs = [f for m in um for f in m["functions"]]
    cbs = callbacks(arts, [n for n, _ in funcs])
    liz = [m["lizard"] for m in um]
    liz_funcs = None if any(x is None for x in liz) else [f for x in liz for f in x]
    api = set().union(*(m["api"] for m in um)) if um else set()
    api_gen = set().union(*(ms[id(a)]["api"] for a in gen)) - api if gen else set()
    schema = set().union(*(m["schema"] for m in um)) if um else set()
    ukeys = set().union(*(m["user_keys"] for m in um)) if um else set()
    own = {a.label for a in arts} | {os.path.basename(a.path) for a in arts}
    headers = set().union(*(m["headers"] for m in um)) - own if um else set()
    cred = [sum(ms[id(a)]["cred"][i] for a in sel) for i in range(4)]
    ccn = [c for _, c in funcs]
    row = {
        "files_user": len(user),
        "files_user_values": sum(a.role == "user_values" for a in sel),
        "files_generated": sum(a.role == "generated" for a in sel),
        "languages": "+".join(sorted({a.lang for a in user} | {a.lang for a in sel if a.role == "user_values"})),
        "loc_user": sum(m["loc"] for m in um),
        "loc_generated": sum(ms[id(a)]["loc"] for a in gen),
        "loc_skeleton": sum(skeleton_lines(a) for a in user if a.label == "sketch" and "arduino_cloud" in a.path),
        "physical_user": sum(m["physical"] for m in um),
        "tokens_user": sum(m["tokens"] for m in um),
        "tokens_generated": sum(ms[id(a)]["tokens"] for a in gen),
        "functions": len(funcs),
        "callbacks": sum(n in cbs for n, _ in funcs),
        "function_names": ";".join(f"{n}{'*' if n in cbs else ''}({c})" for n, c in funcs),
        "ccn_sum": sum(ccn),
        "ccn_max": max(ccn, default=0),
        "ccn_lizard_sum": "" if liz_funcs is None else sum(c for _, c in liz_funcs),
        "ccn_lizard_max": "" if liz_funcs is None else max((c for _, c in liz_funcs), default=0),
        "api_count": len(api),
        "api": ";".join(sorted(api)),
        "api_generated_only_count": len(api_gen),
        "schema_key_count": len(schema),
        "schema_keys": ";".join(sorted(schema)),
        "user_key_count": len(ukeys),
        "user_keys": ";".join(sorted(ukeys)),
        "libraries": ";".join(sorted(headers)),
        "cred_lines": cred[0],
        "cred_lines_expected": cred[1],
        "cred_lines_typed": cred[2],
        "identity_lines": cred[3],
    }
    if side == "all":
        dev = set().union(*(string_names(a) for a in arts if a.side == "device"))
        cloud = set()
        for a in arts:
            if a.side == "cloud":
                cloud |= string_names(a)
                cloud.add(os.path.splitext(os.path.basename(a.path.split("#")[0]))[0])
        shared = sorted((dev & cloud) - {""})
        row["coupling_count"] = len(shared)
        row["couplings"] = ";".join(shared)
    return row, api, schema


# ---- changes ----------------------------------------------------------------------------------

CHANGES_DIR = BASE + "changes/local_to_aws/"


def change_pairs():
    """(name, approach, [(kind, before or None, after or None)])."""
    out = []
    for target in ("app5_classify", "app4_ask"):
        for ap in APPROACHES:
            before = {a.kind: a for a in artifacts(ap, "app1_save")}
            after = {a.kind: a for a in artifacts(ap, target)}
            kinds = list(dict.fromkeys(list(before) + list(after)))
            out.append((f"add_ai:app1_to_{target.split('_')[0]}", ap,
                        [(k, before.get(k), after.get(k)) for k in kinds]))
    aws05 = artifacts("beyondboard", "app5_classify")
    cfg = aws05[1]
    local05 = Artifact("beyondboard", "sketch", "device", "user", "C++", CHANGES_DIR + "05_local/05_local.ino")
    out.append(("local_to_aws:app5", "beyondboard", [("sketch", local05, aws05[0]), ("aws_config.h", None, cfg)]))
    alias = [Artifact("beyondboard", "sketch", "device", "user", "C++", CHANGES_DIR + f"05_alias_{d}/05_alias_{d}.ino")
             for d in ("local", "aws")]
    out.append(("local_to_aws:app5_alias", "beyondboard", [("sketch", alias[0], alias[1]),
                                                           ("aws_config.h", None, cfg)]))
    return out


def diff_count(a, b):
    added = removed = 0
    for line in difflib.unified_diff(a, b, lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        added += line.startswith("+")
        removed += line.startswith("-")
    return added, removed


def change_row(pairs, side, role_filter):
    row = {"diff_added": 0, "diff_removed": 0, "diff_physical_added": 0, "diff_physical_removed": 0,
           "files_changed": 0, "files_added": 0, "files_removed": 0, "changed": []}
    for kind, a, b in pairs:
        art = b or a
        if side != "all" and art.side != side:
            continue
        if not role_filter(art.role):
            continue
        ca, cb = (code_lines(a) if a else []), (code_lines(b) if b else [])
        pa, pb = (a.text.splitlines() if a else []), (b.text.splitlines() if b else [])
        add, rem = diff_count(ca, cb)
        padd, prem = diff_count(pa, pb)
        if not (add or rem or padd or prem):
            continue
        row["diff_added"] += add
        row["diff_removed"] += rem
        row["diff_physical_added"] += padd
        row["diff_physical_removed"] += prem
        state = "added" if a is None else "removed" if b is None else "changed"
        row["files_" + state] += 1
        row["changed"].append(f"{kind}({state},+{add}/-{rem})")
    row["changed"] = ";".join(row["changed"])
    return row


# ---- loc.csv check ----------------------------------------------------------------------------


def loc_check(rows):
    path = os.path.join(ROOT, BASE, "loc.csv")
    with open(path, newline="") as f:
        expected = {r["app"]: r for r in csv.DictReader(f)}
    got = {}
    for app in APPS:
        by = {ap: {a.label: len(code_lines(a)) for a in artifacts(ap, app)} for ap in APPROACHES}
        got[app] = {
            "raw_sketch": by["raw_aws"]["sketch"], "raw_secrets_h": by["raw_aws"]["secrets.h"],
            "raw_cloud_code": by["raw_aws"].get("lambda", 0),
            "ac_sketch": by["arduino_cloud"]["sketch"],
            "ac_generated_files": by["arduino_cloud"]["thingProperties.h"] + by["arduino_cloud"]["arduino_secrets.h"],
            "ac_cloud_code": by["arduino_cloud"].get("function", 0),
            "ours_sketch": by["beyondboard"]["sketch"], "ours_cloud_code": by["beyondboard"].get("function", 0),
        }
    mismatches = [(app, col, expected[app][col], v) for app in APPS for col, v in got[app].items()
                  if int(expected[app][col]) != v]
    return mismatches, got


# ---- main -------------------------------------------------------------------------------------

COLUMNS = ["scope", "approach", "side", "files_user", "files_user_values", "files_generated", "languages",
           "loc_user", "loc_generated", "loc_skeleton", "physical_user", "tokens_user", "tokens_generated",
           "functions", "callbacks", "function_names", "ccn_sum", "ccn_max", "ccn_lizard_sum", "ccn_lizard_max",
           "api_count", "api", "api_generated_only_count", "schema_key_count", "schema_keys",
           "user_key_count", "user_keys", "libraries", "cred_lines", "cred_lines_expected", "cred_lines_typed",
           "identity_lines", "coupling_count", "couplings",
           "diff_added", "diff_removed", "diff_physical_added", "diff_physical_removed",
           "files_changed", "files_added", "files_removed", "changed"]


def main():
    rows = []
    union = {ap: {"device": [set(), set()], "cloud": [set(), set()], "all": [set(), set()]} for ap in APPROACHES}
    for app in APPS:
        for ap in APPROACHES:
            arts = artifacts(ap, app)
            for side in ("device", "cloud", "all"):
                row, api, schema = summarize(arts, side)
                union[ap][side][0] |= api
                union[ap][side][1] |= schema
                rows.append({"scope": app, "approach": ap, "side": side, **row})
    for ap in APPROACHES:
        for side in ("device", "cloud", "all"):
            api, schema = union[ap][side]
            rows.append({"scope": "union_app1-5", "approach": ap, "side": side, "api_count": len(api),
                         "api": ";".join(sorted(api)), "schema_key_count": len(schema),
                         "schema_keys": ";".join(sorted(schema))})
    for name, ap, pairs in change_pairs():
        rows.append({"scope": "change:" + name, "approach": ap, "side": "all (user-written)",
                     **change_row(pairs, "all", lambda r: r == "user")})
        rows.append({"scope": "change:" + name, "approach": ap, "side": "all (generated or user_values)",
                     **change_row(pairs, "all", lambda r: r != "user")})
    with open(os.path.join(ROOT, OUT_CSV), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})

    # Print the main tables.
    def get(scope, ap, side):
        return next(r for r in rows if r["scope"] == scope and r["approach"] == ap and r["side"] == side)

    print("Per app (user-written files; generated files in brackets)")
    print(f"{'app':15}{'approach':15}{'files':>6}{'langs':>18}{'LOC dev':>8}{'LOC cld':>8}{'tok dev':>8}"
          f"{'tok cld':>8}{'fn':>4}{'cb':>4}{'CCN':>5}{'max':>4}{'API':>5}{'keys':>5}{'cred':>5}{'exp':>5}"
          f"{'typed':>6}{'coupl':>6}")
    for app in APPS:
        for ap in APPROACHES:
            d, c, a = get(app, ap, "device"), get(app, ap, "cloud"), get(app, ap, "all")
            print(f"{app:15}{ap:15}{a['files_user']:>3}[{a['files_user_values'] + a['files_generated']}]"
                  f"{a['languages']:>18}{d['loc_user']:>8}{c['loc_user']:>8}{d['tokens_user']:>8}"
                  f"{c['tokens_user']:>8}{a['functions']:>4}{a['callbacks']:>4}{a['ccn_sum']:>5}{a['ccn_max']:>4}"
                  f"{a['api_count']:>5}{a['schema_key_count']:>5}{d['cred_lines']:>5}"
                  f"{d['cred_lines_expected']:>5}{d['cred_lines_typed']:>6}{a['coupling_count']:>6}")
    print("\nPlatform API identifiers, union over apps 1-5")
    for ap in APPROACHES:
        for side in ("device", "cloud"):
            r = get("union_app1-5", ap, side)
            print(f"  {ap:14}{side:7}{r['api_count']:>3}  {r['api']}")
            if r["schema_key_count"]:
                print(f"  {'':14}{'keys':7}{r['schema_key_count']:>3}  {r['schema_keys']}")
    print("\nChanges (code lines added/removed; physical in brackets)")
    for r in rows:
        if r["scope"].startswith("change:"):
            print(f"  {r['scope']:32}{r['approach']:15}{r['side']:32}+{r['diff_added']}/-{r['diff_removed']}"
                  f" [+{r['diff_physical_added']}/-{r['diff_physical_removed']}]  {r['changed']}")
    try:
        import lizard  # noqa: F401
        diffs = [r for r in rows if r.get("ccn_lizard_sum", "") != "" and
                 (r["ccn_lizard_sum"], r["ccn_lizard_max"]) != (r["ccn_sum"], r["ccn_max"])]
        print(f"\nlizard: {'agrees on every row' if not diffs else f'differs on {len(diffs)} rows'}")
        for r in diffs:
            print(f"  {r['scope']} {r['approach']} {r['side']}: own {r['ccn_sum']}/{r['ccn_max']}, "
                  f"lizard {r['ccn_lizard_sum']}/{r['ccn_lizard_max']}")
    except ImportError:
        print("\nlizard: not installed; own cyclomatic complexity only")
    mismatches, _ = loc_check(rows)
    print("\nloc.csv: " + ("every value matches" if not mismatches else "MISMATCH"))
    for app, col, exp, got in mismatches:
        print(f"  {app} {col}: loc.csv {exp}, computed {got}")
    print(f"\nwrote {OUT_CSV}")


if __name__ == "__main__":
    main()
