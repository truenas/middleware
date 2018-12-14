#!/bin/sh

# Helper script which reads some pipeline ENV settings and figures out GH PR details
populate_pr_pipeline()
{
  if [ -z "$CHANGE_ID" ] ; then return 0; fi
  if [ -z "$GH_ORG" ] ; then return 0; fi
  if [ -z "$GH_REPO" ] ; then return 0; fi
  ORG="$GH_ORG"
  PRBUILDER="$GH_REPO"

  # Fetch the details from github API
  echo "curl https://api.github.com/repos/$ORG/$PRBUILDER/pulls/$CHANGE_ID"
  curl "https://api.github.com/repos/$ORG/$PRBUILDER/pulls/$CHANGE_ID" > /tmp/jsonout.$$
  #echo "Raw GH output:"
  #cat /tmp/jsonout.$$

  ghprbTargetBranch=$(cat /tmp/jsonout.$$ | jq -r '.base.ref')
  ghprbSourceBranch=$(cat /tmp/jsonout.$$ | jq -r '.base.ref')
  ghprbCommentBody=$(cat /tmp/jsonout.$$ | jq -r '.body')
  ghprbPullLongDescription=$(cat /tmp/jsonout.$$ | jq -r '.body')
  rm /tmp/jsonout.$$

  export ghprbTargetBranch ghprbSourceBranch ghprbCommentBody ghprbPullLongDescription
  export ORG PRBUILDER

  export ARTIFACTONFAIL=yes
  export ARTIFACTONSUCCESS=yes

  echo "** Populated GitHub PR details: **"
  echo "ghprbTargetBranch: $ghprbTargetBranch"
  echo "ghprbSourceBranch: $ghprbSourceBranch"
  echo "ghprbCommentBody: $ghprbCommentBody"
  echo "ghprbPullLongDescription: $ghprbPullLongDescription"

  # Something went wrong?
  if [ -z "$ghprbTargetBranch" ] ; then exit 1 ; fi
}

get_depends()
{
  if [ -z "$ghprbPullLongDescription" ] ; then return 0; fi

  # Are there DEPENDS listed?
  echo "$ghprbPullLongDescription" | grep -q "DEPENDS:"
  if [ $? -ne 0 ] ; then return 0; fi

  echo -e "$ghprbPullLongDescription" > /tmp/.depsParse.$$
  while read line
  do
    echo $line | grep -q "DEPENDS:"
    if [ $? -ne 0 ] ; then continue; fi
    _depsLine=`echo $line | sed -n -e 's/^.*DEPENDS: //p' | cut -d '\' -f 1`
    echo "*** Found PR DEPENDS Line: $_depsLine ***"
    _deps="$_deps $_depsLine"
  done < /tmp/.depsParse.$$
  rm /tmp/.depsParse.$$

  for prtgt in $_deps
  do
     if [ -z "$prtgt" ] ; then continue ; fi
     if [ "$prtgt" = " " ] ; then continue ; fi
     echo "*** Found PR DEPENDS: $_prtgt ***"
     # Pull the target PR/Repo
     tgt=`echo $prtgt | sed 's|http://||g'`
     tgt=`echo $tgt | sed 's|https://||g'`
     tgt=`echo $tgt | sed 's|www.github.com||g'`
     tgt=`echo $tgt | sed 's|github.com||g'`
     tgt=`echo $tgt | sed 's|^/||g'`
     tproject=`echo $tgt | cut -d '/' -f 1`
     trepo=`echo $tgt | cut -d '/' -f 2`
     tbranch=`echo $tgt | cut -d '/' -f 3-`
     tbranch=`echo $tbranch | sed 's|^tree/||g' | tr -d '\n\r' | tr -d '\n'`


     # TODO, maybe skip git and use fetch to download from githum ala:
     # fetch https://github.com/freenas/os/archive/sef-icp-amd64-test.tar.gz
     echo "*** Cloning DEPENDS repo https://github.com/$tproject/$trepo $tbranch***"
     git clone --depth=1 -b ${tbranch} https://github.com/${tproject}/${trepo} /usr/local_source/${trepo} 2>/tmp/.ghClone.$$ >/tmp/.ghClone.$$
     if [ $? -ne 0 ] ; then
	cat /tmp/.ghClone.$$
	rm /tmp/.ghClone.$$
	echo "**** ERROR: Failed: git clone --depth=1 -b $tbranch https://github.com/$tproject/$trepo /freenas-pr/freenas/_BE/${trepo} ****"
	exit 1
     fi
     rm /tmp/.ghClone.$$
  done
}

populate_pr_pipeline
get_depends
