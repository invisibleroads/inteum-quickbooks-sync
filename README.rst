inteum-quickbooks-sync
======================
Here is an unfinished project for importing invoice data from LEDES spreadsheets into QuickBooks and synchronizing these records with Inteum.  It is mostly complete, but there are some bugs in the way that the program updates existing QuickBooks data.  I stopped working on the project in November 2011 when I realized that the approach was not sustainable.

Requirements
------------
- QuickBooks desktop application
- QuickBooks SDK
- Inteum desktop application
- `win32com <http://sourceforge.net/projects/pywin32/>`_
- `sqlalchemy <http://www.sqlalchemy.org/>`_

Usage
-----
::

    python go.py
