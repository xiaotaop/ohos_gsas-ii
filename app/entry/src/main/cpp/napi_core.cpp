// N-API surface for the CORE_API v1.0 orchestration (core/core_service.cpp)
// and the embedded bridge entries (python/python_host.cpp). JSON crosses this
// boundary byte-identical: config, request and event strings are forwarded
// verbatim, mirroring the §8 stable entries. The registration style follows
// file_exporter.cpp (module name == .so name == ArkTS import name).
#include <napi/native_api.h>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "core/core_service.h"
#include "python/python_host.h"

namespace {

using gsas::core::CoreService;
using gsas::core::ServiceError;
using gsas::python::CPythonHooks;

// Process-lifetime singletons, deliberately never destroyed: joining the
// orchestration worker during static teardown would abort the app, and
// CPython is never finalized in-process (RUNTIME_PACKAGING §2). shutdownCore
// stops the worker; a later initializeCore rebuilds it over the same hooks.
CPythonHooks* g_hooks = nullptr;
CoreService* g_service = nullptr;
bool g_service_stopped = false;
std::mutex g_service_mutex;

std::mutex g_emit_mutex;
napi_threadsafe_function g_emit = nullptr;

napi_value Undefined(napi_env env)
{
    napi_value value = nullptr;
    napi_get_undefined(env, &value);
    return value;
}

napi_value ToString(napi_env env, const std::string& text)
{
    napi_value value = nullptr;
    if (napi_create_string_utf8(env, text.c_str(), text.size(), &value) != napi_ok) {
        return nullptr;
    }
    return value;
}

// Rejections carry the frozen contract error shape: Error with code plus
// message and a retryable flag the facade can read without parsing.
napi_value MakeContractError(napi_env env, const ServiceError& error)
{
    napi_value code = nullptr;
    napi_value message = nullptr;
    napi_value thrown = nullptr;
    napi_create_string_utf8(env, error.code.c_str(), error.code.size(), &code);
    napi_create_string_utf8(env, error.message.c_str(), error.message.size(), &message);
    if (napi_create_error(env, code, message, &thrown) != napi_ok) {
        return nullptr;
    }
    napi_value retryable = nullptr;
    napi_get_boolean(env, error.retryable, &retryable);
    napi_set_named_property(env, thrown, "retryable", retryable);
    return thrown;
}

void ThrowContractError(napi_env env, const ServiceError& error)
{
    napi_value thrown = MakeContractError(env, error);
    if (thrown != nullptr) {
        napi_throw(env, thrown);
    }
}

// Reads exactly one string argument; oversized or non-string shapes are
// rejected before CoreService ever sees them (cap covers full §6 requests).
bool ReadSingleString(napi_env env, napi_callback_info info, std::string* out)
{
    size_t argc = 1;
    napi_value args[1];
    if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) != napi_ok || argc != 1) {
        return false;
    }
    size_t length = 0;
    if (napi_get_value_string_utf8(env, args[0], nullptr, 0, &length) != napi_ok || length == 0
        || length > 262144) {
        return false;
    }
    std::vector<char> buffer(length + 1);
    size_t copied = 0;
    if (napi_get_value_string_utf8(env, args[0], buffer.data(), buffer.size(), &copied) != napi_ok
        || copied != length) {
        return false;
    }
    out->assign(buffer.data(), length);
    return true;
}

// Runs on the CoreService worker thread. Enqueues for the ArkTS main thread
// without ever blocking the job: a full or closing queue drops delivery only
// (the snapshot still records the event, matching the empty-sink rule).
void PublishEvent(const std::string& event_json)
{
    std::lock_guard<std::mutex> guard(g_emit_mutex);
    if (g_emit == nullptr) {
        return;
    }
    auto* payload = new std::string(event_json);
    if (napi_call_threadsafe_function(g_emit, payload, napi_tsfn_nonblocking) != napi_ok) {
        delete payload;
    }
}

// Runs on the ArkTS main thread, once per queued event, with the raw event
// JSON as the single argument.
void DeliverEvent(napi_env env, napi_value js_callback, void* /* context */, void* data)
{
    std::unique_ptr<std::string> payload(static_cast<std::string*>(data));
    if (js_callback == nullptr) {
        return;
    }
    napi_value argument = nullptr;
    if (napi_create_string_utf8(env, payload->c_str(), payload->size(), &argument) != napi_ok) {
        return;
    }
    napi_value receiver = nullptr;
    napi_value thrown = nullptr;
    napi_get_undefined(env, &receiver);
    if (napi_call_function(env, receiver, js_callback, 1, &argument, &thrown) != napi_ok) {
        // Listener failures never abort delivery or the running job
        // (bridge/service.py swallows them the same way).
        napi_value cleared = nullptr;
        napi_get_and_clear_last_exception(env, &cleared);
    }
}

napi_value SetEventCallback(napi_env env, napi_callback_info info)
{
    size_t argc = 1;
    napi_value args[1] = {nullptr};
    if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) != napi_ok || argc > 1) {
        ThrowContractError(env, {"INVALID_REQUEST", "事件回调参数无效", false});
        return nullptr;
    }
    bool detach = true;
    if (argc == 1) {
        napi_valuetype type = napi_undefined;
        if (napi_typeof(env, args[0], &type) != napi_ok) {
            ThrowContractError(env, {"INVALID_REQUEST", "事件回调参数无效", false});
            return nullptr;
        }
        if (type == napi_function) {
            detach = false;
        } else if (type != napi_null && type != napi_undefined) {
            ThrowContractError(env, {"INVALID_REQUEST", "事件回调必须是函数或空值", false});
            return nullptr;
        }
    }
    napi_threadsafe_function created = nullptr;
    if (!detach) {
        napi_value name = nullptr;
        napi_create_string_utf8(env, "gsas-core-events", NAPI_AUTO_LENGTH, &name);
        if (napi_create_threadsafe_function(env, args[0], nullptr, name, 0, 1, nullptr, nullptr,
                nullptr, DeliverEvent, &created)
            != napi_ok) {
            ThrowContractError(env, {"INTERNAL_ERROR", "无法装配事件通道", true});
            return nullptr;
        }
    }
    napi_threadsafe_function previous = nullptr;
    {
        std::lock_guard<std::mutex> guard(g_emit_mutex);
        previous = g_emit;
        g_emit = created;  // nullptr when detaching
    }
    if (previous != nullptr) {
        // Already-queued events on the old channel still get delivered.
        napi_release_threadsafe_function(previous, napi_tsfn_release);
    }
    return Undefined(env);
}

// getCoreConfig() emits a flat object (Files.ets CoreConfig), so a literal
// scan is enough here; escaped paths are rejected rather than guessed at and
// the Python side still validates the authoritative config.
bool ExtractRuntimeRoot(const std::string& config_json, std::string* out)
{
    const std::string key = "\"runtimeRoot\":\"";
    size_t marker = config_json.find(key);
    if (marker == std::string::npos) {
        return false;
    }
    size_t start = marker + key.size();
    size_t end = config_json.find('"', start);
    if (end == std::string::npos) {
        return false;
    }
    std::string value = config_json.substr(start, end - start);
    if (value.empty() || value.find('\\') != std::string::npos) {
        return false;
    }
    out->swap(value);
    return true;
}

struct InitializeWork {
    napi_async_work work = nullptr;
    napi_deferred deferred = nullptr;
    std::string config_json;
    std::string core_info_json;
    ServiceError error {"INTERNAL_ERROR", "核心初始化未完成", true};
    bool ok = false;
};

// Boots CPython and imports the bridge on the libuv pool thread, then on the
// gsas-core-worker; the ArkTS main thread only ever sees the Promise.
void RunInitialize(napi_env /* env */, void* data)
{
    auto* job = static_cast<InitializeWork*>(data);
    std::string runtime_root;
    if (!ExtractRuntimeRoot(job->config_json, &runtime_root)) {
        job->error = {"INVALID_REQUEST", "配置缺少可解析的 runtimeRoot", false};
        return;
    }
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_hooks == nullptr) {
        job->error = {"INTERNAL_ERROR", "原生模块尚未注册", true};
        return;
    }
    g_hooks->SetRuntimeRoot(runtime_root);
    if (g_service == nullptr || g_service_stopped) {
        g_service = new CoreService(*g_hooks);
        g_service->SetEventSink(PublishEvent);
        g_service_stopped = false;
    }
    job->ok = g_service->Initialize(job->config_json, &job->core_info_json, &job->error);
}

void CompleteInitialize(napi_env env, napi_status status, void* data)
{
    std::unique_ptr<InitializeWork> job(static_cast<InitializeWork*>(data));
    if (job->work != nullptr) {
        napi_delete_async_work(env, job->work);
    }
    if (job->deferred == nullptr) {
        return;
    }
    if (status == napi_cancelled) {
        napi_value rejection = MakeContractError(env, {"PROCESS_INTERRUPTED", "核心初始化被取消", true});
        if (rejection != nullptr) {
            napi_reject_deferred(env, job->deferred, rejection);
        }
        return;
    }
    napi_value result = nullptr;
    if (job->ok) {
        result = ToString(env, job->core_info_json);
        if (result != nullptr) {
            napi_resolve_deferred(env, job->deferred, result);
            return;
        }
    }
    result = MakeContractError(env, job->error);
    if (result != nullptr) {
        napi_reject_deferred(env, job->deferred, result);
    }
}

napi_value InitializeCore(napi_env env, napi_callback_info info)
{
    auto* job = new InitializeWork();
    if (!ReadSingleString(env, info, &job->config_json)) {
        delete job;
        ThrowContractError(env, {"INVALID_REQUEST", "配置必须是 JSON 字符串", false});
        return nullptr;
    }
    napi_value promise = nullptr;
    if (napi_create_promise(env, &job->deferred, &promise) != napi_ok) {
        delete job;
        ThrowContractError(env, {"INTERNAL_ERROR", "无法创建异步句柄", true});
        return nullptr;
    }
    napi_value name = nullptr;
    napi_create_string_utf8(env, "gsas-core-initialize", NAPI_AUTO_LENGTH, &name);
    if (napi_create_async_work(env, nullptr, name, RunInitialize, CompleteInitialize, job, &job->work)
        != napi_ok) {
        job->work = nullptr;
        napi_value rejection = MakeContractError(env, {"INTERNAL_ERROR", "无法排队初始化任务", true});
        if (rejection != nullptr) {
            napi_reject_deferred(env, job->deferred, rejection);
        }
        delete job;
        return promise;
    }
    if (napi_queue_async_work(env, job->work) != napi_ok) {
        napi_delete_async_work(env, job->work);
        job->work = nullptr;
        napi_value rejection = MakeContractError(env, {"INTERNAL_ERROR", "无法启动初始化任务", true});
        if (rejection != nullptr) {
            napi_reject_deferred(env, job->deferred, rejection);
        }
        delete job;
        return promise;
    }
    return promise;
}

struct ShutdownWork {
    napi_async_work work = nullptr;
    napi_deferred deferred = nullptr;
};

void RunShutdown(napi_env /* env */, void* /* data */)
{
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_service != nullptr && !g_service_stopped) {
        // Waits for an in-flight execute (CoreService::Shutdown contract),
        // which is exactly why this runs off the main thread.
        g_service->Shutdown();
        g_service_stopped = true;
    }
}

void CompleteShutdown(napi_env env, napi_status status, void* data)
{
    std::unique_ptr<ShutdownWork> job(static_cast<ShutdownWork*>(data));
    if (job->work != nullptr) {
        napi_delete_async_work(env, job->work);
    }
    if (job->deferred == nullptr) {
        return;
    }
    if (status == napi_cancelled) {
        napi_value rejection = MakeContractError(env, {"PROCESS_INTERRUPTED", "核心关闭被取消", true});
        if (rejection != nullptr) {
            napi_reject_deferred(env, job->deferred, rejection);
        }
        return;
    }
    napi_value value = Undefined(env);
    napi_resolve_deferred(env, job->deferred, value);
}

napi_value ShutdownCore(napi_env env, napi_callback_info info)
{
    size_t argc = 0;
    if (napi_get_cb_info(env, info, &argc, nullptr, nullptr, nullptr) != napi_ok || argc != 0) {
        ThrowContractError(env, {"INVALID_REQUEST", "shutdownCore 不接受参数", false});
        return nullptr;
    }
    auto* job = new ShutdownWork();
    napi_value promise = nullptr;
    if (napi_create_promise(env, &job->deferred, &promise) != napi_ok) {
        delete job;
        ThrowContractError(env, {"INTERNAL_ERROR", "无法创建异步句柄", true});
        return nullptr;
    }
    napi_value name = nullptr;
    napi_create_string_utf8(env, "gsas-core-shutdown", NAPI_AUTO_LENGTH, &name);
    if (napi_create_async_work(env, nullptr, name, RunShutdown, CompleteShutdown, job, &job->work)
        != napi_ok) {
        job->work = nullptr;
        napi_value rejection = MakeContractError(env, {"INTERNAL_ERROR", "无法排队关闭任务", true});
        if (rejection != nullptr) {
            napi_reject_deferred(env, job->deferred, rejection);
        }
        delete job;
        return promise;
    }
    if (napi_queue_async_work(env, job->work) != napi_ok) {
        napi_delete_async_work(env, job->work);
        job->work = nullptr;
        napi_value rejection = MakeContractError(env, {"INTERNAL_ERROR", "无法启动关闭任务", true});
        if (rejection != nullptr) {
            napi_reject_deferred(env, job->deferred, rejection);
        }
        delete job;
        return promise;
    }
    return promise;
}

napi_value AcquireJob(napi_env env, napi_callback_info info)
{
    std::string job_id;
    if (!ReadSingleString(env, info, &job_id)) {
        ThrowContractError(env, {"INVALID_REQUEST", "jobId 必须是 JSON 字符串", false});
        return nullptr;
    }
    ServiceError error;
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_service == nullptr || g_service_stopped) {
        ThrowContractError(env, {"CORE_NOT_READY", "核心尚未初始化", true});
        return nullptr;
    }
    if (!g_service->AcquireJob(job_id, &error)) {
        ThrowContractError(env, error);
        return nullptr;
    }
    return Undefined(env);
}

napi_value ReleaseJob(napi_env env, napi_callback_info info)
{
    std::string job_id;
    if (!ReadSingleString(env, info, &job_id)) {
        ThrowContractError(env, {"INVALID_REQUEST", "jobId 必须是 JSON 字符串", false});
        return nullptr;
    }
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_service != nullptr && !g_service_stopped) {
        g_service->ReleaseJob(job_id);  // Idempotent; an unknown id is a no-op.
    }
    return Undefined(env);
}

napi_value StartAcquiredJob(napi_env env, napi_callback_info info)
{
    std::string request_json;
    if (!ReadSingleString(env, info, &request_json)) {
        ThrowContractError(env, {"INVALID_REQUEST", "请求必须是 JSON 字符串", false});
        return nullptr;
    }
    ServiceError error;
    std::string accepted_json;
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_service == nullptr || g_service_stopped) {
        ThrowContractError(env, {"CORE_NOT_READY", "核心尚未初始化", true});
        return nullptr;
    }
    if (!g_service->StartAcquiredJob(request_json, &accepted_json, &error)) {
        ThrowContractError(env, error);
        return nullptr;
    }
    return ToString(env, accepted_json);
}

napi_value CancelJob(napi_env env, napi_callback_info info)
{
    std::string job_id;
    if (!ReadSingleString(env, info, &job_id)) {
        ThrowContractError(env, {"INVALID_REQUEST", "jobId 必须是 JSON 字符串", false});
        return nullptr;
    }
    ServiceError error;
    std::string ack_json;
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_service == nullptr || g_service_stopped) {
        ThrowContractError(env, {"CORE_NOT_READY", "核心尚未初始化", true});
        return nullptr;
    }
    if (!g_service->CancelJob(job_id, &ack_json, &error)) {
        ThrowContractError(env, error);
        return nullptr;
    }
    return ToString(env, ack_json);
}

napi_value GetJobSnapshot(napi_env env, napi_callback_info info)
{
    std::string job_id;
    if (!ReadSingleString(env, info, &job_id)) {
        ThrowContractError(env, {"INVALID_REQUEST", "jobId 必须是 JSON 字符串", false});
        return nullptr;
    }
    ServiceError error;
    std::string snapshot_json;
    std::lock_guard<std::mutex> guard(g_service_mutex);
    if (g_service == nullptr || g_service_stopped) {
        ThrowContractError(env, {"CORE_NOT_READY", "核心尚未初始化", true});
        return nullptr;
    }
    if (!g_service->GetJobSnapshot(job_id, &snapshot_json, &error)) {
        ThrowContractError(env, error);
        return nullptr;
    }
    return ToString(env, snapshot_json);
}

napi_value Init(napi_env env, napi_value exports)
{
    g_hooks = new CPythonHooks();
    napi_property_descriptor properties[] = {
        {"setEventCallback", nullptr, SetEventCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"initializeCore", nullptr, InitializeCore, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"acquireJob", nullptr, AcquireJob, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"releaseJob", nullptr, ReleaseJob, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"startAcquiredJob", nullptr, StartAcquiredJob, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"cancelJob", nullptr, CancelJob, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getJobSnapshot", nullptr, GetJobSnapshot, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"shutdownCore", nullptr, ShutdownCore, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    if (napi_define_properties(env, exports, sizeof(properties) / sizeof(properties[0]), properties)
        != napi_ok) {
        return nullptr;
    }
    return exports;
}

}  // namespace

static napi_module module = { 1, 0, nullptr, Init, "gsas_core", nullptr, {0} };

extern "C" __attribute__((constructor)) void RegisterGsasCore()
{
    napi_module_register(&module);
}
