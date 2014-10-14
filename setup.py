from distutils.core import setup

setup(
    name='mossum',
    version='0.1.0',
    author='Hjalti Magnússon',
    author_email='hjaltmann@gmail.com',
    packages=['mossum'],
    scripts=['bin/mossum'],
    url='https://github.com/hjalti/mossum',
    license='LICENSE',
    description='',
    long_description='',
    install_requires=[
        "beautifulsoup4>=4.3.2",
        "fake-factory>=0.4.2",
        "html5lib>=0.999",
        "ipython>=2.3.0",
        "pydot>=1.0.29",
        "pyparsing>=2.0.2",
        "requests>=2.4.3",
        "six>=1.8.0",
    ],
    dependency_links = [
        "git+https://github.com/nlhepler/pydot/#egg=pydot-1.0.29"
    ],
)

