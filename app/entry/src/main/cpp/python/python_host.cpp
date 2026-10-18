// Embedded CPython host for the CORE_API §8 bridge entries. Without a
// compile-time Python payload (cpp/python/include absent) this file builds
// the stub variant so a file-service-only HAP still compiles; every call
// then rejects with CORE_NOT_READY.
#include "python_host.h"

#include <utility>

#if defined(GSAS_HAS_PYTHON)

#include <Python.h>

namespace {

const char* kEmitCapsule = "gsas_emit";
const char* kCancelCapsule = "gsas_cancel";

// Reads the sanitized code/message attributes of a raised BridgeError.
// Anything else stays INTERNAL_ERROR: this layer widens no masking the
// Python side already performed (bridge/errors.py).
gsas::core::ServiceError ErrorFromException()
{
    gsas::core::ServiceError error {"INTERNAL_ERROR", "核心发生未知错误", true};
    if (!PyErr_Occurred()) {
        return error;
    }
    PyObject* type = nullptr;
    PyObject* value = nullptr;
    PyObject* traceback = nullptr;
    PyErr_Fetch(&type, &value, &traceback);
    PyErr_NormalizeException(&type, &value, &traceback);
    if (value != nullptr) {
        PyObject* code = PyObject_GetAttrString(value, "code");
        PyObject* message = PyObject_GetAttrString(value, "message");
        if (code != nullptr && PyUnicode_Check(code)) {
            const char* text = PyUnicode_AsUTF8(code);
            if (text != nullptr) {
                error.code = text;
            }
        }
        if (message != nullptr && PyUnicode_Check(message)) {
            const char* text = PyUnicode_AsUTF8(message);
            if (text != nullptr) {
                error.message = text;
            }
        }
        Py_XDECREF(code);
        Py_XDECREF(message);
        PyErr_Clear();  // failed attribute lookups must not escape.
        error.retryable = error.code == "CORE_NOT_READY" || error.code == "BUSY"
            || error.code == "OUTPUT_WRITE_FAILED" || error.code == "PROCESS_INTERRUPTED"
            || error.code == "INTERNAL_ERROR";
    }
    Py_XDECREF(type);
    Py_XDECREF(value);
    Py_XDECREF(traceback);
    return error;
}

struct EmitBox {
    std::function<void(const std::string&)> fn;
};

struct CancelBox {
    std::function<bool()> fn;
};

PyObject* EmitCallback(PyObject* self, PyObject* args)
{
    PyObject* raw = nullptr;
    if (!PyArg_ParseTuple(args, "O", &raw)) {
        return nullptr;
    }
    const char* text = PyUnicode_AsUTF8(raw);
    if (text == nullptr) {
        return nullptr;
    }
    auto* box = static_cast<EmitBox*>(PyCapsule_GetPointer(self, kEmitCapsule));
    if (box != nullptr && box->fn) {
        try {
            box->fn(std::string(text));
        } catch (...) {
            // The CoreService sink already swallows listener failures; a C++
            // exception must never travel back into Python.
        }
    }
    Py_RETURN_NONE;
}

PyObject* CancelCallback(PyObject* self, PyObject*)
{
    auto* box = static_cast<CancelBox*>(PyCapsule_GetPointer(self, kCancelCapsule));
    bool cancelled = false;
    if (box != nullptr && box->fn) {
        try {
            cancelled = box->fn();
        } catch (...) {
            cancelled = false;
        }
    }
    return PyBool_FromLong(cancelled ? 1 : 0);
}

PyMethodDef g_emit_def = {"emit_event", EmitCallback, METH_O, nullptr};
PyMethodDef g_cancel_def = {"is_cancelled", CancelCallback, METH_NOARGS, nullptr};

}  // namespace

#endif  // helpers

namespace gsas {
namespace python {

using gsas::core::BridgeFailure;
using gsas::core::ServiceError;

#if defined(GSAS_HAS_PYTHON)

class CPythonHooks::Impl {
  public:
    ~Impl()
    {
        Py_XDECREF(initialize_fn);
        Py_XDECREF(execute_fn);
        Py_XDECREF(module);
    }

    std::string runtime_root;
    PyObject* module = nullptr;
    PyObject* initialize_fn = nullptr;
    PyObject* execute_fn = nullptr;

    bool Boot(std::string* failure_message)
    {
        if (Py_IsInitialized()) {
            *failure_message = "嵌入式解释器重复初始化";
            return false;
        }
        PyConfig config;
        PyConfig_InitPythonConfig(&config);
        config.use_environment = 0;       // The app sandbox is the only truth.
        config.user_site_directory = 0;
        config.write_bytecode = 0;
        config.stdio_encoding = nullptr;  // Keep the default UTF-8 behaviour.
        std::wstring wide_root;
        wide_root.assign(runtime_root.begin(), runtime_root.end());
        if (PyStatus_Exception(PyConfig_SetString(&config, &config.home, wide_root.c_str()))) {
            PyConfig_Clear(&config);
            *failure_message = "无法设置 runtimeRoot";
            return false;
        }
        PyStatus status = Py_InitializeFromConfig(&config);
        PyConfig_Clear(&config);
        if (PyStatus_Exception(status)) {
            *failure_message = "无法初始化嵌入式解释器";
            return false;
        }
        // RUNTIME_PACKAGING §2 layout: bridge package at the runtime root,
        // stdlib under lib/python3.12, wheels unpacked into site-packages.
        PyObject* sys_path = PySys_GetObject("path");
        if (sys_path == nullptr || !PyList_Check(sys_path)) {
            *failure_message = "sys.path 不可用";
            return false;
        }
        const std::string candidates[] = {
            runtime_root,
            runtime_root + "/lib/python3.12/site-packages",
            runtime_root + "/lib/python3.12",
        };
        for (const std::string& entry : candidates) {
            PyObject* item = PyUnicode_DecodeUTF8(entry.c_str(), entry.size(), "strict");
            if (item == nullptr) {
                PyErr_Clear();
                continue;
            }
            if (PyList_Append(sys_path, item) != 0) {
                PyErr_Clear();
            }
            Py_DECREF(item);
        }
        module = PyImport_ImportModule("bridge");
        if (module == nullptr) {
            *failure_message = "无法导入桥接模块: " + ErrorFromException().code;
            return false;
        }
        initialize_fn = PyObject_GetAttrString(module, "initialize");
        execute_fn = PyObject_GetAttrString(module, "execute");
        if (initialize_fn == nullptr || execute_fn == nullptr) {
            PyErr_Clear();
            *failure_message = "桥接模块缺少 CORE_API §8 入口";
            return false;
        }
        return true;
    }
};

bool CPythonHooks::EnsureBooted()
{
    std::lock_guard<std::mutex> guard(m_boot_mutex);
    if (m_booted) {
        return true;
    }
    std::string message;
    if (!m_impl->Boot(&message)) {
        throw BridgeFailure({"CORE_NOT_READY", message, true});
    }
    m_booted = true;
    return true;
}

void CPythonHooks::SetRuntimeRoot(const std::string& runtime_root)
{
    std::lock_guard<std::mutex> guard(m_boot_mutex);
    m_impl->runtime_root = runtime_root;
}

std::string CPythonHooks::initialize(const std::string& config_json)
{
    EnsureBooted();
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject* argument = PyUnicode_DecodeUTF8(config_json.c_str(), config_json.size(), "strict");
    if (argument == nullptr) {
        ServiceError error = ErrorFromException();
        PyGILState_Release(gil);
        throw BridgeFailure(error);
    }
    PyObject* result = PyObject_CallFunctionObjArgs(m_impl->initialize_fn, argument, nullptr);
    Py_DECREF(argument);
    if (result == nullptr) {
        ServiceError error = ErrorFromException();
        PyGILState_Release(gil);
        throw BridgeFailure(error);
    }
    std::string out;
    const char* text = PyUnicode_AsUTF8(result);
    if (text == nullptr) {
        ServiceError error = ErrorFromException();
        Py_DECREF(result);
        PyGILState_Release(gil);
        throw BridgeFailure(error);
    }
    out.assign(text);
    Py_DECREF(result);
    PyGILState_Release(gil);
    return out;
}

std::string CPythonHooks::execute(const std::string& request_json,
    const std::function<void(const std::string&)>& emit_event,
    const std::function<bool()>& is_cancelled)
{
    if (!m_booted) {
        throw BridgeFailure({"CORE_NOT_READY", "核心尚未初始化", true});
    }
    EmitBox emit_box {emit_event};
    CancelBox cancel_box {is_cancelled};
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject* emit_capsule = PyCapsule_New(&emit_box, kEmitCapsule, nullptr);
    PyObject* cancel_capsule = PyCapsule_New(&cancel_box, kCancelCapsule, nullptr);
    PyObject* emit_fn = emit_capsule != nullptr ? PyCFunction_New(&g_emit_def, emit_capsule) : nullptr;
    PyObject* cancel_fn = cancel_capsule != nullptr ? PyCFunction_New(&g_cancel_def, cancel_capsule) : nullptr;
    PyObject* argument = PyUnicode_DecodeUTF8(request_json.c_str(), request_json.size(), "strict");
    std::string out;
    ServiceError error {"INTERNAL_ERROR", "核心调用失败", true};
    bool ok = false;
    if (emit_fn != nullptr && cancel_fn != nullptr && argument != nullptr) {
        PyObject* result = PyObject_CallFunctionObjArgs(
            m_impl->execute_fn, argument, emit_fn, cancel_fn, nullptr);
        if (result != nullptr) {
            const char* text = PyUnicode_AsUTF8(result);
            if (text != nullptr) {
                out.assign(text);
                ok = true;
            } else {
                error = ErrorFromException();
            }
            Py_DECREF(result);
        } else {
            error = ErrorFromException();
        }
    } else if (argument == nullptr) {
        error = ErrorFromException();
    }
    Py_XDECREF(argument);
    Py_XDECREF(emit_fn);
    Py_XDECREF(cancel_fn);
    Py_XDECREF(emit_capsule);
    Py_XDECREF(cancel_capsule);
    PyGILState_Release(gil);
    if (!ok) {
        throw BridgeFailure(error);
    }
    return out;
}

#else  // !GSAS_HAS_PYTHON

class CPythonHooks::Impl {};

void CPythonHooks::SetRuntimeRoot(const std::string&) {}

bool CPythonHooks::EnsureBooted()
{
    // Never true in the stub build: there is no interpreter to boot.
    return m_booted;
}

std::string CPythonHooks::initialize(const std::string&)
{
    throw BridgeFailure({"CORE_NOT_READY", "嵌入式运行时未装配", true});
}

std::string CPythonHooks::execute(const std::string&,
    const std::function<void(const std::string&)>&,
    const std::function<bool()>&)
{
    throw BridgeFailure({"CORE_NOT_READY", "嵌入式运行时未装配", true});
}

#endif  // GSAS_HAS_PYTHON

CPythonHooks::CPythonHooks() : m_impl(new CPythonHooks::Impl())
{
}

CPythonHooks::~CPythonHooks() = default;

}  // namespace python
}  // namespace gsas
