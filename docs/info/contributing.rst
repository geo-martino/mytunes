============
Contributing
============
To contribute to MyTunes, follow these steps:


Setup your development environment
==================================
1. Ensure you have Python3.12 or greater installed on your system.
2. Go to the `GitHub repository <https://github.com/geo-martino/mytunes>`_ and fork the project by clicking
   **Fork** in the top left:

   .. image:: images/contributing/fork.png

3. Go to the page of your GitHub account's fork of MyTunes and
   `clone the repository <https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository>`_:

   .. image:: images/contributing/clone.png

4. In a terminal, navigate to the directory of the cloned project and create a virtual environment for MyTunes:

   .. code-block:: bash

      python -m venv .venv

5. Install the dependencies with ``pip`` for the changes you wish to make as follows:

   .. code-block:: bash

      pip install -e '.[test]'  # installs just the core package + the required dependencies for testing
      pip install -e '.[dev]'  # installs the `test` dependencies + dependencies for linting and other development uses
      pip install -e '.[docs]'  # installs just the core package + the required dependencies for building documentation

6. Optionally, to ensure inheritance diagrams in the documentation render correctly, install graphviz.
   See `here <https://graphviz.org/download/>`_ for platform-specific info on how to install graphviz.

Making changes and testing
==========================
Create a new branch in your local git project and commit changes to this branch as you develop.

All tests are located within ``./tests``.
If you make any changes to the functionality of the package, you **must** either modify or add new tests for these changes.
To run tests, you must have installed either the ``test`` or ``dev`` optional dependencies and run ``pytest`` e.g.:

.. code-block:: bash

   pytest
   # OR
   pytest path/to/test/file.py

As part of code validation, your code will be required to pass certain linting checks.
This project uses flake8 to help give an indication as to the quality of your code.
For the current checks that your code will be expected to pass,
please check the ``.flake8`` config file in the root of the project.

To run these checks locally, simply run the following command in a terminal:

.. code-block:: bash

   flake8

Submitting your changes for review
==================================
1. Ensure all tests pass locally first.
2. Add any changes you made to the :ref:`release-history`.
3. Go to your forked repository and open a pull request for your branch.

   .. image:: images/contributing/pr_new.png

   .. image:: images/contributing/pr_create1.png

4. Add a title, a motivation for your changes, and the changes you have made.
   This can just be a copy-paste from your release history notes.

   .. image:: images/contributing/pr_create2.png

5. Wait for a review and make any necessary changes.
6. Have your changes committed 🎉
