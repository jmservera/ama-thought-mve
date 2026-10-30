#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "fileutils.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(void)
{
    char directory[] = "/tmp/mve-openat2-XXXXXX";
    assert(mkdtemp(directory));
    int parent = open(directory, O_DIRECTORY | O_RDONLY | O_CLOEXEC);
    assert(parent >= 0);
    int file = openat(parent, "regular", O_CREAT | O_WRONLY | O_CLOEXEC, 0600);
    assert(file >= 0);
    close(file);
    assert(symlinkat("regular", parent, "link") == 0);

    file = ul_openat_resolve(parent, "regular", O_RDONLY | O_CLOEXEC, 0,
                             RESOLVE_NO_SYMLINKS);
    assert(file >= 0);
    close(file);
    errno = 0;
    file = ul_openat_resolve(parent, "link", O_RDONLY | O_CLOEXEC, 0,
                             RESOLVE_NO_SYMLINKS);
    assert(file == -1 && errno == ELOOP);
    assert(unlinkat(parent, "link", 0) == 0);
    assert(unlinkat(parent, "regular", 0) == 0);
    close(parent);
    assert(rmdir(directory) == 0);
    puts("PASS: real file opens; ordinary symlink is rejected by the patched wrapper");
    return 0;
}
