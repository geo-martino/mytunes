.. _installation:

Installation
------------

Install through pip using one of the following commands:

.. code-block:: bash

   pip install mytunes
   # or
   python -m pip install mytunes

This package has various optional dependencies for optional functionality.
Should you wish to take advantage of some or all of this functionality, install the optional dependencies as follows:

.. code-block:: bash

   pip install mytunes[all]  # installs all optional dependencies

   pip install mytunes[bars]  # dependencies for displaying progress bars on longer running processes
   pip install mytunes[musicbee]  # dependencies for working with a local MusicBee library and its playlist types
   pip install mytunes[sqlite]  # dependencies for working with a SQLite cache backend for caching API responses

   # or you may install any combination of these e.g.
   pip install mytunes[bars,images,musicbee]
