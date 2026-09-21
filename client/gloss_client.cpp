// 수어 글로스 추천기 C++ 클라이언트
//
// 의사 질문 한 문장을 보내면 문진단계·질문유형·숫자질문 여부·표제어 후보를 받는다.
// 외부 라이브러리 없이 소켓만 쓰므로 g++ / MSVC 로 바로 빌드된다.
//
//   Linux : g++ -std=c++17 -O2 -o gloss_client gloss_client.cpp
//   Windows(MinGW) : g++ -std=c++17 -O2 -o gloss_client.exe gloss_client.cpp -lws2_32
//   Windows(MSVC)  : cl /std:c++17 /EHsc gloss_client.cpp ws2_32.lib
//
//   ./gloss_client "언제부터 아팠어요?"
//   ./gloss_client            (인자 없이 실행하면 한 줄씩 입력받는 대화 모드)
//
// 접속 정보는 실행 파일과 같은 위치의 config.txt 에서 읽는다.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#if defined(_WIN32)
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  pragma comment(lib, "ws2_32.lib")
   typedef SOCKET sock_t;
#  define CLOSESOCK closesocket
#else
#  include <arpa/inet.h>
#  include <netdb.h>
#  include <netinet/in.h>
#  include <sys/socket.h>
#  include <sys/time.h>
#  include <unistd.h>
   typedef int sock_t;
#  define INVALID_SOCKET (-1)
#  define CLOSESOCK close
#endif

// ─────────────────────────────────────────────────────────────
// 설정
// ─────────────────────────────────────────────────────────────
struct Config {
    std::string host = "10.254.66.168";
    std::string port = "8777";
    std::string path = "/api/keywords";
    int timeout_sec = 60;
};

static std::string trim(const std::string& s) {
    size_t b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    size_t e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

static Config load_config(const std::string& file) {
    Config c;
    std::ifstream in(file);
    if (!in) {
        std::cerr << "[경고] " << file << " 를 열 수 없어 기본값으로 진행합니다.\n";
        return c;
    }
    std::string line;
    while (std::getline(in, line)) {
        std::string t = trim(line);
        if (t.empty() || t[0] == '#') continue;
        size_t eq = t.find('=');
        if (eq == std::string::npos) continue;
        std::string key = trim(t.substr(0, eq));
        std::string val = trim(t.substr(eq + 1));
        if (key == "host") c.host = val;
        else if (key == "port") c.port = val;
        else if (key == "path") c.path = val;
        else if (key == "timeout_sec") c.timeout_sec = std::atoi(val.c_str());
    }
    return c;
}

// ─────────────────────────────────────────────────────────────
// JSON: 이 응답 스키마에 필요한 최소 기능만 구현한다.
// 최상위 키만 찾으므로 latencyMs 같은 중첩 객체의 키와 섞이지 않는다.
// ─────────────────────────────────────────────────────────────
static size_t skip_ws(const std::string& s, size_t i) {
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) ++i;
    return i;
}

// 문자열 리터럴의 끝(닫는 따옴표) 다음 위치를 돌려준다. i 는 여는 따옴표 위치.
static size_t skip_string(const std::string& s, size_t i) {
    ++i;
    while (i < s.size()) {
        if (s[i] == '\\') { i += 2; continue; }
        if (s[i] == '"') return i + 1;
        ++i;
    }
    return i;
}

// 최상위(depth 1) 키의 값 시작 위치를 찾는다. 없으면 npos.
static size_t find_top_key(const std::string& s, const std::string& key) {
    int depth = 0;
    bool expect_key = false;
    for (size_t i = 0; i < s.size();) {
        char ch = s[i];
        if (ch == '"') {
            size_t end = skip_string(s, i);
            if (depth == 1 && expect_key) {
                std::string name = s.substr(i + 1, end - i - 2);
                size_t j = skip_ws(s, end);
                if (j < s.size() && s[j] == ':' && name == key) return skip_ws(s, j + 1);
            }
            i = end;
            continue;
        }
        if (ch == '{' || ch == '[') { ++depth; expect_key = (ch == '{'); ++i; continue; }
        if (ch == '}' || ch == ']') { --depth; ++i; continue; }
        if (ch == ',') { expect_key = (depth == 1); ++i; continue; }
        ++i;
    }
    return std::string::npos;
}

static std::string unescape(const std::string& s) {
    std::string out;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] != '\\') { out += s[i]; continue; }
        if (++i >= s.size()) break;
        switch (s[i]) {
            case 'n': out += '\n'; break;
            case 't': out += '\t'; break;
            case 'r': out += '\r'; break;
            case 'b': out += '\b'; break;
            case 'f': out += '\f'; break;
            case 'u': {  // \uXXXX -> UTF-8
                if (i + 4 >= s.size()) return out;
                unsigned cp = std::strtoul(s.substr(i + 1, 4).c_str(), nullptr, 16);
                i += 4;
                if (cp < 0x80) out += char(cp);
                else if (cp < 0x800) {
                    out += char(0xC0 | (cp >> 6));
                    out += char(0x80 | (cp & 0x3F));
                } else {
                    out += char(0xE0 | (cp >> 12));
                    out += char(0x80 | ((cp >> 6) & 0x3F));
                    out += char(0x80 | (cp & 0x3F));
                }
                break;
            }
            default: out += s[i];
        }
    }
    return out;
}

static std::string json_string(const std::string& s, const std::string& key) {
    size_t p = find_top_key(s, key);
    if (p == std::string::npos || p >= s.size() || s[p] != '"') return "";
    size_t end = skip_string(s, p);
    return unescape(s.substr(p + 1, end - p - 2));
}

static bool json_bool(const std::string& s, const std::string& key, bool dflt = false) {
    size_t p = find_top_key(s, key);
    if (p == std::string::npos) return dflt;
    return s.compare(p, 4, "true") == 0;
}

static long json_int(const std::string& s, const std::string& key, long dflt = -1) {
    size_t p = find_top_key(s, key);
    if (p == std::string::npos) return dflt;
    return std::strtol(s.c_str() + p, nullptr, 10);
}

static std::vector<std::string> json_string_array(const std::string& s, const std::string& key) {
    std::vector<std::string> out;
    size_t p = find_top_key(s, key);
    if (p == std::string::npos || p >= s.size() || s[p] != '[') return out;
    size_t i = p + 1;
    while (i < s.size()) {
        i = skip_ws(s, i);
        if (i >= s.size() || s[i] == ']') break;
        if (s[i] == '"') {
            size_t end = skip_string(s, i);
            out.push_back(unescape(s.substr(i + 1, end - i - 2)));
            i = end;
        } else ++i;
        i = skip_ws(s, i);
        if (i < s.size() && s[i] == ',') ++i;
    }
    return out;
}

static std::string json_escape(const std::string& s) {
    std::string out;
    for (unsigned char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (c < 0x20) { char buf[8]; std::snprintf(buf, sizeof buf, "\\u%04x", c); out += buf; }
                else out += char(c);
        }
    }
    return out;
}

// ─────────────────────────────────────────────────────────────
// HTTP POST
// ─────────────────────────────────────────────────────────────
static bool http_post(const Config& cfg, const std::string& body, std::string& response, std::string& err) {
    addrinfo hints{}, *res = nullptr;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(cfg.host.c_str(), cfg.port.c_str(), &hints, &res) != 0 || !res) {
        err = "주소를 찾을 수 없습니다: " + cfg.host + ":" + cfg.port;
        return false;
    }
    sock_t fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (fd == INVALID_SOCKET) { freeaddrinfo(res); err = "소켓 생성 실패"; return false; }

#if defined(_WIN32)
    DWORD tv = DWORD(cfg.timeout_sec) * 1000;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, (const char*)&tv, sizeof tv);
#else
    timeval tv{cfg.timeout_sec, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
#endif

    if (connect(fd, res->ai_addr, (int)res->ai_addrlen) != 0) {
        freeaddrinfo(res); CLOSESOCK(fd);
        err = "접속 실패: " + cfg.host + ":" + cfg.port + " (서버가 켜져 있는지, 방화벽·랜 연결을 확인하세요)";
        return false;
    }
    freeaddrinfo(res);

    std::ostringstream req;
    req << "POST " << cfg.path << " HTTP/1.1\r\n"
        << "Host: " << cfg.host << ":" << cfg.port << "\r\n"
        << "Content-Type: application/json; charset=utf-8\r\n"
        << "Content-Length: " << body.size() << "\r\n"
        << "Connection: close\r\n\r\n"
        << body;
    std::string r = req.str();
    for (size_t sent = 0; sent < r.size();) {
        int n = send(fd, r.data() + sent, (int)(r.size() - sent), 0);
        if (n <= 0) { CLOSESOCK(fd); err = "요청 전송 실패"; return false; }
        sent += size_t(n);
    }

    std::string raw;
    char buf[8192];
    for (;;) {
        int n = recv(fd, buf, sizeof buf, 0);
        if (n > 0) raw.append(buf, size_t(n));
        else break;             // 0=정상 종료, <0=타임아웃/오류
    }
    CLOSESOCK(fd);
    if (raw.empty()) { err = "응답이 비었습니다 (타임아웃 가능)"; return false; }

    size_t sep = raw.find("\r\n\r\n");
    if (sep == std::string::npos) { err = "HTTP 응답 형식 오류"; return false; }
    std::string head = raw.substr(0, sep);
    std::string payload = raw.substr(sep + 4);

    // Connection: close 라 chunked 로 올 수 있다. 오면 길이 표기를 걷어낸다.
    if (head.find("Transfer-Encoding: chunked") != std::string::npos ||
        head.find("transfer-encoding: chunked") != std::string::npos) {
        std::string dec;
        size_t i = 0;
        while (i < payload.size()) {
            size_t eol = payload.find("\r\n", i);
            if (eol == std::string::npos) break;
            size_t len = std::strtoul(payload.substr(i, eol - i).c_str(), nullptr, 16);
            if (len == 0) break;
            i = eol + 2;
            dec.append(payload, i, len);
            i += len + 2;
        }
        payload = dec;
    }
    response = payload;
    return true;
}

// ─────────────────────────────────────────────────────────────
static void ask(const Config& cfg, const std::string& question) {
    std::string body = "{\"question\":\"" + json_escape(question) + "\"}";
    std::string resp, err;
    if (!http_post(cfg, body, resp, err)) {
        std::cout << "[오류] " << err << "\n";
        return;
    }
    std::string apiErr = json_string(resp, "error");
    if (!apiErr.empty()) { std::cout << "[서버 오류] " << apiErr << "\n"; return; }

    std::cout << "질문        : " << json_string(resp, "question") << "\n"
              << "문진단계    : " << json_string(resp, "stage")
              << " / " << json_string(resp, "subCategory") << "\n"
              << "질문유형    : " << json_string(resp, "qTypeLabel")
              << " (" << json_string(resp, "qType") << ")\n"
              << "숫자질문    : " << (json_bool(resp, "isNumericQuestion") ? "예" : "아니오") << "\n"
              << "범위외      : " << (json_bool(resp, "outOfScope") ? "예" : "아니오") << "\n";

    std::vector<std::string> kws = json_string_array(resp, "keywords");
    std::cout << "표제어      : " << json_int(resp, "count", (long)kws.size()) << "개\n";
    for (size_t i = 0; i < kws.size(); ++i) {
        std::cout << "  " << (i + 1) << ". " << kws[i] << "\n";
    }
    std::cout << std::endl;
}

int main(int argc, char** argv) {
#if defined(_WIN32)
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) { std::cerr << "WSAStartup 실패\n"; return 1; }
    SetConsoleOutputCP(CP_UTF8);   // 한글 출력
#endif
    Config cfg = load_config("config.txt");
    std::cout << "접속 대상: http://" << cfg.host << ":" << cfg.port << cfg.path << "\n\n";

    if (argc > 1) {
        std::string q = argv[1];
        for (int i = 2; i < argc; ++i) q += std::string(" ") + argv[i];
        ask(cfg, q);
    } else {
        std::cout << "의사 질문을 입력하세요. (빈 줄이면 종료)\n";
        std::string line;
        while (std::cout << "> " && std::getline(std::cin, line)) {
            line = trim(line);
            if (line.empty()) break;
            ask(cfg, line);
        }
    }
#if defined(_WIN32)
    WSACleanup();
#endif
    return 0;
}
