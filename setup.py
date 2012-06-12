from distutils.core import setup

setup(
    name='igor',
    version='0.1.0',
    author='Fabian Deutsch',
    author_email='fabiand@fedoraproject.org',
    packages=['igor', 'igor.test'],
    scripts=['bin/igord','bin/status2report.py'],
    url='http://www.gitorious.org/ovirt/igord',
    license='LGPLv2.1',
    description='Testing a Linux distribution',
    long_description=open('README.txt').read(),
)

