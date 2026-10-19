// Host-only regression: embed real CPython and initialize the production
// bridge from two native threads. The host intentionally has no GSAS-II
// native payload, so BOTH attempts must reject CORE_NOT_READY. The second
// thread would hang if the initialization thread retained the GIL.
// This is not scientific validation, an OHOS build or an execute() test.
// See the CI step for a complete stdlib/bridge-only runtime setup.
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include "python/python_host.h"

int main()
{
    const char* root = std::getenv("GSAS_SMOKE_ROOT");
    assert(root != nullptr);
    const std::string files(root);
    gsas::python::CPythonHooks hooks;
    hooks.SetRuntimeRoot(files + "/rt");
    const std::string config = std::string("{\"schemaVersion\":\"1.0\",")
        + "\"runtimeRoot\":\"" + files + "/rt\","
        + "\"workspaceRoot\":\"" + files + "/jobs\","
        + "\"outputRoot\":\"" + files + "/outputs\","
        + "\"maxConcurrentJobs\":1,\"logLevel\":\"info\"}";
    auto check = [&] {
        try {
            hooks.initialize(config);
            assert(false && "host native preflight must reject incomplete runtime");
        } catch (const gsas::core::BridgeFailure& failure) {
            assert(failure.error().code == "CORE_NOT_READY");
        }
    };
    check();
    std::thread worker(check);
    worker.join();
    std::cout << "python-host-thread-smoke: both threads rejected missing native payload; no GIL deadlock" << std::endl;
    return 0;
}
