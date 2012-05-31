#!/bin/bash -x

emph() { 
echo -e "\033[1m$@\033[0m" ;
#echo -e "\E[34;47m$@" ; tput sgr0
}

debug() { echo "$(date) $(hostname) $@" >&2 ; }
warning() { emph "$(date) $(hostname) WARNING $@" >&2 ; }
die() { warning $@ ; exit 1 ; }

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

TMPDIRPREFIX="/tmp/cobbler-import"

add()
{
  BNAME=$1
  ISO=$2
  TMPDIR=""
  DISTRONAME=$BNAME-distro
  PROFILENAME=$BNAME-profile
  TMPDIR=""
  TFTPBOOTDIR=""

  # Check some basic things
  [ -e $ISO ] || die "Given ISO '$ISO' does not exist."
  _object_exists profile $PROFILENAME && die "Profile '$PROFILENAME' already exists"
  _object_exists distro $DISTRONAME && die "Distro '$DISTRONAME' already exists"

  TMPDIR="$TMPDIRPREFIX-$BNAME"
  [[ -e $TMPDIR ]] && die "Tmpdir $TMPDIR already exists. Already imported?"
  debug "Using tmpdir $TMPDIR"
  mkdir $TMPDIR
  cd $TMPDIR

  livecd-iso-to-pxeboot "$ISO"
  TFTPBOOTDIR="$TMPDIR/tftpboot"
  [ -e $TFTPBOOTDIR ] || die "tftpboot wasn't created"

  cobbler distro add \
    --name=$DISTRONAME \
    --kernel=$(ls $(pwd)/tftpboot/vmlinuz*) \
    --initrd=$(ls $(pwd)/tftpboot/initrd*) \
    --kopts="$(grep APPEND $(pwd)/tftpboot/pxelinux.cfg/default | sed -r 's/^[ \t]+APPEND // ; s/initrd=[^[:space:]]+//g ; s/[[:space:]]$//')" \
    --arch=x86_64
  cobbler profile add --name=$PROFILENAME --distro=$DISTRONAME
  [[ -z $FORCE_SYNC ]] || cobbler sync

  exit 0
}

remove()
{
  BNAME=$1
  DISTRONAME=$BNAME-distro
  PROFILENAME=$BNAME-profile
  TMPDIR="$TMPDIRPREFIX-$BNAME"
  TFTPBOOTDIR="$TMPDIR/tftpboot"

  [ -z $BNAME ] && die "<bname> needs to be given."

  _object_exists profile $PROFILENAME && {
    cobbler profile remove --name=$PROFILENAME 
  } || warning "Profile '$PROFILENAME' does not exist"
  _object_exists distro $DISTRONAME && {
    cobbler distro remove --name=$DISTRONAME
  } || warning "Distro '$DISTRONAME' does not exist"
  [[ -z $FORCE_SYNC ]] || cobbler sync

  [[ -e $TMPDIR ]] && {
    rm $TFTPBOOTDIR/pxelinux.cfg/*
    rmdir $TFTPBOOTDIR/pxelinux.cfg
    rm $TFTPBOOTDIR/*
    rmdir $TFTPBOOTDIR
    rmdir $TMPDIR
  } || warning "Tmpdir '$TMPDIR' does not exists. Already imported?"

  exit 0
}

readd()
{
  BNAME=$1
  ISO=$2
  remove $ISO
  add $BNAME $ISO
}

RTMPDIR="/tmp/ovirt_cobbler_temporary_folder_for_remote_import"
pre_remote()
{
  DSTHOST=$1

  debug "Preparing remote temp dir: $RTMPDIR"
  ssh $DSTHOST "[[ -e $RTMPDIR ]] && exit 1 ; mkdir $RTMPDIR" || die "Something wrong with remote dir."

  debug "Copying this script"
  scp $0 $DSTHOST:$RTMPDIR/
}
post_remote()
{
  DSTHOST=$1
  debug "Cleaning remote"
  ssh $DSTHOST "cd $RTMPDIR && { rm -vrf tftpboot ; rm -vf * ; cd ~ && rmdir -v $RTMPDIR ; }"
}
remote_add()
{
  DSTHOST=$1
  BNAME=$2
  ISO=$3

  pre_remote $DSTHOST

  debug "Copying ISO $ISO to remote"
  scp -C $ISO $DSTHOST:$RTMPDIR/$(basename $ISO)
  debug "Running remote"
  ssh $DSTHOST "cd $RTMPDIR && bash $(basename $0) add $BNAME $RTMPDIR/$(basename $ISO)"

  post_remote $DSTHOST
}
remote_remove()
{
  DSTHOST=$1
  BNAME=$2

  pre_remote $DSTHOST

  ssh $DSTHOST "cd $RTMPDIR && bash $(basename $0) remove $BNAME"

  post_remote $DSTHOST
}
remote_readd()
{
  DSTHOST=$1
  BNAME=$2
  ISO=$3

  pre_remote $DSTHOST

  ssh $DSTHOST "cd $RTMPDIR && bash $(basename $0) readd $BNAME $RTMPDIR/$(basename $ISO)"

  post_remote $DSTHOST
}


${@:-usage}

# vim: sw=2:

