#include <cerrno>
#include <cstdlib>
#include <string>
#include <vector>
#include <unistd.h>
#include <napi/native_api.h>
#include <filemanagement/file_uri/oh_file_uri.h>
#include "exclusive_file.h"

static napi_value Fail(napi_env env)
{
    // Keep paths and platform details out of user-facing errors.
    napi_throw_error(env, "OUTPUT_WRITE_FAILED", "Cannot create export destination exclusively");
    return nullptr;
}

static napi_value OpenExclusive(napi_env env, napi_callback_info info)
{
    size_t argc = 1;
    napi_value args[1];
    if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) != napi_ok || argc != 1) {
        return Fail(env);
    }
    size_t length = 0;
    if (napi_get_value_string_utf8(env, args[0], nullptr, 0, &length) != napi_ok || length == 0 || length > 16384) {
        return Fail(env);
    }
    std::vector<char> buffer(length + 1);
    size_t copied = 0;
    if (napi_get_value_string_utf8(env, args[0], buffer.data(), buffer.size(), &copied) != napi_ok || copied != length) {
        return Fail(env);
    }
    const std::string uri(buffer.data(), length);
    if (uri.find('\0') != std::string::npos || uri.compare(0, 7, "file://") != 0 || uri.compare(0, 12, "file://docs/") == 0) {
        return Fail(env);
    }
    char *path = nullptr;
    if (OH_FileUri_GetPathFromUri(uri.data(), static_cast<unsigned int>(uri.size()), &path) != 0 || !path) {
        free(path);
        return Fail(env);
    }
    const int fd = GsasOpenExclusive(path);
    free(path);
    if (fd < 0) { return Fail(env); }
    napi_value result;
    if (napi_create_int32(env, fd, &result) != napi_ok) {
        close(fd);
        return Fail(env);
    }
    return result;
}

static napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor property = {
        "openExclusive", nullptr, OpenExclusive, nullptr, nullptr, nullptr, napi_default, nullptr
    };
    if (napi_define_properties(env, exports, 1, &property) != napi_ok) { return nullptr; }
    return exports;
}
static napi_module module = { 1, 0, nullptr, Init, "gsas_fileio", nullptr, {0} };
extern "C" __attribute__((constructor)) void RegisterGsasFileIo()
{
    napi_module_register(&module);
}
