
import logging
import time
import os
import subprocess

logger = logging.getLogger(__name__)
logging.basicConfig( \
    format='%(levelname)s - %(asctime)s - %(module)s - %(message)s', \
    level=logging.DEBUG)
# Picking up from client-bootstrap.sh
class Igor(object):
  def __init__(self):
    for name in ["APIURL", "SESSION", "CURRENT_STEP", "TESTSUITE", "LIBDIR"]:
      v = "__%s__" % name
      k = "IGOR_%s" % name
      if k in os.environ:
        v = os.environ[k]
      self.__dict__[name.lower()] = v

igor = Igor()

def debug(msg):
  logger.debug(msg) 

def run(cmd, with_retval=False):
  """Run a command cmd.

  >>> run("echo 0")
  '0'
  """
  proc = subprocess.Popen(cmd, shell=True, \
                          stdout=subprocess.PIPE, \
                          stderr=subprocess.PIPE)
  (stdout, stderr) = proc.communicate()
  proc.wait()
  if stderr:
      logger.warning(stderr)
  r = stdout.strip()
  if with_retval:
      r = (proc.returncode, stdout.strip())
  return r

def debug_curl(url):
  """Curl a URL
  >>> debug_curl("localhost")
  ''
  """
  debug("Calling '%s'" % url)
  return run("curl --silent '%s'" % url)

def api_url(p):
  """Build an api url
  >>> api_url("p")
  '__APIURL__/p'
  """
  return os.path.join(igor.apiurl, p)

def api_call(p):
  """Build and curl an API URL
  >>> api_call("p")
  ''
  """
  return debug_curl(api_url(p))

def step_succeeded():
  api_call("job/step/{session}/{step}/success".format(session=igor.session, \
                                                      step=igor.current_step))

def step_failed():
  api_call("job/step/{session}/{step}/failed".format(session=igor.session, \
                                                     step=igor.current_step))

def add_artifact(dst, filename):
  if not os.path.exists(filename):
    raise Exception(("Failed to add artifact '%s', because file '%s' does " + \
                     "not exist") % (dst, filename))

  debug("Adding artifact '%s': '%s'" % (dst, filename))
  url = api_url("job/artifact/for/" + \
                "{session}/{dst}".format(session=igor.session, \
                                         dst=dst))
  run("curl --silent --request PUT --upload-file - " + \
      "'{url}' <'{filename}'".format(url=url, filename=filename))

# vim: set sw=2:
