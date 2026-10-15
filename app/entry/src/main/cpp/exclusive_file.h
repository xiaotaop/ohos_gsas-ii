#ifndef GSAS_PC_EXCLUSIVE_FILE_H
#define GSAS_PC_EXCLUSIVE_FILE_H
#include <fcntl.h>
// Never open an existing destination, even if it is empty or a symlink.
// The caller owns the descriptor and must close it exactly once.
inline int GsasOpenExclusive(const char *path)
{
    return open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
}
#endif
