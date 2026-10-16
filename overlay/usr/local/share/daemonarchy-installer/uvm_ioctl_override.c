/* Interpose NVIDIA UVM initialization for Linux binaries on FreeBSD.
 * The FreeBSD nvidia-uvm device rejects the Linuxulator's initialize ioctl.
 * CUDA still runs when that call reports "not supported" and /dev/nvidia-uvm
 * is diverted. Based on Alexey Shklyarov's public workaround:
 * https://gist.github.com/shkhln/40ef290463e78fb2b0000c60f4ad797e
 */
#define _GNU_SOURCE

#include <assert.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>

#define NV_UVM_INITIALIZE 0x30000001
#define NV_UVM_DEINITIALIZE 0x30000002
#define NV_ERR_NOT_SUPPORTED 0x56

struct NvUvmInitParams {
  uint64_t flags __attribute__((aligned(8)));
  uint32_t status;
};

int (*libc_ioctl)(int fd, unsigned long request, ...) = NULL;

int ioctl(int fd, unsigned long request, ...) {
  if (!libc_ioctl)
    libc_ioctl = dlsym(RTLD_NEXT, "ioctl");

  va_list args;
  va_start(args, request);
  void *data = va_arg(args, void *);
  va_end(args);

  if (request == NV_UVM_INITIALIZE) {
    struct NvUvmInitParams *params = data;
    params->status = NV_ERR_NOT_SUPPORTED;
    return 0;
  }
  if (request == NV_UVM_DEINITIALIZE)
    return 0;
  return libc_ioctl(fd, request, data);
}

int (*libc_open)(const char *path, int flags, ...) = NULL;

static int open_common(const char *path, int flags, mode_t mode) {
  if (strcmp("/dev/nvidia-uvm", path) == 0)
    return libc_open("/dev/null", flags, mode);
  return libc_open(path, flags, mode);
}

int open(const char *path, int flags, ...) {
  if (!libc_open)
    libc_open = dlsym(RTLD_NEXT, "open");
  mode_t mode = 0;
  va_list args;
  va_start(args, flags);
  if (flags & O_CREAT)
    mode = va_arg(args, int);
  va_end(args);
  return open_common(path, flags, mode);
}

int open64(const char *path, int flags, ...) {
  if (!libc_open)
    libc_open = dlsym(RTLD_NEXT, "open");
  mode_t mode = 0;
  va_list args;
  va_start(args, flags);
  if (flags & O_CREAT)
    mode = va_arg(args, int);
  va_end(args);
  return open_common(path, flags, mode);
}

FILE *(*libc_fopen)(const char *path, const char *mode) = NULL;

FILE *fopen(const char *path, const char *mode) {
  if (!libc_fopen)
    libc_fopen = dlsym(RTLD_NEXT, "fopen");
  if (strncmp(path, "/proc/self/task/", sizeof("/proc/self/task/") - 1) == 0) {
    const char *tail = strchr(path + sizeof("/proc/self/task/"), '/');
    if (tail != NULL && strcmp(tail, "/comm") == 0) {
      assert(strcmp(mode, "wb") == 0);
      return libc_fopen("/dev/null", mode);
    }
  }
  return libc_fopen(path, mode);
}
