// CORE_API v1.0 host-side orchestration: single worker thread, BUSY gate,
// process-lifetime jobId ledger, snapshots and cooperative cancellation.
// This is the C++ port of `bridge/service.py` (that file documents why each
// rule exists). It deliberately contains no N-API and no Python headers:
// the embedding lives behind BridgeHooks so the full state machine stays
// testable on any C++17 host (see tests/core-service-native.test.cpp).
#ifndef GSAS_PC_CORE_SERVICE_H
#define GSAS_PC_CORE_SERVICE_H

#include <atomic>
#include <condition_variable>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <vector>

namespace gsas {
namespace core {

// Synchronous rejection payload; matches CORE_API error objects.
struct ServiceError {
    std::string code;
    std::string message;
    bool retryable = false;
};

// Thrown by BridgeHooks to reject a call before any event is emitted.
class BridgeFailure : public std::exception {
  public:
    explicit BridgeFailure(ServiceError error);
    const ServiceError& error() const { return m_error; }
    const char* what() const noexcept override { return m_what.c_str(); }

  private:
    ServiceError m_error;
    std::string m_what;
};

// The stable Python bridge entries (CORE_API §8). Implementations must be
// callable on the service worker thread only (the CPython host and the
// host tests both honour this).
class BridgeHooks {
  public:
    virtual ~BridgeHooks() = default;
    // Returns the CoreInfo JSON string; throws BridgeFailure on rejection.
    virtual std::string initialize(const std::string& config_json) = 0;
    // Runs one job to its terminal event. emit_event receives exactly one
    // CoreEvent JSON string at a time; is_cancelled is polled at stage
    // boundaries and must return immediately. Returns the terminal event
    // JSON, identical to the last emitted event.
    virtual std::string execute(const std::string& request_json,
                                const std::function<void(const std::string&)>& emit_event,
                                const std::function<bool()>& is_cancelled) = 0;
};

// Mirrors LocalCoreService from bridge/service.py except where a crash-safe
// deviation is marked "deviation:".
class CoreService {
  public:
    explicit CoreService(BridgeHooks& hooks);
    ~CoreService();
    CoreService(const CoreService&) = delete;
    CoreService& operator=(const CoreService&) = delete;

    // Replaces the event fan-out target (N-API wires the threadsafe
    // function here). Sink is called on the worker thread; it must not
    // block and its exceptions are swallowed. An empty sink drops delivery
    // but still records snapshots.
    void SetEventSink(std::function<void(const std::string&)> sink);

    bool Initialize(const std::string& config_json, std::string* core_info_json, ServiceError* error);
    // Synchronous single-task gate. On success the job is "queued" with a
    // snapshot; the caller must then call StartAcquiredJob or ReleaseJob.
    bool AcquireJob(const std::string& job_id, ServiceError* error);
    void ReleaseJob(const std::string& job_id);
    // Validates the cheap synchronous fields, then enqueues execution on
    // the worker. Returns the JobAccepted JSON.
    bool StartAcquiredJob(const std::string& request_json, std::string* accepted_json, ServiceError* error);
    bool CancelJob(const std::string& job_id, std::string* ack_json, ServiceError* error);
    bool GetJobSnapshot(const std::string& job_id, std::string* snapshot_json, ServiceError* error);

    bool Initialized() const;
    // Blocks until the queue drains and no job is active (mirrors
    // LocalCoreService.wait_idle; used by host tests and teardown paths).
    bool WaitIdle(int timeout_ms);
    // Waits for the worker to finish an in-flight execute before joining;
    // callers must treat this as best effort at process teardown.
    void Shutdown();

    // Collects the fileIds referenced by a refinement request (data,
    // instrument and phase inputs) so the facade can lease them first.
    static bool RequestInputIds(const std::string& request_json, std::vector<std::string>* ids);

  private:
    struct Snapshot;
    struct Command;
    using CommandPtr = std::shared_ptr<Command>;
    void worker_loop();
    void run_execute(const std::string& request_json, const std::string& job_id,
                     std::shared_ptr<std::atomic<bool>> cancel_flag);
    bool record_event(const std::string& event_json);
    void dispatch(const std::string& event_json);
    void synthesize_failed(const std::string& job_id, const ServiceError& failure);
    bool sync_validate(const std::string& request_json, ServiceError* error, std::string* job_id_out);

    BridgeHooks& m_hooks;
    std::function<void(const std::string&)> m_sink;
    mutable std::mutex m_mutex;
    std::condition_variable m_available;
    std::condition_variable m_idle;
    std::deque<CommandPtr> m_pending;
    std::thread m_worker;
    bool m_stop = false;
    bool m_executing = false;
    bool m_initialized = false;
    std::vector<std::string> m_recipes;
    std::string m_active_job;
    std::set<std::string> m_seen_job_ids;
    std::map<std::string, std::shared_ptr<std::atomic<bool>>> m_cancel_flags;
    std::map<std::string, Snapshot> m_snapshots;
};

}  // namespace core
}  // namespace gsas

#endif  // GSAS_PC_CORE_SERVICE_H
