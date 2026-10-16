/* SPDX-License-Identifier: BSD-2-Clause */
/* Native FreeBSD checks for a disposable Secure Boot qualification guest. */
#include <sys/param.h>
#include <sys/ioctl.h>
#include <sys/linker.h>
#include <dev/veriexec/veriexec_ioctl.h>
#include <errno.h>
#include <fcntl.h>
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
	return (failed);
}
