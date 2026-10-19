// Host-only GSAS_HAS_PYTHON smoke (NOT part of CI, NOT OHOS aarch64 proof).
// Embeds the real system CPython through the shipping python_host.cpp, loads
// the real bridge package via the CORE_API §8 entry points, and runs one job
// to its terminal event. Without a GSAS-II payload the run must end in a
// CORE_NOT_READY job.failed emitted across the C boundary — that round trip
// is exactly what stub builds and pure-Python tests cannot cover (it caught
// the METH_O emit-capsule defect fixed alongside this file).
//
// Reproduce (Ubuntu 22.04, python3-dev installed):
//   S=/tmp/gsas-python-host/run; mkdir -p $S/rt/lib $S/jobs $S/outputs
//   ln -s /usr/lib/python3.10 $S/rt/lib/python3.10          # embedded stdlib home
//   ln -s <repo>/bridge $S/rt/bridge
//   for pairs: mkdir $S/imports/<fileId>; copy the matching tests/fixtures file
//     file_pbso4_xra_001/PBSO4.XRA  file_inst_xry_001/INST_XRY.PRM
//     file_pbso4_cwn_001/PBSO4.CWN  file_inst_d1a_001/inst_d1a.prm
//     file_pbso4_cif_001/PbSO4-Wyckoff.cif
//   g++ once on a single line, joining these parts:
//     -std=c++17 -Wall -Wextra -Werror -DGSAS_HAS_PYTHON -pthread
//     -I app/entry/src/main/cpp -I /usr/include/python3.10
//     tests/python-host-embed-smoke.cpp app/entry/src/main/cpp/python/python_host.cpp
//     app/entry/src/main/cpp/core/core_service.cpp -lpython3.10 -o /tmp/gsas-py-smoke
//   GSAS_SMOKE_ROOT=$S /tmp/gsas-py-smoke
#include <cassert>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "python/python_host.h"

namespace {

std::string readFile(const std::string& path)
{
    std::ifstream in(path);
    return std::string((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
}

bool contains(const std::string& text, const std::string& needle)
{
    return text.find(needle) != std::string::npos;
}

}  // namespace

int main()
{
    const char* root = std::getenv("GSAS_SMOKE_ROOT");
    assert(root != nullptr);
    const std::string files(root);
    const std::string rt = files + "/rt";

    gsas::python::CPythonHooks hooks;
    hooks.SetRuntimeRoot(rt);

    const std::string config = std::string("{\"schemaVersion\":\"1.0\",")
        + "\"runtimeRoot\":\"" + rt + "\","
        + "\"workspaceRoot\":\"" + files + "/jobs\","
        + "\"outputRoot\":\"" + files + "/outputs\","
        + "\"maxConcurrentJobs\":1,\"logLevel\":\"info\"}";

    const std::string info = hooks.initialize(config);
    std::cout << "initialize -> " << info << std::endl;
    assert(contains(info, "\"ready\": true"));
    assert(contains(info, "pythonVersion"));   // the embedded interpreter answers for itself
    assert(contains(info, "powder-five-stage-v1"));
    assert(info == hooks.initialize(config));   // §3 idempotent re-init

    const std::string request = std::string("{\"schemaVersion\":\"1.0\",")
        + "\"jobId\":\"job_host_python_001\",\"operation\":\"powder-refinement\","
        + "\"recipeId\":\"powder-five-stage-v1\","
        + "\"inputs\":{\"histograms\":["
        + "{\"id\":\"xray\",\"role\":\"xray\",\"dataFileId\":\"file_pbso4_xra_001\","
        + "\"instrumentFileId\":\"file_inst_xry_001\",\"formatHint\":\"GSAS powder\"},"
        + "{\"id\":\"neutron\",\"role\":\"neutron\",\"dataFileId\":\"file_pbso4_cwn_001\","
        + "\"instrumentFileId\":\"file_inst_d1a_001\",\"formatHint\":\"GSAS powder\"}],"
        + "\"phase\":{\"id\":\"pbso4\",\"name\":\"PbSO4\",\"fileId\":\"file_pbso4_cif_001\"}},"
        + "\"options\":{\"cycleCount\":3,\"validateAgainstBaseline\":true},"
        + "\"output\":{\"projectName\":\"PbSO4-refined.gpx\",\"overwrite\":false}}";

    std::vector<std::string> events;
    const std::string terminal = hooks.execute(request,
        [&](const std::string& event) { events.push_back(event); },
        [] { return false; });
    for (const std::string& event : events) {
        std::cout << "event -> " << event << std::endl;
    }
    assert(!events.empty());
    assert(terminal == events.back());
    assert(contains(events.front(), "\"job.accepted\""));
    // The five real fixtures hash-gate and resolve inside the embedded
    // interpreter, so the job reaches validating; only GSAS-II itself is
    // absent from this host, which the bridge maps to CORE_NOT_READY.
    assert(contains(terminal, "\"job.failed\""));
    assert(contains(terminal, "CORE_NOT_READY"));
    assert(contains(terminal, "GSAS-II"));
    assert(contains(terminal, "\"sequence\":"));
    const std::string traceback = readFile(files + "/jobs/job_host_python_001/logs/traceback.log");
    assert(contains(traceback, "GSAS-II"));   // private log written, never emitted

    std::cout << "python-host-embed-smoke: all assertions passed (host only, not OHOS evidence)"
              << std::endl;
    return 0;
}
