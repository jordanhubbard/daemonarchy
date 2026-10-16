/* Linux executable for an actual GPU test through FreeBSD's Linuxulator.
 * Build on Linux: cc -Wall -Wextra -Werror cuda-probe.c -ldl -o cuda-probe
 * No toolkit headers required; use the installed NVIDIA driver API.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint64_t DevicePointer;
#define API(name, args) static int (*name) args
API(cuInit, (unsigned));
API(cuDeviceGetCount, (int *));
API(cuDeviceGet, (int *, int));
API(cuDeviceGetName, (char *, int, int));
API(cuCtxCreate_v2, (void **, unsigned, int));
API(cuModuleLoadData, (void **, const void *));
API(cuModuleGetFunction, (void **, void *, const char *));
API(cuMemAlloc_v2, (DevicePointer *, size_t));
API(cuMemcpyHtoD_v2, (DevicePointer, const void *, size_t));
API(cuLaunchKernel, (void *, unsigned, unsigned, unsigned, unsigned,
    unsigned, unsigned, unsigned, void *, void **, void **));
API(cuCtxSynchronize, (void));
API(cuMemcpyDtoH_v2, (void *, DevicePointer, size_t));
API(cuMemFree_v2, (DevicePointer));
API(cuModuleUnload, (void *));
API(cuCtxDestroy_v2, (void *));

static void
check(const char *operation, int result)
{
    if (result != 0) {
        fprintf(stderr, "FAIL %s: CUDA error %d\n", operation, result);
        exit(1);
    }
    printf("PASS %s\n", operation);
}

#define LOAD(name) do { *(void **)(&name) = dlsym(driver, #name); \
    if (!name) { fprintf(stderr, "Missing %s: %s\n", #name, dlerror()); return 1; } \
    } while (0)
#define CHECK(call) check(#call, (call))

int
main(void)
{
    const char ptx[] = ".version 8.0\n.target sm_89\n.address_size 64\n"
        ".visible .entry write_answer(.param .u64 output) {\n"
        " .reg .u64 %rd; .reg .u32 %r;\n"
        " ld.param.u64 %rd, [output]; mov.u32 %r, 42;\n"
        " st.global.u32 [%rd], %r; ret; }\n";
    void *driver, *context, *module, *function;
    DevicePointer output;
    void *arguments[] = { &output };
    int count, device, answer = 0;
    char name[256];

    setbuf(stdout, NULL);
    driver = dlopen("libcuda.so.1", RTLD_NOW);
    if (!driver) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    LOAD(cuInit); LOAD(cuDeviceGetCount); LOAD(cuDeviceGet);
    LOAD(cuDeviceGetName); LOAD(cuCtxCreate_v2); LOAD(cuModuleLoadData);
    LOAD(cuModuleGetFunction); LOAD(cuMemAlloc_v2); LOAD(cuMemcpyHtoD_v2);
    LOAD(cuLaunchKernel); LOAD(cuCtxSynchronize); LOAD(cuMemcpyDtoH_v2);
    LOAD(cuMemFree_v2); LOAD(cuModuleUnload); LOAD(cuCtxDestroy_v2);
    CHECK(cuInit(0));
    CHECK(cuDeviceGetCount(&count));
    if (count < 1) { fputs("No CUDA devices\n", stderr); return 1; }
    CHECK(cuDeviceGet(&device, 0));
    CHECK(cuDeviceGetName(name, sizeof(name), device));
    printf("CUDA device: %s (%d devices)\n", name, count);
    CHECK(cuCtxCreate_v2(&context, 0, device));
    CHECK(cuModuleLoadData(&module, ptx));
    CHECK(cuModuleGetFunction(&function, module, "write_answer"));
    CHECK(cuMemAlloc_v2(&output, sizeof(answer)));
    CHECK(cuMemcpyHtoD_v2(output, &answer, sizeof(answer)));
    CHECK(cuLaunchKernel(function, 1, 1, 1, 1, 1, 1, 0, NULL, arguments, NULL));
    CHECK(cuCtxSynchronize());
    CHECK(cuMemcpyDtoH_v2(&answer, output, sizeof(answer)));
    CHECK(cuMemFree_v2(output));
    CHECK(cuModuleUnload(module));
    CHECK(cuCtxDestroy_v2(context));
    if (answer != 42) { fprintf(stderr, "Wrong GPU result: %d\n", answer); return 1; }
    puts("PASS CUDA GPU executed PTX and returned 42");
    dlclose(driver);
    return 0;
}
