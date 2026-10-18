// C++ port of bridge/service.py (LocalCoreService). The Python file remains
// the specification: every behaviour here mirrors its docstring and code,
// except deviations that are marked and exist so a host failure cannot take
// down an application process (CORE_API §11.8).
#include "core_service.h"

#include <cctype>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <future>
#include <sstream>
#include <utility>

namespace gsas {
namespace core {

namespace {

// ---------------------------------------------------------------------------
// Minimal tolerant JSON scanning. Event payloads must cross the boundary as
// verbatim strings (re-serializing could drift number formatting), so this
// layer only ever *extracts* values; anything recomposed for snapshots embeds
// the raw substrings it found.
// ---------------------------------------------------------------------------

void SkipWs(const std::string& text, size_t* pos)
{
    while (*pos < text.size()) {
        char ch = text[*pos];
        if (ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r') {
            return;
        }
        ++(*pos);
    }
}

// Scans one JSON string starting at the opening quote; advances pos past it.
bool ScanString(const std::string& text, size_t* pos, std::string* decoded)
{
    if (*pos >= text.size() || text[*pos] != '\"') {
        return false;
    }
    ++(*pos);
    decoded->clear();
    while (*pos < text.size()) {
        char ch = text[*pos];
        if (ch == '\"') {
            ++(*pos);
            return true;
        }
        if (ch == '\\') {
            ++(*pos);
            if (*pos >= text.size()) {
                return false;
            }
            char esc = text[*pos];
            if (esc == '\"' || esc == '\\' || esc == '/') {
                decoded->push_back(esc);
            } else if (esc == 'b') {
                decoded->push_back('\b');
            } else if (esc == 'f') {
                decoded->push_back('\f');
            } else if (esc == 'n') {
                decoded->push_back('\n');
            } else if (esc == 'r') {
                decoded->push_back('\r');
            } else if (esc == 't') {
                decoded->push_back('\t');
            } else if (esc == 'u') {
                if (*pos + 4 >= text.size()) {
                    return false;
                }
                unsigned long code = strtoul(text.substr(*pos + 1, 4).c_str(), nullptr, 16);
                *pos += 4;
                if (code >= 0xD800 && code <= 0xDBFF && *pos + 6 < text.size()
                    && text[*pos + 1] == '\\' && text[*pos + 2] == 'u') {
                    unsigned long low = strtoul(text.substr(*pos + 3, 4).c_str(), nullptr, 16);
                    if (low >= 0xDC00 && low <= 0xDFFF) {
                        code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00);
                        *pos += 6;
                    }
                }
                if (code <= 0x7F) {
                    decoded->push_back(static_cast<char>(code));
                } else if (code <= 0x7FF) {
                    decoded->push_back(static_cast<char>(0xC0 | (code >> 6)));
                    decoded->push_back(static_cast<char>(0x80 | (code & 0x3F)));
                } else if (code <= 0xFFFF) {
                    decoded->push_back(static_cast<char>(0xE0 | (code >> 12)));
                    decoded->push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
                    decoded->push_back(static_cast<char>(0x80 | (code & 0x3F)));
                } else {
                    decoded->push_back(static_cast<char>(0xF0 | (code >> 18)));
                    decoded->push_back(static_cast<char>(0x80 | ((code >> 12) & 0x3F)));
                    decoded->push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
                    decoded->push_back(static_cast<char>(0x80 | (code & 0x3F)));
                }
            } else {
                return false;
            }
            ++(*pos);
            continue;
        }
        if (static_cast<unsigned char>(ch) < 0x20) {
            return false;
        }
        decoded->push_back(ch);
        ++(*pos);
    }
    return false;
}

// Skips one value respecting nested containers; returns the raw substring.
bool ScanValue(const std::string& text, size_t* pos, std::string* raw)
{
    SkipWs(text, pos);
    if (*pos >= text.size()) {
        return false;
    }
    char head = text[*pos];
    if (head == '{' || head == '[') {
        char close = head == '{' ? '}' : ']';
        size_t start = *pos;
        int depth = 0;
        bool inString = false;
        while (*pos < text.size()) {
            char ch = text[*pos];
            if (inString) {
                if (ch == '\\') {
                    ++(*pos);
                } else if (ch == '\"') {
                    inString = false;
                }
            } else if (ch == '\"') {
                inString = true;
            } else if (ch == head) {
                ++depth;
            } else if (ch == close) {
                --depth;
                if (depth == 0) {
                    ++(*pos);
                    *raw = text.substr(start, *pos - start);
                    return true;
                }
            }
            ++(*pos);
        }
        return false;
    }
    if (head == '\"') {
        size_t start = *pos;
        std::string decoded;
        if (!ScanString(text, pos, &decoded)) {
            return false;
        }
        *raw = text.substr(start, *pos - start);
        return true;
    }
    size_t start = *pos;
    while (*pos < text.size()) {
        char ch = text[*pos];
        if (ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r') {
            break;
        }
        ++(*pos);
    }
    *raw = text.substr(start, *pos - start);
    return !raw->empty();
}

struct Member {
    std::string key;
    std::string raw;
    std::string decoded;  // unescaped value for string members
    bool isString = false;
};

// Parses the top-level members of a JSON object. Nested values stay raw.
bool ParseObjectTop(const std::string& text, std::vector<Member>* members)
{
    members->clear();
    size_t pos = 0;
    SkipWs(text, &pos);
    if (pos >= text.size() || text[pos] != '{') {
        return false;
    }
    ++pos;
    SkipWs(text, &pos);
    if (pos < text.size() && text[pos] == '}') {
        return true;
    }
    while (pos < text.size()) {
        SkipWs(text, &pos);
        std::string key;
        if (!ScanString(text, &pos, &key)) {
            return false;
        }
        SkipWs(text, &pos);
        if (pos >= text.size() || text[pos] != ':') {
            return false;
        }
        ++pos;
        std::string raw;
        if (!ScanValue(text, &pos, &raw)) {
            return false;
        }
        Member member;
        member.key = key;
        member.raw = raw;
        member.isString = !raw.empty() && raw[0] == '\"';
        if (member.isString) {
            size_t valuePos = 0;
            ScanString(raw, &valuePos, &member.decoded);
        }
        members->push_back(member);
        SkipWs(text, &pos);
        if (pos < text.size() && text[pos] == ',') {
            ++pos;
            continue;
        }
        if (pos < text.size() && text[pos] == '}') {
            return true;
        }
        return false;
    }
    return false;
}

const Member* FindMember(const std::vector<Member>& members, const char* key)
{
    for (const Member& member : members) {
        if (member.key == key) {
            return &member;
        }
    }
    return nullptr;
}

std::string JsonEscape(const std::string& text)
{
    std::string out;
    out.reserve(text.size() + 8);
    out.push_back('\"');
    for (unsigned char ch : text) {
        if (ch == '\"') {
            out += "\\\"";
        } else if (ch == '\\') {
            out += "\\\\";
        } else if (ch == '\n') {
            out += "\\n";
        } else if (ch == '\r') {
            out += "\\r";
        } else if (ch == '\t') {
            out += "\\t";
        } else if (ch < 0x20) {
            char buffer[8];
            std::snprintf(buffer, sizeof(buffer), "\\u%04x", ch);
            out += buffer;
        } else {
            out.push_back(static_cast<char>(ch));
        }
    }
    out.push_back('\"');
    return out;
}

std::string FormatPercent(double value)
{
    std::ostringstream stream;
    stream << value;
    std::string text = stream.str();
    if (text.find('.') == std::string::npos && text.find('e') == std::string::npos
        && text.find("inf") == std::string::npos && text.find("nan") == std::string::npos) {
        text += ".0";
    }
    return text;
}

std::string UtcTimestamp()
{
    std::time_t now = std::time(nullptr);
    std::tm parts {};
#if defined(_WIN32)
    gmtime_s(&parts, &now);
#else
    gmtime_r(&now, &parts);
#endif
    char buffer[32];
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &parts);
    return std::string(buffer);
}

bool ValidJobId(const std::string& jobId)
{
    const std::string prefix = "job_";
    if (jobId.size() <= prefix.size() || jobId.compare(0, prefix.size(), prefix) != 0) {
        return false;
    }
    size_t tail = jobId.size() - prefix.size();
    if (tail < 8 || tail > 64) {
        return false;
    }
    for (size_t index = prefix.size(); index < jobId.size(); ++index) {
        char ch = jobId[index];
        if (std::isalnum(static_cast<unsigned char>(ch)) == 0 && ch != '_' && ch != '-') {
            return false;
        }
    }
    return true;
}

bool IsFileId(const std::string& value)
{
    return value.size() > 5 && value.compare(0, 5, "file_") == 0;
}

// Collects file_… string values stored under any of the given keys anywhere
// in the document. Ids are plain identifiers, so a bounded textual scan is
// sufficient and the file service re-validates every id it receives.
std::vector<std::string> CollectKeyValues(const std::string& text, const std::vector<std::string>& keys)
{
    std::vector<std::string> values;
    for (const std::string& key : keys) {
        std::string needle = "\"" + key + "\"";
        size_t from = 0;
        while ((from = text.find(needle, from)) != std::string::npos) {
            size_t pos = from + needle.size();
            SkipWs(text, &pos);
            if (pos < text.size() && text[pos] == ':') {
                ++pos;
                SkipWs(text, &pos);
                std::string decoded;
                if (ScanString(text, &pos, &decoded) && IsFileId(decoded)) {
                    values.push_back(decoded);
                }
            }
            from += needle.size();
        }
    }
    return values;
}

// Enumerates the plain string items of a JSON array substring.
std::vector<std::string> ArrayStrings(const std::string& raw)
{
    std::vector<std::string> values;
    if (raw.size() < 2 || raw[0] != '[') {
        return values;
    }
    size_t pos = 1;
    while (pos < raw.size()) {
        SkipWs(raw, &pos);
        if (pos >= raw.size()) {
            break;
        }
        if (raw[pos] == '\"') {
            std::string decoded;
            if (!ScanString(raw, &pos, &decoded)) {
                break;
            }
            values.push_back(decoded);
        } else if (raw[pos] == ',' || raw[pos] == ' ' || raw[pos] == '\n' || raw[pos] == '\t' || raw[pos] == '\r') {
            ++pos;
        } else if (raw[pos] == ']') {
            break;
        } else {
            break;
        }
    }
    return values;
}

}  // namespace

BridgeFailure::BridgeFailure(ServiceError error)
    : m_error(std::move(error)), m_what(m_error.code + ": " + m_error.message)
{
}

struct CoreService::Snapshot {
    std::string jobId;
    std::string state = "queued";
    long long lastSequence = -1;
    double percent = 0.0;
    bool hasStage = false;
    std::string stage;
    bool hasTerminal = false;
    std::string terminalType;
    std::string terminalPayloadRaw;

    std::string ToJson() const
    {
        std::string out = "{\"jobId\":" + JsonEscape(jobId) + ",\"state\":" + JsonEscape(state)
            + ",\"lastSequence\":" + std::to_string(lastSequence) + ",\"percent\":" + FormatPercent(percent);
        if (hasStage) {
            out += ",\"stage\":" + JsonEscape(stage);
        } else {
            out += ",\"stage\":null";
        }
        if (hasTerminal) {
            out += ",\"terminal\":{\"type\":" + JsonEscape(terminalType) + ",\"payload\":" + terminalPayloadRaw + "}";
        } else {
            out += ",\"terminal\":null";
        }
        out += "}";
        return out;
    }
};

struct CoreService::Command {
    enum Kind { kInitialize, kExecute } kind = kExecute;
    std::string payload;
    std::string jobId;
    std::shared_ptr<std::atomic<bool>> cancelFlag;
    struct Reply {
        bool ok = false;
        std::string json;
        ServiceError error;
    };
    std::shared_ptr<std::promise<Reply>> reply;
};

CoreService::CoreService(BridgeHooks& hooks) : m_hooks(hooks)
{
}

CoreService::~CoreService()
{
    Shutdown();
}

void CoreService::SetEventSink(std::function<void(const std::string&)> sink)
{
    std::lock_guard<std::mutex> guard(m_mutex);
    m_sink = std::move(sink);
}

bool CoreService::Initialized() const
{
    std::lock_guard<std::mutex> guard(m_mutex);
    return m_initialized;
}

bool CoreService::WaitIdle(int timeout_ms)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return m_idle.wait_for(lock, std::chrono::milliseconds(timeout_ms), [this] {
        return !m_executing && m_pending.empty() && m_active_job.empty();
    });
}

void CoreService::Shutdown()
{
    std::thread worker;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        m_stop = true;
        worker = std::move(m_worker);
    }
    m_available.notify_all();
    if (worker.joinable()) {
        // A running execute is not interrupted (stage-boundary cooperative
        // cancellation only); joining therefore waits for the in-flight job.
        worker.join();
    }
}

bool CoreService::Initialize(const std::string& config_json, std::string* core_info_json, ServiceError* error)
{
    CommandPtr command = std::make_shared<Command>();
    command->kind = Command::kInitialize;
    command->payload = config_json;
    command->reply = std::make_shared<std::promise<Command::Reply>>();
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        if (m_stop) {
            if (error != nullptr) {
                *error = ServiceError {"CORE_NOT_READY", "核心已停止", true};
            }
            return false;
        }
        if (!m_worker.joinable()) {
            m_worker = std::thread([this] { worker_loop(); });
        }
        m_pending.push_back(command);
    }
    m_available.notify_one();
    Command::Reply result = command->reply->get_future().get();
    if (!result.ok) {
        if (error != nullptr) {
            *error = result.error;
        }
        return false;
    }
    if (core_info_json != nullptr) {
        *core_info_json = result.json;
    }
    return true;
}

bool CoreService::AcquireJob(const std::string& job_id, ServiceError* error)
{
    std::lock_guard<std::mutex> guard(m_mutex);
    if (m_stop) {
        if (error != nullptr) {
            *error = ServiceError {"CORE_NOT_READY", "核心已停止", true};
        }
        return false;
    }
    if (!ValidJobId(job_id)) {
        if (error != nullptr) {
            *error = ServiceError {"INVALID_REQUEST", "任务编号无效", false};
        }
        return false;
    }
    if (!m_initialized) {
        if (error != nullptr) {
            *error = ServiceError {"CORE_NOT_READY", "核心尚未初始化", true};
        }
        return false;
    }
    if (m_seen_job_ids.count(job_id) != 0) {
        if (error != nullptr) {
            *error = ServiceError {"JOB_ALREADY_EXISTS", "jobId " + job_id + " 已存在", false};
        }
        return false;
    }
    if (!m_active_job.empty()) {
        if (error != nullptr) {
            *error = ServiceError {"BUSY", "任务 " + m_active_job + " 正在运行", true};
        }
        return false;
    }
    m_seen_job_ids.insert(job_id);
    m_active_job = job_id;
    m_cancel_flags[job_id] = std::make_shared<std::atomic<bool>>(false);
    Snapshot snapshot;
    snapshot.jobId = job_id;
    m_snapshots[job_id] = snapshot;
    return true;
}

void CoreService::ReleaseJob(const std::string& job_id)
{
    std::lock_guard<std::mutex> guard(m_mutex);
    if (m_active_job == job_id) {
        m_active_job.clear();
    }
    m_seen_job_ids.erase(job_id);
    m_cancel_flags.erase(job_id);
    m_snapshots.erase(job_id);
}

bool CoreService::StartAcquiredJob(const std::string& request_json, std::string* accepted_json, ServiceError* error)
{
    ServiceError local;
    std::string job_id;
    if (!sync_validate(request_json, &local, &job_id)) {
        if (error != nullptr) {
            *error = local;
        }
        return false;
    }
    std::string accepted;
    CommandPtr command = std::make_shared<Command>();
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        if (m_active_job != job_id || m_cancel_flags.count(job_id) == 0 || m_stop) {
            if (error != nullptr) {
                *error = ServiceError {"INVALID_REQUEST", "任务未处于已接受状态", false};
            }
            return false;
        }
        command->kind = Command::kExecute;
        command->payload = request_json;
        command->jobId = job_id;
        command->cancelFlag = m_cancel_flags[job_id];
        if (!m_worker.joinable()) {
            m_worker = std::thread([this] { worker_loop(); });
        }
        m_pending.push_back(command);
        accepted = "{\"schemaVersion\":\"1.0\",\"jobId\":" + JsonEscape(job_id)
            + ",\"state\":\"queued\",\"acceptedAt\":" + JsonEscape(UtcTimestamp()) + "}";
    }
    m_available.notify_one();
    if (accepted_json != nullptr) {
        *accepted_json = accepted;
    }
    return true;
}

bool CoreService::CancelJob(const std::string& job_id, std::string* ack_json, ServiceError* error)
{
    std::lock_guard<std::mutex> guard(m_mutex);
    auto flag = m_cancel_flags.find(job_id);
    if (flag == m_cancel_flags.end() || m_active_job != job_id) {
        if (error != nullptr) {
            *error = ServiceError {"JOB_NOT_FOUND", "无法取消未知或已结束的任务 " + job_id, false};
        }
        return false;
    }
    flag->second->store(true);
    if (ack_json != nullptr) {
        *ack_json = "{\"schemaVersion\":\"1.0\",\"jobId\":" + JsonEscape(job_id) + ",\"requested\":true}";
    }
    return true;
}

bool CoreService::GetJobSnapshot(const std::string& job_id, std::string* snapshot_json, ServiceError* error)
{
    std::lock_guard<std::mutex> guard(m_mutex);
    auto found = m_snapshots.find(job_id);
    if (found == m_snapshots.end()) {
        if (error != nullptr) {
            *error = ServiceError {"JOB_NOT_FOUND", "未知任务 " + job_id, false};
        }
        return false;
    }
    if (snapshot_json != nullptr) {
        *snapshot_json = found->second.ToJson();
    }
    return true;
}

bool CoreService::RequestInputIds(const std::string& request_json, std::vector<std::string>* ids)
{
    std::vector<std::string> found = CollectKeyValues(request_json, {"dataFileId", "instrumentFileId", "fileId"});
    ids->assign(found.begin(), found.end());
    // The request carries two histograms (data+instrument each) and one
    // phase; anything smaller cannot be the frozen five-stage shape.
    return ids->size() >= 5;
}

bool CoreService::sync_validate(const std::string& request_json, ServiceError* error, std::string* job_id_out)
{
    std::vector<Member> members;
    if (!ParseObjectTop(request_json, &members)) {
        *error = ServiceError {"INVALID_REQUEST", "请求不是 JSON 对象", false};
        return false;
    }
    const Member* version = FindMember(members, "schemaVersion");
    if (version == nullptr || !version->isString) {
        *error = ServiceError {"INVALID_REQUEST", "缺少 schemaVersion", false};
        return false;
    }
    if (version->decoded != "1.0") {
        *error = ServiceError {"UNSUPPORTED_SCHEMA", "schemaVersion " + version->decoded + " 不受支持", false};
        return false;
    }
    const Member* jobId = FindMember(members, "jobId");
    if (jobId == nullptr || !jobId->isString || !ValidJobId(jobId->decoded)) {
        *error = ServiceError {"INVALID_REQUEST", "jobId 无效", false};
        return false;
    }
    const Member* operation = FindMember(members, "operation");
    if (operation == nullptr || !operation->isString || operation->decoded != "powder-refinement") {
        *error = ServiceError {"INVALID_REQUEST", "operation 无效", false};
        return false;
    }
    for (const char* key : {"inputs", "options", "output"}) {
        const Member* member = FindMember(members, key);
        if (member == nullptr || member->raw.empty() || member->raw[0] != '{') {
            *error = ServiceError {"INVALID_REQUEST", std::string("缺少 ") + key, false};
            return false;
        }
    }
    const Member* recipe = FindMember(members, "recipeId");
    if (recipe == nullptr || !recipe->isString) {
        *error = ServiceError {"INVALID_REQUEST", "缺少 recipeId", false};
        return false;
    }
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        if (!m_recipes.empty()) {
            bool supported = false;
            for (const std::string& known : m_recipes) {
                if (known == recipe->decoded) {
                    supported = true;
                    break;
                }
            }
            if (!supported) {
                *error = ServiceError {"UNSUPPORTED_RECIPE", "未实现 recipe " + recipe->decoded, false};
                return false;
            }
        }
    }
    *job_id_out = jobId->decoded;
    return true;
}

void CoreService::dispatch(const std::string& event_json)
{
    std::function<void(const std::string&)> sink;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        sink = m_sink;
    }
    if (!sink) {
        return;
    }
    try {
        // A raising UI listener must never abort the running job.
        sink(event_json);
    } catch (...) {
    }
}

bool CoreService::record_event(const std::string& event_json)
{
    std::vector<Member> members;
    if (!ParseObjectTop(event_json, &members)) {
        return false;
    }
    const Member* jobId = FindMember(members, "jobId");
    const Member* type = FindMember(members, "type");
    const Member* sequence = FindMember(members, "sequence");
    const Member* payload = FindMember(members, "payload");
    if (jobId == nullptr || type == nullptr || sequence == nullptr || payload == nullptr) {
        return false;
    }
    std::string job_id = jobId->decoded;
    std::string event_type = type->decoded;
    bool terminal = event_type == "job.completed" || event_type == "job.failed" || event_type == "job.cancelled";
    std::vector<Member> payloadMembers;
    ParseObjectTop(payload->raw, &payloadMembers);
    std::lock_guard<std::mutex> guard(m_mutex);
    auto found = m_snapshots.find(job_id);
    if (found == m_snapshots.end()) {
        return false;
    }
    Snapshot& snapshot = found->second;
    if (terminal) {
        // deviation: service.py raises on a second terminal event; dropping
        // it keeps a misbehaving bridge from killing the worker thread.
        if (snapshot.hasTerminal) {
            return false;
        }
        snapshot.hasTerminal = true;
        snapshot.terminalType = event_type;
        snapshot.terminalPayloadRaw = payload->raw;
        snapshot.state = event_type == "job.completed" ? "succeeded"
            : event_type == "job.failed" ? "failed" : "cancelled";
    } else {
        const Member* state = FindMember(payloadMembers, "state");
        if (state != nullptr && state->isString) {
            snapshot.state = state->decoded;
        }
    }
    snapshot.lastSequence = std::strtoll(sequence->raw.c_str(), nullptr, 10);
    if (event_type == "job.progress") {
        const Member* percent = FindMember(payloadMembers, "percent");
        const Member* stage = FindMember(payloadMembers, "stage");
        if (percent != nullptr) {
            snapshot.percent = std::strtod(percent->raw.c_str(), nullptr);
        }
        if (stage != nullptr && stage->isString) {
            snapshot.hasStage = true;
            snapshot.stage = stage->decoded;
        }
    }
    return true;
}

void CoreService::synthesize_failed(const std::string& job_id, const ServiceError& failure)
{
    bool missing_terminal = false;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        auto found = m_snapshots.find(job_id);
        missing_terminal = found != m_snapshots.end() && !found->second.hasTerminal;
    }
    if (!missing_terminal) {
        // deviation: service.py synthesizes unconditionally; here the job
        // already has its single terminal event, so nothing is emitted.
        return;
    }
    std::string tail = job_id.compare(0, 4, "job_") == 0 ? job_id.substr(4) : job_id;
    std::string event = "{\"schemaVersion\":\"1.0\",\"eventId\":\"evt_" + tail + "_sync\",\"jobId\":"
        + JsonEscape(job_id) + ",\"sequence\":0,\"timestamp\":" + JsonEscape(UtcTimestamp())
        + ",\"type\":\"job.failed\",\"payload\":{\"state\":\"failed\",\"error\":{\"code\":"
        + JsonEscape(failure.code) + ",\"message\":" + JsonEscape(failure.message)
        + ",\"retryable\":" + (failure.retryable ? "true" : "false") + "}}}";
    record_event(event);
    dispatch(event);
}

void CoreService::run_execute(const std::string& request_json, const std::string& job_id,
    std::shared_ptr<std::atomic<bool>> cancel_flag)
{
    auto emit = [this](const std::string& event_json) {
        record_event(event_json);
        dispatch(event_json);
    };
    auto is_cancelled = [cancel_flag]() { return cancel_flag->load(); };
    try {
        std::string terminal = m_hooks.execute(request_json, emit, is_cancelled);
        (void)terminal;
    } catch (const BridgeFailure& failure) {
        synthesize_failed(job_id, failure.error());
    } catch (const std::exception&) {
        synthesize_failed(job_id, ServiceError {"INTERNAL_ERROR", "核心发生未知错误", true});
    }
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        if (m_active_job == job_id) {
            m_active_job.clear();
        }
        m_cancel_flags.erase(job_id);
        m_executing = false;
    }
    m_idle.notify_all();
}

void CoreService::worker_loop()
{
    for (;;) {
        CommandPtr command;
        {
            std::unique_lock<std::mutex> lock(m_mutex);
            m_available.wait(lock, [this] { return m_stop || !m_pending.empty(); });
            if (m_pending.empty()) {
                if (m_stop) {
                    return;
                }
                continue;
            }
            command = m_pending.front();
            m_pending.pop_front();
            if (command->kind == Command::kExecute) {
                m_executing = true;
            }
        }
        if (command->kind == Command::kInitialize) {
            Command::Reply reply;
            try {
                std::string info = m_hooks.initialize(command->payload);
                std::vector<Member> members;
                std::vector<std::string> recipes;
                if (ParseObjectTop(info, &members)) {
                    const Member* supported = FindMember(members, "supportedRecipes");
                    if (supported != nullptr) {
                        recipes = ArrayStrings(supported->raw);
                    }
                }
                {
                    std::lock_guard<std::mutex> guard(m_mutex);
                    m_recipes = recipes;
                    m_initialized = true;
                }
                reply.ok = true;
                reply.json = info;
            } catch (const BridgeFailure& failure) {
                reply.ok = false;
                reply.error = failure.error();
            } catch (const std::exception&) {
                reply.ok = false;
                reply.error = ServiceError {"INTERNAL_ERROR", "核心初始化失败", true};
            }
            command->reply->set_value(reply);
            continue;
        }
        run_execute(command->payload, command->jobId, command->cancelFlag);
    }
}

}  // namespace core
}  // namespace gsas
