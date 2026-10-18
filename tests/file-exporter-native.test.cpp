#include "../app/entry/src/main/cpp/exclusive_file.h"
#include <cassert>
#include <cerrno>
#include <cstdlib>
#include <string>
#include <unistd.h>
int main()
{
    char directory[] = "/tmp/gsas-exclusive-native-XXXXXX";
    assert(mkdtemp(directory));
    const std::string path = std::string(directory) + "/new.xra";
    int fd = GsasOpenExclusive(path.c_str());
    assert(fd >= 0 && close(fd) == 0);
    errno = 0;
    assert(GsasOpenExclusive(path.c_str()) == -1 && errno == EEXIST);
    assert(unlink(path.c_str()) == 0);
    const std::string target = std::string(directory) + "/original";
    fd = GsasOpenExclusive(target.c_str());
    assert(fd >= 0 && write(fd, "keep", 4) == 4 && close(fd) == 0);
    assert(symlink(target.c_str(), path.c_str()) == 0);
    assert(GsasOpenExclusive(path.c_str()) == -1);
    char bytes[4]; fd = open(target.c_str(), O_RDONLY);
    assert(fd >= 0 && read(fd, bytes, 4) == 4 && std::string(bytes, 4) == "keep");
    assert(close(fd) == 0 && unlink(path.c_str()) == 0 && unlink(target.c_str()) == 0 && rmdir(directory) == 0);
}
