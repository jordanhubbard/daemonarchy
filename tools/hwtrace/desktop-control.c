/* SPDX-License-Identifier: BSD-2-Clause
 * Private display-control harness. Mounts only its explicitly named RAM root.
 */
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mount.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <sys/event.h>
#include <err.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <fts.h>
#include <stdint.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

static void wait_socket(const char *root, const char *relative, const char *seconds) {
 char path[PATH_MAX], parent[PATH_MAX], *end;
 struct timespec now, deadline, remaining;
 struct stat st;
 long duration = strtol(seconds, &end, 10);
 if (*end || duration < 1 || duration > 30 ||
     strncmp(relative,"var/run/",8) || strstr(relative,"..") ||
     strlen(root)+strlen(relative)+2 > sizeof(path))
  errx(64,"invalid socket wait");
 snprintf(path,sizeof(path),"%s/%s",root,relative);
 strlcpy(parent,path,sizeof(parent)); *strrchr(parent,'/')='\0';
 int fd=open(parent,O_RDONLY|O_DIRECTORY);
 if (fd<0) err(1,"socket parent");
 int queue=kqueue(); if (queue<0) err(1,"kqueue");
 struct kevent change,event;
 EV_SET(&change,fd,EVFILT_VNODE,EV_ADD|EV_CLEAR,
     NOTE_WRITE|NOTE_DELETE|NOTE_RENAME,0,NULL);
 if (kevent(queue,&change,1,NULL,0,NULL)<0) err(1,"watch socket parent");
 if (clock_gettime(CLOCK_MONOTONIC,&deadline)) err(1,"clock");
 deadline.tv_sec+=duration;
 for (;;) {
  if (lstat(path,&st)==0) {
   if (!S_ISSOCK(st.st_mode)) errx(1,"expected socket");
   close(queue); close(fd); return;
  }
  if (errno!=ENOENT) err(1,"socket stat");
  if (clock_gettime(CLOCK_MONOTONIC,&now)) err(1,"clock");
  remaining.tv_sec=deadline.tv_sec-now.tv_sec;
  remaining.tv_nsec=deadline.tv_nsec-now.tv_nsec;
  if (remaining.tv_nsec<0) { remaining.tv_sec--; remaining.tv_nsec+=1000000000; }
  if (remaining.tv_sec<0 || (!remaining.tv_sec && !remaining.tv_nsec))
   errx(1,"socket readiness deadline");
  int count=kevent(queue,NULL,0,&event,1,&remaining);
  if (count<0 && errno==EINTR) continue;
  if (count<0) err(1,"wait socket");
  if (!count) errx(1,"socket readiness deadline");
  if (event.fflags & (NOTE_DELETE|NOTE_RENAME)) errx(1,"socket parent moved");
 }
}

static void allowed(const char *root) {
 const char *prefix = "/var/tmp/daemonarchy-desktop-";
 if (strncmp(root, prefix, strlen(prefix)) || strlen(root) > 120 ||
     strchr(root + strlen(prefix), '/') || strstr(root, ".."))
  errx(64, "invalid private runtime root");
}
static int mountfs(const char *type, const char *path, int tmpfs) {
 struct iovec iov[12]; int n = 0;
 #define ADD(k,v) do { iov[n++] = (struct iovec){(void *)(k),strlen(k)+1}; iov[n++] = (struct iovec){(void *)(v),strlen(v)+1}; } while (0)
 ADD("fstype", type); ADD("fspath", path);
 if (tmpfs) { ADD("size", "768m"); ADD("mode", "0755"); }
 return nmount(iov, n, MNT_NOSUID | MNT_NOATIME);
}
static void enter(const char *root, int user, char **args) {
 if (chroot(root) || chdir("/")) err(1,"chroot");
 if (user) {
  gid_t groups[] = {1001,44};
  if (setgroups(2,groups) || setgid(1001) || setuid(1001)) err(1,"drop display credentials");
  if (chdir("/home/displaytest")) err(1,"display home");
  setenv("USER","displaytest",1); setenv("LOGNAME","displaytest",1);
  setenv("XDG_RUNTIME_DIR","/var/run/displaytest",1);
  setenv("XDG_CACHE_HOME","/var/cache/displaytest",1);
  setenv("XDG_SESSION_TYPE","wayland",1);
  setenv("LIBSEAT_BACKEND","seatd",1);
  setenv("WLR_BACKENDS","drm,libinput",1);
  setenv("WLR_DRM_DEVICES","/dev/dri/card0",1);
  setenv("WLR_RENDERER","pixman",1);
  setenv("WLR_LIBINPUT_NO_DEVICES","1",1);
  setenv("LC_ALL","C.UTF-8",1);
 }
 setenv("PATH","/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin",1);
 setenv("SEATD_VTBOUND","0",1);
 execv(args[0],args); err(1,"exec %s",args[0]);
}
int main(int argc, char **argv) {
 char path[PATH_MAX],log[PATH_MAX]; struct xvfsconf vfc;
 if (argc == 2 && !strcmp(argv[1],"probe")) {
  printf("tmpfs=%d devfs=%d\n", getvfsbyname("tmpfs",&vfc)==0,
      getvfsbyname("devfs",&vfc)==0); return 0;
 }
 if (argc < 3 || getuid()!=0) errx(64,"root: control init|devfs|exec-root|exec-user|launch-root|launch-user ROOT [COMMAND ...]");
 allowed(argv[2]); umask(0077);
 if (!strcmp(argv[1],"wait-socket")) {
  if (argc!=5) errx(64,"wait-socket ROOT RELATIVE-PATH SECONDS");
  wait_socket(argv[2],argv[3],argv[4]); return 0;
 }
 if (!strcmp(argv[1],"inventory")) {
  char *paths[] = {argv[2],NULL};
  FTS *tree = fts_open(paths,FTS_PHYSICAL|FTS_NOCHDIR|FTS_XDEV,NULL);
  if (!tree) err(1,"inventory open");
  FTSENT *entry;
  while ((entry=fts_read(tree)) != NULL) {
   if (entry->fts_level==0 || entry->fts_info==FTS_DP) continue;
   if (entry->fts_info==FTS_ERR || entry->fts_info==FTS_NS) errx(1,"inventory stat");
   const struct stat *st=entry->fts_statp;
   char kind=S_ISDIR(st->st_mode)?'d':S_ISREG(st->st_mode)?'f':S_ISLNK(st->st_mode)?'l':'x';
   printf("%o %u %u %ju %c\t%s\n",(unsigned)(st->st_mode&07777),(unsigned)st->st_uid,(unsigned)st->st_gid,(uintmax_t)st->st_size,kind,entry->fts_path+strlen(argv[2])+1);
  }
  if (fts_close(tree)) err(1,"inventory close");
  return 0;
 }

 if (!strcmp(argv[1],"init")) {
  if (mkdir(argv[2],0755)) err(1,"create fresh mountpoint");
  if (mountfs("tmpfs",argv[2],1)) err(1,"mount private tmpfs");
  printf("RAM runtime mounted at %s\n",argv[2]); return 0;
 }
 if (!strcmp(argv[1],"devfs")) {
  snprintf(path,sizeof(path),"%s/dev",argv[2]);
  if (mountfs("devfs",path,0)) err(1,"mount private devfs");
  printf("private device namespace mounted\n"); return 0;
 }
 if (argc < 4) errx(64,"missing executable");
 if (!strcmp(argv[1],"exec-root")) enter(argv[2],0,argv+3);
 if (!strcmp(argv[1],"exec-user")) enter(argv[2],1,argv+3);
 if (!strcmp(argv[1],"launch-root") || !strcmp(argv[1],"launch-user")) {
  int user = !strcmp(argv[1],"launch-user");
  snprintf(path,sizeof(path),"%s/var/log",argv[2]);
  if (mkdir(path,0700) && errno!=EEXIST) err(1,"create private log directory");
  snprintf(log,sizeof(log),"%s/%s.log",path,user?"sway":"seatd");
  int fd = open(log,O_WRONLY|O_CREAT|O_EXCL,0600); if (fd<0) err(1,"new private log");
  pid_t pid = fork(); if (pid<0) err(1,"fork");
  if (pid == 0) {
   sigset_t empty; sigemptyset(&empty); sigprocmask(SIG_SETMASK,&empty,NULL);
   for (int sig=1; sig<NSIG; sig++) if (sig!=SIGKILL && sig!=SIGSTOP) signal(sig,SIG_DFL);
   if (setsid()<0) err(1,"setsid");
   int null=open("/dev/null",O_RDONLY); if (null>=0) dup2(null,STDIN_FILENO);
   dup2(fd,STDOUT_FILENO); dup2(fd,STDERR_FILENO); close(fd);
   enter(argv[2],user,argv+3);
  }
  close(fd); printf("pid=%d log=%s\n",pid,log); return 0;
 }
 errx(64,"unknown operation");
}
