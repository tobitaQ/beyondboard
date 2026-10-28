#define BEYOND_BOARD_LIBRARY_SOURCE
#include "BeyondBoard.h"

// ---- small JSON helpers (the backend always answers with one flat object) ----

String cloudJsonString(const String& s) {
  String out;
  out.reserve(s.length() + 2);
  out += '"';
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    switch (c) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if ((uint8_t)c < 0x20) {
          out += F("\\u00");
          out += "0123456789abcdef"[(c >> 4) & 0xF];
          out += "0123456789abcdef"[c & 0xF];
        } else {
          out += c;
        }
    }
  }
  out += '"';
  return out;
}

static void appendUtf8(String& out, uint32_t cp) {
  if (cp < 0x80) {
    out += (char)cp;
  } else if (cp < 0x800) {
    out += (char)(0xC0 | (cp >> 6));
    out += (char)(0x80 | (cp & 0x3F));
  } else if (cp < 0x10000) {
    out += (char)(0xE0 | (cp >> 12));
    out += (char)(0x80 | ((cp >> 6) & 0x3F));
    out += (char)(0x80 | (cp & 0x3F));
  } else {
    out += (char)(0xF0 | (cp >> 18));
    out += (char)(0x80 | ((cp >> 12) & 0x3F));
    out += (char)(0x80 | ((cp >> 6) & 0x3F));
    out += (char)(0x80 | (cp & 0x3F));
  }
}

// Reads a JSON string starting at s[i] == '"'. Leaves i after the closing quote.
static bool readString(const String& s, size_t& i, String& out) {
  if (i >= s.length() || s[i] != '"') return false;
  i++;
  while (i < s.length()) {
    char c = s[i++];
    if (c == '"') return true;
    if (c != '\\') {
      out += c;
      continue;
    }
    if (i >= s.length()) return false;
    char e = s[i++];
    switch (e) {
      case 'n': out += '\n'; break;
      case 'r': out += '\r'; break;
      case 't': out += '\t'; break;
      case 'b': out += '\b'; break;
      case 'f': out += '\f'; break;
      case 'u': {
        if (i + 4 > s.length()) return false;
        uint32_t cp = strtoul(s.substring(i, i + 4).c_str(), nullptr, 16);
        i += 4;
        if (cp >= 0xD800 && cp < 0xDC00 && i + 6 <= s.length() && s[i] == '\\' && s[i + 1] == 'u') {
          uint32_t lo = strtoul(s.substring(i + 2, i + 6).c_str(), nullptr, 16);
          i += 6;
          cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
        }
        appendUtf8(out, cp);
        break;
      }
      default: out += e;  // \" \\ \/
    }
  }
  return false;
}

static void skipSpace(const String& s, size_t& i) {
  while (i < s.length() && isspace((unsigned char)s[i])) i++;
}

// Parses {"ok": .., "code": n, "error": "..", "result": ".."}.
static bool parseResponse(const String& s, int& code, String& error, String& result) {
  size_t i = 0;
  skipSpace(s, i);
  if (i >= s.length() || s[i++] != '{') return false;
  bool haveCode = false;
  while (true) {
    skipSpace(s, i);
    if (i < s.length() && s[i] == '}') return haveCode;
    String key;
    if (!readString(s, i, key)) return false;
    skipSpace(s, i);
    if (i >= s.length() || s[i++] != ':') return false;
    skipSpace(s, i);
    if (i < s.length() && s[i] == '"') {
      String value;
      if (!readString(s, i, value)) return false;
      if (key == "error") error = value;
      else if (key == "result") result = value;
    } else {
      size_t start = i;
      while (i < s.length() && s[i] != ',' && s[i] != '}' && !isspace((unsigned char)s[i])) i++;
      if (key == "code") {
        code = s.substring(start, i).toInt();
        haveCode = true;
      }
    }
    skipSpace(s, i);
    if (i < s.length() && s[i] == ',') {
      i++;
      continue;
    }
    if (i < s.length() && s[i] == '}') return haveCode;
    return false;
  }
}

// Base64 for bytes inside the JSON request (images up to 1 MB become about 1.4 MB).
static void appendBase64(String& out, const uint8_t* data, size_t length) {
  static const char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  out.reserve(out.length() + (length + 2) / 3 * 4 + 64);
  for (size_t i = 0; i < length; i += 3) {
    uint32_t n = (uint32_t)data[i] << 16;
    if (i + 1 < length) n |= (uint32_t)data[i + 1] << 8;
    if (i + 2 < length) n |= data[i + 2];
    out += table[(n >> 18) & 63];
    out += table[(n >> 12) & 63];
    out += i + 1 < length ? table[(n >> 6) & 63] : '=';
    out += i + 2 < length ? table[n & 63] : '=';
  }
}

// Numbers are saved without trailing zeros: 23.5 -> "23.5", 20.0 -> "20".
static String numberText(double value) {
  String s(value, 6);  // works on every board (AVR printf has no %f)
  if (s.indexOf('.') >= 0) {
    while (s.endsWith("0")) s.remove(s.length() - 1);
    if (s.endsWith(".")) s.remove(s.length() - 1);
  }
  return s;
}

// ---- Cloud: the calls every destination offers ----

bool Cloud::fail(int code, const String& message) {
  _code = code;
  _error = message;
  return false;
}

// Messages written with F("...") stay in flash, which matters on boards with
// little RAM (Arduino UNO has 2 KB).
bool Cloud::fail(int code, const __FlashStringHelper* message) {
  _code = code;
  _error = message;
  return false;
}

bool Cloud::checkName(const char* name) {
  size_t n = name ? strlen(name) : 0;
  bool good = n > 0 && n <= 128 && name[0] != '/' && strstr(name, "..") == nullptr;
  for (size_t i = 0; good && i < n; i++) {
    char c = name[i];
    good = isalnum((unsigned char)c) || c == '.' || c == '_' || c == '-' || c == '/';
  }
  if (!good) {
    return fail(CLOUD_ERR_INVALID_NAME, String('"') + (name ? name : "") +
                                            F("\" cannot be used as a name. Use letters, digits and "
                                              ". _ - / (up to 128)."));
  }
  return true;
}

bool Cloud::request(const char* op, const String& body, unsigned long timeoutMs, String* result) {
  if (!_ready) return fail(CLOUD_ERR_NOT_INITIALIZED, String(F("Call ")) + _name + F(".begin() first."));
  noteCall(op);
  String id = String((unsigned long)random(0x7FFFFFFF), HEX) + String(millis(), HEX);
  String answer;
  if (!send(op, body, timeoutMs, id, answer)) return false;

  int code = CLOUD_ERR_SERVER;
  String error, value;
  if (!parseResponse(answer, code, error, value)) {
    return fail(CLOUD_ERR_SERVER, F("The cloud returned an unexpected answer. Update the library."));
  }
  if (code != CLOUD_OK) return fail(code, error);
  _code = CLOUD_OK;
  _error = "";
  *result = value;
  return true;
}

// Warns once when calls come faster than ASK_PER_MIN / OTHER_PER_MIN.
static const unsigned int ASK_PER_MIN = 6;     // once every 10 s
static const unsigned int OTHER_PER_MIN = 60;  // once a second

void Cloud::noteCall(const char* op) {
  if (strcmp(op, "ping") == 0) return;
  int kind = strcmp(op, "ask") == 0 ? 0 : 1;
  unsigned long now = millis();
  if (_calls[kind] == 0 || now - _windowStart[kind] >= 60000UL) {
    _windowStart[kind] = now;
    _calls[kind] = 0;
  }
  _calls[kind]++;
  unsigned int limit = kind == 0 ? ASK_PER_MIN : OTHER_PER_MIN;
  if (!_warnings || _warned[kind] || _calls[kind] < limit) return;
  _warned[kind] = true;

  unsigned long elapsed = now - _windowStart[kind];
  if (elapsed < 1000) elapsed = 1000;
  float perMinute = _calls[kind] * 60000.0f / elapsed;
  float cost = kind == 0 ? _askCost : _callCost;
  String call = String(_name) + '.' + (kind == 0 ? "ask" : op) + F("()");

  String text = String(F("[BeyondBoard] Warning: ")) + call + F(" was called ") + _calls[kind] +
                F(" times in ") + (elapsed / 1000) + F(" s (about ") +
                (unsigned long)(perMinute + 0.5) + F(" per minute).");
  if (cost > 0) {
    text += String(F(" At this pace it would cost about USD ")) +
            String(perMinute * 60 * 24 * 30 * cost, 2) + F(" per month.");
    if (kind == 0 && _askDailyLimit > 0) {
      text += String(F(" The cloud stops answering after ")) + _askDailyLimit +
              F(" questions a day (about USD ") + String(_askDailyLimit * cost, 2) + F(").");
    }
  } else if (kind == 0) {
    text += F(" The AI on your computer may become slow.");
  }
  text += F(" If you do not need it this often, add a delay() in loop().");
  Serial.println(text);
}

bool Cloud::save(const char* name, const char* value) {
  if (!checkName(name)) return false;
  String body = String(F("{\"name\":")) + cloudJsonString(name) + F(",\"value\":") + cloudJsonString(value) + '}';
  String ignored;
  return request("save", body, 15000, &ignored);
}

bool Cloud::save(const char* name, const String& value) { return save(name, value.c_str()); }
bool Cloud::save(const char* name, int value) { return save(name, String(value)); }
bool Cloud::save(const char* name, long value) { return save(name, String(value)); }
bool Cloud::save(const char* name, unsigned long value) { return save(name, String(value)); }
bool Cloud::save(const char* name, double value) { return save(name, numberText(value)); }

bool Cloud::save(const char* name, const CloudBytes& bytes) {
  if (!checkName(name)) return false;
  if (!bytes.data || bytes.length == 0) return fail(CLOUD_ERR_TOO_LARGE, F("There is nothing to save."));
  if (bytes.length > 1024UL * 1024UL) return fail(CLOUD_ERR_TOO_LARGE, F("The data is too large (limit 1MB)."));
  String body = String(F("{\"name\":")) + cloudJsonString(name) + F(",\"binary\":\"");
  appendBase64(body, bytes.data, bytes.length);
  body += F("\"}");
  String ignored;
  return request("save", body, 30000, &ignored);
}

String Cloud::load(const char* name, unsigned int last) {
  if (!checkName(name)) return "";
  String result;
  String body = String(F("{\"name\":")) + cloudJsonString(name) + F(",\"last\":") + String(last) + '}';
  return request("load", body, 15000, &result) ? result : String();
}

bool Cloud::remove(const char* name) {
  if (!checkName(name)) return false;
  String ignored;
  String body = String(F("{\"name\":")) + cloudJsonString(name) + '}';
  return request("remove", body, 15000, &ignored);
}

String Cloud::list(const char* prefix) {
  if (prefix && *prefix && !checkName(prefix)) return "";
  String result;
  String body = String(F("{\"prefix\":")) + cloudJsonString(prefix ? prefix : "") + '}';
  return request("list", body, 15000, &result) ? result : String();
}

String Cloud::run(const char* name, const String& input, unsigned long timeoutMs) {
  if (timeoutMs > 60000) timeoutMs = 60000;
  String result;
  String body = String(F("{\"name\":")) + cloudJsonString(name ? name : "") + F(",\"input\":") +
                cloudJsonString(input) + F(",\"timeoutMs\":") + String(timeoutMs) + '}';
  return request("run", body, timeoutMs, &result) ? result : String();
}

String Cloud::ask(const char* prompt, const String& data) { return ask(prompt, data, nullptr, 0); }

String Cloud::ask(const char* prompt, const String& data, const char* const choices[], size_t count) {
  String body = String(F("{\"prompt\":")) + cloudJsonString(prompt ? prompt : "") + F(",\"data\":") +
                cloudJsonString(data) + F(",\"choices\":[");
  for (size_t i = 0; i < count; i++) {
    if (i) body += ',';
    body += cloudJsonString(choices[i]);
  }
  body += "]}";
  String result;
  // A local AI on a slow computer can take a while, so wait up to a minute.
  return request("ask", body, 60000, &result) ? result : String();
}

String Cloud::ask(const char* prompt, const CloudBytes& image, const char* const choices[],
                  size_t count) {
  if (!image.data || image.length == 0) {
    fail(CLOUD_ERR_TOO_LARGE, F("There is no image."));
    return String();
  }
  String body = String(F("{\"prompt\":")) + cloudJsonString(prompt ? prompt : "") + F(",\"choices\":[");
  for (size_t i = 0; i < count; i++) {
    if (i) body += ',';
    body += cloudJsonString(choices[i]);
  }
  body += F("],\"image\":\"");
  appendBase64(body, image.data, image.length);
  body += F("\"}");
  String result;
  return request("ask", body, 60000, &result) ? result : String();
}
