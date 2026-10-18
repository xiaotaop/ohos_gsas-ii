// BridgeHooks implementation over the embedded CPython interpreter.
// All methods run on the CoreService worker thread (CORE_API §10); this
// class owns every GIL transition. Without a compile-time Python payload
// (cpp/python/include missing) it compiles as a stub that rejects with
// CORE_NOT_READY so the HAP still builds for file-service-only development.
#ifndef GSAS_PC_PYTHON_HOST_H
#define GSAS_PC_PYTHON_HOST_H

#include <functional>
#include <memory>
#include <mutex>
#include <string>

#include "core/core_service.h"

namespace gsas {
namespace python {

class CPythonHooks : public core::BridgeHooks {
  public:
    CPythonHooks();
    ~CPythonHooks() override;
    CPythonHooks(const CPythonHooks&) = delete;
    CPythonHooks& operator=(const CPythonHooks&) = delete;

    // Absolute sandbox directory that holds lib/python3.12, site-packages
    // and the bridge package (CoreConfig.runtimeRoot).
    void SetRuntimeRoot(const std::string& runtime_root);

    std::string initialize(const std::string& config_json) override;
    std::string execute(const std::string& request_json,
                        const std::function<void(const std::string&)>& emit_event,
                        const std::function<bool()>& is_cancelled) override;

  private:
    class Impl;
    bool EnsureBooted();
    std::unique_ptr<Impl> m_impl;
    std::mutex m_boot_mutex;
    bool m_booted = false;
};

}  // namespace python
}  // namespace gsas

#endif  // GSAS_PC_PYTHON_HOST_H
