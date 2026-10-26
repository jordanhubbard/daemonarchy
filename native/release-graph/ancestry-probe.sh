export GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0 GIT_OPTIONAL_LOCKS=0 LC_ALL=C
echo "host=$(hostname) uname=$(uname -srvm | tr ' ' '_')"
echo "started_utc=$(date -u +%FT%TZ)"
echo "bhyve_guests=$(pgrep -x bhyve | wc -l | tr -d ' ')"
echo "git_version=$(git --version)"
probe() { name=$1 repo=$2 fork=$3 up=$4
  echo "== repo=$name path=$repo"
  echo "origin=$(git -C $repo config --get remote.origin.url)"
  echo "gitdir=$(git -C $repo rev-parse --absolute-git-dir)"
  echo "partial_clone_filter=$(git -C $repo config --get remote.origin.partialclonefilter || echo none)"
  echo "promisor=$(git -C $repo config --get remote.origin.promisor || echo none)"
  for c in $fork $up; do
    t=$(timeout 60 git -C $repo cat-file -t $c 2>&1); echo "cat-file -t $c -> rc=$? out=$t"
  done
  cmd="timeout 60 git -C $repo merge-base --is-ancestor $up $fork"
  echo "cmd=$cmd"
  s=$(date +%s); out=$($cmd 2>&1); rc=$?; e=$(date +%s)
  echo "exit=$rc elapsed_s=$((e-s)) output=${out:-<empty>}"
}
probe daemonarchy-src /usr/src d63d77f4eb3cc29e16510f7bdec73602e27c2844 a3d1d4e88ae7435cfc32a886999dcde2173839cd
probe daemonarchy-ports /usr/ports b785784219af455a9ce4fd70c59bc96ba77f469f a7c9a97bae26bf342e1bffb2273b7ef331cdb289
echo "finished_utc=$(date -u +%FT%TZ)"
