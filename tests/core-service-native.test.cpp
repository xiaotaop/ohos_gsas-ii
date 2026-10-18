// Host unit test for the N-API core orchestration (app/entry/src/main/cpp/
// core/core_service.cpp). It exercises the C++ port of bridge/service.py
// with a fake BridgeHooks: no N-API, no CPython, no device required. The
// fake mirrors the Python engine's event discipline so the C++ snapshot and
// gate logic is validated against the same semantics CI already checks.
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "../app/entry/src/main/cpp/core/core_service.h"

using gsas::core::BridgeFailure;
using gsas::core::BridgeHooks;
using gsas::core::CoreService;
using gsas::core::ServiceError;

namespace {

const char* kConfig = "{\"schemaVersion\":\"1.0\",\"runtimeRoot\":\"/tmp/runtime\","
    "\"workspaceRoot\":\"/tmp/jobs\",\"outputRoot\":\"/tmp/outputs\","
    "\"maxConcurrentJobs\":1,\"logLevel\":\"info\"}";

const char* kCoreInfo = "{\"schemaVersion\":\"1.0\",\"ready\":true,\"pythonVersion\":\"3.12.9\","
    "\"gsasCommit\":\"2b4aba1bc44de63a3da9d4495944c3b99e389399\","
    "\"supportedRecipes\":[\"powder-five-stage-v1\"]}";

std::string MakeRequest(const std::string& jobId, const std::string& recipe = "powder-five-stage-v1")
{
    return "{\"schemaVersion\":\"1.0\",\"jobId\":\"" + jobId + "\",\"operation\":\"powder-refinement\","
        "\"recipeId\":\"" + recipe + "\","
        "\"inputs\":{\"histograms\":["
        "{\"id\":\"hist_xray\",\"role\":\"xray\",\"dataFileId\":\"file_pbso4_xra_001\","
        "\"instrumentFileId\":\"file_inst_xry_001\",\"formatHint\":\"GSAS powder\"},"
        "{\"id\":\"hist_neutron\",\"role\":\"neutron\",\"dataFileId\":\"file_pbso4_cwn_001\","
        "\"instrumentFileId\":\"file_inst_d1a_001\",\"formatHint\":\"GSAS powder\"}],"
        "\"phase\":{\"id\":\"phase_pbso4\",\"name\":\"PbSO4\",\"fileId\":\"file_pbso4_cif_001\"}},"
        "\"options\":{\"cycleCount\":0,\"validateAgainstBaseline\":true},"
        "\"output\":{\"projectName\":\"sample.gpx\",\"overwrite\":false}}";
}

std::string Event(const std::string& jobId, int sequence, const char* type, const std::string& payload)
{
    std::string tail = jobId.substr(4);
    char eventId[128];
    std::snprintf(eventId, sizeof(eventId), "evt_%.80s_%04d", tail.c_str(), sequence);
    return std::string("{\"schemaVersion\":\"1.0\",\"eventId\":\"") + eventId + "\",\"jobId\":\"" + jobId
        + "\",\"sequence\":" + std::to_string(sequence) + ",\"timestamp\":\"2026-10-18T08:00:00Z\",\"type\":\""
        + type + "\",\"payload\":" + payload + "}";
}

class FakeHooks : public BridgeHooks {
  public:
    enum Mode { kHappy, kThrowBeforeEvents, kWaitCancel, kDoubleTerminal };

    std::string initialize(const std::string& config_json) override
    {
        ++initialize_calls;
        last_config = config_json;
        if (fail_next_initialize) {
            fail_next_initialize = false;
            throw BridgeFailure({"INVALID_REQUEST", "配置无效", false});
        }
        return kCoreInfo;
    }

    std::string execute(const std::string& request_json,
        const std::function<void(const std::string&)>& emit_event,
        const std::function<bool()>& is_cancelled) override
    {
        std::string jobId = request_json;
        size_t marker = jobId.find("\"jobId\":\"");
        assert(marker != std::string::npos);
        size_t start = marker + 9;
        jobId = jobId.substr(start, jobId.find('\"', start) - start);
        observed_cancel = false;
        const std::string accepted = Event(jobId, 0, "job.accepted", "{\"state\":\"queued\"}");
        if (mode == kThrowBeforeEvents) {
            throw BridgeFailure({"REFINEMENT_FAILED", "无法读取相文件", false});
        }
        emit_event(accepted);
        emit_event(Event(jobId, 1, "job.progress",
            "{\"state\":\"running\",\"stage\":\"cells\",\"stageIndex\":4,\"stageCount\":7,"
            "\"percent\":55.0,\"message\":\"晶胞参数\"}"));
        emit_event(Event(jobId, 2, "job.log", "{\"level\":\"info\",\"source\":\"gsas-ii\",\"message\":\"Rwp=0.051\"}"));
        if (mode == kWaitCancel) {
            for (int attempt = 0; attempt < 200 && !is_cancelled(); ++attempt) {
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            observed_cancel = is_cancelled();
            const std::string cancelled = Event(jobId, 3, "job.cancelled", "{\"state\":\"cancelled\",\"reason\":\"取消\"}");
            emit_event(cancelled);
            return cancelled;
        }
        const std::string terminal = Event(jobId, 3, "job.completed",
            "{\"state\":\"succeeded\",\"result\":{\"recipeId\":\"powder-five-stage-v1\","
            "\"upstreamCommit\":\"2b4aba1b\",\"elapsedSeconds\":1.5,\"stages\":[],"
            "\"artifacts\":[{\"fileId\":\"file_out_x_gpx\",\"kind\":\"project\",\"displayName\":\"sample.gpx\","
            "\"mediaType\":\"application/octet-stream\"}]}}");
        emit_event(terminal);
        if (mode == kDoubleTerminal) {
            emit_event(Event(jobId, 4, "job.failed",
                "{\"state\":\"failed\",\"error\":{\"code\":\"INTERNAL_ERROR\",\"message\":\"late\",\"retryable\":true}}"));
        }
        return terminal;
    }

    int initialize_calls = 0;
    bool fail_next_initialize = false;
    bool observed_cancel = false;
    std::string last_config;
    Mode mode = kHappy;
};

struct Recorder {
    std::vector<std::string> events;
    bool throw_once = false;

    void operator()(const std::string& event_json)
    {
        events.push_back(event_json);
        if (throw_once) {
            throw_once = false;
            throw std::runtime_error("listener failure must not abort the job");
        }
    }
};

bool Contains(const std::string& text, const std::string& needle)
{
    return text.find(needle) != std::string::npos;
}

void ExpectReject(const ServiceError& error, const char* code)
{
    assert(error.code == code);
    assert(!error.message.empty());
}

}  // namespace

int main()
{
    // 1. initialize: failure surfaces the contract code, success reports CoreInfo verbatim.
    FakeHooks hooks;
    CoreService service(hooks);
    ServiceError error;
    std::string result;
    hooks.fail_next_initialize = true;
    assert(!service.Initialize(kConfig, &result, &error));
    ExpectReject(error, "INVALID_REQUEST");
    assert(!service.Initialized());
    assert(service.Initialize(kConfig, &result, &error));
    assert(service.Initialized());
    assert(result == kCoreInfo);
    assert(hooks.initialize_calls == 2);
    assert(hooks.last_config == kConfig);

    // 2. job ids are validated before the gate touches anything.
    assert(!service.AcquireJob("job_short", &error));
    ExpectReject(error, "INVALID_REQUEST");
    assert(!service.GetJobSnapshot("job_unknown_1234", &result, &error));
    ExpectReject(error, "JOB_NOT_FOUND");

    // 3. single-task gate: BUSY and process-lifetime jobId ledger, no events.
    assert(service.AcquireJob("job_gate_first_001", &error));
    assert(!service.AcquireJob("job_gate_second_002", &error));
    ExpectReject(error, "BUSY");
    assert(!service.AcquireJob("job_gate_first_001", &error));
    ExpectReject(error, "JOB_ALREADY_EXISTS");
    assert(service.GetJobSnapshot("job_gate_first_001", &result, &error));
    assert(Contains(result, "\"state\":\"queued\""));
    assert(Contains(result, "\"lastSequence\":-1"));
    assert(Contains(result, "\"stage\":null"));
    assert(Contains(result, "\"terminal\":null"));
    // Releasing drops the snapshot; the id stops being "already seen".
    service.ReleaseJob("job_gate_first_001");
    assert(!service.GetJobSnapshot("job_gate_first_001", &result, &error));
    ExpectReject(error, "JOB_NOT_FOUND");
    assert(service.AcquireJob("job_gate_first_001", &error));
    service.ReleaseJob("job_gate_first_001");

    // 4. synchronous request validation rejects without events.
    Recorder recorder;
    // SetEventSink copies the callable; capture by reference so assertions
    // observe the recorder the worker dispatches into.
    service.SetEventSink([&recorder](const std::string& event_json) { recorder(event_json); });
    assert(!service.StartAcquiredJob("{not json", &result, &error));
    ExpectReject(error, "INVALID_REQUEST");
    assert(service.AcquireJob("job_validate_0001", &error));
    assert(!service.StartAcquiredJob(MakeRequest("job_validate_0001", "other-recipe"), &result, &error));
    ExpectReject(error, "UNSUPPORTED_RECIPE");
    assert(!service.StartAcquiredJob(
        "{\"schemaVersion\":\"2.0\",\"jobId\":\"job_validate_0001\",\"operation\":\"powder-refinement\","
        "\"recipeId\":\"powder-five-stage-v1\",\"inputs\":{},\"options\":{},\"output\":{}}", &result, &error));
    ExpectReject(error, "UNSUPPORTED_SCHEMA");
    // start with a jobId different from the acquired job is rejected.
    assert(!service.StartAcquiredJob(MakeRequest("job_other_job_9999"), &result, &error));
    ExpectReject(error, "INVALID_REQUEST");
    service.ReleaseJob("job_validate_0001");

    // 5. happy path: verbatim event order, snapshot follows events, gate frees on terminal.
    assert(service.AcquireJob("job_happy_path_01", &error));
    std::string accepted;
    assert(service.StartAcquiredJob(MakeRequest("job_happy_path_01"), &accepted, &error));
    assert(Contains(accepted, "\"jobId\":\"job_happy_path_01\""));
    assert(Contains(accepted, "\"state\":\"queued\""));
    assert(Contains(accepted, "\"acceptedAt\":\"20"));
    assert(service.WaitIdle(5000));
    assert(recorder.events.size() == 4);
    assert(recorder.events[0] == Event("job_happy_path_01", 0, "job.accepted", "{\"state\":\"queued\"}"));
    assert(Contains(recorder.events[1], "\"percent\":55.0"));
    assert(service.GetJobSnapshot("job_happy_path_01", &result, &error));
    assert(Contains(result, "\"state\":\"succeeded\""));
    assert(Contains(result, "\"lastSequence\":3"));
    assert(Contains(result, "\"percent\":55"));
    assert(Contains(result, "\"stage\":\"cells\""));
    assert(Contains(result, "\"terminal\":{\"type\":\"job.completed\",\"payload\":{\"state\":\"succeeded\""));
    // Snapshot stays queryable after the job slot frees; a new job may start.
    assert(service.AcquireJob("job_happy_path_02", &error));
    service.ReleaseJob("job_happy_path_02");

    // 6. a second terminal event is dropped, not crashed, and not re-recorded.
    hooks.mode = FakeHooks::kDoubleTerminal;
    recorder.events.clear();
    assert(service.AcquireJob("job_double_term_1", &error));
    assert(service.StartAcquiredJob(MakeRequest("job_double_term_1"), &accepted, &error));
    assert(service.WaitIdle(5000));
    assert(recorder.events.size() == 5);  // late event is delivered (mirror) but not recorded
    assert(service.GetJobSnapshot("job_double_term_1", &result, &error));
    assert(Contains(result, "\"type\":\"job.completed\""));
    assert(!Contains(result, "job.failed"));
    hooks.mode = FakeHooks::kHappy;

    // 7. throwing before any event synthesizes exactly one terminal failed event.
    hooks.mode = FakeHooks::kThrowBeforeEvents;
    recorder.events.clear();
    assert(service.AcquireJob("job_throw_sync_1", &error));
    assert(service.StartAcquiredJob(MakeRequest("job_throw_sync_1"), &accepted, &error));
    assert(service.WaitIdle(5000));
    assert(recorder.events.size() == 1);
    assert(Contains(recorder.events[0], "\"eventId\":\"evt_throw_sync_1_sync\""));
    assert(Contains(recorder.events[0], "\"sequence\":0"));
    assert(Contains(recorder.events[0], "\"code\":\"REFINEMENT_FAILED\""));
    assert(service.GetJobSnapshot("job_throw_sync_1", &result, &error));
    assert(Contains(result, "\"state\":\"failed\""));
    hooks.mode = FakeHooks::kHappy;

    // 8. cooperative cancellation: ack precedes the terminal event; flag observed by bridge.
    hooks.mode = FakeHooks::kWaitCancel;
    recorder.events.clear();
    assert(service.AcquireJob("job_cancel_flow_1", &error));
    assert(service.StartAcquiredJob(MakeRequest("job_cancel_flow_1"), &accepted, &error));
    // Wait until the bridge is inside execute, then cancel.
    while (recorder.events.size() < 2) {
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
    std::string ack;
    assert(service.CancelJob("job_cancel_flow_1", &ack, &error));
    assert(Contains(ack, "\"requested\":true"));
    assert(service.WaitIdle(5000));
    assert(hooks.observed_cancel);
    assert(recorder.events.back() == Event("job_cancel_flow_1", 3, "job.cancelled", "{\"state\":\"cancelled\",\"reason\":\"取消\"}"));
    assert(service.GetJobSnapshot("job_cancel_flow_1", &result, &error));
    assert(Contains(result, "\"state\":\"cancelled\""));
    // Cancelling a finished job is a synchronous rejection.
    assert(!service.CancelJob("job_cancel_flow_1", &ack, &error));
    ExpectReject(error, "JOB_NOT_FOUND");
    hooks.mode = FakeHooks::kHappy;

    // 9. a throwing listener must not abort the running job.
    recorder.events.clear();
    recorder.throw_once = true;
    assert(service.AcquireJob("job_listener_throw", &error));
    assert(service.StartAcquiredJob(MakeRequest("job_listener_throw"), &accepted, &error));
    assert(service.WaitIdle(5000));
    assert(recorder.events.size() == 4);
    assert(service.GetJobSnapshot("job_listener_throw", &result, &error));
    assert(Contains(result, "\"state\":\"succeeded\""));
    recorder.throw_once = false;

    // 10. input ids are collected for the file lease.
    std::vector<std::string> ids;
    assert(CoreService::RequestInputIds(MakeRequest("job_ids_check_01"), &ids));
    assert(ids.size() == 5);
    for (const char* expected : {"file_pbso4_xra_001", "file_inst_xry_001", "file_pbso4_cwn_001",
             "file_inst_d1a_001", "file_pbso4_cif_001"}) {
        assert(std::find(ids.begin(), ids.end(), std::string(expected)) != ids.end());
    }

    // 11. after shutdown the service refuses new work instead of hanging.
    service.Shutdown();
    assert(!service.Initialize(kConfig, &result, &error));
    ExpectReject(error, "CORE_NOT_READY");
    assert(!service.AcquireJob("job_after_stop_1", &error));
    ExpectReject(error, "CORE_NOT_READY");

    std::puts("core-service-native: all assertions passed");
    return 0;
}
