/* SPDX-License-Identifier: BSD-2-Clause */
/* Native FreeBSD checks for a disposable Secure Boot qualification guest. */
#include <sys/param.h>
#include <sys/ioctl.h>
#include <sys/linker.h>
#include <sys/sysctl.h>
#include <sys/wait.h>
#include <dev/veriexec/veriexec_ioctl.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int
denied(const char *name, int result, int expected)
{

	if (result != -1 || errno != expected) {
		fprintf(stderr, "FAIL %s: result=%d errno=%d expected=%d\n",
		    name, result, errno, expected);
		return (1);
	}
	printf("PASS %s: errno=%d\n", name, expected);
	return (0);
}

int
main(int argc, char **argv)
{
	struct verified_exec_params params;
	pid_t child;
	size_t length;
	int mib[4], result;
	int fd, failed;

	if (argc != 3 || getuid() != 0) {
		fprintf(stderr, "usage (root, disposable guest only): %s "
		    "unsigned-module protected-module\n", argv[0]);
		return (2);
	}
	setbuf(stdout, NULL);
	/* The linker class dispatcher reports ENOEXEC; require the kernel log too. */
	failed = denied("unsigned-module", kldload(argv[1]), ENOEXEC);
	failed |= denied("protected-module-write",
	    open(argv[2], O_WRONLY), EPERM);
	failed |= denied("kernel-memory-write", open("/dev/kmem", O_WRONLY),
	    EPERM);
	fd = open("/dev/veriexec", O_RDWR);
	if (fd < 0) {
		perror("open /dev/veriexec");
		return (1);
	}
	memset(&params, 0, sizeof(params));
	failed |= denied("locked-policy-load",
	    ioctl(fd, VERIEXEC_SIGNED_LOAD, &params), EPERM);
	close(fd);
	/* Desktop session helpers read another process's environment. The full
	 * upstream userland-label hook called VOP_GETATTR without a vnode lock. */
	child = fork();
	if (child == -1) {
		perror("fork process-inspection child");
		return (1);
	}
	if (child == 0) {
		for (;;)
			pause();
	}
	mib[0] = CTL_KERN;
	mib[1] = KERN_PROC;
	mib[2] = KERN_PROC_ENV;
	mib[3] = child;
	length = 0;
	result = sysctl(mib, 4, NULL, &length, NULL, 0);
	if (result == 0 && length > 0)
		puts("PASS process-environment-read");
	else {
		fprintf(stderr, "FAIL process-environment-read: result=%d errno=%d\n",
		    result, errno);
		failed = 1;
	}
	kill(child, SIGTERM);
	while (waitpid(child, NULL, 0) == -1 && errno == EINTR)
		;
	return (failed);
}
