from distutils.core import setup

setup(
    name='igor',
    version='0.1.0',
    author='Fabian Deutsch',
    author_email='fabiand@fedoraproject.org',
    packages=['igor', 'igor.test'],
    package_data={'igor': ['data/*.xsl']},
    scripts=['bin/igord', 'bin/igor-status-to-report'],
    data_files=[('/lib/systemd/system', ['igord.service'])],
    url='http://www.gitorious.org/ovirt/igord',
    license='LGPLv2.1',
    description='Testing a Linux distribution',
    long_description=open('README.txt').read(),
)
