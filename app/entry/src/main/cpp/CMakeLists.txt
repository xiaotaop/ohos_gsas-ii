cmake_minimum_required(VERSION 3.5.0)
project(gsas_fileio)

add_library(gsas_fileio SHARED file_exporter.cpp)
target_compile_features(gsas_fileio PRIVATE cxx_std_17)
target_compile_options(gsas_fileio PRIVATE -Wall -Wextra -Werror -Wno-unused-command-line-argument)
target_link_libraries(gsas_fileio PUBLIC libace_napi.z.so libohfileuri.so)

# CORE_API v1.0 orchestration: N-API glue, the C++ port of bridge/service.py
# and the embedded-CPython host. The interpreter is compiled in only when the
# RUNTIME_PACKAGING §2 payload has been dropped under cpp/python (include/
# Python.h plus libs/<abi>/libpython3.12.so); without it python_host.cpp
# builds the stub variant that rejects with CORE_NOT_READY, so a
# file-service-only HAP still assembles.
add_library(gsas_core SHARED
  napi_core.cpp
  core/core_service.cpp
  python/python_host.cpp
)
# Device dependencies live in the installed app library directory. Do not
# embed the temporary host staging directory as a runtime search path.
set_target_properties(gsas_core PROPERTIES SKIP_BUILD_RPATH TRUE)
target_compile_features(gsas_core PRIVATE cxx_std_17)
target_compile_options(gsas_core PRIVATE -Wall -Wextra -Werror -Wno-unused-command-line-argument)
target_include_directories(gsas_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(gsas_core PUBLIC libace_napi.z.so)

if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/python/include/Python.h)
  # find_library is unusable here: ohos.toolchain.cmake sets
  # CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY, which re-roots PATHS into the
  # sysroot and never finds the payload directory. Link the file directly;
  # libpython3.12.so carries no SONAME, so the loader records it by file name
  # and resolves it from libs/arm64-v8a/ on device (RUNTIME_PACKAGING §2).
  set(GSAS_PYTHON_LIBRARY ${CMAKE_CURRENT_SOURCE_DIR}/python/libs/${OHOS_ARCH}/libpython3.12.so)
  if(NOT EXISTS ${GSAS_PYTHON_LIBRARY})
    message(FATAL_ERROR
      "cpp/python/include found but libpython3.12.so is missing under cpp/python/libs/${OHOS_ARCH}")
  endif()
  target_compile_definitions(gsas_core PRIVATE GSAS_HAS_PYTHON)
  target_include_directories(gsas_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/python/include)
  target_link_libraries(gsas_core PUBLIC ${GSAS_PYTHON_LIBRARY})
endif()
