#!/bin/bash

set -e

emph() { 
echo -e "\033[1m$@\033[0m" ;
#echo -e "\E[34;47m$@" ; tput sgr0
}

debug() { emph "$(date) $@" >&2 ; }
die() { debug $@ ; exit 1 ; }

run() {
  debug "Running $@"
  $@
}
sshrun()
{
  debug "Running $2 on $1"
  ssh $1 "$2"
}

usage()
{
  cat <<EOU
$0 add <bname> <iso>
add <bname> <iso>   - Add a cobbler distro- and profile.
                      distro- and profile-name will be dervied from 
                      <bname> by appending -distro and -profile.
remove <bname>      - Remove a cobbler distro

remote_add <host> <bname> <localiso>
remote_remove <host> <bname>
EOU
}


_object_exists()
{
  if cobbler $1 report --name="$2" >/dev/null 2>&1; then
    debug "$1 object $2 exists"
    return 0
  fi
  return 1
}

add()
{
  BNAME=$1
  ISO=$2
  TMPDIR=""
  DISTRONAME=$BNAME-distro
  PROFILENAME=$BNAME-profile
  TFTPBOOTDIR=""

  # Check some basic things
  [ -e $ISO ] || die "Given ISO '$ISO' does not exist."
  _object_exists profile $PROFILENAME && die "Profile '$PROFILENAME' already exists"
  _object_exists distro $DISTRONAME && die "Distro '$DISTRONAME' already exists"

  pushd .
  TMPDIR=$(mktemp -d)
  TFTPBOOTDIR="$TMPDIR/tftpboot"
  debug "Using tmpdir $TMPDIR"
  cd $TMPDIR

  run livecd-iso-to-pxeboot "$ISO"
  [ -e $TFTPBOOTDIR ] || die "tftpboot wasn't created"

  run cobbler distro add \
    --name=$DISTRONAME \
    --kernel=$(ls $(pwd)/tftpboot/vmlinuz*) \
    --initrd=$(ls $(pwd)/tftpboot/initrd*) \
    --kopts="$(grep APPEND $(pwd)/tftpboot/pxelinux.cfg/default | sed -r 's/^[ \t]+APPEND // ; s/initrd=[^[:space:]]+//g')" \
    --arch=x86_64
  run cobbler profile add --name=$PROFILENAME --distro=$DISTRONAME
  run cobbler sync

  run rm $TFTPBOOTDIR/pxelinux.cfg/*
  run rmdir $TFTPBOOTDIR/pxelinux.cfg
  run rm $TFTPBOOTDIR/*
  run rmdir $TFTPBOOTDIR
  popd
  run rmdir $TMPDIR
  exit 0
}

remove()
{
  BNAME=$1
  DISTRONAME=$BNAME-distro
  PROFILENAME=$BNAME-profile

  [ -z $BNAME ] && die "<bname> needs to be given."

  _object_exists profile $PROFILENAME || die "Profile '$PROFILENAME' does not exist"
  _object_exists distro $DISTRONAME || die "Distro '$DISTRONAME' does not exist"

  cobbler profile remove --name=$PROFILENAME
  cobbler distro remove --name=$DISTRONAME
  run cobbler sync

  exit 0
}

readd()
{
  BNAME=$1
  ISO=$2
  remove $ISO
  add $BNAME $ISO
}

RTMPDIR="/tmp/ovirt_temporary_cobler_import"
pre_remote()
{
  DSTHOST=$1

  debug "Preparing remote temp dir: $RTMPDIR"
  sshrun $DSTHOST "[[ -e $RTMPDIR ]] && exit 1 ; mkdir $RTMPDIR" || die "Something wrong with remote dir."

  debug "Copying this script"
  run scp $0 $DSTHOST:$RTMPDIR/
}
post_remote()
{
  DSTHOST=$1
  debug "Cleaning remote"
  sshrun $DSTHOST "cd $RTMPDIR && { rm -vrf tftpboot ; rm -vf * ; cd ~ && rmdir -v $RTMPDIR ; }"
}
remote_add()
{
  DSTHOST=$1
  BNAME=$2
  ISO=$3

  pre_remote $DSTHOST

  debug "Copying ISO $ISO to remote"
  run scp -C $ISO $DSTHOST:$RTMPDIR/$(basename $ISO)
  debug "Running remote"
  sshrun $DSTHOST "cd $RTMPDIR && bash $(basename $0) add $BNAME $RTMPDIR/$(basename $ISO)"

  post_remote $DSTHOST
}
remote_remove()
{
  DSTHOST=$1
  BNAME=$2

  pre_remote $DSTHOST

  sshrun $DSTHOST "cd $RTMPDIR && bash $(basename $0) remove $BNAME"

  post_remote $DSTHOST
}
remote_readd()
{
  DSTHOST=$1
  BNAME=$2
  ISO=$3

  pre_remote $DSTHOST

  sshrun $DSTHOST "cd $RTMPDIR && bash $(basename $0) readd $BNAME $RTMPDIR/$(basename $ISO)"

  post_remote $DSTHOST
}


${@:-usage}

# vim: sw=2:

