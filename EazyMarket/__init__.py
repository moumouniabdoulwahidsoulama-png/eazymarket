"""
Pilote MySQL pour les hébergements mutualisés.

`mysqlclient` doit être compilé, ce qui échoue souvent sur un cPanel.
PyMySQL est écrit en Python pur : il s'installe partout et se fait passer
pour mysqlclient auprès de Django.
"""

try:  # pragma: no cover - dépend de l'environnement
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover
    pass
