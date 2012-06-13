from distutils.core import setup
import os
import re

def build_testcases_filelist(dst, path):
    xpat = re.compile("~$")
    lst = []
    for root, dirs, files in os.walk(path):
        lf = []
        for f in files:
            if xpat.search(f):
                continue
            lf.append(os.path.join(root, f))
        lst.append((os.path.join(dst, root), lf))
    return lst

setup(
    name='igor',
    version='0.1.0',
    author='Fabian Deutsch',
    author_email='fabiand@fedoraproject.org',
    packages=['igor', 'igor.test'],
    package_data={'igor': ['data/*.xsl', 'data/*.sh']},
    scripts=['bin/igord', 'bin/igor-status-to-report'],
    data_files=[('/lib/systemd/system', ['data/igord.service']),
                ('/etc/igord', ['data/igord.cfg.example']),
                ('/srv/igord', []),
                ('/usr/lib/igord/testcases', [])], # FIXME testcases are missing
    url='http://www.gitorious.org/ovirt/igord',
    license='LGPLv2.1',
    description='Testing a Linux distribution',
    long_description=open('README.txt').read(),
)
